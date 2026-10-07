// Staging data-layer reference, not a public production API or editor.
import {hash} from './auth.js';
const fail=(code='INVALID')=>{const e=Error(code);e.code=code;throw e;};
const statement=(sql,...params)=>({sql,params});
const metadataKeys=['year','brand','set_name','category','section','notes','prefixes','uncertainty','set_size'];
const publicKeys=['id',...metadataKeys,'source_list_type','completed_sets','source_refs','creation_origin'];
const modes=['want_list','have_list','complete','uncertain'];
export async function catalog(db){return (await db.prepare(`SELECT id,revision,list_type,json_extract(content_json,'$.year') year,
  json_extract(content_json,'$.brand') brand,json_extract(content_json,'$.set_name') set_name FROM records WHERE deleted_at IS NULL ORDER BY id`).all()).results;}
export async function openRecord(db,id){
  const r=await db.prepare('SELECT * FROM records WHERE id=?').bind(id).first();if(!r)return null;
  const groups=(await db.prepare(`SELECT * FROM record_groups WHERE record_id=? ORDER BY CASE kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,position`).bind(id).all()).results;
  const entries=(await db.prepare(`SELECT i.* FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? ORDER BY CASE g.kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,g.position,i.field_key,i.position`).bind(id).all()).results;
  return {...r,content:JSON.parse(r.content_json),groups:groups.map(g=>({...g,entries:entries.filter(i=>i.group_id===g.id)}))};
}
export function publicProjection(r){
  const out={};for(const k of publicKeys)if(k in r.content)out[k]=r.content[k];
  Object.assign(out,{list_type:r.list_type,revision:r.revision,updated_at:r.updated_at,deleted:!!r.deleted_at,projection_version:2,groups:[]});
  if(!r.deleted_at)out.groups=r.groups.map(g=>{
    const m=JSON.parse(g.metadata_json),body={id:g.id,kind:g.kind,list_type:g.list_type};
    for(const k of ['label','description','notes','source_list_type'])if(k in m)body[k]=m[k];
    body.entries=g.entries.filter(i=>!i.deleted_at).map(i=>({id:i.id,value:i.value,position:i.position,field_key:i.field_key,state:i.state,actionable:i.actionable,pending_at:i.pending_at,received_at:i.received_at}));
    return body;
  });
  return out;
}
function validateMetadata(data,creating=false){
  if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).some(k=>!metadataKeys.includes(k)))fail();
  if(Object.values(data).some(v=>v===undefined))fail();
  for(const k of ['year','brand','set_name','category','section'])if(k in data&&data[k]!==null&&(typeof data[k]!=='string'||data[k].length>500))fail();
  if((creating||'set_name'in data)&&(!data.set_name||!data.set_name.trim()))fail();
  for(const k of ['notes','prefixes','uncertainty'])if(k in data&&(!Array.isArray(data[k])||data[k].some(x=>typeof x!=='string'||x.length>10000)))fail();
  if(data.set_size!=null&&(!Number.isInteger(data.set_size)||data.set_size<1))fail();
}
export function mutationControl(db,input){
  return db.prepare('SELECT s.completed,m.request_sha256,m.result_json FROM staging_import_state s LEFT JOIN mutation_receipts m ON m.id=? WHERE s.id=1').bind(typeof input?.request_id==='string'?input.request_id:null);
}
export async function mutate(db,input,preflight,prefetchedRow){
  if(!input||typeof input!=='object'||typeof input.request_id!=='string'||!/^[-\w]{16,100}$/.test(input.request_id))fail();
  const requestHash=await hash(JSON.stringify(input));
  const control=preflight ?? await mutationControl(db,input).first();
  const receipt=control?.result_json?control:null;
  if(receipt){if(receipt.request_sha256!==requestHash)fail('CONFLICT');return {...JSON.parse(receipt.result_json),replayed:true};}
  if(!control?.completed)fail('CONFLICT');
  if(input.op==='add')return addOne(db,input,requestHash,prefetchedRow);
  if(['remove_item','restore_item'].includes(input.op))return removeRestoreOne(db,input,requestHash,prefetchedRow);
  if(input.op==='transition')return transitionOne(db,input,requestHash,prefetchedRow);
  if(['edit','delete','restore'].includes(input.op))return editHeaderOne(db,input,requestHash,prefetchedRow);
  const stamp=new Date().toISOString(),sql=[];let r,before={},after={},itemId=null;
  if(input.op==='create'){
    validateMetadata(input.metadata,true);const mode=input.list_type||'want_list';if(!modes.includes(mode))fail();
    const id='owner-record-'+crypto.randomUUID();
    r={id,import_id:null,list_type:mode,revision:1,created_at:stamp,updated_at:stamp,deleted_at:null,content:{id,creation_origin:'owner',notes:[],prefixes:[],uncertainty:[],...input.metadata},groups:[]};
    sql.push(statement('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)',id,mode,JSON.stringify(r.content),stamp,stamp));
  }else fail();
  const add=(values,state,field='card_numbers')=>{
    if(!Array.isArray(values)||values.length>20||!['wanted','owned'].includes(state)||!['card_numbers','items'].includes(field))fail();
    if(!values.length)return;
    if(state==='wanted'&&r.list_type==='complete')fail();
    if(values.some(v=>typeof v!=='string'||!v.trim()||v.length>500)||new Set(values.map(v=>v.trim())).size!==values.length)fail();
    const mode=state==='wanted'?'want_list':'have_list';let g=r.groups.find(g=>g.list_type===mode);
    if(!g){const kind=r.groups.length?'mixed':'primary',position=kind==='primary'?0:Math.max(-1,...r.groups.filter(x=>x.kind==='mixed').map(x=>x.position))+1;
      g={id:'owner-group-'+crypto.randomUUID(),record_id:r.id,kind,position,list_type:mode,metadata_json:'{}',inventory_keys_json:'["card_numbers","items","card_ranges"]',entries:[]};r.groups.push(g);
      sql.push(statement('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)',g.id,r.id,kind,position,mode,g.metadata_json,g.inventory_keys_json));}
    let pos=Math.max(-1,...g.entries.filter(i=>i.field_key===field).map(i=>i.position))+1;
    after.items=[];
    for(let value of values){value=value.trim();if(g.entries.some(i=>!i.deleted_at&&i.value===value))fail();
      const i={id:'owner-item-'+crypto.randomUUID(),group_id:g.id,field_key:field,position:pos++,value,state,actionable:1,limitation:null,pending_at:null,received_at:null,deleted_at:null};g.entries.push(i);after.items.push(i);
      sql.push(statement('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)',i.id,g.id,field,i.position,value,state));}
  };
  if(input.op==='create'){
    add(input.wanted||[],'wanted');add(input.owned||[],'owned');add(input.wanted_names||[],'wanted','items');add(input.owned_names||[],'owned','items');
    after={metadata:r.content,list_type:r.list_type,items:r.groups.flatMap(g=>g.entries).map(i=>({id:i.id,value:i.value,position:i.position,field_key:i.field_key,state:i.state}))};
  }else fail();
  const result={saved:true,record_id:r.id,revision:r.revision};
  // D1 batch is transactional. The CHECK guard rolls back EVERY statement if
  // another writer changed the revision between our reads and this batch.
  if(input.op!=='create')sql.unshift(statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,r.id,r.id,input.revision,JSON.stringify(result),stamp));
  else sql.push(statement('INSERT INTO mutation_receipts VALUES(?,?,?,1,?,?)',input.request_id,requestHash,r.id,JSON.stringify(result),stamp));
  if(input.op!=='create')sql.push(statement('UPDATE records SET content_json=?,list_type=?,revision=?,updated_at=?,deleted_at=? WHERE id=?',JSON.stringify(r.content),r.list_type,r.revision,stamp,r.deleted_at,r.id));
  sql.push(statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),r.id,itemId,'owner',input.op,JSON.stringify(before),JSON.stringify(after),stamp));
  sql.push(statement(`INSERT INTO public_records VALUES(?,?,?,?,?) ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at,deleted=excluded.deleted,public_json=excluded.public_json`,r.id,r.revision,stamp,r.deleted_at?1:0,JSON.stringify(publicProjection(r))));
  // Consolidate item inserts; at most 96 bindings per statement.
  const inserts=sql.filter(s=>s.sql==='INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)');
  for(const i of inserts)sql.splice(sql.indexOf(i),1);
  for(let n=0;n<inserts.length;n+=16){const part=inserts.slice(n,n+16);
    const at=sql.findIndex(s=>s.sql.startsWith('INSERT INTO mutation_receipts'));
    sql.splice(at<0?sql.length:at,0,statement('INSERT INTO items VALUES '+part.map(()=>'(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)').join(','),...part.flatMap(s=>s.params)));}
  if(sql.length>44)fail(); // Leave room for authenticated reads under Free's 50-query limit.
  try{await db.batch(sql.map(s=>db.prepare(s.sql).bind(...s.params)));}
  catch(error){
    // Failed/retried concurrent requests may have already committed once.
    const existing=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();
    if(existing&&existing.request_sha256===requestHash)return {...JSON.parse(existing.result_json),replayed:true};
    if(/CHECK constraint|UNIQUE constraint/i.test(error.message))fail('CONFLICT');throw error;
  }
  return result;
}

