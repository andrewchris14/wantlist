import json,time,secrets,hashlib,uuid,datetime,sys,concurrent.futures
from pathlib import Path
from foundation.staging.runner import Client,state,sql,STATE,ROOT
from foundation.staging.cloudflare import api,query,metrics,WORKER

def run():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    c=Client();dbid=state()['database_id'];c.batch([sql('DELETE FROM login_limits')]);assert c.login()['status']==200
    report={};old_cookie=c.cookie;old_credential=c.state['credential'];s=state();s['credential']=secrets.token_urlsafe(32);s['credential_version']=secrets.token_hex(16)
    cfg={'algorithm':'SHA-256','digest':hashlib.sha256(s['credential'].encode()).hexdigest(),'version':s['credential_version']}
    api('/workers/scripts/'+WORKER+'/secrets','PUT',{'name':'OWNER_AUTH_CONFIG','type':'secret_text','text':json.dumps(cfg)})
    STATE.write_text(json.dumps(s));STATE.chmod(0o600);c.state=s
    for _ in range(20):
     r=c.call('/session')
     if r['status']==401:break
     time.sleep(1)
    assert r['status']==401
    report['manual_secret_rotation_rejects_old_session']=True
    r=c.call('/login',{'credential':old_credential,'remembered':True},cookie=False);assert r['status']==401
    report['manual_secret_rotation_rejects_old_code']=True
    for attempt in range(12):
     result=c.login()
     if result['status']==200:break
     if result['status']==429:c.batch([sql('DELETE FROM login_limits')])
     time.sleep(1)
    else:raise AssertionError('New secret did not propagate')
    report['new_code_login_works']=True
    report['secret_propagation_login_retries']=attempt
    # Target the actual largest imported set, rather than a small fictional set.
    rows=query(dbid,"SELECT g.record_id,count(*) AS n FROM record_groups g JOIN items i ON i.group_id=g.id JOIN records r ON r.id=g.record_id WHERE r.import_id='baseline' GROUP BY g.record_id ORDER BY n DESC LIMIT 1")[0]['results'];rid=rows[0]['record_id']
    r=c.call('/record?id='+rid)['body'];item=next(i for g in r['groups'] for i in g['entries'] if i['actionable'] and i['state'] in ('wanted','owned'));revision=r['revision']
    start=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z');measurements=[]
    targets=['pending','wanted']*5 if item['state']=='wanted' else ['wanted','owned']*5
    for target in targets:
     body={'request_id':str(uuid.uuid4()),'op':'transition','record_id':rid,'revision':revision,'item_id':item['id'],'state':target}
     result=c.call('/action',body);assert result['status']==200,result
     revision=result['body']['revision'];measurements.append({k:result[k] for k in ['status','rows_read','rows_written','client_wall_ms']})
    end=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    report['largest_set_changes']=measurements;report['largest_set_items']=rows[0]['n'];report['largest_cpu_window']={'start':start,'end':end}
    # Real concurrent optimistic saves, same revision, distinct idempotency keys.
    a=c.call('/record?id='+rid)['body'];base=a['revision']
    clients=[Client(),Client()]
    for client in clients:client.cookie=c.cookie
    bodies=[{'request_id':str(uuid.uuid4()),'op':'edit','record_id':rid,'revision':base,'metadata':{'notes':a['content'].get('notes',[])}} for _ in range(2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
     results=list(pool.map(lambda pair:pair[0].call('/action',pair[1]),zip(clients,bodies)))
    assert sorted(r['status'] for r in results)==[200,409],results
    report['actual_concurrent_saves_one_success_one_conflict']=True
    report['same_record_projection_revision']=query(dbid,'SELECT r.revision=p.revision AS ok FROM records r JOIN public_records p ON p.record_id=r.id WHERE r.id=?',[rid])[0]['results'][0]['ok']==1
    (ROOT/'foundation/staging/additional-result.json').write_text(json.dumps(report,indent=2))
    print('Manual secret rotation, largest-set changes, concurrent conflict and projection checks passed.')
    print('Largest changes metering:',measurements)

if __name__=='__main__':
    run()
