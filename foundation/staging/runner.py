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


def deploy_staging():
    s = state()
    assert s['worker'] == WORKER
    cfg = {'algorithm': 'SHA-256', 'digest': hashlib.sha256(s['credential'].encode()).hexdigest(), 'version': s['credential_version']}
    bindings = [{'type':'secret_text','name':'OWNER_AUTH_CONFIG','text':json.dumps(cfg)},
                {'type':'secret_text','name':'PROBE_KEY','text':s['operator_key']},
                {'type':'plain_text','name':'STAGING_ONLY','text':'true'},
                {'type':'d1','name':'DB','id':s['database_id']}]
    modules = {name: (ROOT / 'foundation/staging' / name).read_text() for name in ('worker.mjs','auth.js','records.js')}
    deploy(WORKER, modules, 'worker.mjs', bindings)
    endpoint(WORKER, True)


class Client:
    def __init__(self):
        self.state = state()
        self.origin = 'https://' + WORKER + '.andrewchris14.workers.dev'
        self.cookie = None
        self.measurements = []

    def call(self, path, body=None, *, cookie=True, origin=True, gate=True):
        headers = {'User-Agent':'Mozilla/5.0'}
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

    def wait_ready(self):
        for _ in range(30):
            r = self.call('/health')
            if r['status'] == 200:
                return
            time.sleep(2)
        raise RuntimeError('Staging routing unavailable')


def sql(statement, *params):
    return {'sql':statement,'params':list(params)}
