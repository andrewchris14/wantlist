"""Lossless local SQLite reference for the D1-compatible schema.

No Cloudflare SDK, remote URLs, or production database operations are used here.
"""
import csv
import hashlib
import io
import json
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASELINE_COMMIT = 'd452f58d9006a498db7a8c65827c645b8f817703'
BASELINE_SHA256 = '38a7ee7ad07ede1ae744dbe91b819c1bb78a294c70ca30f933bc66604d44c98a'
ROOT = Path(__file__).resolve().parents[1]
INVENTORIES = ('card_numbers', 'items', 'card_ranges')
PUBLIC_FIELDS = ('id', 'year', 'brand', 'set_name', 'category', 'section',
                 'list_type', 'source_list_type', 'notes', 'prefixes', 'set_size',
                 'uncertainty', 'sublists', 'mixed_lists', 'completed_sets',
                 'card_numbers', 'items', 'card_ranges', 'source_refs')
BACKUP_TABLES = ('foundation_meta', 'import_batches', 'records', 'record_groups',
                 'items', 'provenance', 'private_details', 'change_history')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path=':memory:'):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def apply_schema(db):
    # No destructive reset, DROP, or automatic schema replacement.
    db.executescript((ROOT / 'foundation/migrations/0001_foundation.sql').read_text())
    db.executescript((ROOT / 'foundation/migrations/0002_query_indexes.sql').read_text())


def load_baseline(path=None):
    raw = Path(path or ROOT / 'data/wantlists.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
        raise ValueError('Not the approved baseline: hash mismatch. Do not change the baseline to bypass this guard.')
    return json.loads(raw)


def materialize(record, group, key):
    """Only actionable identities we can determine without parsing prose.

    Named values and ranges are retained as literal rows with a group relationship,
    not guessed into individual cards. Griffey is explicitly human-confirmed.
    """
    mode = group.get('list_type', record['list_type'])
    if mode == 'uncertain':
        mode = group.get('source_list_type', record.get('source_list_type'))
    state = {'want_list': 'wanted', 'have_list': 'owned'}.get(mode)
    if key == 'card_numbers' and state:
        return state, 1, None
    if key == 'items' and '17' in record.get('corrections', []) and state:
        return state, 1, None
    reason = 'Range retained literally; individual boundaries require owner review.' if key == 'card_ranges' else \
        'Literal name/prose retained in its original group; not assumed to identify one actionable item.'
    if key == 'card_numbers':
        reason = 'No unambiguous WANT/HAVE relationship; preserved without an item-state assumption.'
    return None, 0, reason


def initialize(db, baseline):
    existing = db.execute("SELECT value FROM foundation_meta WHERE key='baseline_sha256'").fetchone()
    if existing:
        changed = db.execute('SELECT count(*) FROM change_history').fetchone()[0] or \
            db.execute('SELECT count(*) FROM records WHERE revision != 1 OR deleted_at IS NOT NULL').fetchone()[0]
        if existing[0] != BASELINE_SHA256 or changed:
            raise ValueError('Initialization refused: database differs or contains live edits. Use a NEW disposable database.')
        report = reconcile(db, baseline)
        if not report['passed']:
            raise ValueError('Initialization refused: existing content no longer reconciles.')
        return 'already_initialized'
    if any(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in BACKUP_TABLES):
        raise ValueError('Initialization refused: database is not empty.')
    # Check semantic baseline too: callers cannot mutate a loaded baseline in memory.
    if baseline != load_baseline():
        raise ValueError('Initialization requires the exact approved baseline content.')
    stamp = now()
    with db:
        db.execute('INSERT INTO import_batches VALUES (?,?,?,?,?)',
                   ('baseline', BASELINE_COMMIT, BASELINE_SHA256,
                    dumps({k: v for k, v in baseline.items() if k != 'records'}), stamp))
        for record in baseline['records']:
            content = {k: v for k, v in record.items() if k not in (*INVENTORIES, 'mixed_lists', 'sublists', 'list_type')}
            db.execute('INSERT INTO records VALUES (?,?,?,?,1,?,?,NULL)',
                       (record['id'], 'baseline', record['list_type'], dumps(content), stamp, stamp))
            db.execute('INSERT INTO provenance VALUES (?,?,?,?)',
                       (record['id'], dumps(record), hashlib.sha256(dumps(record).encode()).hexdigest(), dumps(record['source_refs'])))
            sources = [('primary', 0, record)]
            sources += [('mixed', i, g) for i, g in enumerate(record.get('mixed_lists', []))]
            sources += [('sublist', i, g) for i, g in enumerate(record.get('sublists', []))]
            for kind, position, group in sources:
                gid = f"{record['id']}:{kind}:{position}"
                metadata = {} if kind == 'primary' else {k: v for k, v in group.items() if k not in INVENTORIES}
                keys = [key for key in INVENTORIES if key in group]
                db.execute('INSERT INTO record_groups VALUES (?,?,?,?,?,?,?)',
                           (gid, record['id'], kind, position, group.get('list_type', record['list_type']), dumps(metadata), dumps(keys)))
                for key in keys:
                    state, actionable, limitation = materialize(record, group, key)
                    for i, value in enumerate(group[key]):
                        if not isinstance(value, str) or not value:
                            raise ValueError(f'Invalid literal in {gid}; stop instead of silently changing it.')
                        db.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL)',
                                   (f'{gid}:{key}:{i}', gid, key, i, value, state, actionable, limitation))
        db.execute('INSERT INTO foundation_meta VALUES (?,?)', ('baseline_sha256', BASELINE_SHA256))
        db.execute('INSERT INTO foundation_meta VALUES (?,?)', ('schema_version', '1'))
    return 'initialized'


