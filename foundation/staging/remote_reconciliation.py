"""Read-only exact payload reconciliation on the disposable import database."""
import json
from collections import Counter
from pathlib import Path
from foundation.staging import historical_import as h
def main():
    reg=json.loads((h.storage.ROOT/'foundation/.local/phase3c2-isolated.json').read_text());t=h.Remote(reg['database_id']);plan={r['id']:r for r in h.manifest()['records']};ids={r['record_id'] for r in t.rows('SELECT record_id FROM derived_import_receipts')};counts={}
    for table in h.TABLES:
     cols=[r['name'] for r in t.rows('PRAGMA table_info('+table+')')];expected=[]
     for rid in ids:expected.extend(plan[rid]['tables'][table])
     if table=='records':rows=t.rows("SELECT * FROM records WHERE id IN (SELECT record_id FROM derived_import_receipts)")
     elif table=='items':rows=t.rows("SELECT i.* FROM items i JOIN record_groups g ON g.id=i.group_id WHERE g.record_id IN (SELECT record_id FROM derived_import_receipts)")
     else:rows=t.rows('SELECT * FROM '+table)
     actual=[[row[c] for c in cols] for row in rows];assert Counter(h.storage.dumps(row) for row in actual)==Counter(h.storage.dumps(row) for row in expected),table;counts[table]=len(actual)
    assert t.rows('SELECT count(*) n FROM public_browse_index')[0]['n']==len(ids)
    report={'receipted_listings':len(ids),'exact_source_payload_reconciliation':True,'table_counts':counts,'public_index_rows':len(ids),'fixture_removed_root_excluded':True,'full_remote_collection':False,'usage':t.meter}
    (h.storage.ROOT/'foundation/staging/phase3c3-remote-reconciliation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
