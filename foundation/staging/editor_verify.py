"""Actual staging-only owner API checks and repeated targeted Undo measurements.
No full import; no real credential in output. Requires temporarily enabled editor.
"""
import json,time,uuid,statistics
from datetime import datetime,timezone
from .runner import Client,ROOT,sql
from .cloudflare import metrics_groups,WORKER
REPORT=ROOT/'foundation/staging/editor-verification-result.json'
def utc():return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def run():
 c=Client();c.wait_ready();c.batch([sql('DELETE FROM login_limits')]);checks={};samples=[]
 def expect(name,r,status=200):
  assert r['status']==status,(name,r['status']);checks[name]=True;return r['body']
 expect('public_write_rejected',c.call('/action',{'op':'create'},gate=False,cookie=False),401)
 expect('private_read_rejected',c.call('/owner/recent',gate=False,cookie=False),401)
 expect('diagnostic_api_still_gated',c.call('/test/batch',{'statements':[]},gate=False),403)
 expect('origin_protection',c.call('/login',{'credential':c.state['credential'],'remembered':True},gate=False,origin=False),403)
 expect('owner_login_without_operator_gate',c.call('/login',{'credential':c.state['credential'],'remembered':True},gate=False))
 created=expect('new_future_record',c.call('/action',{'op':'create','request_id':str(uuid.uuid4()),'metadata':{'year':'2027','brand':'Topps','set_name':'2027 Topps Owner API Practice','category':'baseball_cards','notes':['Disposable owner UX verification']},'wanted':['47','92']},gate=False))
 rid=created['record_id'];rev=created['revision'];r=expect('lean_owner_read',c.call('/owner/record?id='+rid,gate=False));item=r['groups'][0]['entries'][0]
 assert 'content_json' not in r and 'source_refs' not in r['content'];checks['owner_read_omits_source_blob']=True
 start=utc()
 def call(label,body,instrumented=False):
  nonlocal rev
  # One request/second for interpretable sampled CPU. Sleep is outside Worker.
  time.sleep(1.05);a=utc();result=c.call('/action',{'record_id':rid,'revision':rev,'request_id':str(uuid.uuid4()),**body},gate=False,instrumented=instrumented);b=utc()
  expect(label,result);rev=result['body']['revision'];samples.append({'operation':label,'started':a,'ended':b,**{k:result[k] for k in ('status','client_wall_ms','instrumented','rows_read','rows_written','d1_duration_ms')}})
  return result['body']
 for n in range(5):
  call('pending',{'op':'transition','item_id':item['id'],'state':'pending'})
  h=expect('read_recent',c.call('/owner/recent',gate=False,instrumented=False))['changes'][0]
  assert h['undoable'];checks['undo_current_revision_only']=True
  call('undo_pending',{'op':'undo','history_id':h['id']})
  for count in (1,2,20):call('add_'+str(count),{'op':'add','values':[f'UX-{n}-{count}-{j}' for j in range(count)],'state':'wanted'})
 # Actual D1 row costs, separate instrumented invocations from raw CPU.
 for count in (1,2,20):call('add_'+str(count),{'op':'add','values':[f'UX-meter-{count}-{j}' for j in range(count)],'state':'wanted'},True)
 call('pending',{'op':'transition','item_id':item['id'],'state':'pending'},True)
 h=expect('read_recent_metered',c.call('/owner/recent',gate=False))['changes'][0]
 call('undo_pending',{'op':'undo','history_id':h['id']},True)
 added=call('add_delta',{'op':'add','values':['12','18'],'state':'wanted'},True)
 assert len(added['added_items'])==2;checks['add_returns_bounded_confirmed_delta']=True
 stale=c.call('/action',{'record_id':rid,'revision':rev,'request_id':str(uuid.uuid4()),'op':'undo','history_id':h['id']},gate=False)
 expect('stale_undo_rejected',stale,409)
 end=utc()
 expect('logout',c.call('/logout',{},gate=False));expect('writes_after_logout_rejected',c.call('/action',{'op':'edit'},gate=False),401)
 report={'checks':checks,'samples':samples,'start':start,'end':end,'full_import':False,'production_cutover':False,'authentication_redesigned':False}
 REPORT.write_text(json.dumps(report,indent=2));print('Actual owner API checks passed:',len(checks))
def collect():
 report=json.loads(REPORT.read_text());rows=metrics_groups(WORKER,report['start'],report['end']);observations={r['dimensions']['datetime']:r for r in rows if r['sum']['requests']==1}
 for s in report['samples']:
  r=observations.get(s['started'].split('.')[0]+'Z')
  if r:s['cpu_ms']=r['quantiles']['cpuTimeP50']/1000
 summary={}
 for op in sorted({s['operation'] for s in report['samples']}):
  samples=[s for s in report['samples'] if s['operation']==op and not s['instrumented']];cpus=[s['cpu_ms'] for s in samples if 'cpu_ms'in s]
  summary[op]={'raw_runs':len(samples),'successes':sum(s['status']==200 for s in samples),'cpu_observations':len(cpus),'median_cpu_ms':statistics.median(cpus) if cpus else None,'max_cpu_ms':max(cpus) if cpus else None,'median_wall_ms':statistics.median(s['client_wall_ms'] for s in samples) if samples else None,'metered':[{k:s[k] for k in ('rows_read','rows_written','d1_duration_ms')} for s in report['samples'] if s['operation']==op and s['instrumented']]}
 report['summary']=summary;REPORT.write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':
 import sys
 collect() if '--collect' in sys.argv else run()
