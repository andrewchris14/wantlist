"""Reproducible LOCAL query/size review. No Cloudflare calls or credentials.

Rows returned and logical writes are measurable in SQLite; neither is D1 billing
metadata. VM instructions are a bounded-work diagnostic, NOT a row-read count.
"""
import argparse
import json
import sqlite3
from pathlib import Path

from .owner_reference import (add_cards, create_record, delete_or_restore_item,
                              edit_record, find_item, get_record, recent_changes,
                              record_summaries)
from .storage import (apply_schema, change_item, initialize, load_baseline,
                      public_export, restore_record, soft_delete)


class AuditedCursor:
    def __init__(self, cursor, db):
        self.cursor, self.db = cursor, db

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is not None and self.db.measuring:
            self.db.returned += 1
        return row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if self.db.measuring:
            self.db.returned += len(rows)
        return rows

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class AuditedConnection(sqlite3.Connection):
    measuring = False

    def execute(self, sql, parameters=()):
        cursor = super().execute(sql, parameters)
        if self.measuring:
            self.statements.append((sql, parameters))
            return AuditedCursor(cursor, self)
        return cursor


def measure(db, operation):
    db.statements, db.returned, db.vm_steps = [], 0, 0
    def progress():
        db.vm_steps += 1
        return 0
    before = db.total_changes
    db.measuring = True
    db.set_progress_handler(progress, 1)
    try:
        result = operation()
    finally:
        db.set_progress_handler(None, 0)
        db.measuring = False
    plans = []
    for sql, params in db.statements:
        detail = [r[3] for r in db.execute('EXPLAIN QUERY PLAN ' + sql, params)]
        plans.append({'sql': sql, 'plan': detail})
    return result, {'sql_statements': len(plans), 'rows_returned': db.returned,
                    'logical_rows_written': db.total_changes - before,
                    'sqlite_vm_instructions': db.vm_steps, 'queries': plans}


