"""Actual staging-only replacement/PIN checks; no secret or token in report."""
import json,time,uuid,statistics
from datetime import datetime,timezone
from .runner import Client,ROOT,sql,state
from .cloudflare import metrics_groups,WORKER,query
PATH=ROOT/'foundation/staging/revision-verification-result.json'
def utc():return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def run():
 c=Client();c.wait_ready();c.batch([sql('DELETE FROM login_limits')]);checks={};samples=[]
 def expect(label,r,status=200):
  assert r['status']==status,(label,r['status']);checks[label]=True;return r['body']
 expect('pin_login',c.login());checks['remembered_cookie_secure']=all(x in c.measurements[-1].get('cookie_flags','') for x in ('Secure','HttpOnly','SameSite=Strict','Max-Age=7776000'));assert checks['remembered_cookie_secure']
 r=expect('create_have_future_set',c.call('/action',{'op':'create','request_id':str(uuid.uuid4()),'metadata':{'year':'2027','brand':'Topps','set_name':'2027 Replacement API Practice','category':'baseball_cards','display_category':'OBC Wantlist'},'list_type':'have_list','owned':['1','3','5','7','9']}));rid=r['record_id'];rev=r['revision'];full=expect('owner_read',c.call('/owner/record?id='+rid));g=full['groups'][0]['id'];old_id=full['groups'][0]['entries'][0]['id'];start=utc()
 def replace(mode,values,diag=False):
  nonlocal rev
  time.sleep(1.05);beg=utc();body={'op':'replace_list','request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev,'group_id':g,'list_type':mode,'values':values};r=c.call('/action',body,instrumented=diag);end=utc();expect(mode,r);rev=r['body']['revision'];samples.append({'operation':mode,'started':beg,'ended':end,**{k:r[k] for k in ('status','client_wall_ms','instrumented','rows_read','rows_written','d1_duration_ms')}});return body
 for n in range(5):replace('want_list',['6','8','10']);replace('have_list',['2','4'])
 replace('want_list',['6','8','10'],True);last=replace('have_list',['2','4'],True)
 expect('old_representation_individual_restore_rejected',c.call('/action',{'op':'restore_item','request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev,'item_id':old_id}),400)
 expect('duplicate_retry_receipt',c.call('/action',last));public=expect('exact_have_public_projection',c.call('/public/record?id='+rid));assert public['list_type']=='have_list' and [e['value'] for e in public['groups'][0]['entries']]==['2','4'];checks['no_inferred_complement']=True
 h=expect('recent_changes',c.call('/owner/recent'))['changes'][0];assert h['action']=='replace_list' and h['undoable'];r=expect('undo_replacement',c.call('/action',{'op':'undo','request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev,'history_id':h['id']}));rev=r['revision'];public=expect('undo_exact_previous_projection',c.call('/public/record?id='+rid));assert [e['value'] for e in public['groups'][0]['entries']]==['6','8','10'] and public['list_type']=='want_list'
 expect('stale_undo_rejected',c.call('/action',{'op':'undo','request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev,'history_id':h['id']}),409)
 expect('internal_restore_cannot_bypass_undo',c.call('/action',{'op':'restore_representation','replacement_history':h['id'],'request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev}),400)
 expect('metadata_relabel_rejected',c.call('/action',{'op':'edit','list_type':'have_list','request_id':str(uuid.uuid4()),'record_id':rid,'revision':rev}),400)
 expect('public_replace_rejected',c.call('/action',last,cookie=False,gate=False),401)
 expect('csrf_rejected',c.call('/action',last,origin=False),403)
 assert not query(state()['database_id'],'SELECT record_id FROM provenance WHERE record_id=?',[rid])[0]['results'];checks['future_set_no_word_provenance']=True
 for name in ('display-eau-claire-players','display-milwaukee-8x10-list','display-brewers-bobblehead-wantlist'):expect('section_'+name,c.call('/public/record?id='+name))
 expect('reserved_duplicate_section_rejected',c.call('/action',{'op':'create','request_id':str(uuid.uuid4()),'metadata':{'set_name':'Duplicate','display_category':'Eau Claire Players'}}),400)
 end=utc();expect('logout',c.call('/logout',{}));PATH.write_text(json.dumps({'checks':checks,'record_id':rid,'samples':samples,'start':start,'end':end,'full_import':False,'production_cutover':False,'permanent_owner_pin_configured':False},indent=2));print('Actual revision checks passed:',len(checks))
def collect():
 r=json.loads(PATH.read_text());db=state()['database_id']
 if 'record_id' not in r:r['record_id']=query(db,"SELECT record_id FROM change_history WHERE action='replace_list' ORDER BY created_at DESC,id DESC LIMIT 1")[0]['results'][0]['record_id']
 gid=query(db,"SELECT id FROM record_groups WHERE record_id=? AND kind='primary'",[r['record_id']])[0]['results'][0]['id']
 r['replacement_query_plans']={}
 for label,statement,params in [('next_position','SELECT COALESCE(MAX(position),-1)+1 FROM items WHERE group_id=? AND field_key=?',[gid,'card_numbers']),('history_membership','SELECT id FROM items WHERE group_id=? AND deleted_at IS NULL',[gid]),('affected_public_group','SELECT * FROM items WHERE group_id=? AND deleted_at IS NULL ORDER BY field_key,position',[gid]),('record_projection','SELECT * FROM public_records WHERE record_id=?',[r['record_id']]),('individual_restore_event',"SELECT json_extract(before_json,'$.group_list_type') FROM change_history INDEXED BY history_record_recent WHERE record_id=? AND created_at=? AND item_id=? AND action='remove_item' LIMIT 1",[r['record_id'],'timestamp','item'])]:
  rows=query(db,'EXPLAIN QUERY PLAN '+statement,params)[0]['results'];assert not any('SCAN items' in x.get('detail','') for x in rows),(label,rows);r['replacement_query_plans'][label]=rows
 buckets={x['dimensions']['datetime']:x for x in metrics_groups(WORKER,r['start'],r['end']) if x['sum']['requests']==1}
 for s in r['samples']:
  b=buckets.get(s['started'].split('.')[0]+'Z')
  if b:s['cpu_ms']=b['quantiles']['cpuTimeP50']/1000
 summary={}
 for mode in ('want_list','have_list'):
  raw=[s for s in r['samples'] if s['operation']==mode and not s['instrumented']];cpu=[s['cpu_ms'] for s in raw if 'cpu_ms' in s];diag=[s for s in r['samples'] if s['operation']==mode and s['instrumented']][0]
  summary[mode]={'runs':len(raw),'successes':sum(s['status']==200 for s in raw),'cpu_samples':len(cpu),'median_cpu_ms':statistics.median(cpu) if cpu else None,'max_cpu_ms':max(cpu) if cpu else None,'median_wall_ms':statistics.median(s['client_wall_ms'] for s in raw),'d1_reads':diag['rows_read'],'d1_writes':diag['rows_written']}
 r['summary']=summary;PATH.write_text(json.dumps(r,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':
 import sys
 collect() if '--collect' in sys.argv else run()
