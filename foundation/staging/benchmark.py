import sys,json,secrets,hashlib,time,urllib.request,datetime,statistics
from pathlib import Path
from foundation.staging.cloudflare import api,deploy,endpoint,metrics,PROBE

def run():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    key=secrets.token_hex(32);credential=secrets.token_urlsafe(32)
    auth={'algorithm':'SHA-256','digest':hashlib.sha256(credential.encode()).hexdigest(),'version':secrets.token_hex(16)}
    root=Path(__file__).resolve().parent
    deploy(PROBE,{'probe.mjs':(root/'credential-probe.mjs').read_text(),'auth.js':(root/'auth.js').read_text()},'probe.mjs',[{'type':'secret_text','name':'PROBE_KEY','text':key},{'type':'secret_text','name':'OWNER_AUTH_CONFIG','text':json.dumps(auth)}])
    endpoint(PROBE,True)
    url='https://'+PROBE+'.andrewchris14.workers.dev';rows=[]
    def call(correct):
     start=time.perf_counter();req=urllib.request.Request(url+'?sample='+secrets.token_hex(8),data=json.dumps({'credential':credential if correct else 'incorrect-disposable-access-code'}).encode(),headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/json','X-Staging-Probe':key})
     try:
      with urllib.request.urlopen(req,timeout=30) as r:body=json.load(r);body['status']=r.status
     except urllib.error.HTTPError as e:body={'status':e.code}
     body['client_wall_ms']=(time.perf_counter()-start)*1000;return body
    try:
     for _ in range(20):
      warm=call(True)
      if warm['status']==200:break
      time.sleep(2)
     else:raise RuntimeError('Staging routing never became available')
     start=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
     for correct in [True]*20+[False]*10:
      row=call(correct)
      for retry in range(5):
       if row['status']!=404:break
       time.sleep(1);row=call(correct)
      rows.append(row)
      assert row['status']==200 and row['valid']==correct,row
     end=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
     report={'start':start,'end':end,'samples':rows,'metrics':metrics(PROBE,start,end)}
     (root/'credential-benchmark-result.json').write_text(json.dumps(report,indent=2))
     print('SHA-256 correct/wrong samples:',len(rows),'all passed.')
     print('Analytics:',json.dumps(report['metrics']))
     print('Client wall ms median/min/max:',statistics.median(x['client_wall_ms'] for x in rows),min(x['client_wall_ms'] for x in rows),max(x['client_wall_ms'] for x in rows))
    finally:endpoint(PROBE,False);print('Probe endpoint disabled.')

if __name__=='__main__':
    run()
