"""Owner-run backup core: stdlib only; no credentials, snapshots or DBs on disk.

Remote work is reachable only through explicit owner controls in the launcher.
SQL is generated here; callers cannot supply SQL, resource IDs or arbitrary URLs.
"""
import datetime as dt
import json
import math
import re
import sqlite3
import urllib.error
import urllib.request

DATABASE_ID = '81f241d4-b17d-4cd4-802d-177f982cc5e1'
DATABASE_NAME = 'wantlist-staging'
READ_LIMIT = 5_000_000
WRITE_LIMIT = 100_000
ROW_CAP = 300_000
OBJECT_CAP = 100
TABLE_CAP = 32
READ_RESERVATION = 1_250_000
LAG_RESERVE = 1_000_000
MAX_BYTES = 128 * 1024 * 1024
INTERNAL_TABLES = {'_cf_KV', '_cf_METADATA'}
REQUIRED_TABLES = {'records', 'record_groups', 'items', 'provenance', 'private_details',
                   'change_history', 'public_records', 'mutation_receipts', 'categories',
                   'auth_control', 'sessions', 'login_limits', 'staging_import_state'}
SCHEMA_SQL = 'SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name LIMIT 101'

class Stop(Exception):
    """Messages are safe for the UI: never interpolate SQL, rows or credentials."""

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def ident(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise Stop('Unsupported schema identifier. Stop for review.')
    return '"' + value.replace('"', '""') + '"'

def literal(value):
    return "'" + value.replace("'", "''") + "'"

def count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Stop('Usage counters are missing or invalid. No export permitted.')
    return value

def quota_gate(usage, dashboard_reads, dashboard_writes, email_today, remaining=READ_RESERVATION):
    if email_today:
        raise Stop('A D1-limit notice applies to this UTC quota day. Wait; do not export.')
    reads = max(count(usage.get('rowsRead')), count(dashboard_reads))
    writes = max(count(usage.get('rowsWritten')), count(dashboard_writes))
    if reads + remaining + LAG_RESERVE > READ_LIMIT or writes >= WRITE_LIMIT:
        raise Stop('Insufficient Free quota headroom. No export; wait for a fresh quota day.')
    return {'account_rows_read': reads, 'account_rows_written': writes,
            'read_reservation': remaining, 'lag_reserve': LAG_RESERVE,
            'quota_day_utc': dt.datetime.now(dt.timezone.utc).date().isoformat()}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Stop('Unexpected API redirect. Stopped without forwarding credentials.')

class Cloudflare:
    """Only three fixed read-only routes. Never uses Codex environment credentials."""
    def __init__(self, account, token):
        if not re.fullmatch(r'[a-fA-F0-9]{32}', account or ''):
            raise Stop('Account ID must contain 32 hexadecimal characters.')
        if not isinstance(token, str) or not token or len(token) > 512 or any(c.isspace() for c in token):
            raise Stop('Enter your short-lived read-only API token.')
        self.account, self.token = account, token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, payload=None):
        allowed = {'/graphql', '/accounts/' + self.account + '/d1/database/' + DATABASE_ID,
                   '/accounts/' + self.account + '/d1/database/' + DATABASE_ID + '/query'}
        if path not in allowed:
            raise Stop('Remote route is not permitted.')
        request = urllib.request.Request('https://api.cloudflare.com/client/v4' + path,
            data=None if payload is None else canonical(payload).encode(),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
                     'User-Agent': 'WantListOwnerLocalBackup/1'},
            method='GET' if payload is None else 'POST')
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise Stop('Response exceeds the reviewed memory size limit. Stop for review.')
            data = json.loads(raw)
        except Stop:
            raise
        except urllib.error.HTTPError as error:
            raise Stop('Cloudflare request failed (HTTP %d). No retry or fallback; check read-only permissions and quota.' % error.code) from None
        except Exception:
            raise Stop('Cloudflare response unavailable. Stopped; no credentials or data logged.') from None
        if path == '/graphql':
            if data.get('errors'):
                raise Stop('Account usage analytics unavailable. No export permitted.')
            return data.get('data')
        if data.get('success') is not True:
            raise Stop('Cloudflare rejected the read. Stopped without logging the response.')
        return data.get('result')

    def database(self):
        return self.request('/accounts/' + self.account + '/d1/database/' + DATABASE_ID)

    def usage(self):
        now = dt.datetime.now(dt.timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # No database dimension/filter: sum covers the WHOLE account, not just staging.
        query = ('query($account:String!){viewer{accounts(filter:{accountTag:$account}){'
                 'd1AnalyticsAdaptiveGroups(limit:1,filter:{datetime_geq:' + json.dumps(start.isoformat().replace('+00:00','Z')) +
                 ',datetime_leq:' + json.dumps(now.isoformat().replace('+00:00','Z')) +
                 '}){sum{rowsRead rowsWritten}}}}}')
        data = self.request('/graphql', {'query': query, 'variables': {'account': self.account}})
        try:
            accounts = data['viewer']['accounts']
            if len(accounts) != 1:
                raise ValueError()
            groups = accounts[0]['d1AnalyticsAdaptiveGroups']
            if len(groups) != 1:
                raise ValueError()  # Empty analytics is unknown, not assumed zero.
            usage = groups[0]['sum']
            count(usage['rowsRead']); count(usage['rowsWritten'])
            return usage
        except Exception:
            raise Stop('Complete account usage counters unavailable. No export permitted.') from None

    def query(self, statements):
        # Every statement must be generated by this module, SELECT only. No generic
        # endpoint accepts SQL from the browser or from a backup file.
        if any(not s.startswith('SELECT ') or ';' in s for s in statements):
            raise Stop('Only reviewed single read statements are permitted.')
        return self.request('/accounts/' + self.account + '/d1/database/' + DATABASE_ID + '/query',
                            {'batch': [{'sql': s} for s in statements]})


def application_schema(rows):
    if len(rows) > OBJECT_CAP:
        raise Stop('Schema exceeds the reviewed object limit. Nothing omitted; stop for review.')
    objects = []
    for row in rows:
        name = row['name']
        if name.startswith('sqlite_') or name in INTERNAL_TABLES or row['tbl_name'] in INTERNAL_TABLES:
            continue
        if row['type'] not in ('table', 'index', 'trigger', 'view') or not row.get('sql'):
            raise Stop('Unsupported schema object. Stop for review.')
        if row['type'] == 'table' and re.search(r'CREATE\s+VIRTUAL\s+TABLE', row['sql'], re.I):
            raise Stop('Virtual tables require separate backup review; nothing was skipped.')
        objects.append({k: row[k] for k in ('type','name','tbl_name','sql')})
    tables = [o['name'] for o in objects if o['type'] == 'table']
    if not REQUIRED_TABLES <= set(tables) or len(tables) > TABLE_CAP:
        raise Stop('Staging schema is incomplete or outside reviewed limits. No backup created.')
    return objects, tables, any(row['name'] == 'sqlite_sequence' for row in rows)


def column_sql(table):
    return ('SELECT cid,name,type,\"notnull\",dflt_value,pk,hidden,(SELECT wr FROM pragma_table_list WHERE schema=\'main\' AND name=' + literal(table) + ') without_rowid FROM pragma_table_xinfo(' + literal(table) + ') ORDER BY cid')


def snapshot_sql(objects, columns, sequence=False):
    # One SELECT/UNION statement gives one SQLite read snapshot across EVERY
    # application table and schema object. No cross-table joins or sorting scans.
    # Encode values by SQLite type: distinguish blobs from text and preserve int64.
    predicates = ["name NOT LIKE 'sqlite\\_%' ESCAPE '\\'",
                  'name NOT IN (' + ','.join(literal(s) for s in sorted(INTERNAL_TABLES)) + ')',
                  'tbl_name NOT IN (' + ','.join(literal(s) for s in sorted(INTERNAL_TABLES)) + ')',
                  'sql IS NOT NULL']
    statements = ["SELECT 'schema' kind,name,json_object('type',type,'name',name,'tbl_name',tbl_name,'sql',sql) body FROM sqlite_schema WHERE " + ' AND '.join(predicates)]
    for table, fields in columns.items():
        values = []
        for field in fields:
            c = 't.' + ident(field['name'])
            values += [literal(field['name']), "json_array(typeof(" + c + "),CASE WHEN typeof(" + c + ")='blob' THEN hex(" + c + ') ELSE ' + c + ' END)']
        rowid = 'NULL'
        if not fields[0]['without_rowid']:
            candidates=[n for n in ('rowid','_rowid_','oid') if n not in {f['name'].lower() for f in fields}]
            if not candidates: raise Stop('All implicit rowid aliases are shadowed. Stop for schema review.')
            rowid='t.'+ident(candidates[0])
        statements.append("SELECT 'row'," + literal(table) + ",json_object('rowid',"+rowid+",'values',json_object(" + ','.join(values) + ')) FROM ' + ident(table) + ' t')
    if sequence:
        statements.append("SELECT 'sequence','sqlite_sequence',json_object('name',name,'seq',seq) FROM sqlite_sequence")
    sql = ' UNION ALL '.join(statements) + ' LIMIT ' + str(ROW_CAP + 1)
    if len(sql.encode()) > 90_000:
        raise Stop('Snapshot query exceeds reviewed SQL size; stop for review.')
    return sql


def unpack_snapshot(rows, objects, columns, source, sequence=False):
    if len(rows) >= ROW_CAP + 1:
        raise Stop('Snapshot reached the row cap; no partial backup will be saved.')
    actual_objects, tables, seq = [], {t: [] for t in columns}, []
    for row in rows:
        data = json.loads(row['body'])
        if row['kind'] == 'schema':
            actual_objects.append(data)
        elif row['kind'] == 'sequence' and sequence:
            seq.append(data)
        elif row['kind'] == 'row' and row['name'] in tables:
            tables[row['name']].append(data)
        else:
            raise Stop('Unexpected snapshot row; no backup created.')
    if sorted(actual_objects, key=canonical) != sorted(objects, key=canonical):
        raise Stop('Schema changed during preflight. Stop edits and review before retrying.')
    # Type-tagged JSON preserves int64, BLOBs, NULL and JSON-as-text without the
    # browser parsing plaintext records. Row order is canonical, not source order.
    return {'format': 'wantlist-owner-snapshot-v1', 'source': source,
            'schema_objects': sorted(objects, key=canonical), 'columns': columns,
            'tables': {t: sorted(rs, key=canonical) for t, rs in tables.items()},
            'sqlite_sequence': sorted(seq, key=canonical)}


def backup(client, approvals):
    """Bounded reads only; mocks implement the same three methods in local tests."""
    if not all(approvals.get(k) is True for k in ('reviewed','free','quiet','encrypted_pc')):
        raise Stop('Owner review, Free plan, stopped edits/jobs and encrypted computer must be confirmed.')
    now = dt.datetime.now(dt.timezone.utc)
    if approvals.get('quota_day') != now.date().isoformat():
        raise Stop('Dashboard readings must be for the current UTC quota day.')
    used = 0
    def gate():
        if dt.datetime.now(dt.timezone.utc).date() != now.date():
            raise Stop('Quota day changed. Stop and restart with fresh dashboard readings.')
        usage = client.usage()
        # Conservatively add our measured reads even if already ingested by analytics.
        usage = {**usage, 'rowsRead': count(usage.get('rowsRead')) + used}
        return quota_gate(usage, approvals.get('dashboard_reads'), approvals.get('dashboard_writes'),
                          approvals.get('email_today') is not False, READ_RESERVATION - used)
    quota = gate()  # Before ANY D1 SQL, including metadata discovery.
    database = client.database()
    if database.get('uuid') != DATABASE_ID or database.get('name') != DATABASE_NAME:
        raise Stop('Source database identity mismatch. No SQL read permitted.')
    def query(statements):
        nonlocal used
        results = client.query(statements)
        if not isinstance(results, list) or len(results) != len(statements):
            raise Stop('Incomplete D1 result set; no backup created.')
        for result in results:
            if result.get('success') is not True or not isinstance(result.get('results'), list):
                raise Stop('A snapshot read failed; no backup created.')
            meta = result.get('meta', {})
            if count(meta.get('rows_written')) != 0:
                raise Stop('Unexpected write accounting. Stop for review.')
            used += count(meta.get('rows_read'))
        if used > READ_RESERVATION:
            raise Stop('Read budget exceeded. No further read or retry; stop for review.')
        return [r['results'] for r in results]
    objects, tables, sequence = application_schema(query([SCHEMA_SQL])[0])
    # Internal SQLite names are not application schema; sqlite_sequence values
    # are nevertheless retained when AUTOINCREMENT tables exist.
    columns = dict(zip(tables, query([column_sql(t) for t in tables])))
    if any(not fs or len(fs) > 40 or any(f.get('without_rowid') not in (0,1) or f.get('hidden') not in (0,2,3) for f in fs) for fs in columns.values()):
        raise Stop('Unsupported column layout. No incomplete backup created.')
    gate()
    sql = snapshot_sql(objects, columns, sequence)
    source = {'database_id': DATABASE_ID, 'database_name': DATABASE_NAME}
    first = unpack_snapshot(query([sql])[0], objects, columns, source, sequence)
    gate()
    second = unpack_snapshot(query([sql])[0], objects, columns, source, sequence)
    if canonical(first) != canonical(second):
        raise Stop('Two complete snapshots differ. No backup saved; stop edits before a reviewed retry.')
    report = restore_verify(first)
    if dt.datetime.now(dt.timezone.utc).date() != now.date():
        raise Stop('Quota day changed. Restart only after fresh readings and review.')
    first['created_utc'] = now.isoformat()
    raw = canonical(first).encode()
    if len(raw) > MAX_BYTES:
        raise Stop('Snapshot exceeds the reviewed memory limit. No backup saved.')
    return raw, {**report, 'matching_reads': True, 'remote_rows_read': used,
                 'remote_rows_written': 0, 'quota': quota, 'recovery_verified': False}


def decode_value(value):
    if not isinstance(value, list) or len(value) != 2:
        raise Stop('Unsupported backup value encoding.')
    kind, data = value
    if kind == 'null' and data is None: return None
    if kind == 'text' and isinstance(data, str): return data
    if kind == 'integer' and isinstance(data, int) and not isinstance(data, bool) and -(2**63) <= data < 2**63: return data
    if kind == 'real' and isinstance(data, (int,float)) and not isinstance(data, bool) and math.isfinite(data): return float(data)
    if kind == 'blob' and isinstance(data, str):
        try: return bytes.fromhex(data)
        except ValueError: pass
    raise Stop('Unsupported backup value encoding.')


def restore_verify(snapshot):
    """A fresh :memory: DB, sandboxed before any untrusted schema SQL executes."""
    if not isinstance(snapshot, dict) or snapshot.get('format') != 'wantlist-owner-snapshot-v1':
        raise Stop('Unsupported snapshot format. Use its original recovery procedure.')
    tables, objects, columns = snapshot.get('tables'), snapshot.get('schema_objects'), snapshot.get('columns')
    if not isinstance(tables, dict) or not isinstance(columns, dict) or set(tables) != set(columns) or not REQUIRED_TABLES <= set(tables):
        raise Stop('Backup table coverage is incomplete.')
    if not isinstance(objects, list) or len(objects) > OBJECT_CAP or len(tables) > TABLE_CAP or sum(len(rs) for rs in tables.values()) > ROW_CAP:
        raise Stop('Backup exceeds reviewed restoration limits.')
    if {o['name'] for o in objects if o['type'] == 'table'} != set(tables):
        raise Stop('Backup schema/table coverage mismatch.')
    db = sqlite3.connect(':memory:')
    try:
        db.execute('PRAGMA temp_store=MEMORY')
        db.execute('PRAGMA foreign_keys=OFF')
        db.enable_load_extension(False)
        deny = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_CREATE_VTABLE,
                sqlite3.SQLITE_DROP_VTABLE, sqlite3.SQLITE_PRAGMA}
        def authorizer(action, a, b, database, trigger):
            if (action in deny and not (action == sqlite3.SQLITE_PRAGMA and a in ('table_xinfo','table_list'))) or (action == sqlite3.SQLITE_FUNCTION and b in ('load_extension','readfile','writefile')):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorizer)
        # Triggers are installed AFTER rows, so restoring does not produce extra
        # projections/history or overwrite the backed-up row state.
        for obj in objects:
            if obj['type'] == 'table': db.execute(obj['sql'])
        for table, rows in tables.items():
            fields = columns[table]
            names = [f['name'] for f in fields if f.get('hidden',0) == 0]
            for encoded in rows:
                if set(encoded) != {'rowid','values'}: raise Stop('Unsupported backup row encoding.')
                row=encoded['values']
                if set(row) != {f['name'] for f in fields}:
                    raise Stop('Backup row column coverage mismatch.')
                insert_names=list(names);values=[decode_value(row[n]) for n in names]
                if not fields[0]['without_rowid']:
                    alias=next(n for n in ('rowid','_rowid_','oid') if n not in {f['name'].lower() for f in fields})
                    insert_names.insert(0,alias);values.insert(0,decode_value(['integer',encoded['rowid']]))
                elif encoded['rowid'] is not None: raise Stop('Unexpected rowid in a WITHOUT ROWID table.')
                db.execute('INSERT INTO '+ident(table)+'('+','.join(ident(n) for n in insert_names)+') VALUES('+','.join('?' for _ in insert_names)+')',values)
        if snapshot.get('sqlite_sequence'):
            db.execute('DELETE FROM sqlite_sequence')
            db.executemany('INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)', [(r['name'],r['seq']) for r in snapshot['sqlite_sequence']])
        for obj in objects:
            if obj['type'] != 'table': db.execute(obj['sql'])
        db.commit()
        # Authorizer disabled only for fixed verification PRAGMAs after all
        # supplied SQL has executed; no externally supplied SQL follows.
        db.set_authorizer(None)
        db.execute('PRAGMA foreign_keys=ON')
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchall():
            raise Stop('Restored database failed integrity or foreign-key verification.')
        db.set_authorizer(authorizer)
        actual = [dict(zip(('type','name','tbl_name','sql'), r)) for r in db.execute(SCHEMA_SQL)]
        actual, _, sequence = application_schema(actual)
        restored_columns = {t: [dict(zip(('cid','name','type','notnull','dflt_value','pk','hidden','without_rowid'), r)) for r in db.execute(column_sql(t))] for t in tables}
        if restored_columns != columns:
            raise Stop('Restored column definitions differ.')
        sql = snapshot_sql(actual, restored_columns, sequence)
        rows = [dict(zip(('kind','name','body'), row)) for row in db.execute(sql)]
        rebuilt = unpack_snapshot(rows, objects, columns, snapshot.get('source'), sequence)
        expected = {k: snapshot[k] for k in ('format','source','schema_objects','columns','tables','sqlite_sequence')}
        if canonical(rebuilt) != canonical(expected):
            raise Stop('Restored rows or schema differ from the backup.')
        return {'isolated_restore_verified': True, 'integrity': 'ok', 'foreign_keys': 'ok',
                'table_counts': {t: len(rs) for t, rs in tables.items()},
                'all_rows_and_schema_equal': True, 'plaintext_file_created': False,
                'live_database_changed': False}
    except Stop:
        raise
    except Exception:
        raise Stop('Isolated restoration failed. No live database or plaintext file was changed.') from None
    finally:
        db.close()
