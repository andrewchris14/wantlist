-- Staging-only durable quota reservations; not part of the historical schema.
CREATE TABLE IF NOT EXISTS import_write_days (
  day TEXT PRIMARY KEY,
  reserved INTEGER NOT NULL CHECK(reserved>=0),
  budget INTEGER NOT NULL CHECK(budget>0 AND budget<=80000),
  CHECK(reserved<=budget)
);
CREATE TABLE IF NOT EXISTS import_write_attempts (
  id TEXT PRIMARY KEY,
  chunk_id TEXT NOT NULL,
  day TEXT NOT NULL REFERENCES import_write_days(day),
  reserved INTEGER NOT NULL CHECK(reserved>0),
  actual INTEGER CHECK(actual>=0 AND actual<=reserved),
  completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN(0,1))
);
