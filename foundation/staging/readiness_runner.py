"""Authorized no-D1 probe controller. Import, --help and default are offline.

CLI --run also requires fresh quota evidence. No SQL/fixture/application APIs.
Private checkpoints contain rollback code and safe evidence, not review keys.
"""
import argparse,json,os,secrets,signal,subprocess,sys,time
from datetime import timedelta
from pathlib import Path
from .minimal_free_plan import WORKER,DATABASE,ORIGIN,StopReview,CallBudget,verify_quota,verify_resources,cpu_observation,utc
from .minimal_free_release import ROOT,digest,canonical
from .minimal_free_runner import private_json,work_path,cleanup_lock,cleanup_operations,parent_alive,now,iso
from .readiness_evidence import classify

PROTOCOL='readiness-no-d1-v1'
TEMP={'MINIMAL_FREE_REVIEW','MINIMAL_FREE_REVIEW_UNTIL','FREE_HTTP_REVIEW_KEY','READINESS_PROBE_NONCE'}
SOURCE=ROOT/'foundation/staging/readiness-probe.mjs'
MANIFEST=ROOT/'docs/evidence/readiness-probe-release-manifest.json'


def authorize(auth,manifest,clock):
    for key in ('owner_authorized','allow_probe_release','allow_enable','allow_two_gets','allow_cleanup'):
        if auth.get(key) is not True:raise StopReview('OWNER_PROBE_AUTHORIZATION_REQUIRED')
    if auth.get('protocol')!=PROTOCOL or auth.get('worker')!=WORKER or auth.get('database')!=DATABASE:
        raise StopReview('PROBE_AUTHORIZATION_TARGET_MISMATCH')
    if utc(auth.get('expires_at_utc'))<=clock:raise StopReview('PROBE_AUTHORIZATION_EXPIRED')
    if auth.get('probe_source_sha256')!=manifest['probe_source_sha256'] or digest(SOURCE.read_bytes())!=manifest['probe_source_sha256']:
        raise StopReview('PROBE_SOURCE_NOT_REVIEWED')


