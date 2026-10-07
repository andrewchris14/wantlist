import sqlite3
import unittest

from foundation.review_usage import AuditedConnection, measure
from foundation.storage import apply_schema, connect, initialize, load_baseline, public_export, change_item
from foundation.owner_reference import (create_record, add_cards, get_record, find_item, edit_record,
                                       recent_changes, record_summaries, delete_or_restore_item)


class QueryPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = connect(); apply_schema(cls.template)
        initialize(cls.template, load_baseline())

    @classmethod
    def tearDownClass(cls):
        cls.template.close()

    def setUp(self):
        self.db = sqlite3.connect(':memory:', factory=AuditedConnection)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.template.backup(self.db)
        self.rid = create_record(self.db, {'year': '2027', 'set_name': '2027 Topps', 'category': 'baseball_cards'}, wanted=['47'], actor='owner')
        self.iid = find_item(self.db, self.rid, '47')[0]['id']

    def tearDown(self):
        self.db.close()

    def test_routine_set_operations_never_scan_global_items(self):
        operations = [lambda: get_record(self.db, self.rid), lambda: find_item(self.db, self.rid, '47'),
                      lambda: change_item(self.db, self.iid, 'pending', expected_revision=1, actor='owner'),
                      lambda: change_item(self.db, self.iid, 'wanted', expected_revision=2, actor='owner'),
                      lambda: add_cards(self.db, self.rid, ['48', '49'], expected_revision=3, actor='owner'),
                      lambda: edit_record(self.db, self.rid, {'notes': ['changed']}, expected_revision=4, actor='owner'),
                      lambda: delete_or_restore_item(self.db, self.iid, expected_revision=5, actor='owner'),
                      lambda: delete_or_restore_item(self.db, self.iid, restore=True, expected_revision=6, actor='owner')]
        for operation in operations:
            _, metrics = measure(self.db, operation)
            details = [p for q in metrics['queries'] for p in q['plan']]
            self.assertFalse(any('SCAN i' in p or 'SCAN items' in p or 'SCAN g' in p or 'SCAN record_groups' in p for p in details), details)
            self.assertLess(metrics['sqlite_vm_instructions'], 2000)

    def test_recent_changes_is_indexed_and_bounded_with_1000_rows(self):
        for n in range(1000):
            self.db.execute('INSERT INTO change_history VALUES (?,?,NULL,?,?,?,?,?)',
                            (str(n), self.rid, 'owner', 'test_only', '{}', '{}', f'2027-01-01T00:00:{n:04d}Z'))
        self.db.commit()
        for rid, index in ((None, 'history_recent'), (self.rid, 'history_record_recent')):
            result, metrics = measure(self.db, lambda: recent_changes(self.db, rid))
            self.assertEqual(len(result), 20)
            self.assertTrue(any(index in p for q in metrics['queries'] for p in q['plan']))
            self.assertFalse(any('TEMP B-TREE' in p for q in metrics['queries'] for p in q['plan']))
            self.assertLess(metrics['sqlite_vm_instructions'], 1000)

    def test_catalog_filtering_after_load_executes_no_sql(self):
        catalog = record_summaries(self.db)
        matches, metrics = measure(self.db, lambda: [r for r in catalog if '2027' in (r['year'] or '')])
        self.assertTrue(matches)
        self.assertEqual(metrics['sql_statements'], 0)

    def test_full_snapshot_reads_each_table_once(self):
        snapshot, metrics = measure(self.db, lambda: public_export(self.db))
        self.assertEqual(metrics['sql_statements'], 3)
        expected = sum(self.db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('records', 'record_groups', 'items'))
        self.assertEqual(metrics['rows_returned'], expected)
        self.assertEqual(len(snapshot['records']), 3393)

    def test_add_twenty_batches_round_trips_and_bindings(self):
        created, metrics = measure(self.db, lambda: add_cards(self.db, self.rid, [str(n) for n in range(100, 120)], expected_revision=1, actor='owner'))
        self.assertEqual(len(created), 20)
        self.assertLessEqual(metrics['sql_statements'], 10)
        self.assertLessEqual(max(q['sql'].count('?') for q in metrics['queries']), 60)
