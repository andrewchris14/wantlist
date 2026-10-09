"""Authentication-free application backup, including categories and D1 projections.
Restore is intentionally local/disposable only; never resets live owner sessions.
"""
import json
from foundation import storage
TABLES=('categories','foundation_meta','import_batches','records','record_groups','items','provenance','private_details','change_history','public_records','mutation_receipts','staging_import_state','staging_import_chunks','category_history','category_receipts')
def export(db):
 return {'export_schema':'wantlist-staging-private-v2','baseline_sha256':storage.BASELINE_SHA256,'tables':{t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in TABLES}}
def restore(db,snapshot):
 if snapshot.get('export_schema')!='wantlist-staging-private-v2' or snapshot.get('baseline_sha256')!=storage.BASELINE_SHA256 or set(snapshot.get('tables',{}))!=set(TABLES):raise ValueError('Unsupported staging backup')
 if any(db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in TABLES if t!='categories'):raise ValueError('Restore only into a NEW disposable database')
 if db.execute('SELECT count(*) FROM sessions').fetchone()[0]:raise ValueError('Restore cannot overwrite sessions')
 with db:
  db.execute('DELETE FROM categories')
  for table in TABLES:
   columns=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
   for row in snapshot['tables'][table]:
    if set(row)!=set(columns):raise ValueError('Unexpected staging backup columns')
    db.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[row[k] for k in columns])
  if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Staging foreign-key check failed')
