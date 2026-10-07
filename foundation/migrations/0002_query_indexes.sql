-- Supersede redundant prefix indexes: existing UNIQUE indexes already serve
-- group listing and field/position ordering. These replacements serve actual
-- exact-item lookup and bounded recent-history query patterns.
DROP INDEX items_group;
DROP INDEX groups_record;
CREATE INDEX items_group_value ON items(group_id,value);
CREATE INDEX history_recent ON change_history(created_at DESC,id DESC);
CREATE INDEX history_record_recent ON change_history(record_id,created_at DESC,id DESC);
