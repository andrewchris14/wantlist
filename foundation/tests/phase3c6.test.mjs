import test from 'node:test';
import assert from 'node:assert/strict';
import {performanceFixture,maximumBody,recordId,groupId} from './performance-fixture.mjs';
import {mutate} from '../staging/records.js';
import {ownerRecord,ownerRecordJSON} from '../staging/owner.js';
import worker from '../staging/worker.mjs';
const act=(db,body)=>mutate(db,{request_id:crypto.randomUUID(),record_id:recordId,...body});
const items=db=>db.sqlite.prepare('SELECT * FROM items WHERE group_id=? ORDER BY id').all(groupId).map(x=>({...x}));
const history=db=>db.sqlite.prepare("SELECT id FROM change_history WHERE record_id=? ORDER BY rowid DESC LIMIT 1").get(recordId).id;
const projection=db=>JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(recordId).public_json);

test('500 changes plus 500 additions: one revision, replay, exact Undo and retained removed provenance',async()=>{
 const db=performanceFixture();try{
 const before=items(db),content=db.sqlite.prepare('SELECT content_json FROM records WHERE id=?').get(recordId).content_json;
 const body=maximumBody();const result=await mutate(db,body);
 assert.equal(result.revision,2);assert.equal((await mutate(db,body)).replayed,true);
 assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history WHERE record_id=?').get(recordId).n,1);
 const all=items(db);assert.equal(all.filter(i=>!i.deleted_at).length,1026);assert.equal(all.filter(i=>i.state==='pending').length,500);
 const added=all.filter(i=>!before.some(old=>old.id===i.id));assert.equal(added.length,500);
 assert.deepEqual(added.map(i=>i.position).sort((a,b)=>a-b),Array.from({length:500},(_,n)=>2029+n));
 assert.deepEqual(all.filter(i=>before.slice(526).some(old=>old.id===i.id)),before.slice(526));
 assert.equal(projection(db).revision,2);
 await assert.rejects(act(db,{op:'edit_session',revision:1,metadata:{notes:['Stale']}}));
 const undo={op:'undo',revision:2,history_id:history(db),request_id:crypto.randomUUID()};await act(db,undo);
 assert.equal((await act(db,undo)).replayed,true);
 assert.deepEqual(items(db).filter(i=>before.some(old=>old.id===i.id)),before);
 assert.ok(items(db).filter(i=>added.some(old=>old.id===i.id)).every(i=>i.deleted_at));
 assert.equal(db.sqlite.prepare('SELECT content_json FROM records WHERE id=?').get(recordId).content_json,content);
 assert.equal(projection(db).groups[0].entries.length,526);
 }finally{db.close();}
});

test('late batch failure rolls back items, revision, history, receipts and both public projections',async()=>{
 const db=performanceFixture();try{
 const tables=['records','record_groups','items','change_history','mutation_receipts','public_records','public_browse_index'];
 const snapshot=()=>tables.map(t=>JSON.stringify(db.sqlite.prepare('SELECT * FROM '+t+' ORDER BY rowid').all()));
 const before=snapshot();
 const failing={prepare:db.prepare,batch:statements=>db.batch([...statements,{execute(){throw Error('Synthetic late failure');}}])};
 await assert.rejects(mutate(failing,maximumBody()));assert.deepEqual(snapshot(),before);
 }finally{db.close();}
});

test('CAS race cannot publish a partial maximum Save',async()=>{
 const db=performanceFixture();try{
 const before=items(db);
 const racing={prepare:db.prepare,batch:statements=>{db.sqlite.prepare('UPDATE records SET revision=revision+1 WHERE id=?').run(recordId);return db.batch(statements);}};
 await assert.rejects(mutate(racing,maximumBody()));assert.deepEqual(items(db),before);
 assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n,0);
 assert.equal(projection(db).revision,1);
 }finally{db.close();}
});

test('header-only saves reuse index inventory; missing index repairs; duplicate and pending rules remain',async()=>{
 const db=performanceFixture();try{
 const initial=db.sqlite.prepare('SELECT index_json FROM public_browse_index WHERE record_id=?').get(recordId).index_json;
 await act(db,{op:'edit_session',revision:1,metadata:{notes:['Quote " slash \\ and Unicode é']}});
 const updated=JSON.parse(db.sqlite.prepare('SELECT index_json FROM public_browse_index WHERE record_id=?').get(recordId).index_json);
 assert.deepEqual(updated.items,JSON.parse(initial).items);
 assert.deepEqual(projection(db).notes,['Quote " slash \\ and Unicode é']);
 db.sqlite.prepare('DELETE FROM public_browse_index WHERE record_id=?').run(recordId);
 await act(db,{op:'edit_session',revision:2,metadata:{notes:['Repaired']}});
 assert.deepEqual(JSON.parse(db.sqlite.prepare('SELECT index_json FROM public_browse_index WHERE record_id=?').get(recordId).index_json).items,updated.items);
 await assert.rejects(act(db,{op:'edit_session',revision:3,additions:[{group_id:groupId,field_key:'items',state:'wanted',value:'Synthetic literal 1'}]}));
 await act(db,{op:'edit_session',revision:3,changes:[{id:'synthetic-item-000001',state:'pending',removed:false}]});
 await assert.rejects(act(db,{op:'edit_session',revision:4,changes:[{id:'synthetic-item-000001',state:'pending',removed:true}]}));
 await assert.rejects(mutate(db,maximumBody(4,501)));
 assert.equal((await ownerRecord(db,recordId)).revision,4);
 }finally{db.close();}
});

