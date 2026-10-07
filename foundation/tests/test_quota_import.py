"""Identical resumable SQL engine with virtual-day local SQLite tests."""
import json
import unittest
from pathlib import Path
from foundation import storage
from foundation.staging.quota_import import Importer,LocalTransport,plan,render,payload_schema
ROOT=Path(__file__).resolve().parents[2]

class QuotaImportTests(unittest.TestCase):
 def setUp(self):
  self.db=storage.connect();storage.apply_schema(self.db)
  self.db.executescript((ROOT/'foundation/staging/schema.sql').read_text())
  self.db.executescript((ROOT/'foundation/staging/import_budget.sql').read_text())
  self.db.executescript(payload_schema())
  self.baseline=storage.load_baseline()
  # Many groups/items cross chunk boundaries without importing the full baseline.
  from foundation.staging.import_baseline import selection
  self.selected=selection(self.baseline);self.transport=LocalTransport(self.db)
 def tearDown(self):self.db.close()
 def test_multiple_days_pause_resume_exact_fidelity_and_idempotency(self):
  chunks=plan(self.baseline,self.selected);budget=max(c['bound'] for c in chunks)
  importer=Importer(self.transport,self.baseline,self.selected,budget)
  reports=[]
  for day in range(10):
   self.transport.day=f'2026-10-{7+day:02d}';r=importer.run();reports.append(r)
   if not r['paused']:break
  self.assertTrue(any(r['paused'] for r in reports));self.assertTrue(r['reconciliation']['passed'])
  self.assertEqual(r['imported_records'],len(self.selected))
  self.assertTrue(all(d['reserved']<=d['budget'] for d in r['daily_reservations']))
  before=self.db.total_changes;again=importer.run();self.assertEqual(again['completed_now'],0);self.assertEqual(self.db.total_changes,before)
 def test_lost_response_retains_reservation_and_skips_committed_chunk(self):
  importer=Importer(self.transport,self.baseline,self.selected);original=self.transport.batch;failed=False
  def lose(statements):
   nonlocal failed
   r=original(statements)
   if not failed and any('INSERT INTO import_chunk_payloads' in s['sql'] for s in statements):failed=True;raise ConnectionError('response lost')
   return r
  self.transport.batch=lose
  with self.assertRaisesRegex(RuntimeError,'reservation retained'):importer.run()
  self.transport.batch=original;r=importer.run();self.assertGreater(r['skipped'],0);self.assertTrue(r['reconciliation']['passed'])
 def test_changed_baseline_or_live_edits_refuse_initialization(self):
  importer=Importer(self.transport,self.baseline,self.selected);importer.run()
  id=self.selected[0]['id'];self.db.execute('UPDATE records SET revision=2 WHERE id=?',(id,));self.db.commit()
  with self.assertRaisesRegex(ValueError,'live edits'):importer.run()
 def test_atomic_chunk_failure_leaves_no_partial_content(self):
  original=self.transport.batch;failed=False
  def invalid(statements):
   nonlocal failed
   if not failed and any('INSERT INTO import_chunk_payloads' in s['sql'] for s in statements):
    failed=True;statements=[*statements,{'sql':'INSERT INTO auth_control VALUES(2,0)','params':[]}]
   return original(statements)
  self.transport.batch=invalid
  with self.assertRaises(RuntimeError):Importer(self.transport,self.baseline,self.selected).run()
  self.assertEqual(self.db.execute('SELECT count(*) FROM staging_import_chunks').fetchone()[0],0)
  self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],0)
  self.assertGreater(self.db.execute('SELECT sum(reserved) FROM import_write_days').fetchone()[0],0)
 def test_quote_roundtrip_and_hard_budget_ceiling(self):
  statement={'sql':'SELECT ? value','params':["Have O'Brien?; DROP TABLE records; --"]}
  self.assertEqual(self.db.execute(render(statement)).fetchone()[0],statement['params'][0])
  with self.assertRaises(ValueError):Importer(self.transport,self.baseline,self.selected,100001)
  r=Importer(self.transport,self.baseline,self.selected,100).run();self.assertTrue(r['paused']);self.assertLess(r['completed_chunks'],r['chunks_total']);self.assertLessEqual(sum(d['reserved'] for d in r['daily_reservations']),100)