def reconstruct(db, include_deleted=False):
    """Reconstruct from LIVE columns/groups/items, not the provenance mirror."""
    result = []
    records = db.execute('SELECT * FROM records ORDER BY id')
    for row in records:
        if row['deleted_at'] and not include_deleted:
            continue
        record = json.loads(row['content_json'])
        record['list_type'] = row['list_type']
        record['mixed_lists'], record['sublists'] = [], []
        for group in db.execute('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position', (row['id'],)):
            body = json.loads(group['metadata_json'])
            body.update({k: [] for k in json.loads(group['inventory_keys_json'])})
            for item in db.execute('SELECT * FROM items WHERE group_id=? ORDER BY field_key,position', (group['id'],)):
                if include_deleted or not item['deleted_at']:
                    body[item['field_key']].append(item['value'])
            if group['kind'] == 'primary':
                record.update(body)
            else:
                record['mixed_lists' if group['kind'] == 'mixed' else 'sublists'].append(body)
        result.append(record)
    return result


def reconcile(db, baseline):
    expected = {r['id']: r for r in baseline['records']}
    live = reconstruct(db, include_deleted=True)
    actual = {r['id']: r for r in live}
    missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    diffs = {rid: [k for k in expected[rid].keys() | actual[rid].keys() if k not in expected[rid] or k not in actual[rid] or expected[rid][k] != actual[rid][k]]
             for rid in expected.keys() & actual.keys() if expected[rid] != actual[rid]}
    header_row = db.execute('SELECT header_json FROM import_batches WHERE id=?', ('baseline',)).fetchone()
    header = json.loads(header_row[0]) if header_row else None
    header_matches = header == {k: v for k, v in baseline.items() if k != 'records'}
    batch = db.execute('SELECT baseline_commit,dataset_sha256 FROM import_batches WHERE id=?', ('baseline',)).fetchone()
    import_identity_matches = bool(batch and tuple(batch) == (BASELINE_COMMIT, BASELINE_SHA256)) and \
        db.execute('SELECT count(*) FROM import_batches').fetchone()[0] == 1 and \
        db.execute("SELECT count(*) FROM records WHERE import_id IS NULL OR import_id != 'baseline'").fetchone()[0] == 0
    provenance_errors = []
    for rid, record in expected.items():
        row = db.execute('SELECT * FROM provenance WHERE record_id=?', (rid,)).fetchone()
        if not row or json.loads(row['baseline_json']) != record or json.loads(row['source_refs_json']) != record['source_refs'] or \
                row['baseline_sha256'] != hashlib.sha256(dumps(record).encode()).hexdigest():
            provenance_errors.append(rid)
    limitations = [dict(r) for r in db.execute('SELECT r.id,r.content_json,count(*) AS literal_count FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id WHERE actionable=0 GROUP BY r.id ORDER BY r.id')]
    limitations = [{'id': r['id'], 'set_name': json.loads(r['content_json'])['set_name'], 'literal_count': r['literal_count']} for r in limitations]
    known = {}
    for rid in ('p1566-l003', 'p0672-l001', 'p0694-l001', 'p0730-l001'):
        known[rid] = {'set_name': actual.get(rid, {}).get('set_name'), 'matches_baseline': actual.get(rid) == expected[rid]}
    def item_state(value):
        row = db.execute('SELECT state FROM items WHERE value=? AND group_id LIKE ?', (value, 'p1566-l003:%')).fetchone()
        return row[0] if row else None
    known['Griffey_states'] = {'Blue Border Griffey': item_state('Blue Border Griffey'), 'Red Border Griffey': item_state('Red Border Griffey')}
    states_match = known['Griffey_states'] == {'Blue Border Griffey': 'wanted', 'Red Border Griffey': 'owned'}
    categories_match = all(actual.get(rid, {}).get('category') == 'baseball_cards' for rid in ('p0672-l001', 'p0694-l001', 'p0730-l001'))
    duplicate_ids = len(live) - len(actual)
    # Ensure materialized states/limits/group mode match the import contract as well.
    item_errors, expected_groups, expected_items = [], set(), set()
    for rid, record in expected.items():
        groups = [('primary', 0, record)] + [('mixed', i, g) for i, g in enumerate(record['mixed_lists'])] + [('sublist', i, g) for i, g in enumerate(record['sublists'])]
        for kind, pos, group in groups:
            gid = f'{rid}:{kind}:{pos}'
            expected_groups.add(gid)
            row = db.execute('SELECT list_type FROM record_groups WHERE id=?', (gid,)).fetchone()
            if not row or row[0] != group.get('list_type', record['list_type']):
                item_errors.append(gid)
            for key in INVENTORIES:
                state, action, reason = materialize(record, group, key)
                for i, value in enumerate(group.get(key, [])):
                    iid = f'{gid}:{key}:{i}'
                    expected_items.add(iid)
                    row = db.execute('SELECT state,actionable,limitation,deleted_at,pending_at,received_at FROM items WHERE id=?', (iid,)).fetchone()
                    if not row or tuple(row) != (state, action, reason, None, None, None):
                        item_errors.append(f'{gid}:{key}:{i}')
    actual_groups = {r[0] for r in db.execute('SELECT id FROM record_groups')}
    actual_items = {r[0] for r in db.execute('SELECT id FROM items')}
    identity_differences = {'missing_groups': sorted(expected_groups - actual_groups), 'extra_groups': sorted(actual_groups - expected_groups),
                           'missing_items': sorted(expected_items - actual_items), 'extra_items': sorted(actual_items - expected_items)}
    representatives = {}
    for label in ('have_list', 'complete', 'uncertain'):
        record = next(r for r in baseline['records'] if r['list_type'] == label)
        representatives[label] = {'id': record['id'], 'matches_baseline': actual.get(record['id']) == record}
    for category in sorted({r['category'] for r in baseline['records']} - {'baseball_cards'}):
        record = next(r for r in baseline['records'] if r['category'] == category)
        representatives[category] = {'id': record['id'], 'matches_baseline': actual.get(record['id']) == record}
    deleted = db.execute('SELECT count(*) FROM records WHERE deleted_at IS NOT NULL').fetchone()[0]
    return {'passed': not (missing or extra or diffs or provenance_errors or duplicate_ids or item_errors or deleted or any(identity_differences.values())) and header_matches and import_identity_matches and states_match and categories_match,
            'baseline_commit': BASELINE_COMMIT, 'dataset_sha256': BASELINE_SHA256,
            'baseline_record_count': len(expected), 'imported_record_count': len(live),
            'baseline_list_types': dict(Counter(r['list_type'] for r in baseline['records'])),
            'list_types': dict(Counter(r['list_type'] for r in live)),
            'baseline_categories': dict(Counter(r['category'] for r in baseline['records'])),
            'categories': dict(Counter(r['category'] for r in live)),
            'records_with_groups': sum(bool(r['mixed_lists'] or r['sublists']) for r in live),
            'group_count': db.execute('SELECT count(*) FROM record_groups').fetchone()[0],
            'literal_value_rows': db.execute('SELECT count(*) FROM items').fetchone()[0],
            'actionable_items': db.execute('SELECT count(*) FROM items WHERE actionable=1').fetchone()[0],
            'records_not_fully_itemized': limitations,
            'provenance_coverage': len(expected) - len(provenance_errors),
            'header_matches': header_matches, 'import_identity_matches': import_identity_matches,
            'missing': missing, 'extra': extra, 'field_differences': diffs,
            'duplicate_ids': duplicate_ids, 'provenance_errors': provenance_errors,
            'item_state_errors': item_errors, 'identity_differences': identity_differences,
            'reviewed_edge_cases': known, 'representative_statuses_and_categories': representatives}


