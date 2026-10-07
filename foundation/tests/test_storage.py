import json
import csv
import io
import sqlite3
import unittest

from foundation.storage import (apply_schema, change_item, connect, initialize,
                                items_csv, load_baseline, private_export,
                                public_export, reconcile, reconstruct, restore,
                                soft_delete, sql_export, records_csv, restore_record)


class FoundationStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = load_baseline()
        cls.template = connect()
        apply_schema(cls.template)
        initialize(cls.template, cls.baseline)

    @classmethod
    def tearDownClass(cls):
        cls.template.close()

    def setUp(self):
        self.db = connect()
        self.template.backup(self.db)

    def tearDown(self):
        self.db.close()

    def find_item(self, value='Blue Border Griffey'):
        return self.db.execute('SELECT id FROM items WHERE value=?', (value,)).fetchone()[0]

    def test_full_content_reconciliation(self):
        report = reconcile(self.db, self.baseline)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['imported_record_count'], 3392)
        self.assertEqual(report['provenance_coverage'], 3392)
        self.assertEqual(report['duplicate_ids'], 0)

    def test_round_trip_is_not_provenance_mirror(self):
        self.db.execute("UPDATE items SET value='wrong' WHERE id=?", (self.find_item(),))
        report = reconcile(self.db, self.baseline)
        self.assertFalse(report['passed'])
        self.assertIn('p1566-l003', report['field_differences'])

    def test_item_state_and_group_corruption_detected(self):
        self.db.execute("UPDATE items SET state='owned' WHERE id=?", (self.find_item(),))
        self.assertFalse(reconcile(self.db, self.baseline)['passed'])
        self.db.execute("UPDATE record_groups SET list_type='have_list' WHERE id='p1566-l003:primary:0'")
        self.assertIn('p1566-l003:primary:0', reconcile(self.db, self.baseline)['item_state_errors'])

    def test_extra_groups_are_reported_even_without_extra_values(self):
        self.db.execute("INSERT INTO record_groups VALUES ('unexpected','p1566-l003','primary',1,'want_list','{}','[]')")
        report = reconcile(self.db, self.baseline)
        self.assertFalse(report['passed'])
        self.assertEqual(report['identity_differences']['extra_groups'], ['unexpected'])

    def test_missing_item_is_reported_not_crashed(self):
        self.db.execute('DELETE FROM items WHERE id=?', (self.find_item(),))
        report = reconcile(self.db, self.baseline)
        self.assertFalse(report['passed'])
        self.assertTrue(report['identity_differences']['missing_items'])

    def test_idempotent_initialization(self):
        self.assertEqual(initialize(self.db, self.baseline), 'already_initialized')
        self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0], 3392)

    def test_initialization_refuses_after_live_edit(self):
        change_item(self.db, self.find_item(), 'pending', expected_revision=1, actor='owner')
        with self.assertRaisesRegex(ValueError, 'live edits'):
            initialize(self.db, self.baseline)

    def test_wrong_baseline_refused(self):
        db = connect()
        apply_schema(db)
        changed = dict(self.baseline, schema_version='not-approved')
        with self.assertRaisesRegex(ValueError, 'exact approved'):
            initialize(db, changed)
        self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0], 0)
        db.close()

    def test_duplicate_identity_rejected(self):
        row = tuple(self.db.execute('SELECT * FROM records LIMIT 1').fetchone())
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?)', row)

    def test_constraints_and_foreign_keys(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE records SET list_type='pending' WHERE id='p1566-l003'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE items SET state='pending',pending_at=NULL WHERE id=?", (self.find_item(),))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE items SET group_id='missing' WHERE id=?", (self.find_item(),))

    def test_griffey_mixed_relationships(self):
        rows = self.db.execute("SELECT value,state FROM items WHERE group_id LIKE 'p1566-l003:%' ORDER BY value").fetchall()
        self.assertEqual([tuple(r) for r in rows], [('Blue Border Griffey', 'wanted'), ('Red Border Griffey', 'owned')])

    def test_flagship_categories(self):
        records = {r['id']: r for r in reconstruct(self.db)}
        for rid in ('p0672-l001', 'p0694-l001', 'p0730-l001'):
            self.assertEqual(records[rid]['category'], 'baseball_cards')

    def test_have_complete_uncertain_and_oddballs_preserved(self):
        live = {r['id']: r for r in reconstruct(self.db)}
        for r in self.baseline['records']:
            if r['list_type'] in ('have_list', 'complete', 'uncertain') or r['category'] != 'baseball_cards':
                self.assertEqual(live[r['id']], r)
        # No invented IDs or checklist complements: every literal came from an
        # existing field in an existing primary/mixed/sublist group.
        expected = sum(len(g.get(k, [])) for r in self.baseline['records']
                       for g in [r, *r['mixed_lists'], *r['sublists']]
                       for k in ('card_numbers', 'items', 'card_ranges'))
        self.assertEqual(self.db.execute('SELECT count(*) FROM items').fetchone()[0], expected)

    def test_ranges_and_prose_are_not_guessed(self):
        ranges = self.db.execute("SELECT * FROM items WHERE field_key='card_ranges'").fetchall()
        self.assertTrue(ranges)
        self.assertTrue(all(not r['actionable'] and r['state'] is None for r in ranges))
        literal = self.db.execute('SELECT id FROM items WHERE actionable=0 LIMIT 1').fetchone()[0]
        with self.assertRaisesRegex(ValueError, 'owner review'):
            change_item(self.db, literal, 'owned', expected_revision=1, actor='owner')

    def test_pending_falls_through_received_and_history(self):
        iid = self.find_item()
        for revision, state in enumerate(('pending', 'wanted', 'pending', 'owned'), 1):
            change_item(self.db, iid, state, expected_revision=revision, actor='owner')
        row = self.db.execute('SELECT * FROM items WHERE id=?', (iid,)).fetchone()
        self.assertEqual(row['state'], 'owned')
        self.assertIsNotNone(row['received_at'])
        self.assertIsNone(row['pending_at'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM change_history').fetchone()[0], 4)
        self.assertEqual(self.db.execute("SELECT list_type FROM records WHERE id='p1566-l003'").fetchone()[0], 'want_list')

    def test_revision_conflict_rolls_back(self):
        iid = self.find_item()
        change_item(self.db, iid, 'pending', expected_revision=1, actor='owner')
        before = private_export(self.db)
        with self.assertRaisesRegex(ValueError, 'Revision conflict'):
            change_item(self.db, iid, 'owned', expected_revision=1, actor='owner')
        self.assertEqual(private_export(self.db), before)

    def test_unauthorized_local_changes_rejected(self):
        before = private_export(self.db)
        with self.assertRaises(PermissionError):
            change_item(self.db, self.find_item(), 'pending', expected_revision=1, actor='visitor')
        with self.assertRaises(PermissionError):
            soft_delete(self.db, 'p1566-l003', expected_revision=1, actor='visitor')
        self.assertEqual(private_export(self.db), before)

    def test_soft_delete_history_and_no_hard_delete(self):
        soft_delete(self.db, 'p1566-l003', expected_revision=1, actor='owner')
        self.assertNotIn('p1566-l003', {r['id'] for r in reconstruct(self.db)})
        self.assertIn('p1566-l003', {r['id'] for r in reconstruct(self.db, True)})
        self.assertEqual(self.db.execute('SELECT action FROM change_history').fetchone()[0], 'soft_delete')
        self.assertEqual(self.db.execute('SELECT count(*) FROM provenance').fetchone()[0], 3392)
        restore_record(self.db, 'p1566-l003', expected_revision=2, actor='owner')
        restored = next(r for r in reconstruct(self.db) if r['id'] == 'p1566-l003')
        original = next(r for r in self.baseline['records'] if r['id'] == 'p1566-l003')
        self.assertEqual(restored, original)
        self.assertEqual(self.db.execute('SELECT count(*) FROM change_history').fetchone()[0], 2)

    def test_public_allowlist_and_current_item_states(self):
        iid = self.find_item()
        self.db.execute('INSERT INTO private_details VALUES (?,?)', (iid, '{"sender":"PRIVATE_SENTINEL"}'))
        row = self.db.execute("SELECT content_json FROM records WHERE id='p1566-l003'").fetchone()
        content = json.loads(row[0]); content['private_notes'] = 'PRIVATE_SENTINEL'
        self.db.execute("UPDATE records SET content_json=? WHERE id='p1566-l003'", (json.dumps(content),))
        self.db.commit()
        change_item(self.db, iid, 'owned', expected_revision=1, actor='owner')
        data = public_export(self.db)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(data))
        griffey = next(r for r in data['records'] if r['id'] == 'p1566-l003')
        entry = next(i for g in griffey['groups'] for i in g['entries'] if i['value'] == 'Blue Border Griffey')
        self.assertEqual(entry['state'], 'owned')
        self.assertIn('revision', data); self.assertIn('updated_at', data)

    def test_backup_restore_preserves_live_changes_and_private_details(self):
        iid = self.find_item()
        change_item(self.db, iid, 'pending', expected_revision=1, actor='owner')
        self.db.execute('INSERT INTO private_details VALUES (?,?)', (iid, '{"trade_note":"private"}'))
        self.db.commit()
        exported = private_export(self.db)
        fresh = connect(); apply_schema(fresh)
        restore(fresh, json.loads(json.dumps(exported)))
        self.assertEqual(private_export(fresh), exported)
        self.assertEqual(public_export(fresh), public_export(self.db))
        self.assertEqual(fresh.execute('SELECT count(*) FROM sessions').fetchone()[0], 0)
        with self.assertRaisesRegex(ValueError, 'NEW empty'):
            restore(fresh, exported)
        with self.assertRaisesRegex(ValueError, 'live edits'):
            initialize(fresh, self.baseline)
        fresh.close()

    def test_sql_dump_restore(self):
        fresh = connect()
        fresh.executescript(sql_export(self.db))
        self.assertEqual(fresh.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertTrue(reconcile(fresh, self.baseline)['passed'])
        fresh.close()

    def test_backup_excludes_authentication_secrets(self):
        self.db.execute("INSERT INTO owners VALUES ('owner','{\"test_marker\":\"AUTH_SENTINEL\"}',1)")
        self.db.commit()
        self.assertNotIn('AUTH_SENTINEL', json.dumps(private_export(self.db)))
        self.assertNotIn('AUTH_SENTINEL', sql_export(self.db))

    def test_records_csv_includes_complete_and_uncertain(self):
        rows = list(csv.DictReader(io.StringIO(records_csv(self.db))))
        self.assertEqual(len(rows), 3392)
        self.assertTrue(any(r['list_type'] == 'complete' for r in rows))
        self.assertTrue(any(r['list_type'] == 'uncertain' and r['uncertainty'] for r in rows))

    def test_csv_has_owned_pending_and_formula_protection(self):
        iid = self.find_item()
        change_item(self.db, iid, 'pending', expected_revision=1, actor='owner')
        self.db.execute('UPDATE items SET value=? WHERE id=?', ('=HYPERLINK("bad")', iid))
        exported = items_csv(self.db)
        self.assertIn('pending', exported)
        self.assertIn('owned', exported)
        self.assertIn("'=HYPERLINK", exported)


if __name__ == '__main__':
    unittest.main()
