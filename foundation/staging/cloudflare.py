"""Restricted Cloudflare API client for explicitly named staging resources.

Secrets are sent only to api.cloudflare.com, never printed or saved by this module.
No billing API or production routing operations are implemented.
"""
import json
import os
import secrets
import urllib.request

WORKER = 'wantlist-staging'
PROBE = 'wantlist-staging-3b2-probe'


def api(path, method='GET', payload=None, raw=None, content_type=None):
    account = os.environ['CLOUDFLARE_ACCOUNT_ID']
    data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    headers = {'Authorization': 'Bearer ' + os.environ['CLOUDFLARE_API_TOKEN'], 'User-Agent': 'Mozilla/5.0'}
    if data is not None:
        headers['Content-Type'] = content_type or 'application/json'
    req = urllib.request.Request('https://api.cloudflare.com/client/v4/accounts/' + account + path,
                                 data=data, headers=headers, method=method)
    try:
        result = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Cloudflare API HTTP {error.code}; no payload logged') from None
    if not result.get('success'):
        raise RuntimeError('Cloudflare API rejected staging operation: ' + str(result.get('errors')))
    return result['result']


def deploy(name, modules, main, bindings):
    if name not in (WORKER, PROBE):
        raise ValueError('Only the approved staging Worker names may be deployed')
    if name == WORKER and any(b.get('name') == 'ISOLATED_TEST_STORAGE' and b.get('text') == 'true' for b in bindings):
        raise ValueError('Human-review staging cannot enable diagnostic test writes')
    metadata = {'main_module': main, 'compatibility_date': '2026-10-01', 'bindings': bindings}
    boundary = '----staging' + secrets.token_hex(12)
    parts = []
    for name_, filename, body, mime in [('metadata', None, json.dumps(metadata), 'application/json')] + [
        (name_, name_, body, 'application/javascript+module') for name_, body in modules.items()
    ]:
        disposition = f'form-data; name="{name_}"' + (f'; filename="{filename}"' if filename else '')
        parts.append(f'--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {mime}\r\n\r\n{body}\r\n'.encode())
    raw = b''.join(parts) + f'--{boundary}--\r\n'.encode()
    return api('/workers/scripts/' + name, 'PUT', raw=raw, content_type='multipart/form-data; boundary=' + boundary)


def endpoint(name, enabled):
    if name not in (WORKER, PROBE):
        raise ValueError('Staging names only')
    return api('/workers/scripts/' + name + '/subdomain', 'POST', {'enabled': enabled, 'previews_enabled': False})


def query(database, sql, params=None):
    return api('/d1/database/' + database + '/query', 'POST', {'sql': sql, 'params': params or []})


def metrics(name, start, end):
    if name not in (WORKER, PROBE):
        raise ValueError('Staging metrics only')
    # Cloudflare's Time-variable filtering returned empty data despite matching
    # literal timestamp queries; serialize validated strings as GraphQL literals.
    from datetime import datetime
    for value in (start, end):
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    q = 'query($account: String!) { viewer { accounts(filter: {accountTag: $account}) { workersInvocationsAdaptive(limit: 10, filter: {scriptName: '+json.dumps(name)+', datetime_geq: '+json.dumps(start)+', datetime_leq: '+json.dumps(end)+'}) { sum {requests errors} quantiles {cpuTimeP50 cpuTimeP99 wallTimeP50 wallTimeP99} } } } }'
    req = urllib.request.Request('https://api.cloudflare.com/client/v4/graphql',
        data=json.dumps({'query': q, 'variables': {'account': os.environ['CLOUDFLARE_ACCOUNT_ID']}}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['CLOUDFLARE_API_TOKEN'], 'Content-Type': 'application/json',
                 'User-Agent': 'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req, timeout=30))


def metrics_groups(name, start, end):
    """Minute-aligned analytics fetch; retain only measured invocation timestamps.

    Sub-minute aggregate filters returned empty data for observed requests. Keep
    explicit timestamps/group counts; do not invent per-request CPU measurements.
    """
    from datetime import datetime, timedelta
    if name not in (WORKER, PROBE):
        raise ValueError('Staging metrics only')
    a = datetime.fromisoformat(start.replace('Z', '+00:00'))
    b = datetime.fromisoformat(end.replace('Z', '+00:00'))
    lower = a.replace(second=0, microsecond=0).isoformat().replace('+00:00','Z')
    upper = (b.replace(second=0, microsecond=0)+timedelta(minutes=1)).isoformat().replace('+00:00','Z')
    q = 'query($account: String!) {viewer {accounts(filter:{accountTag:$account}) {workersInvocationsAdaptive(limit:1000,filter:{scriptName:'+json.dumps(name)+',datetime_geq:'+json.dumps(lower)+',datetime_leq:'+json.dumps(upper)+'}) {dimensions {datetime status} quantiles {cpuTimeP50 cpuTimeP99 wallTimeP50 wallTimeP99} sum {requests errors}}}}}'
    req = urllib.request.Request('https://api.cloudflare.com/client/v4/graphql',
        data=json.dumps({'query':q,'variables':{'account':os.environ['CLOUDFLARE_ACCOUNT_ID']}}).encode(),
        headers={'Authorization':'Bearer '+os.environ['CLOUDFLARE_API_TOKEN'],'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    r = json.load(urllib.request.urlopen(req,timeout=30))
    if r.get('errors'):
        raise RuntimeError('Analytics unavailable')
    rows = r['data']['viewer']['accounts'][0]['workersInvocationsAdaptive']
    return [row for row in rows if a <= datetime.fromisoformat(row['dimensions']['datetime'].replace('Z','+00:00')) <= b]
