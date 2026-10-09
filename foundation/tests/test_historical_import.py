import copy,json,unittest
from pathlib import Path
from foundation.staging import historical_import as h
from foundation.staging.import_rehearsal import fresh

class DerivedRemoteSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=h.manifest()
    def setUp(self):
        self.db=fresh();self.db.executescript((h.storage.ROOT/'foundation/staging/public-index.sql').read_text());self.db.executescript(h.schema());self.t=h.Local(self.db);self.i=h.Importer(self.t,self.plan);self.i.prepare()
    def tearDown(self):self.db.close()
    def test_atomic_receipt_projection_retry_and_existing_owner_edits(self):
        first=self.i.run(2);self.assertEqual(len(first['added']),2)
        rid=first['added'][0];self.db.execute("UPDATE records SET revision=2,deleted_at='owner removed',content_json=json_set(content_json,'$.notes',json('[\"Keep\"]')) WHERE id=?",(rid,));self.db.commit()
        before=dict(self.db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone());again=self.i.run(1)
        self.assertIn(rid,again['replayed']);self.assertEqual(dict(self.db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()),before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM public_records').fetchone()[0],3)
        self.assertEqual(self.db.execute('SELECT count(*) FROM public_browse_index').fetchone()[0],3)
    def test_lost_response_reads_receipt_without_duplicate_import(self):
        raw=self.t.statement;lost=False
        def fail(sql,args=()):
            nonlocal lost
            result=raw(sql,args)
            if 'INSERT INTO derived_import_payloads' in sql and not lost:lost=True;raise ConnectionError('lost after commit')
            return result
        self.t.statement=fail;self.assertEqual(len(self.i.run(1)['added']),1);self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],1)
        self.assertIn(self.plan['records'][0]['id'],self.i.run(1)['replayed'])
    def test_failed_payload_retains_budget_and_rolls_back_all_listing_tables(self):
        raw=self.t.statement
        def invalid(sql,args=()):
            if 'INSERT INTO derived_import_payloads' in sql:
                args=list(args);body=json.loads(args[5]);body['records'][0][3]='{"id":"invalid"}';args[5]=json.dumps(body)
            return raw(sql,args)
        self.t.statement=invalid
        with self.assertRaises(RuntimeError):self.i.run(1)
        for table in h.TABLES:self.assertEqual(self.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        self.assertGreater(self.db.execute('SELECT sum(reserved) FROM derived_import_days').fetchone()[0],0)
        self.t.statement=raw;self.assertEqual(len(self.i.run(1)['added']),1)
    def test_existing_without_receipt_is_preserved_and_budgets_pause(self):
        self.i.run(1);rid=self.plan['records'][0]['id'];self.db.execute('DELETE FROM derived_import_receipts WHERE record_id=?',(rid,));self.db.commit();self.assertIn(rid,self.i.run(1)['preserved'])
        tiny=h.Importer(self.t,self.plan,100);result=tiny.run(1,day='2026-11-10');self.assertTrue(result['paused'])
    def test_index_excludes_archived_owned_notes_and_keeps_pending_search(self):
        r=next(r for r in self.plan['records'] if r['id']=='p1566-l003');plan={**self.plan,'records':[r]};self.assertEqual(h.Importer(self.t,plan).run(1)['added'],['p1566-l003'])
        index=json.loads(self.db.execute('SELECT index_json FROM public_browse_index').fetchone()[0]);text=' '.join(index['items']);self.assertIn('Blue Border Griffey',text);self.assertNotIn('Red Border Griffey',text);self.assertNotIn('User-confirmed',json.dumps(index));self.assertEqual(index['notes'],['Red Border Griffey already owned'])
        self.assertFalse(self.db.execute('PRAGMA foreign_key_check').fetchall())

if __name__=='__main__':unittest.main()
