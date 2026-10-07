-- Apply AFTER approved foundation migrations, only to a new staging database.
-- The old local-only PBKDF2 owner/session schema is superseded, not populated.
DROP TABLE sessions;
DROP TABLE owners;
CREATE TABLE auth_control (
  id INTEGER PRIMARY KEY CHECK(id=1),
  generation INTEGER NOT NULL CHECK(generation>=1)
);
INSERT INTO auth_control VALUES(1,1);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY CHECK(length(token_hash)=64),
  credential_version TEXT NOT NULL,
  revocation_generation INTEGER NOT NULL,
  remembered INTEGER NOT NULL CHECK(remembered IN (0,1)),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL CHECK(expires_at>created_at),
  last_seen_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE TABLE staging_import_state (
  id INTEGER PRIMARY KEY CHECK(id=1),
  baseline_sha256 TEXT NOT NULL,
  selection_sha256 TEXT NOT NULL,
  expected_records INTEGER NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN(0,1))
);
CREATE TABLE staging_import_chunks (
  id TEXT PRIMARY KEY,
  content_sha256 TEXT NOT NULL,
  records_added INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE mutation_receipts (
  id TEXT PRIMARY KEY,
  request_sha256 TEXT NOT NULL,
  record_id TEXT NOT NULL REFERENCES records(id),
  guard INTEGER NOT NULL CHECK(guard=1),
  result_json TEXT NOT NULL CHECK(json_valid(result_json)),
  created_at TEXT NOT NULL
);
CREATE TABLE public_records (
  record_id TEXT PRIMARY KEY REFERENCES records(id),
  revision INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  deleted INTEGER NOT NULL CHECK(deleted IN(0,1)),
  public_json TEXT NOT NULL CHECK(json_valid(public_json))
);
