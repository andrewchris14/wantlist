"""LOCAL ONLY derived-collection rehearsal. No Cloudflare transport or execution flag.

This is a safety reference, not a deployable D1 importer. Existing IDs, including
soft-deleted records, are never updated. Receipt and new listing commit together.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
from foundation import storage

ROOT = storage.ROOT
VIEW = ROOT / 'foundation/staging/historical-view.json'
STAMP = '2026-10-09T00:00:00Z'

def digest(value):
    return hashlib.sha256(storage.dumps(value).encode()).hexdigest()

def fresh(path=':memory:'):
    if str(path) != ':memory:' and Path(path).exists():
        raise ValueError('Use a NEW disposable SQLite file')
    db = storage.connect(path)
    storage.apply_schema(db)
    db.executescript((ROOT/'foundation/staging/schema.sql').read_text())
    db.executescript((ROOT/'foundation/staging/categories.sql').read_text())
    return db

def load_view():
    view = json.loads(VIEW.read_text())
    if view['baseline_sha256'] != storage.BASELINE_SHA256:
        raise ValueError('Wrong protected baseline')
    if len(view['records']) != 3394 or len({r['id'] for r in view['records']}) != 3394:
        raise ValueError('Unexpected display identity count')
    return view

def rows_for(record):
    """Retain full source evidence in provenance; never parse prose or ranges."""
    r = record
    mode = r.get('display_list_type') or r['list_type']
    content = {k:v for k,v in r.items() if k not in (*storage.INVENTORIES, 'mixed_lists', 'sublists', 'list_type', 'source_records', 'source_wording', 'source_group', 'section_line_ledger')}
    content['source_list_type'] = r.get('source_list_type', r['list_type'])
    tables = {
        'records': [(r['id'], 'rehearsal-derived', mode, storage.dumps(content), 1, STAMP, STAMP, None)],
        'provenance': [(r['id'], storage.dumps(r), digest(r), storage.dumps(r['source_refs']))],
        'record_groups': [], 'items': [],
    }
    groups = [('primary', 0, r)] + [('mixed', i, g) for i,g in enumerate(r.get('mixed_lists', []))] + [('sublist', i, g) for i,g in enumerate(r.get('sublists', []))]
    for kind, pos, g in groups:
        gid = f"{r['id']}:{kind}:{pos}"
        gm = mode if kind == 'primary' else g.get('list_type', mode)
        keys = [k for k in storage.INVENTORIES if k in g]
        metadata = {} if kind == 'primary' else {k:v for k,v in g.items() if k not in storage.INVENTORIES}
        tables['record_groups'].append((gid,r['id'],kind,pos,gm,storage.dumps(metadata),storage.dumps(keys)))
        for key in keys:
            for i,value in enumerate(g[key]):
                if not isinstance(value,str) or not value:
                    raise ValueError('Invalid literal; never truncate or discard')
                state, action, reason = storage.materialize({**r,'list_type':mode}, {**g,'list_type':gm}, key)
                # Actual Word-line names in these collections are individual items.
                if key == 'items' and r['display_category'] in ('Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist') and gm in ('want_list','have_list'):
                    state,action,reason = ('wanted' if gm=='want_list' else 'owned'),1,None
                tables['items'].append((f'{gid}:{key}:{i}',gid,key,i,value,state,action,reason,None,None,None))
    return tables

def prepare(db, view):
    db.execute('CREATE TABLE IF NOT EXISTS rehearsal_receipts(record_id TEXT PRIMARY KEY, dataset_hash TEXT NOT NULL, row_hash TEXT NOT NULL)')
    old=db.execute("SELECT dataset_sha256 FROM import_batches WHERE id='rehearsal-derived'").fetchone()
    if old and old[0]!=digest(view):raise ValueError('Prepared dataset drift')
    db.execute('INSERT OR IGNORE INTO import_batches VALUES(?,?,?,?,?)', ('rehearsal-derived','9db0bfe7f414de7e1a8b569599e448c05575b546',digest(view),storage.dumps({'local_only':True,'baseline_sha256':storage.BASELINE_SHA256}),STAMP))
    db.commit()

def import_batch(db, view, offset, size=20, fail_after=None):
    if not isinstance(size,int) or not 1 <= size <= 50:
        raise ValueError('Batch size must be 1..50')
    added, preserved = [], []
    view_hash = digest(view)
    prepared=db.execute("SELECT dataset_sha256 FROM import_batches WHERE id='rehearsal-derived'").fetchone()
    if not prepared or prepared[0]!=view_hash:raise ValueError('Prepare and verify the same dataset before importing')
    # Deliberately per-listing atomic. Earlier completed listings survive failure.
    for r in view['records'][offset:offset+size]:
        receipt = db.execute('SELECT * FROM rehearsal_receipts WHERE record_id=?',(r['id'],)).fetchone()
        if receipt and (receipt['dataset_hash'],receipt['row_hash']) != (view_hash,digest(r)):
            raise ValueError('Dataset drift; stop instead of overwrite')
        if db.execute('SELECT id FROM records WHERE id=?',(r['id'],)).fetchone():
            preserved.append(r['id']); continue
        if receipt:
            raise ValueError('Receipt exists but record missing; investigate')
        tables = rows_for(r)
        with db:
            for table, rows in tables.items():
                for row in rows:
                    db.execute('INSERT INTO '+table+' VALUES('+','.join('?' for _ in row)+')',row)
                    if fail_after is not None:
                        fail_after -= 1
                        if fail_after == 0: raise RuntimeError('Simulated interrupted listing transaction')
            db.execute('INSERT INTO rehearsal_receipts VALUES(?,?,?)',(r['id'],view_hash,digest(r)))
        added.append(r['id'])
    return {'added':added,'preserved':preserved,'next_offset':min(offset+size,len(view['records']))}

def reconcile(db, view, preserved=()):
    differences=[]
    for r in view['records']:
        if r['id'] in preserved: continue
        expected = rows_for(r)
        for table, rows in expected.items():
            if table=='record_groups': actual=db.execute('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position',(r['id'],)).fetchall(); rows=sorted(rows,key=lambda x:(x[2],x[3]))
            elif table=='items': actual=db.execute('SELECT i.* FROM items i JOIN record_groups g ON g.id=i.group_id WHERE g.record_id=? ORDER BY i.id',(r['id'],)).fetchall(); rows=sorted(rows,key=lambda x:x[0])
            else: actual=db.execute('SELECT * FROM '+table+' WHERE '+('id' if table=='records' else 'record_id')+'=?',(r['id'],)).fetchall()
            if [tuple(row) for row in actual] != rows: differences.append({'id':r['id'],'table':table})
    foreign_errors=len(db.execute('PRAGMA foreign_key_check').fetchall())
    return {'passed':not differences and not foreign_errors,'differences':differences,'preserved_existing':len(preserved),'foreign_key_errors':foreign_errors}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    path=Path(a.output).resolve()
    if not path.is_relative_to(ROOT/'work'):
        raise ValueError('Rehearsal outputs must be in ignored work/')
    view=load_view();db=fresh(path);prepare(db,view)
    for offset in range(0,len(view['records']),20): import_batch(db,view,offset)
    result=reconcile(db,view)
    if not result['passed']:raise ValueError('Full local reconciliation failed')
    result.update(local_only=True,listings=len(view['records']),items=db.execute('SELECT count(*) FROM items').fetchone()[0],groups=db.execute('SELECT count(*) FROM record_groups').fetchone()[0],categories=dict(Counter(r['display_category'] for r in view['records'])),list_types=dict(Counter(r.get('display_list_type') or r['list_type'] for r in view['records'])))
    print(json.dumps(result,indent=2));db.close()

if __name__=='__main__': main()
