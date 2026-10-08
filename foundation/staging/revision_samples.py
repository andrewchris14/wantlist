"""Append ONLY three derived section samples. Never initializes/resets live DB.
Idempotent: existing identities are checked and never overwritten, even after edits.
"""
import json,secrets,uuid,hashlib
from pathlib import Path
from foundation import storage
from .runner import ROOT,Client,state,sql
from .cloudflare import query

def run():
 view=json.loads((ROOT/'data/display-wantlists.json').read_text());selected=[r for r in view['records'] if r['id'].startswith('display-')];assert len(selected)==3
 local=storage.connect();storage.apply_schema(local)
 # The historical initializer remains unchanged and is never used for a derived
 # baseline. These three supplemental records have explicit source provenance.
 stamp=storage.now();local.execute('INSERT INTO import_batches VALUES (?,?,?,?,?)',('display-sections-v1',storage.BASELINE_COMMIT,hashlib.sha256(storage.dumps(selected).encode()).hexdigest(),storage.dumps({'baseline_sha256':view['baseline_sha256'],'derivation':'tools/build_display_wantlists.py','sample_only':True}),stamp))
 for record in selected:
  content={k:v for k,v in record.items() if k not in (*storage.INVENTORIES,'mixed_lists','sublists','list_type')}
  local.execute('INSERT INTO records VALUES (?,?,?,?,1,?,?,NULL)',(record['id'],'display-sections-v1',record['list_type'],storage.dumps(content),stamp,stamp))
  local.execute('INSERT INTO provenance VALUES (?,?,?,?)',(record['id'],storage.dumps(record),hashlib.sha256(storage.dumps(record).encode()).hexdigest(),storage.dumps(record['source_refs'])))
  sources=[('primary',0,record)]+[('mixed',i,g) for i,g in enumerate(record.get('mixed_lists',[]))]+[('sublist',i,g) for i,g in enumerate(record.get('sublists',[]))]
  for kind,position,g in sources:
   gid=f"{record['id']}:{kind}:{position}";metadata={} if kind=='primary' else {k:v for k,v in g.items() if k not in storage.INVENTORIES};keys=[k for k in storage.INVENTORIES if k in g]
   local.execute('INSERT INTO record_groups VALUES (?,?,?,?,?,?,?)',(gid,record['id'],kind,position,g.get('list_type',record['list_type']),storage.dumps(metadata),storage.dumps(keys)))
   for key in keys:
    state_,actionable,limitation=storage.materialize(record,g,key)
    for i,value in enumerate(g[key]):local.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL)',(f'{gid}:{key}:{i}',gid,key,i,value,state_,actionable,limitation))
 # Exact line-derived names in these explicitly WANT/HAVE sections are literal
 # item identities. No comma/range splitting or checklist complements.
 local.execute("UPDATE items SET actionable=1,state=(SELECT CASE g.list_type WHEN 'want_list' THEN 'wanted' WHEN 'have_list' THEN 'owned' END FROM record_groups g WHERE g.id=items.group_id),limitation=NULL WHERE field_key='items' AND group_id IN (SELECT id FROM record_groups WHERE record_id!='display-eau-claire-players' AND list_type IN ('want_list','have_list'))")
 local.commit();c=Client();db=state()['database_id'];writes=0;inserted=[]
 batches=[dict(r) for r in local.execute('SELECT * FROM import_batches')]
 for row in batches:
  if not query(db,'SELECT id FROM import_batches WHERE id=?',[row['id']])[0]['results']:
   c.batch([sql('INSERT INTO import_batches VALUES('+','.join('?' for _ in row)+')',*row.values())])
 for record in selected:
  rid=record['id'];existing=query(db,'SELECT id FROM records WHERE id=?',[rid])[0]['results']
  if existing:
   saved=query(db,'SELECT baseline_sha256 FROM provenance WHERE record_id=?',[rid])[0]['results']
   assert saved and saved[0]['baseline_sha256']==hashlib.sha256(storage.dumps(record).encode()).hexdigest(),'Existing derived source differs: stop; never overwrite live edits'
   continue
  statements=[];gids=[r['id'] for r in local.execute('SELECT id FROM record_groups WHERE record_id=?',(rid,))]
  for table in ('records','record_groups','items','provenance'):
   rows=[dict(r) for r in local.execute('SELECT * FROM '+table) if (r['id']==rid if table=='records' else r['record_id']==rid if table in ('record_groups','provenance') else r['group_id'] in gids)]
   for row in rows:statements.append(sql('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',*row.values()))
  # Entire small section imports atomically, with batched literals below100 bindings.
  compact=[]
  for table in ('records','record_groups','items','provenance'):
   same=[s for s in statements if s['sql'].startswith('INSERT INTO '+table+'(')]
   if not same:continue
   columns=len(same[0]['params']);size=99//columns
   for at in range(0,len(same),size):
    part=same[at:at+size];base=part[0]['sql'].split(' VALUES')[0]
    compact.append(sql(base+' VALUES '+','.join('('+','.join('?' for _ in range(columns))+')' for s in part),*[v for s in part for v in s['params']]))
  assert len(compact)<=44
  result=c.batch(compact);writes+=result['rows_written'];inserted.append(rid)
  assert c.call('/test/publish',{'record_id':rid})['status']==200
 assert writes<10000
 print('Section sample additions:',len(inserted),'D1 writes:',writes,'full baseline import: false')
 local.close()
if __name__=='__main__':run()
