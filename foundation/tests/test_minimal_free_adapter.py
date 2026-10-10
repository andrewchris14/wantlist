"""No sockets/credentials: exercise the real runner using a faulting transport."""
import copy, io, json, sqlite3, tempfile, unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from foundation.tests.test_minimal_free_plan import NOW, quota, resources
from foundation.staging.minimal_free_plan import StopReview, FIXTURE_RECORD as R, FIXTURE_GROUP as G, STAGING_DATABASE, verify_quota
from foundation.staging.minimal_free_release import build, validate, canonical, digest, ROOT
from foundation.staging.minimal_free_runner import Runner, authorize, watchdog, private_json, cleanup_operations
from foundation.staging.minimal_free_transport import LiveTransport, NoRedirect
from foundation.staging import minimal_free_sql as S

class Clock:
    def __init__(self):self.value=NOW
    def __call__(self):return self.value
    def sleep(self,n):self.value+=timedelta(seconds=n)

def owner():
    entries=[{'id':R+'-item-'+str(n),'group_id':G,'state':'wanted','actionable':1,'deleted_at':None} for n in range(526)]
    entries += [{'id':R+'-removed-'+str(n),'group_id':G,'state':'wanted','actionable':1,'deleted_at':'old'} for n in range(1503)]
    return {'id':R,'list_type':'want_list','deleted_at':None,'revision':1,'groups':[{'id':G,'list_type':'want_list','entries':entries}]}

class Fake:
    def __init__(self,package,fault=None):
        self.package=package;self.fault=fault;self.events=[];self.before=lambda k:None
        self.bindings=resources()['bindings'];self.enabled=False;self.live={'worker.mjs':'original'};self.rev=1;self.removed=1503;self.receipts={};self.cookie=None;self.key=None;self.actions=0;self.current_label=None
    def event(self,name,kind='control'):
        self.before(kind);self.events.append(name)
        if self.fault==name:raise StopReview('NETWORK_RESULT_UNKNOWN')
        if self.fault=='interrupt:'+name:raise KeyboardInterrupt()
    def metadata(self):self.event('metadata');return {**resources(),'bindings':self.bindings,'release_options':{'compatibility_date':'2026-10-01'},'database_bytes':10000000}
    def modules(self,kind='control'):self.event('modules',kind);return self.live
    def release_metadata(self,r):self.event('release_metadata');return {**r,'bindings':self.bindings}
    def sql(self,sql,params=()):
        self.event('sql')
        if sql==S.SCHEMA:
            defs=self.package['schema']['legacy'] if self.fault in ('migration','migration_unapproved') else self.package['schema']['expected']
            rows=[{'name':n,'sql':v} for n,v in defs.items()]
            if self.fault=='bad_schema':rows[0]['sql']='bogus'
        elif sql==S.SCAN:rows=[{'n':1001 if self.fault=='scan' else 3}]
        elif sql==S.FIXTURE:
            rows=[{'revision':1,'public_revision':1,'browse_revision':1,'list_type':'want_list','deleted_at':None,'marker':'synthetic-disposable-http-review','groups':1,'total':2029,'active':526,'removed':1503}]
            if self.fault=='fixture':rows[0]['marker']='human'
        elif sql==S.STATE:rows=[{'content_json':'{"id":"synthetic-only","notes":["old"]}','original_items':'original-synthetic-rows','original_groups':'group','provenance':'provenance','public_active':526,'public_notes':'["old"]','browse_notes':'["old"]','active':526,'removed':self.removed,'revision':self.rev,'public_revision':self.rev,'browse_revision':self.rev}]
        elif sql==S.HISTORY:rows=[{'id':'history-'+str(params[1])}]
        elif sql==S.RECEIPT:rows=[] if self.fault=='missing_receipt' else [self.receipts[params[0]]] if params[0] in self.receipts else []
        elif sql==self.package['schema']['migration']:raise StopReview('D1_RESULT_UNKNOWN')
        else:raise AssertionError('unexpected SQL')
        if self.fault=='unknown_sql_cost':return [{'results':rows,'meta':{}}]
        return [{'results':rows,'meta':{'rows_read':10,'rows_written':0}}]
    def publish(self,modules,main,bindings,kind='control',release_options=None):
        self.event('restore' if kind=='cleanup' else 'publish',kind);self.live=modules;self.bindings=bindings
        if self.fault=='publish_ambiguous' and kind!='cleanup':raise StopReview('NETWORK_RESULT_UNKNOWN')
    def endpoint(self,enabled,kind='control'):
        self.event('enable' if enabled else 'disable',kind)
        if self.fault=='shutdown' and not enabled:raise StopReview('NETWORK_RESULT_UNKNOWN')
        self.enabled=enabled
    def disabled(self):self.event('disabled','cleanup');return not self.enabled
    def remove_key(self):self.event('remove_key','cleanup')
    def restored(self,original):self.event('restored','cleanup');return self.live==original['modules'] and self.bindings==original['bindings'] and not self.enabled
    def http(self,path,body=None,diagnostic=False):
        if path.startswith('/public'):label='index';data={'records':[],'next':None}
        elif 'login' in path:label='login';self.cookie='RAM-cookie';data={'signed_in':True}
        elif 'owner' in path:label='owner';data=owner()
        else:
            label='save' if body['op']=='edit_session' else 'undo'
            self.event(label,'http');self.actions+=1;self.rev+=1
            if label=='undo':self.removed+=500
            data={'saved':True,'record_id':R,'revision':self.rev}
            self.receipts[body['request_id']]={'record_id':R,'result_json':json.dumps(data),'request_sha256':digest(json.dumps(body,separators=(',',':'),ensure_ascii=False))}
            if self.fault in ('lost_'+label,'interrupt_after_'+label,'missing_receipt') and (label=='save' or self.fault.endswith('undo')):
                self.fault_used=True
                if not getattr(self,'already_lost',False):
                    self.already_lost=True
                    if self.fault.startswith('interrupt'):raise KeyboardInterrupt()
                    raise StopReview('NETWORK_RESULT_UNKNOWN')
            if (self.fault=='lost_raw_save' and self.actions==3) or (self.fault=='lost_raw_undo' and self.actions==4):raise StopReview('NETWORK_RESULT_UNKNOWN')
            self.current_label=label
            return {'status':200,'diagnostic':diagnostic,'d1_complete':True,'rows_read':100,'rows_written':100},data
        self.event(label,'http');self.current_label=label
        sample={'status':200,'diagnostic':diagnostic,'d1_complete':True,'rows_read':100,'rows_written':1}
        if self.fault=='cost' and label=='owner':sample['rows_read']=12001
        if self.fault=='missing_diagnostics' and label=='owner':sample['d1_complete']=False
        return sample,data
    def analytics(self,sample):
        self.event('analytics')
        if self.fault=='missing_cpu':return []
        n=2 if self.fault=='ambiguous_cpu' else 1
        cpu=9000 if self.fault=='cpu' and self.current_label=='save' else 1000
        return [{'dimensions':{'datetime':sample['started'],'status':'success'},'sum':{'requests':n,'errors':0},'quantiles':{'cpuTimeP50':cpu}}]

