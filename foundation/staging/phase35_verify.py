"""Read-only post-release checks and preservation comparison against fresh backup."""
import json,urllib.request,urllib.error,hashlib,collections,re
from pathlib import Path
from .phase34_operator import settings,ORIGIN
from .cloudflare import query,api
ROOT=Path(__file__).resolve().parents[2]
def verify():
 s,db=settings();q=lambda sql,params=None:query(db,sql,params)[0]['results']
 old=json.loads((ROOT/'foundation/.local/phase35-pre-maintenance.json').read_text())['tables'];manifest=json.loads((ROOT/'foundation/staging/phase35-cleanup-manifest.json').read_text());ids={r['id'] for r in manifest['items']}
 records=q('SELECT * FROM records ORDER BY id');byid={r['id']:r for r in records};items=q('SELECT * FROM items ORDER BY id');byitem={i['id']:i for i in items};groups=q('SELECT * FROM record_groups ORDER BY id');bygroup={g['id']:g for g in groups};hist=q('SELECT * FROM change_history ORDER BY id');byhistory={h['id']:h for h in hist}
 assert all(byhistory[h['id']]==h for h in old['change_history'])
 for r in old['records']:
  if r['id'] not in ('p1237-l004','display-eau-claire-players'):assert byid[r['id']]==r
 original=next(r for r in old['records'] if r['id']=='p1237-l004');current=byid[original['id']];expected=json.loads(original['content_json']);expected.update(manifest['restore_metadata']);assert json.loads(current['content_json'])==expected and current['revision']==original['revision']+1
 moved={g['id'] for g in old['record_groups'] if g['record_id']=='display-eau-claire-players' and g['kind']=='sublist'}
 for i in old['items']:
  after=byitem[i['id']];copy=dict(after)
  if i['id'] in ids:assert after['deleted_at'];copy['deleted_at']=i['deleted_at']
  elif i['group_id'] in moved:assert after['actionable']==1 and after['state']=='wanted' and after['limitation'] is None;copy.update({k:i[k] for k in ('actionable','state','limitation')})
  assert copy==i
 assert len(items)==len(old['items'])
 for g in old['record_groups']:
  copy=dict(bygroup[g['id']])
  if g['id'] in moved:assert copy['record_id'].startswith('display-eau-claire-');copy['record_id']=g['record_id']
  assert copy==g
 live_provenance={p['record_id']:p for p in q('SELECT * FROM provenance')}
 for p in old['provenance']:assert live_provenance[p['record_id']]==p
 classifications={'p0060-l001':'complete','p0273-l029':'complete','p0273-l039':'want_list','p1996-l008':'complete','p2501-l001':'complete','p2851-l007':'complete','p3022-l006':'have_list'}
 assert all(byid[id]['list_type']==mode for id,mode in classifications.items())
 stage=q("SELECT json_extract(content_json,'$.display_category') category,count(*) n FROM records WHERE deleted_at IS NULL GROUP BY category")
 report={'record_counts':{'total':len(records),'active':sum(r['deleted_at'] is None for r in records)},'items':len(items),'history_events':len(hist),'cleanup':{'record':'p1237-l004','revision':current['revision'],'soft_removed':len(ids),'remaining_active_cpu_test':q("SELECT count(*) n FROM items WHERE value LIKE 'cpu-test-%' AND deleted_at IS NULL")[0]['n'],'metadata':{k:expected[k] for k in ('year','brand','notes')},'all_other_item_properties_preserved':True,'all_prior_history_preserved':True},'eau':[{'id':id,'name':json.loads(byid[id]['content_json'])['set_name'],'active_entries':q('SELECT count(*) n FROM items i JOIN record_groups g ON g.id=i.group_id WHERE g.record_id=? AND i.deleted_at IS NULL',[id])[0]['n']} for id in ('display-eau-claire-1','display-eau-claire-2','display-eau-claire-3')],'historical_staging_categories':stage,'approved_classifications':classifications,'old_records_unchanged_except_reviewed_targets':True,'protected_existing_provenance_unchanged':True,'owner_created_records_preserved':sum(r['id'].startswith('owner-record-') for r in records),'other_review_candidates':manifest['audit_candidates'][1:] if manifest['audit_candidates'][0]['id']=='p1237-l004' else [r for r in manifest['audit_candidates'] if r['id']!='p1237-l004'],'test_storage_enabled':any(b['name']=='ISOLATED_TEST_STORAGE' and b.get('text')=='true' for b in s['bindings']),'maintenance_gate_enabled':any(b['name']=='PHASE35_MAINTENANCE_DIGEST' for b in s['bindings']),'public_checks':{}}
 def get(path,method='GET'):
  request=urllib.request.Request(ORIGIN+path,headers={'User-Agent':'Mozilla/5.0',**({'Content-Type':'application/json','Origin':ORIGIN} if method=='POST' else {})},method=method,data=b'{}' if method=='POST' else None)
  try:
   with urllib.request.urlopen(request,timeout=30) as response:return response.status,response.read()
  except urllib.error.HTTPError as error:return error.code,error.read()
 for path,status in [('/',200),('/public/categories',200),('/owner/record?id=p1237-l004',401)]:
  actual,body=get(path);assert actual==status;report['public_checks'][path]=actual
  if path=='/':assert b"Jason's Want List" in body;assert body==(ROOT/'foundation/.local/editor-dist/index.html').read_bytes()
 for path in ['/operator/phase35-maintenance','/test/batch']:
  status,_=get(path,'POST');assert status==403;report['public_checks'][path]=status
 for id in ['p1237-l004','display-eau-claire-1','display-eau-claire-2','display-eau-claire-3','display-milwaukee-8x10-list']:
  status,body=get('/public/record?id='+id);assert status==200;public=json.loads(body)
  assert not any(i['value'].startswith('cpu-test-') for g in public['groups'] for i in g['entries'])
  if id=='p1237-l004':assert public['year']=='2007' and public['brand']=='Upper Deck' and public['notes']==[];assert any(i['value']=='1' and i['state']=='pending' for g in public['groups'] for i in g['entries'])
 view=json.loads((ROOT/'foundation/staging/historical-view.json').read_text());report['derived_display_count']=len(view['records']);report['derived_category_counts']=view['display_category_counts'];report['derived_classifications']=dict(collections.Counter(r.get('display_list_type') or r['list_type'] for r in view['records']))
 duplicate_counts=collections.Counter((i['group_id'],i['value']) for i in items if not i['deleted_at'])
 report['all_staging_duplicate_value_candidates']=[{'record_id':bygroup[gid]['record_id'],'group_id':gid,'value':value,'count':count,'item_ids':[i['id'] for i in items if i['group_id']==gid and i['value']==value and not i['deleted_at']],'action':'preserved; source/group/history review required'} for (gid,value),count in duplicate_counts.items() if count>1]
 report['owner_group_review_candidates']=[]
 for g in groups:
  if g['id'].startswith('owner-group-'):
   count=sum(i['group_id']==g['id'] and not i['deleted_at'] for i in items)
   if g['list_type']!=byid[g['record_id']]['list_type'] or not count:report['owner_group_review_candidates'].append({'record_id':g['record_id'],'group_id':g['id'],'group_type':g['list_type'],'record_type':byid[g['record_id']]['list_type'],'active_entries':count,'action':'preserved; empty/recovery/mixed groups can be legitimate'})
 report['database_size_bytes']=api('/d1/database/'+db).get('file_size')
 (ROOT/'foundation/staging/phase35-verification-result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='other_review_candidates'},indent=2))
 return report
if __name__=='__main__':verify()
