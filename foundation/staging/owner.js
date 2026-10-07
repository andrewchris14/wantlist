// Owner-facing read models. Historical source blobs stay in D1, not editor forms.
export async function ownerRecord(db,id){
 const r=await db.prepare(`SELECT id,revision,list_type,deleted_at,json_object(
 'year',json_extract(content_json,'$.year'),'brand',json_extract(content_json,'$.brand'),
 'set_name',json_extract(content_json,'$.set_name'),'category',json_extract(content_json,'$.category'),
 'notes',json_extract(content_json,'$.notes'),'prefixes',json_extract(content_json,'$.prefixes'),
 'uncertainty',json_extract(content_json,'$.uncertainty')) content FROM records WHERE id=?`).bind(id).first();
 if(!r)return null;r.content=JSON.parse(r.content);
 const groups=(await db.prepare('SELECT id,list_type,metadata_json FROM record_groups WHERE record_id=? ORDER BY CASE kind WHEN \'primary\' THEN 0 WHEN \'mixed\' THEN 1 ELSE 2 END,position').bind(id).all()).results;
 const entries=(await db.prepare('SELECT i.id,i.group_id,i.value,i.field_key,i.position,i.state,i.actionable,i.deleted_at FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? ORDER BY i.field_key,i.position').bind(id).all()).results;
 const byGroup=new Map();for(const i of entries){if(!byGroup.has(i.group_id))byGroup.set(i.group_id,[]);byGroup.get(i.group_id).push(i);}
 r.groups=groups.map(g=>{const m=JSON.parse(g.metadata_json);return {id:g.id,list_type:g.list_type,label:m.label,description:m.description,notes:m.notes,entries:byGroup.get(g.id)||[]};});
 return r;
}
export function inverseOf(h){
 const before=typeof h.before_json==='string'?JSON.parse(h.before_json):h.before;
 const after=typeof h.after_json==='string'?JSON.parse(h.after_json):h.after;
 if(h.action==='transition')return {op:'transition',item_id:h.item_id,state:before.state};
 if(h.action==='remove_item')return {op:'restore_item',item_id:h.item_id};
 if(h.action==='restore_item')return {op:'remove_item',item_id:h.item_id};
 if(h.action==='delete')return {op:'restore'};
 if(h.action==='restore'||h.action==='create')return {op:'delete'};
 if(h.action==='edit')return {op:'edit',metadata:before.metadata||{},list_type:before.list_type};
 if(h.action==='add'&&after.items?.length===1)return {op:'remove_item',item_id:after.items[0].id};
 return null;
}
export async function recentOwner(db){
 const rows=(await db.prepare(`SELECT h.*,r.revision,json_object('year',json_extract(r.content_json,'$.year'),'brand',json_extract(r.content_json,'$.brand'),'set_name',json_extract(r.content_json,'$.set_name')) content
 FROM change_history h INDEXED BY history_recent JOIN records r ON r.id=h.record_id ORDER BY h.created_at DESC,COALESCE(json_extract(h.after_json,'$._record_revision'),0) DESC,h.id DESC LIMIT 20`).all()).results;
 const changes=rows.map(h=>{
  const before=JSON.parse(h.before_json),after=JSON.parse(h.after_json);
  const inverse=inverseOf(h),latest=after._record_revision===h.revision;
  // Only fields required for readable labels; never disclose arbitrary history.
  const summary=x=>({value:x.value,state:x.state,items:x.items?.map(i=>({value:i.value})),metadata:x.metadata?Object.fromEntries(Object.keys(x.metadata).map(k=>[k,true])):undefined});
  return {id:h.id,record_id:h.record_id,item_id:h.item_id,action:h.action,created_at:h.created_at,revision:h.revision,content:JSON.parse(h.content),before:summary(before),after:summary(after),undoable:!!inverse&&latest,undo_reason:!latest?'A newer change was made. Open this set to correct it.':'Open this set to remove the added cards individually.'};
 });
 const removed=(await db.prepare(`SELECT id,revision,json_object('year',json_extract(content_json,'$.year'),'brand',json_extract(content_json,'$.brand'),'set_name',json_extract(content_json,'$.set_name')) content FROM records WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC LIMIT 20`).all()).results.map(r=>({...r,content:JSON.parse(r.content)}));
 return {changes,removed};
}
