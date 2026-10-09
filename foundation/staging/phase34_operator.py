"""Staging-only operator release. Inherits all existing secrets; no owner login.
Backs up application tables, verifies a disposable restore, and uses one ephemeral
in-memory migration credential. Never runs test writes against review staging.
"""
import argparse,hashlib,json,secrets,sqlite3,urllib.request,urllib.error,os,time
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from .cloudflare import api,query,deploy,WORKER
from .phase34_backup import TABLES
ROOT=Path(__file__).resolve().parents[2]
ORIGIN='https://wantlist-staging.andrewchris14.workers.dev'
def settings():
 s=api('/workers/scripts/'+WORKER+'/settings')
 assert any(b['name']=='STAGING_ONLY' and b.get('text')=='true' for b in s['bindings'])
 db=next(b['id'] for b in s['bindings'] if b['name']=='DB' and b['type']=='d1')
 assert api('/d1/database/'+db)['name']=='wantlist-staging'
 return s,db

def backup(db):
 identity=lambda:query(db,'SELECT id,revision,deleted_at FROM records ORDER BY id')[0]['results']
 before=identity()
 names={r['name']:r['sql'] for r in query(db,"SELECT name,sql FROM sqlite_master WHERE type='table'")[0]['results']}
 tables=[t for t in TABLES if t in names]
 snapshot={'kind':'authentication-free staging application backup','tables':{t:query(db,'SELECT * FROM '+t+' ORDER BY 1')[0]['results'] for t in tables},'schema':{t:names[t] for t in tables}}
 assert identity()==before,'Concurrent owner edits detected; retry backup before release'
 local=sqlite3.connect(':memory:');local.execute('PRAGMA foreign_keys=ON')
 for sql in snapshot['schema'].values():local.execute(sql)
 for table,rows in snapshot['tables'].items():
  for row in rows:local.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',list(row.values()))
 assert not local.execute('PRAGMA foreign_key_check').fetchall()
 for table,rows in snapshot['tables'].items():assert local.execute('SELECT count(*) FROM '+table).fetchone()[0]==len(rows)
 local.close()
 path=ROOT/'foundation/.local/phase34-pre-migration.json';path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(snapshot,ensure_ascii=False));path.chmod(0o600)
 return {'backup_file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'local_restore_verified':True,'tables':len(tables),'records':len(before),'authentication_excluded':True}

def worker_backup(path=None):
 account=os.environ['CLOUDFLARE_ACCOUNT_ID']
 req=urllib.request.Request('https://api.cloudflare.com/client/v4/accounts/'+account+'/workers/scripts/'+WORKER,headers={'Authorization':'Bearer '+os.environ['CLOUDFLARE_API_TOKEN'],'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=45) as response:
  content_type=response.headers['Content-Type'];raw=response.read()
 message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
 assert message.is_multipart(),'Expected the existing modular staging Worker'
 modules={}
 for part in message.iter_parts():
  name=part.get_filename() or part.get_param('name',header='content-disposition')
  if name and name!='metadata':modules[name]=part.get_payload(decode=True).decode()
 assert 'worker.mjs' in modules,'Expected staging main module'
 path=path or ROOT/'foundation/.local/phase34-worker-rollback.json';path.write_text(json.dumps(modules));path.chmod(0o600)
 return modules

def release(s,digest=None):
 bindings=[]
 for b in s['bindings']:
  if b['name'] in ('PHASE34_MIGRATION_DIGEST','ISOLATED_TEST_STORAGE'):continue
  bindings.append({'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b)
 if digest:bindings.append({'name':'PHASE34_MIGRATION_DIGEST','type':'plain_text','text':digest})
 for name,value in [('STAGING_ONLY','true'),('STAGING_EDITOR','true'),('STAGING_METRICS','false'),('STAGING_BENCH_VERSION','phase34-human-review')]:
  bindings=[b for b in bindings if b['name']!=name]+[{'name':name,'type':'plain_text','text':value}]
 modules={name:(ROOT/'foundation/staging'/name).read_text() for name in ('worker.mjs','auth.js','records.js','owner.js','replace-list.js','categories.js','phase34-migration.js','phase34-samples.js')}
 dist=ROOT/'foundation/.local/editor-dist';assets={}
 for p in dist.rglob('*'):
  if p.is_file():assets['/'+str(p.relative_to(dist))]={'body':p.read_text(),'type':'text/html; charset=utf-8' if p.suffix=='.html' else 'text/css; charset=utf-8' if p.suffix=='.css' else 'application/javascript; charset=utf-8'}
 assert '/index.html' in assets
 assets['/']=assets['/index.html'];modules['editor-assets.js']='export const editorAssets='+json.dumps(assets)+';'
 assert sum(len(v.encode()) for v in modules.values())<3_000_000,'Free Worker size limit'
 return deploy(WORKER,modules,'worker.mjs',bindings)

def apply():
 s,db=settings()
 preflight=query(db,"SELECT revision,deleted_at,(SELECT count(*) FROM change_history WHERE record_id=r.id) history_count FROM records r WHERE id='display-brewers-bobblehead-wantlist'")[0]['results']
 assert preflight and preflight[0]=={'revision':1,'deleted_at':None,'history_count':0},'Bobblehead migration conflict; stop before writes'
 saved=backup(db);old_modules=worker_backup()
 # Additive schema only. Owner PIN/auth/session tables are not touched.
 query(db,(ROOT/'foundation/staging/categories.sql').read_text())
 token=secrets.token_urlsafe(32)
 release(s,hashlib.sha256(token.encode()).hexdigest())
 migration=None
 try:
  req=urllib.request.Request(ORIGIN+'/operator/phase34-migration',data=b'{}',headers={'Content-Type':'application/json','Origin':ORIGIN,'X-Phase34-Migration':token,'User-Agent':'Mozilla/5.0'})
  for attempt in range(15):
   try:
    with urllib.request.urlopen(req,timeout=45) as response:migration=json.load(response)
    break
   except urllib.error.HTTPError as e:
    if e.code not in (403,503) or attempt==14:raise
    time.sleep(2)
 finally:
  # Remove the ephemeral gate on success or failure. No token is persisted.
  if migration:
   release(s)
  else:
   bindings=[{'name':b['name'],'type':'inherit'} if b['type']=='secret_text' else b for b in s['bindings']]
   deploy(WORKER,old_modules,'worker.mjs',bindings)
 after,_=settings();assert {b['name'] for b in after['bindings'] if b['type']=='secret_text'}=={b['name'] for b in s['bindings'] if b['type']=='secret_text'}
 report={'backup':saved,'migration':migration,'staging_only':True,'existing_secret_bindings_inherited':True,'sessions_modified':False,'test_writes_performed':False,'full_import':False,'production_cutover':False}
 (ROOT/'foundation/staging/phase34-release-result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true',required=True);p.parse_args();apply()
