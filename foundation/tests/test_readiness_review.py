import hashlib,json,unittest
from unittest.mock import patch
from foundation.staging.cleanup_review import review
from foundation.staging.historical_import import Remote

def fixture():
 records=[{'id':'owner-record-practice-'+str(n),'revision':1,'content_json':'{}','deleted_at':None,'import_id':None} for n in range(202)]
 entries=[{'id':r['id'],'expected_revision':1,'content_sha256':hashlib.sha256(b'{}').hexdigest()} for r in records]
 manifest={'count':202,'records':entries,'manifest_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 return {'tables':{'records':records,'provenance':[],'items':[{'value':'cpu-test-removed','deleted_at':'removed'}]}},manifest
class ReadinessReviewTests(unittest.TestCase):
 def test_practice_manifest_excludes_sources_and_detects_later_edits(self):
  snap,m=fixture();r=review(snap,m);self.assertEqual(r['historical_ids_affected'],0);self.assertEqual(r['active_benchmark_rows'],0)
  snap['tables']['records'][0]['revision']=2;self.assertEqual(review(snap,m)['revision_or_content_conflicts'],['owner-record-practice-0'])
 def test_unexpected_provenance_duplicate_and_incomplete_coverage_fail_closed(self):
  snap,m=fixture();snap['tables']['provenance']=[{'record_id':'owner-record-practice-0'}]
  with self.assertRaises(ValueError):review(snap,m)
  snap,m=fixture();m['records'][0]['id']='p0060-l001'
  m['manifest_sha256']=hashlib.sha256(json.dumps(m['records'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with self.assertRaises(ValueError):review(snap,m)
  snap,m=fixture();snap['tables']['records'].append({'id':'owner-record-unreviewed','revision':1,'deleted_at':None})
  with self.assertRaises(ValueError):review(snap,m)
 def test_remote_meter_counts_read_and_write_statement_overhead(self):
  t=object.__new__(Remote);t.database='isolated-test';t.meter={'api_requests':0,'rows_read':0,'rows_written':0,'d1_duration_ms':0}
  response=[{'results':[{'count':3}],'meta':{'rows_read':3,'rows_written':2,'duration':1.25}}]
  with patch('foundation.staging.historical_import.query',return_value=response):
   self.assertEqual(t.rows('SELECT'),[{'count':3}]);self.assertEqual(t.statement('INSERT'),2)
  self.assertEqual(t.meter,{'api_requests':2,'rows_read':6,'rows_written':4,'d1_duration_ms':2.5})
if __name__=='__main__':unittest.main()
