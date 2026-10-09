"""Isolated concurrent import race: a competing record must survive unchanged."""
import json
from . import historical_import as h

def main():
 reg=json.loads((h.storage.ROOT/'foundation/.local/phase3c2-isolated.json').read_text());t=h.Remote(reg['database_id']);plan=h.manifest();ids={r['id'] for r in t.rows('SELECT id FROM records')};candidate=next(r for r in plan['records'] if r['id'] not in ids);plan['records']=[candidate]
 raw=t.statement;row=list(candidate['tables']['records'][0]);content=json.loads(row[3]);content['notes']=['Concurrent isolated owner fixture, preserve'];row[3]=h.storage.dumps(content);row[4]=17;cols=[r['name'] for r in t.rows('PRAGMA table_info(records)')];inserted=False
 def race(sql,args=()):
  nonlocal inserted
  if 'INSERT INTO derived_import_payloads' in sql and not inserted:
   raw('INSERT INTO records('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',row);inserted=True
  return raw(sql,args)
 t.statement=race;stopped=False
 try:h.Importer(t,plan).run(1)
 except RuntimeError:stopped=True
 assert stopped and inserted
 actual=t.rows('SELECT * FROM records WHERE id=?',[candidate['id']])[0];assert [actual[c] for c in cols]==row
 for table in ['record_groups','provenance','public_records','derived_import_receipts']:
  assert not t.rows('SELECT * FROM '+table+' WHERE record_id=?',[candidate['id']])
 t.statement=raw;retry=h.Importer(t,plan).run(1);assert retry['preserved']==[candidate['id']] and retry['reported_d1_usage']['rows_written']==0
 report={'resource':reg['worker'],'conflict_record_id':candidate['id'],'concurrent_root_preserved_exactly':True,'no_partial_inventory_projection_or_receipt':True,'retry_writes':0,'reservation_retained':True,'human_review_writes':False,'reported_usage':t.meter}
 (h.storage.ROOT/'foundation/staging/phase3c3-remote-conflict.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
def lost_response():
 reg=json.loads((h.storage.ROOT/'foundation/.local/phase3c2-isolated.json').read_text());t=h.Remote(reg['database_id']);plan=h.manifest();ids={r['id'] for r in t.rows('SELECT id FROM records')};candidate=next(r for r in plan['records'] if r['id'] not in ids);plan['records']=[candidate];raw=t.statement;lost=False
 def drop(sql,args=()):
  nonlocal lost
  value=raw(sql,args)
  if 'INSERT INTO derived_import_payloads' in sql and not lost:lost=True;raise ConnectionError('simulated lost committed response')
  return value
 t.statement=drop;result=h.Importer(t,plan).run(1);assert result['added']==[candidate['id']] and result['ambiguous_payload_responses']==1 and result['actual_writes'] is None
 t.statement=raw;retry=h.Importer(t,plan).run(1);assert retry['replayed']==[candidate['id']] and retry['actual_writes']==0
 report={'resource':reg['worker'],'record_id':candidate['id'],'committed_response_lost_then_receipt_recovered':True,'ambiguous_responses':1,'complete_actual_write_total_claimed':False,'retry_writes':0,'reported_usage':t.meter,'human_review_writes':False}
 (h.storage.ROOT/'foundation/staging/phase3c3-remote-lost-response.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lost-response',action='store_true');lost_response() if p.parse_args().lost_response else main()
