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
  const groups=(await db.prepare('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position').bind(id).all()).results;
  const entries=(await db.prepare(`SELECT i.* FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? ORDER BY g.kind,g.position,i.field_key,i.position`).bind(id).all()).results;
  return {...r,content:JSON.parse(r.content_json),groups:groups.map(g=>({...g,entries:entries.filter(i=>i.group_id===g.id)}))};
}
export function publicProjection(r){
  const out={};for(const k of publicKeys)if(k in r.content)out[k]=r.content[k];
  Object.assign(out,{list_type:r.list_type,revision:r.revision,updated_at:r.updated_at,deleted:!!r.deleted_at,groups:[]});
  if(!r.deleted_at)out.groups=r.groups.map(g=>{
    const m=JSON.parse(g.metadata_json),body={id:g.id,kind:g.kind,list_type:g.list_type};
    for(const k of ['label','description','notes','source_list_type'])if(k in m)body[k]=m[k];
    body.entries=g.entries.filter(i=>!i.deleted_at).map(i=>({id:i.id,value:i.value,field_key:i.field_key,state:i.state,actionable:i.actionable,pending_at:i.pending_at,received_at:i.received_at}));
    return body;
  });
  return out;
}
function validateMetadata(data,creating=false){
  if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).some(k=>!metadataKeys.includes(k)))fail();
  for(const k of ['year','brand','set_name','category','section'])if(k in data&&data[k]!==null&&(typeof data[k]!=='string'||data[k].length>500))fail();
  if((creating||'set_name'in data)&&(!data.set_name||!data.set_name.trim()))fail();
  for(const k of ['notes','prefixes','uncertainty'])if(k in data&&(!Array.isArray(data[k])||data[k].some(x=>typeof x!=='string'||x.length>10000)))fail();
  if(data.set_size!=null&&(!Number.isInteger(data.set_size)||data.set_size<1))fail();
}
export async function mutate(db,input){
  if(!input||typeof input!=='object'||typeof input.request_id!=='string'||!/^[-\w]{16,100}$/.test(input.request_id))fail();
  const requestHash=await hash(JSON.stringify(input));
  const receipt=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();
  if(receipt){if(receipt.request_sha256!==requestHash)fail('CONFLICT');return {...JSON.parse(receipt.result_json),replayed:true};}
  const ready=await db.prepare('SELECT completed FROM staging_import_state WHERE id=1').first();
  if(!ready||!ready.completed)fail('CONFLICT');
  if(input.op==='transition')return transitionOne(db,input,requestHash);
  if(['edit','delete','restore'].includes(input.op))return editHeaderOne(db,input,requestHash);
  const stamp=new Date().toISOString(),sql=[];let r,before={},after={},itemId=null;
  if(input.op==='create'){
    validateMetadata(input.metadata,true);const mode=input.list_type||'want_list';if(!modes.includes(mode))fail();
    const id='owner-record-'+crypto.randomUUID();
    r={id,import_id:null,list_type:mode,revision:1,created_at:stamp,updated_at:stamp,deleted_at:null,content:{id,creation_origin:'owner',notes:[],prefixes:[],uncertainty:[],...input.metadata},groups:[]};
    sql.push(statement('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)',id,mode,JSON.stringify(r.content),stamp,stamp));
  }else{
    if(!Number.isInteger(input.revision)||input.revision<1)fail();
    r=await openRecord(db,input.record_id);if(!r||r.revision!==input.revision)fail('CONFLICT');
    if((r.deleted_at&&input.op!=='restore')||(!r.deleted_at&&input.op==='restore'))fail('CONFLICT');
    r.revision++;r.updated_at=stamp;
  }
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
    after={metadata:r.content,list_type:r.list_type,items:r.groups.flatMap(g=>g.entries).map(i=>({id:i.id,value:i.value,field_key:i.field_key,state:i.state}))};
  }else if(input.op==='add')add(input.values,input.state||'wanted',input.field_key||'card_numbers');
  else if(['transition','remove_item','restore_item'].includes(input.op)){
    const i=r.groups.flatMap(g=>g.entries).find(i=>i.id===input.item_id);if(!i)fail();itemId=i.id;before={...i};
    if(input.op==='transition'){
      if(i.deleted_at||!i.actionable||!({wanted:['pending','owned'],pending:['wanted','owned'],owned:['wanted']}[i.state]||[]).includes(input.state))fail();
      if(r.list_type==='complete'&&['wanted','pending'].includes(input.state))fail();
      i.state=input.state;i.pending_at=i.state==='pending'?stamp:null;i.received_at=i.state==='owned'?stamp:null;
      sql.push(statement('UPDATE items SET state=?,pending_at=?,received_at=? WHERE id=?',i.state,i.pending_at,i.received_at,i.id));
    }else{
      if(input.op==='remove_item'){if(i.deleted_at)fail();i.deleted_at=stamp;}
      else{if(!i.deleted_at||(r.list_type==='complete'&&['wanted','pending'].includes(i.state))||r.groups.flatMap(g=>g.entries).some(other=>other.id!==i.id&&other.group_id===i.group_id&&other.value===i.value&&!other.deleted_at))fail();i.deleted_at=null;}
      sql.push(statement('UPDATE items SET deleted_at=? WHERE id=?',i.deleted_at,i.id));
    }
    after={...i};
  }else if(input.op==='edit'){
    validateMetadata(input.metadata||{});before={metadata:Object.fromEntries(Object.keys(input.metadata||{}).map(k=>[k,r.content[k]??null])),list_type:r.list_type};
    const mode=input.list_type||r.list_type;if(!modes.includes(mode))fail();
    if(mode==='complete'&&r.groups.some(g=>g.entries.some(i=>!i.deleted_at&&(['wanted','pending'].includes(i.state)||(!i.actionable&&g.list_type==='want_list')))))fail();
    Object.assign(r.content,input.metadata||{});r.list_type=mode;after={metadata:input.metadata||{},list_type:mode};
  }else if(input.op==='delete'||input.op==='restore'){
    before={deleted_at:r.deleted_at};r.deleted_at=input.op==='delete'?stamp:null;after={deleted_at:r.deleted_at};
  }else fail();
  const result={saved:true,record_id:r.id,revision:r.revision};
  // D1 batch is transactional. The CHECK guard rolls back EVERY statement if
  // another writer changed the revision between our reads and this batch.
  if(input.op!=='create')sql.unshift(statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,r.id,r.id,input.revision,JSON.stringify(result),stamp));
  else sql.push(statement('INSERT INTO mutation_receipts VALUES(?,?,?,1,?,?)',input.request_id,requestHash,r.id,JSON.stringify(result),stamp));
  if(input.op!=='create')sql.push(statement('UPDATE records SET content_json=?,list_type=?,revision=?,updated_at=?,deleted_at=? WHERE id=?',JSON.stringify(r.content),r.list_type,r.revision,stamp,r.deleted_at,r.id));
  sql.push(statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),r.id,itemId,'owner',input.op,JSON.stringify(before),JSON.stringify(after),stamp));
  sql.push(statement(`INSERT INTO public_records VALUES(?,?,?,?,?) ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at,deleted=excluded.deleted,public_json=excluded.public_json`,r.id,r.revision,stamp,r.deleted_at?1:0,JSON.stringify(publicProjection(r))));
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
async function transitionOne(db,input,requestHash){
  if(!Number.isInteger(input.revision)||input.revision<1||!['wanted','pending','owned'].includes(input.state))fail();
  const row=await db.prepare(`SELECT i.*,g.record_id,r.revision record_revision,r.list_type record_list_type,r.deleted_at record_deleted
    FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id
    WHERE i.id=? AND g.record_id=?`).bind(input.item_id,input.record_id).first();
  if(!row||row.record_revision!==input.revision||row.record_deleted)fail('CONFLICT');
  if(!row.actionable||row.deleted_at||!({wanted:['pending','owned'],pending:['wanted','owned'],owned:['wanted']}[row.state]||[]).includes(input.state))fail();
  if(row.record_list_type==='complete'&&['wanted','pending'].includes(input.state))fail();
  const location=await db.prepare(`SELECT p.revision,'$.groups['||g.key||'].entries['||e.key||']' path
    FROM public_records p,json_each(p.public_json,'$.groups') g,json_each(g.value,'$.entries') e
    WHERE p.record_id=? AND json_extract(e.value,'$.id')=? LIMIT 1`).bind(row.record_id,row.id).first();
  if(!location||location.revision!==input.revision)fail('CONFLICT');
  const stamp=new Date().toISOString(),revision=input.revision+1;
  const before=Object.fromEntries(Object.entries(row).filter(([key])=>!['record_id','record_revision','record_list_type','record_deleted'].includes(key)));
  const after={...before,state:input.state,pending_at:input.state==='pending'?stamp:null,received_at:input.state==='owned'?stamp:null};
  const published=Object.fromEntries(['id','value','field_key','state','actionable','pending_at','received_at'].map(k=>[k,after[k]]));
  const result={saved:true,record_id:row.record_id,revision};
  const statements=[
    statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,row.record_id,row.record_id,input.revision,JSON.stringify(result),stamp),
    statement('UPDATE items SET state=?,pending_at=?,received_at=? WHERE id=?',after.state,after.pending_at,after.received_at,row.id),
    statement('UPDATE records SET revision=?,updated_at=? WHERE id=?',revision,stamp,row.record_id),
    statement('INSERT INTO change_history VALUES(?,?,?,?,?,?,?,?)',crypto.randomUUID(),row.record_id,row.id,'owner','transition',JSON.stringify(before),JSON.stringify(after),stamp),
    statement("UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(public_json,'$.revision',?,'$.updated_at',?, ?,json(?)) WHERE record_id=?",revision,stamp,revision,stamp,location.path,JSON.stringify(published),row.record_id)
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
async function editHeaderOne(db,input,requestHash){
  if(!Number.isInteger(input.revision)||input.revision<1)fail();
  const row=await db.prepare('SELECT * FROM records WHERE id=?').bind(input.record_id).first();
  if(!row||row.revision!==input.revision||(row.deleted_at&&input.op!=='restore')||(!row.deleted_at&&input.op==='restore'))fail('CONFLICT');
  const projection=await db.prepare('SELECT revision FROM public_records WHERE record_id=?').bind(row.id).first();
  if(!projection||projection.revision!==input.revision)fail('CONFLICT');
  const content=JSON.parse(row.content_json),stamp=new Date().toISOString(),revision=input.revision+1;
  let mode=row.list_type,deleted=row.deleted_at,before={},after={},patch={revision,updated_at:stamp};
  if(input.op==='edit'){
    validateMetadata(input.metadata||{});mode=input.list_type||mode;if(!modes.includes(mode))fail();
    if(mode==='complete'){
      const needed=await db.prepare(`SELECT i.id FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? AND i.deleted_at IS NULL
        AND (i.state IN ('wanted','pending') OR (i.actionable=0 AND g.list_type='want_list')) LIMIT 1`).bind(row.id).first();if(needed)fail();
    }
    before={metadata:Object.fromEntries(Object.keys(input.metadata||{}).map(k=>[k,content[k]??null])),list_type:row.list_type};
    Object.assign(content,input.metadata||{});after={metadata:input.metadata||{},list_type:mode};patch={...patch,...input.metadata,list_type:mode};
  }else{
    deleted=input.op==='delete'?stamp:null;before={deleted_at:row.deleted_at};after={deleted_at:deleted};patch.deleted=!!deleted;
  }
  const result={saved:true,record_id:row.id,revision};
  const pairs=Object.entries(patch),paths=pairs.map(()=>',?,json(?)').join('');
  const statements=[
    statement(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`,input.request_id,requestHash,row.id,row.id,input.revision,JSON.stringify(result),stamp),
    statement('UPDATE records SET content_json=?,list_type=?,revision=?,updated_at=?,deleted_at=? WHERE id=?',JSON.stringify(content),mode,revision,stamp,deleted,row.id),
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