test('encoded owner response preserves field types, escaping, order and individual removed state without private blobs',async()=>{
 const db=performanceFixture(':memory:',3,1);try{
 db.sqlite.prepare('UPDATE record_groups SET metadata_json=? WHERE id=?').run(JSON.stringify({label:null,description:['Quoted "','é'],notes:'line\nline',private_blob:'Excluded'}),groupId);
 const response=JSON.parse(await ownerRecordJSON(db,recordId));assert.equal(response.groups[0].label,null);
 assert.deepEqual(response.groups[0].description,['Quoted "','é']);assert.equal(response.groups[0].notes,'line\nline');
 assert.equal(response.groups[0].private_blob,undefined);assert.equal(response.groups[0].entries.length,4);
 assert.deepEqual(response.groups[0].entries.map(x=>x.position),[0,1,2,3]);
 db.sqlite.prepare('UPDATE record_groups SET metadata_json=? WHERE id=?').run(JSON.stringify({label:true,notes:false}),groupId);
 const typed=await ownerRecord(db,recordId);assert.equal(typed.groups[0].label,true);assert.equal(typed.groups[0].notes,false);
 db.sqlite.prepare('UPDATE record_groups SET metadata_json=? WHERE id=?').run(JSON.stringify({notes:['Normal group note']}),groupId);
 await act(db,{op:'edit_session',revision:1,changes:[{id:'synthetic-item-000001',state:'wanted',removed:true}]});
 const removed=(await ownerRecord(db,recordId)).groups[0].entries.find(i=>i.id==='synthetic-item-000001');
 // Session removals remain session history, not legacy individually removed entries.
 assert.equal(removed.individually_removed,0);assert.ok(removed.deleted_at);
 assert.equal(await ownerRecordJSON(db,'missing'),null);
 }finally{db.close();}
});

test('full collection index paginates locally without 404 and unauthenticated owner calls remain blocked',async()=>{
 const db=performanceFixture(':memory:',1,0);try{
 const insert=db.sqlite.prepare('INSERT INTO public_records VALUES(?,1,?,0,?)');
 const record=db.sqlite.prepare('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)');
 for(let n=0;n<3393;n++){const id='synthetic-page-'+String(n).padStart(5,'0'),body=JSON.stringify({id,list_type:'want_list',set_name:'Synthetic',groups:[]});record.run(id,'want_list',body,'synthetic','synthetic');insert.run(id,'synthetic',body);}
 const env={STAGING_ONLY:'true',STAGING_EDITOR:'true',DB:db};let cursor='',count=0,pages=0;
 do{const r=await worker.fetch(new Request('https://isolated.invalid/public/index?after='+encodeURIComponent(cursor)),env);assert.equal(r.status,200);const data=await r.json();count+=data.records.length;cursor=data.next;pages++;}while(cursor);
 assert.equal(count,3394);assert.equal(pages,7);
 assert.equal((await worker.fetch(new Request('https://isolated.invalid/owner/record?id='+recordId),env)).status,401);
 }finally{db.close();}
});

test('addition positions retain global ordinal across mixed groups and Undo preserves other groups',async()=>{
 const db=performanceFixture(':memory:',3,0);try{
 const other=recordId+'-mixed';db.sqlite.prepare('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)').run(other,recordId,'mixed',0,'want_list','{}','["items"]');
 db.sqlite.prepare('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)').run('synthetic-mixed-original',other,'items',7,'Mixed original','wanted');
 const before=JSON.stringify(db.sqlite.prepare('SELECT * FROM record_groups WHERE record_id=? ORDER BY id').all(recordId));
 await act(db,{op:'edit_session',revision:1,additions:[{group_id:groupId,field_key:'items',state:'wanted',value:'Added primary'},{group_id:other,field_key:'items',state:'wanted',value:'Added mixed'},{group_id:groupId,field_key:'card_numbers',state:'wanted',value:'Another primary'}]});
 assert.equal(db.sqlite.prepare('SELECT position FROM items WHERE value=?').get('Added primary').position,3);
 assert.equal(db.sqlite.prepare('SELECT position FROM items WHERE value=?').get('Added mixed').position,9);
 assert.equal(db.sqlite.prepare('SELECT position FROM items WHERE value=?').get('Another primary').position,5);
 await act(db,{op:'undo',revision:2,history_id:history(db)});
 assert.equal(JSON.stringify(db.sqlite.prepare('SELECT * FROM record_groups WHERE record_id=? ORDER BY id').all(recordId)),before);
 assert.equal(db.sqlite.prepare('SELECT deleted_at FROM items WHERE id=?').get('synthetic-mixed-original').deleted_at,null);
 }finally{db.close();}
});
