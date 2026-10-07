import sys,json,secrets,hashlib,os
from pathlib import Path
from foundation.staging.cloudflare import api,query

def run():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    root=Path(__file__).resolve().parents[2];private=root/'foundation/.local/staging-access.json'
    if private.exists():raise RuntimeError('Staging checkpoint exists; reuse deliberately rather than create another DB')
    assert not api('/d1/database'),'Unexpected existing databases; stop for review'
    db=api('/d1/database','POST',{'name':'wantlist-staging'})
    state={'database_id':db['uuid'],'worker':'wantlist-staging','operator_key':secrets.token_hex(32),'credential':secrets.token_urlsafe(32),'credential_version':secrets.token_hex(16)}
    private.parent.mkdir(exist_ok=True)
    fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(state,f)
    print('Created one Free-account staging D1 database: wantlist-staging')
    for path in ['foundation/migrations/0001_foundation.sql','foundation/migrations/0002_query_indexes.sql','foundation/staging/schema.sql']:
     rows=query(db['uuid'],(root/path).read_text());print(path,'accepted;',len(rows),'statement results')
    print('Schema compatible; no owners table:',query(db['uuid'],"SELECT name FROM sqlite_master WHERE type='table' AND name='owners'")[0]['results']==[])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='NEW isolated staging resource only; manually verify Free billing first')
    parser.add_argument('--confirm-free-manually-verified',action='store_true',required=True)
    parser.parse_args()
    run()
