import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from foundation.staging import runner
class IsolationTests(unittest.TestCase):
 def test_legacy_remote_state_cannot_run_write_tests(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';path.write_text(json.dumps({'worker':'wantlist-staging','database_id':'human-review'}))
   with patch.object(runner,'STATE',path):
    with self.assertRaisesRegex(RuntimeError,'Remote write-producing tests disabled'):runner.state()
 def test_even_claimed_remote_isolation_requires_supported_provisioning(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';path.write_text(json.dumps({'worker':'wantlist-test-unverified','test_isolation':True}))
   with patch.object(runner,'STATE',path):
    with self.assertRaisesRegex(RuntimeError,'not enabled'):runner.state()

 def test_human_review_deployment_rejects_test_write_capability(self):
  from foundation.staging.cloudflare import deploy
  with self.assertRaisesRegex(ValueError,'cannot enable diagnostic'):
   deploy('wantlist-staging',{},'worker.mjs',[{'name':'ISOLATED_TEST_STORAGE','type':'plain_text','text':'true'}])
