import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {localD1} from './d1-local-adapter.mjs';import {samples} from '../staging/phase34-samples.js';import {recoverHistoricalSamples} from '../staging/phase34-migration.js';
function fixture(){const db=localD1();db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',0,1)");
 const id='display-brewers-bobblehead-wantlist',stamp=new Date().toISOString(),members=samples.filter(s=>s.content.display_category==='Brewers Bobblehead Wantlist');
 db.sqlite.prepare('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)').run(id,'want_list',JSON.stringify({id,set_name:'Brewers Bobblehead Wantlist'}),stamp,stamp);
 db.sqlite.prepare('INSERT INTO provenance VALUES(?,?,?,?)').run(id,JSON.stringify({source_records:members.map(s=>s.source),display_members:members.map(s=>s.id)}),'original-source','[]');
 db.sqlite.prepare('INSERT INTO public_records VALUES(?,1,?,0,?)').run(id,stamp,JSON.stringify({id,list_type:'want_list',groups:[]}));return db;}
test('atomic supplemental restoration has 26 separate bobbleheads, 7 approved samples and exact untouched provenance; rerun does not overwrite edits',async()=>{
 const db=fixture();try{
 const result=await recoverHistoricalSamples(db);assert.equal(result.added_records,33);assert.ok(result.statements<=44);assert.equal(result.bobblehead_listings,26);assert.equal(db.sqlite.prepare("SELECT count(*) n FROM records WHERE deleted_at IS NULL AND json_extract(content_json,'$.display_category')='Brewers Bobblehead Wantlist'").get().n,26);
 for(const s of samples){const r=db.sqlite.prepare('SELECT * FROM records WHERE id=?').get(s.id);assert.equal(r.list_type,s.list_type);const p=db.sqlite.prepare('SELECT baseline_json FROM provenance WHERE record_id=?').get(s.id);assert.deepEqual(JSON.parse(p.baseline_json),s.source);}
 db.sqlite.prepare('UPDATE records SET revision=2 WHERE id=?').run(samples[0].id);assert.equal((await recoverHistoricalSamples(db)).replayed,true);assert.equal(db.sqlite.prepare('SELECT revision FROM records WHERE id=?').get(samples[0].id).revision,2);
 }finally{db.close();}
});
test('aggregate edit blocks migration and a constraint failure rolls back all inserted history/projections/source rows',async()=>{
 const db=fixture();try{
 db.sqlite.exec("UPDATE records SET revision=2 WHERE id='display-brewers-bobblehead-wantlist'");await assert.rejects(recoverHistoricalSamples(db));assert.equal(db.sqlite.prepare('SELECT count(*) n FROM records').get().n,1);
 db.sqlite.exec("UPDATE records SET revision=1; CREATE TRIGGER fail_insert BEFORE INSERT ON items BEGIN SELECT RAISE(ABORT,'CHECK constraint injected'); END;");await assert.rejects(recoverHistoricalSamples(db));assert.equal(db.sqlite.prepare('SELECT count(*) n FROM records').get().n,1);assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n,0);assert.equal(db.sqlite.prepare('SELECT count(*) n FROM import_batches').get().n,0);assert.equal(db.sqlite.prepare("SELECT count(*) n FROM foundation_meta WHERE key LIKE 'phase34%'").get().n,0);
 }finally{db.close();}
});
