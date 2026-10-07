"""Resumable initial import via D1 HTTP API, never the public website.

Default: plan only. --execute imports ONLY the representative sample. Full
execution remains disabled pending separate approval. The same resumable engine
and chunk plan handle the full baseline; tests simulate multiple UTC days.

Daily reservations deliberately overcount. Never refund an uncertain attempt:
rollback, response loss and reservation writes can themselves consume quota.
The <=80k/day project budget leaves >=20k for other account activity; the
operator must verify other databases' usage and lower the budget if necessary.
"""
import datetime as dt
import hashlib
import json
import math
import sqlite3
import uuid
from pathlib import Path
from foundation import storage
from .import_baseline import build_chunks, selection
from .runner import ROOT
from .cloudflare import api, query

DEFAULT_BUDGET=80000

def literal(value):
    if value is None:return 'NULL'
    if isinstance(value,(int,float)):return str(value)
    if not isinstance(value,str):raise TypeError('Unsupported SQL value')
    if '\x00' in value:raise ValueError('NUL SQL literal is not supported')
    return "'"+value.replace("'","''")+"'"

def render(statement):
    parts=statement['sql'].split('?');params=statement['params']
    if len(parts)!=len(params)+1:raise ValueError('SQL placeholder mismatch')
    return ''.join(part+(literal(params[n]) if n<len(params) else '') for n,part in enumerate(parts))

def execute_sql(statements):return ';\n'.join(render(s) for s in statements)+';'

def plan(baseline,selected):
    raw=build_chunks(baseline,selected);chunks=[];current=[];size=0
    for old in raw:
      for statement in old:
        # HTTP API SQL has a finite text-size limit. Split by both byte size
        # and statement count, with strings quoted before sizing.
        columns=statement['sql'].split(' VALUES ')[1].split(')')[0].count('?')
        rows=[statement['params'][i:i+columns] for i in range(0,len(statement['params']),columns)]
        for row in rows:
          one={'sql':statement['sql'].split(' VALUES ')[0]+' VALUES ('+','.join('?' for _ in row)+')','params':row}
          length=len(render(one).encode())+2
          if length>1000000:raise ValueError('A literal row exceeds the safe bound-JSON value size; do not truncate it')
          if current and (size+length>60000 or len(current)>=300):chunks.append(current);current=[];size=0
          current.append(one);size+=length
    if current:chunks.append(current)
    local=storage.connect();storage.apply_schema(local)
    costs={table:1+2*len(list(local.execute('PRAGMA index_list('+table+')'))) for table in storage.BACKUP_TABLES};local.close()
    plans=[]
    for n,statements in enumerate(chunks):
        writes=64;records=0
        for s in statements:
            table=s['sql'].split()[2];rows=s['sql'].split(' VALUES ')[1].count('(')
            writes+=rows*costs[table]
            if table=='records':records+=rows
        plans.append({'id':f'baseline-{n:05d}','sha256':hashlib.sha256(storage.dumps(statements).encode()).hexdigest(),'statements':statements,'bound':writes,'records_added':records})
    return plans

def payload_schema():
    """Fixed table/column allowlist. Source rows remain verbatim bound JSON."""
    db=storage.connect();storage.apply_schema(db)
    statements=["CREATE TABLE IF NOT EXISTS import_chunk_payloads(id TEXT PRIMARY KEY,content_sha256 TEXT NOT NULL,records_added INTEGER NOT NULL,attempt_id TEXT NOT NULL REFERENCES import_write_attempts(id),payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),guard INTEGER NOT NULL CHECK(guard=1));", "CREATE TRIGGER IF NOT EXISTS import_payload_apply AFTER INSERT ON import_chunk_payloads BEGIN"]
    for table in storage.BACKUP_TABLES:
        if table in ('private_details','change_history'):continue
        columns=[r['name'] for r in db.execute('PRAGMA table_info('+table+')')]
        statements.append('INSERT INTO '+table+'('+','.join(columns)+') SELECT '+','.join("json_extract(value,'$["+str(n)+"]')" for n in range(len(columns)))+" FROM json_each(NEW.payload_json,'$."+table+"');")
    statements.extend(["INSERT INTO staging_import_chunks VALUES(NEW.id,NEW.content_sha256,NEW.records_added,strftime('%Y-%m-%dT%H:%M:%SZ','now'));", "UPDATE import_write_attempts SET completed=1 WHERE id=NEW.attempt_id;", "DELETE FROM import_chunk_payloads WHERE id=NEW.id;", 'END;'])
    db.close();return '\n'.join(statements)