// Common card-state changes must not deserialize/serialize a whole large set.
// D1 locates the affected JSON entry; only a path and one item leave D1.
async function transitionOne(db,input,requestHash,prefetched){
  if(!Number.isInteger(input.revision)||input.revision<1||!['wanted','pending','owned'].includes(input.state))fail();
  const row=prefetched ?? await readtransitionOne(db,input).first();
  if(!row||row.record_revision!==input.revision||row.record_deleted)fail('CONFLICT');
  if(!row.actionable||row.deleted_at||!({wanted:['pending','owned'],pending:['wanted','owned'],owned:['wanted']}[row.state]||[]).includes(input.state))fail();
  if(row.record_list_type==='complete'&&['wanted','pending'].includes(input.state))fail();
  if(!row.public_path||row.public_revision!==input.revision)fail('CONFLICT');
  const stamp=new Date().toISOString(),revision=input.revision+1;
  const before=Object.fromEntries(Object.entries(row).filter(([key])=>!['record_id','record_revision','record_list_type','record_deleted','public_revision','public_path'].includes(key)));
  const after={...before,state:input.state,pending_at:input.state==='pending'?stamp:null,received_at:input.state==='owned'?stamp:null};
  const published=Object.fromEntries(['id','value','position','field_key','state','actionable','pending_at','received_at'].map(k=>[k,after[k]]));
  const result={saved:true,record_id:row.record_id,revision};
  const statements=[
    statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,row.record_id,row.record_id,input.revision,JSON.stringify(result),stamp),
    statement('UPDATE items SET state=?,pending_at=?,received_at=? WHERE id=?',after.state,after.pending_at,after.received_at,row.id),
    statement('UPDATE records SET revision=?,updated_at=? WHERE id=?',revision,stamp,row.record_id),
    statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),row.record_id,row.id,'owner','transition',JSON.stringify(before),JSON.stringify(after),stamp),
    statement("UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json,'$.revision',?,'$.updated_at',?, ?,json(?)) WHERE record_id=?",revision,stamp,revision,stamp,row.public_path,JSON.stringify(published),row.record_id)
  ];
  try{await db.batch(statements.map(s=>db.prepare(s.sql).bind(...s.params)));}
  catch(error){
    const existing=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();
    if(existing&&existing.request_sha256===requestHash)return {...JSON.parse(existing.result_json),replayed:true};
    if(/CHECK constraint|UNIQUE constraint/i.test(error.message))fail('CONFLICT');throw error;
  }
  return result;
}

