"""Read-only consistent staging backup. Restores only into local memory.

Includes hashed session rows privately for disaster recovery; never prints their
contents. Worker PIN/secrets are not retrievable and are not read or changed.
"""
import datetime
import hashlib
import json
from pathlib import Path
from .phase34_backup import TABLES
from .phase34_operator import settings
from .cloudflare import query
from .readiness_audit import restore_snapshot

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['phase3c1','phase3c2'],default='phase3c1');phase=p.parse_args().phase
    _,database=settings()
    names={r['name']:r['sql'] for r in query(database,"SELECT name,sql FROM sqlite_master WHERE type='table'")[0]['results']}
    allowed=(*TABLES,'auth_control','sessions','login_limits','import_write_days','import_write_attempts','import_chunk_payloads','public_browse_index','derived_import_manifests','derived_import_days','derived_import_attempts','derived_import_receipts','derived_import_payloads')
    tables=[t for t in allowed if t in names]
    unknown=set(names)-set(tables)
    if any(not t.startswith('_') for t in unknown):raise ValueError('Unrecognized application table: review backup coverage')
    def read():return {t:query(database,'SELECT * FROM '+t+' ORDER BY 1')[0]['results'] for t in tables}
    data=read()
    if read()!=data:raise ValueError('Concurrent edits: retry consistent snapshot; nothing changed remotely')
    objects=query(database,"SELECT name,type,sql FROM sqlite_master WHERE type IN ('index','trigger','view') AND sql IS NOT NULL AND name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY type,name")[0]['results']
    snapshot={'schema':{t:names[t] for t in data},'tables':data,'schema_objects':objects}
    restored=restore_snapshot(snapshot);restored.close()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path=Path(__file__).resolve().parents[1]/'.local'/(phase+'-complete-private-'+stamp+'.json')
    with path.open('x',encoding='utf-8') as stream:
        path.chmod(0o600);json.dump(snapshot,stream,ensure_ascii=False)
    report={'created_utc':stamp,'private_file':str(path.relative_to(Path(__file__).resolve().parents[2])),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'tables':{t:len(rows) for t,rows in data.items()},'exact_restore_and_foreign_keys_verified':True,'hashed_authentication_rows_in_private_backup':True,'worker_secrets_read':False,'remote_writes':False,'native_time_travel_tested':False}
    out=Path(__file__).with_name(phase+'-complete-backup.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
