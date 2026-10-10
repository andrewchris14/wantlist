"""Fixed disposable-only verification SQL. None executes at import time."""
from .minimal_free_plan import FIXTURE_RECORD, FIXTURE_GROUP
SCHEMA = "SELECT name,sql FROM sqlite_master WHERE name IN ('items_group_value','history_record_recent','history_item_reference','public_browse_index','public_index_insert','public_index_update')"
# Saturating count bounds a possible index build; a saturated result stops it.
SCAN = 'SELECT count(*) n FROM (SELECT rowid FROM change_history LIMIT 1001)'
FIXTURE = """WITH inventory AS MATERIALIZED (SELECT state,deleted_at,actionable FROM items WHERE group_id=? LIMIT 2030),
 totals AS (SELECT count(*) total,sum(deleted_at IS NULL AND state='wanted' AND actionable=1) active,sum(deleted_at IS NOT NULL) removed FROM inventory)
 SELECT r.revision,r.list_type,r.deleted_at,
 json_extract(r.content_json,'$.creation_origin') marker,
 (SELECT count(*) FROM record_groups WHERE record_id=r.id) groups,
 (SELECT revision FROM public_records WHERE record_id=r.id) public_revision,
 (SELECT revision FROM public_browse_index WHERE record_id=r.id) browse_revision,
 t.total,t.active,t.removed FROM records r CROSS JOIN totals t WHERE r.id=?"""
FIXTURE_PARAMS = [FIXTURE_GROUP,FIXTURE_RECORD]
STATE = """WITH counts AS (SELECT sum(deleted_at IS NULL) active,sum(deleted_at IS NOT NULL) removed FROM items WHERE group_id=?) SELECT r.content_json,
 (SELECT json_group_array(json(body)) FROM (SELECT json_object('id',i.id,'group_id',i.group_id,'field_key',i.field_key,'position',i.position,'value',i.value,'state',i.state,'actionable',i.actionable,'limitation',i.limitation,'pending_at',i.pending_at,'received_at',i.received_at,'deleted_at',i.deleted_at) body FROM json_each(?) ids CROSS JOIN items i WHERE i.id=ids.value AND i.group_id=? ORDER BY i.id)) original_items,
 c.active,c.removed,
 (SELECT revision FROM public_records WHERE record_id=r.id) public_revision,
 (SELECT revision FROM public_browse_index WHERE record_id=r.id) browse_revision,
 (SELECT json_extract(public_json,'$.notes') FROM public_records WHERE record_id=r.id) public_notes,
 (SELECT json_extract(index_json,'$.notes') FROM public_browse_index WHERE record_id=r.id) browse_notes,
 (SELECT sum(json_array_length(g.value,'$.entries')) FROM public_records p,json_each(p.public_json,'$.groups') g WHERE p.record_id=r.id) public_active,
 (SELECT json_group_array(json_object('id',id,'kind',kind,'position',position,'list_type',list_type,'metadata_json',metadata_json,'inventory_keys_json',inventory_keys_json)) FROM record_groups WHERE record_id=r.id) original_groups,
 (SELECT json_object('baseline_sha256',baseline_sha256,'baseline_json',json(baseline_json),'source_refs_json',json(source_refs_json)) FROM provenance WHERE record_id=r.id) provenance,r.revision
 FROM records r CROSS JOIN counts c WHERE r.id=? AND json_extract(r.content_json,'$.creation_origin')='synthetic-disposable-http-review'"""
RECEIPT = 'SELECT record_id,result_json,request_sha256 FROM mutation_receipts WHERE id=?'
HISTORY = "SELECT id FROM change_history WHERE record_id=? AND action='edit_session' AND json_extract(after_json,'$._record_revision')=? ORDER BY created_at DESC,id DESC LIMIT 2"
