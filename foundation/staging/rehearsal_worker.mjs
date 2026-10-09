// Local-only full-scale projection/edit diagnostics. Node timings are NOT Cloudflare CPU.
import {writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {localD1} from '../tests/d1-local-adapter.mjs';
import {openRecord,publicProjection,mutate} from './records.js';
import {browseRecord,effectiveListType,effectiveCategory,logicalInventories,sortedEntries,yearInfo,recordYear,currentNotesText} from '../../owner/model.js';
import {recentOwner} from './owner.js';
const db=localD1('work/phase3c1-full.sqlite',false),observations=[];
db.sqlite.exec("INSERT OR IGNORE INTO staging_import_state VALUES(1,'isolated','isolated',3394,1)");
const measure=async(label,operation)=>{const start=performance.now(),cpu=process.cpuUsage();const result=await operation();const used=process.cpuUsage(cpu);observations.push({operation:label,node_process_cpu_ms:(used.user+used.system)/1000,local_wall_ms:performance.now()-start});return result;};
const ids=db.sqlite.prepare('SELECT id FROM records ORDER BY id').all();
const projectionRecords=[];
await measure('project_all_3394',async()=>{
 for(const {id} of ids){const full=await openRecord(db,id),p=publicProjection(full);db.sqlite.prepare('INSERT OR REPLACE INTO public_records VALUES(?,?,?,?,?)').run(id,full.revision,full.updated_at,0,JSON.stringify(p));projectionRecords.push(p);assert.equal(effectiveCategory(p),full.content.display_category);assert.equal(effectiveListType(p),full.list_type);assert.equal(currentNotesText(p),(full.content.notes||[]).join('\n'));}
});
const largest=db.sqlite.prepare('SELECT g.record_id,count(*) n FROM items i JOIN record_groups g ON g.id=i.group_id GROUP BY g.record_id ORDER BY n DESC LIMIT 1').get();
const act=body=>mutate(db,{request_id:crypto.randomUUID(),op:'edit_session',...body});
for(const id of [largest.record_id,'display-milwaukee-8x10-list','display-eau-claire-1','p1566-l003']){
 let r=await openRecord(db,id);const original=publicProjection(r);const historyBefore=db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n;
 const inventories=logicalInventories(r);const gid=inventories[0]?.id||'new-primary';
 const mode=effectiveListType(r);const value='ISOLATED REHEARSAL ENTRY';
 await measure('add_and_notes_'+id,()=>act({record_id:id,revision:r.revision,metadata:{notes:['Isolated current owner note'],entry_order:'original'},additions:[{value,state:mode==='have_list'?'owned':'wanted',field_key:'items',group_id:gid}]}));
 r=await openRecord(db,id);const publicRow=JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(id).public_json);assert.equal(publicRow.entry_order,'original');assert.equal(currentNotesText(publicRow),'Isolated current owner note');assert.ok(browseRecord(publicRow).logical_inventories.flatMap(g=>g.entries).some(i=>i.value===value));
 const h=(await recentOwner(db)).changes.find(h=>h.record_id===id);await mutate(db,{op:'undo',request_id:crypto.randomUUID(),record_id:id,revision:r.revision,history_id:h.id});
 const restored=publicProjection(await openRecord(db,id));assert.deepEqual(restored.groups,original.groups);assert.deepEqual(restored.notes,original.notes);assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n,historyBefore+2);
}
let large=await openRecord(db,largest.record_id);const editable=large.groups.flatMap(g=>g.entries).filter(i=>i.state==='wanted'&&!i.deleted_at).slice(0,500);
assert.equal(editable.length,500);
await measure('save_500_pending_'+largest.record_id,()=>act({record_id:large.id,revision:large.revision,changes:editable.map(i=>({id:i.id,state:'pending',removed:false}))}));
large=await openRecord(db,large.id);assert.equal(large.groups.flatMap(g=>g.entries).filter(i=>i.state==='pending').length,500);
const history=(await recentOwner(db)).changes.find(h=>h.record_id===large.id);await measure('undo_500_pending',()=>mutate(db,{op:'undo',request_id:crypto.randomUUID(),record_id:large.id,revision:large.revision,history_id:history.id}));
assert.deepEqual(sortedEntries(['10','KB-12','2','KB-2','1'].map(value=>({value}))).map(i=>i.value),['1','2','10','KB-2','KB-12']);
const yearExamples=projectionRecords.filter(r=>yearInfo(recordYear(r)).label).slice(0,20).map(r=>({id:r.id,year:recordYear(r),...yearInfo(recordYear(r))}));
db.sqlite.exec("INSERT OR IGNORE INTO staging_import_state VALUES(1,'isolated','isolated',3394,1)");
const report={local_only:true,cloudflare_cpu_measured:false,projections:ids.length,largest_listing:largest,observations,year_examples:yearExamples,unknown_years:projectionRecords.filter(r=>yearInfo(recordYear(r)).sort===null).length,uncertain_years:projectionRecords.filter(r=>yearInfo(recordYear(r)).label==='Year uncertain').length,database_bytes:db.sqlite.prepare('PRAGMA page_count').get().page_count*db.sqlite.prepare('PRAGMA page_size').get().page_size};
writeFileSync('foundation/staging/phase3c1-local-worker.json',JSON.stringify(report,null,2)+'\n');db.close();console.log(JSON.stringify(report,null,2));
