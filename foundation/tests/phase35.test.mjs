import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {localD1} from './d1-local-adapter.mjs';import {mutate,openRecord,publicProjection} from '../staging/records.js';import {recentOwner} from '../staging/owner.js';import {browseRecord,logicalInventories,sortedEntries,recordYear,yearInfo} from '../../owner/model.js';
const fixture=()=>{const db=localD1();db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',0,1)");return db;};
const act=(db,input)=>mutate(db,{request_id:crypto.randomUUID(),...input});
test('Save is atomic, idempotent, CAS guarded, persists order and Pending, and Undo restores exact entries',async()=>{const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Draft',display_category:'OBC Wantlist'},wanted:['3','1','2']});const full=await openRecord(db,r.record_id),g=full.groups[0];
 const body={op:'edit_session',record_id:r.record_id,revision:r.revision,request_id:crypto.randomUUID(),metadata:{year:'1990(?)',entry_order:'original',notes:['Keep']},changes:[{id:g.entries[0].id,state:'pending',removed:false},{id:g.entries[1].id,state:'wanted',removed:true}],additions:[{value:'KB-2',field_key:'card_numbers',group_id:g.id,state:'wanted'}]};
 r=await mutate(db,body);assert.equal((await mutate(db,body)).replayed,true);assert.equal(r.revision,2);
 const saved=await openRecord(db,r.record_id),projection=publicProjection(saved),view=browseRecord(projection);
 assert.equal(projection.entry_order,'original');assert.equal(saved.content.year,'1990(?)');assert.equal(view.logical_inventories[0].entries.filter(i=>i.state==='pending')[0].value,'3');assert.equal(saved.groups.length,1);
 await assert.rejects(act(db,{...body,request_id:undefined,revision:1}));
 const h=(await recentOwner(db)).changes[0];assert.equal(h.undoable,true);r=await act(db,{op:'undo',record_id:r.record_id,revision:2,history_id:h.id});
 const undone=await openRecord(db,r.record_id);assert.deepEqual(undone.groups[0].entries.filter(i=>!i.deleted_at).map(i=>[i.value,i.state]),[['3','wanted'],['1','wanted'],['2','wanted']]);assert.equal(undone.content.entry_order,null);
 }finally{db.close();}});
test('pending cancellation and confirmed removal create no HAVE group; additions can be pending in same Save',async()=>{const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Pending'},wanted:['2']});const g=(await openRecord(db,r.record_id)).groups[0];
 r=await act(db,{op:'edit_session',record_id:r.record_id,revision:1,changes:[{id:g.entries[0].id,state:'pending',removed:false}],additions:[{value:'15',field_key:'card_numbers',group_id:g.id,state:'pending'}]});
 let full=await openRecord(db,r.record_id);assert.ok(full.groups[0].entries.every(i=>i.state==='pending'));
 await assert.rejects(act(db,{op:'edit_session',record_id:r.record_id,revision:r.revision,changes:[{id:g.entries[0].id,state:'pending',removed:true}]}));
 r=await act(db,{op:'edit_session',record_id:r.record_id,revision:r.revision,changes:[{id:g.entries[0].id,state:'wanted',removed:false}]});
 full=await openRecord(db,r.record_id);assert.equal(full.groups.length,1);assert.equal(full.groups[0].entries[0].state,'wanted');
 }finally{db.close();}});