class LocalTransport:
    """Same transactional SQL as D1, with an explicit test-only virtual day."""
    def __init__(self,db,day='2026-10-07'):self.db=db;self.day=day
    def rows(self,sql,params=()):return [dict(r) for r in self.db.execute(sql,params)]
    def batch(self,statements):
        with self.db:
            for s in statements:self.db.execute(s['sql'],s['params'])
        return None # Local SQLite does NOT measure D1 billed row writes.
    def today(self):return self.day

class D1Transport:
    def __init__(self,database):
        info=api('/d1/database/'+database)
        if info['name'] not in ('wantlist-staging','wantlist-staging-import-budget'):raise ValueError('Staging databases only')
        self.database=database
    def rows(self,sql,params=()):return query(self.database,sql,list(params))[0]['results']
    def batch(self,statements):
        if len(statements)==1:
            s=statements[0];results=query(self.database,s['sql'],s['params'])
            return sum(r['meta']['rows_written'] for r in results)
        results=query(self.database,execute_sql(statements))
        return sum(r['meta']['rows_written'] for r in results)
    def today(self):return self.rows("SELECT strftime('%Y-%m-%d','now') day")[0]['day']

class Importer:
    def __init__(self,transport,baseline,selected,budget=DEFAULT_BUDGET,progress=None):
        if not isinstance(budget,int) or not 100<=budget<=DEFAULT_BUDGET:raise ValueError('Budget must be 100..80,000')
        self.t=transport;self.progress=progress;self.baseline=baseline;self.selected=selected;self.budget=budget
        self.digest=hashlib.sha256(storage.dumps(selected).encode()).hexdigest();self.chunks=plan(baseline,selected)
    def unchanged(self):
        if self.t.rows('SELECT id FROM change_history LIMIT 1') or self.t.rows('SELECT id FROM records WHERE revision<>1 OR deleted_at IS NOT NULL OR import_id IS NULL LIMIT 1'):raise ValueError('Initialization refused: live edits exist')
    def run(self):
        self.unchanged();existing=self.t.rows('SELECT * FROM staging_import_state WHERE id=1')
        if existing:
            s=existing[0]
            if (s['baseline_sha256'],s['selection_sha256'],s['expected_records'])!=(storage.BASELINE_SHA256,self.digest,len(self.selected)):raise ValueError('Baseline/selection mismatch')
        else:
            if self.t.rows('SELECT id FROM records LIMIT 1') or self.t.rows('SELECT key FROM foundation_meta LIMIT 1'):raise ValueError('Initialization requires empty data')
            self.t.batch([{'sql':'INSERT INTO staging_import_state VALUES(1,?,?,?,0)','params':[storage.BASELINE_SHA256,self.digest,len(self.selected)]}])
        report={'expected_records':len(self.selected),'chunks_total':len(self.chunks),'completed_now':0,'skipped':0,'actual_chunk_writes':0,'local_metering_unavailable':isinstance(self.t,LocalTransport),'paused':False}
        for chunk in self.chunks:
            done=self.t.rows('SELECT content_sha256 FROM staging_import_chunks WHERE id=?',[chunk['id']])
            if done:
                if done[0]['content_sha256']!=chunk['sha256']:raise ValueError('Chunk checksum mismatch')
                report['skipped']+=1;continue
            if existing and existing[0]['completed']:raise ValueError('Completed import missing a chunk')
            day=self.t.today();used=self.t.rows('SELECT reserved,budget FROM import_write_days WHERE day=?',[day])
            if used and used[0]['budget']!=self.budget:raise ValueError('Daily budget cannot change mid-day')
            if (used[0]['reserved'] if used else 0)+chunk['bound']>self.budget:
                report['paused']=True;report['next_chunk']=chunk['id'];report['next_chunk_reserved_writes']=chunk['bound'];break
            attempt=str(uuid.uuid4())
            # Reservation and its receipt are atomic; the CHECK closes races.
            self.t.batch([
                {'sql':'INSERT INTO import_write_days VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET reserved=reserved+excluded.reserved','params':[day,chunk['bound'],self.budget]},
                {'sql':'INSERT INTO import_write_attempts(id,chunk_id,day,reserved) VALUES(?,?,?,?)','params':[attempt,chunk['id'],day,chunk['bound']]}])
            payload={}
            for statement in chunk['statements']:
                table=statement['sql'].split()[2];payload.setdefault(table,[]).append(statement['params'])
            guarded=[{'sql':"INSERT INTO import_chunk_payloads VALUES(?,?,?,?,?,CASE WHEN (SELECT completed FROM staging_import_state WHERE id=1)=0 AND NOT EXISTS(SELECT 1 FROM change_history LIMIT 1) AND NOT EXISTS(SELECT 1 FROM records WHERE revision<>1 OR deleted_at IS NOT NULL OR import_id IS NULL LIMIT 1) THEN 1 ELSE 0 END)",
                'params':[chunk['id'],chunk['sha256'],chunk['records_added'],attempt,storage.dumps(payload)]}]
            try:actual=self.t.batch(guarded)
            except Exception:
                # A lost response must not trigger a blind re-import. A later
                # run checks the atomic completion ledger; reservation remains.
                raise RuntimeError('Import stopped; reservation retained. Rerun to inspect completion ledger.') from None
            if actual is not None:
                if actual+32>chunk['bound']:raise RuntimeError('STOP: actual writes exceeded conservative bound')
                self.t.batch([{'sql':'UPDATE import_write_attempts SET actual=? WHERE id=?','params':[actual,attempt]}]);report['actual_chunk_writes']+=actual
            report['completed_now']+=1
            if self.progress:self.progress({'event':'chunk_complete','chunk':chunk['id'],'chunks_total':len(self.chunks),'reserved_writes':chunk['bound'],'actual_chunk_writes':actual})
        report['completed_chunks']=len(self.t.rows('SELECT id FROM staging_import_chunks'))
        report['imported_records']=self.t.rows('SELECT count(*) n FROM records')[0]['n']
        report['daily_reservations']=self.t.rows('SELECT * FROM import_write_days ORDER BY day')
        if report['completed_chunks']==len(self.chunks):
            # Exact baseline reconstruction, not just top-level counts.
            db=storage.connect();storage.apply_schema(db)
            for table in storage.BACKUP_TABLES:
                for row in self.t.rows(f'SELECT * FROM {table} ORDER BY 1'):
                    if table=='foundation_meta' and row['key'].startswith('quota-import-'):raise ValueError('Incomplete transaction')
                    keys=list(row);db.execute(f"INSERT INTO {table}({','.join(keys)}) VALUES({','.join('?' for _ in keys)})",[row[k] for k in keys])
            db.commit();reconciled=storage.reconcile(db,{**self.baseline,'records':self.selected});db.close()
            if not reconciled['passed']:raise ValueError('STOP: content reconciliation failed')
            # Completion is a small bounded write reserved in the final chunk.
            if not existing or not existing[0]['completed']:self.t.batch([{'sql':'UPDATE staging_import_state SET completed=1 WHERE id=1','params':[]}])
            report['reconciliation']=reconciled
        return report

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--database-id');p.add_argument('--budget',type=int,default=DEFAULT_BUDGET);a=p.parse_args()
    baseline=storage.load_baseline()
    if not a.execute:
        chunks=plan(baseline,baseline['records']);bound=sum(c['bound'] for c in chunks)
        print(json.dumps({'plan_only':True,'full_import_executed':False,'records':len(baseline['records']),'chunks':len(chunks),'conservative_reserved_writes':bound,'daily_budget':a.budget,'minimum_budget_days':math.ceil(bound/a.budget),'largest_chunk_bound':max(c['bound'] for c in chunks)},indent=2));return
    if not a.database_id:raise ValueError('--database-id required')
    report=Importer(D1Transport(a.database_id),baseline,selection(baseline),a.budget,progress=lambda event:print(json.dumps(event),flush=True)).run();print(json.dumps(report,indent=2))
if __name__=='__main__':main()
