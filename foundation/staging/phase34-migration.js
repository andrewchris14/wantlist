// Fixed supplemental migration, atomic and CAS-guarded. No arbitrary SQL input.
import {samples,selectionSha256} from './phase34-samples.js';
const marker='phase34-historical-recovery-v1',aggregate='display-brewers-bobblehead-wantlist';
const fail=()=>{const e=Error('Migration conflicts with staging edits; no changes applied');e.code='CONFLICT';throw e;};
export async function recoverHistoricalSamples(db){
 if(await db.prepare('SELECT value FROM foundation_meta WHERE key=?').bind(marker).first())return {migrated:false,replayed:true};
 const old=await db.prepare(`SELECT r.id,r.revision,r.deleted_at,p.baseline_json,(SELECT count(*) FROM change_history WHERE record_id=r.id) history_count FROM records r JOIN provenance p ON p.record_id=r.id WHERE r.id=?`).bind(aggregate).first();
 if(!old||old.revision!==1||old.deleted_at||old.history_count)fail();
 const source=JSON.parse(old.baseline_json);
 if(source.source_records?.length!==26||source.display_members?.length!==26)fail();
 const existing=(await db.prepare(`SELECT r.id,r.revision,r.deleted_at,p.baseline_sha256,(SELECT count(*) FROM change_history WHERE record_id=r.id) history_count FROM records r LEFT JOIN provenance p ON p.record_id=r.id WHERE r.id IN (SELECT value FROM json_each(?))`).bind(JSON.stringify(samples.map(r=>r.id))).all()).results;
 const byId=new Map(existing.map(r=>[r.id,r]));
 for(const r of existing){const s=samples.find(s=>s.id===r.id);if(r.revision!==1||r.deleted_at||r.history_count||r.baseline_sha256!==s.source_sha256)fail();}
 const stamp=new Date().toISOString(),statements=[];
 // Atomic guard catches edits arriving after our read, including member records.
 statements.push(db.prepare(`INSERT INTO foundation_meta VALUES(?,CASE WHEN (SELECT revision FROM records WHERE id=?)=1 AND NOT EXISTS(SELECT 1 FROM change_history WHERE record_id=?) AND NOT EXISTS(SELECT 1 FROM records WHERE id IN (SELECT value FROM json_each(?)) AND (revision!=1 OR deleted_at IS NOT NULL)) THEN '1' ELSE NULL END)`).bind(marker,aggregate,aggregate,JSON.stringify(samples.map(r=>r.id))));
 const rows={records:[],provenance:[],record_groups:[],items:[],public_records:[],change_history:[]};
 const batchId='phase34-supplemental';
 statements.push(db.prepare('INSERT INTO import_batches VALUES(?,?,?,?,?)').bind(batchId,'33ffe970b2c9772df1144556c002dd706022a20f',selectionSha256,JSON.stringify({derivation:'Phase 3B.4 owner approvals and original bobblehead listings',sample_only:true,records:33}),stamp));
 for(const s of samples){
  const previous=byId.get(s.id),revision=previous?2:1;
  if(previous){
   statements.push(db.prepare('UPDATE records SET content_json=json_set(content_json,\'$.display_category\',?,\'$.display_year\',?),list_type=?,revision=2,updated_at=? WHERE id=?').bind(s.content.display_category,s.content.display_year||null,s.list_type,stamp,s.id));
   statements.push(db.prepare('UPDATE record_groups SET list_type=? WHERE record_id=? AND kind=\'primary\'').bind(s.list_type,s.id));
  }else{
   rows.records.push([s.id,batchId,s.list_type,JSON.stringify(s.content),1,stamp,stamp,null]);
   rows.provenance.push([s.id,JSON.stringify(s.source),s.source_sha256,JSON.stringify(s.source.source_refs)]);
   for(const g of s.groups){
    rows.record_groups.push([g.id,s.id,g.kind,g.position,g.list_type,JSON.stringify(g.metadata),JSON.stringify(g.keys)]);
    for(const i of g.entries)rows.items.push([i.id,g.id,i.field_key,i.position,i.value,i.state,i.actionable,i.limitation,null,null,null]);
   }
  }
  const projection={...s.content,list_type:s.list_type,revision,updated_at:stamp,deleted:false,projection_version:2,groups:s.groups.map(g=>({id:g.id,kind:g.kind,list_type:g.list_type,...Object.fromEntries(['label','description','notes','source_list_type'].filter(k=>k in g.metadata).map(k=>[k,g.metadata[k]])),entries:g.entries.map(({limitation,...i})=>i)}))};
  rows.public_records.push([s.id,revision,stamp,0,JSON.stringify(projection)]);
  rows.change_history.push([crypto.randomUUID(),s.id,null,'phase34-migration','historical_recovery',JSON.stringify({existing:!!previous,revision:previous?.revision}),JSON.stringify({classification:s.list_type,source_sha256:s.source_sha256,_record_revision:revision}),stamp]);
 }
 // Bound every statement below D1's 100-bind limit, then one transaction.
 for(const [table,values] of Object.entries(rows)){
  if(!values.length)continue;const width=values[0].length,size=Math.floor(99/width);
  for(let i=0;i<values.length;i+=size){const part=values.slice(i,i+size);const tail=table==='public_records'?' ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at,deleted=excluded.deleted,public_json=excluded.public_json':'';
   statements.push(db.prepare('INSERT INTO '+table+' VALUES '+part.map(()=>'('+Array(width).fill('?').join(',')+')').join(',')+tail).bind(...part.flat()));
  }
 }
 statements.push(db.prepare('UPDATE records SET deleted_at=?,revision=2,updated_at=? WHERE id=?').bind(stamp,stamp,aggregate));
 statements.push(db.prepare(`UPDATE public_records SET deleted=1,revision=2,updated_at=?,public_json=json_set(public_json,'$.deleted',json('true'),'$.revision',2,'$.updated_at',?) WHERE record_id=?`).bind(stamp,stamp,aggregate));
 statements.push(db.prepare('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)').bind(crypto.randomUUID(),aggregate,'phase34-migration','archive_consolidation',JSON.stringify({revision:1,display_members:source.display_members}),JSON.stringify({restored_ids:samples.filter(r=>r.content.display_category==='Brewers Bobblehead Wantlist').map(r=>r.id),_record_revision:2}),stamp));
 if(statements.length>44)throw Error('Migration exceeds staging Free query budget');
 try{await db.batch(statements);}catch(e){if(/constraint/i.test(e.message))fail();throw e;}
 return {migrated:true,added_records:samples.length-existing.length,bobblehead_listings:26,approved_classifications:7,statements:statements.length,aggregate_archived:true};
}