def change_item(db, item_id, new_state, *, expected_revision, actor):
    """Local reference for an eventual protected API, NOT exposed by the Worker."""
    if actor != 'owner':
        raise PermissionError('Owner authorization required')
    transitions = {'wanted': {'pending', 'owned'}, 'pending': {'wanted', 'owned'}, 'owned': {'wanted'}}
    stamp = now()
    with db:
        row = db.execute('SELECT i.*,g.record_id FROM items i JOIN record_groups g ON g.id=i.group_id WHERE i.id=?', (item_id,)).fetchone()
        if not row or not row['actionable'] or row['deleted_at']:
            raise ValueError('Item requires explicit owner review or is deleted')
        if new_state not in transitions.get(row['state'], set()):
            raise ValueError('Invalid state transition')
        mode = db.execute('SELECT list_type FROM records WHERE id=?', (row['record_id'],)).fetchone()[0]
        if mode == 'complete' and new_state in ('wanted', 'pending'):
            raise ValueError('Unmark Complete before changing an item to wanted/pending')
        changed = db.execute('UPDATE records SET revision=revision+1,updated_at=? WHERE id=? AND revision=? AND deleted_at IS NULL', (stamp, row['record_id'], expected_revision)).rowcount
        if changed != 1:
            raise ValueError('Revision conflict or deleted record')
        db.execute('UPDATE items SET state=?,pending_at=?,received_at=? WHERE id=?',
                   (new_state, stamp if new_state == 'pending' else None, stamp if new_state == 'owned' else None, item_id))
        after = dict(db.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone())
        db.execute('INSERT INTO change_history VALUES (?,?,?,?,?,?,?,?)',
                   (str(uuid.uuid4()), row['record_id'], item_id, actor, 'item_state', dumps(dict(row)), dumps(after), stamp))


