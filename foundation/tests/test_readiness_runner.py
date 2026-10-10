"""Probe controller/supervisor tests. All transports are fakes; no network."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from multiprocessing import get_context
from foundation.tests.test_minimal_free_plan import NOW,quota,resources
from foundation.staging.minimal_free_release import ROOT,digest,canonical
from foundation.staging.minimal_free_plan import StopReview,verify_resources
from foundation.staging.minimal_free_runner import private_json,iso
from foundation.staging.readiness_runner import ProbeRunner,PROTOCOL,SOURCE,TEMP,watchdog,supervise
from foundation.staging.readiness_evidence import ERROR_1042_SHA256
from foundation.staging.readiness_transport import ProbeTransport

class Clock:
    def __init__(self):self.value=NOW
    def __call__(self):return self.value
    def sleep(self,n):self.value+=timedelta(seconds=n)
    def monotonic(self):return (self.value-NOW).total_seconds()

class Fake:
    def __init__(self,fault=None,results=('1042','1042'),clock=None):
        self.fault=fault;self.results=list(results);self.clock=clock;self.events=[];self.http_offsets=[];self.enabled=False;self.cookie=None;self.key=None
        self.current_modules={'worker.mjs':'old source'};self.bindings=resources()['bindings']
        self.options={'compatibility_date':'2026-10-01','compatibility_flags':[],'logpush':False};self.before=lambda _:None
    def event(self,name,kind='control'):
        self.before(kind);self.events.append(name)
        if self.fault==name:raise StopReview('FAKE_NETWORK_FAILURE')
        if self.fault=='interrupt:'+name:raise KeyboardInterrupt()
    def metadata(self):
        self.event('metadata');r=resources();r.pop('synthetic_fixture_verified');r.pop('reviewed_code_and_schema_verified')
        return {**r,'bindings':self.bindings,'database_bytes':10000000,'release_options':self.options}
    def modules(self,kind='control'):self.event('modules',kind);return self.current_modules
    def publish(self,modules,main,bindings,kind='control',release_options=None):
        self.event('restore' if kind=='cleanup' else 'publish',kind);self.current_modules=modules;self.bindings=bindings
        if self.fault=='ambiguous_upload' and kind!='cleanup':raise StopReview('FAKE_NETWORK_FAILURE')
    def release_metadata(self,r):
        self.event('release_metadata');actual={**r,'bindings':copy.deepcopy(self.bindings)}
        if self.fault=='bad_guard':actual['bindings']=[b for b in actual['bindings'] if b['name']!='FREE_HTTP_REVIEW_KEY']
        if self.fault=='bad_db':actual['bindings'][0]['id']='human-staging'
        return actual
    def endpoint(self,enabled,kind='control'):
        self.event('enable' if enabled else 'disable',kind);self.enabled=enabled
        self.ack_at=self.clock.monotonic() if self.clock else 0
        if self.fault=='ambiguous_enable' and enabled:raise StopReview('FAKE_NETWORK_FAILURE')
        return {'enabled':enabled,'previews_enabled':False}
    def api(self,path,*args,**kw):
        self.event('endpoint_verify');return {'enabled':False if self.fault=='enable_verification' else self.enabled,'previews_enabled':False}
    def disabled(self):self.event('disabled','cleanup');return not self.enabled
    def remove_key(self):self.event('remove_key','cleanup')
    def restored(self,original):self.event('restored','cleanup');return not self.enabled and self.current_modules==original['modules'] and self.bindings==original['bindings'] and not {b['name'] for b in self.bindings}.intersection(TEMP)
    def sql(self,*args,**kwargs):raise AssertionError('SQL forbidden in probe')
    def http(self):
        self.event('http','http');self.http_offsets.append(self.clock.monotonic()-self.ack_at);kind=self.results.pop(0)
        if self.fault=='slow_first':self.clock.sleep(31)
        sample={'status':404,'headers':{},'response_bytes':17,'response_sha256':ERROR_1042_SHA256}
        if kind=='1042':return sample,None
        nonce=next(b['text'] for b in self.bindings if b['name']=='READINESS_PROBE_NONCE')
        if kind=='wrong_nonce':nonce='f'*32
        sample.update(status=200 if kind!='403' else 403,headers={'x-wantlist-readiness':'no-d1-v1','x-wantlist-readiness-nonce':nonce})
        if kind=='unknown':sample['status']=502
        data={'probe':'wantlist-readiness-no-d1-v1','nonce':nonce,'authorized':True}
        sample.update(response_bytes=len(canonical(data).encode()),response_sha256=digest(canonical(data)))
        return sample,data
    def analytics(self,sample):
        self.event('analytics')
        if self.fault=='missing_cpu':return []
        return [{'dimensions':{'datetime':sample['started'],'status':'success'},'sum':{'requests':1,'errors':0},'quantiles':{'cpuTimeP50':9000 if self.fault=='cpu' else 1000}}]

class ProbeTests(unittest.TestCase):
    def scenario(self,fault=None,results=('1042','1042'),authpatch=None,qpatch=None,supervisor=None,browser=None):
        (ROOT/'work').mkdir(exist_ok=True);directory=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(directory.cleanup)
        c=Clock();t=Fake(fault,results,c);q=quota();q.update(qpatch or {})
        manifest={'probe_source_sha256':digest(SOURCE.read_bytes()),'original_module_sha256':{'worker.mjs':digest('old source')},'original_options_sha256':digest(canonical(t.options))}
        auth={'protocol':PROTOCOL,'worker':resources()['worker_name'],'database':resources()['database_id'],'expires_at_utc':iso(NOW+timedelta(minutes=15)),'probe_source_sha256':manifest['probe_source_sha256']}
        auth.update({k:True for k in ('owner_authorized','allow_probe_release','allow_enable','allow_two_gets','allow_cleanup','allow_optional_browser')});auth.update(authpatch or {})
        r=ProbeRunner(t,auth,lambda:q,directory.name,supervisor or (lambda _:lambda:True),c,c.sleep,c.monotonic,manifest=manifest)
        if browser:r.on_browser=lambda event:browser(r,event)
        t.before=r.before
        return t,r,r.run()
    def test_both_1042_requests_are_fixed_spaced_and_complete_cleanup(self):
        t,r,result=self.scenario();self.assertEqual(t.http_offsets,[5,30]);self.assertTrue(result['probe_complete']);self.assertFalse(result['route_established']);self.assertTrue(result['cleanup']['complete']);self.assertEqual(result['calls']['http'],2);self.assertEqual(result['sql_calls'],0)
        self.assertLessEqual(result['calls']['control'],40);self.assertLessEqual(result['calls']['cleanup'],10)
        private=(r.session/'report.json').read_text()+(r.session/'session.json').read_text();self.assertNotIn(t.key,private);self.assertNotIn('old source',private)
    def test_first_marker_skips_second_request_and_measures_cpu(self):
        t,r,result=self.scenario(results=('marker',));self.assertEqual(t.http_offsets,[5]);self.assertTrue(result['route_established']);self.assertEqual(result['samples'][0]['cpu_ms'],1)
    def test_second_marker_records_transient_recovery(self):
        t,r,result=self.scenario(results=('1042','marker'));self.assertEqual(t.http_offsets,[5,30]);self.assertTrue(result['route_established'])
    def test_unknown_status_or_nonce_or_auth_failure_never_retries(self):
        for kind in ('unknown','wrong_nonce','403'):
            with self.subTest(kind=kind):
                t,r,result=self.scenario(results=(kind,));self.assertEqual(t.http_offsets,[5]);self.assertEqual(result['stop_code'],'PROBE_RESPONSE_UNEXPECTED');self.assertTrue(result['cleanup']['complete'])
    def test_quota_and_authorization_stop_before_any_transport(self):
        for a,q in [({'owner_authorized':False},{}),({}, {'observed_at_utc':iso(NOW-timedelta(minutes=6))}),({}, {'rows_read_upper_bound':2_000_000}),({}, {'worker_requests_upper_bound':None})]:
            with self.subTest(a=a,q=q):
                t,r,result=self.scenario(authpatch=a,qpatch=q);self.assertEqual(t.events,[]);self.assertFalse(result['probe_complete'])
    def test_supervisor_must_handshake_before_publish(self):
        t,r,result=self.scenario(supervisor=lambda _:lambda:False);self.assertNotIn('publish',t.events);self.assertNotIn('enable',t.events);self.assertTrue(result['cleanup']['not_required_no_publication'])
    def test_supervisor_death_stops_before_next_operation(self):
        healthy=[True,False]
        t,r,result=self.scenario(supervisor=lambda _:lambda:healthy.pop(0) if healthy else False);self.assertNotIn('publish',t.events);self.assertTrue(result['cleanup']['complete'])
    def test_upload_timeout_and_interruptions_cleanup_without_http(self):
        for fault in ('publish','ambiguous_upload','interrupt:publish','enable','ambiguous_enable','interrupt:enable','enable_verification'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertNotIn('http',t.events);self.assertTrue(result['cleanup']['complete'],result)
    def test_wrong_guard_or_binding_never_enables(self):
        for fault in ('bad_guard','bad_db'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertNotIn('enable',t.events);self.assertTrue(result['cleanup']['complete'])
    def test_response_interruption_or_network_failure_never_replays(self):
        for fault in ('http','interrupt:http'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertEqual(t.events.count('http'),1);self.assertTrue(result['cleanup']['complete'])
    def test_failed_shutdown_keeps_guard_never_restores_original(self):
        t,r,result=self.scenario('disable');self.assertNotIn('restore',t.events);self.assertEqual(t.events.count('disable'),2);self.assertFalse(result['cleanup']['complete']);self.assertEqual(t.current_modules,{'worker.mjs':SOURCE.read_text()})
    def test_failed_restoration_or_key_removal_never_claims_success(self):
        for fault in ('restore','remove_key'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertFalse(result['cleanup']['complete']);self.assertTrue(result['cleanup']['disabled_verified'])
    def test_cpu_threshold_or_missing_cpu_stops_with_cleanup(self):
        for fault in ('cpu','missing_cpu'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault,results=('marker',));self.assertFalse(result['probe_complete']);self.assertEqual(t.events.count('http'),1);self.assertTrue(result['cleanup']['complete'])
    def test_slow_first_response_does_not_replay_missed_second_slot(self):
        t,r,result=self.scenario('slow_first');self.assertEqual(t.http_offsets,[5]);self.assertEqual(result['stop_code'],'PROBE_SCHEDULE_MISSED');self.assertTrue(result['cleanup']['complete'])
    def test_browser_comparison_body_is_bounded_and_nonce_checked(self):
        def result(r,event):private_json(r.session/'browser-result.json',{'probe':'wantlist-readiness-no-d1-v1','nonce':event['expected_public_nonce'],'authorized':False})
        t,r,report=self.scenario(browser=result);self.assertTrue(report['browser_result']['matching_public_probe_body_reported_by_owner']);self.assertEqual(t.http_offsets,[5,30]);self.assertTrue(report['cleanup']['complete'])
    def test_optional_browser_timeout_and_skip_are_bounded(self):
        for callback in (lambda *_:None,lambda r,_:private_json(r.session/'browser-result.json',{'skip':True})):
            t,r,report=self.scenario(browser=callback);self.assertIn(report['browser_result'],('owner_skipped','not_received_before_deadline'));self.assertLessEqual(r.clock()-NOW,timedelta(seconds=90));self.assertTrue(report['cleanup']['complete'])
    def test_expired_quota_during_wait_stops_and_cleanup_still_runs(self):
        q={'observed_at_utc':iso(NOW-timedelta(seconds=280))}
        t,r,result=self.scenario(qpatch=q);self.assertEqual(t.http_offsets,[5]);self.assertEqual(result['stop_code'],'STALE_ACCOUNT_WIDE_QUOTA');self.assertTrue(result['cleanup']['complete'])
    def test_watchdog_takeover_stops_parent_and_preserves_completion(self):
        t,r,result=self.scenario();state=json.loads((r.session/'session.json').read_text());state.update(cleanup_in_progress=True,done=False);private_json(r.session/'session.json',state)
        with self.assertRaisesRegex(StopReview,'WATCHDOG_TAKEOVER'):r.before('control')
        state.update(watchdog_cleanup={'complete':True},done=True);private_json(r.session/'session.json',state);r.checkpoint()
        self.assertTrue(json.loads((r.session/'session.json').read_text())['done']);self.assertTrue(r.report['cleanup']['complete'])
    def test_all_four_temporary_bindings_absent_after_cleanup(self):
        t,r,result=self.scenario();self.assertFalse({b['name'] for b in t.bindings}.intersection(TEMP));self.assertEqual(len(TEMP),4)
    def test_probe_scope_does_not_require_or_claim_application_schema(self):
        r=resources();r.pop('reviewed_code_and_schema_verified');r.pop('synthetic_fixture_verified');self.assertTrue(verify_resources(r,require_application=False))
        with self.assertRaises(StopReview):verify_resources(r)

def watchdog_case(self,patch_state=None,alive=lambda _:False,independent=False):
    t,r,result=self.scenario();r.state.update(done=False,armed=True);r.checkpoint()
    state=json.loads((r.session/'session.json').read_text());state.update(patch_state or {});private_json(r.session/'session.json',state)
    def factory(before):t.before=before;return t
    if independent:
        proc=get_context('fork').Process(target=watchdog,args=(r.session,),kwargs={'transport_factory':factory,'clock':r.clock,'alive':alive,'sleep':lambda _:None});proc.start();proc.join(3)
        if proc.is_alive():proc.terminate();proc.join();self.fail('watchdog did not terminate')
        self.assertEqual(proc.exitcode,0)
    else:watchdog(r.session,transport_factory=factory,clock=r.clock,alive=alive,sleep=lambda _:self.fail('watchdog should act immediately'))
    state=json.loads((r.session/'session.json').read_text());self.assertTrue(state['done']);self.assertTrue(state['watchdog_cleanup']['complete']);self.assertLessEqual(state['cleanup_calls'],10)

class WatchdogTests(unittest.TestCase):
    scenario=ProbeTests.scenario
    def test_parent_death(self):watchdog_case(self,independent=True)
    def test_expiry(self):watchdog_case(self,{'expires':iso(NOW)},alive=lambda _:True)
    def test_stalled_heartbeat(self):watchdog_case(self,{'heartbeat':iso(NOW-timedelta(seconds=91))},alive=lambda _:True)
    def test_invalid_checkpoint(self):
        t,r,result=self.scenario();r.state.update(done=False,cleanup_authorized=False);r.checkpoint()
        with self.assertRaisesRegex(StopReview,'AUTHORIZATION_MISSING'):watchdog(r.session,transport_factory=lambda _:self.fail('no construction'))
    def test_supervisor_handshake_health(self):
        t,r,result=self.scenario()
        class Child:
            pid=4242
            def poll(self):return None
        child=Child()
        def spawn(*args,**kwargs):
            self.assertTrue(kwargs['start_new_session']);private_json(r.session/'watchdog-ready.json',{'pid':child.pid,'parent_pid':os.getpid(),'heartbeat':iso(NOW),'protocol':PROTOCOL});return child
        with patch('foundation.staging.readiness_runner.subprocess.Popen',side_effect=spawn),patch('foundation.staging.readiness_runner.now',return_value=NOW):
            healthy=supervise(r.session);self.assertTrue(healthy());child.poll=lambda:1;self.assertFalse(healthy())

class TransportTests(unittest.TestCase):
    def test_sql_and_application_routes_rejected_before_dispatch(self):
        t=ProbeTransport.__new__(ProbeTransport);t.cookie=None;t.request=lambda *a,**kw:self.fail('dispatch')
        for action in (lambda:t.sql('SELECT 1'),lambda:t.api('/d1/database/anything/query','POST',{}),lambda:t.http('/owner/record?id=anything'),lambda:t.http(body={}),lambda:t.http(diagnostic=True)):
            with self.assertRaises(StopReview):action()
    def test_no_cookie_or_overlarge_body(self):
        t=ProbeTransport.__new__(ProbeTransport);t.cookie='forbidden';t.request=lambda *a,**kw:self.fail('dispatch')
        with self.assertRaises(StopReview):t.http()
    def test_parent_dispatch_waits_for_cleanup_lock_and_then_fails_closed(self):
        import threading
        from foundation.staging.minimal_free_runner import cleanup_lock
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
            held=threading.Event();release=threading.Event();called=[];errors=[]
            def child_cleanup():
                with cleanup_lock(directory):held.set();release.wait(2)
            child=threading.Thread(target=child_cleanup);child.start();self.assertTrue(held.wait(1))
            t=ProbeTransport.__new__(ProbeTransport);t.operation_lock=directory
            def before(kind):called.append(kind);raise StopReview('PROBE_WATCHDOG_TAKEOVER')
            t.before=before
            def parent_dispatch():
                try:t.request('https://unused.invalid')
                except StopReview as e:errors.append(str(e))
            parent=threading.Thread(target=parent_dispatch);parent.start();parent.join(.05);self.assertTrue(parent.is_alive());self.assertEqual(called,[])
            release.set();parent.join(2);child.join(2);self.assertFalse(parent.is_alive());self.assertEqual(errors,['PROBE_WATCHDOG_TAKEOVER'])
    def test_actual_restoration_check_rejects_leftover_public_nonce(self):
        from foundation.staging.readiness_runner import TEMP
        t=ProbeTransport.__new__(ProbeTransport);original={'modules':{'worker.mjs':'original'},'options':{'compatibility_date':'2026-10-01'},'bindings':resources()['bindings']}
        settings={**original['options'],'bindings':copy.deepcopy(original['bindings'])}
        t.api=lambda *a,**kw:settings;t.disabled=lambda:True;t.modules=lambda **kw:original['modules']
        self.assertTrue(t.restored(original));settings['bindings'].append({'name':'READINESS_PROBE_NONCE','type':'plain_text','text':'a'*32});self.assertFalse(t.restored(original))
    def test_diagnostic_response_cap_selected_before_request(self):
        t=ProbeTransport.__new__(ProbeTransport)
        with patch('foundation.staging.minimal_free_transport.LiveTransport.request',return_value=(200,{},b'{}')):
            t.request('unused',kind='http');self.assertEqual(t.response_limit,65536);t.request('unused',kind='control');self.assertEqual(t.response_limit,4_000_000)

if __name__=='__main__':unittest.main()
