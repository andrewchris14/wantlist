// Owner-facing read models. Historical source blobs stay in D1, not editor forms.
export async function ownerRecord(db,id){
 const r=await db.prepare(`SELECT id,revision,list_type,deleted_at,json_object(
 'source_list_type',json_extract(content_json,'$.source_list_type'),'entry_order',json_extract(content_json,'$.entry_order'),'display_year',json_extract(content_json,'$.display_year'),'display_category',json_extract(content_json,'$.display_category'),'year',json_extract(content_json,'$.year'),'brand',json_extract(content_json,'$.brand'),
 'set_name',json_extract(content_json,'$.set_name'),'category',json_extract(content_json,'$.category'),
 'notes',json_extract(content_json,'$.notes'),'prefixes',json_extract(content_json,'$.prefixes'),
 'uncertainty',json_extract(content_json,'$.uncertainty')) content FROM records WHERE id=?`).bind(id).first();
 if(!r)return null;r.content=JSON.parse(r.content);
 const groups=(await db.prepare('SELECT id,kind,list_type,metadata_json FROM record_groups WHERE record_id=? ORDER BY CASE kind WHEN \'primary\' THEN 0 WHEN \'mixed\' THEN 1 ELSE 2 END,position').bind(id).all()).results;
 const entries=(await db.prepare(`SELECT i.id,i.group_id,i.value,i.field_key,i.position,i.state,i.actionable,i.deleted_at,CASE WHEN i.deleted_at IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM change_history h INDEXED BY history_record_recent WHERE h.record_id=g.record_id AND h.created_at=i.deleted_at AND h.item_id=i.id AND h.action='remove_item' AND (i.actionable=1 OR json_extract(h.before_json,'$.group_list_type')=g.list_type)) END individually_removed FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? ORDER BY CASE WHEN i.id LIKE 'owner-item-%' THEN 1 ELSE 0 END,CASE WHEN i.id NOT LIKE 'owner-item-%' THEN i.field_key END,i.position`).bind(id).all()).results;
 const byGroup=new Map();for(const i of entries){if(!byGroup.has(i.group_id))byGroup.set(i.group_id,[]);byGroup.get(i.group_id).push(i);}
 r.groups=groups.map(g=>{const m=JSON.parse(g.metadata_json);return {id:g.id,kind:g.kind,list_type:g.list_type,label:m.label,description:m.description,notes:m.notes,entries:byGroup.get(g.id)||[]};});
 return r;
}
export function inverseOf(h){
 if(h.record_id?.startsWith('display-')&&['restore','create'].includes(h.action))return null;
 const before=typeof h.before_json==='string'?JSON.parse(h.before_json):h.before;
 const after=typeof h.after_json==='string'?JSON.parse(h.after_json):h.after;
 if(['edit_session','benchmark_cleanup'].includes(h.action))return {op:'undo_session',session_history:h.id};
 if(h.action==='replace_list')return {op:'restore_representation',replacement_history:h.id};
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
 const rows=(await db.prepare(`SELECT h.id,h.record_id,h.item_id,h.action,h.created_at,
 json_object('value',json_extract(h.before_json,'$.value'),'state',json_extract(h.before_json,'$.state'),'list_type',COALESCE(json_extract(h.before_json,'$.group_list_type'),json_extract(h.before_json,'$.list_type')),'metadata',json_extract(h.before_json,'$.metadata')) before_json,
 json_object('value',json_extract(h.after_json,'$.value'),'state',json_extract(h.after_json,'$.state'),'list_type',COALESCE(json_extract(h.after_json,'$.group_list_type'),json_extract(h.after_json,'$.list_type')),'metadata',json_extract(h.after_json,'$.metadata'),'_record_revision',json_extract(h.after_json,'$._record_revision'),'items',CASE WHEN h.action IN ('add','create') THEN json_extract(h.after_json,'$.items') ELSE json('[]') END) after_json,
 r.revision,json_object('year',json_extract(r.content_json,'$.year'),'brand',json_extract(r.content_json,'$.brand'),'set_name',json_extract(r.content_json,'$.set_name')) content
 FROM change_history h INDEXED BY history_recent JOIN records r ON r.id=h.record_id ORDER BY h.created_at DESC,COALESCE(json_extract(h.after_json,'$._record_revision'),0) DESC,h.id DESC LIMIT 20`).all()).results;
 const changes=rows.map(h=>{
  const before=JSON.parse(h.before_json),after=JSON.parse(h.after_json);
  const inverse=inverseOf(h),latest=after._record_revision===h.revision;
  // Only fields required for readable labels; never disclose arbitrary history.
  const summary=x=>({value:x.value,state:x.state,list_type:x.group_list_type||x.list_type,items:x.items?.map(i=>({value:i.value})),metadata:x.metadata?Object.fromEntries(Object.keys(x.metadata).map(k=>[k,true])):undefined});
  return {id:h.id,record_id:h.record_id,item_id:h.item_id,action:h.action,created_at:h.created_at,revision:h.revision,content:JSON.parse(h.content),before:summary(before),after:summary(after),undoable:!!inverse&&latest,undo_reason:!latest?'A newer change was made. Open this set to correct it.':'Open this set to remove the added cards individually.'};
 });
 const removed=(await db.prepare(`SELECT id,revision,json_object('year',json_extract(content_json,'$.year'),'brand',json_extract(content_json,'$.brand'),'set_name',json_extract(content_json,'$.set_name')) content FROM records WHERE deleted_at IS NOT NULL AND id NOT IN ('display-brewers-bobblehead-wantlist','display-eau-claire-players') ORDER BY deleted_at DESC LIMIT 20`).all()).results.map(r=>({...r,content:JSON.parse(r.content)}));
 return {changes,removed};
}
