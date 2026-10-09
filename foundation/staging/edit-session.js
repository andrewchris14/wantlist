import {effectiveListType} from './effective-list-type.js';
// One revision, receipt, audit event and transactional projection per Save.
// Unchanged inventories never cross the Worker: JSON work stays in D1.
const changeKeys=new Set(['id','state','removed']),itemStates=new Set(['wanted','pending','owned',null]),additionFields=new Set(['card_numbers','items']),additionStates=new Set(['wanted','pending','owned']);
const fail=(code='INVALID')=>{throw Object.assign(Error(code),{code});};
const itemJSON=`json_object('id',i.id,'group_id',i.group_id,'field_key',i.field_key,'position',i.position,'value',i.value,'state',i.state,'actionable',i.actionable,'limitation',i.limitation,'pending_at',i.pending_at,'received_at',i.received_at,'deleted_at',i.deleted_at)`;
export function rebuildProjection(db,id,revision,stamp,metadata={},rebuildGroups=true){
 const keys=Object.keys(metadata),patch=keys.map(()=>',?,json(?)').join('');
 const groups=`json((SELECT json_group_array(json(body)) FROM (SELECT json_patch(json_object('id',g.id,'kind',g.kind,'list_type',g.list_type),json_patch(json_object('label',json_extract(g.metadata_json,'$.label'),'description',json_extract(g.metadata_json,'$.description'),'notes',json(json_extract(g.metadata_json,'$.notes')),'source_list_type',json_extract(g.metadata_json,'$.source_list_type')),json_object('entries',json((SELECT json_group_array(json(entry)) FROM (SELECT json_object('id',i.id,'value',i.value,'field_key',i.field_key,'position',i.position,'state',i.state,'actionable',i.actionable,'pending_at',i.pending_at,'received_at',i.received_at) entry FROM items i WHERE i.group_id=g.id AND i.deleted_at IS NULL ORDER BY CASE WHEN i.id LIKE 'owner-item-%' THEN 1 ELSE 0 END,CASE WHEN i.id NOT LIKE 'owner-item-%' THEN i.field_key END,i.position)))))) body FROM record_groups g WHERE g.record_id=? ORDER BY CASE g.kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,g.position)))`;
 // Patch metadata and membership together: the browse-index trigger runs once.
 return db.prepare(`UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json${patch},'$.revision',?,'$.updated_at',?,'$.list_type',(SELECT list_type FROM records WHERE id=?),'$.entry_order',COALESCE((SELECT json_extract(content_json,'$.entry_order') FROM records WHERE id=?),'natural')${rebuildGroups?",'$.groups',"+groups:''}) WHERE record_id=?`).bind(revision,stamp,...keys.flatMap(k=>['$.'+k,JSON.stringify(metadata[k])]),revision,stamp,id,id,...(rebuildGroups?[id]:[]),id);
}
export async function editSession(db,input,requestHash,undoing=false){
 const row=await db.prepare(`SELECT r.id,r.revision,r.list_type,r.deleted_at,json_extract(r.content_json,'$.source_list_type') source_list_type,CASE WHEN r.list_type='uncertain' THEN EXISTS(SELECT 1 FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=r.id AND i.deleted_at IS NULL) ELSE 0 END has_entries,p.revision public_revision FROM records r JOIN public_records p ON p.record_id=r.id WHERE r.id=?`).bind(input.record_id).first();
 if(!row||row.deleted_at||row.revision!==input.revision||row.public_revision!==input.revision)fail('CONFLICT');
 const stamp=new Date().toISOString(),revision=input.revision+1,changes=input.changes||[],additions=input.additions||[],metadata={...(input.metadata||{})};
 // An explicit live year edit supersedes its historical presentation label.
 // The original label is retained in provenance and the session's before-state.
 if(Object.hasOwn(metadata,'year'))metadata.display_year=metadata.year;
 const currentMode=effectiveListType(row),mode=input.list_type||currentMode,storedMode=input.list_type||row.list_type,statements=[];
 if(!['want_list','have_list','complete','uncertain'].includes(mode)||!Number.isInteger(input.revision))fail();
 const conversion=['want_list','have_list'].includes(mode)&&mode!==currentMode;
 if(mode==='complete'&&mode!==currentMode&&!input.confirm_complete)fail();
 if(conversion&&!input.confirm_conversion)fail();
 if(!Array.isArray(changes)||!Array.isArray(additions)||changes.length>500||additions.length>500)fail();
 if(new Set(changes.map(c=>c.id)).size!==changes.length)fail();
 if(changes.some(c=>typeof c.id!=='string'||Object.keys(c).some(k=>!changeKeys.has(k))||typeof c.removed!=='boolean'||!itemStates.has(c.state)))fail();
 if(additions.some(a=>typeof a.value!=='string'||!a.value.trim()||a.value.length>500||!additionFields.has(a.field_key)||!additionStates.has(a.state)||typeof a.group_id!=='string'))fail();
 if(mode==='complete'&&(changes.length||additions.length))fail();
 const changesJSON=JSON.stringify(changes);
 const validation=changes.length?await db.prepare(`SELECT count(*) n,
 COALESCE(sum(i.deleted_at IS NOT NULL),0) deleted,
 COALESCE(sum(CASE WHEN json_extract(c.value,'$.removed')=0 AND json_extract(c.value,'$.state') IS NOT i.state AND
 (?!='want_list' OR (g.list_type!='want_list' AND NOT(g.kind='primary' AND g.list_type='uncertain')) OR COALESCE(i.state,'wanted') NOT IN ('wanted','pending') OR json_extract(c.value,'$.state') NOT IN ('wanted','pending') OR json_extract(c.value,'$.state') IS NULL) THEN 1 ELSE 0 END),0) invalid,
 COALESCE(sum(i.state='pending' AND json_extract(c.value,'$.removed')=1),0) pending_removed
 FROM json_each(?) c CROSS JOIN items i CROSS JOIN record_groups g WHERE i.id=json_extract(c.value,'$.id') AND g.id=i.group_id AND g.record_id=?`).bind(currentMode,changesJSON,row.id).first():{n:0,invalid:0,deleted:0,pending_removed:0};
 if(validation.n!==changes.length||validation.invalid)fail();
 if(validation.deleted)fail('CONFLICT');
 if(validation.pending_removed&&!input.confirm_pending_removal)fail();
 // Explicit conversion must remove all active primary logical entries, never
 // silently transfer old owned identifiers into a wanted inventory.
 if(conversion){
  const remain=await db.prepare(`SELECT count(*) n FROM items i JOIN record_groups g ON g.id=i.group_id WHERE g.record_id=? AND (g.list_type=? OR g.kind='primary' AND g.list_type='uncertain') AND i.deleted_at IS NULL AND i.id NOT IN (SELECT json_extract(value,'$.id') FROM json_each(?) WHERE json_extract(value,'$.removed')=1)`).bind(row.id,currentMode,changesJSON).first();
  if(remain.n)fail();
 }
 const groups=additions.length?(await db.prepare('SELECT * FROM record_groups WHERE record_id=?').bind(row.id).all()).results:[];
 const groupById=new Map(groups.map(g=>[g.id,g]));
 const newGroups=[],added=[],valuesByGroup=new Map();
 for(const a of additions){
  let g=groupById.get(a.group_id);
  if(g&&!(g.list_type===mode||g.kind==='primary'&&g.list_type==='uncertain'&&mode===currentMode))g=null;
  if(!g&&a.group_id==='new-primary'){
   g=newGroups[0];if(!g){g={id:'owner-group-'+crypto.randomUUID(),kind:groups.length?'mixed':'primary',position:Math.max(-1,...groups.filter(g=>g.kind==='mixed').map(g=>g.position))+1};newGroups.push(g);}
  }
  if(mode==='have_list'&&a.state!=='owned'||mode==='want_list'&&a.state==='owned')fail();
  if(!g||!['want_list','have_list'].includes(mode))fail();
  const value=a.value.trim();let values=valuesByGroup.get(g.id);if(!values){values=new Set();valuesByGroup.set(g.id,values);}if(values.has(value))fail();values.add(value);
  added.push({id:'owner-item-'+crypto.randomUUID(),group_id:g.id,field_key:a.field_key,value,state:mode==='want_list'?(a.state==='pending'?'pending':'wanted'):'owned'});
 }
 // Duplicates across the logical inventory are checked in SQL, excluding draft removals.
 const addedJSON=JSON.stringify(added);
 const duplicate=added.length?await db.prepare(`SELECT i.id FROM json_each(?) a CROSS JOIN record_groups g CROSS JOIN items i INDEXED BY items_group_value WHERE g.record_id=? AND i.group_id=g.id AND i.value=a.value AND (g.list_type=? OR g.kind='primary' AND g.list_type='uncertain') AND i.deleted_at IS NULL AND i.id NOT IN (SELECT json_extract(value,'$.id') FROM json_each(?) WHERE json_extract(value,'$.removed')=1) LIMIT 1`).bind(JSON.stringify(added.map(a=>a.value)),row.id,mode,changesJSON).first():null;
 if(duplicate)fail();
 const result={saved:true,record_id:row.id,revision};
 const st=(sql,...params)=>db.prepare(sql).bind(...params);
 statements.push(st(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,row.id,row.id,input.revision,JSON.stringify(result),stamp));
 const historyId=crypto.randomUUID(),keys=Object.keys(metadata);
 const oldMeta=keys.length?`json_object(${keys.map(k=>`'${k}',json_extract(r.content_json,'$.${k}')`).join(',')})`:`json('{}')`;
 statements.push(st(`INSERT INTO change_history SELECT ?,r.id,NULL,'owner','edit_session',json_object('metadata',json(${oldMeta}),'list_type',r.list_type,'items',json((SELECT json_group_array(json(${itemJSON})) FROM items i WHERE i.id IN (SELECT json_extract(value,'$.id') FROM json_each(?))))),?,? FROM records r WHERE r.id=?`,historyId,changesJSON,JSON.stringify({metadata,list_type:storedMode,added_ids:added.map(a=>a.id),_record_revision:revision}),stamp,row.id));
 for(const g of newGroups)statements.push(st('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)',g.id,row.id,g.kind,g.kind==='primary'?0:g.position,mode,'{}','["card_numbers","items","card_ranges"]'));
 // Join each change once by the existing item primary key; no per-column JSON scans.
 if(changes.length)statements.push(st(`UPDATE items SET actionable=CASE WHEN json_extract(c.value,'$.state') IN ('wanted','pending') THEN 1 ELSE items.actionable END,limitation=CASE WHEN json_extract(c.value,'$.state') IN ('wanted','pending') THEN NULL ELSE items.limitation END,state=json_extract(c.value,'$.state'),pending_at=CASE WHEN json_extract(c.value,'$.state')='pending' THEN COALESCE(items.pending_at,?) ELSE NULL END,deleted_at=CASE WHEN json_extract(c.value,'$.removed')=1 THEN ? ELSE NULL END FROM json_each(?) c WHERE items.id=json_extract(c.value,'$.id')`,stamp,stamp,changesJSON));
 // Materialize positions once per group, including removed entries. Keep the
 // original global addition ordinal, field ordering and stable identifiers.
 if(added.length)statements.push(st(`WITH additions AS MATERIALIZED (SELECT CAST(key AS INTEGER) ordinal,json_extract(value,'$.id') id,json_extract(value,'$.group_id') group_id,json_extract(value,'$.field_key') field_key,json_extract(value,'$.value') value,json_extract(value,'$.state') state FROM json_each(?)),bases AS MATERIALIZED (SELECT group_id,COALESCE((SELECT max(position) FROM items WHERE items.group_id=g.group_id),-1)+1 base FROM (SELECT DISTINCT group_id FROM additions) g) INSERT INTO items SELECT a.id,a.group_id,a.field_key,b.base+a.ordinal,a.value,a.state,1,NULL,CASE WHEN a.state='pending' THEN ? ELSE NULL END,NULL,NULL FROM additions a JOIN bases b ON b.group_id=a.group_id`,addedJSON,stamp));
 statements.push(st(`UPDATE records SET content_json=json_set(content_json${keys.map(()=>',?,json(?)').join('')}),list_type=?,revision=?,updated_at=? WHERE id=?`,...keys.flatMap(k=>['$.'+k,JSON.stringify(metadata[k])]),storedMode,revision,stamp,row.id));
 statements.push(rebuildProjection(db,row.id,revision,stamp,metadata,!!(changes.length||added.length||storedMode!==row.list_type)));
 return commit(db,input,requestHash,statements,result);
}
export async function undoSession(db,input,requestHash){
 const h=await db.prepare("SELECT id,json_object('metadata',json_extract(before_json,'$.metadata'),'list_type',json_extract(before_json,'$.list_type')) before_json,json_object('_record_revision',json_extract(after_json,'$._record_revision'),'list_type',json_extract(after_json,'$.list_type'),'added_ids',json_extract(after_json,'$.added_ids')) after_json,json_array_length(before_json,'$.items') changed_items FROM change_history WHERE id=? AND record_id=? AND action IN ('edit_session','benchmark_cleanup')").bind(input.session_history,input.record_id).first();if(!h)fail();
 const before=JSON.parse(h.before_json),after=JSON.parse(h.after_json);
 if(after._record_revision!==input.revision)fail('CONFLICT');
 const stamp=new Date().toISOString(),revision=input.revision+1,result={saved:true,record_id:input.record_id,revision},st=(sql,...p)=>db.prepare(sql).bind(...p),keys=Object.keys(before.metadata);
 const statements=[st(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,input.record_id,input.record_id,input.revision,JSON.stringify(result),stamp)];
 if(h.changed_items)statements.push(st(`UPDATE items SET actionable=json_extract(j.value,'$.actionable'),limitation=json_extract(j.value,'$.limitation'),state=json_extract(j.value,'$.state'),pending_at=json_extract(j.value,'$.pending_at'),received_at=json_extract(j.value,'$.received_at'),deleted_at=json_extract(j.value,'$.deleted_at') FROM json_each((SELECT before_json FROM change_history WHERE id=?),'$.items') j WHERE items.id=json_extract(j.value,'$.id')`,h.id));
 if(after.added_ids?.length)statements.push(st('UPDATE items SET deleted_at=? WHERE id IN (SELECT value FROM json_each(?))',stamp,JSON.stringify(after.added_ids)));
 statements.push(st(`UPDATE records SET content_json=json_set(content_json${keys.map(()=>',?,json(?)').join('')}),list_type=?,revision=?,updated_at=? WHERE id=?`,...keys.flatMap(k=>['$.'+k,JSON.stringify(before.metadata[k])]),before.list_type,revision,stamp,input.record_id));
 statements.push(st('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',crypto.randomUUID(),input.record_id,'owner','undo_session',JSON.stringify({history_id:h.id}),JSON.stringify({_record_revision:revision}),stamp));
 statements.push(rebuildProjection(db,input.record_id,revision,stamp,before.metadata,!!(h.changed_items||after.added_ids?.length||before.list_type!==after.list_type)));
 return commit(db,input,requestHash,statements,result);
}
async function commit(db,input,sha,statements,result){
 try{await db.batch(statements);}catch(e){const receipt=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();if(receipt?.request_sha256===sha)return {...JSON.parse(receipt.result_json),replayed:true};if(/CHECK constraint|UNIQUE constraint/i.test(e.message))fail('CONFLICT');throw e;}return result;
}