class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.assets.cleanup)
        directory=Path(cls.assets.name);(directory/'assets').mkdir()
        (directory/'index.html').write_text('<script src="/assets/local.js"></script><link href="/assets/local.css">')
        (directory/'assets/local.js').write_text('/* local test asset */');(directory/'assets/local.css').write_text('body{}')
        cls.package,cls.manifest=build(directory)
    def scenario(self,fault=None,authpatch=None,qpatch=None):
        clock=Clock();q=quota();q.update(qpatch or {})
        auth={'protocol':'minimal-free-six-v1','worker':resources()['worker_name'],'database':resources()['database_id'],'restore_main_module':'worker.mjs','expires_at_utc':(NOW+timedelta(minutes=15)).isoformat(),'release_sha256':validate(self.package)}
        auth.update({k:True for k in ('owner_authorized','allow_release','allow_schema_verification','allow_fixture_verification','allow_test','allow_cleanup')});auth.update(authpatch or {})
        (ROOT/'work').mkdir(exist_ok=True);directory=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(directory.cleanup)
        fake=Fake(self.package,fault);runner=Runner(fake,self.package,auth,lambda:q,Path(directory.name),clock,clock.sleep);fake.before=runner.before
        result=runner.run();return fake,runner,result
    def test_full_sequence_has_exactly_eight_http_six_measurements_and_cleanup(self):
        t,r,result=self.scenario();self.assertTrue(result['test_complete'],result);self.assertEqual(result['calls']['http'],8);self.assertEqual(len(result['accepted']),6);self.assertEqual(t.actions,4);self.assertTrue(result['cleanup']['complete']);self.assertEqual(result['last_verified_restoration']['removed'],2503)
        self.assertFalse(result['final_account_reconciliation_complete']);self.assertLessEqual(result['calls']['cleanup'],10)
        report=(r.session/'report.json').read_text();self.assertNotIn('RAM-cookie',report);self.assertNotIn('original-synthetic-rows',report);self.assertNotIn('synthetic-only',report)
    def test_authorization_and_quota_rejected_before_transport(self):
        for patch,qpatch in [({'owner_authorized':False},{}),({}, {'rows_read_upper_bound':2_000_000}),({}, {'worker_requests_upper_bound':None}),({}, {'workers_free_confirmed':False})]:
            with self.subTest(patch=patch,qpatch=qpatch):
                t,r,result=self.scenario(authpatch=patch,qpatch=qpatch);self.assertEqual(t.events,[]);self.assertFalse(result['test_complete'])
    def test_schema_fixture_and_scan_failure_never_publish(self):
        for fault in ('bad_schema','scan','fixture','unknown_sql_cost','migration_unapproved'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertNotIn('publish',t.events);self.assertNotIn('enable',t.events)
    def test_failed_migration_is_not_replayed_or_claimed_success(self):
        t,r,result=self.scenario('migration',{'allow_performance_migration':True});self.assertNotIn('publish',t.events);self.assertTrue(r.sql_unknown);self.assertFalse(result['test_complete'])
    def test_enable_interruption_and_ambiguous_publish_both_cleanup(self):
        for fault in ('interrupt:enable','enable','publish_ambiguous','interrupt:publish'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertTrue(result['cleanup']['complete'],result);self.assertFalse(t.enabled)
    def test_lost_save_response_is_resolved_then_one_undo_never_save_replay(self):
        for fault in ('lost_save','interrupt_after_save'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertEqual(t.events.count('save'),1);self.assertEqual(t.events.count('undo'),1);self.assertIsNone(r.pending);self.assertTrue(result['cleanup']['complete']);self.assertFalse(result['test_complete'])
    def test_lost_undo_response_resolves_receipt_without_replay(self):
        for fault in ('lost_undo','interrupt_after_undo'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertEqual(t.events.count('undo'),1);self.assertIsNone(r.pending);self.assertTrue(result['cleanup']['complete'])
    def test_lost_raw_save_and_undo_resolve_without_exceeding_eight_calls(self):
        for fault in ('lost_raw_save','lost_raw_undo'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertEqual(t.events.count('save'),2);self.assertEqual(t.events.count('undo'),2);self.assertIsNone(r.pending);self.assertTrue(result['cleanup']['complete']);self.assertLessEqual(result['calls']['http'],8)
    def test_stale_evidence_stops_next_dispatch_but_cleanup_has_separate_budget(self):
        t,r,result=self.scenario();r.clock.sleep(301)
        with self.assertRaisesRegex(StopReview,'STALE_ACCOUNT_WIDE_QUOTA'):r.before('control')
        r.calls.counts['control']=40;r.before('cleanup');self.assertLessEqual(r.calls.counts['cleanup'],10)
    def test_watchdog_expiry_and_stalled_heartbeat(self):
        for patch in ({'expires':NOW.isoformat()},{'heartbeat':(NOW-timedelta(seconds=91)).isoformat()}):
            with self.subTest(patch=patch):
                t,r,result=self.scenario();r.state.update(done=False,armed=True);r.checkpoint()
                state=json.loads((r.session/'session.json').read_text());state.update(patch);private_json(r.session/'session.json',state)
                def factory(before):t.before=before;return t
                watchdog(r.session,transport_factory=factory,clock=r.clock,alive=lambda _:True,sleep=lambda _:self.fail('watchdog should act immediately'))
                self.assertTrue(json.loads((r.session/'session.json').read_text())['watchdog_cleanup']['complete'])
    def test_absent_ambiguous_receipt_stops_with_owner_review_needed(self):
        t,r,result=self.scenario('missing_receipt');self.assertEqual(t.events.count('save'),1);self.assertNotIn('undo',t.events);self.assertTrue(result['rollback_incomplete']);self.assertTrue(result['cleanup']['complete'])
    def test_cpu_stop_rolls_back_save_and_ends_sequence(self):
        t,r,result=self.scenario('cpu');self.assertEqual(result['stop_code'],'CPU_SAFETY_STOP');self.assertEqual(t.actions,2);self.assertTrue(result['cleanup']['complete'])
    def test_missing_ambiguous_cpu_or_diagnostics_never_advances(self):
        for fault in ('missing_cpu','ambiguous_cpu','missing_diagnostics','cost'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertNotIn('save',t.events);self.assertFalse(result['test_complete']);self.assertTrue(result['cleanup']['complete'])
    def test_failed_shutdown_retains_guard_never_restores_unguarded_worker(self):
        t,r,result=self.scenario('shutdown');self.assertFalse(result['cleanup']['complete']);self.assertFalse(result['cleanup']['disabled_verified']);self.assertNotIn('restore',t.events);self.assertEqual(t.live,self.package['modules']);self.assertEqual(t.events.count('disable'),2)
    def test_failed_restore_or_key_removal_is_not_success(self):
        for fault in ('restore','remove_key'):
            with self.subTest(fault=fault):
                t,r,result=self.scenario(fault);self.assertFalse(result['cleanup']['complete']);self.assertTrue(result['cleanup']['disabled_verified'])
    def test_watchdog_parent_death_only_shutdown_no_sql_or_http(self):
        t,r,result=self.scenario('enable');r.state.update(done=False,armed=True);r.pending={'kind':'save'};r.checkpoint();before_len=len(t.events)
        def factory(before):t.before=before;return t
        watchdog(r.session,transport_factory=factory,clock=r.clock,sleep=r.sleep,alive=lambda pid:False)
        state=json.loads((r.session/'session.json').read_text());self.assertTrue(state['done']);self.assertTrue(state['watchdog_cleanup']['complete']);self.assertTrue(state['rollback_requires_owner_review']);self.assertNotIn('sql',t.events[before_len:])
    def test_watchdog_rejects_unapproved_checkpoint_before_transport(self):
        t,r,result=self.scenario();r.state.update(done=False,armed=True,cleanup_authorized=False);r.checkpoint()
        with self.assertRaisesRegex(StopReview,'WATCHDOG_AUTHORIZATION_MISSING'):watchdog(r.session,transport_factory=lambda before:self.fail('transport constructed'),clock=r.clock,alive=lambda _:False)
    def test_release_reproducible_and_closure_complete(self):
        p,m=build(self.assets.name);self.assertEqual(validate(p),self.manifest['package_sha256']);self.assertLess(m['module_bytes'],3_000_000);self.assertEqual(len(p['modules']),14);self.assertIn('editor-assets.js',p['modules']);self.assertIn('/assets/local.js',p['modules']['editor-assets.js'])
        broken=copy.deepcopy(p);del broken['modules']['owner.js']
        with self.assertRaisesRegex(ValueError,'Missing imported module'):validate(broken)
        self.assertNotEqual(p['schema']['expected'],p['schema']['legacy'])
    def test_bootstrap_bound_exception_preserves_headroom_and_other_gates(self):
        q=quota();q['migration_scan_bound_confirmed']=False;verify_quota(q,NOW,require_migration_bound=False)
        with self.assertRaisesRegex(StopReview,'MIGRATION_SCAN_BOUND'):verify_quota(q,NOW)
        q['rows_read_upper_bound']=1_900_001
        with self.assertRaisesRegex(StopReview,'HEADROOM'):verify_quota(q,NOW,require_migration_bound=False)

class VerificationSqlTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;self.addCleanup(self.db.close)
        for p in sorted((ROOT/'foundation/migrations').glob('*.sql')):self.db.executescript(p.read_text())
        for name in ('categories.sql','schema.sql','public-index.sql','phase3c6-performance.sql'):self.db.executescript((ROOT/'foundation/staging'/name).read_text())
        content={'id':R,'creation_origin':'synthetic-disposable-http-review','notes':['old'],'list_type':'want_list'}
        self.db.execute('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)',(R,'want_list',json.dumps(content),'synthetic','synthetic'))
        self.db.execute('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)',(G,R,'primary',0,'want_list','{}','["items"]'))
        self.ids=[]
        for n in range(2029):
            id=R+'-item-'+str(n);self.ids.append(id)
            self.db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,?)',(id,G,'items',n,'S'*500,'wanted',None if n<526 else 'old'))
        projection={**content,'revision':1,'groups':[{'list_type':'want_list','entries':[{'state':'wanted','value':'S'} for _ in range(526)]}]}
        self.db.execute('INSERT INTO public_records VALUES(?,1,?,0,?)',(R,'synthetic',json.dumps(projection)))
    def test_fixed_fixture_and_state_sql_actual_schema_large_rows(self):
        f=dict(self.db.execute(S.FIXTURE,S.FIXTURE_PARAMS).fetchone());self.assertEqual((f['active'],f['removed'],f['total']),(526,1503,2029))
        st=dict(self.db.execute(S.STATE,[G,json.dumps(self.ids),G,R]).fetchone());self.assertEqual(len(json.loads(st['original_items'])),2029);self.assertEqual(st['public_active'],526);self.assertEqual(st['public_notes'],st['browse_notes']);self.assertLess(len(st['original_items'].encode()),2_000_000)
        plan=' '.join(str(tuple(row)) for row in self.db.execute('EXPLAIN QUERY PLAN '+S.STATE,[G,json.dumps(self.ids),G,R]));self.assertIn('sqlite_autoindex_items_1',plan)
    def test_fixture_saturates_above_baseline(self):
        for n in range(2029,2100):self.db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)',(R+'-extra-'+str(n),G,'items',n,'extra','wanted'))
        self.assertEqual(self.db.execute(S.FIXTURE,S.FIXTURE_PARAMS).fetchone()['total'],2030)
    def test_history_scan_saturates_and_migration_sql_restores_known_definitions(self):
        for n in range(1002):self.db.execute('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',(str(n),R,'owner','edit_session','{}','{}','synthetic'))
        self.assertEqual(self.db.execute(S.SCAN).fetchone()['n'],1001)
        from foundation.staging.minimal_free_release import schema_manifest,normalize_sql
        expected=schema_manifest()['expected'];observed={r['name']:normalize_sql(r['sql']) for r in self.db.execute(S.SCHEMA)};self.assertEqual(observed,expected)

class TransportTests(unittest.TestCase):
    def transport(self):
        t=LiveTransport.__new__(LiveTransport);t.before=lambda k:None;t.api_root='https://api.cloudflare.com/client/v4/accounts/dummy';t.token='never-network';t.cookie=None;t.key=None;return t
    def test_target_allowlists_block_staging_and_arbitrary_worker_routes(self):
        t=self.transport();t.request=lambda *a,**k:self.fail('dispatch')
        for path,method in [('/d1/database/'+STAGING_DATABASE+'/query','POST'),('/workers/scripts/production','PUT')]:
            with self.assertRaisesRegex(StopReview,'TARGET_FORBIDDEN'):t.api(path,method)
        with self.assertRaisesRegex(StopReview,'HTTP_TARGET_FORBIDDEN'):t.http('/owner/record?id=human')
    def test_redirect_never_follows(self):
        with self.assertRaisesRegex(StopReview,'REDIRECT_FORBIDDEN'):NoRedirect().redirect_request(None,None,None,None,None,None)
    def test_delete_404_only_is_idempotent(self):
        t=self.transport();t.request=lambda *a,**k:(404,{},b'')
        self.assertEqual(t.remove_key(),{})
        with self.assertRaisesRegex(StopReview,'API_HTTP_404'):t.api('/workers/scripts/'+resources()['worker_name']+'/settings')
    def test_pagination_and_failed_api_fail_closed(self):
        t=self.transport()
        for body in ({'success':True,'result':[],'result_info':{'total_pages':2}},{'success':False,'result':[]}):
            t.request=lambda *a,**k:(200,{},json.dumps(body).encode())
            with self.assertRaises(StopReview):t.api('/zones?per_page=50',global_path=True)
    def test_socket_error_is_redacted(self):
        t=self.transport()
        class Opener:
            def open(self,*a,**k):raise OSError('private credential text')
        t.opener=Opener()
        with self.assertRaisesRegex(StopReview,'^NETWORK_RESULT_UNKNOWN$'):t.request('https://not-used.invalid')
    def test_response_size_and_overall_deadline_bounded(self):
        t=self.transport()
        class Response:
            status=200;headers={}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read1(self,n):return b'X'*65536
        class Opener:
            def open(self,*a,**k):assert k['timeout']==10;return Response()
        t.opener=Opener()
        with self.assertRaisesRegex(StopReview,'RESPONSE_SIZE_STOP'):t.request('https://not-used.invalid')
        with patch('foundation.staging.minimal_free_transport.time.monotonic',side_effect=[0,31]),self.assertRaisesRegex(StopReview,'HTTP_TOTAL_TIMEOUT'):t.request('https://not-used.invalid')

if __name__=='__main__':unittest.main()