def collect(path):
    path = Path(path)
    if path.exists():
        raise ValueError('Use a NEW disposable database; this review never overwrites one.')
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, factory=AuditedConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    apply_schema(db); initialize(db, load_baseline())
    baseline_bytes = path.stat().st_size
    sizes = {'baseline_with_review_indexes_bytes': baseline_bytes,
             'page_size': db.execute('PRAGMA page_size').fetchone()[0]}
    metrics = {}
    def run(name, fn):
        result, metric = measure(db, fn)
        metrics[name] = metric
        return result
    rid = create_record(db, {'year': '2027', 'brand': 'Topps', 'set_name': '2027 Topps', 'category': 'baseball_cards'},
                        wanted=['12', '18', '47'], owned=['9', '24'], actor='owner')
    revision = lambda: db.execute('SELECT revision FROM records WHERE id=?', (rid,)).fetchone()[0]
    iid = find_item(db, rid, '47')[0]['id']
    # Revision/version is sent by the already-open form, not separately fetched
    # from D1 by the endpoint. Resolve fixture versions before measurement.
    run('owner_catalog_initial_load', lambda: record_summaries(db))
    catalog = record_summaries(db)
    run('search_catalog_in_memory', lambda: [r for r in catalog if '2027 topps' in (r['set_name'] or '').lower()])
    run('open_future_set', lambda: get_record(db, rid))
    run('find_card_in_known_set', lambda: find_item(db, rid, '47'))
    largest = db.execute('SELECT g.record_id,count(*) AS n FROM record_groups g JOIN items i ON i.group_id=g.id GROUP BY g.record_id ORDER BY n DESC LIMIT 1').fetchone()
    run('open_largest_historical_set', lambda: get_record(db, largest['record_id']))
    sizes['largest_historical_record_id'] = largest['record_id']
    sizes['largest_historical_record_item_count'] = largest['n']
    for name, state in [('mark_received', 'owned'), ('return_owned_to_wanted', 'wanted'),
                        ('mark_pending', 'pending'), ('pending_back_to_wanted', 'wanted')]:
        rev = revision()
        run(name, lambda state=state, rev=rev: change_item(db, iid, state, expected_revision=rev, actor='owner'))
    for count in (2, 20):
        rev = revision()
        run(f'add_{count}_wanted', lambda count=count, rev=rev: add_cards(db, rid, [f'NEW{count}-{n}' for n in range(count)], expected_revision=rev, actor='owner'))
    rev = revision()
    run('edit_notes', lambda: edit_record(db, rid, {'notes': ['Updated owner notes']}, expected_revision=rev, actor='owner'))
    run('create_set_20_wanted', lambda: create_record(db, {'year': '2027', 'brand': 'Example', 'set_name': 'Future test set', 'category': 'baseball_cards'}, wanted=[str(n) for n in range(1, 21)], actor='owner'))
    rev = revision()
    run('delete_item', lambda: delete_or_restore_item(db, iid, expected_revision=rev, actor='owner'))
    rev = revision()
    run('restore_item', lambda: delete_or_restore_item(db, iid, restore=True, expected_revision=rev, actor='owner'))
    rev = revision()
    run('delete_record', lambda: soft_delete(db, rid, expected_revision=rev, actor='owner'))
    rev = revision()
    run('restore_record', lambda: restore_record(db, rid, expected_revision=rev, actor='owner'))
    # Populate 1,000 representative item-history events. This is synthetic size
    # growth, not an assertion about the owner's edit frequency.
    before_history = path.stat().st_size
    for n in range(1000):
        change_item(db, iid, 'pending' if n % 2 == 0 else 'wanted', expected_revision=revision(), actor='owner')
    sizes['history_1000_growth_bytes'] = path.stat().st_size - before_history
    run('recent_changes_global_20', lambda: recent_changes(db))
    run('recent_changes_record_20', lambda: recent_changes(db, rid))
    # SQL shapes mirror auth.js. Credential verification CPU is NOT measured.
    db.execute("INSERT INTO owners VALUES ('owner','{\"test_only\":true}',1)"); db.commit()
    def login():
        with db:
            for bucket in ('owner-global', 'ip:test-only'):
                db.execute('INSERT INTO login_limits VALUES (?,0,1) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1 RETURNING attempts', (bucket,)).fetchall()
            owner = db.execute("SELECT * FROM owners WHERE id='owner'").fetchone()
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,NULL)', ('a' * 64, owner['id'], owner['auth_version'], 1, 1800000000, 1807776000, 1800000000))
    run('login_sql_only', login)
    session_sql = 'SELECT s.*,o.auth_version AS current_version FROM sessions s JOIN owners o ON o.id=s.owner_id WHERE token_hash=?'
    run('validate_session', lambda: db.execute(session_sql, ('a' * 64,)).fetchone())
    def daily_seen():
        row = db.execute(session_sql, ('a' * 64,)).fetchone()
        with db:
            db.execute('UPDATE sessions SET last_seen_at=? WHERE token_hash=?', (1800086400, row['token_hash']))
    run('validate_session_daily_touch', daily_seen)
    snapshot = run('full_public_snapshot_generation', lambda: public_export(db))
    sizes['public_snapshot_json_bytes'] = len(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode())
    before_future = path.stat().st_size
    for n in range(100):
        create_record(db, {'year': '2027', 'brand': 'Example', 'set_name': f'Future growth test {n}', 'category': 'baseball_cards'},
                      wanted=[str(v) for v in range(1, 21)], actor='owner')
    sizes['future_100_sets_20_cards_growth_bytes'] = path.stat().st_size - before_future
    db.commit()
    sizes['final_file_bytes'] = path.stat().st_size
    sizes['baseline_decimal_500mb_headroom_bytes'] = 500_000_000 - baseline_bytes
    sizes['final_decimal_500mb_headroom_bytes'] = 500_000_000 - sizes['final_file_bytes']
    before_pending = path.stat().st_size
    future_items = db.execute("SELECT i.id,g.record_id,r.revision FROM items i JOIN record_groups g ON g.id=i.group_id JOIN records r ON r.id=g.record_id WHERE g.record_id != ? AND r.import_id IS NULL AND i.state='wanted' LIMIT 50", (rid,)).fetchall()
    for item in future_items:
        rev = db.execute('SELECT revision FROM records WHERE id=?', (item['record_id'],)).fetchone()[0]
        change_item(db, item['id'], 'pending', expected_revision=rev, actor='owner')
    sizes['pending_50_with_history_growth_bytes'] = path.stat().st_size - before_pending
    sizes['final_file_bytes'] = path.stat().st_size
    sizes['final_decimal_500mb_headroom_bytes'] = 500_000_000 - sizes['final_file_bytes']
    sizes['final_pending_count'] = db.execute("SELECT count(*) FROM items WHERE state='pending'").fetchone()[0]
    # Index footprint from SQLite dbstat, if available. These are file pages,
    # not Cloudflare allocated/billed storage sizes.
    try:
        sizes['object_page_bytes'] = {r[0]: r[1] for r in db.execute('SELECT name,sum(pgsize) FROM dbstat GROUP BY name')}
    except sqlite3.OperationalError:
        sizes['object_page_bytes'] = None
    db.close()
    return {'sqlite_version': sqlite3.sqlite_version, 'planning_limits': {'rows_read_daily': 5_000_000, 'rows_written_daily': 100_000, 'database_bytes_conservative': 500_000_000, 'total_storage_bytes': 5_000_000_000, 'time_travel_days': 7},
            'measurement_caveat': 'SQLite rows returned/logical writes/VM instructions are not measured D1 rows_read/rows_written. No staging resource exists.',
            'sizes': sizes, 'actions': metrics}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, help='NEW disposable local .sqlite path')
    args = parser.parse_args()
    if not args.db.endswith('.sqlite') or '://' in args.db:
        parser.error('Local .sqlite file required')
    print(json.dumps(collect(args.db), indent=2))
