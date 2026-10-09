// Deliberate bounded representation replacement, never checklist inference.
// Old rows remain soft-deleted; history records their exact live membership in D1.
const fail=(code='INVALID')=>{const e=Error(code);e.code=code;throw e;};
export async function replaceList(db,input,requestHash){
 const undo=input.op==='restore_representation';
 // These source sections have fixed WANT/HAVE meanings; edit their individual
 // items/notes instead of replacing the whole historical container.
 if(input.record_id?.startsWith('display-'))fail();
 if(!Number.isInteger(input.revision)||input.revision<1)fail();
 let prior=null;
 if(undo){prior=await db.prepare('SELECT before_json,after_json FROM change_history WHERE id=? AND record_id=? AND action=\'replace_list\'').bind(input.replacement_history,input.record_id).first();if(!prior)fail();prior={before:JSON.parse(prior.before_json),after:JSON.parse(prior.after_json)};if(prior.after._record_revision!==input.revision)fail('CONFLICT');}
 const gid=undo?prior.before.group_id:input.group_id;
 const row=await db.prepare(`SELECT r.id,r.revision,r.list_type,r.deleted_at,g.id gid,g.kind group_kind,g.list_type group_type,p.revision public_revision,
 (SELECT '$.groups['||key||']' FROM json_each(p.public_json,'$.groups') WHERE json_extract(value,'$.id')=g.id) path,
 (SELECT COALESCE(MAX(position),-1)+1 FROM items WHERE group_id=g.id AND field_key=?) position
 FROM records r JOIN record_groups g ON g.record_id=r.id JOIN public_records p ON p.record_id=r.id WHERE r.id=? AND g.id=?`).bind(input.field_key||'card_numbers',input.record_id,gid).first();
 if(!row||row.deleted_at||row.revision!==input.revision||row.public_revision!==input.revision||!row.path)fail('CONFLICT');
 const mode=undo?prior.before.group_list_type:input.list_type;
 if(!(undo?['want_list','have_list','complete','uncertain']:['want_list','have_list']).includes(mode))fail();
 let values=input.values||[];const field=input.field_key||'card_numbers';
 if(!undo&&(!['card_numbers','items'].includes(field)||!Array.isArray(values)||values.length>500||values.some(v=>typeof v!=='string'||!v.trim()||v.length>500)||new Set(values.map(v=>v.trim())).size!==values.length))fail();
 if(!undo)values=values.map(v=>v.trim());
 const metadata=undo?(prior.before.metadata||{}):(input.metadata||{}),keys=Object.keys(metadata);
 const oldMetadata=keys.length?await db.prepare("SELECT json_object("+keys.map(k=>"'"+k+"',json_extract(content_json,'$."+k+"')").join(',')+") value FROM records WHERE id=?").bind(row.id).first():{value:'{}'};
 const stamp=new Date().toISOString(),revision=row.revision+1,state=mode==='have_list'?'owned':'wanted';
 const sameMeaning=mode===row.group_type;
 // Only matching identifiers cross the Worker boundary. Large old inventories
 // and pending-removal counting stay in D1 rather than consuming Worker CPU.
 const existing=undo||!sameMeaning?[]:(await db.prepare('SELECT id,value,field_key,position,state,actionable,pending_at,received_at FROM items WHERE group_id=? AND deleted_at IS NULL AND value IN (SELECT value FROM json_each(?)) LIMIT 501').bind(gid,JSON.stringify(values)).all()).results;
 if(existing.length>500||new Set(existing.map(i=>i.value)).size!==existing.length)fail();
 const retained=new Map(existing.map(i=>[i.value,i]));
 const pending=undo?null:await db.prepare('SELECT count(*) n FROM items WHERE group_id=? AND deleted_at IS NULL AND state=\'pending\' AND (?=0 OR value NOT IN (SELECT value FROM json_each(?)))').bind(gid,sameMeaning?1:0,JSON.stringify(values)).first();
 if(pending?.n&&input.confirm_pending_removal!==true)fail();
 const items=undo?[]:values.map((v,i)=>retained.get(v.trim())||({id:crypto.randomUUID(),value:v.trim(),field_key:field,position:row.position+i,state,actionable:1,pending_at:null,received_at:null}));
 const after={group_id:gid,list_type:undo?prior.before.list_type:row.group_kind==='primary'?mode:row.list_type,group_list_type:mode,items:items.map(i=>({id:i.id,value:i.value})),_record_revision:revision};
 const result={saved:true,record_id:row.id,revision},historyId=crypto.randomUUID();
 const st=[db.prepare(`INSERT INTO mutation_receipts VALUES(?,?,?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN 1 ELSE 0 END,?,?)`).bind(input.request_id,requestHash,row.id,row.id,input.revision,JSON.stringify(result),stamp)];
 // Capture live identifiers before changing anything; no old inventory crosses Worker.
 st.push(db.prepare(`INSERT INTO change_history SELECT ?,?,NULL,'owner',?,json_object('list_type',?,'group_list_type',?,'group_id',?,'metadata',json(?),'active_ids',json(COALESCE((SELECT json_group_array(id) FROM items WHERE group_id=? AND deleted_at IS NULL),'[]'))),?,?`).bind(historyId,row.id,input.op,row.list_type,row.group_type,gid,oldMetadata.value,gid,JSON.stringify(after),stamp));
 if(undo){
  st.push(db.prepare('UPDATE items SET deleted_at=? WHERE id IN (SELECT json_extract(value,\'$.id\') FROM json_each(?)) AND group_id=?').bind(stamp,JSON.stringify(prior.after.items),gid));
  st.push(db.prepare('UPDATE items SET deleted_at=NULL WHERE id IN (SELECT value FROM json_each(?)) AND group_id=?').bind(JSON.stringify(prior.before.active_ids),gid));
 }else{
  const kept=items.filter(i=>retained.get(i.value)?.id===i.id).map(i=>i.id),keptSet=new Set(kept),fresh=items.filter(i=>!keptSet.has(i.id));
  st.push(db.prepare('UPDATE items SET deleted_at=? WHERE group_id=? AND deleted_at IS NULL AND id NOT IN (SELECT value FROM json_each(?))').bind(stamp,gid,JSON.stringify(kept)));
  for(let offset=0;offset<fresh.length;offset+=16){const part=fresh.slice(offset,offset+16);st.push(db.prepare('INSERT INTO items VALUES '+part.map(()=>'(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)').join(',')).bind(...part.flatMap(i=>[i.id,gid,field,i.position,i.value,state])));}
 }
 st.push(db.prepare('UPDATE record_groups SET list_type=? WHERE id=?').bind(mode,gid));
 st.push(db.prepare('UPDATE records SET list_type=?,revision=?,updated_at=?,content_json=json_patch(content_json,?) WHERE id=?').bind(after.list_type,revision,stamp,JSON.stringify(metadata),row.id));
 st.push(db.prepare(`UPDATE public_records SET revision=?,updated_at=?,public_json=json_set(json_patch(public_json,?),'$.revision',?,'$.updated_at',?,'$.list_type',?, ?,?, ?,json((SELECT json_group_array(json(body)) FROM (SELECT json_object('id',id,'value',value,'position',position,'field_key',field_key,'state',state,'actionable',actionable,'pending_at',pending_at,'received_at',received_at) body FROM items WHERE group_id=? AND deleted_at IS NULL ORDER BY field_key,position)))) WHERE record_id=?`).bind(revision,stamp,JSON.stringify(metadata),revision,stamp,after.list_type,row.path+'.list_type',mode,row.path+'.entries',gid,row.id));
 try{await db.batch(st);}catch(e){const receipt=await db.prepare('SELECT request_sha256,result_json FROM mutation_receipts WHERE id=?').bind(input.request_id).first();if(receipt&&receipt.request_sha256===requestHash)return {...JSON.parse(receipt.result_json),replayed:true};if(/CHECK constraint|UNIQUE constraint/i.test(e.message))fail('CONFLICT');throw e;}
 return result;
}
