"""Minimal live adapter. --run needs separately granted owner authorization.

No network on import or --help. Default is refusal. Only fixed disposable targets
are supported. Private session files hold code rollback material and identifiers,
never D1 contents, cookie, PIN or ephemeral header key.
"""
import argparse, fcntl, json, os, secrets, signal, subprocess, sys, time, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .minimal_free_plan import (WORKER,DATABASE,ORIGIN,FIXTURE_RECORD,FIXTURE_GROUP,MEASURED_SEQUENCE,
    StopReview,CallBudget,Measurements,verify_quota,verify_resources,verify_review_release,cpu_observation,maximum_payload,utc)
from .minimal_free_release import ROOT,canonical,digest,normalize_sql,validate
from . import minimal_free_sql as SQL

TEMP_NAMES={'MINIMAL_FREE_REVIEW','MINIMAL_FREE_REVIEW_UNTIL','FREE_HTTP_REVIEW_KEY'}
def now():return datetime.now(timezone.utc)
def iso(value):return value.isoformat(timespec='milliseconds').replace('+00:00','Z')
def private_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix('.tmp');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)
def work_path(value):
    p=(ROOT/value).resolve()
    if not p.is_relative_to(ROOT/'work'):raise StopReview('PRIVATE_PATH_MUST_BE_WORK')
    return p

def authorize(auth,package,clock):
    for name in ('owner_authorized','allow_release','allow_schema_verification','allow_fixture_verification','allow_test','allow_cleanup'):
        if auth.get(name) is not True:raise StopReview('OWNER_REMOTE_AUTHORIZATION_REQUIRED')
    if auth.get('protocol')!='minimal-free-six-v1' or auth.get('worker')!=WORKER or auth.get('database')!=DATABASE:
        raise StopReview('AUTHORIZATION_TARGET_MISMATCH')
    if auth.get('restore_main_module')!='worker.mjs' or utc(auth.get('expires_at_utc'))<=clock:
        raise StopReview('AUTHORIZATION_INVALID')
    if auth.get('release_sha256')!=validate(package):raise StopReview('AUTHORIZED_RELEASE_MISMATCH')

