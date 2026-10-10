"""Offline response attribution hints, not a connected diagnostic or proof of origin."""
import hashlib,re
ERROR_1042=b'error code: 1042\n'
ERROR_1042_SHA256=hashlib.sha256(ERROR_1042).hexdigest()
MARKER='no-d1-v1'

def classify(sample,expected_nonce=None):
    headers={k.lower():v for k,v in sample.get('headers',{}).items()}
    fingerprint=sample.get('response_bytes')==len(ERROR_1042) and sample.get('response_sha256')==ERROR_1042_SHA256
    marked=(isinstance(expected_nonce,str) and re.fullmatch(r'[a-f0-9]{32}',expected_nonce) is not None
            and headers.get('x-wantlist-readiness')==MARKER and headers.get('x-wantlist-readiness-nonce')==expected_nonce
            and sample.get('status') in (200,403))
    if fingerprint:return {'classification':'cloudflare_1042_fingerprint','application_route_confirmed':False,'known_error_code':1042}
    if marked:return {'classification':'disposable_probe_marker_observed','application_route_confirmed':True,'authorized_response':sample['status']==200}
    return {'classification':'unattributed_response','application_route_confirmed':False}
