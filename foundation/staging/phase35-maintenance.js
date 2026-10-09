// Fixed, reviewed IDs only. Gate absent from normal deployments. No arbitrary SQL.
import {cleanup,eau} from './phase35-maintenance-data.js';
import {rebuildProjection} from './edit-session.js';
const fail=()=>{throw Object.assign(Error('Maintenance conflict'),{code:'CONFLICT'});};
export async function maintainPhase35(db,operation){
 const marker='phase35-'+operation;
 if(!['cleanup','eau-split'].includes(operation))fail();
 if(await db.prepare('SELECT value FROM foundation_meta WHERE key=?').bind(marker).first())return {replayed:true};
 const id=operation==='cleanup'?cleanup.record_id:eau.parent;
 const expected=operation==='cleanup'?cleanup.revision:eau.revision;
 const row=await db.prepare('SELECT * FROM records WHERE id=?').bind(id).first();
 if(!row||row.revision!==expected||row.deleted_at)fail();
 const stamp=new Date().toISOString(),revision=expected+1,st=(sql,...args)=>db.prepare(sql).bind(...args),sql=[];
 sql.push(st(`INSERT INTO foundation_meta VALUES(?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN '1' ELSE NULL END)`,marker,id,expected));
 if(operation==='cleanup'){
  const actual=await db.prepare(`SELECT count(*) n FROM items i JOIN record_groups g ON g.id=i.group_id WHERE g.record_id=? AND i.id IN (SELECT value FROM json_each(?)) AND i.deleted_at IS NULL AND i.state='wanted' AND i.value LIKE 'cpu-test-%'`).bind(id,JSON.stringify(cleanup.ids)).first();if(actual.n!==1403||cleanup.ids.length!==1403)fail();
  const meta=JSON.parse(row.content_json);if(meta.year!=='2027'||meta.brand!=='Topps'||JSON.stringify(meta.notes)!==JSON.stringify(cleanup.expected_notes))fail();
  sql.push(st(`INSERT INTO change_history SELECT ?,r.id,NULL,'phase35-maintenance','benchmark_cleanup',json_object('metadata',json_object('year',json_extract(r.content_json,'$.year'),'brand',json_extract(r.content_json,'$.brand'),'notes',json(json_extract(r.content_json,'$.notes'))),'list_type',r.list_type,'items',json((SELECT json_group_array(json_object('id',i.id,'state',i.state,'actionable',i.actionable,'limitation',i.limitation,'pending_at',i.pending_at,'received_at',i.received_at,'deleted_at',i.deleted_at)) FROM items i WHERE i.id IN (SELECT value FROM json_each(?))))),?,? FROM records r WHERE r.id=?`,crypto.randomUUID(),JSON.stringify(cleanup.ids),JSON.stringify({removed_count:1403,manifest_sha256:cleanup.manifest_sha256,metadata:cleanup.metadata,_record_revision:revision}),stamp,id));
  sql.push(st('UPDATE items SET deleted_at=? WHERE id IN (SELECT value FROM json_each(?))',stamp,JSON.stringify(cleanup.ids)));
  sql.push(st("UPDATE records SET content_json=json_set(content_json,'$.year',?,'$.brand',?,'$.notes',json(?)),revision=?,updated_at=? WHERE id=?",cleanup.metadata.year,cleanup.metadata.brand,JSON.stringify(cleanup.metadata.notes),revision,stamp,id));
  sql.push(st("UPDATE public_records SET public_json=json_set(public_json,'$.year',?,'$.brand',?,'$.notes',json(?)) WHERE record_id=?",cleanup.metadata.year,cleanup.metadata.brand,JSON.stringify(cleanup.metadata.notes),id));
  sql.push(rebuildProjection(db,id,revision,stamp));
 }else{
  const groups=(await db.prepare("SELECT * FROM record_groups WHERE record_id=? AND kind='sublist' ORDER BY position").bind(id).all()).results;
  if(groups.length!==3)fail();
  for(const [n,g] of groups.entries()){
   const entries=(await db.prepare('SELECT * FROM items WHERE group_id=? ORDER BY field_key,position').bind(g.id).all()).results;
   if(JSON.stringify(entries.map(i=>i.value))!==JSON.stringify(eau.listings[n].source.items)||entries.some(i=>i.deleted_at||i.state!==null||i.actionable!==0))fail();
   const listing=eau.listings[n],content={...listing.content,notes:JSON.parse(row.content_json).notes};
   sql.push(st('INSERT INTO records VALUES(?,?,?,?,1,?,?,NULL)',listing.id,row.import_id,'want_list',JSON.stringify(content),stamp,stamp));
   sql.push(st('INSERT INTO provenance VALUES(?,?,?,?)',listing.id,JSON.stringify(listing.source),listing.source_sha256,JSON.stringify(listing.source.source_refs)));
   // Group and item IDs stay unchanged. Archived parent/history remain available.
   sql.push(st('UPDATE record_groups SET record_id=? WHERE id=?',listing.id,g.id));
   sql.push(st("UPDATE items SET actionable=1,state='wanted',limitation=NULL WHERE group_id=?",g.id));
   sql.push(st('INSERT INTO public_records VALUES(?,1,?,0,?)',listing.id,stamp,JSON.stringify({...content,list_type:'want_list',revision:1,groups:[],projection_version:2,deleted:false})));
   sql.push(rebuildProjection(db,listing.id,1,stamp));
   sql.push(st('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',crypto.randomUUID(),listing.id,'phase35-maintenance','source_group_split',JSON.stringify({parent:id,parent_revision:expected,group_id:g.id,original_actionable:0,original_state:null,items:entries}),JSON.stringify({source_sha256:listing.source_sha256,items:entries.length,_record_revision:1}),stamp));
  }
  sql.push(st('UPDATE records SET deleted_at=?,revision=?,updated_at=? WHERE id=?',stamp,revision,stamp,id));
  sql.push(st("UPDATE public_records SET deleted=1,revision=?,updated_at=?,public_json=json_set(public_json,'$.deleted',json('true'),'$.revision',?,'$.updated_at',?) WHERE record_id=?",revision,stamp,revision,stamp,id));
  sql.push(st('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',crypto.randomUUID(),id,'phase35-maintenance','archive_source_container',JSON.stringify({revision:expected,groups:groups.map(g=>g.id)}),JSON.stringify({new_ids:eau.listings.map(r=>r.id),_record_revision:revision}),stamp));
 }
 if(sql.length>44)fail();
 try{await db.batch(sql);}catch(e){if(/constraint/i.test(e.message))fail();throw e;}
 return {operation,saved:true,record_id:id,revision,statements:sql.length,...(operation==='cleanup'?{soft_removed:1403,manifest_sha256:cleanup.manifest_sha256}:{listings:eau.listings.map(r=>({id:r.id,name:r.content.set_name,count:r.source.items.length})),parent_history_preserved:true})};
}
// Explicit recovery only, guarded against every subsequent owner change.
export async function rollbackEauSplit(db){
 const parent=await db.prepare('SELECT revision,deleted_at FROM records WHERE id=?').bind(eau.parent).first();if(!parent?.deleted_at||parent.revision!==eau.revision+1)fail();
 const histories=(await db.prepare("SELECT h.record_id,h.before_json,r.revision FROM change_history h JOIN records r ON r.id=h.record_id WHERE h.action='source_group_split' AND h.record_id IN (SELECT value FROM json_each(?))").bind(JSON.stringify(eau.listings.map(r=>r.id))).all()).results;
 if(histories.length!==3||histories.some(h=>h.revision!==1))fail();
 const stamp=new Date().toISOString(),revision=parent.revision+1,st=(sql,...p)=>db.prepare(sql).bind(...p),sql=[];
 sql.push(st(`INSERT INTO foundation_meta VALUES('phase35-eau-rollback',CASE WHEN (SELECT revision FROM records WHERE id=?)=? AND NOT EXISTS(SELECT 1 FROM records WHERE id IN (SELECT value FROM json_each(?)) AND revision!=1) THEN '1' ELSE NULL END)`,eau.parent,parent.revision,JSON.stringify(eau.listings.map(r=>r.id))));
 for(const h of histories){const before=JSON.parse(h.before_json);sql.push(st('UPDATE record_groups SET record_id=? WHERE id=?',eau.parent,before.group_id));sql.push(st(`UPDATE items SET actionable=json_extract(j.value,'$.actionable'),state=json_extract(j.value,'$.state'),limitation=json_extract(j.value,'$.limitation') FROM json_each(?) j WHERE items.id=json_extract(j.value,'$.id')`,JSON.stringify(before.items)));sql.push(st('UPDATE records SET deleted_at=?,revision=2,updated_at=? WHERE id=?',stamp,stamp,h.record_id));sql.push(st("UPDATE public_records SET deleted=1,revision=2,updated_at=?,public_json=json_set(public_json,'$.deleted',json('true'),'$.revision',2) WHERE record_id=?",stamp,h.record_id));sql.push(st('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',crypto.randomUUID(),h.record_id,'phase35-maintenance','rollback_source_split','{}',JSON.stringify({_record_revision:2}),stamp));}
 sql.push(st('UPDATE records SET deleted_at=NULL,revision=?,updated_at=? WHERE id=?',revision,stamp,eau.parent));sql.push(st("UPDATE public_records SET deleted=0,public_json=json_set(public_json,'$.deleted',json('false')) WHERE record_id=?",eau.parent));sql.push(rebuildProjection(db,eau.parent,revision,stamp));sql.push(st('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',crypto.randomUUID(),eau.parent,'phase35-maintenance','rollback_source_split','{}',JSON.stringify({_record_revision:revision}),stamp));await db.batch(sql);return {rolled_back:true,parent:eau.parent,revision};
}
