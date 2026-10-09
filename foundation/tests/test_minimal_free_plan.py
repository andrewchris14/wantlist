from datetime import datetime, timedelta, timezone
import unittest
from foundation.staging.minimal_free_plan import (
    WORKER, DATABASE, STAGING_DATABASE, admit, verify_quota, verify_resources, verify_review_release,
    cpu_observation, Measurements, MEASURED_SEQUENCE, StopReview,
    protected_scope, CallBudget, maximum_payload, FIXTURE_RECORD, FIXTURE_GROUP,
)

NOW=datetime(2026,10,10,15,tzinfo=timezone.utc)
def quota():
    return {'workers_free_confirmed':True,'d1_free_confirmed':True,'account_wide':True,'period_verified':True,
            'source':'owner-dashboard','competing_bulk_jobs_paused':True,'observed_at_utc':NOW.isoformat(),
            'period_start_utc':NOW.replace(hour=0).isoformat(),
            'period_end_utc':(NOW.replace(hour=0)+timedelta(days=1)).isoformat(),
            'rows_read_upper_bound':10000,'rows_written_upper_bound':1000,'worker_requests_upper_bound':1000,
            'storage_bytes_upper_bound':36000000,'database_count':3,'disposable_database_bytes_upper_bound':10000000,
            'migration_pending':True,'migration_scan_bound_confirmed':True}
def resources():
    return {'worker_name':WORKER,'database_name':WORKER,'database_id':DATABASE,
            'bindings':[{'name':'DB','type':'d1','id':DATABASE}]+[{'name':name,'type':'plain_text','text':'true'} for name in ('STAGING_ONLY','STAGING_EDITOR','ISOLATED_TEST_STORAGE')],
            'custom_domains':[],'routes':[],'endpoint_enabled':False,'previews_enabled':False,
            'reviewed_code_and_schema_verified':True,'synthetic_fixture_verified':True,'explicit_cpu_limit_ms':None}
def sample(label, diagnostic=True):
    return {'label':label,'diagnostic':diagnostic,'status':200,'started':'2026-10-10T15:00:01.200Z',
            'ended':'2026-10-10T15:00:01.800Z','d1_complete':True,'rows_read':100,'rows_written':1}
def analytics(cpu_us=5000):
    return [{'dimensions':{'datetime':'2026-10-10T15:00:01Z','status':'success'},'sum':{'requests':1,'errors':0},'quantiles':{'cpuTimeP50':cpu_us}}]

class AdmissionTests(unittest.TestCase):
    def test_usage_update_is_not_remote_approval(self):
        with self.assertRaisesRegex(StopReview,'OWNER_REMOTE_AUTHORIZATION_REQUIRED'):
            admit(quota(),resources(),NOW)
    def test_current_owner_report_cannot_admit_the_review(self):
        q=quota();q.update(rows_read_upper_bound=6_560_000,rows_written_upper_bound=52750)
        with self.assertRaisesRegex(StopReview,'INSUFFICIENT_ACCOUNT_WIDE_HEADROOM'):
            admit(q,resources(),NOW,True)
    def test_sufficient_fresh_account_wide_usage_and_exact_resources_admit(self):
        self.assertEqual(admit(quota(),resources(),NOW,True)['remaining_reads'],4_990_000)
    def test_missing_stale_or_wrong_period_quota_fails_closed(self):
        cases=[{'account_wide':False},{'workers_free_confirmed':False},{'d1_free_confirmed':False},
               {'rows_read_upper_bound':None},{'worker_requests_upper_bound':None},{'rows_written_upper_bound':True},
               {'observed_at_utc':(NOW-timedelta(minutes=6)).isoformat()},
               {'observed_at_utc':(NOW+timedelta(minutes=1)).isoformat()},
               {'period_end_utc':NOW.isoformat()},{'migration_scan_bound_confirmed':False},
               {'period_verified':False},{'competing_bulk_jobs_paused':False},{'rows_read_upper_bound':2_000_000},
               {'rows_written_upper_bound':61000},{'worker_requests_upper_bound':99500},{'storage_bytes_upper_bound':None},{'database_count':11},{'disposable_database_bytes_upper_bound':490000001}]
        for patch in cases:
            with self.subTest(patch=patch),self.assertRaises(StopReview):
                verify_quota({**quota(),**patch},NOW)
    def test_missing_or_extra_d1_binding_and_staging_identity_fail(self):
        for patch in [{'database_id':STAGING_DATABASE},{'worker_name':'wantlist-staging'},
                      {'custom_domains':['private.example']},{'routes':None},
                      {'endpoint_enabled':True},{'previews_enabled':True},
                      {'reviewed_code_and_schema_verified':False},{'synthetic_fixture_verified':False},
                      {'explicit_cpu_limit_ms':30000}]:
            with self.subTest(patch=patch),self.assertRaises(StopReview):verify_resources({**resources(),**patch})
        for extra in [{'name':'OTHER','type':'d1','id':STAGING_DATABASE},
                      {'name':'DB','type':'d1','id':DATABASE},
                      {'name':'STORE','type':'kv_namespace'},
                      {'name':'PHASE35_MAINTENANCE_DIGEST','type':'secret_text'}]:
            r=resources();r['bindings'].append(extra)
            with self.assertRaises(StopReview):verify_resources(r)

