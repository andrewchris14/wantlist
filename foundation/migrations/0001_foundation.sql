-- Local/staging foundation only. Never executed by the Phase 3A website.
PRAGMA foreign_keys = ON;
CREATE TABLE foundation_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE import_batches (
  id TEXT PRIMARY KEY,
  baseline_commit TEXT NOT NULL,
  dataset_sha256 TEXT NOT NULL UNIQUE,
  header_json TEXT NOT NULL CHECK(json_valid(header_json)),
  imported_at TEXT NOT NULL
);
CREATE TABLE records (
  id TEXT PRIMARY KEY,
  -- Future owner-created records have NULL import_id; never invent Word refs.
  import_id TEXT REFERENCES import_batches(id),
  list_type TEXT NOT NULL CHECK(list_type IN ('want_list','have_list','complete','uncertain','needs_review')),
  content_json TEXT NOT NULL CHECK(json_valid(content_json) AND json_extract(content_json,'$.id') = id),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);
CREATE TABLE record_groups (
  id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL REFERENCES records(id),
  kind TEXT NOT NULL CHECK(kind IN ('primary','mixed','sublist')),
  position INTEGER NOT NULL CHECK(position >= 0),
  list_type TEXT NOT NULL CHECK(list_type IN ('want_list','have_list','complete','uncertain','needs_review')),
  metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
  inventory_keys_json TEXT NOT NULL CHECK(json_valid(inventory_keys_json)),
  UNIQUE(record_id,kind,position)
);
CREATE TABLE items (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL REFERENCES record_groups(id),
  field_key TEXT NOT NULL CHECK(field_key IN ('card_numbers','items','card_ranges')),
  position INTEGER NOT NULL CHECK(position >= 0),
  value TEXT NOT NULL CHECK(length(value) > 0),
  state TEXT CHECK(state IN ('wanted','pending','owned')),
  actionable INTEGER NOT NULL CHECK(actionable IN (0,1)),
  limitation TEXT,
  pending_at TEXT,
  received_at TEXT,
  deleted_at TEXT,
  CHECK((actionable = 1 AND state IS NOT NULL AND limitation IS NULL) OR (actionable = 0 AND state IS NULL AND limitation IS NOT NULL)),
  CHECK(state != 'pending' OR pending_at IS NOT NULL),
  UNIQUE(group_id,field_key,position)
);
CREATE INDEX items_group ON items(group_id);
CREATE INDEX groups_record ON record_groups(record_id);
CREATE TABLE provenance (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  baseline_json TEXT NOT NULL CHECK(json_valid(baseline_json)),
  baseline_sha256 TEXT NOT NULL,
  source_refs_json TEXT NOT NULL CHECK(json_valid(source_refs_json))
);
CREATE TABLE private_details (
  item_id TEXT PRIMARY KEY REFERENCES items(id),
  details_json TEXT NOT NULL CHECK(json_valid(details_json))
);
CREATE TABLE change_history (
  id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL REFERENCES records(id),
  item_id TEXT REFERENCES items(id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT NOT NULL CHECK(json_valid(before_json)),
  after_json TEXT NOT NULL CHECK(json_valid(after_json)),
  created_at TEXT NOT NULL
);
CREATE TABLE owners (
  id TEXT PRIMARY KEY CHECK(id = 'owner'),
  password_verifier_json TEXT NOT NULL CHECK(json_valid(password_verifier_json)),
  auth_version INTEGER NOT NULL DEFAULT 1 CHECK(auth_version >= 1)
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES owners(id),
  auth_version INTEGER NOT NULL,
  remembered INTEGER NOT NULL CHECK(remembered IN (0,1)),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL CHECK(expires_at > created_at),
  last_seen_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE TABLE login_limits (
  bucket TEXT PRIMARY KEY,
  window_start INTEGER NOT NULL,
  attempts INTEGER NOT NULL CHECK(attempts >= 0)
);
