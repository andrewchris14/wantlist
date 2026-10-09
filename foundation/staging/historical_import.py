"""Checksummed derived import via one atomic D1 trigger per listing.

CLI execution is disposable-only in this phase. No Worker bulk execution, record
UPSERT, UPDATE or DELETE. Existing IDs, even removed ones, are always preserved.
"""
import hashlib,json,uuid,datetime
from pathlib import Path
from foundation import storage
from .import_rehearsal import load_view,rows_for
from .cloudflare import api,query,isolated_name

TABLES=('records','provenance','record_groups','items','public_records')

def sha(v):return hashlib.sha256(storage.dumps(v).encode()).hexdigest()

def projection(r,tables):
    content=json.loads(tables['records'][0][3])
    keys=('id','year','display_year','brand','set_name','category','display_category','section','notes','prefixes','uncertainty','set_size','entry_order','source_list_type','completed_sets','source_refs')
    p={k:content[k] for k in keys if k in content};p.update(list_type=tables['records'][0][2],revision=1,updated_at=tables['records'][0][6],deleted=False,projection_version=2,groups=[])
    for g in tables['record_groups']:
        m=json.loads(g[5]);body={'id':g[0],'kind':g[2],'list_type':g[4],**{k:m[k] for k in ('label','description','notes','source_list_type') if k in m}}
        body['entries']=[dict(zip(('id','value','position','field_key','state','actionable','pending_at','received_at'),(i[0],i[4],i[3],i[2],i[5],i[6],i[8],i[9]))) for i in sorted(tables['items'],key=lambda i:(i[2],i[3])) if i[1]==g[0]]
        p['groups'].append(body)
    return p

def manifest():
    view=load_view();records=[]
    for r in view['records']:
        tables=rows_for(r);row=list(tables['records'][0]);row[1]='derived-3c2';tables['records']=[row]
        p=projection(r,tables);tables['public_records']=[[r['id'],1,row[6],0,storage.dumps(p)]]
        source_hash=sha(r);payload_hash=sha(tables)
        # Overcounts indexes and quota/receipt/index-trigger bookkeeping.
        bound=100+sum(len(rows)*{'records':5,'provenance':3,'record_groups':5,'items':7,'public_records':7}[t] for t,rows in tables.items())
        records.append({'id':r['id'],'source_hash':source_hash,'payload_hash':payload_hash,'bound':bound,'tables':tables})
    identity={'approved_commit':'a9f92c96f2328f735c89dc3b9de4d488938190fa','baseline_sha256':storage.BASELINE_SHA256,'dataset_sha256':sha(view),'records':[{k:r[k] for k in ('id','source_hash','payload_hash','bound')} for r in records]}
    return {'hash':sha(identity),'identity':identity,'records':records}

def schema():
    db=storage.connect();storage.apply_schema(db);db.executescript((storage.ROOT/'foundation/staging/schema.sql').read_text())
    text=["CREATE TABLE IF NOT EXISTS derived_import_manifests(hash TEXT PRIMARY KEY,identity_json TEXT NOT NULL CHECK(json_valid(identity_json)));",
          "CREATE TABLE IF NOT EXISTS derived_import_days(day TEXT PRIMARY KEY,reserved INTEGER NOT NULL,budget INTEGER NOT NULL CHECK(budget BETWEEN 100 AND 80000),CHECK(reserved BETWEEN 0 AND budget));",
          "CREATE TABLE IF NOT EXISTS derived_import_attempts(id TEXT PRIMARY KEY,record_id TEXT NOT NULL,day TEXT NOT NULL REFERENCES derived_import_days(day),reserved INTEGER NOT NULL);",
          "CREATE TABLE IF NOT EXISTS derived_import_receipts(record_id TEXT PRIMARY KEY REFERENCES records(id),manifest_hash TEXT NOT NULL REFERENCES derived_import_manifests(hash),source_hash TEXT NOT NULL,payload_hash TEXT NOT NULL,attempt_id TEXT NOT NULL REFERENCES derived_import_attempts(id));",
          "CREATE TABLE IF NOT EXISTS derived_import_payloads(record_id TEXT PRIMARY KEY,manifest_hash TEXT NOT NULL,source_hash TEXT NOT NULL,payload_hash TEXT NOT NULL,attempt_id TEXT NOT NULL,payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),guard INTEGER NOT NULL CHECK(guard=1));",
          "CREATE TRIGGER IF NOT EXISTS derived_import_apply AFTER INSERT ON derived_import_payloads BEGIN"]
    for table in TABLES:
        cols=[r['name'] for r in db.execute('PRAGMA table_info('+table+')')]
        text.append('INSERT INTO '+table+'('+','.join(cols)+') SELECT '+','.join("json_extract(value,'$["+str(n)+"]')" for n in range(len(cols)))+" FROM json_each(NEW.payload_json,'$."+table+"');")
    text.extend(["INSERT INTO derived_import_receipts VALUES(NEW.record_id,NEW.manifest_hash,NEW.source_hash,NEW.payload_hash,NEW.attempt_id);","DELETE FROM derived_import_payloads WHERE record_id=NEW.record_id;",'END;']);db.close()
    return '\n'.join(text)

class Local:
    def __init__(self,db):self.db=db
    def rows(self,sql,args=()):return [dict(r) for r in self.db.execute(sql,args)]
    def statement(self,sql,args=()):
        with self.db:self.db.execute(sql,args)
        return None