class ReleaseTests(unittest.TestCase):
    def release(self):
        r=resources();r.update(main_module='free-review-wrapper.mjs',release_module_digests_verified=True)
        r['bindings'] += [{'name':name,'type':'plain_text','text':'true'} for name in ('MINIMAL_FREE_REVIEW','STAGING_METRICS')]
        r['bindings'] += [{'name':'FREE_HTTP_REVIEW_KEY','type':'secret_text'},
                          {'name':'MINIMAL_FREE_REVIEW_UNTIL','type':'plain_text','text':(NOW+timedelta(minutes=10)).isoformat()}]
        return r
    def test_guarded_release_requires_verified_short_lease_and_disabled_endpoint(self):
        self.assertTrue(verify_review_release(self.release(),NOW))
        for name in ('MINIMAL_FREE_REVIEW','STAGING_METRICS','FREE_HTTP_REVIEW_KEY','MINIMAL_FREE_REVIEW_UNTIL'):
            r=self.release();r['bindings']=[b for b in r['bindings'] if b['name']!=name]
            with self.assertRaises(StopReview):verify_review_release(r,NOW)
        r=self.release();r['main_module']='worker.mjs'
        with self.assertRaises(StopReview):verify_review_release(r,NOW)
        r=self.release();r['endpoint_enabled']=True
        with self.assertRaises(StopReview):verify_review_release(r,NOW)

class MeasurementTests(unittest.TestCase):
    def test_six_measurements_separate_actual_diagnostics_from_raw_projections(self):
        ledger=Measurements()
        for label,_,diagnostic in MEASURED_SEQUENCE:
            observation=ledger.accept(sample(label,diagnostic),analytics())
            if not diagnostic:self.assertNotIn('rows_read',observation)
        self.assertEqual(len(ledger.accepted),6);self.assertEqual(ledger.diagnostic_reads,300)
        self.assertEqual(ledger.projected_raw_reads,600)
        with self.assertRaisesRegex(StopReview,'MEASURED_REQUEST_BUDGET_EXHAUSTED'):
            ledger.accept(sample('more'),analytics())
    def test_known_maximum_write_workload_is_not_rejected_by_an_unrealistic_ceiling(self):
        ledger=Measurements()
        ledger.accept(sample('owner_open_diagnostic'),analytics())
        ledger.accept(sample('owner_open_raw',False),analytics())
        ledger.accept({**sample('maximum_save_diagnostic'),'rows_written':2512,'rows_read':1000},analytics())
        ledger.accept({**sample('large_undo_diagnostic'),'rows_written':1012,'rows_read':9130},analytics())
        self.assertEqual(ledger.diagnostic_writes,3525)
    def test_missing_ambiguous_aggregated_or_failed_cpu_does_not_become_a_measurement(self):
        variants=[[],analytics()+analytics(),[{**analytics()[0],'sum':{'requests':2,'errors':0}}],
                  [{**analytics()[0],'sum':{'requests':1,'errors':1}}],
                  [{**analytics()[0],'quantiles':{'cpuTimeP50':float('nan')}}]]
        for rows in variants:
            with self.assertRaises(StopReview):cpu_observation(sample('owner_open_diagnostic'),rows)
    def test_second_resolution_cpu_never_ignores_an_intermediate_invocation(self):
        s=sample('owner_open_diagnostic');s['ended']='2026-10-10T15:00:04.200Z'
        rows=analytics()+[{'dimensions':{'datetime':'2026-10-10T15:00:02Z','status':'success'},'sum':{'requests':1,'errors':0},'quantiles':{'cpuTimeP50':2000}}]
        with self.assertRaisesRegex(StopReview,'CPU_ANALYTICS_MISSING_OR_AMBIGUOUS'):cpu_observation(s,rows)
    def test_excess_reads_missing_metadata_cpu_limit_http_and_order_stop_immediately(self):
        for patch,rows in [({'rows_read':2_430_969},analytics()),({'d1_complete':False},analytics()),
                           ({'rows_read':None},analytics()),({'status':404},analytics()),
                           ({'label':'maximum_save_raw'},analytics()),({},analytics(9000))]:
            ledger=Measurements()
            with self.assertRaises(StopReview):ledger.accept({**sample('owner_open_diagnostic'),**patch},rows)
            self.assertTrue(ledger.stopped)
            with self.assertRaisesRegex(StopReview,'REVIEW_ALREADY_STOPPED'):
                ledger.accept(sample('owner_open_diagnostic'),analytics())
    def test_cleanup_budget_survives_exhausted_work_calls(self):
        budget=CallBudget()
        for _ in range(8):budget.before('http')
        with self.assertRaises(StopReview):budget.before('http')
        for _ in range(40):budget.before('control')
        with self.assertRaises(StopReview):budget.before('control')
        for _ in range(10):budget.before('cleanup')
        with self.assertRaises(StopReview):budget.before('cleanup')

