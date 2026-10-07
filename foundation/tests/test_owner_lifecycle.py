import json
import tempfile
from pathlib import Path
import unittest

from foundation.storage import (apply_schema, change_item, connect, private_export, records_csv, items_csv,
                                public_export, restore, soft_delete, restore_record)
from foundation.owner_reference import (create_record, get_record, add_cards, edit_record,
                                       find_item, recent_changes, add_group, delete_or_restore_item)


class OwnerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(); apply_schema(self.db)

    def tearDown(self):
        self.db.close()

    def revision(self, rid):
        return self.db.execute('SELECT revision FROM records WHERE id=?', (rid,)).fetchone()[0]

    def test_2027_topps_full_lifecycle_no_historical_provenance(self):
        rid = create_record(self.db, {'year': '2027', 'brand': 'Topps', 'set_name': '2027 Topps',
                                     'category': 'baseball_cards', 'notes': ['New owner-created set']},
                            wanted=['12', '18', '47'], owned=['9', '24'], actor='owner')
        result = get_record(self.db, rid)
        self.assertEqual(result['year'], '2027')
        self.assertEqual(result['creation_origin'], 'owner')
        self.assertEqual(len(result['groups']), 2)
        self.assertEqual(sum(len(g['entries']) for g in result['groups']), 5)
        add_cards(self.db, rid, ['92', '99'], expected_revision=self.revision(rid), actor='owner')
        pending = find_item(self.db, rid, '12')[0]['id']
        received = find_item(self.db, rid, '18')[0]['id']
        change_item(self.db, pending, 'pending', expected_revision=self.revision(rid), actor='owner')
        self.assertEqual(find_item(self.db, rid, '12')[0]['state'], 'pending')
        change_item(self.db, received, 'owned', expected_revision=self.revision(rid), actor='owner')
        change_item(self.db, pending, 'wanted', expected_revision=self.revision(rid), actor='owner')
        edit_record(self.db, rid, {'notes': ['Updated notes'], 'year': '2027-28', 'brand': 'Topps',
                                 'set_name': '2027 Topps — updated', 'category': 'baseball_cards'},
                    expected_revision=self.revision(rid), actor='owner')
        edit_record(self.db, rid, {'uncertainty': ['Owner is unsure about checklist']}, list_type='uncertain',
                    expected_revision=self.revision(rid), actor='owner')
        self.assertEqual(get_record(self.db, rid)['list_type'], 'uncertain')
        edit_record(self.db, rid, {'uncertainty': []}, list_type='want_list', expected_revision=self.revision(rid), actor='owner')
        wrong = find_item(self.db, rid, '99')[0]['id']
        delete_or_restore_item(self.db, wrong, expected_revision=self.revision(rid), actor='owner')
        self.assertEqual(find_item(self.db, rid, '99'), [])
        delete_or_restore_item(self.db, wrong, restore=True, expected_revision=self.revision(rid), actor='owner')
        self.assertEqual(find_item(self.db, rid, '99')[0]['state'], 'wanted')
        with self.assertRaisesRegex(ValueError, 'Resolve wanted'):
            edit_record(self.db, rid, {}, list_type='complete', expected_revision=self.revision(rid), actor='owner')
        for value in ('12', '47', '92', '99'):
            change_item(self.db, find_item(self.db, rid, value)[0]['id'], 'owned', expected_revision=self.revision(rid), actor='owner')
        edit_record(self.db, rid, {}, list_type='complete', expected_revision=self.revision(rid), actor='owner')
        self.assertEqual(get_record(self.db, rid)['list_type'], 'complete')
        edit_record(self.db, rid, {}, list_type='want_list', expected_revision=self.revision(rid), actor='owner')
        before = get_record(self.db, rid)
        soft_delete(self.db, rid, expected_revision=self.revision(rid), actor='owner')
        self.assertIsNone(get_record(self.db, rid))
        restore_record(self.db, rid, expected_revision=self.revision(rid), actor='owner')
        result = get_record(self.db, rid)
        self.assertEqual(result['notes'], ['Updated notes'])
        self.assertEqual(result['groups'], before['groups'])
        self.assertIsNone(self.db.execute('SELECT import_id FROM records WHERE id=?', (rid,)).fetchone()[0])
        self.assertEqual(self.db.execute('SELECT count(*) FROM provenance').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM import_batches').fetchone()[0], 0)
        for field in ('source_refs', 'source_wording', 'normalized_wording', 'corrections'):
            self.assertNotIn(field, result)
        actions = [r['action'] for r in reversed(recent_changes(self.db, rid, limit=100))]
        self.assertEqual(actions, ['create_record', 'add_cards', 'item_state', 'item_state', 'item_state',
                                  'edit_record', 'edit_record', 'edit_record', 'soft_delete_item', 'restore_item',
                                  *['item_state'] * 4, 'edit_record', 'edit_record', 'soft_delete', 'restore_record'])
        exported = private_export(self.db)
        self.assertIn('2027 Topps — updated', records_csv(self.db))
        self.assertIn('owned', items_csv(self.db))
        fresh = connect(); apply_schema(fresh)
        restore(fresh, json.loads(json.dumps(exported)))
        self.assertEqual(get_record(fresh, rid), result)
        self.assertEqual(private_export(fresh), exported)
        self.assertEqual(len(public_export(fresh)['records']), 1)
        self.assertEqual(len(recent_changes(fresh, rid, limit=100)), 18)
        fresh.close()

    def test_named_oddballs_prefixes_ranges_and_sublists(self):
        rid = create_record(self.db, {'year': '2027-28', 'brand': 'Example', 'set_name': 'Future postcards',
                                     'category': 'postcards', 'prefixes': ['PC-'], 'notes': ['Owner notes']},
                            wanted_names=['Milwaukee postcard'], owned_names=['Chicago postcard'], actor='owner')
        group = add_group(self.db, rid, 'Oversized postcards', list_type='want_list', expected_revision=1, actor='owner')
        add_cards(self.db, rid, ['PC-001'], group_id=group, expected_revision=2, actor='owner')
        item = find_item(self.db, rid, 'Milwaukee postcard')[0]
        change_item(self.db, item['id'], 'pending', expected_revision=3, actor='owner')
        record = get_record(self.db, rid)
        self.assertEqual(record['category'], 'postcards')
        self.assertEqual(record['prefixes'], ['PC-'])
        self.assertEqual(record['year'], '2027-28')
        self.assertEqual(len(record['groups']), 3)

    def test_duplicate_bad_actor_and_conflicting_revision_roll_back(self):
        rid = create_record(self.db, {'set_name': '2027 Topps', 'category': 'baseball_cards'}, wanted=['47'], actor='owner')
        original = private_export(self.db)
        for values, revision, actor, error in [(['47'], 1, 'owner', ValueError), (['48'], 0, 'owner', ValueError), (['48'], 1, 'visitor', PermissionError)]:
            with self.assertRaises(error):
                add_cards(self.db, rid, values, expected_revision=revision, actor=actor)
            self.assertEqual(private_export(self.db), original)
        with self.assertRaises(ValueError):
            create_record(self.db, {'set_name': 'fake', 'source_refs': [{'paragraph': 1}]}, actor='owner')

    def test_complete_cannot_hide_wanted_pending_or_reactivated_items(self):
        rid = create_record(self.db, {'set_name': 'Complete future set'}, owned=['47'], list_type='complete', actor='owner')
        iid = find_item(self.db, rid, '47')[0]['id']
        with self.assertRaises(ValueError):
            change_item(self.db, iid, 'wanted', expected_revision=1, actor='owner')
        with self.assertRaises(ValueError):
            add_cards(self.db, rid, ['48'], expected_revision=1, actor='owner')
        self.assertEqual(get_record(self.db, rid)['revision'], 1)

    def test_owner_created_set_persists_after_closing_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'disposable.sqlite'
            db = connect(path); apply_schema(db)
            rid = create_record(db, {'year': '2027', 'brand': 'Topps', 'set_name': '2027 Topps', 'category': 'baseball_cards'},
                                wanted=['47'], owned=['12'], actor='owner')
            saved = get_record(db, rid)
            db.close()
            reopened = connect(path)
            self.assertEqual(get_record(reopened, rid), saved)
            self.assertEqual(reopened.execute('SELECT count(*) FROM provenance').fetchone()[0], 0)
            reopened.close()
