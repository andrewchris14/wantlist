import sys,json,time,uuid,datetime
from pathlib import Path
from foundation.staging.runner import Client,state,sql,ROOT
from foundation.staging.cloudflare import query,WORKER,metrics

def run():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    c=Client();c.batch([sql('DELETE FROM login_limits')]);assert c.login()['status']==200
    rid=query(state()['database_id'],"SELECT g.record_id,count(*) n FROM record_groups g JOIN items i ON i.group_id=g.id JOIN records r ON r.id=g.record_id WHERE r.import_id='baseline' GROUP BY g.record_id ORDER BY n DESC LIMIT 1")[0]['results'][0]['record_id']
    r=c.call('/record?id='+rid)['body'];i=next(i for g in r['groups'] for i in g['entries'] if i['actionable'] and i['state'] in ['wanted','owned']);rev=r['revision'];targets=['pending','wanted'] if i['state']=='wanted' else ['wanted','owned']
    time.sleep(2);start=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z');samples=[]
    for n in range(10):
     result=c.call('/action',{'request_id':str(uuid.uuid4()),'op':'transition','record_id':rid,'revision':rev,'item_id':i['id'],'state':targets[n%2]});assert result['status']==200,result
     rev=result['body']['revision'];samples.append({k:result[k] for k in ['rows_read','rows_written','client_wall_ms']});time.sleep(1)
    end=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z');time.sleep(2)
    report={'start':start,'end':end,'samples':samples,'metrics':metrics(WORKER,start,end)}
    (ROOT/'foundation/staging/isolated-edit-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':
    run()