class Runner:
    def __init__(self,transport,package,auth,quota_provider,session,clock=now,sleep=time.sleep,supervise=None):
        self.t=transport;self.package=package;self.auth=auth;self.quota_provider=quota_provider
        self.session=Path(session);self.clock=clock;self.sleep=sleep;self.supervise=supervise
        self.calls=CallBudget();self.measurements=Measurements();self.original=None;self.pending=None;self.baseline=None
        self.report={'protocol':'minimal-free-six-v1','worker':WORKER,'database':DATABASE,'release_sha256':digest(canonical(package)),
                     'samples':[],'http_measured_usage':{'reads':0,'writes':0},'raw_dispatch_projection':{'reads':0,'writes':0},'ambiguous_read_reserve':0,'ambiguous_write_reserve':0,'sql_usage':{'setup':{'reads':0,'writes':0},'migration':{'reads':0,'writes':0},'rollback':{'reads':0,'writes':0}},
                     'cleanup':{},'test_complete':False,'final_account_reconciliation_complete':False}
        self.state={'armed':False,'done':False,'cleanup_authorized':True,'protocol':'minimal-free-six-v1','worker':WORKER,'database':DATABASE,'parent_pid':os.getpid(),'heartbeat':iso(clock()),'cleanup_calls':0}
        self.start=clock();self.lease=None;self.sql_unknown=False;self.last_http_second=None
    def checkpoint(self):
        self.report['calls']=self.calls.counts;self.report['accepted']=self.measurements.accepted
        self.report['raw_cost_projections']={'reads':self.report['raw_dispatch_projection']['reads'],'writes':self.report['raw_dispatch_projection']['writes'],'billed_measurements':False}
        self.state.update(heartbeat=iso(self.clock()),cleanup_calls=self.calls.counts['cleanup'],pending=self.pending)
        private_json(self.session/'report.json',self.report);private_json(self.session/'session.json',self.state)
    def quota(self,cleanup=False):
        snapshot=dict(self.quota_provider())
        actual=sum(v['reads'] for v in self.report['sql_usage'].values())+self.report['http_measured_usage']['reads']+self.report['ambiguous_read_reserve']
        written=sum(v['writes'] for v in self.report['sql_usage'].values())+self.report['http_measured_usage']['writes']+self.report['ambiguous_write_reserve']
        # Baseline + this run's measured/projected costs, or the latest account
        # observation, whichever is larger. Raw values are never relabeled billed.
        if not hasattr(self,'account_baseline'):self.account_baseline=snapshot.copy()
        snapshot['rows_read_upper_bound']=max(snapshot.get('rows_read_upper_bound',5_000_000),self.account_baseline['rows_read_upper_bound']+actual+max(self.measurements.projected_raw_reads,self.report['raw_dispatch_projection']['reads']))
        snapshot['rows_written_upper_bound']=max(snapshot.get('rows_written_upper_bound',100_000),self.account_baseline['rows_written_upper_bound']+written+max(self.measurements.projected_raw_writes,self.report['raw_dispatch_projection']['writes']))
        snapshot['worker_requests_upper_bound']=max(snapshot.get('worker_requests_upper_bound',100_000),self.account_baseline['worker_requests_upper_bound']+self.calls.counts['http'])
        snapshot.update(migration_pending=True)
        if cleanup:
            if self.sql_unknown or snapshot['rows_read_upper_bound']>4_970_000 or snapshot['rows_written_upper_bound']>95_000:
                raise StopReview('ROLLBACK_QUOTA_UNKNOWN_OR_EXHAUSTED')
            # Cleanup uses its reserved smaller envelope, not admission reserve.
            if not snapshot.get('workers_free_confirmed') or not snapshot.get('d1_free_confirmed'):raise StopReview('FREE_BILLING_UNCONFIRMED')
            observed=utc(snapshot.get('observed_at_utc'))
            if self.clock()-observed>timedelta(minutes=5) or not utc(snapshot.get('period_start_utc'))<=self.clock()<utc(snapshot.get('period_end_utc')):
                raise StopReview('ROLLBACK_QUOTA_STALE')
        else:verify_quota(snapshot,self.clock(),require_migration_bound=False)
        return snapshot
    def before(self,kind):
        if kind!='cleanup':
            checkpoint=self.session/'session.json'
            if checkpoint.exists() and json.loads(checkpoint.read_text()).get('watchdog_cleanup') is not None:raise StopReview('WATCHDOG_TAKEOVER_STOP')
            if self.clock()-self.start>=timedelta(minutes=10) or utc(self.auth['expires_at_utc'])<=self.clock():raise StopReview('RUN_DEADLINE_STOP')
            if self.lease and self.clock()+timedelta(seconds=35)>=self.lease:raise StopReview('LEASE_NEAR_EXPIRY')
            if not getattr(self,'rolling_back',False):self.quota()
        self.calls.before(kind);self.checkpoint()
    def sql(self,sql,params=(),kind='setup'):
        if kind=='rollback':self.quota(cleanup=True)
        try:results=self.t.sql(sql,params)
        except BaseException:
            # API failure might have consumed reads or partly executed DDL.
            self.sql_unknown=True;raise
        rows=[]
        for r in results:
            m=r.get('meta',{})
            if any(type(m.get(k)) is not int or m[k]<0 for k in ('rows_read','rows_written')):
                self.sql_unknown=True;raise StopReview('SQL_COST_UNKNOWN')
            self.report['sql_usage'][kind]['reads']+=m['rows_read'];self.report['sql_usage'][kind]['writes']+=m['rows_written'];rows.extend(r.get('results',[]))
        self.checkpoint();u=self.report['sql_usage'][kind]
        limits={'setup':(10000,1000),'migration':(100000,10000),'rollback':(30000,5000)}[kind]
        if u['reads']>limits[0] or u['writes']>limits[1] or self.report['sql_usage']['setup']['writes']+self.report['sql_usage']['rollback']['writes']>5000:raise StopReview('SQL_BUDGET_STOP')
        return rows
    def schema(self):return {r['name']:normalize_sql(r['sql']) for r in self.sql(SQL.SCHEMA)}
    def preflight(self):
        authorize(self.auth,self.package,self.clock());snapshot=self.quota()
        resources=self.t.metadata()
        if type(resources.get('database_bytes')) is not int or resources['database_bytes']>snapshot['disposable_database_bytes_upper_bound']:raise StopReview('DATABASE_STORAGE_BOUND_MISMATCH')
        # Only identity/route checks are temporarily filled here. Real code/schema
        # and fixture checks must complete below before arming or publishing.
        verify_resources({**resources,'reviewed_code_and_schema_verified':True,'synthetic_fixture_verified':True})
        if any(b.get('name') in TEMP_NAMES for b in resources['bindings']):raise StopReview('PRIOR_REVIEW_NOT_CLEANED')
        modules=self.t.modules()
        if 'worker.mjs' not in modules:raise StopReview('ORIGINAL_ENTRYPOINT_MISSING')
        bindings=[{'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b for b in resources['bindings']]
        self.original={'modules':modules,'main':'worker.mjs','bindings':bindings,'options':resources.get('release_options',{})}
        if self.original['options'].get('compatibility_date')!='2026-10-01':raise StopReview('UNREVIEWED_COMPATIBILITY_DATE')
        private_json(self.session/'original.private.json',self.original)
        expected=self.package['schema']['expected'];legacy=self.package['schema']['legacy'];observed=self.schema()
        # Unknown schema is a hard stop, not permission to overwrite it.
        for name,definition in observed.items():
            if definition not in (expected.get(name),legacy.get(name)):raise StopReview('UNRECOGNIZED_SCHEMA_DEFINITION')
        for name in ('items_group_value','history_record_recent','public_browse_index'):
            if observed.get(name)!=expected[name]:raise StopReview('REQUIRED_BASE_SCHEMA_MISSING')
        needed=observed!=expected;count=self.sql(SQL.SCAN)
        if len(count)!=1 or type(count[0].get('n')) is not int or count[0]['n']>1000:raise StopReview('MIGRATION_SCAN_BOUND_STOP')
        fixture=self.sql(SQL.FIXTURE,SQL.FIXTURE_PARAMS)
        if len(fixture)!=1:raise StopReview('SYNTHETIC_FIXTURE_MISSING')
        f=fixture[0]
        if f.get('marker')!='synthetic-disposable-http-review' or f.get('groups')!=1 or f.get('total')!=2029 or f.get('active')!=526 or f.get('removed')!=1503 or f.get('list_type')!='want_list' or f.get('deleted_at') is not None or not f.get('revision')==f.get('public_revision')==f.get('browse_revision'):
            raise StopReview('SYNTHETIC_BASELINE_MISMATCH')
        self.resources={**resources,'reviewed_code_and_schema_verified':not needed,'synthetic_fixture_verified':True}
        self.report['preflight']={'identity_verified':True,'fixture_revision':f['revision'],'active':526,'removed':1503,'history_rows_upper_bound':count[0]['n'],'migration_needed':needed}
        self.checkpoint()
        if needed:
            if self.auth.get('allow_performance_migration') is not True:raise StopReview('PERFORMANCE_MIGRATION_AUTHORIZATION_REQUIRED')
            self.sql(self.package['schema']['migration'],kind='migration')
            if self.schema()!=expected:raise StopReview('MIGRATION_VERIFICATION_FAILED')
        self.resources['reviewed_code_and_schema_verified']=True;self.quota()
        verify_resources(self.resources)
    def publish(self):
        self.state['armed']=True;self.state['expires']=iso(self.clock()+timedelta(minutes=10));self.checkpoint()
        if self.supervise:self.supervise(self.session)
        self.lease=utc(self.state['expires']);self.t.key=secrets.token_hex(32)
        bindings=[b for b in self.original['bindings'] if b['name'] not in TEMP_NAMES|{'STAGING_METRICS'}]
        bindings += [{'name':n,'type':'plain_text','text':'true'} for n in ('MINIMAL_FREE_REVIEW','STAGING_METRICS')]
        bindings += [{'name':'MINIMAL_FREE_REVIEW_UNTIL','type':'plain_text','text':iso(self.lease)}, {'name':'FREE_HTTP_REVIEW_KEY','type':'secret_text','text':self.t.key}]
        self.state['publication_attempted']=True;self.checkpoint()
        self.t.publish(self.package['modules'],self.package['main_module'],bindings,release_options=self.original['options'])
        actual=self.t.release_metadata(self.resources);live=self.t.modules()
        verify_review_release({**actual,'reviewed_code_and_schema_verified':True,'synthetic_fixture_verified':True,'main_module':self.package['main_module'],'release_module_digests_verified':live==self.package['modules']},self.clock())
        self.t.endpoint(True)
    def call(self,label,path,body=None,diagnostic=False):
        # Separate all Worker requests into distinct UTC seconds.
        while self.last_http_second==int(self.clock().timestamp()):self.sleep(.1)
        self.last_http_second=int(self.clock().timestamp());started=iso(self.clock())
        if not diagnostic:
            operation=next((op for name,op,diag in MEASURED_SEQUENCE if name==label and not diag),None)
            if operation not in self.measurements.diagnostic_costs:raise StopReview('RAW_COST_BASELINE_MISSING')
            reads,writes=self.measurements.diagnostic_costs[operation]
            self.report['raw_dispatch_projection']['reads']+=2*reads;self.report['raw_dispatch_projection']['writes']+=2*writes
        self.report['inflight']={'label':label,'started':started};self.checkpoint()
        try:sample,data=self.t.http(path,body,diagnostic)
        except BaseException:
            self.report['inflight']['result']='unknown'
            self.last_http_second=int(self.clock().timestamp())
            if self.pending:self.report['ambiguous_read_reserve']+=2_500_000;self.report['ambiguous_write_reserve']+=15_000
            self.checkpoint();raise
        self.last_http_second=int(self.clock().timestamp())
        sample.update(label=label,started=started,ended=iso(self.clock()));self.report['samples'].append(sample);self.report.pop('inflight',None);self.checkpoint()
        if sample.get('status')!=200 or not isinstance(data,dict):
            if self.pending:self.report['ambiguous_read_reserve']+=2_500_000;self.report['ambiguous_write_reserve']+=15_000;self.checkpoint()
            raise StopReview('HTTP_RESULT_UNKNOWN')
        if diagnostic and (sample.get('d1_complete') is not True or any(type(sample.get(k)) is not int or sample[k]<0 for k in ('rows_read','rows_written'))):
            if self.pending:self.report['ambiguous_read_reserve']+=2_500_000;self.report['ambiguous_write_reserve']+=15_000;self.checkpoint()
            raise StopReview('D1_DIAGNOSTICS_MISSING')
        if diagnostic:
            bucket=self.report['sql_usage']['setup'] if label in ('index_readiness','login') else self.report['sql_usage']['rollback'] if label=='cleanup_undo' else self.report['http_measured_usage']
            bucket['reads']+=sample['rows_read'];bucket['writes']+=sample['rows_written'];self.checkpoint()
            if sample['rows_read']>12000 or sample['rows_written']>3500:raise StopReview('DIAGNOSTIC_D1_STOP')
            if bucket is self.report['http_measured_usage'] and (bucket['reads']>20000 or bucket['writes']>5000):raise StopReview('DIAGNOSTIC_D1_STOP')
            if bucket is self.report['sql_usage']['setup'] and (bucket['reads']>10000 or bucket['writes']>1000):raise StopReview('SETUP_COST_STOP')
            if bucket is self.report['sql_usage']['rollback'] and (bucket['reads']>30000 or bucket['writes']+self.report['sql_usage']['setup']['writes']>5000):raise StopReview('ROLLBACK_COST_STOP')
        return sample,data
    def cpu(self,sample):
        for attempt in range(3):
            rows=self.t.analytics(sample)
            try:cpu_observation(sample,rows);return rows
            except StopReview as e:
                if str(e)!='CPU_ANALYTICS_MISSING_OR_AMBIGUOUS' or rows or attempt==2:raise
                self.sleep(15)
        raise StopReview('ANALYTICS_UNAVAILABLE')
    def state_read(self,kind='rollback'):
        ids=self.original_ids
        rows=self.sql(SQL.STATE,[FIXTURE_GROUP,json.dumps(ids),FIXTURE_GROUP,FIXTURE_RECORD],kind=kind)
        if len(rows)!=1:raise StopReview('SYNTHETIC_STATE_UNKNOWN')
        return rows[0]
    def verify_undo(self,revision):
        state=self.state_read()
        if state['active']!=526 or canonical(json.loads(state['content_json']))!=canonical(json.loads(self.baseline['content_json'])) or state['original_items']!=self.baseline['original_items'] or not state['revision']==revision==state['public_revision']==state['browse_revision']:
            raise StopReview('UNDO_STATE_MISMATCH')
        notes=json.dumps(json.loads(self.baseline['content_json']).get('notes'),separators=(',',':'))
        if state.get('original_groups')!=self.baseline.get('original_groups') or state.get('provenance')!=self.baseline.get('provenance') or state.get('public_active')!=526 or state.get('public_notes')!=notes or state.get('browse_notes')!=notes:raise StopReview('UNDO_PROJECTION_OR_PROVENANCE_MISMATCH')
        expected_removed=1503+500*((revision-self.baseline['revision'])//2)
        if state['removed']!=expected_removed:raise StopReview('UNDO_REMOVED_STATE_MISMATCH')
        self.report['last_verified_restoration']={'revision':revision,'active':state['active'],'removed':state['removed']}
        return revision
    def history(self,revision,kind='setup'):
        rows=self.sql(SQL.HISTORY,[FIXTURE_RECORD,revision],kind=kind)
        if len(rows)!=1:raise StopReview('SAVE_HISTORY_AMBIGUOUS')
        return rows[0]['id']
    def save(self,owner,label,diagnostic):
        body=maximum_payload(owner,str(uuid.uuid4()))
        self.pending={'request_id':body['request_id'],'request_sha256':digest(json.dumps(body,separators=(',',':'),ensure_ascii=False)), 'revision_before':body['revision'],'kind':'save'}
        # Match the exact wire JSON/hash used by the unchanged receipt system.
        self.pending['request_sha256']=digest(json.dumps(body,separators=(',',':'),ensure_ascii=False))
        self.checkpoint();sample,result=self.call(label,'/action',body,diagnostic)
        if result.get('saved') is not True or result.get('record_id')!=FIXTURE_RECORD or result.get('revision')!=body['revision']+1:raise StopReview('SAVE_RESULT_AMBIGUOUS')
        self.pending.update(revision=result['revision']);self.checkpoint()
        return sample,result['revision']
    def undo(self,revision,label,diagnostic):
        h=self.history(revision,kind='rollback' if getattr(self,'rolling_back',False) else 'setup')
        body={'op':'undo','request_id':str(uuid.uuid4()),'record_id':FIXTURE_RECORD,'revision':revision,'history_id':h}
        self.pending.update(undo_request_id=body['request_id'],undo_request_sha256=digest(json.dumps(body,separators=(',',':'),ensure_ascii=False)),undo_revision=revision+1,history_id=h)
        self.checkpoint();sample,result=self.call(label,'/action',body,diagnostic)
        if result.get('saved') is not True or result.get('record_id')!=FIXTURE_RECORD or result.get('revision')!=revision+1:raise StopReview('UNDO_RESULT_AMBIGUOUS')
        self.verify_undo(revision+1);self.pending=None;self.checkpoint()
        return sample,revision+1
    def benchmark(self):
        sample,page=self.call('index_readiness','/public/index?after=',diagnostic=True)
        from_collection=page.get('records');cursor=page.get('next')
        if not isinstance(from_collection,list) or len(from_collection)>500 or not (cursor is None or from_collection and cursor==from_collection[-1].get('id')):raise StopReview('INDEX_PAGE_INVALID')
        self.setup_sample(sample)
        sample,login=self.call('login','/test/free-review-login',{},True)
        if login.get('signed_in') is not True or not self.t.cookie:raise StopReview('LOGIN_RESULT_UNKNOWN')
        self.setup_sample(sample)
        sample,owner=self.call('owner_open_diagnostic','/owner/record?id='+FIXTURE_RECORD,diagnostic=True)
        maximum_payload(owner,str(uuid.uuid4()))
        self.original_ids=[i['id'] for g in owner['groups'] for i in g['entries']]
        if len(self.original_ids)!=2029:raise StopReview('OWNER_COHORT_MISMATCH')
        self.baseline=self.state_read(kind='setup')
        self.measurements.accept(sample,self.cpu(sample));self.checkpoint()
        sample,raw_owner=self.call('owner_open_raw','/owner/record?id='+FIXTURE_RECORD)
        if canonical(raw_owner)!=canonical(owner):raise StopReview('OWNER_RESPONSE_MISMATCH')
        self.measurements.accept(sample,self.cpu(sample));self.checkpoint()
        sample,revision=self.save(owner,'maximum_save_diagnostic',True)
        self.measurements.accept(sample,self.cpu(sample));self.checkpoint()
        sample,revision=self.undo(revision,'large_undo_diagnostic',True)
        self.measurements.accept(sample,self.cpu(sample));self.checkpoint()
        owner['revision']=revision
        sample,revision=self.save(owner,'maximum_save_raw',False)
        self.measurements.accept(sample,self.cpu(sample));self.checkpoint()
        sample,revision=self.undo(revision,'large_undo_raw',False)
        self.measurements.accept(sample,self.cpu(sample));self.report['test_complete']=True;self.checkpoint()
    def setup_sample(self,sample):
        if sample['rows_read']>12000 or sample['rows_written']>3500 or self.report['sql_usage']['setup']['reads']>10000 or self.report['sql_usage']['setup']['writes']>1000:raise StopReview('SETUP_COST_STOP')
        sample['cpu_ms']=cpu_observation(sample,self.cpu(sample));self.checkpoint()
        if sample['cpu_ms']>=9:raise StopReview('CPU_SAFETY_STOP')
        self.checkpoint()
    def rollback(self):
        if not self.pending:return
        self.rolling_back=True
        try:
            self.quota(cleanup=True)
            # No replays: inspect the exact receipt after a lost Save or Undo.
            if self.pending.get('undo_request_id'):
                rows=self.sql(SQL.RECEIPT,[self.pending['undo_request_id']],kind='rollback')
                if rows:
                    r=rows[0];result=json.loads(r['result_json'])
                    if r.get('record_id')!=FIXTURE_RECORD or result.get('saved') is not True or result.get('record_id')!=FIXTURE_RECORD or r['request_sha256']!=self.pending['undo_request_sha256'] or result.get('revision')!=self.pending['undo_revision']:raise StopReview('UNDO_RECEIPT_MISMATCH')
                    self.verify_undo(result['revision']);self.pending=None;return
                # Absence of a receipt after ambiguous Undo does not prove an
                # in-flight request has stopped; never issue a second Undo.
                raise StopReview('UNDO_RESULT_UNRESOLVED')
            rows=self.sql(SQL.RECEIPT,[self.pending['request_id']],kind='rollback')
            if not rows:raise StopReview('SAVE_RESULT_UNRESOLVED')
            r=rows[0];result=json.loads(r['result_json'])
            if r.get('record_id')!=FIXTURE_RECORD or result.get('saved') is not True or result.get('record_id')!=FIXTURE_RECORD or r.get('request_sha256')!=self.pending['request_sha256'] or result.get('revision')!=self.pending['revision_before']+1:raise StopReview('SAVE_RECEIPT_MISMATCH')
            sample,revision=self.undo(result['revision'],'cleanup_undo',True)
            # Cleanup costs are real diagnostics, separately charged, not a
            # successful seventh benchmark or a retry of the original Save.
        except BaseException:self.report['rollback_incomplete']=True
        finally:self.rolling_back=False;self.checkpoint()
    def run(self):
        try:
            self.preflight();self.publish();self.benchmark()
        except BaseException as error:
            self.report['stop_code']=str(error) if isinstance(error,StopReview) else 'INTERRUPTED' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'LOCAL_OR_NETWORK_FAILURE'
        finally:
            if self.state['armed']:
                self.rollback();self.cleanup()
            self.state['done']=True;self.checkpoint()
        return self.report
    def cleanup(self):
        with cleanup_lock(self.session):
            stored=json.loads((self.session/'session.json').read_text())
            if stored.get('watchdog_cleanup') is not None:
                self.report['cleanup']=stored['watchdog_cleanup'];self.state.update(stored);return
            result=cleanup_operations(self.t,self.original)
            self.report['cleanup']=result;self.checkpoint()

class cleanup_lock:
    def __init__(self,directory):self.path=Path(directory)/'cleanup.lock'
    def __enter__(self):self.stream=open(self.path,'a');fcntl.flock(self.stream,fcntl.LOCK_EX);return self
    def __exit__(self,*args):self.stream.close()

def cleanup_operations(transport,original):
    result={'disabled_verified':False,'restored_verified':False,'temporary_key_removed':False,'complete':False}
    for _ in range(2):
        try:
            transport.endpoint(False,kind='cleanup')
            result['disabled_verified']=transport.disabled()
        except BaseException:pass
        if result['disabled_verified']:break
    if result['disabled_verified']:
        try:transport.publish(original['modules'],original['main'],original['bindings'],kind='cleanup',release_options=original['options'])
        except BaseException:pass
    # Restore PUT normally removes the temporary secret. DELETE may return 404;
    # transport treats that one idempotent-delete outcome as success.
    try:transport.remove_key();result['temporary_key_removed']=True
    except BaseException:pass
    if result['disabled_verified']:
        try:result['restored_verified']=transport.restored(original)
        except BaseException:pass
    result['complete']=result['disabled_verified'] and result['restored_verified'] and result['temporary_key_removed']
    return result

def supervise(session):
    subprocess.Popen([sys.executable,'-m','foundation.staging.minimal_free_runner','--watchdog',str(session)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def parent_alive(pid):
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False

def watchdog(session,transport_factory=None,clock=now,sleep=time.sleep,alive=parent_alive):
    from .minimal_free_transport import LiveTransport
    directory=work_path(str(session));path=directory/'session.json'
    while True:
        state=json.loads(path.read_text())
        if state.get('cleanup_authorized') is not True or state.get('protocol')!='minimal-free-six-v1' or state.get('worker')!=WORKER or state.get('database')!=DATABASE:raise StopReview('WATCHDOG_AUTHORIZATION_MISSING')
        if state.get('done') or not state.get('armed'):return
        if not alive(state['parent_pid']) or clock()>=utc(state['expires']) or clock()-utc(state['heartbeat'])>timedelta(seconds=90):break
        sleep(5)
    with cleanup_lock(directory):
        state=json.loads(path.read_text())
        if state.get('done'):return
        original=json.loads((directory/'original.private.json').read_text())
        def before(kind):
            if kind!='cleanup':raise StopReview('WATCHDOG_SQL_OR_BENCHMARK_FORBIDDEN')
            if state['cleanup_calls']>=10:raise StopReview('CLEANUP_BUDGET_EXHAUSTED')
            state['cleanup_calls']+=1;private_json(path,state)
        t=(transport_factory or LiveTransport)(before)
        result=cleanup_operations(t,original)
        state.update(done=True,watchdog_cleanup=result,rollback_requires_owner_review=bool(state.get('pending')))
        private_json(path,state)


def main():
    parser=argparse.ArgumentParser(description='NO DEFAULT EXECUTION: separately approved fixed-disposable six-call adapter')
    parser.add_argument('--run',action='store_true');parser.add_argument('--watchdog');parser.add_argument('--authorization');parser.add_argument('--quota');parser.add_argument('--release');parser.add_argument('--session')
    args=parser.parse_args()
    if args.watchdog:watchdog(args.watchdog);return
    if not args.run:parser.error('Remote execution requires --run and separate owner authorization')
    if not all((args.authorization,args.quota,args.release,args.session)):parser.error('Authorization, quota, release and private session paths required')
    package=json.loads(work_path(args.release).read_text());auth=json.loads(work_path(args.authorization).read_text());quota_path=work_path(args.quota)
    authorize(auth,package,now());verify_quota({**json.loads(quota_path.read_text()),'migration_pending':True},now(),require_migration_bound=False)
    session=work_path(args.session)
    if session.exists():raise StopReview('SESSION_DIRECTORY_MUST_BE_NEW')
    session.mkdir(mode=0o700,parents=True)
    # No credentials or transport construction until all local admission checks.
    from .minimal_free_transport import LiveTransport
    runner=Runner(None,package,auth,lambda:json.loads(quota_path.read_text()),session,supervise=supervise)
    runner.t=LiveTransport(runner.before)
    def interrupted(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
    result=runner.run();print(json.dumps({'test_complete':result['test_complete'],'stop_code':result.get('stop_code'),'cleanup':result['cleanup'],'report':str(session/'report.json')}))
    if not result['test_complete'] or not result['cleanup'].get('complete'):sys.exit(1)
if __name__=='__main__':main()
