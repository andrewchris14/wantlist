"""Operator-only staging harness. No owner secrets/session tokens in reports.

State is held in ignored foundation/.local/staging-access.json. Only staging
resources are accepted. Do not use this diagnostic deployment as production.
"""
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from .cloudflare import WORKER, deploy, endpoint, query

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'foundation/.local/staging-access.json'


def state():
    return json.loads(STATE.read_text())


def deploy_staging(instrumented=True, benchmark_version=None, editor=False):
    benchmark_version = benchmark_version or 'cpu-review-' + secrets.token_hex(12)
    s = state()
    assert s['worker'] == WORKER
    cfg = {'algorithm': 'SHA-256', 'digest': hashlib.sha256(s['credential'].encode()).hexdigest(), 'version': s['credential_version']}
    bindings = [{'type':'secret_text','name':'OWNER_AUTH_CONFIG','text':json.dumps(cfg)},
                {'type':'secret_text','name':'PROBE_KEY','text':s['operator_key']},
                {'type':'plain_text','name':'STAGING_ONLY','text':'true'},
                {'type':'plain_text','name':'STAGING_EDITOR','text':'true' if editor else 'false'},
                {'type':'plain_text','name':'STAGING_BENCH_VERSION','text':benchmark_version},
                {'type':'plain_text','name':'STAGING_METRICS','text':'true' if instrumented else 'false'},
                {'type':'d1','name':'DB','id':s['database_id']}]
    modules = {name: (ROOT / 'foundation/staging' / name).read_text() for name in ('worker.mjs','auth.js','records.js','owner.js','editor-assets.js')}
    if editor:
        assets={}
        dist=ROOT/'foundation/.local/editor-dist'
        for p in dist.rglob('*'):
            if p.is_file():
                key='/' + str(p.relative_to(dist))
                assets[key]={'body':p.read_text(),'type':'text/html; charset=utf-8' if p.suffix=='.html' else 'text/css; charset=utf-8' if p.suffix=='.css' else 'application/javascript; charset=utf-8'}
        assert '/index.html' in assets,'Build the isolated editor first'
        assets['/']=assets['/index.html']
        modules['editor-assets.js']='export const editorAssets='+json.dumps(assets)+';'
    deploy(WORKER, modules, 'worker.mjs', bindings)
    endpoint(WORKER, True)
    return benchmark_version


class Client:
    def __init__(self):
        self.state = state()
        self.origin = 'https://' + WORKER + '.andrewchris14.workers.dev'
        self.cookie = None
        self.measurements = []

    def call(self, path, body=None, *, cookie=True, origin=True, gate=True, instrumented=True):
        headers = {'User-Agent':'Mozilla/5.0'}
        headers['X-Staging-Metrics']='on' if instrumented else 'off'
        if gate:
            headers['X-Staging-Probe'] = self.state['operator_key']
        if cookie and self.cookie:
            headers['Cookie'] = self.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'
            if origin:
                headers['Origin'] = self.origin
        # Cache-busting only, never put secrets in URLs.
        separator = '&' if '?' in path else '?'
        req = urllib.request.Request(self.origin + path + separator + 'test=' + secrets.token_hex(6),
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        start = time.perf_counter()
        try:
            response = urllib.request.urlopen(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                data = json.loads(raw)
            except ValueError:
                data = {'error':'Non-JSON staging response'}
            result = {'status':response.status, 'body':data, 'rows_read':int(response.headers.get('X-Staging-D1-Reads',0)),
                      'rows_written':int(response.headers.get('X-Staging-D1-Writes',0)),
                      'd1_duration_ms':float(response.headers.get('X-Staging-D1-Ms',0)),
                      'instrumented':response.headers.get('X-Staging-D1-Reads') is not None,
                      'client_wall_ms':round((time.perf_counter()-start)*1000,3)}
            if response.headers.get('Set-Cookie'):
                self.cookie = response.headers['Set-Cookie'].split(';')[0]
                result['cookie_flags'] = ';'.join(response.headers['Set-Cookie'].split(';')[1:])
        self.measurements.append({'path':path.split('?')[0],**{k:v for k,v in result.items() if k not in ('body',)}})
        return result

    def batch(self, statements):
        r = self.call('/test/batch', {'statements':statements})
        if r['status'] != 200:
            raise RuntimeError('Staging transactional batch failed; response does not expose SQL/secrets')
        return r

    def login(self, remembered=True):
        return self.call('/login', {'credential':self.state['credential'],'remembered':remembered}, cookie=False)

    def wait_ready(self, expected_version=None):
        for _ in range(30):
            r = self.call('/health')
            if r['status'] == 200 and (expected_version is None or r['body'].get('benchmark_version')==expected_version):
                return
            time.sleep(2)
        raise RuntimeError('Staging routing unavailable')


def sql(statement, *params):
    return {'sql':statement,'params':list(params)}
