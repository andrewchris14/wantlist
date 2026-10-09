// Owner-facing read models. Historical source blobs stay in D1, not editor forms.
// Build the lean response in one consistent SQL read. The HTTP route forwards
// this JSON string without materializing/re-serializing thousands of item objects.
export async function ownerRecordJSON(db,id){
 const row=await db.prepare(`SELECT substr(header,1,length(header)-1)||',"groups":'||groups_json||'}' body FROM (SELECT json_object('id',r.id,'revision',r.revision,'list_type',r.list_type,'deleted_at',r.deleted_at,'content',json_object('source_list_type',json_extract(r.content_json,'$.source_list_type'),'entry_order',json_extract(r.content_json,'$.entry_order'),'display_year',json_extract(r.content_json,'$.display_year'),'display_category',json_extract(r.content_json,'$.display_category'),'year',json_extract(r.content_json,'$.year'),'brand',json_extract(r.content_json,'$.brand'),'set_name',json_extract(r.content_json,'$.set_name'),'category',json_extract(r.content_json,'$.category'),'notes',json_extract(r.content_json,'$.notes'),'prefixes',json_extract(r.content_json,'$.prefixes'),'uncertainty',json_extract(r.content_json,'$.uncertainty'))) header,(SELECT '['||COALESCE(group_concat(body,','),'')||']' FROM (SELECT substr(header,1,length(header)-1)||',"entries":'||entries||'}' body FROM (
 SELECT (SELECT json_group_object(key,json(value)) FROM (
  SELECT 'id' key,json_quote(g.id) value UNION ALL SELECT 'kind',json_quote(g.kind) UNION ALL SELECT 'list_type',json_quote(g.list_type)
  UNION ALL SELECT key,CASE WHEN type IN ('array','object') THEN value WHEN type IN ('true','false','null') THEN type ELSE json_quote(value) END FROM json_each(g.metadata_json) WHERE key IN ('label','description','notes')
 )) header,(SELECT json_group_array(json(entry)) FROM (
   SELECT json_object('id',i.id,'group_id',i.group_id,'value',i.value,'field_key',i.field_key,'position',i.position,'state',i.state,'actionable',i.actionable,'deleted_at',i.deleted_at,'individually_removed',CASE WHEN i.deleted_at IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM change_history h WHERE h.item_id=i.id AND h.record_id=g.record_id AND h.created_at=i.deleted_at AND h.action='remove_item' AND (i.actionable=1 OR json_extract(h.before_json,'$.group_list_type')=g.list_type)) END) entry
   FROM items i WHERE i.group_id=g.id ORDER BY CASE WHEN i.id LIKE 'owner-item-%' THEN 1 ELSE 0 END,CASE WHEN i.id NOT LIKE 'owner-item-%' THEN i.field_key END,i.position
  )) entries FROM record_groups g WHERE g.record_id=r.id ORDER BY CASE g.kind WHEN 'primary' THEN 0 WHEN 'mixed' THEN 1 ELSE 2 END,g.position
 ))) groups_json FROM records r WHERE r.id=?)`).bind(id).first();
 return row?.body||null;
}
export async function ownerRecord(db,id){
 const body=await ownerRecordJSON(db,id);return body?JSON.parse(body):null;
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
