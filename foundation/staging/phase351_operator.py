"""Release only the tested staging Worker; audit verification performs no D1 writes."""
import json,hashlib,re,urllib.request,urllib.error,time
from pathlib import Path
from .phase34_operator import settings,worker_backup,ORIGIN
from .phase35_operator import release
from .cloudflare import query
ROOT=Path(__file__).resolve().parents[2]
def run():
 s,db=settings()
 def state():
  return {'records':query(db,'SELECT id,revision,list_type,content_json,deleted_at FROM records ORDER BY id')[0]['results'],
   'history_count':query(db,'SELECT count(*) n FROM change_history')[0]['results'],
   'sessions':query(db,'SELECT count(*) n,min(created_at) oldest,max(created_at) newest FROM sessions')[0]['results'],
   'auth_generation':query(db,'SELECT generation FROM auth_control WHERE id=1')[0]['results']}
 before=state();rollback=ROOT/'foundation/.local/phase351-worker-rollback.json'
 if not rollback.exists():worker_backup(rollback)
 deployed=release(s)
 def fetch(path):
  with urllib.request.urlopen(urllib.request.Request(ORIGIN+path,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as response:return response.read()
 for attempt in range(20):
  html=fetch('/').decode();asset=re.search(r'src="([^"]+\.js)"',html)[1];path=ROOT/'foundation/.local/editor-dist'/asset.lstrip('/')
  if path.exists():
   live=fetch(asset);local=path.read_bytes()
   if live==local:break
  if attempt==19:raise AssertionError('Deployed asset does not match tested build after propagation retries')
  time.sleep(2)
 assert b'mailto:jschris@triwest.net' in live
 public=json.loads(fetch('/public/record?id=p0581-l001'));assert public['id']=='p0581-l001' and public['list_type']=='have_list'
 assert public.get('display_category') in (None,'Football Wantlist')
 try:fetch('/owner/record?id=p0581-l001');guest_status=200
 except urllib.error.HTTPError as error:guest_status=error.code
 assert guest_status==401,'Guest owner read was not rejected'
 after=state();assert before==after,'Concurrent staging changes detected: inspect before claiming unchanged D1'
 current,_=settings();assert {b['name'] for b in s['bindings'] if b['type']=='secret_text'}=={b['name'] for b in current['bindings'] if b['type']=='secret_text'}
 result={'staging_only':True,'guest_owner_read_status':guest_status,'deployment':deployed,'tested_asset_sha256':hashlib.sha256(local).hexdigest(),'deployed_asset_matches_tested_build':True,'public_football_id':public['id'],'public_football_type':public['list_type'],'d1_records_and_history_unchanged':True,'sessions_and_auth_generation_unchanged':True,'secret_names_preserved':True,'d1_test_writes':False,'record_count':len(before['records'])}
 (ROOT/'foundation/staging/phase351-release-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':run()