def soft_delete(db, record_id, *, expected_revision, actor):
    if actor != 'owner':
        raise PermissionError('Owner authorization required')
    with db:
        before = db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
        if not before:
            raise ValueError('Record not found')
        stamp = now()
        if db.execute('UPDATE records SET deleted_at=?,updated_at=?,revision=revision+1 WHERE id=? AND revision=? AND deleted_at IS NULL', (stamp, stamp, record_id, expected_revision)).rowcount != 1:
            raise ValueError('Revision conflict or already deleted')
        after = dict(db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone())
        db.execute('INSERT INTO change_history VALUES (?,?,?,?,?,?,?,?)',
                   (str(uuid.uuid4()), record_id, None, actor, 'soft_delete', dumps(dict(before)), dumps(after), stamp))


def restore_record(db, record_id, *, expected_revision, actor):
    if actor != 'owner':
        raise PermissionError('Owner authorization required')
    with db:
        before = db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
        if not before:
            raise ValueError('Record not found')
        stamp = now()
        if db.execute('UPDATE records SET deleted_at=NULL,updated_at=?,revision=revision+1 WHERE id=? AND revision=? AND deleted_at IS NOT NULL', (stamp, record_id, expected_revision)).rowcount != 1:
            raise ValueError('Revision conflict or record not deleted')
        after = dict(db.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone())
        db.execute('INSERT INTO change_history VALUES (?,?,?,?,?,?,?,?)',
                   (str(uuid.uuid4()), record_id, None, actor, 'restore_record', dumps(dict(before)), dumps(after), stamp))


