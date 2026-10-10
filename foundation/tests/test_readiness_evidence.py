import json,unittest
from foundation.staging.minimal_free_release import ROOT
from foundation.staging.readiness_evidence import classify,ERROR_1042_SHA256
class AttributionTests(unittest.TestCase):
    def test_saved_response_matches_standard_1042_fingerprint(self):
        r=json.loads((ROOT/'docs/evidence/minimal-free-attempt-20261010.json').read_text())['samples'][0]
        self.assertEqual(classify(r)['known_error_code'],1042)
    def test_ray_and_envoy_alone_do_not_establish_worker_origin(self):
        self.assertEqual(classify({'status':404,'headers':{'server':'envoy','cf-ray':'a4825a2a5a5af210-LAX'}})['classification'],'unattributed_response')
    def test_hash_requires_matching_size(self):
        self.assertFalse(classify({'status':404,'response_sha256':ERROR_1042_SHA256,'response_bytes':18})['application_route_confirmed'])
        self.assertEqual(classify({'response_sha256':ERROR_1042_SHA256,'response_bytes':18})['classification'],'unattributed_response')
    def test_marker_requires_expected_public_nonce_and_expected_status(self):
        nonce='a'*32;r={'status':200,'headers':{'X-Wantlist-Readiness':'no-d1-v1','X-Wantlist-Readiness-Nonce':nonce}}
        self.assertTrue(classify(r,nonce)['application_route_confirmed']);self.assertFalse(classify(r,'b'*32)['application_route_confirmed']);self.assertFalse(classify(r,None)['application_route_confirmed'])
        r['status']=403;self.assertFalse(classify(r,nonce)['authorized_response']);self.assertTrue(classify(r,nonce)['application_route_confirmed'])
        r['status']=404;self.assertFalse(classify(r,nonce)['application_route_confirmed'])

class SafeHeaderTests(unittest.TestCase):
    def test_transport_retains_marker_but_never_cookie_or_key_in_evidence(self):
        from foundation.staging.minimal_free_transport import LiveTransport
        t=LiveTransport.__new__(LiveTransport);t.key='private-review-key';t.cookie=None
        nonce='a'*32
        t.request=lambda *args,**kw:(200,{'X-Wantlist-Readiness':'no-d1-v1','X-Wantlist-Readiness-Nonce':nonce,'Set-Cookie':'private-cookie; Secure','Authorization':'private-auth'},b'{"probe":"wantlist-readiness-no-d1-v1"}')
        evidence,_=t.http('/public/index?after=')
        self.assertTrue(classify(evidence,nonce)['application_route_confirmed'])
        self.assertNotIn('private-',json.dumps(evidence));self.assertEqual(t.cookie,'private-cookie')
