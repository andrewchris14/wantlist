"""Explicit disposable-only HTTP review. Never invokes the historical importer.

Run with supported per-command network permission and inherited proxy/TLS trust.
No credentials, cookies or database rows are written into the report.
"""
import collections
import hashlib
import datetime as dt
import json
import statistics
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .cloudflare import api, deploy, endpoint, metrics_groups, query

def response_evidence(origin, path, raw, headers):
    """Safe response fingerprint; never retain body, cookies or request secrets."""
    return {'response_sha256': hashlib.sha256(raw).hexdigest(),
            'response_headers': {key: headers.get(key) for key in ('CF-Ray','Server','Content-Type')},
            'public_index_url': origin + path if path.startswith('/public/index?') else None}

ROOT = Path(__file__).resolve().parents[2]
NAME = 'wantlist-test-3c2-bc5991ba'
STAGING_DB = '81f241d4-b17d-4cd4-802d-177f982cc5e1'
PREFIX = 'synthetic-3c5-'
TARGETS = dict(zip([
    'OBC Wantlist', 'UV Wantlist', 'Eau Claire Players', 'Milwaukee 8x10 List',
    'Brewers Bobblehead Wantlist', 'Football Wantlist', 'Other Stuff',
], [583, 2517, 3, 1, 26, 62, 202]))
REPORT = ROOT / 'foundation/staging/phase3c5-http-review.json'
PRIVATE = ROOT / 'work/phase3c5-session.private.json'


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