class DraftTests(unittest.TestCase):
    def owner(self):
        return {'id':FIXTURE_RECORD,'revision':7,'list_type':'want_list','deleted_at':None,
                'groups':[{'id':FIXTURE_GROUP,'list_type':'want_list','entries':[
                    {'id':FIXTURE_RECORD+'-item-'+str(n),'group_id':FIXTURE_GROUP,'state':'wanted','actionable':1,'deleted_at':None} for n in range(526)]}]}
    def test_maximum_draft_contains_500_changes_500_distinct_full_length_additions(self):
        request_id='00000000-0000-4000-8000-000000000001'
        result=maximum_payload(self.owner(),request_id)
        self.assertEqual(len(result['changes']),500);self.assertEqual(len(result['additions']),500)
        self.assertEqual(len({a['value'] for a in result['additions']}),500)
        self.assertTrue(all(len(a['value'])==500 for a in result['additions']))
        self.assertEqual(result['revision'],7)
        self.assertEqual(result,maximum_payload(self.owner(),request_id))
    def test_historical_practice_pending_or_deleted_fixture_is_never_selected(self):
        for patch in [{'id':'p0001-l001'},{'id':'owner-record-practice'},{'deleted_at':'deleted'},{'list_type':'have_list'}]:
            with self.assertRaises(StopReview):maximum_payload({**self.owner(),**patch},'00000000-0000-4000-8000-000000000001')
        owner=self.owner();owner['groups'][0]['entries'][0]['state']='pending'
        with self.assertRaises(StopReview):maximum_payload(owner,'00000000-0000-4000-8000-000000000001')

class CleanupTests(unittest.TestCase):
    def callbacks(self,action_failure=False,disable_failure=False,restore_failure=False):
        log=[]
        def call(name,fail=False,value=None):
            def callback():
                log.append(name)
                if fail:raise RuntimeError('private exception must not enter report')
                return value
            return callback
        return log,dict(action=call('enable_and_run',action_failure),disable=call('disable',disable_failure),
                        verify_disabled=call('verify_disabled',value=True),restore=call('restore',restore_failure),
                        remove_key=call('remove_key'),verify_restored=call('verify_restored',value=True),verified=True)
    def test_enable_timeout_and_work_failure_always_trigger_disable_before_restore(self):
        for failure in [False,True]:
            log,callbacks=self.callbacks(action_failure=failure);report=protected_scope(**callbacks)
            self.assertTrue(report['cleanup_complete']);self.assertLess(log.index('disable'),log.index('restore'))
            self.assertNotIn('private',str(report))
    def test_disable_failure_retains_expiring_guard_and_reports_incomplete(self):
        log,callbacks=self.callbacks(disable_failure=True);report=protected_scope(**callbacks)
        self.assertEqual(log.count('disable'),2);self.assertNotIn('restore',log)
        self.assertIn('remove_key',log);self.assertFalse(report['cleanup_complete'])
    def test_restore_failure_still_removes_temporary_key(self):
        log,callbacks=self.callbacks(restore_failure=True);report=protected_scope(**callbacks)
        self.assertIn('remove_key',log);self.assertFalse(report['cleanup_complete'])
    def test_no_verified_resources_means_no_control_calls(self):
        log,callbacks=self.callbacks();callbacks['verified']=False
        with self.assertRaises(StopReview):protected_scope(**callbacks)
        self.assertEqual(log,[])
    def test_interrupt_still_runs_cleanup_and_is_not_swallowed(self):
        log,callbacks=self.callbacks()
        def interrupt():raise KeyboardInterrupt()
        callbacks['action']=interrupt
        with self.assertRaises(KeyboardInterrupt):protected_scope(**callbacks)
        self.assertIn('disable',log);self.assertIn('verify_restored',log)

if __name__=='__main__':unittest.main()