class ProbeRunner:
    def __init__(self,transport,auth,quota_provider,session,supervisor,clock=now,sleep=time.sleep,monotonic=time.monotonic,on_browser=None,manifest=None):
        self.t=transport;self.auth=auth;self.quota_provider=quota_provider;self.session=Path(session)
        self.supervisor=supervisor;self.clock=clock;self.sleep=sleep;self.monotonic=monotonic;self.on_browser=on_browser
        self.manifest=manifest or json.loads(MANIFEST.read_text());self.calls=CallBudget();self.start=clock();self.lease=None
        self.original=None;self.nonce=None;self.guard_health=None
        self.report={'protocol':PROTOCOL,'worker':WORKER,'database':DATABASE,'probe_source_sha256':self.manifest['probe_source_sha256'],'samples':[],'cleanup':{},'sql_calls':0,'application_http_calls':0,'probe_complete':False,'final_account_reconciliation_complete':False}
        self.state={'protocol':PROTOCOL,'worker':WORKER,'database':DATABASE,'cleanup_authorized':True,'parent_pid':os.getpid(),'armed':False,'publication_attempted':False,'done':False,'cleanup_calls':0,'heartbeat':iso(clock())}
    def checkpoint(self):
        path=self.session/'session.json'
        if path.exists():
            stored=json.loads(path.read_text())
            if stored.get('cleanup_in_progress') or stored.get('watchdog_cleanup') is not None:
                self.state.update(stored)
                self.calls.counts['cleanup']=max(self.calls.counts['cleanup'],stored['cleanup_calls'])
                if stored.get('watchdog_cleanup') is not None:self.report['cleanup']=stored['watchdog_cleanup']
                self.report['calls']=dict(self.calls.counts);private_json(self.session/'report.json',self.report);return
        self.state.update(heartbeat=iso(self.clock()),cleanup_calls=self.calls.counts['cleanup'])
        self.report['calls']=dict(self.calls.counts)
        private_json(self.session/'report.json',self.report);private_json(self.session/'session.json',self.state)
    def quota(self):
        q=dict(self.quota_provider());q.update(migration_pending=True)
        q['worker_requests_upper_bound']=q['worker_requests_upper_bound']+self.calls.counts['http']+int(self.report.get('browser_offered',False))
        return verify_quota(q,self.clock(),require_migration_bound=False)
    def admission(self):
        authorize(self.auth,self.manifest,self.clock());self.quota()
    def before(self,kind):
        if kind!='cleanup':
            stored=self.session/'session.json'
            if stored.exists():
                observed=json.loads(stored.read_text())
                if observed.get('watchdog_cleanup') is not None or observed.get('cleanup_in_progress'):raise StopReview('PROBE_WATCHDOG_TAKEOVER')
            self.admission()
            if self.clock()-self.start>=timedelta(minutes=10):raise StopReview('PROBE_RUN_DEADLINE')
            if self.lease and self.clock()+timedelta(seconds=35)>=self.lease:raise StopReview('PROBE_LEASE_NEAR_EXPIRY')
            if self.guard_health and not self.guard_health():raise StopReview('PROBE_SUPERVISOR_UNHEALTHY')
        if kind=='http' and self.calls.counts['http']>=2:raise StopReview('PROBE_HTTP_BUDGET_EXHAUSTED')
        self.calls.before(kind);self.checkpoint()
    def preflight(self):
        self.admission();r=self.t.metadata();verify_resources(r,require_application=False)
        if type(r.get('database_bytes')) is not int or r['database_bytes']>self.quota_provider()['disposable_database_bytes_upper_bound']:raise StopReview('PROBE_STORAGE_BOUND_MISMATCH')
        if any(b['name'] in TEMP for b in r['bindings']):raise StopReview('PRIOR_PROBE_NOT_CLEANED')
        modules=self.t.modules()
        if {k:digest(v) for k,v in modules.items()}!=self.manifest['original_module_sha256']:raise StopReview('PROBE_ORIGINAL_MODULES_CHANGED')
        if digest(canonical(r['release_options']))!=self.manifest['original_options_sha256']:raise StopReview('PROBE_ORIGINAL_OPTIONS_CHANGED')
        self.original={'main':'worker.mjs','modules':modules,'options':r['release_options'],'bindings':[{'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b for b in r['bindings']]}
        private_json(self.session/'original.private.json',self.original);self.resources=r
        self.report['preflight']={'disposable_identity_verified':True,'original_release_verified':True,'application_schema_or_fixture_inspected':False};self.checkpoint()
    def publish(self):
        self.lease=self.clock()+timedelta(minutes=10);self.nonce=secrets.token_hex(16);self.t.key=secrets.token_hex(32)
        self.state.update(armed=True,expires=iso(self.lease));self.report['public_nonce']=self.nonce;self.checkpoint()
        # Supervisor handshake/health is mandatory BEFORE uploading or enabling.
        self.guard_health=self.supervisor(self.session)
        if not callable(self.guard_health) or not self.guard_health():raise StopReview('PROBE_SUPERVISOR_NOT_READY')
        bindings=list(self.original['bindings'])+[{'name':'MINIMAL_FREE_REVIEW','type':'plain_text','text':'true'},{'name':'MINIMAL_FREE_REVIEW_UNTIL','type':'plain_text','text':iso(self.lease)},{'name':'FREE_HTTP_REVIEW_KEY','type':'secret_text','text':self.t.key},{'name':'READINESS_PROBE_NONCE','type':'plain_text','text':self.nonce}]
        modules={'worker.mjs':SOURCE.read_text()}
        self.state['publication_attempted']=True;self.checkpoint()
        self.t.publish(modules,'worker.mjs',bindings,release_options=self.original['options'])
        actual=self.t.release_metadata(self.resources);verify_resources(actual,require_application=False)
        if self.t.modules()!=modules:raise StopReview('PROBE_UPLOAD_MISMATCH')
        bs={b['name']:b for b in actual['bindings']}
        for name,text in (('MINIMAL_FREE_REVIEW','true'),('MINIMAL_FREE_REVIEW_UNTIL',iso(self.lease)),('READINESS_PROBE_NONCE',self.nonce)):
            if bs.get(name,{}).get('type')!='plain_text' or bs[name].get('text')!=text:raise StopReview('PROBE_GUARD_BINDING_MISMATCH')
        if bs.get('FREE_HTTP_REVIEW_KEY',{}).get('type')!='secret_text':raise StopReview('PROBE_PRIVATE_KEY_BINDING_MISSING')
        self.report['endpoint_enable']={'started':iso(self.clock())};self.checkpoint()
        ack=self.t.endpoint(True);self.enabled_at=self.monotonic()
        self.report['endpoint_enable'].update(acknowledged_at=iso(self.clock()),api_enabled=ack.get('enabled') if isinstance(ack,dict) else None);self.checkpoint()
        endpoint=self.t.api('/workers/scripts/'+WORKER+'/subdomain')
        if endpoint.get('enabled') is not True or endpoint.get('previews_enabled') is not False:raise StopReview('PROBE_ENDPOINT_ENABLE_UNVERIFIED')
    def wait_until(self,target):
        while self.monotonic()<target:
            self.before_wait();self.sleep(min(.5,target-self.monotonic()))
    def before_wait(self):
        # No API calls or budget consumption while waiting; still cancelable.
        self.admission()
        if self.clock()-self.start>=timedelta(minutes=10) or (self.lease and self.clock()+timedelta(seconds=35)>=self.lease):raise StopReview('PROBE_WAIT_DEADLINE')
        if self.guard_health and not self.guard_health():raise StopReview('PROBE_SUPERVISOR_UNHEALTHY')
        stored=json.loads((self.session/'session.json').read_text())
        if stored.get('watchdog_cleanup') is not None or stored.get('cleanup_in_progress'):raise StopReview('PROBE_WATCHDOG_TAKEOVER')
        self.checkpoint()
    def measure(self,offset):
        self.wait_until(self.enabled_at+offset)
        # Never make a missed scheduled observation later after a slow response.
        if self.monotonic()>self.enabled_at+offset+2:raise StopReview('PROBE_SCHEDULE_MISSED')
        started=iso(self.clock());sample,data=self.t.http()
        sample.update(started=started,ended=iso(self.clock()),scheduled_offset_seconds=offset)
        sample['attribution']=classify(sample,self.nonce);self.report['samples'].append(sample);self.checkpoint()
        kind=sample['attribution']['classification']
        if kind=='cloudflare_1042_fingerprint' and sample.get('status')==404:return False
        if kind!='disposable_probe_marker_observed' or sample.get('status')!=200 or data!={'probe':'wantlist-readiness-no-d1-v1','nonce':self.nonce,'authorized':True}:raise StopReview('PROBE_RESPONSE_UNEXPECTED')
        self.report['route_marker_observed']=True;self.checkpoint()
        for attempt in range(3):
            rows=self.t.analytics(sample)
            if not rows and attempt<2:self.wait_until(self.monotonic()+15);continue
            sample['cpu_ms']=cpu_observation(sample,rows);self.checkpoint()
            if sample['cpu_ms']>=9:raise StopReview('PROBE_CPU_SAFETY_STOP')
            return True
        raise StopReview('PROBE_CPU_UNAVAILABLE')
    def browser(self):
        if not self.auth.get('allow_optional_browser') or not self.on_browser:return
        q=self.quota_provider();deadline=min(self.clock()+timedelta(seconds=60),utc(q['observed_at_utc'])+timedelta(minutes=5)-timedelta(seconds=35),self.lease-timedelta(seconds=35),utc(self.auth['expires_at_utc'])-timedelta(seconds=35))
        if deadline<=self.clock():return
        self.report.update(browser_offered=True,browser_deadline_utc=iso(deadline));self.checkpoint()
        self.on_browser({'event':'optional_browser_comparison','url':ORIGIN+'/public/index?after=','browser_view_source_url':'view-source:'+ORIGIN+'/public/index?after=','expected_public_nonce':self.nonce,'deadline_utc':iso(deadline)})
        path=self.session/'browser-result.json'
        while self.clock()<deadline:
            self.before_wait()
            if path.exists():
                if path.stat().st_size>1024:raise StopReview('BROWSER_RESULT_INVALID')
                result=json.loads(path.read_text())
                if result.get('skip') is True:self.report['browser_result']='owner_skipped';return
                if result.get('probe')!='wantlist-readiness-no-d1-v1' or result.get('nonce')!=self.nonce or result.get('authorized') is not False:raise StopReview('BROWSER_RESULT_UNATTRIBUTED')
                self.report['browser_result']={'matching_public_probe_body_reported_by_owner':True,'http_status_independently_verified':False};self.checkpoint();return
            self.sleep(.5)
        self.report['browser_result']='not_received_before_deadline'
    def cleanup(self):
        with cleanup_lock(self.session):
            stored=json.loads((self.session/'session.json').read_text())
            if stored.get('watchdog_cleanup') is not None:self.state.update(stored);self.report['cleanup']=stored['watchdog_cleanup'];return
            self.report['cleanup']=cleanup_operations(self.t,self.original) if self.state['publication_attempted'] else {'complete':True,'not_required_no_publication':True}
            self.checkpoint()
    def run(self):
        try:
            self.preflight();self.publish()
            if self.measure(5):self.report['route_established']=True
            elif self.measure(30):self.report['route_established']=True
            else:self.report['route_established']=False;self.browser()
            self.report['probe_complete']=True
        except BaseException as e:self.report['stop_code']=str(e) if isinstance(e,StopReview) else 'PROBE_INTERRUPTED' if isinstance(e,(KeyboardInterrupt,SystemExit)) else 'PROBE_LOCAL_OR_NETWORK_FAILURE'
        finally:
            if self.state['armed']:self.cleanup()
            self.state['done']=True;self.checkpoint()
        return self.report


def valid_checkpoint(state):
    if state.get('protocol')!=PROTOCOL or state.get('worker')!=WORKER or state.get('database')!=DATABASE or state.get('cleanup_authorized') is not True:raise StopReview('PROBE_WATCHDOG_AUTHORIZATION_MISSING')


def watchdog(directory,transport_factory=None,clock=now,sleep=time.sleep,alive=parent_alive):
    directory=work_path(str(directory));path=directory/'session.json'
    while True:
        state=json.loads(path.read_text());valid_checkpoint(state)
        if state.get('done') or not state.get('armed'):return
        private_json(directory/'watchdog-ready.json',{'pid':os.getpid(),'parent_pid':state['parent_pid'],'heartbeat':iso(clock()),'protocol':PROTOCOL})
        if not alive(state['parent_pid']) or clock()>=utc(state['expires']) or clock()-utc(state['heartbeat'])>timedelta(seconds=90):break
        sleep(2)
    with cleanup_lock(directory):
        state=json.loads(path.read_text());valid_checkpoint(state)
        if state.get('done'):return
        state['cleanup_in_progress']=True;private_json(path,state)
        def before(kind):
            if kind!='cleanup':raise StopReview('PROBE_WATCHDOG_NONCLEANUP_FORBIDDEN')
            if state['cleanup_calls']>=10:raise StopReview('PROBE_CLEANUP_BUDGET_EXHAUSTED')
            state['cleanup_calls']+=1;private_json(path,state)
        if state.get('publication_attempted'):
            from .readiness_transport import ProbeTransport
            original=json.loads((directory/'original.private.json').read_text())
            result=cleanup_operations((transport_factory or ProbeTransport)(before),original)
        else:result={'complete':True,'not_required_no_publication':True}
        state.update(done=True,watchdog_cleanup=result);private_json(path,state)


def supervise(directory):
    child=subprocess.Popen([sys.executable,'-m','foundation.staging.readiness_runner','--watchdog',str(directory)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    ready=Path(directory)/'watchdog-ready.json';deadline=time.monotonic()+5
    def health():
        if child.poll() is not None or not ready.exists():return False
        try:
            r=json.loads(ready.read_text());return r.get('pid')==child.pid and r.get('parent_pid')==os.getpid() and r.get('protocol')==PROTOCOL and timedelta(0)<=now()-utc(r['heartbeat'])<=timedelta(seconds=10)
        except (OSError,ValueError):return False
    while time.monotonic()<deadline:
        if health():return health
        if child.poll() is not None:break
        time.sleep(.1)
    raise StopReview('PROBE_SUPERVISOR_HANDSHAKE_FAILED')


def main():
    parser=argparse.ArgumentParser(description='Offline by default; separately authorized no-D1 readiness probe only')
    parser.add_argument('--run',action='store_true');parser.add_argument('--watchdog');parser.add_argument('--authorization');parser.add_argument('--quota');parser.add_argument('--session')
    args=parser.parse_args()
    if args.watchdog:watchdog(args.watchdog);return
    if not args.run:parser.error('No remote execution without --run and owner authorization')
    if not all((args.authorization,args.quota,args.session)):parser.error('Authorization, fresh quota and new private session required')
    auth=json.loads(work_path(args.authorization).read_text());qpath=work_path(args.quota)
    manifest=json.loads(MANIFEST.read_text());authorize(auth,manifest,now())
    verify_quota({**json.loads(qpath.read_text()),'migration_pending':True},now(),require_migration_bound=False)
    session=work_path(args.session)
    if session.exists():raise StopReview('PROBE_SESSION_MUST_BE_NEW')
    session.mkdir(parents=True,mode=0o700)
    runner=ProbeRunner(None,auth,lambda:json.loads(qpath.read_text()),session,supervise,on_browser=lambda event:print(json.dumps(event),flush=True))
    from .readiness_transport import ProbeTransport
    runner.t=ProbeTransport(runner.before);runner.t.operation_lock=session
    def interrupted(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
    r=runner.run();print(json.dumps({'probe_complete':r['probe_complete'],'stop_code':r.get('stop_code'),'cleanup':r['cleanup'],'report':str(session/'report.json')}),flush=True)
    if not r['probe_complete'] or not r['cleanup'].get('complete'):sys.exit(1)
if __name__=='__main__':main()
