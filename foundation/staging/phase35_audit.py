"""Read-only evidence and exact benchmark manifest. No deletion by appearance."""
import json,re,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def identify(snapshot):
 records=snapshot['tables']['records'];items=snapshot['tables']['items'];groups={g['id']:g for g in snapshot['tables']['record_groups']};history=snapshot['tables']['change_history']
 rid='p1237-l004';record=next(r for r in records if r['id']==rid);events=sorted([h for h in history if h['record_id']==rid],key=lambda h:(h['created_at'],h['id']))
 pattern=re.compile(r'^cpu-test-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-(1|2|20)-(\d+)$')
 benchmark=[i for i in items if not i['deleted_at'] and groups[i['group_id']]['record_id']==rid and i['value'].startswith('cpu-test-')]
 assert len(benchmark)==1403,'Contamination count changed: investigate before cleanup'
 rounds=collections.defaultdict(set);links={};last_add=''
 for h in events:
  after=json.loads(h['after_json'])
  if h['action']=='add':
   values=after.get('items',[])
   if any(i['value'].startswith('cpu-test-') for i in values):
    assert len(values) in (1,2,20) and all(pattern.fullmatch(i['value']) for i in values)
    for i in values:links[i['id']]=h
    last_add=max(last_add,h['created_at'])
 for i in benchmark:
  m=pattern.fullmatch(i['value']);assert m and i['id'] in links and i['state']=='wanted'
  assert next(v for v in json.loads(links[i['id']]['after_json'])['items'] if v['id']==i['id'])['value']==i['value']
  rounds[m[1]].add((int(m[2]),int(m[3])))
  # Every later item-specific or bulk/session history reference is checked.
  for h in events:
   if h['created_at']>links[i['id']]['created_at']:
    assert h['item_id']!=i['id'] and i['id'] not in h['before_json'] and i['id'] not in h['after_json'],'Later entry interaction requires review'
 signature={(size,n) for size in (1,2,20) for n in range(size)}
 assert len(rounds)==61 and all(v==signature for v in rounds.values())
 metadata_edits=[h for h in events if h['action']=='edit' and json.loads(h['after_json']).get('metadata')=={'brand':'Topps','year':'2027'}]
 assert len(metadata_edits)==61
 first=metadata_edits[0];before=json.loads(first['before_json'])['metadata'];assert before=={'brand':'Upper Deck','year':'2007'}
 assert not any(h['created_at']>metadata_edits[-1]['created_at'] and any(k in json.loads(h['after_json']).get('metadata',{}) for k in ('year','brand')) for h in events)
 current=json.loads(record['content_json']);assert current['year']=='2027' and current['brand']=='Topps'
 note_edits=[h for h in events if h['action']=='edit' and re.fullmatch(r'Disposable staging CPU benchmark \d+', '\n'.join(json.loads(h['after_json']).get('metadata',{}).get('notes',[])))]
 assert note_edits and current['notes']==json.loads(note_edits[-1]['after_json'])['metadata']['notes']
 first_notes=note_edits[0];original_notes=json.loads(first_notes['before_json'])['metadata']['notes']
 assert not any(h['created_at']>first_notes['created_at'] and h not in note_edits and 'notes' in json.loads(h['after_json']).get('metadata',{}) for h in events)
 before={**before,'notes':original_notes}
 manifest={'record_id':rid,'expected_revision':record['revision'],'rounds':61,'addition_events':len({h['id'] for h in links.values()}),'items':[{'id':i['id'],'value':i['value'],'group_id':i['group_id'],'addition_history_id':links[i['id']]['id']} for i in sorted(benchmark,key=lambda i:i['id'])],'restore_metadata':before,'pre_cleanup_notes':current['notes'],'benchmark_note_history_ids':[h['id'] for h in note_edits],'original_notes_verified':original_notes,'later_legitimate_events_preserved':sum(h['created_at']>metadata_edits[-1]['created_at'] for h in events),'exact_signature_verified':True}
 candidate_records=[]
 for r in records:
  content=json.loads(r['content_json']);known=bool(re.search(r'CPU staging|staging test|owner-(desktop|mobile) \d{13}|Practice API|Replacement API',content.get('set_name',''),re.I))
  entries=[i for i in items if groups[i['group_id']]['record_id']==r['id'] and not i['deleted_at']]
  prefixes=[i for i in entries if re.match(r'^(cpu-test-|test-|fixture-|cpu-first-)',i['value'])]
  if prefixes or known or any('benchmark' in n.lower() for n in content.get('notes',[])):
   candidate_records.append({'id':r['id'],'active_known_prefix_items':len(prefixes),'name':content.get('set_name'),'known_fixture_title_candidate':known,'benchmark_note':any('benchmark' in n.lower() for n in content.get('notes',[])),'duplicates':sum(n-1 for n in collections.Counter(i['value'] for i in entries).values() if n>1),'action':'only confirmed cpu-test entries authorized for cleanup; other records preserved for review'})
 manifest['audit_candidates']=candidate_records
 manifest['sha256']=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
 return manifest