def public_export(db):
    """Full allowlist snapshot in THREE intentional bulk reads.

    Offline/publication reference only, not a per-visit/per-edit API. A later
    publisher needs incremental updates and bounded coalesced full rebuilds.
    """
    rows = sorted(db.execute('SELECT * FROM records').fetchall(), key=lambda r: r['id'])
    all_groups = db.execute('SELECT * FROM record_groups').fetchall()
    all_items = db.execute('SELECT id,group_id,position,value,field_key,state,actionable,pending_at,received_at FROM items WHERE deleted_at IS NULL').fetchall()
    groups_by_record, items_by_group = {}, {}
    for group in all_groups:
        groups_by_record.setdefault(group['record_id'], []).append(group)
    for item in all_items:
        items_by_group.setdefault(item['group_id'], []).append(item)
    revision = hashlib.sha256(dumps([(r['id'], r['revision'], r['updated_at']) for r in rows]).encode()).hexdigest()
    records = []
    for row in rows:
        if row['deleted_at']:
            continue
        content = json.loads(row['content_json'])
        content['list_type'] = row['list_type']
        record = {k: content[k] for k in PUBLIC_FIELDS if k in content and k not in (*INVENTORIES, 'mixed_lists', 'sublists')}
        record['groups'] = []
        for group in sorted(groups_by_record.get(row['id'], []), key=lambda g: (g['kind'], g['position'])):
            metadata = json.loads(group['metadata_json'])
            body = {k: metadata[k] for k in ('label', 'description', 'notes', 'source_list_type') if k in metadata}
            body.update({'id': group['id'], 'kind': group['kind'], 'list_type': group['list_type']})
            body['entries'] = [{k: i[k] for k in ('id', 'value', 'field_key', 'state', 'actionable', 'pending_at', 'received_at')}
                               for i in sorted(items_by_group.get(group['id'], []), key=lambda i: (i['field_key'], i['position']))]
            record['groups'].append(body)
        records.append(record)
        # Explicit entry states avoid showing a received item as wanted merely
        # because it originated in a WANT group. No existing UI consumes this.
    return {'export_schema': 'wantlist-public-v1-foundation', 'revision': revision,
            'updated_at': max((r['updated_at'] for r in rows), default=None),
            'snapshot_kind': 'saved_snapshot', 'records': records}


def private_export(db):
    # Authentication verifiers/session hashes excluded deliberately. Recovery
    # provisions a fresh owner and revokes all old sessions.
    return {'export_schema': 'wantlist-private-v1', 'baseline_sha256': BASELINE_SHA256,
            'tables': {t: [dict(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY 1')] for t in BACKUP_TABLES}}


def restore(db, exported):
    if exported.get('export_schema') != 'wantlist-private-v1' or set(exported.get('tables', {})) != set(BACKUP_TABLES):
        raise ValueError('Unsupported backup contract')
    if exported.get('baseline_sha256') != BASELINE_SHA256:
        raise ValueError('Unexpected baseline identity')
    if any(db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in (*BACKUP_TABLES, 'owners', 'sessions', 'login_limits')):
        raise ValueError('Restore only into a NEW empty disposable database')
    with db:
        for table in BACKUP_TABLES:
            columns = [r[1] for r in db.execute(f'PRAGMA table_info({table})')]
            for row in exported['tables'][table]:
                if set(row) != set(columns):
                    raise ValueError(f'Unexpected columns in {table}')
                db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [row[c] for c in columns])
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Backup foreign-key check failed')


def sql_export(db):
    # Exclude authentication material just like the private JSON export. SQLite
    # dumps order tables alphabetically, so FK enforcement is off during restore;
    # the receiving operator MUST run foreign_key_check before accepting it.
    fresh = connect()
    try:
        apply_schema(fresh)
        restore(fresh, private_export(db))
        return 'PRAGMA foreign_keys=OFF;\n' + '\n'.join(fresh.iterdump()) + '\nPRAGMA foreign_keys=ON;\nPRAGMA foreign_key_check;\n'
    finally:
        fresh.close()


def items_csv(db):
    out = io.StringIO()
    fields = ('record_id', 'set_name', 'group_kind', 'list_type', 'value_kind', 'value', 'state', 'actionable')
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    query = '''SELECT r.id AS record_id,r.content_json,g.kind AS group_kind,g.list_type,
                      i.field_key AS value_kind,i.value,i.state,i.actionable
               FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id
               WHERE r.deleted_at IS NULL AND i.deleted_at IS NULL ORDER BY r.id,g.id,i.field_key,i.position'''
    def cell(value):
        # Spreadsheet formula injection protection on PUBLIC exports too.
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        return value
    for row in db.execute(query):
        data = {k: row[k] for k in fields if k != 'set_name'}
        data['set_name'] = json.loads(row['content_json'])['set_name']
        writer.writerow({k: cell(v) for k, v in data.items()})
    return out.getvalue()


def records_csv(db):
    out = io.StringIO()
    fields = ('id', 'year', 'brand', 'set_name', 'category', 'list_type', 'notes', 'uncertainty')
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for record in reconstruct(db):
        row = {k: record.get(k) for k in fields}
        for key in ('notes', 'uncertainty'):
            row[key] = ' | '.join(row[key] or [])
        writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    return out.getvalue()
