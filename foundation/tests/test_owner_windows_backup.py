"""Synthetic data only. No Cloudflare, owner keys, downloads or real DB reads."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('owner_backup_core', ROOT/'tools/windows-backup/core.py')
core = importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

def fixture():
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    for path in sorted((ROOT/'foundation/migrations').glob('*.sql')):
        db.executescript(path.read_text())
    for name in ('schema.sql','categories.sql','public-index.sql'):
        db.executescript((ROOT/'foundation/staging'/name).read_text())
    db.execute('UPDATE categories SET rowid=rowid+1000')
    db.execute("INSERT INTO staging_import_state VALUES(1,'synthetic','synthetic',1,1)")
    content=json.dumps({'id':'synthetic-owner-backup','set_name':'Synthetic only','notes':['Preserved " note é']})
    db.execute('INSERT INTO records VALUES(?,NULL,?,?,7,?,?,?)',('synthetic-owner-backup','want_list',content,'synthetic','synthetic','synthetic-removed'))
    db.execute('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)',('synthetic-group','synthetic-owner-backup','primary',0,'want_list','{}','["items"]'))
    for n,state in enumerate(['wanted','pending','owned']):
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,?,NULL,?)',('synthetic-item-'+str(n),'synthetic-group','items',n,'Synthetic '+str(n),state,'synthetic-pending' if state=='pending' else None,'synthetic-removed' if n==2 else None))
    db.execute('INSERT INTO provenance VALUES(?,?,?,?)',('synthetic-owner-backup','{"synthetic_original":true}','synthetic-hash','[{"synthetic_source":"line"}]'))
    db.execute('INSERT INTO change_history VALUES(?,?,NULL,?,?,?,?,?)',('synthetic-history','synthetic-owner-backup','owner','edit_session','{"synthetic_before":true}','{"synthetic_after":true}','synthetic'))
    db.execute("INSERT INTO sessions VALUES(?, 'synthetic-version',1,0,1,1000,1,NULL)",('f'*64,))
    # Extra application table demonstrates dynamic coverage and exact value types.
    db.execute('CREATE TABLE "owner_extra"(id INTEGER PRIMARY KEY AUTOINCREMENT,wide INTEGER,payload BLOB,nullable TEXT,computed INTEGER GENERATED ALWAYS AS (wide-1) STORED)')
    db.execute('INSERT INTO owner_extra(wide,payload) VALUES(?,?)',(9223372036854775807,b'\x00\xffsynthetic'))
    db.execute('CREATE TABLE owner_without_rowid(id TEXT PRIMARY KEY,value BLOB) WITHOUT ROWID')
    db.execute('INSERT INTO owner_without_rowid VALUES(?,?)',('synthetic',b'\x00\xff'))
    db.execute('CREATE INDEX extra_wide ON owner_extra(wide)')
    db.execute('CREATE VIEW extra_view AS SELECT wide FROM owner_extra')
    db.commit();return db

def approvals():
    return {'reviewed':True,'free':True,'quiet':True,'encrypted_pc':True,'quota_day':core.dt.datetime.now(core.dt.timezone.utc).date().isoformat(),'dashboard_reads':100,'dashboard_writes':10,'email_today':False}

class FakeCloudflare:
    def __init__(self,db=None):
        self.db=db or fixture();self.calls=[];self.reads=100;self.writes=10;self.snapshots=0;self.change=False;self.missing_usage=False;self.bad_identity=False;self.bad_meta=False
    def usage(self):
        self.calls.append('usage')
        if self.missing_usage:raise core.Stop('Usage unavailable')
        return {'rowsRead':self.reads,'rowsWritten':self.writes}
    def database(self):
        self.calls.append('identity');return {'name':'production' if self.bad_identity else core.DATABASE_NAME,'uuid':core.DATABASE_ID}
    def query(self,statements):
        results=[]
        for sql in statements:
            self.calls.append(sql)
            if "SELECT 'schema' kind" in sql:
                self.snapshots+=1
                if self.change and self.snapshots==2:self.db.execute("UPDATE records SET revision=revision+1 WHERE id='synthetic-owner-backup'")
            rows=[dict(r) for r in self.db.execute(sql)]
            results.append({'success':True,'results':rows,'meta':{} if self.bad_meta else {'rows_read':len(rows),'rows_written':0}})
        return results

def synthetic_backup():
    client=FakeCloudflare()
    try:return core.backup(client,approvals())
    finally:client.db.close()

class WindowsBackupTest(unittest.TestCase):
    def test_complete_two_matching_snapshots_restore_exactly(self):
        raw,report=synthetic_backup();snapshot=json.loads(raw)
        self.assertTrue(report['matching_reads']);self.assertTrue(report['all_rows_and_schema_equal'])
        self.assertFalse(report['plaintext_file_created']);self.assertFalse(report['recovery_verified'])
        self.assertEqual(snapshot['tables']['records'][0]['values']['deleted_at'],['text','synthetic-removed'])
        self.assertEqual(snapshot['tables']['items'][1]['values']['state'],['text','pending'])
        self.assertEqual(snapshot['tables']['owner_extra'][0]['values']['wide'],['integer',9223372036854775807])
        self.assertEqual(snapshot['tables']['owner_extra'][0]['values']['payload'],['blob','00FF73796E746865746963'])
        self.assertEqual(snapshot['tables']['owner_without_rowid'][0]['rowid'],None)
        self.assertIn('sessions',snapshot['tables']);self.assertIn('provenance',snapshot['tables']);self.assertIn('change_history',snapshot['tables'])
        self.assertTrue(core.restore_verify(snapshot)['all_rows_and_schema_equal'])
    def test_quota_gate_never_reads_sql_when_exhausted_missing_or_notice(self):
        for kind in ('exhausted','missing','notice','insufficient','writes','stale','unapproved'):
            c=FakeCloudflare();a=approvals()
            try:
                if kind=='exhausted':c.reads=5_000_000
                if kind=='missing':c.missing_usage=True
                if kind=='notice':a['email_today']=True
                if kind=='insufficient':c.reads=3_000_000
                if kind=='writes':c.writes=100_000
                if kind=='stale':a['quota_day']='2000-01-01'
                if kind=='unapproved':a['reviewed']=False
                with self.assertRaises(core.Stop):core.backup(c,a)
                self.assertFalse(any(x.startswith('SELECT ') for x in c.calls),kind)
            finally:c.db.close()
    def test_identity_mismatch_stops_before_sql(self):
        c=FakeCloudflare();c.bad_identity=True
        try:
            with self.assertRaises(core.Stop):core.backup(c,approvals())
            self.assertEqual(c.calls,['usage','identity'])
        finally:c.db.close()
    def test_different_snapshots_no_backup_or_retry(self):
        c=FakeCloudflare();c.change=True
        try:
            with self.assertRaisesRegex(core.Stop,'differ'):core.backup(c,approvals())
            self.assertEqual(c.snapshots,2)
        finally:c.db.close()
    def test_missing_usage_metadata_and_caps_fail_closed(self):
        c=FakeCloudflare();c.bad_meta=True
        try:
            with self.assertRaises(core.Stop):core.backup(c,approvals())
            self.assertEqual(c.snapshots,0)
        finally:c.db.close()
        with patch.object(core,'ROW_CAP',5):
            with self.assertRaisesRegex(core.Stop,'row cap'):synthetic_backup()
    def test_mutation_sql_no_route_or_credentials_to_unexpected_host(self):
        client=core.Cloudflare('a'*32,'synthetic-token')
        with self.assertRaises(core.Stop):client.request('/accounts/anything/workers')
        with self.assertRaises(core.Stop):client.query(['DELETE FROM records'])
        with self.assertRaises(core.Stop):client.query(['SELECT 1; DROP TABLE records'])
        with self.assertRaises(core.Stop):core.NoRedirect().redirect_request(None,None,302,'',{},'https://unapproved.invalid')
    def test_foreign_keys_schema_and_rows_are_verified(self):
        raw,_=synthetic_backup();snapshot=json.loads(raw)
        broken=copy.deepcopy(snapshot);broken['tables']['items'][0]['values']['group_id']=['text','missing-group']
        with self.assertRaises(core.Stop):core.restore_verify(broken)
        broken=copy.deepcopy(snapshot);broken['schema_objects'][0]['sql']='CREATE TABLE wrong(x)'
        with self.assertRaises(core.Stop):core.restore_verify(broken)
        broken=copy.deepcopy(snapshot);broken['tables']['items'][0]['values'].pop('value')
        with self.assertRaises(core.Stop):core.restore_verify(broken)
    def test_filesystem_restore_escape_is_denied(self):
        raw,_=synthetic_backup();snapshot=json.loads(raw)
        for sql in ["ATTACH DATABASE '/tmp/backup-test-must-not-exist.sqlite' AS escaped", "PRAGMA writable_schema=ON", "CREATE VIRTUAL TABLE evil USING fts5(x)","CREATE TABLE evil AS SELECT load_extension('not-allowed')"]:
            bad=copy.deepcopy(snapshot)
            obj=next(o for o in bad['schema_objects'] if o['name']=='owner_extra');obj['sql']=sql
            with self.assertRaises(core.Stop):core.restore_verify(bad)
    def test_snapshot_is_one_statement_and_read_only(self):
        c=FakeCloudflare()
        try:
            core.backup(c,approvals())
            for sql in c.calls:
                if sql.startswith('SELECT '):self.assertNotIn(';',sql)
            self.assertEqual(c.snapshots,2)
        finally:c.db.close()
    def test_account_analytics_has_no_database_filter_and_unknown_is_not_zero(self):
        client=core.Cloudflare('a'*32,'synthetic-token');captured=[]
        def response(path,payload):
            captured.append((path,payload))
            return {'viewer':{'accounts':[{'d1AnalyticsAdaptiveGroups':[{'sum':{'rowsRead':100,'rowsWritten':10}}]}]}}
        client.request=response
        self.assertEqual(client.usage()['rowsRead'],100)
        query=captured[0][1]['query'];self.assertNotIn('databaseId',query);self.assertNotIn('dimensions',query)
        client.request=lambda *args:{'viewer':{'accounts':[{'d1AnalyticsAdaptiveGroups':[]}]}}
        with self.assertRaises(core.Stop):client.usage()
        for invalid in [True,-1,1.2,None,'100']:
            with self.assertRaises(core.Stop):core.count(invalid)

    def test_authorized_local_restore_returns_only_verification_report(self):
        import base64
        from importlib.machinery import SourceFileLoader
        sys.modules['core']=core
        spec=importlib.util.spec_from_loader('owner_backup_positive',SourceFileLoader('owner_backup_positive',str(ROOT/'tools/windows-backup/Start Want List Backup.pyw')))
        launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
        raw,_=synthetic_backup();body=json.dumps({'plaintext_b64':base64.b64encode(raw).decode()}).encode()
        h=launcher.Handler.__new__(launcher.Handler)
        h.server=types.SimpleNamespace(host='127.0.0.1:1234',origin='http://127.0.0.1:1234',capability='synthetic-cap',operation_lock=threading.Lock())
        h.path='/restore';h.headers={'Host':h.server.host,'Origin':h.server.origin,'X-WantList-Local':h.server.capability,'Content-Type':'application/json','Content-Length':str(len(body))};h.rfile=io.BytesIO(body);out=[]
        h.send=lambda status,raw,kind=None:out.append((status,json.loads(raw)))
        with patch.object(launcher,'Cloudflare',side_effect=AssertionError('Recovery must not contact Cloudflare')):
            h.do_POST()
        self.assertEqual(out[0][0],200);self.assertEqual(set(out[0][1]),{'report'})
        self.assertTrue(out[0][1]['report']['all_rows_and_schema_equal'])
        self.assertNotIn('synthetic-history',json.dumps(out[0][1]))

    def test_local_server_requires_host_origin_and_capability(self):
        sys.modules['core']=core
        spec=importlib.util.spec_from_file_location('owner_backup_launcher',ROOT/'tools/windows-backup/Start Want List Backup.pyw')
        # .pyw needs an explicit loader on non-Windows hosts.
        if spec is None:
            from importlib.machinery import SourceFileLoader
            spec=importlib.util.spec_from_loader('owner_backup_launcher',SourceFileLoader('owner_backup_launcher',str(ROOT/'tools/windows-backup/Start Want List Backup.pyw')))
        launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
        for change in ('host','origin','capability','sql-route','files-route'):
            h=launcher.Handler.__new__(launcher.Handler);h.server=types.SimpleNamespace(host='127.0.0.1:1234',origin='http://127.0.0.1:1234',capability='synthetic-cap',operation_lock=threading.Lock())
            h.path='/backup';h.headers={'Host':h.server.host,'Origin':h.server.origin,'X-WantList-Local':h.server.capability,'Content-Type':'application/json'};h.rfile=io.BytesIO(b'{}');out=[];h.send=lambda status,raw,kind=None:out.append(status)
            if change=='host':h.headers['Host']='evil.invalid'
            if change=='origin':h.headers['Origin']='https://evil.invalid'
            if change=='capability':h.headers['X-WantList-Local']='wrong'
            if change=='sql-route':h.path='/sql'
            if change=='files-route':h.path='/../../core.py';h.do_GET();self.assertEqual(out,[404]);continue
            h.do_POST();self.assertIn(out[0],(403,404))

if __name__=='__main__':unittest.main()