class Remote:
    def __init__(self,database):
        if not isolated_name(api('/d1/database/'+database)['name']):raise ValueError('Phase 3C.2 execution requires a disposable named database; human-review import is disabled')
        self.database=database
    def rows(self,sql,args=()):return query(self.database,sql,list(args))[0]['results']
    def statement(self,sql,args=()):return sum(r['meta']['rows_written'] for r in query(self.database,sql,list(args)))

class Importer:
    def __init__(self,transport,plan,budget=60000):
        if not isinstance(budget,int) or not 100<=budget<=80000:raise ValueError('Free-safe budget required')
        self.t,self.plan,self.budget=transport,plan,budget
        if sha(plan['identity'])!=plan['hash']:raise ValueError('Manifest checksum mismatch')
        self.entries={r['id']:r for r in plan['identity']['records']}
    def prepare(self):
        p=self.plan
        old=self.t.rows('SELECT identity_json FROM derived_import_manifests WHERE hash=?',[p['hash']])
        if old and old[0]['identity_json']!=storage.dumps(p['identity']):raise ValueError('Manifest drift')
        if not old:self.t.statement('INSERT INTO derived_import_manifests VALUES(?,?)',[p['hash'],storage.dumps(p['identity'])])
        # Header alone is new; never changes existing baseline headers/records.
        old=self.t.rows("SELECT dataset_sha256 FROM import_batches WHERE id='derived-3c2'")
        if old and old[0]['dataset_sha256']!=p['identity']['dataset_sha256']:raise ValueError('Import header drift')
        if not old:self.t.statement('INSERT INTO import_batches VALUES(?,?,?,?,?)',['derived-3c2',p['identity']['approved_commit'],p['identity']['dataset_sha256'],storage.dumps(p['identity']),datetime.datetime.now(datetime.timezone.utc).isoformat()])
    def run(self,limit=20,day=None):
        if not isinstance(limit,int) or not 1<=limit<=3394:raise ValueError('Invalid controlled batch')
        report={'added':[],'preserved':[],'replayed':[],'actual_writes':0,'paused':False,'manifest':self.plan['hash']}
        day=day or self.t.rows("SELECT strftime('%Y-%m-%d','now') day")[0]['day']
        receipts={r['record_id']:r for r in self.t.rows('SELECT * FROM derived_import_receipts')}
        existing={r['id'] for r in self.t.rows('SELECT id FROM records')}
        for record in self.plan['records']:
            rid=record['id'];receipt=receipts.get(rid)
            if {k:record[k] for k in ('id','source_hash','payload_hash','bound')}!=self.entries.get(rid) or sha(record['tables'])!=record['payload_hash']:raise ValueError('Listing payload checksum mismatch')
            if receipt:
                if (receipt['manifest_hash'],receipt['source_hash'],receipt['payload_hash'])!=(self.plan['hash'],record['source_hash'],record['payload_hash']):raise ValueError('Receipt drift')
                if rid not in existing:raise ValueError('Missing receipted record; investigate')
                report['replayed'].append(rid);continue
            if rid in existing:report['preserved'].append(rid);continue
            if len(report['added'])>=limit:break
            attempt=str(uuid.uuid4());bound=record['bound']
            used=self.t.rows('SELECT reserved,budget FROM derived_import_days WHERE day=?',[day])
            if used and used[0]['budget']!=self.budget:raise ValueError('Do not change a reserved daily budget')
            if (used[0]['reserved'] if used else 0)+bound>self.budget:report['paused']=True;break
            # Atomic reservation is independent of uncertain later payload response.
            self.t.statement('INSERT INTO derived_import_days VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET reserved=CASE WHEN budget=excluded.budget THEN reserved+excluded.reserved ELSE NULL END',[day,bound,self.budget])
            self.t.statement('INSERT INTO derived_import_attempts VALUES(?,?,?,?)',[attempt,rid,day,bound])
            payload=storage.dumps(record['tables'])
            if len(payload.encode())>256*1024:raise ValueError('Oversize listing; stop rather than truncate')
            sql="INSERT INTO derived_import_payloads VALUES(?,?,?,?,?,?,CASE WHEN NOT EXISTS(SELECT 1 FROM records WHERE id=?) AND EXISTS(SELECT 1 FROM derived_import_manifests WHERE hash=?) AND EXISTS(SELECT 1 FROM derived_import_attempts WHERE id=? AND record_id=?) THEN 1 ELSE 0 END)"
            try:actual=self.t.statement(sql,[rid,self.plan['hash'],record['source_hash'],record['payload_hash'],attempt,payload,rid,self.plan['hash'],attempt,rid])
            except Exception:
                # Read receipt after ambiguous response; never blindly overwrite/retry.
                done=self.t.rows('SELECT * FROM derived_import_receipts WHERE record_id=?',[rid])
                if not done:raise RuntimeError('Stopped: reservation retained; inspect conflict or failed transaction before retry') from None
                if (done[0]['manifest_hash'],done[0]['source_hash'],done[0]['payload_hash'])!=(self.plan['hash'],record['source_hash'],record['payload_hash']):raise ValueError('Conflicting receipt')
                actual=None
            if actual is not None:
                if actual>bound:raise RuntimeError('Measured D1 writes exceeded reservation; stop')
                report['actual_writes']+=actual
            report['added'].append(rid)
        return report

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-isolated');p.add_argument('--limit',type=int,default=20);a=p.parse_args();plan=manifest()
    if not a.execute_isolated:print(json.dumps({'plan_only':True,'manifest':plan['hash'],'listings':3394,'literal_rows':59098},indent=2));return
    importer=Importer(Remote(a.execute_isolated),plan);importer.prepare();print(json.dumps(importer.run(a.limit),indent=2))
if __name__=='__main__':main()
