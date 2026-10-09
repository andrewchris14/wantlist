import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {localD1} from './d1-local-adapter.mjs';import {mutate,openRecord} from '../staging/records.js';import {categories,categoryMutation} from '../staging/categories.js';import {recentOwner} from '../staging/owner.js';
const fixture=()=>{const db=localD1();db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',0,1)");return db;};
const act=(db,input)=>mutate(db,{request_id:crypto.randomUUID(),...input});const cat=(db,input)=>categoryMutation(db,{request_id:crypto.randomUUID(),...input});
test('owner categories persist; rename, move, safe delete, uniqueness, receipts and audit',async()=>{
 const db=fixture();try{
 assert.equal((await categories(db)).length,7);
 let c=await cat(db,{op:'create',name:'Twilight Zone Actor Wantlist'});
 const body={op:'rename',id:c.id,revision:c.revision,name:'Twilight Zone Actors',request_id:crypto.randomUUID()};c=await categoryMutation(db,body);assert.equal((await categoryMutation(db,body)).replayed,true);
 let r=await act(db,{op:'create',metadata:{set_name:'Actor cards',display_category:'Twilight Zone Actors'},wanted_names:['Rod Serling']});
 await assert.rejects(cat(db,{op:'remove',id:c.id,revision:c.revision}));
 c=await cat(db,{op:'rename',id:c.id,revision:c.revision,name:'Actors'});let full=await openRecord(db,r.record_id);assert.equal(full.content.display_category,'Actors');assert.equal(full.revision,2);
 const projection=JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(r.record_id).public_json);assert.equal(projection.display_category,'Actors');assert.equal(projection.revision,full.revision);
 r=await act(db,{op:'edit',record_id:r.record_id,revision:2,metadata:{display_category:'OBC Wantlist'}});assert.equal((await openRecord(db,r.record_id)).content.display_category,'OBC Wantlist');
 const moveHistory=(await recentOwner(db)).changes[0];r=await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:moveHistory.id});assert.equal((await openRecord(db,r.record_id)).content.display_category,'Actors');
 await assert.rejects(cat(db,{op:'remove',id:c.id,revision:c.revision}));r=await act(db,{op:'edit',record_id:r.record_id,revision:r.revision,metadata:{display_category:'UV Wantlist'}});await cat(db,{op:'remove',id:c.id,revision:c.revision});assert.equal((await categories(db)).length,7);
 await assert.rejects(cat(db,{op:'create',name:'obc wantlist'}));await assert.rejects(cat(db,{op:'rename',id:'historical-obc',revision:1,name:'Oops'}));
 await assert.rejects(act(db,{op:'create',metadata:{set_name:'Unknown category',display_category:'No such category'}}));
 assert.equal(db.sqlite.prepare('SELECT count(*) n FROM category_history').get().n,4);
 }finally{db.close();}
});
test('Bulk Edit replaces active membership, preserves pending and opaque entries, unrelated groups, notes and Undo',async()=>{
 const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Mixed',notes:['Keep note']},wanted:['1','2','10'],owned_names:['Rod Serling']});let full=await openRecord(db,r.record_id),g=full.groups.find(g=>g.list_type==='want_list'),pending=g.entries[1];
 r=await act(db,{op:'transition',record_id:r.record_id,revision:r.revision,item_id:pending.id,state:'pending'});
 const body={op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:g.id,list_type:'want_list',values:['2','3'],request_id:crypto.randomUUID()};r=await mutate(db,body);assert.equal((await mutate(db,body)).replayed,true);
 full=await openRecord(db,r.record_id);g=full.groups.find(x=>x.id===g.id);assert.equal(g.entries.find(i=>i.value==='2').id,pending.id);assert.equal(g.entries.find(i=>i.value==='2').state,'pending');assert.deepEqual(g.entries.filter(i=>!i.deleted_at).map(i=>i.value),['2','3']);assert.equal(full.groups.find(g=>g.list_type==='have_list').entries[0].value,'Rod Serling');assert.deepEqual(full.content.notes,['Keep note']);
 await assert.rejects(act(db,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:g.id,list_type:'want_list',values:['3']}));
 let h=(await recentOwner(db)).changes[0];r=await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:h.id});full=await openRecord(db,r.record_id);assert.equal(full.groups.find(x=>x.id===g.id).entries.find(i=>i.id===pending.id).state,'pending');
 r=await act(db,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:g.id,list_type:'want_list',values:['10'],confirm_pending_removal:true});assert.equal((await openRecord(db,r.record_id)).groups.find(x=>x.id===g.id).entries.filter(i=>!i.deleted_at).length,1);
 }finally{db.close();}
});
test('conversion saves metadata atomically, preserves meaning, supports Undo; COMPLETE keeps recoverable entries',async()=>{
 const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Ten cards',notes:['Original']},list_type:'have_list',owned:['1','3','5','7','9']});let full=await openRecord(db,r.record_id),gid=full.groups[0].id;
 r=await act(db,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:gid,list_type:'want_list',values:['6','8','10'],metadata:{set_name:'Updated',notes:['New']}});full=await openRecord(db,r.record_id);assert.equal(full.content.set_name,'Updated');assert.deepEqual(full.groups[0].entries.filter(i=>!i.deleted_at).map(i=>[i.value,i.state]),[['6','wanted'],['8','wanted'],['10','wanted']]);
 let h=(await recentOwner(db)).changes[0];r=await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:h.id});full=await openRecord(db,r.record_id);assert.equal(full.content.set_name,'Ten cards');assert.deepEqual(full.content.notes,['Original']);assert.equal(full.list_type,'have_list');
 await assert.rejects(act(db,{op:'edit',record_id:r.record_id,revision:r.revision,list_type:'complete'}));
 r=await act(db,{op:'edit',record_id:r.record_id,revision:r.revision,list_type:'complete',confirm_complete:true});assert.equal((await openRecord(db,r.record_id)).groups[0].entries.filter(i=>!i.deleted_at).length,5);
 await assert.rejects(act(db,{op:'add',record_id:r.record_id,revision:r.revision,state:'owned',values:['11']}));
 h=(await recentOwner(db)).changes[0];r=await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:h.id});assert.equal((await openRecord(db,r.record_id)).list_type,'have_list');
 }finally{db.close();}
});
test('large old inventories remain in D1 and 500 new entries stay under the Free per-request SQL budget',async()=>{
 const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Large'},wanted:['original']});let full=await openRecord(db,r.record_id),g=full.groups[0];
 const insert=db.sqlite.prepare('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)');for(let n=1;n<=5000;n++)insert.run('large-'+n,g.id,'card_numbers',n,String(n),'wanted');
 full=await openRecord(db,r.record_id);const {publicProjection}=await import('../staging/records.js');db.sqlite.prepare('UPDATE public_records SET public_json=? WHERE record_id=?').run(JSON.stringify(publicProjection(full)),r.record_id);
 let boundRows=0,maxBatch=0;const wrap=s=>({bind(...args){return wrap(s.bind(...args));},async first(){return s.first();},async all(){const out=await s.all();boundRows=Math.max(boundRows,out.results.length);return out;},raw:s});
 const measured={prepare(sql){return wrap(db.prepare(sql));},async batch(st){maxBatch=Math.max(maxBatch,st.length);return db.batch(st.map(s=>s.raw));}};
 r=await act(measured,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:g.id,list_type:'want_list',values:['2','10','KB-2']});assert.ok(boundRows<=3);assert.equal((await openRecord(db,r.record_id)).groups[0].entries.filter(i=>!i.deleted_at).length,3);
 r=await act(measured,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:g.id,list_type:'want_list',values:Array.from({length:500},(_,i)=>'fresh-'+i)});assert.ok(maxBatch<=44);assert.equal((await openRecord(db,r.record_id)).groups[0].entries.filter(i=>!i.deleted_at).length,500);
 }finally{db.close();}
});
test('an empty WANT/HAVE conversion requires explicit confirmation; an inventory cannot use that shortcut',async()=>{
 const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Empty'}});
 await assert.rejects(act(db,{op:'edit',record_id:r.record_id,revision:r.revision,list_type:'have_list'}));
 r=await act(db,{op:'edit',record_id:r.record_id,revision:r.revision,list_type:'have_list',confirm_empty_conversion:true});assert.equal((await openRecord(db,r.record_id)).list_type,'have_list');
 r=await act(db,{op:'add',record_id:r.record_id,revision:r.revision,state:'owned',values:['1']});await assert.rejects(act(db,{op:'edit',record_id:r.record_id,revision:r.revision,list_type:'want_list',confirm_empty_conversion:true}));
 }finally{db.close();}
});
test('conversion cannot duplicate fixed photo/player sections through metadata',async()=>{
 const db=fixture();try{const r=await act(db,{op:'create',metadata:{set_name:'Ordinary'},wanted:['1']}),full=await openRecord(db,r.record_id);
 await assert.rejects(act(db,{op:'replace_list',record_id:r.record_id,revision:r.revision,group_id:full.groups[0].id,list_type:'have_list',values:['2'],metadata:{display_category:'Milwaukee 8x10 List'}}));
 assert.equal((await openRecord(db,r.record_id)).list_type,'want_list');
 }finally{db.close();}
});
