import unittest,json
from foundation import storage
from foundation.staging import phase34_backup as backup
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def fixture():
 db=storage.connect();storage.apply_schema(db);db.executescript((ROOT/'foundation/staging/schema.sql').read_text());db.executescript((ROOT/'foundation/staging/categories.sql').read_text());return db
class CategoryBackupTests(unittest.TestCase):
 def test_extended_staging_backup_preserves_categories_and_audit_without_auth(self):
  db=fixture();fresh=fixture()
  try:
   db.execute("INSERT INTO categories VALUES('new','Twilight Zone Actors',0,1,NULL)");db.execute("INSERT INTO category_history VALUES('history','new','create','{}','{}','now')");db.commit()
   snap=backup.export(db);self.assertNotIn('sessions',snap['tables']);self.assertNotIn('login_limits',snap['tables']);backup.restore(fresh,snap);self.assertEqual(backup.export(fresh),snap)
   with self.assertRaises(ValueError):backup.restore(fresh,snap)
  finally:db.close();fresh.close()
