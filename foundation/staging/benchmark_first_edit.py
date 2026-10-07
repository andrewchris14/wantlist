"""First observed edit after staging redeployment; no claim to force cold isolates."""
import datetime as dt
import json
import time
import uuid
from .runner import ROOT,Client,deploy_staging,state,sql
from .cloudflare import query,metrics_groups,WORKER
REPORT=ROOT/'foundation/staging/cpu-first-edit-result.json'
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def run():
    s=state();rid=query(s['database_id'],"SELECT g.record_id,count(*) n FROM record_groups g JOIN items i ON i.group_id=g.id JOIN records r ON r.id=g.record_id WHERE r.import_id='baseline' GROUP BY g.record_id ORDER BY n DESC LIMIT 1")[0]['results'][0]['record_id']
    samples=[];report={'started':stamp(),'samples':samples,'forced_cold_isolate':False}
    for n in range(5):
        version='cpu-first-'+str(uuid.uuid4());deploy_staging(benchmark_version=version);c=Client();c.wait_ready(expected_version=version);c.batch([sql('DELETE FROM login_limits')]);assert c.login()['status']==200
        r=c.call('/record?id='+rid)['body'];i=next(i for g in r['groups'] for i in g['entries'] if i['actionable'] and not i['deleted_at'] and i['state'] in ('wanted','pending'))
        time.sleep(1.15)
        start=stamp();result=c.call('/action',{'request_id':str(uuid.uuid4()),'op':'transition','record_id':rid,'revision':r['revision'],'item_id':i['id'],'state':'pending' if i['state']=='wanted' else 'wanted'},instrumented=False);end=stamp()
        samples.append({'redeployment':n+1,'started':start,'ended':end,'status':result['status'],'wall_ms':result['client_wall_ms']});assert result['status']==200
        REPORT.write_text(json.dumps(report,indent=2));print('First edit after redeployment',n+1,'passed',flush=True)
    report['ended']=stamp();REPORT.write_text(json.dumps(report,indent=2))
def collect():
    r=json.loads(REPORT.read_text());rows=metrics_groups(WORKER,r['started'],r['ended']);r['analytics_observations']=rows
    by={row['dimensions']['datetime']:row for row in rows if row['sum']['requests']==1}
    for s in r['samples']:
        row=by.get(s['started'].split('.')[0]+'Z')
        if row:s['cpu_ms']=row['quantiles']['cpuTimeP50']/1000
    REPORT.write_text(json.dumps(r,indent=2));print('First-edit samples',r['samples'])
if __name__=='__main__':
    import sys
    collect() if '--collect' in sys.argv else run()
