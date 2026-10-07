"""Repeated actual-Worker edits, with diagnostic/raw runs separated.

Only the approved staging database is touched. CPU comes from Cloudflare
analytics, never performance.now() or client time. No credentials in reports.
"""
import datetime as dt
import json
import statistics
import time
import uuid
from pathlib import Path
from .runner import Client, ROOT, state, sql
from .cloudflare import query, metrics_groups, WORKER

REPORT=ROOT/'foundation/staging/cpu-investigation-result.json'
def utc():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def run(rounds=20):
    c=Client();c.wait_ready();c.batch([sql('DELETE FROM login_limits')]);assert c.login()['status']==200
    rid=query(state()['database_id'],"SELECT g.record_id,count(*) n FROM record_groups g JOIN items i ON i.group_id=g.id JOIN records r ON r.id=g.record_id WHERE r.import_id='baseline' GROUP BY g.record_id ORDER BY n DESC LIMIT 1")[0]['results'][0]['record_id']
    r=c.call('/record?id='+rid)['body'];candidates=[i for g in r['groups'] for i in g['entries'] if i['actionable'] and not i['deleted_at']];item=next((i for i in candidates if i['value']=='347'),candidates[min(347,len(candidates)-1)]);rev=r['revision']
    if item['state']!='wanted':
        result=c.call('/action',{'request_id':str(uuid.uuid4()),'op':'transition','record_id':rid,'revision':rev,'item_id':item['id'],'state':'wanted'});assert result['status']==200;rev=result['body']['revision']
    report={'large_record_id':rid,'target_literal':item['value'],'large_set_initial_items':sum(len(g['entries']) for g in r['groups']),'rounds':rounds,'samples':[],'started':utc()}
    for n in range(rounds+3):
        instrumented=n>=rounds
        def call(label,body):
            nonlocal rev
            # Keep requests in distinct second buckets for sampled analytics.
            time.sleep(max(0,1.15-(time.time()%1)))
            started=utc();result=c.call('/action',{'request_id':str(uuid.uuid4()),**body},instrumented=instrumented);ended=utc()
            sample={'operation':label,'round':n,'instrumented':instrumented,'started':started,'ended':ended,'status':result['status'],'client_wall_ms':result['client_wall_ms']}
            if result['instrumented']:sample.update(rows_read=result['rows_read'],rows_written=result['rows_written'],d1_duration_ms=result['d1_duration_ms'])
            report['samples'].append(sample);REPORT.write_text(json.dumps(report,indent=2))
            if result['status']!=200:raise RuntimeError('Benchmark edit failed; inspect sanitized report')
            if body.get('record_id')==rid:rev=result['body']['revision']
            return result['body']
        def edit(label,**body):return call(label,{'record_id':rid,'revision':rev,**body})
        edit('wanted_to_pending',op='transition',item_id=item['id'],state='pending')
        edit('pending_to_owned',op='transition',item_id=item['id'],state='owned')
        edit('setup_owned_to_wanted',op='transition',item_id=item['id'],state='wanted')
        edit('setup_wanted_to_pending',op='transition',item_id=item['id'],state='pending')
        edit('pending_to_wanted',op='transition',item_id=item['id'],state='wanted')
        prefix='cpu-test-'+str(uuid.uuid4())
        for count in (1,2,20):edit('add_'+str(count),op='add',values=[prefix+'-'+str(count)+'-'+str(j) for j in range(count)])
        edit('remove_item',op='remove_item',item_id=item['id'])
        edit('restore_item',op='restore_item',item_id=item['id'])
        edit('edit_notes',op='edit',metadata={'notes':['Disposable staging CPU benchmark '+str(n)]})
        edit('edit_metadata',op='edit',metadata={'brand':'Topps','year':'2027'})
        call('create_20',{'op':'create','metadata':{'year':'2027','brand':'Topps','set_name':'2027 Topps CPU staging '+str(n),'category':'baseball_cards'},'wanted':[str(j) for j in range(20)]})
        print('completed CPU round',n+1,'/',rounds+3,flush=True)
    report['ended']=utc();REPORT.write_text(json.dumps(report,indent=2));print('Actual Worker edits complete; fetch analytics after ingestion',flush=True)

def collect():
    report=json.loads(REPORT.read_text());rows=metrics_groups(WORKER,report['started'],report['ended']);report['analytics_observations']=rows
    observations={row['dimensions']['datetime']:row for row in rows if row['sum']['requests']==1}
    for sample in report['samples']:
        key=sample['started'].split('.')[0]+'Z'
        row=observations.get(key)
        if row:sample.update(cpu_ms=row['quantiles']['cpuTimeP50']/1000,worker_wall_ms=row['quantiles']['wallTimeP50']/1000)
    summary={}
    for label in sorted({s['operation'] for s in report['samples']}):
        samples=[s for s in report['samples'] if s['operation']==label and not s['instrumented']]
        observed=[s['cpu_ms'] for s in samples if 'cpu_ms'in s];metered=[s for s in report['samples'] if s['operation']==label and s['instrumented']]
        def quantile(p):return sorted(observed)[min(len(observed)-1,max(0,__import__('math').ceil(p*len(observed))-1))] if observed else None
        summary[label]={'executions':len(samples),'successes':sum(s['status']==200 for s in samples),'cpu_observations':len(observed),'cpu_median_ms':statistics.median(observed) if observed else None,'observed_p95_ms':quantile(.95),'observed_p99_ms':quantile(.99),'observed_max_ms':max(observed) if observed else None,'observed_over_10ms':sum(v>=10 for v in observed),'client_wall_median_ms':statistics.median(s['client_wall_ms'] for s in samples),'diagnostic_rows_read':[s['rows_read'] for s in metered],'diagnostic_rows_written':[s['rows_written'] for s in metered],'diagnostic_d1_ms':[s['d1_duration_ms'] for s in metered]}
    report['summary']=summary;REPORT.write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--collect',action='store_true');p.add_argument('--rounds',type=int,default=20);a=p.parse_args()
    collect() if a.collect else run(a.rounds)
