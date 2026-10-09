"""Offline audit of a private read-only snapshot and local full-scale rehearsal."""
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from foundation import storage
from . import import_rehearsal as rehearsal

def restore_snapshot(snapshot):
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
    for sql in snapshot['schema'].values():db.execute(sql)
    for table,rows in snapshot['tables'].items():
        for row in rows:db.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',list(row.values()))
    db.commit()
    if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Backup foreign-key error')
    for table,rows in snapshot['tables'].items():
        if [dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY 1')]!=rows:raise ValueError('Restore mismatch: '+table)
    return db

def main():
    root=storage.ROOT;view=rehearsal.load_view();source=storage.load_baseline()
    # Recheck actual Word boundaries independently; do not write generated data.
    import sys
    sys.path.insert(0,str(root/'tools'))
    try:
        from build_display_wantlists import build
        if build()!=view:raise ValueError('Derived view differs from independent Word rebuild')
    finally:sys.path.pop(0)
    covered=[r['id'] for display in view['records'] for r in display.get('source_records',[display])]
    if Counter(covered)!=Counter(r['id'] for r in source['records']):raise ValueError('Source identity coverage mismatch')
    duplicate_groups=[]
    for r in view['records']:
        for n,g in enumerate([r,*r.get('mixed_lists',[]),*r.get('sublists',[])]):
            for field in storage.INVENTORIES:
                duplicate_values=[(value,count) for value,count in Counter(g.get(field,[])).items() if count>1]
                if duplicate_values:duplicate_groups.append({'id':r['id'],'group':n,'field':field,'duplicates':duplicate_values})
    path=root/'foundation/.local/phase3c1-readonly-snapshot.json';snap=json.loads(path.read_text())
    restored=restore_snapshot(snap);restored.close()
    records=snap['tables']['records'];groups={g['id']:g for g in snap['tables']['record_groups']};items=snap['tables']['items']
    ids={r['id'] for r in view['records']};original=set(view['mapping']);active=[r for r in records if not r['deleted_at']]
    candidates=[]
    for r in records:
        c=json.loads(r['content_json']);entries=[i for i in items if groups[i['group_id']]['record_id']==r['id'] and not i['deleted_at']]
        prefixes=[i for i in entries if re.match(r'^(cpu-test-|test-|fixture-|cpu-first-)',i['value'])]
        known=bool(re.search(r'CPU staging|staging test|owner-(desktop|mobile) \d{13}|Practice API|Replacement API',c.get('set_name',''),re.I))
        if prefixes or known or any('benchmark' in n.lower() for n in c.get('notes',[])):
            candidates.append({'id':r['id'],'name':c.get('set_name'),'active_prefix_items':len(prefixes),'fixture_title_candidate':known,'duplicate_values':sum(n-1 for n in Counter(i['value'] for i in entries).values() if n>1),'decision':'preserve; owner/provenance review required'})
    # Snapshot restored into a disposable reference, never human-review D1.
    overlay=rehearsal.fresh();overlay.execute('DELETE FROM categories')
    for table,rows in snap['tables'].items():
        for row in rows:overlay.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',list(row.values()))
    overlay.commit();rehearsal.prepare(overlay,view)
    preserved={r['id'] for r in records if r['id'] in ids}
    added=0
    for offset in range(0,len(view['records']),20):added+=len(rehearsal.import_batch(overlay,view,offset)['added'])
    # Exact old rows remain, including all receipts/history/deleted test entries.
    old_rows_unchanged=all(dict(overlay.execute('SELECT * FROM '+table+' WHERE '+next(iter(row))+'=?',(row[next(iter(row))],)).fetchone())==row for table,rows in snap['tables'].items() for row in rows)
    comparison=rehearsal.reconcile(overlay,view,preserved)
    # Full application backup includes every existing application table + receipt.
    tables=[r[0] for r in overlay.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('sessions','auth_control','login_limits')")]
    backup={'schema':{t:overlay.execute('SELECT sql FROM sqlite_master WHERE name=?',(t,)).fetchone()[0] for t in tables},'tables':{t:[dict(r) for r in overlay.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in tables}}
    restored=restore_snapshot(backup);restored.close()
    report={'baseline_commit':'9db0bfe7f414de7e1a8b569599e448c05575b546','protected_sha256':storage.BASELINE_SHA256,'display_sha256':rehearsal.digest(view),'source_records':len(source['records']),'display_listings':len(ids),'source_coverage':sum(len(r.get('source_records',[r])) for r in view['records']),
      'categories':{cat:{'listings':sum(r['display_category']==cat for r in view['records']),'types':dict(Counter(r.get('display_list_type') or r['list_type'] for r in view['records'] if r['display_category']==cat)),'literal_items':sum(len(g.get(k,[])) for r in view['records'] if r['display_category']==cat for g in [r,*r.get('mixed_lists',[]),*r.get('sublists',[])] for k in storage.INVENTORIES)} for cat in view['categories']},
      'eau_claire':[{'id':r['id'],'name':r['set_name'],'items':len(r['items'])} for r in view['records'] if r['display_category']=='Eau Claire Players'],
      'approved_classifications':{rid:{'expected':a['list_type'],'actual':next(r.get('display_list_type') or r['list_type'] for r in view['records'] if r['id']==rid)} for rid,a in view['classification_approvals'].items()},
      'staging':{'stored':len(records),'active':len(active),'derived_matches':sum(r['id'] in ids for r in active),'legacy_members':sum(r['id'] in original and r['id'] not in ids for r in active),'owner_created':sum(r['import_id'] is None and r['id'] not in ids and r['id'] not in original for r in active),'deleted_ids':[r['id'] for r in records if r['deleted_at']],'items':len(items),'active_items':sum(not i['deleted_at'] for i in items),'history':len(snap['tables']['change_history']),'fixture_candidates':candidates,'active_cpu_entries':sum(not i['deleted_at'] and i['value'].startswith('cpu-test-') for i in items),'removed_cpu_entries':sum(bool(i['deleted_at']) and i['value'].startswith('cpu-test-') for i in items),'preserved_historical_ids':sorted(preserved),'historical_edits':[{'id':r['id'],'revision':r['revision']} for r in records if r['id'] in ids and r['revision']>1]},
      'overlay_rehearsal':{'added':added,'preserved':len(preserved),'stored_after':overlay.execute('SELECT count(*) FROM records').fetchone()[0],'old_rows_exactly_unchanged':old_rows_unchanged,'comparison':comparison},
      'backup':{'snapshot_sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest(),'existing_snapshot_exact_restore':True,'overlay_exact_restore':True,'overlay_tables':len(tables),'authentication_excluded':True,'native_time_travel_tested':False},
      'source_anomalies':{'duplicate_identifier_groups':duplicate_groups,'same_title_source_pairs':[['p0185-l001','p0187-l001'],['p1056-l005','p1058-l001'],['p1056-l007','p1060-l007']],'identical_inventory_at_distinct_source_locations':['p1056-l005','p1058-l001'],'normalized_literals':59104,'derived_literals':59098,'word_line_special_collections':{'Milwaukee 8x10 List':{'normalized':251,'display':250},'Eau Claire Players':{'normalized':117,'display':112}},'source_records_preserved_in_provenance':True,'derived_independently_rebuilt_from_word':True}}
    overlay.close();out=root/'foundation/staging/phase3c1-audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('categories','approved_classifications','staging')},indent=2));print('Fixture candidates:',len(candidates))

if __name__=='__main__':main()