// Notes/status/deletion changes similarly patch the saved public JSON in D1.
async function editHeaderOne(db,input,requestHash,prefetched){
  if(!Number.isInteger(input.revision)||input.revision<1)fail();
  validateMetadata(input.metadata||{});
  const keys=Object.keys(input.metadata||{});
  const oldMetadata=keys.length?"json_object("+keys.map(k=>"'"+k+"',json_extract(content_json,'$."+k+"')").join(',')+")":"'{}'";
  const row=prefetched ?? await readHeader(db,input).first();
  if(!row||row.revision!==input.revision||(row.deleted_at&&input.op!=='restore')||(!row.deleted_at&&input.op==='restore'))fail('CONFLICT');
  if(row.public_revision!==input.revision)fail('CONFLICT');
  const old=JSON.parse(row.old_metadata),stamp=new Date().toISOString(),revision=input.revision+1;
  let mode=row.list_type,deleted=row.deleted_at,before={},after={},patch={revision,updated_at:stamp};
  if(input.op==='edit'){
    validateMetadata(input.metadata||{});mode=input.list_type||mode;if(!modes.includes(mode))fail();
    if(mode==='complete'){
      const needed=await db.prepare(`SELECT i.id FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? AND i.deleted_at IS NULL
        AND (i.state IN ('wanted','pending') OR (i.actionable=0 AND g.list_type='want_list')) LIMIT 1`).bind(row.id).first();if(needed)fail();
    }
    before={metadata:old,list_type:row.list_type};
    after={metadata:input.metadata||{},list_type:mode};patch={...patch,...input.metadata,list_type:mode};
  }else{
    deleted=input.op==='delete'?stamp:null;before={deleted_at:row.deleted_at};after={deleted_at:deleted};patch.deleted=!!deleted;
  }
  const result={saved:true,record_id:row.id,revision};
  const pairs=Object.entries(patch),paths=pairs.map(()=>',?,json(?)').join('');
  const statements=[
    statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,row.id,row.id,input.revision,JSON.stringify(result),stamp),
    statement('UPDATE records SET content_json='+ (keys.length?'json_set(content_json'+keys.map(()=>',?,json(?)').join('')+')':'content_json')+',list_type=?,revision=?,updated_at=?,deleted_at=? WHERE id=?',...keys.flatMap(k=>['$.'+k,JSON.stringify(input.metadata[k])]),mode,revision,stamp,deleted,row.id),
    statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),row.id,null,'owner',input.op,JSON.stringify(before),JSON.stringify(after),stamp),
    statement('UPDATE public_records SET revision=?,updated_at=?,deleted=?,public_json=json_set(public_json'+paths+') WHERE record_id=?',revision,stamp,deleted?1:0,...pairs.flatMap(([key,value])=>['$.'+key,JSON.stringify(value)]),row.id)
  ];
  try{await db.batch(statements.map(s=>db.prepare(s.sql).bind(...s.params)));}
  catch(error){
    const existing=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();
    if(existing&&existing.request_sha256===requestHash)return {...JSON.parse(existing.result_json),replayed:true};
    if(/CHECK constraint|UNIQUE constraint/i.test(error.message))fail('CONFLICT');throw error;
  }
  return result;
}