test('logical photo inventory includes historic and new names while group IDs and source order remain intact',()=>{
 const r={list_type:'have_list',content:{display_category:'Milwaukee 8x10 List'},groups:[{id:'source',kind:'sublist',list_type:'have_list',entries:[{id:'a',value:'Aaron, H',state:'owned'},{id:'y',value:'Yount, R',state:'owned'}]},{id:'new',kind:'primary',list_type:'have_list',entries:[{id:'m',value:'Megill, T',state:'owned'}]}]};
 const g=logicalInventories(r)[0];assert.equal(g.entries.length,3);assert.deepEqual(sortedEntries(g.entries).map(i=>i.value),['Aaron, H','Megill, T','Yount, R']);assert.deepEqual(sortedEntries(g.entries,true).map(i=>i.value),['Aaron, H','Yount, R','Megill, T']);assert.deepEqual(g.entries.map(i=>i.group_id),['source','source','new']);
});
test('WANT/HAVE conversion needs explicit new identifiers, keeps source group meaning, and can Undo',async()=>{const db=fixture();try{
 let r=await act(db,{op:'create',list_type:'have_list',metadata:{set_name:'Five'},owned:['1','3','5']});const g=(await openRecord(db,r.record_id)).groups[0];
 await assert.rejects(act(db,{op:'edit_session',record_id:r.record_id,revision:1,list_type:'want_list',confirm_conversion:true}));
 r=await act(db,{op:'edit_session',record_id:r.record_id,revision:1,list_type:'want_list',confirm_conversion:true,changes:g.entries.map(i=>({id:i.id,state:i.state,removed:true})),additions:[{value:'6',state:'wanted',field_key:'card_numbers',group_id:'new-primary'}]});
 let f=await openRecord(db,r.record_id);assert.equal(f.groups[0].list_type,'have_list');assert.deepEqual(browseRecord(publicProjection(f)).logical_inventories.flatMap(g=>g.entries.map(i=>i.value)),['6']);
 const h=(await recentOwner(db)).changes[0];await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:h.id});f=await openRecord(db,r.record_id);assert.equal(f.list_type,'have_list');assert.equal(f.groups[0].entries.filter(i=>!i.deleted_at).length,3);
 }finally{db.close();}});
test('500 draft changes use bounded statements and no unrelated inventory serialization; failures roll back',async()=>{const db=fixture();try{
 let r=await act(db,{op:'create',metadata:{set_name:'Large'},wanted:['source']});const g=(await openRecord(db,r.record_id)).groups[0];let max=0;const measured={prepare:db.prepare,batch:async s=>{max=Math.max(max,s.length);return db.batch(s);}};
 r=await act(measured,{op:'edit_session',record_id:r.record_id,revision:1,additions:Array.from({length:500},(_,n)=>({value:'KB-'+n,state:'wanted',field_key:'card_numbers',group_id:g.id}))});assert.ok(max<=9);assert.equal((await openRecord(db,r.record_id)).groups[0].entries.length,501);
 await assert.rejects(act(db,{op:'edit_session',record_id:r.record_id,revision:r.revision,metadata:{display_category:'Not registered'},changes:[{id:g.entries[0].id,state:'wanted',removed:true}]}));assert.equal((await openRecord(db,r.record_id)).revision,r.revision);assert.equal((await openRecord(db,r.record_id)).groups[0].entries[0].deleted_at,null);
 }finally{db.close();}});

test('explicit owner year correction supersedes historical uncertain label and Undo restores it',async()=>{const db=fixture();try{let r=await act(db,{op:'create',metadata:{set_name:'1990(?) Topps',year:'1990'},wanted:['1']});db.sqlite.prepare("UPDATE records SET content_json=json_set(content_json,'$.display_year','1990(?)') WHERE id=?").run(r.record_id);db.sqlite.prepare("UPDATE public_records SET public_json=json_set(public_json,'$.display_year','1990(?)') WHERE record_id=?").run(r.record_id);r=await act(db,{op:'edit_session',record_id:r.record_id,revision:1,metadata:{year:'1990'}});let full=await openRecord(db,r.record_id);assert.equal(recordYear(full.content),'1990');assert.equal(yearInfo(recordYear(full.content)).label,null);const h=(await recentOwner(db)).changes[0];await act(db,{op:'undo',record_id:r.record_id,revision:r.revision,history_id:h.id});full=await openRecord(db,r.record_id);assert.equal(recordYear(full.content),'1990(?)');}finally{db.close();}});
