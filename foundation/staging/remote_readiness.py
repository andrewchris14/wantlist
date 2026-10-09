"""Larger real D1 rehearsal, disposable-only; no Worker or staging mutations.

Use the private disposable registry from Phase 3C.2. The daily import ledger is
honored, including deliberately failed attempts. CLI never changes its budget.
"""
import argparse,copy,datetime,json,time
from pathlib import Path
from . import historical_import as h

ROOT=h.storage.ROOT

def run(limit=200):
    if not 1<=limit<=250:raise ValueError('Controlled isolated rehearsal only')
    registry=json.loads((ROOT/'foundation/.local/phase3c2-isolated.json').read_text())
    t=h.Remote(registry['database_id']);plan=h.manifest();i=h.Importer(t,plan);i.prepare()
    before=t.rows('SELECT count(*) n FROM records')[0]['n'];start=time.monotonic();batches=[]
    # Explicit batch boundaries demonstrate resume via server receipts.
    remaining=limit
    while remaining:
        result=i.run(min(20,remaining));batches.append(result);remaining-=len(result['added'])
        if result['paused'] or not result['added']:break
        print('Committed isolated batch:',len(result['added']),flush=True)
    elapsed=time.monotonic()-start;raw=t.statement
    def subset(records):return {**plan,'records':records}
    def absent():
        ids={r['id'] for r in t.rows('SELECT id FROM records')}
        return [r for r in plan['records'] if r['id'] not in ids]
    # Preserve a deliberately removed/edited existing historical-ID fixture.
    candidate=absent()[0];row=list(candidate['tables']['records'][0]);content=json.loads(row[3]);content['notes']=['Isolated owner-edit preservation fixture'];row[2]='have_list';row[3]=h.storage.dumps(content);row[4]=12;row[7]='isolated removal'
    cols=[x['name'] for x in t.rows('PRAGMA table_info(records)')]
    raw('INSERT INTO records('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',row)
    record_before=t.rows('SELECT * FROM records WHERE id=?',[candidate['id']]);preserve=h.Importer(t,subset([candidate])).run(1)
    assert candidate['id'] in preserve['preserved'] and record_before==t.rows('SELECT * FROM records WHERE id=?',[candidate['id']])
    # A malformed payload must roll back every listing table and leave reservation.
    bad=absent()[0]
    def corrupt(sql,args=()):
        if 'INSERT INTO derived_import_payloads' in sql:
            args=list(args);payload=json.loads(args[5]);payload['records'][0][3]='{"id":"invalid"}';args[5]=json.dumps(payload)
        return raw(sql,args)
    t.statement=corrupt;failed=False
    try:h.Importer(t,subset([bad])).run(1)
    except RuntimeError:failed=True
    assert failed
    for table,key in [('records','id'),('provenance','record_id'),('record_groups','record_id'),('public_records','record_id'),('derived_import_receipts','record_id')]:
        assert not t.rows('SELECT * FROM '+table+' WHERE '+key+'=?',[bad['id']])
    t.statement=raw;recovered=h.Importer(t,subset([bad])).run(1);assert recovered['added']==[bad['id']]
    # Interrupt after two committed payloads; next batch must replay those roots.
    targets=absent()[:4];commits=0
    def interrupt(sql,args=()):
        nonlocal commits
        if 'INSERT INTO derived_import_payloads' in sql and commits==2:raise ConnectionError('isolated interruption before third commit')
        value=raw(sql,args)
        if 'INSERT INTO derived_import_payloads' in sql:commits+=1
        return value
    t.statement=interrupt;stopped=False
    try:h.Importer(t,subset(targets)).run(4)
    except RuntimeError:stopped=True
    assert stopped and commits==2
    t.statement=raw;resumed=h.Importer(t,subset(targets)).run(4)
    assert resumed['added']==[r['id'] for r in targets[2:]] and set(resumed['replayed'])=={r['id'] for r in targets[:2]}
    retry=h.Importer(t,subset(targets)).run(4);assert not retry['added'] and retry['reported_d1_usage']['rows_written']==0
    report={'resource':registry['worker'],'started_from_records':before,'added_in_controlled_batches':sum(len(b['added']) for b in batches),'batch_sizes':[len(b['added']) for b in batches],'batch_elapsed_api_wall_seconds_not_cpu':round(elapsed,3),'batch_usage':{k:sum(b['reported_d1_usage'][k] for b in batches) for k in t.meter},'conservative_ledger':t.rows('SELECT * FROM derived_import_days'),'preserved_removed_owner_fixture':candidate['id'],'malformed_atomic_rollback_and_retry':True,'interrupted_after_two_commits_resumed':True,'retry_writes':0,'remote_records':t.rows('SELECT count(*) n FROM records')[0]['n'],'remote_receipts':t.rows('SELECT count(*) n FROM derived_import_receipts')[0]['n'],'full_remote_collection':False,'human_review_writes':False,'cpu_measurement':None}
    report['database_bytes']=h.api('/d1/database/'+registry['database_id']).get('file_size')
    path=ROOT/'foundation/staging/phase3c3-remote-rehearsal.json';path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--limit',type=int,default=200);run(a.parse_args().limit)
