"""Resumable representative import into the explicitly isolated staging DB.

Never writes historical files. Every chunk's ledger and data commit in one D1
batch. Initialization refuses changed/live databases; partial imports cannot be
edited or treated as complete. Full-baseline import is intentionally NOT enabled.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
from foundation import storage
from .runner import ROOT, Client, state, sql
from .cloudflare import query

MAX_WRITES = 12000


def selection(baseline):
    records = baseline['records']
    ids = {'p1566-l003','p0672-l001','p0694-l001','p0730-l001'}
    def literals(r):
        return sum(len(g.get(k, [])) for g in [r,*r.get('mixed_lists',[]),*r.get('sublists',[])] for k in storage.INVENTORIES)
    for category in {r['category'] for r in records}:
        ids.add(next(r['id'] for r in records if r['category']==category))
    for mode in {r['list_type'] for r in records}:
        ids.add(next(r['id'] for r in records if r['list_type']==mode))
    ids.add(max(records,key=literals)['id'])
    ids.add(next(r['id'] for r in records if r.get('mixed_lists')))
    return [r for r in records if r['id'] in ids]


def build_chunks(baseline, selected):
    local=storage.connect();storage.apply_schema(local);storage.initialize(local,baseline)
    # Stable disposable import timestamps make chunk identities restartable.
    stamp='2026-10-07T00:00:00+00:00'
    local.execute('UPDATE records SET created_at=?,updated_at=?',(stamp,stamp))
    local.execute('UPDATE import_batches SET imported_at=?',(stamp,))
    selected_ids={r['id'] for r in selected}
    groups={r['id'] for r in local.execute('SELECT id,record_id FROM record_groups') if r['record_id'] in selected_ids}
    chunks=[];current=[]
    for table in storage.BACKUP_TABLES:
        if table in ('private_details','change_history'):continue
        rows=[]
        for row in local.execute(f'SELECT * FROM {table} ORDER BY 1'):
            if table in ('records','provenance') and row['id' if table=='records' else 'record_id'] not in selected_ids:continue
            if table=='record_groups' and row['id'] not in groups:continue
            if table=='items' and row['group_id'] not in groups:continue
            rows.append(tuple(row))
        if not rows:continue
        # At most 99 bound parameters per statement, below D1's 100 limit.
        size=max(1,99//len(rows[0]));columns=len(rows[0])
        for offset in range(0,len(rows),size):
            part=rows[offset:offset+size]
            current.append(sql(f'INSERT INTO {table} VALUES '+','.join('('+','.join('?' for _ in range(columns))+')' for _ in part),*[v for row in part for v in row]))
            if len(current)==40:chunks.append(current);current=[]
    if current:chunks.append(current)
    local.close();return chunks


def run():
    baseline=storage.load_baseline();selected=selection(baseline)
    digest=hashlib.sha256(storage.dumps(selected).encode()).hexdigest()
    c=Client();dbid=state()['database_id']
    existing=query(dbid,'SELECT * FROM staging_import_state WHERE id=1')[0]['results']
    if existing and (existing[0]['baseline_sha256']!=storage.BASELINE_SHA256 or existing[0]['selection_sha256']!=digest):raise ValueError('Wrong baseline/selection; use new staging storage')
    if query(dbid,'SELECT count(*) AS n FROM change_history')[0]['results'][0]['n'] or query(dbid,'SELECT count(*) AS n FROM records WHERE revision<>1 OR deleted_at IS NOT NULL OR import_id IS NULL')[0]['results'][0]['n']:raise ValueError('Initialization refused: live edits exist')
    chunks=build_chunks(baseline,selected)
    # Conservative preflight bound for these 960 literals plus indexes/parents.
    estimated=sum(len(g.get(k,[])) for r in selected for g in [r,*r.get('mixed_lists',[]),*r.get('sublists',[])] for k in storage.INVENTORIES)*5+len(selected)*20
    if estimated>MAX_WRITES:raise ValueError('Representative import exceeds staging write budget')
    if not existing:
        if query(dbid,'SELECT count(*) AS n FROM records')[0]['results'][0]['n']:raise ValueError('Not empty')
        c.batch([sql('INSERT INTO staging_import_state VALUES(1,?,?,?,0)',storage.BASELINE_SHA256,digest,len(selected))])
    used=0;skipped=0
    for index,statements in enumerate(chunks):
        cid=f'baseline-sample-{index:04d}';checksum=hashlib.sha256(storage.dumps(statements).encode()).hexdigest()
        done=query(dbid,'SELECT content_sha256 FROM staging_import_chunks WHERE id=?',[cid])[0]['results']
        if done:
            if done[0]['content_sha256']!=checksum:raise ValueError('Chunk identity differs')
            skipped+=1;continue
        if existing and existing[0]['completed']:raise ValueError('Completed import missing a chunk; refuse repair overwrite')
        if used+2000>MAX_WRITES:raise ValueError('Pause import at safe budget checkpoint')
        guard=f'import-guard-{cid}'
        guarded=[sql("INSERT INTO foundation_meta VALUES(?,CASE WHEN (SELECT completed FROM staging_import_state WHERE id=1)=0 AND NOT EXISTS(SELECT 1 FROM change_history LIMIT 1) THEN '1' ELSE NULL END)",guard),
                 *statements,sql('INSERT INTO staging_import_chunks VALUES(?,?,?,?)',cid,checksum,0,'2026-10-07T00:00:00+00:00'),sql('DELETE FROM foundation_meta WHERE key=?',guard)]
        result=c.batch(guarded);used+=result['rows_written']
        print('Import chunk',cid,'rows_read',result['rows_read'],'rows_written',result['rows_written'],flush=True)
    count=query(dbid,'SELECT count(*) AS n FROM records')[0]['results'][0]['n']
    if count!=len(selected):raise ValueError('Partial import; record count mismatch')
    # Content reconciliation must pass before marking complete, not just count.
    exported=storage.connect();storage.apply_schema(exported)
    for table in storage.BACKUP_TABLES:
        rows=query(dbid,f'SELECT * FROM {table} ORDER BY 1')[0]['results']
        for row in rows:
            cols=list(row);exported.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",[row[k] for k in cols])
    exported.commit()
    report=storage.reconcile(exported,{**baseline,'records':selected})
    if not report['passed']:raise ValueError('STOP: unexplained migration differences')
    c.batch([sql('UPDATE staging_import_state SET completed=1 WHERE id=1')])
    report.update(full_baseline_records=len(baseline['records']),subset=True,chunk_count=len(chunks),chunks_skipped=skipped,actual_import_rows_written=used,estimated_preflight_rows_written=estimated,max_staging_import_writes=MAX_WRITES)
    report_path=ROOT/'foundation/staging/import-result.json'
    if skipped and report_path.exists():
        original=json.loads(report_path.read_text());original['idempotent_rerun']={'chunks_skipped':skipped,'additional_import_rows_written':used,'reconciled':True};report=original
    report_path.write_text(json.dumps(report,indent=2))
    print('Reconciliation passed:',len(selected),'records;',report['literal_value_rows'],'literals;',used,'measured writes;',skipped,'chunks skipped')
    # Disposable local copy is ignored, used for portable export/restore tests.
    local=ROOT/'foundation/.local/staging-export.sqlite';out=storage.connect(local)
    exported.backup(out);out.close();exported.close()


if __name__=='__main__':run()
