import datetime,json,sqlite3,time
from pathlib import Path
from foundation.staging import historical_import as h
from foundation.staging.import_rehearsal import fresh
import argparse
a=argparse.ArgumentParser(description='Disposable-only full rehearsal using remote transaction SQL; virtual days never change Cloudflare quotas');a.add_argument('--output-db',required=True);args=a.parse_args();p=Path(args.output_db).resolve()
if not p.is_relative_to(Path('work').resolve()) or p.exists():raise ValueError('Choose a NEW disposable database inside work/')
db=fresh(str(p));db.executescript((h.storage.ROOT/'foundation/staging/public-index.sql').read_text());db.executescript(h.schema());plan=h.manifest();i=h.Importer(h.Local(db),plan);i.prepare();start=time.monotonic();reports=[]
for n in range(30):
 r=i.run(3394,day=str(datetime.date(2030,1,1)+datetime.timedelta(days=n)));reports.append({'added':len(r['added']),'paused':r['paused']})
 if db.execute('SELECT count(*) FROM records').fetchone()[0]==3394:break
assert db.execute('SELECT count(*) FROM items').fetchone()[0]==59098
assert db.execute('SELECT count(*) FROM derived_import_receipts').fetchone()[0]==3394
assert db.execute('SELECT count(*) FROM public_browse_index').fetchone()[0]==3394
assert i.run(3394,day='2030-02-01')['added']==[]
result={'engine':'same per-listing trigger SQL as remote pilot','manifest':plan['hash'],'listings':3394,'items':59098,'groups':db.execute('SELECT count(*) FROM record_groups').fetchone()[0],'reserved_writes':sum(x[0] for x in db.execute('SELECT reserved FROM derived_import_days')),'virtual_free_days':reports,'local_wall_seconds_not_worker_cpu':round(time.monotonic()-start,3),'retry_added':0,'sqlite_database_bytes':db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0],'index_bytes':db.execute('SELECT sum(length(index_json)) FROM public_browse_index').fetchone()[0]}
Path('foundation/staging/phase3c2-full-rehearsal.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
from foundation.staging.readiness_audit import restore_snapshot
names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
snap={'schema':{n:db.execute("SELECT sql FROM sqlite_master WHERE name=?",(n,)).fetchone()[0] for n in names},'tables':{n:[dict(r) for r in db.execute('SELECT * FROM '+n+' ORDER BY 1')] for n in names},'schema_objects':[dict(r) for r in db.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL")]}
restored=restore_snapshot(snap);restored.close();db.close()
Path('foundation/staging/phase3c2-full-restore.json').write_text(json.dumps({'isolated_complete_restore':True,'tables':{n:len(v) for n,v in snap['tables'].items()},'schema_objects':len(snap['schema_objects']),'durable_external_copy':False},indent=2)+'\n')
