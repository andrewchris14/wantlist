-- Additive staging-only category registry; never applied to production.
CREATE TABLE IF NOT EXISTS categories (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
 historical INTEGER NOT NULL CHECK(historical IN(0,1)), revision INTEGER NOT NULL DEFAULT 1,
 deleted_at TEXT
);
INSERT OR IGNORE INTO categories(id,name,historical) VALUES
 ('historical-obc','OBC Wantlist',1),('historical-uv','UV Wantlist',1),
 ('historical-eau','Eau Claire Players',1),('historical-photos','Milwaukee 8x10 List',1),
 ('historical-bobbleheads','Brewers Bobblehead Wantlist',1),
 ('historical-football','Football Wantlist',1),('historical-other','Other Stuff',1);
CREATE TABLE IF NOT EXISTS category_history (
 id TEXT PRIMARY KEY, category_id TEXT NOT NULL REFERENCES categories(id),
 action TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS category_receipts (
 id TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL,
 guard INTEGER NOT NULL CHECK(guard=1), result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
-- These guards close concurrent category removal/creation and move races.
CREATE TRIGGER IF NOT EXISTS record_category_insert BEFORE INSERT ON records
WHEN json_extract(NEW.content_json,'$.display_category') IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM categories WHERE name=json_extract(NEW.content_json,'$.display_category') AND deleted_at IS NULL)
BEGIN SELECT RAISE(ABORT,'Unknown category'); END;
CREATE TRIGGER IF NOT EXISTS record_category_update BEFORE UPDATE OF content_json ON records
WHEN json_extract(NEW.content_json,'$.display_category') IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM categories WHERE name=json_extract(NEW.content_json,'$.display_category') AND deleted_at IS NULL)
BEGIN SELECT RAISE(ABORT,'Unknown category'); END;
CREATE TRIGGER IF NOT EXISTS category_protect BEFORE UPDATE ON categories
WHEN OLD.historical=1 AND (NEW.name!=OLD.name OR NEW.deleted_at IS NOT OLD.deleted_at OR NEW.historical!=1)
BEGIN SELECT RAISE(ABORT,'Historical category protected'); END;
CREATE TRIGGER IF NOT EXISTS category_nonempty BEFORE UPDATE OF deleted_at ON categories
WHEN NEW.deleted_at IS NOT NULL AND EXISTS(SELECT 1 FROM records WHERE json_extract(content_json,'$.display_category')=OLD.name)
BEGIN SELECT RAISE(ABORT,'Category contains listings'); END;

CREATE INDEX IF NOT EXISTS records_display_category ON records(json_extract(content_json,'$.display_category'));
CREATE INDEX IF NOT EXISTS items_group_value ON items(group_id,value);