// Bounded additions never load historical inventories or unrelated card arrays.
async function addOne(db,input,requestHash,prefetched){
  if(!Number.isInteger(input.revision)||input.revision<1)fail();
  const state=input.state||'wanted',field=input.field_key||'card_numbers',values=input.values;
  if(!['wanted','owned'].includes(state)||!['card_numbers','items'].includes(field)||!Array.isArray(values)||!values.length||values.length>20||values.some(v=>typeof v!=='string'||!v.trim()||v.length>500))fail();
  const trimmed=values.map(v=>v.trim());if(new Set(trimmed).size!==trimmed.length)fail();
  const mode=state==='wanted'?'want_list':'have_list';
  const row=prefetched ?? await readaddOne(db,input).first();
  if(!row||row.revision!==input.revision||row.public_revision!==input.revision||row.deleted_at)fail('CONFLICT');
  if(state==='wanted'&&row.list_type==='complete')fail();
  const stamp=new Date().toISOString(),revision=input.revision+1,statements=[];
  let gid=row.group_id,groupPath;
  if(gid){
    const details=await db.prepare(`SELECT
      (SELECT '$.groups['||key||'].entries' FROM json_each(p.public_json,'$.groups') WHERE json_extract(value,'$.id')=?) path,
      json_extract(p.public_json,(SELECT '$.groups['||key||'].entries[#-1].field_key' FROM json_each(p.public_json,'$.groups') WHERE json_extract(value,'$.id')=?)) last_field,
      COALESCE((SELECT position FROM items WHERE group_id=? AND field_key=? ORDER BY position DESC LIMIT 1),-1)+1 next_position,
      (SELECT id FROM items WHERE group_id=? AND deleted_at IS NULL AND value IN (${trimmed.map(()=>'?').join(',')}) LIMIT 1) duplicate,
      json_extract(p.public_json,'$.projection_version') public_version
      FROM public_records p WHERE p.record_id=?`).bind(gid,gid,gid,field,gid,...trimmed,row.id).first();
    if(!details?.path||details.duplicate)fail();groupPath=details.path;row.next_position=details.next_position;row.append_safe=!details.last_field||details.last_field<=field;
    if(!row.append_safe&&details.public_version!==2)fail('CONFLICT');
  }else{
    const details=await db.prepare(`SELECT count(*) n,COALESCE(max(CASE WHEN kind='mixed' THEN position END),-1)+1 next_position FROM record_groups WHERE record_id=?`).bind(row.id).first();
    gid='owner-group-'+crypto.randomUUID();const kind=details.n?'mixed':'primary',position=kind==='primary'?0:details.next_position;
    statements.push(statement('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)',gid,row.id,kind,position,mode,'{}','["card_numbers","items","card_ranges"]'));
    groupPath=null;row.next_position=0;
  }
  const entries=trimmed.map((value,n)=>({id:'owner-item-'+crypto.randomUUID(),group_id:gid,field_key:field,position:row.next_position+n,value,state,actionable:1,limitation:null,pending_at:null,received_at:null,deleted_at:null}));
  // Six parameters/item, <=96/statement. D1 Free has 100 bound parameters.
  for(let n=0;n<entries.length;n+=16){const part=entries.slice(n,n+16);statements.push(statement('INSERT INTO items VALUES '+part.map(()=>'(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)').join(','),...part.flatMap(i=>[i.id,gid,field,i.position,i.value,state])));}
  const published=entries.map(publicItem);
  let patch;
  if(groupPath)patch=statement(`UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json,?,json((SELECT json_group_array(json(entry)) FROM
    (SELECT value entry,json_extract(value,'$.field_key') field,json_extract(value,'$.position') position FROM json_each(public_json,?)
     UNION ALL SELECT value,json_extract(value,'$.field_key'),json_extract(value,'$.position') FROM json_each(?) ORDER BY field,position))), '$.revision',?,'$.updated_at',?) WHERE record_id=?`,revision,stamp,groupPath,groupPath,JSON.stringify(published),revision,stamp,row.id);
  if(groupPath&&row.append_safe)patch=statement("UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(json_insert(public_json"+published.map(()=>',?,json(?)').join('')+"),'$.revision',?,'$.updated_at',?) WHERE record_id=?",revision,stamp,...published.flatMap(i=>[groupPath+'[#]',JSON.stringify(i)]),revision,stamp,row.id);
  // The newly created group's kind comes from the inserted group, not a guess.
  if(!groupPath)patch=statement(`UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json,'$.groups',json((SELECT json_group_array(json(body)) FROM
    (SELECT j.value body,CASE g.kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END kind_order,g.position position FROM json_each(public_json,'$.groups') j JOIN record_groups g ON g.id=json_extract(j.value,'$.id')
     UNION ALL SELECT json_object('id',id,'kind',kind,'list_type',list_type,'entries',json(?)),CASE kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,position FROM record_groups WHERE id=? ORDER BY kind_order,position))), '$.revision',?,'$.updated_at',?) WHERE record_id=?`,revision,stamp,JSON.stringify(published),gid,revision,stamp,row.id);
  return commitDelta(db,input,requestHash,row.id,revision,stamp,null,{}, {items:entries},statements,patch);
}
function publicItem(i){return Object.fromEntries(['id','value','position','field_key','state','actionable','pending_at','received_at'].map(k=>[k,i[k]]));}
async function removeRestoreOne(db,input,requestHash,prefetched){
  if(!Number.isInteger(input.revision)||input.revision<1)fail();
  const row=prefetched ?? await readremoveRestoreOne(db,input).first();
  if(!row||row.record_revision!==input.revision||row.public_revision!==input.revision||row.record_deleted)fail('CONFLICT');
  const restoring=input.op==='restore_item';
  if(restoring?(!row.deleted_at||(row.record_list_type==='complete'&&['wanted','pending'].includes(row.state))):!!row.deleted_at)fail();
  const location=await db.prepare(`SELECT '$.groups['||g.key||'].entries' group_path,
    (SELECT key FROM json_each(g.value,'$.entries') WHERE json_extract(value,'$.id')=?) item_index,
    (SELECT id FROM items WHERE group_id=? AND value=? AND id<>? AND deleted_at IS NULL LIMIT 1) duplicate,
    json_extract(p.public_json,'$.projection_version') public_version
    FROM public_records p,json_each(p.public_json,'$.groups') g WHERE p.record_id=? AND json_extract(g.value,'$.id')=?`).bind(row.id,row.group_id,row.value,row.id,row.record_id,row.group_id).first();
  if(!location||(restoring?(location.duplicate||location.public_version!==2):location.item_index==null))fail();
  const stamp=new Date().toISOString(),revision=input.revision+1;
  const before=Object.fromEntries(Object.entries(row).filter(([k])=>!['record_id','record_revision','record_list_type','record_deleted','public_revision'].includes(k))),after={...before,deleted_at:restoring?null:stamp};
  let patch;
  if(!restoring)patch=statement("UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(json_remove(public_json,?),'$.revision',?,'$.updated_at',?) WHERE record_id=?",revision,stamp,location.group_path+'['+location.item_index+']',revision,stamp,row.record_id);
  else{
    // Public entries retain their literal ordering position, so restore sorts
    // the group's JSON inside D1 without reading unrelated item-table rows.
    patch=statement(`UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json,?,json((SELECT json_group_array(json(entry)) FROM
      (SELECT e.value entry,json_extract(e.value,'$.field_key') field,json_extract(e.value,'$.position') position FROM json_each(public_json,?) e
       UNION ALL SELECT ?,?,? ORDER BY field,position))), '$.revision',?,'$.updated_at',?) WHERE record_id=?`,revision,stamp,location.group_path,location.group_path,JSON.stringify(publicItem(row)),row.field_key,row.position,revision,stamp,row.record_id);
  }
  return commitDelta(db,input,requestHash,row.record_id,revision,stamp,row.id,before,after,[statement('UPDATE items SET deleted_at=? WHERE id=?',after.deleted_at,row.id)],patch);
}
async function commitDelta(db,input,requestHash,id,revision,stamp,itemId,before,after,changes,projection){
  const result={saved:true,record_id:id,revision};
  const statements=[statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,id,id,input.revision,JSON.stringify(result),stamp),...changes,
    statement('UPDATE records SET revision=?,updated_at=? WHERE id=?',revision,stamp,id),
    statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),id,itemId,'owner',input.op,JSON.stringify(before),JSON.stringify(after),stamp),projection];
  try{await db.batch(statements.map(s=>db.prepare(s.sql).bind(...s.params)));}
  catch(error){const existing=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();if(existing&&existing.request_sha256===requestHash)return {...JSON.parse(existing.result_json),replayed:true};if(/CHECK constraint|UNIQUE constraint/i.test(error.message))fail('CONFLICT');throw error;}
  return result;
}

