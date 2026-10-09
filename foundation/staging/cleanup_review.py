"""Offline review of a fresh read-only snapshot; never archives or mutates D1."""
import hashlib,json
from pathlib import Path
from collections import Counter
from foundation import storage
from .historical_import import load_view

def review(snapshot,manifest):
    entries=manifest['records']
    if manifest['count']!=202 or len(entries)!=202:raise ValueError('Review a new manifest before changing the approved 202-record scope')
    canonical=json.dumps(entries,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(canonical).hexdigest()!=manifest['manifest_sha256']:raise ValueError('Manifest checksum mismatch')
    view=load_view();source_ids=set(view['mapping'])|{r['id'] for r in storage.load_baseline()['records']}|{r['id'] for r in view['records']}
    roots={r['id']:r for r in snapshot['tables']['records']};provenance=Counter(r['record_id'] for r in snapshot['tables']['provenance'])
    active_practice={r['id'] for r in roots.values() if r['id'].startswith('owner-record-') and not r['deleted_at']};seen=set();conflicts=[]
    for proposed in entries:
        rid=proposed['id']
        if rid in seen or rid in source_ids or not rid.startswith('owner-record-'):raise ValueError('Historical/non-practice or duplicate cleanup ID')
        seen.add(rid);live=roots.get(rid)
        if not live or live['deleted_at'] or live['import_id'] or provenance[rid]:raise ValueError('Cleanup provenance/state conflict')
        if live['revision']!=proposed['expected_revision'] or hashlib.sha256(live['content_json'].encode()).hexdigest()!=proposed['content_sha256']:conflicts.append(rid)
    if seen!=active_practice:raise ValueError('Manifest does not exactly cover active owner practice IDs')
    benchmark=[i for i in snapshot['tables']['items'] if i['value'].startswith('cpu-test-')]
    return {'manifest_sha256':manifest['manifest_sha256'],'proposed_count':len(entries),'historical_ids_affected':len(seen&source_ids),'revision_or_content_conflicts':conflicts,'benchmark_rows':len(benchmark),'active_benchmark_rows':sum(not i['deleted_at'] for i in benchmark),'approved_corrections_excluded':True,'all_active_practice_ids_covered':True,'archival_executed':False,'approval_still_required':True}

def main():
    root=storage.ROOT;backup=json.loads((root/'foundation/staging/phase3c3-complete-backup.json').read_text());raw=(root/backup['private_file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=backup['sha256']:raise ValueError('Backup checksum mismatch')
    report=review(json.loads(raw),json.loads((root/'foundation/staging/phase3c2-practice-manifest.json').read_text()));report['fresh_backup_sha256']=backup['sha256']
    (root/'foundation/staging/phase3c3-cleanup-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
