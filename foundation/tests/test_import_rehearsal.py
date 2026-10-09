import copy
import unittest
from foundation.staging import import_rehearsal as rehearsal

class RehearsalSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view=rehearsal.load_view()

    def setUp(self):
        self.db=rehearsal.fresh()
        rehearsal.prepare(self.db,self.view)

    def tearDown(self): self.db.close()

    def test_failure_rolls_back_listing_and_retry_is_idempotent(self):
        with self.assertRaises(RuntimeError): rehearsal.import_batch(self.db,self.view,0,2,fail_after=4)
        self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],0)
        first=rehearsal.import_batch(self.db,self.view,0,2)
        second=rehearsal.import_batch(self.db,self.view,0,2)
        self.assertEqual(len(first['added']),2)
        self.assertEqual(len(second['preserved']),2)
        self.assertTrue(rehearsal.reconcile(self.db,{'records':self.view['records'][:2]})['passed'])

    def test_existing_edits_pending_removed_entries_and_deleted_records_survive(self):
        rehearsal.import_batch(self.db,self.view,0,2)
        rid=self.view['records'][0]['id']
        self.db.execute("UPDATE records SET revision=8,content_json=json_set(content_json,'$.notes',json('[\"Owner note\"]'),'$.entry_order','original'),deleted_at='owner removal' WHERE id=?",(rid,))
        self.db.execute("UPDATE items SET deleted_at='confirmed removal' WHERE group_id LIKE ?",(rid+':%',))
        self.db.commit()
        before=[tuple(row) for row in self.db.execute('SELECT * FROM records')]
        before_items=[tuple(row) for row in self.db.execute('SELECT * FROM items')]
        rehearsal.import_batch(self.db,self.view,0,3)
        self.assertEqual(before,[tuple(row) for row in self.db.execute('SELECT * FROM records LIMIT 2')])
        for row in before_items:self.assertEqual(tuple(self.db.execute('SELECT * FROM items WHERE id=?',(row[0],)).fetchone()),row)

    def test_receipt_detects_changed_dataset_before_retry(self):
        rehearsal.import_batch(self.db,self.view,0,1)
        changed=copy.deepcopy(self.view);changed['records'][0]['notes'].append('drift')
        with self.assertRaises(ValueError):rehearsal.import_batch(self.db,changed,0,1)

    def test_failure_after_completed_listing_keeps_owner_work_and_resumes(self):
        rehearsal.import_batch(self.db,self.view,0,1)
        rid=self.view['records'][0]['id']
        self.db.execute("UPDATE records SET revision=2,content_json=json_set(content_json,'$.notes',json('[\"Keep owner work\"]')) WHERE id=?",(rid,));self.db.commit()
        before=tuple(self.db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone())
        with self.assertRaises(RuntimeError):rehearsal.import_batch(self.db,self.view,1,2,fail_after=2)
        self.assertEqual(tuple(self.db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()),before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],1)
        rehearsal.import_batch(self.db,self.view,0,3)
        self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],3)
        self.assertEqual(tuple(self.db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()),before)

    def test_derived_groups_keep_literals_and_reviewed_types(self):
        for rid in ['p3022-l006','p1996-l008','display-eau-claire-1','display-milwaukee-8x10-list']:
            record=next(r for r in self.view['records'] if r['id']==rid)
            rows=rehearsal.rows_for(record)
            self.assertEqual(rows['provenance'][0][2],rehearsal.digest(record))
            self.assertEqual(len(rows['items']),sum(len(g.get(k,[])) for g in [record,*record.get('mixed_lists',[]),*record.get('sublists',[])] for k in rehearsal.storage.INVENTORIES))
            if rid=='p1996-l008': self.assertEqual(rows['records'][0][2],'complete')
            if rid=='p3022-l006':self.assertIn('Complete? Have cards 1-96.',[i[4] for i in rows['items']])

if __name__=='__main__':unittest.main()