function readtransitionOne(db,input){return db.prepare(`SELECT i.*,g.record_id,r.revision record_revision,r.list_type record_list_type,r.deleted_at record_deleted,p.revision public_revision,
      (SELECT '$.groups['||jg.key||'].entries['||e.key||']' FROM json_each(p.public_json,'$.groups') jg,json_each(jg.value,'$.entries') e WHERE json_extract(e.value,'$.id')=i.id LIMIT 1) public_path
    FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id JOIN public_records p ON p.record_id=r.id
    WHERE i.id=? AND g.record_id=?`).bind(typeof input.item_id==='string'?input.item_id:null,typeof input.record_id==='string'?input.record_id:null);}

function readHeader(db,input){
  validateMetadata(input.metadata||{});
  const keys=Object.keys(input.metadata||{});
  const oldMetadata=keys.length?"json_object("+keys.map(k=>"'"+k+"',json_extract(content_json,'$."+k+"')").join(',')+")":"'{}'";
  return db.prepare('SELECT r.id,r.revision,r.list_type,r.deleted_at,'+oldMetadata+' old_metadata,p.revision public_revision FROM records r JOIN public_records p ON p.record_id=r.id WHERE r.id=?').bind(typeof input.record_id==='string'?input.record_id:null);
}

function readaddOne(db,input){return db.prepare(`SELECT r.id,r.revision,r.list_type,r.deleted_at,p.revision public_revision,
    g.id group_id,g.kind,g.position FROM records r JOIN public_records p ON p.record_id=r.id
    LEFT JOIN record_groups g ON g.record_id=r.id AND g.list_type=? WHERE r.id=? ORDER BY CASE g.kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,g.position LIMIT 1`).bind((input.state||'wanted')==='wanted'?'want_list':'have_list',typeof input.record_id==='string'?input.record_id:null);}

function readremoveRestoreOne(db,input){return db.prepare(`SELECT i.*,g.record_id,r.revision record_revision,r.list_type record_list_type,r.deleted_at record_deleted,p.revision public_revision
    FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id JOIN public_records p ON p.record_id=r.id
    WHERE i.id=? AND g.record_id=?`).bind(typeof input.item_id==='string'?input.item_id:null,typeof input.record_id==='string'?input.record_id:null);}

export function mutationReads(db,input){
  const reads=[mutationControl(db,input)];
  if(!input||typeof input!=='object')return reads;
  const readers={transition:readtransitionOne,add:readaddOne,remove_item:readremoveRestoreOne,restore_item:readremoveRestoreOne,edit:readHeader,delete:readHeader,restore:readHeader};
  // Malformed input is rejected by mutate after session authorization; never
  // interpolate unvalidated metadata keys into SQL, even in speculative reads.
  if(Object.hasOwn(readers,input.op)){try{reads.push(readers[input.op](db,input));}catch{ /* validate after auth */ }}
  return reads;
}
