"""Actual staging verification; reports contain metrics/assertions, not secrets.

Requires the operator-only staging deployment and reconciled sample import.
No production resources are accessed. Exported private data stays ignored.
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from foundation import storage
from .cloudflare import api,query,metrics,WORKER
from .runner import Client,ROOT,state,sql


def run(report_path=None):
    c=Client();c.wait_ready();dbid=state()['database_id'];checks={};usage=[]
    def expect(name,result,status=200):
        assert result['status']==status,(name,result['status'],result['body'])
        checks[name]=True
        usage.append({'action':name,**{k:result[k] for k in ('status','rows_read','rows_written','client_wall_ms')}})
        return result['body']
    def reset_limits():c.batch([sql('DELETE FROM login_limits')])
    start=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    reset_limits()
    expect('no_operator_gate',c.call('/health',gate=False),403)
    expect('unauthorized_mutation',c.call('/action',{'op':'edit'},cookie=False),401)
    expect('cross_origin_login',c.call('/login',{'credential':c.state['credential'],'remembered':True},origin=False),403)
    expect('wrong_code',c.call('/login',{'credential':'wrong-disposable-generated-code','remembered':True}),401)
    expect('remembered_login',c.login())
    remembered_cookie=c.cookie
    expect('session_validation',c.call('/session'))
    expect('short_login',c.login(False));short_cookie=c.cookie
    sessions=query(dbid,'SELECT remembered,expires_at-created_at AS lifetime FROM sessions ORDER BY created_at')[0]['results']
    assert any(r['remembered']==1 and r['lifetime']==7776000 for r in sessions)
    assert any(r['remembered']==0 and r['lifetime']==28800 for r in sessions)
    checks['90_day_and_8_hour_server_expiration']=True
    c.cookie=remembered_cookie
    expect('logout',c.call('/logout',{}));c.cookie=remembered_cookie
    expect('logout_replay_rejected',c.call('/session'),401)
    c.cookie=short_cookie
    expect('other_device_still_valid',c.call('/session'))
    token=short_cookie.split('=',1)[1]
    c.batch([sql('UPDATE sessions SET revoked_at=? WHERE token_hash=?',int(time.time()),hashlib.sha256(token.encode()).hexdigest())])
    expect('individual_revocation',c.call('/session'),401)
    reset_limits();expect('login_for_expiration',c.login());expired_cookie=c.cookie
    c.batch([sql('UPDATE sessions SET created_at=?,expires_at=? WHERE token_hash=?',int(time.time())-100,int(time.time())-1,hashlib.sha256(expired_cookie.split('=',1)[1].encode()).hexdigest())])
    expect('expired_session_rejected',c.call('/session'),401)
    expect('login_for_global_revoke',c.login());old_cookie=c.cookie
    expect('revoke_all',c.call('/revoke-all',{}));c.cookie=old_cookie
    expect('global_revoke_rejected',c.call('/session'),401)
    reset_limits()
    for attempt in range(26):
        result=c.call('/login',{'credential':'wrong-disposable-generated-code','remembered':True})
        if result['status']==429:
            expect('login_throttled',result,429);break
        assert result['status']==401
    else:raise AssertionError('Global throttle did not block by attempt 26')
    reset_limits();expect('login_after_staging_throttle_reset',c.login())
    # Real D1 atomic rollback: first write must disappear if the second violates CHECK.
    bad=c.call('/test/batch',{'statements':[sql("INSERT INTO foundation_meta VALUES('must-rollback','test')"),sql('UPDATE auth_control SET generation=0 WHERE id=1')]})
    expect('constraint_failure_generic',bad,503)
    assert query(dbid,"SELECT count(*) AS n FROM foundation_meta WHERE key='must-rollback'")[0]['results'][0]['n']==0
    checks['actual_d1_batch_atomic_rollback']=True
    expect('set_catalog',c.call('/catalog'))
    baseline=storage.load_baseline();sample=json.loads((ROOT/'foundation/staging/import-result.json').read_text())
    ids=query(dbid,'SELECT id FROM records ORDER BY id')[0]['results']
    all_records=[]
    for row in ids:
        r=expect('open_imported_'+row['id'],c.call('/record?id='+row['id']));all_records.append(r)
        expect('initial_publish_'+row['id'],c.call('/test/publish',{'record_id':row['id']}))
    largest=max(all_records,key=lambda r:sum(len(g['entries']) for g in r['groups']))
    smallest=min(all_records,key=lambda r:sum(len(g['entries']) for g in r['groups']))
    expect('open_small_set',c.call('/record?id='+smallest['id']))
    expect('open_large_set',c.call('/record?id='+largest['id']))
    plans={}
    patterns={
      'open_record':('SELECT * FROM records WHERE id=?',[largest['id']]),
      'open_groups':('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position',[largest['id']]),
      'open_items':('SELECT i.* FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=?',[largest['id']]),
      'find_card':('SELECT i.id FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? AND i.value=?',[largest['id'],'1']),
      'recent':('SELECT * FROM change_history ORDER BY created_at DESC,id DESC LIMIT 20',[]),
      'session':('SELECT * FROM sessions WHERE token_hash=?',['0'*64]),
      'public_record':('SELECT * FROM public_records WHERE record_id=?',[largest['id']]),
      'public_page':('SELECT public_json FROM public_records WHERE record_id>? ORDER BY record_id LIMIT 50',[''])
    }
    for name,(statement,params) in patterns.items():
        rows=query(dbid,'EXPLAIN QUERY PLAN '+statement,params)[0]['results'];plans[name]=rows
        assert not any('SCAN items' in r.get('detail','') or 'SCAN i'==r.get('detail','') for r in rows),(name,rows)
    find=query(dbid,patterns['find_card'][0],patterns['find_card'][1])[0]
    usage.append({'action':'find_one_card_known_set','rows_read':find['meta']['rows_read'],'rows_written':find['meta']['rows_written']})
    checks['targeted_d1_query_plans_indexed']=True
    saved=None
    def act(name,body,expected=200):
        nonlocal saved
        result=c.call('/action',{'request_id':str(uuid.uuid4()),**body})
        value=expect(name,result,expected)
        if expected==200:saved=value
        return value
    act('create_2027_with_20_wanted',{'op':'create','metadata':{'year':'2027','brand':'Topps','set_name':'2027 Topps (staging fiction)','category':'baseball_cards','notes':[]},'wanted':[str(i) for i in range(1,21)],'owned':['101','102']})
    rid=saved['record_id'];r=expect('retrieve_2027',c.call('/record?id='+rid))
    assert r['import_id'] is None and r['content']['creation_origin']=='owner' and 'source_refs' not in r['content']
    assert not query(dbid,'SELECT * FROM provenance WHERE record_id=?',[rid])[0]['results']
    def edit(name,body,expected=200):return act(name,{'record_id':rid,'revision':saved['revision'],**body},expected)
    edit('add_two_wanted',{'op':'add','values':['21','22']})
    edit('add_twenty_wanted',{'op':'add','values':[str(i) for i in range(23,43)]})
    edit('add_owned',{'op':'add','state':'owned','values':['103']})
    r=expect('retrieve_added',c.call('/record?id='+rid));entries=[i for g in r['groups'] for i in g['entries']];one=next(i['id'] for i in entries if i['value']=='1');two=next(i['id'] for i in entries if i['value']=='2')
    edit('mark_pending',{'op':'transition','item_id':one,'state':'pending'})
    projection=expect('pending_public_immediate',c.call('/public/record?id='+rid))
    assert next(i for g in projection['groups'] for i in g['entries'] if i['id']==one)['state']=='pending'
    edit('pending_back_to_wanted',{'op':'transition','item_id':one,'state':'wanted'})
    edit('mark_received',{'op':'transition','item_id':two,'state':'owned'})
    edit('edit_notes',{'op':'edit','metadata':{'notes':['Staging lifecycle note']}})
    edit('mark_uncertain',{'op':'edit','list_type':'uncertain','metadata':{'uncertainty':['Owner unsure']}})
    edit('unmark_uncertain',{'op':'edit','list_type':'want_list','metadata':{}})
    edit('complete_rejects_needed_items',{'op':'edit','list_type':'complete','metadata':{}},400)
    edit('remove_wrong_card',{'op':'remove_item','item_id':one});edit('restore_card',{'op':'restore_item','item_id':one})
    edit('soft_delete_record',{'op':'delete'});edit('restore_record',{'op':'restore'})
    replay={'request_id':str(uuid.uuid4()),'op':'edit','record_id':rid,'revision':saved['revision'],'metadata':{'notes':['Idempotent staging note']}}
    first=expect('idempotent_first_save',c.call('/action',replay));second=expect('idempotent_retry',c.call('/action',replay));assert second['replayed'] and second['revision']==first['revision'];saved=first
    act('stale_revision_rejected',{'op':'edit','record_id':rid,'revision':1,'metadata':{}},409)
    edit('invalid_transition_rejected',{'op':'transition','item_id':two,'state':'pending'},400)
    # Complete/unmark complete is tested on an owned-only fictional set.
    act('create_owned_only_future',{'op':'create','metadata':{'year':'2027','set_name':'2027 Owned-only staging test','category':'baseball_cards'},'owned':['1']});owned_rid=saved['record_id']
    act('mark_complete',{'op':'edit','record_id':owned_rid,'revision':saved['revision'],'list_type':'complete','metadata':{}})
    act('unmark_complete',{'op':'edit','record_id':owned_rid,'revision':saved['revision'],'list_type':'have_list','metadata':{}})
    expect('recent_changes',c.call('/recent'))
    expect('public_catalog_refresh',c.call('/public/catalog',cookie=False))
    page=expect('public_snapshot_page',c.call('/public/page',cookie=False));assert page['records']
    checks['per_edit_projection_atomic_and_pending_visible']=True
    checks['owner_created_no_fabricated_provenance']=True
    # A private sentinel proves allowlisting without publishing its value.
    c.batch([sql('INSERT INTO private_details VALUES(?,?)',one,json.dumps({'expected_from':'private staging fixture'}))])
    public=expect('public_sanitized',c.call('/public/record?id='+rid,cookie=False));assert 'private staging fixture' not in json.dumps(public)
    assert 'source_text' not in json.dumps(public) and 'credential' not in json.dumps(public)
    checks['private_details_excluded']=True
    # Partial-import gate rejects edits without reporting success.
    c.batch([sql('UPDATE staging_import_state SET completed=0 WHERE id=1')]);act('partial_import_rejected',{'op':'create','metadata':{'set_name':'must not create'}},409)
    c.batch([sql('UPDATE staging_import_state SET completed=1 WHERE id=1')])
    from .import_baseline import run as import_run
    try:import_run()
    except ValueError as e:assert 'live edits' in str(e);checks['import_refuses_post_import_edits']=True
    else:raise AssertionError('Initialization overwrote edited database')
    # Export actual D1 data (never secret/session tables) and restore locally.
    local=storage.connect();storage.apply_schema(local)
    for table in storage.BACKUP_TABLES:
        rows=query(dbid,f'SELECT * FROM {table} ORDER BY 1')[0]['results']
        for row in rows:
            cols=list(row);local.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",[row[k] for k in cols])
    local.commit();backup=storage.private_export(local)
    private_path=ROOT/'foundation/.local/live-private-export.json';private_path.write_text(json.dumps(backup));private_path.chmod(0o600)
    restored=storage.connect();storage.apply_schema(restored);storage.restore(restored,backup)
    assert storage.private_export(restored)==backup
    public_path=ROOT/'foundation/.local/public-export.json';public_path.write_text(json.dumps(storage.public_export(restored)))
    assert 'private staging fixture' not in public_path.read_text()
    csv=storage.items_csv(restored);assert '2027 Topps' in csv
    (ROOT/'foundation/.local/items.csv').write_text(csv)
    dump=storage.sql_export(restored);(ROOT/'foundation/.local/private-restore.sql').write_text(dump)
    sql_restored=storage.connect();sql_restored.executescript(dump)
    assert not sql_restored.execute('PRAGMA foreign_key_check').fetchall()
    assert storage.private_export(sql_restored)==backup
    checks['actual_d1_json_export_local_restore']=True;checks['actual_d1_data_sql_restore']=True;checks['csv_export']=True
    history=query(dbid,'SELECT action FROM change_history WHERE record_id=? ORDER BY created_at,id',[rid])[0]['results']
    assert len(history)==15,(len(history),history)
    end=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    report={'checks':checks,'actual_d1_usage':usage,'query_plans':plans,'future_record_history_actions':[r['action'] for r in history],
            'snapshot_strategy':'transactional affected-record projection; catalog + keyset public pages; no item-table scan per public read',
            'snapshot_initial_public_rows':len(page['records']),'start':start,'end':end,'worker_metrics':metrics(WORKER,start,end),
            'backend_unavailable':'local fault injection only; actual database not deliberately disconnected','worker_unavailable':'endpoint-disabled behavior tested separately',
            'restore_target':'disposable local SQLite; separate import-budget staging database is not the restore target','credential_expiry':'none; manual rotation only'}
    (report_path or ROOT/'foundation/staging/verification-result.json').write_text(json.dumps(report,indent=2))
    print('Staging checks passed:',len(checks),'future history:',len(history));print('Actual usage:',json.dumps(usage))
    local.close();restored.close();sql_restored.close()


if __name__=='__main__':run()
