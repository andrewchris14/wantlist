"""Staging release and narrowly scoped maintenance; never uses owner credentials."""
import json,hashlib,sqlite3,secrets,urllib.request,urllib.error,time
from pathlib import Path
from .phase34_operator import settings,worker_backup,ORIGIN
from .phase34_backup import TABLES
from .cloudflare import query,api,deploy,WORKER
from .phase35_audit import identify
ROOT=Path(__file__).resolve().parents[2]
def backup(db):
 names={r['name']:r['sql'] for r in query(db,"SELECT name,sql FROM sqlite_master WHERE type='table'")[0]['results']}
 def read():return {t:query(db,'SELECT * FROM '+t+' ORDER BY 1')[0]['results'] for t in TABLES if t in names}
 data=read();assert read()==data,'Concurrent edits: retry the consistent backup'
 snapshot={'kind':'authentication-free consistent staging application backup','tables':data,'schema':{t:names[t] for t in data}}
 local=sqlite3.connect(':memory:');local.execute('PRAGMA foreign_keys=ON')
 for sql in snapshot['schema'].values():local.execute(sql)
 for table,rows in data.items():
  for row in rows:local.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',list(row.values()))
 assert not local.execute('PRAGMA foreign_key_check').fetchall()
 assert all(local.execute('SELECT count(*) FROM '+t).fetchone()[0]==len(v) for t,v in data.items())
 # Verify exact restored values, not only row counts.
 local.row_factory=sqlite3.Row
 for table,rows in data.items():assert [dict(r) for r in local.execute('SELECT * FROM '+table+' ORDER BY 1')]==rows
 local.close();path=ROOT/'foundation/.local/phase35-pre-maintenance.json';path.write_text(json.dumps(snapshot,ensure_ascii=False));path.chmod(0o600)
 return snapshot,{'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'local_restore_verified':True,'exact_rows_verified':True,'authentication_excluded':True,'tables':len(data)}
def release(s,digest=None):
 bindings=[{'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b for b in s['bindings'] if b['name'] not in ('PHASE34_MIGRATION_DIGEST','PHASE35_MAINTENANCE_DIGEST','ISOLATED_TEST_STORAGE')]
 if digest:bindings.append({'name':'PHASE35_MAINTENANCE_DIGEST','type':'plain_text','text':digest})
 for name,value in [('STAGING_ONLY','true'),('STAGING_EDITOR','true'),('STAGING_METRICS','false'),('STAGING_BENCH_VERSION','phase35-human-review')]:bindings=[b for b in bindings if b['name']!=name]+[{'name':name,'type':'plain_text','text':value}]
 modules={p.name:p.read_text() for p in (ROOT/'foundation/staging').glob('*.js') if p.name!='editor-assets.js'}
 modules['worker.mjs']=(ROOT/'foundation/staging/worker.mjs').read_text();assets={}
 for p in (ROOT/'foundation/.local/editor-dist').rglob('*'):
  if p.is_file():assets['/'+str(p.relative_to(ROOT/'foundation/.local/editor-dist'))]={'body':p.read_text(),'type':'text/html; charset=utf-8' if p.suffix=='.html' else 'text/css; charset=utf-8' if p.suffix=='.css' else 'application/javascript; charset=utf-8'}
 assert '/index.html' in assets;assets['/']=assets['/index.html'];modules['editor-assets.js']='export const editorAssets='+json.dumps(assets)+';'
 assert sum(len(v.encode()) for v in modules.values())<3_000_000
 return deploy(WORKER,modules,'worker.mjs',bindings)
def prepare():
 s,db=settings();snapshot,report=backup(db);manifest=identify(snapshot)
 (ROOT/'foundation/staging/phase35-cleanup-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (ROOT/'foundation/staging/phase35-maintenance-data.js').write_text('export const cleanup='+json.dumps({'record_id':manifest['record_id'],'revision':manifest['expected_revision'],'ids':[i['id'] for i in manifest['items']],'metadata':manifest['restore_metadata'],'expected_notes':manifest['pre_cleanup_notes'],'manifest_sha256':manifest['sha256']})+';\n')
 view=json.loads((ROOT/'foundation/staging/historical-view.json').read_text())
 listings=[]
 for r in view['records']:
  if r['id'] in ('display-eau-claire-1','display-eau-claire-2','display-eau-claire-3'):
   source=r['source_group'];content={k:r[k] for k in ('id','year','brand','set_name','category','display_category','section','notes','source_refs','uncertainty')}
   listings.append({'id':r['id'],'content':content,'source':source,'source_sha256':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()})
 parent=next(r for r in snapshot['tables']['records'] if r['id']=='display-eau-claire-players')
 data={'parent':parent['id'],'revision':parent['revision'],'listings':listings}
 assert len(listings)==3
 with (ROOT/'foundation/staging/phase35-maintenance-data.js').open('a') as f:f.write('export const eau='+json.dumps(data)+';\n')
 (ROOT/'work/phase35-backup-result.json').write_text(json.dumps(report,indent=2));print(json.dumps({'backup':report,'confirmed_entries':len(manifest['items']),'other_review_candidates':len(manifest['audit_candidates'])-1},indent=2))
 return snapshot,manifest,report

def apply():
 expected=(ROOT/'foundation/staging/phase35-maintenance-data.js').read_bytes()
 snapshot,manifest,saved=prepare()
 assert (ROOT/'foundation/staging/phase35-maintenance-data.js').read_bytes()==expected,'Staging changed since tested preparation; review regenerated manifest before deployment'
 s,db=settings();old_modules=worker_backup(ROOT/'foundation/.local/phase35-worker-rollback.json')
 sessions=query(db,'SELECT count(*) n,min(created_at) oldest,max(created_at) newest FROM sessions')[0]['results']
 auth=query(db,'SELECT generation FROM auth_control WHERE id=1')[0]['results']
 token=secrets.token_urlsafe(32);maintenance=[]
 result={'backup':saved,'staging_only':True,'automated_test_writes':False,'owner_secrets_inherited':True,'full_import':False,'production_modified':False}
 release(s,hashlib.sha256(token.encode()).hexdigest())
 try:
  for operation in ('cleanup','eau-split'):
   req=urllib.request.Request(ORIGIN+'/operator/phase35-maintenance',data=json.dumps({'operation':operation}).encode(),headers={'Content-Type':'application/json','Origin':ORIGIN,'X-Phase35-Maintenance':token,'User-Agent':'Mozilla/5.0'})
   for attempt in range(12):
    try:
     with urllib.request.urlopen(req,timeout=45) as response:maintenance.append(json.load(response))
     break
    except urllib.error.HTTPError as e:
     if e.code not in (403,503) or attempt==11:raise
     time.sleep(2)
 finally:
  # Gate is removed even after a conflict; no operator token is persisted.
  if maintenance:release(s)
  else:deploy(WORKER,old_modules,'worker.mjs',[{'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b for b in s['bindings']])
  result['maintenance']=maintenance
  (ROOT/'foundation/staging/phase35-release-result.json').write_text(json.dumps(result,indent=2)+'\n')
 after,_=settings()
 assert {b['name'] for b in after['bindings'] if b['type']=='secret_text'}=={b['name'] for b in s['bindings'] if b['type']=='secret_text'}
 assert not any(b['name']=='PHASE35_MAINTENANCE_DIGEST' for b in after['bindings'])
 assert query(db,'SELECT count(*) n,min(created_at) oldest,max(created_at) newest FROM sessions')[0]['results']==sessions
 assert query(db,'SELECT generation FROM auth_control WHERE id=1')[0]['results']==auth
 result['sessions_preserved']=True;result['maintenance_gate_removed']=True
 (ROOT/'foundation/staging/phase35-release-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 apply() if args.apply else prepare()