class Review:
    def __init__(self):
        self.origin = 'https://' + NAME + '.andrewchris14.workers.dev'
        self.cookie = None
        self.review_key = None
        self.report = {'worker': NAME, 'started': utc(), 'samples': [], 'checks': {},
                       'budget': {'http_requests_max': 160, 'api_queries_max': 150,
                                  'reported_api_rows_read_max': 750000,
                                  'reported_api_rows_written_max': 50000},
                       'api_usage': {'queries': 0, 'rows_read': 0, 'rows_written': 0},
                       'cpu_source': 'Cloudflare workersInvocationsAdaptive; microseconds converted to ms',
                       'billing_plan_confirmed': False, 'human_review_writes': False,
                       'historical_import_executed': False, 'backup_delivery_retried': False}

    def save(self):
        REPORT.write_text(json.dumps(self.report, indent=2) + '\n')

    def verify(self):
        settings = api('/workers/scripts/' + NAME + '/settings')
        bindings = settings['bindings']
        dbs = [b for b in bindings if b['type'] == 'd1']
        assert len(dbs) == 1 and dbs[0]['name'] == 'DB'
        self.database = dbs[0]['id']
        info = api('/d1/database/' + self.database)
        assert info['name'] == NAME and self.database != STAGING_DB
        assert any(b['name'] == 'ISOLATED_TEST_STORAGE' and b.get('text') == 'true' for b in bindings)
        assert any(b['name'] == 'STAGING_ONLY' and b.get('text') == 'true' for b in bindings)
        assert any(b['name'] == 'STAGING_EDITOR' and b.get('text') == 'true' for b in bindings)
        self.report['resource_verification'] = {
            'database_id': self.database, 'database_name': info['name'],
            'isolation_markers_verified': True, 'initial_endpoint': api('/workers/scripts/' + NAME + '/subdomain'),
            'initial_worker_limits': settings.get('limits'), 'usage_model': settings.get('usage_model'),
            'initial_database_bytes': info.get('file_size'),
        }
        self.save()

    def configure_wrapper(self):
        # Original deployed modules are retained privately in ignored work
        # storage. Secrets are inherited; PIN/version/session state is untouched.
        self.original_modules = json.loads((ROOT / 'work/disposable-original-modules.private.json').read_text())
        settings = api('/workers/scripts/' + NAME + '/settings')
        self.original_bindings = [{'type': 'inherit', 'name': b['name']} if b['type'] == 'secret_text' else b
                                  for b in settings['bindings']]
        self.review_key = secrets.token_hex(32)
        modules = {**self.original_modules, 'free-review-wrapper.mjs':
                   (ROOT / 'foundation/staging/free-review-wrapper.mjs').read_text()}
        deploy(NAME, modules, 'free-review-wrapper.mjs', self.original_bindings + [
            {'type': 'secret_text', 'name': 'FREE_HTTP_REVIEW_KEY', 'text': self.review_key}])
        self.report['temporary_wrapper_deployed'] = True
        self.save()

    def disable(self):
        endpoint(NAME, False)
        for attempt in range(20):
            observed = api('/workers/scripts/' + NAME + '/subdomain')
            if not observed['enabled']:
                self.report['final_endpoint'] = observed
                return
            if attempt == 10:
                endpoint(NAME, False)
            time.sleep(2)
        raise RuntimeError('Endpoint disable has not converged; owner action required')

    def sql(self, statement, params=None):
        usage = self.report['api_usage']
        if usage['queries'] >= 150 or usage['rows_read'] >= 700000 or usage['rows_written'] >= 45000:
            raise RuntimeError('Bounded API usage stop')
        result = query(self.database, statement, params)
        usage['queries'] += 1
        for row in result:
            for key in ('rows_read', 'rows_written'):
                usage[key] += row.get('meta', {}).get(key, 0)
        self.save()
        if usage['rows_read'] > 750000 or usage['rows_written'] > 50000:
            raise RuntimeError('Reported API budget exceeded; stop further work')
        return result[0]['results']

    def call(self, label, path, body=None, *, diagnostic=False, authenticated=True, expected=200):
        if len(self.report['samples']) >= 160:
            raise RuntimeError('HTTP budget reached')
        # Distinct seconds permit unambiguous single-invocation analytics joins.
        time.sleep(max(0, 1.2 - time.time() % 1))
        headers = {'User-Agent': 'Mozilla/5.0', 'X-Staging-Metrics': 'on' if diagnostic else 'off'}
        if authenticated and self.cookie:
            headers['Cookie'] = self.cookie
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'Origin': self.origin})
        if path == '/test/free-review-login' and self.review_key:
            headers['X-Free-Review-Key'] = self.review_key
        req = urllib.request.Request(self.origin + path, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        started = utc()
        try:
            response = urllib.request.urlopen(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
            if response.headers.get('Set-Cookie'):
                self.cookie = response.headers['Set-Cookie'].split(';')[0]
            sample = {'operation': label, 'route': path.split('?')[0], 'started': started,
                      'ended': utc(), 'status': response.status, 'expected_status': expected,
                      'diagnostic': diagnostic, 'response_bytes': len(raw),
                      **response_evidence(self.origin, path, raw, response.headers)}
            if response.headers.get('X-Staging-D1-Reads') is not None:
                sample.update(rows_read=int(response.headers['X-Staging-D1-Reads']),
                              rows_written=int(response.headers['X-Staging-D1-Writes']),
                              d1_duration_ms=float(response.headers['X-Staging-D1-Ms']))
                # Diagnostic rows are not interchangeable with API setup usage.
                # Future runs stop before repeating unexpectedly expensive work.
                self.report.setdefault('diagnostic_http_usage', {'rows_read': 0, 'rows_written': 0})
                for key in ('rows_read', 'rows_written'):
                    self.report['diagnostic_http_usage'][key] += sample[key]
            self.report['samples'].append(sample)
            self.save()
            print(label, response.status, 'diagnostic' if diagnostic else 'raw', flush=True)
            if diagnostic and sample.get('rows_read', 0) > 100000:
                self.report['diagnostic_cost_stop'] = True
                self.save()
        return sample['status'], data

    def ready(self):
        successes = 0
        for i in range(20):
            status, _ = self.call('routing_readiness', '/public/categories', expected=200)
            successes = successes + 1 if status == 200 else 0
            if successes == 3:
                return
            time.sleep(2)
        raise RuntimeError('Disposable HTTP routing unavailable')

    def seed(self):
        # These are synthetic PUBLIC read-model fixtures, not historical records.
        # Only the 526-entry editable fixture gets item/group storage. This keeps
        # the setup within a bounded Free write budget; it is not a full D1 import.
        counts = {r['category']: r['n'] for r in self.sql(
            "SELECT json_extract(public_json,'$.display_category') category,count(*) n "
            "FROM public_records WHERE deleted=0 GROUP BY 1")}
        assert set(counts) <= set(TARGETS)
        assert not self.sql('SELECT id FROM records WHERE id LIKE ? LIMIT 1', [PREFIX + '%'])
        existing_items = self.sql("SELECT COALESCE(sum(json_array_length(g.value,'$.entries')),0) n "
                                  "FROM public_records p JOIN json_each(p.public_json,'$.groups') g WHERE p.deleted=0")[0]['n']
        needed = sum(TARGETS[c] - counts.get(c, 0) for c in TARGETS)
        assert 0 < needed <= 3394
        self.large_id = PREFIX + '1-0000'
        self.group_id = self.large_id + '-group'
        public_items = 59098 - existing_items - 526
        per, extra = divmod(public_items, needed - 1)
        fixtures, ordinal = [], 0
        stamp = utc()
        for category_index, (category, target) in enumerate(TARGETS.items()):
            for j in range(target - counts.get(category, 0)):
                rid = PREFIX + str(category_index) + '-' + str(j).zfill(4)
                n = 526 if rid == self.large_id else per + (ordinal < extra)
                if rid != self.large_id:
                    ordinal += 1
                content = {'id': rid, 'creation_origin': 'synthetic-disposable-http-review',
                           'set_name': 'Synthetic CPU fixture ' + rid, 'year': '2026',
                           'brand': 'Synthetic Maker', 'display_category': category,
                           'category': 'football_cards' if category == 'Football Wantlist' else 'baseball_cards',
                           'notes': ['Synthetic review fixture'], 'prefixes': [],
                           'source_list_type': 'want_list', 'entry_order': 'natural'}
                entries = [{'id': rid + '-item-' + str(k), 'value': 'Synthetic identifier ' + str(k),
                            'field_key': 'items', 'position': k, 'state': 'wanted', 'actionable': 1,
                            'pending_at': None, 'received_at': None} for k in range(n)]
                public = {**content, 'list_type': 'want_list', 'revision': 1, 'updated_at': stamp,
                          'deleted': False, 'projection_version': 2, 'groups': [{
                              'id': rid + '-group', 'kind': 'primary', 'list_type': 'want_list', 'entries': entries}]}
                fixtures.append({'id': rid, 'content': content, 'public': public})
        for offset in range(0, len(fixtures), 80):
            data = json.dumps(fixtures[offset:offset + 80])
            self.sql("INSERT INTO records SELECT json_extract(value,'$.id'),NULL,'want_list',"
                     "json_extract(value,'$.content'),1,?,?,NULL FROM json_each(?)", [stamp, stamp, data])
            self.sql("INSERT INTO public_records SELECT json_extract(value,'$.id'),1,?,0,"
                     "json_extract(value,'$.public') FROM json_each(?)", [stamp, data])
        self.sql("INSERT INTO record_groups VALUES(?,?,'primary',0,'want_list','{}','[\"items\"]')",
                 [self.group_id, self.large_id])
        self.sql("INSERT INTO items SELECT ?||'-item-'||key,?,'items',CAST(key AS INTEGER),"
                 "value,'wanted',1,NULL,NULL,NULL,NULL FROM json_each(?)",
                 [self.large_id, self.group_id, json.dumps(['Synthetic identifier ' + str(k) for k in range(526)])])
        self.report['fixture'] = {'synthetic_records_added': needed, 'existing_active_records': sum(counts.values()),
                                  'public_active_records': 3394, 'public_projected_entries': 59098,
                                  'editable_synthetic_entries': 526, 'historical_full_collection': False,
                                  'other_synthetic_entries_read_model_only': True, 'category_targets': TARGETS}
        self.save()

    def login(self, diagnostic=False):
        for attempt in range(4):
            status, _ = self.call('login_via_disposable_wrapper', '/test/free-review-login', {},
                                  diagnostic=diagnostic, authenticated=False)
            if status != 404:
                break
            time.sleep(3)
        assert status == 200, 'Existing disposable credential unavailable; do not reset it'
        PRIVATE.write_text(json.dumps({'cookie': self.cookie}))
        PRIVATE.chmod(0o600)

    def browse(self, diagnostic=False):
        all_records, after, pages = [], '', 0
        while True:
            status, body = self.call('full_collection_index', '/public/index?after=' + urllib.parse.quote(after),
                                     diagnostic=diagnostic, authenticated=False)
            assert status == 200
            all_records.extend(body['records'])
            pages += 1
            after = body['next']
            if not after:
                break
        assert len(all_records) == 3394 and len({r['id'] for r in all_records}) == 3394 and pages == 7
        assert collections.Counter(r['display_category'] for r in all_records) == TARGETS
        # Use the application's actual client search/year/category adapters on
        # the complete index fetched from the remote Worker; do not save rows.
        js = """
import {prepareRecords,queryMatches} from './site/model.js';
import {publicSearchRecord,effectiveCategory,recordYear,yearInfo} from './owner/model.js';
let input='';for await(const chunk of process.stdin)input+=chunk;
const records=JSON.parse(input),prepared=prepareRecords(records.map(publicSearchRecord));
const synthetic=prepared.filter(r=>r.id.startsWith('synthetic-3c5-'));
if(!synthetic.length||synthetic.some(r=>!queryMatches(r,'Synthetic CPU fixture')))throw Error('search');
if(synthetic.some(r=>!queryMatches(r,'Synthetic identifier 1')))throw Error('item search');
if(synthetic.some(r=>!yearInfo(recordYear(r)).keys.includes('2026')||r.brand!=='Synthetic Maker'))throw Error('filters');
if(prepared.some(r=>queryMatches(r,'zzznomatchuniquezzzz')))throw Error('negative search');
if(new Set(records.map(effectiveCategory)).size!==7)throw Error('categories');
console.log('application search and filter checks passed');
"""
        subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT,
                       input=json.dumps(all_records), text=True, check=True, capture_output=True)
        for category in TARGETS:
            row = next(r for r in all_records if r['display_category'] == category)
            status, detail = self.call('category_detail_' + category, '/public/record?id=' + urllib.parse.quote(row['id']),
                                       diagnostic=diagnostic, authenticated=False)
            assert status == 200 and detail['id'] == row['id']
        self.report['checks'].update(seven_http_index_pages=True, all_categories=True,
                                     application_search_year_manufacturer_filters=True)
        self.report['search_filter_worker_cpu'] = 'Client-side operations; no dedicated Worker routes. CPU measured for index and detail fetches.'
        self.save()

    def edits(self, diagnostic=False):
        status, owner = self.call('owner_large_record', '/owner/record?id=' + self.large_id, diagnostic=diagnostic)
        assert status == 200
        revision = owner['revision']
        original = [(i['id'], i['state']) for g in owner['groups'] for i in g['entries'] if not i['deleted_at']]
        assert len(original) == 526
        def edit(label, expected=200, **payload):
            nonlocal revision
            body = {'request_id': str(uuid.uuid4()), 'record_id': self.large_id, 'revision': revision, **payload}
            status, result = self.call(label, '/action', body, diagnostic=diagnostic, expected=expected)
            if status == 200:
                revision = result['revision']
            return status, result, body
        def undo(label):
            history = self.sql("SELECT id FROM change_history WHERE record_id=? AND action='edit_session' "
                               "AND json_extract(after_json,'$._record_revision')=?", [self.large_id, revision])
            assert len(history) == 1
            return edit(label, op='undo', history_id=history[0]['id'])
        assert edit('notes_save', op='edit_session', metadata={'notes': ['Synthetic current note']})[0] == 200
        assert undo('notes_undo')[0] == 200
        one = original[0][0]
        assert edit('pending_save', op='edit_session', changes=[{'id': one, 'state': 'pending', 'removed': False}])[0] == 200
        status, public = self.call('pending_public_detail', '/public/record?id=' + self.large_id,
                                   diagnostic=diagnostic, authenticated=False)
        assert status == 200 and any(i['id'] == one and i['state'] == 'pending' for g in public['groups'] for i in g['entries'])
        assert edit('pending_cancel', op='edit_session', changes=[{'id': one, 'state': 'wanted', 'removed': False}])[0] == 200
        assert edit('normal_combined_save', op='edit_session', metadata={'notes': ['Synthetic combined note']},
                    additions=[{'group_id': self.group_id, 'field_key': 'items', 'value': 'Synthetic normal addition', 'state': 'wanted'}])[0] == 200
        assert undo('normal_save_undo')[0] == 200
        changes = [{'id': i, 'state': 'pending', 'removed': False} for i, _ in original[:500]]
        additions = [{'group_id': self.group_id, 'field_key': 'items', 'state': 'wanted',
                      'value': ('Synthetic maximum ' + str(k).zfill(3) + ' ' + 'X' * 500)[:500]} for k in range(500)]
        status, _, body = edit('maximum_500_changes_500_additions', op='edit_session',
                               metadata={'notes': ['Synthetic maximum combined Save']}, changes=changes, additions=additions)
        self.report['checks']['maximum_save_' + ('diagnostic' if diagnostic else 'raw')] = status == 200
        if status == 200:
            if diagnostic and self.report.get('diagnostic_cost_stop'):
                # Finish the inverse transaction on our synthetic fixture before
                # stopping; do not repeat or replay the expensive Save.
                assert undo('large_undo_500_changes_500_additions')[0] == 200
                restored = self.sql('SELECT id,state FROM items WHERE group_id=? AND deleted_at IS NULL ORDER BY id', [self.group_id])
                assert sorted((r['id'], r['state']) for r in restored) == sorted(original)
                self.report['checks']['synthetic_record_restored_diagnostic'] = True
                self.save()
                raise RuntimeError('Expensive diagnostic request; do not repeat before review')
            before_replay = self.sql('SELECT revision FROM records WHERE id=?', [self.large_id])[0]['revision']
            replay, replay_body = self.call('maximum_save_replay', '/action', body, diagnostic=diagnostic)
            assert replay == 200 and replay_body.get('replayed')
            assert self.sql('SELECT revision FROM records WHERE id=?', [self.large_id])[0]['revision'] == before_replay
            state = self.sql("SELECT count(*) active,sum(state='pending') pending FROM items WHERE group_id=? AND deleted_at IS NULL", [self.group_id])[0]
            assert state == {'active': 1026, 'pending': 500}
            assert undo('large_undo_500_changes_500_additions')[0] == 200
            restored = self.sql('SELECT id,state FROM items WHERE group_id=? AND deleted_at IS NULL ORDER BY id', [self.group_id])
            assert sorted((r['id'], r['state']) for r in restored) == sorted(original)
            stale_status, _, _ = edit('stale_revision_rejected', expected=409, op='edit_session', metadata={}, revision=body['revision'])
            assert stale_status == 409
        self.report['checks']['synthetic_record_restored_' + ('diagnostic' if diagnostic else 'raw')] = True
        self.save()

    def run(self):
        self.verify()
        try:
            self.configure_wrapper()
            endpoint(NAME, True)
            self.ready()
            self.login()
            self.seed()
            self.call('unauthenticated_owner_rejected', '/owner/record?id=' + self.large_id,
                      authenticated=False, expected=401)
            self.call('remembered_session', '/session')
            self.browse(diagnostic=True)
            self.call('remembered_session', '/session', diagnostic=True)
            self.edits(diagnostic=True)
            self.browse()
            self.edits()
            self.edits()
            self.report['checks']['invalid_pin_rejected'] = self.call('invalid_pin_rejected', '/login',
                {'credential': 'not-a-pin', 'remembered': True}, authenticated=False, expected=401)[0] == 401
        except Exception as error:
            # Exception messages may contain response bodies or private inputs.
            self.report['stopped_error_type'] = type(error).__name__
            print('Review stopped:', type(error).__name__, flush=True)
        finally:
            self.disable()
            if self.report.get('temporary_wrapper_deployed'):
                deploy(NAME, self.original_modules, 'worker.mjs', self.original_bindings)
                # Deleting only our temporary secret cannot change the owner PIN.
                api('/workers/scripts/' + NAME + '/secrets/FREE_HTTP_REVIEW_KEY', 'DELETE')
                self.report['temporary_wrapper_removed'] = True
                self.disable()
            self.report['ended'] = utc()
            self.report['final_database_bytes'] = api('/d1/database/' + self.database).get('file_size')
            self.save()
            print('Disposable endpoint disabled and API-verified', flush=True)

    def collect(self):
        self.report = json.loads(REPORT.read_text())
        rows = metrics_groups(NAME, self.report['started'], self.report['ended'])
        self.report['analytics_observations'] = rows
        # Analytics dimensions are second-resolution. Reject ambiguous buckets.
        by_second = collections.defaultdict(list)
        for row in rows:
            by_second[row['dimensions']['datetime']].append(row)
        for sample in self.report['samples']:
            keys = {sample['started'].split('.')[0] + 'Z', sample['ended'].split('.')[0] + 'Z'}
            candidates = [row for key in keys for row in by_second[key] if row['sum']['requests'] == 1]
            if len(candidates) == 1:
                row = candidates[0]
                sample['cpu_ms'] = row['quantiles']['cpuTimeP50'] / 1000
                sample['analytics_datetime'] = row['dimensions']['datetime']
                sample['worker_errors'] = row['sum']['errors']
        summary = {}
        for op in sorted({s['operation'] for s in self.report['samples']}):
            raw = [s for s in self.report['samples'] if s['operation'] == op and not s['diagnostic']]
            cpu = [s['cpu_ms'] for s in raw if 'cpu_ms' in s]
            diag = [s for s in self.report['samples'] if s['operation'] == op and s['diagnostic']]
            summary[op] = {'raw_requests': len(raw), 'unexpected_http_statuses': sum(s['status'] != s['expected_status'] for s in raw),
                           'cpu_observations': len(cpu), 'median_cpu_ms': statistics.median(cpu) if cpu else None,
                           'max_cpu_ms': max(cpu) if cpu else None, 'over_10ms': sum(v > 10 for v in cpu),
                           'diagnostic_d1': [{k: s[k] for k in ('rows_read', 'rows_written', 'd1_duration_ms') if k in s} for s in diag]}
        self.report['summary'] = summary
        self.report['worker_errors_observed'] = sum(r['sum']['errors'] for r in rows)
        self.report['analytics_requests_observed'] = sum(r['sum']['requests'] for r in rows)
        self.report['free_cpu_gate_passed'] = None if any(s['raw_requests'] and not s['cpu_observations'] for s in summary.values()) else all(not s['over_10ms'] for s in summary.values())
        self.save()
        print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Enable only the verified disposable endpoint and test')
    parser.add_argument('--collect', action='store_true', help='Read actual Cloudflare analytics without enabling endpoint')
    args = parser.parse_args()
    if args.run == args.collect:
        parser.error('Choose exactly one of --run or --collect')
    if args.run and REPORT.exists():
        parser.error('Review evidence already exists; automatic reruns are disabled. Use --collect for read-only analytics.')
    review = Review()
    review.run() if args.run else review.collect()
