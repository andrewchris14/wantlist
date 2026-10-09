import hashlib
import json
import unittest
from foundation.staging.free_http_review import response_evidence

class ResponseEvidenceTests(unittest.TestCase):
    def test_index_failure_preserves_only_safe_headers_and_public_cursor(self):
        raw=b'private synthetic body not retained'
        report=response_evidence('https://local.invalid','/public/index?after=synthetic-id',raw,{'CF-Ray':'fake-ray','Server':'cloudflare','Content-Type':'text/html','Set-Cookie':'private-cookie','Authorization':'private-token'})
        self.assertEqual(report['response_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(report['public_index_url'],'https://local.invalid/public/index?after=synthetic-id')
        encoded=json.dumps(report)
        for secret in ('private synthetic','private-cookie','private-token','Set-Cookie','Authorization'):
            self.assertNotIn(secret,encoded)
    def test_private_route_query_is_not_retained(self):
        result=response_evidence('https://local.invalid','/owner/record?id=private-id',b'{}',{})
        self.assertIsNone(result['public_index_url'])
        self.assertNotIn('private-id',json.dumps(result))

if __name__=='__main__':unittest.main()
