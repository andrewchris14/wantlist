"""Offline release builder: import closure, rebuilt editor assets, schema digests."""
import argparse, hashlib, json, re, sqlite3, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STAGING = ROOT / 'foundation/staging'
IMPORTS = re.compile(r'(?:from\s*|import\s*)[\'\"](\./[^\'\"]+)[\'\"]')
def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def normalize_sql(value):
    # Normalize whitespace outside quoted SQL strings, preserving JSON literals.
    tokens=re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[^'\"]+",value.strip().rstrip(';'))
    return ''.join(t if t.startswith(('\"',"'")) else re.sub(r'\s+',' ',t) for t in tokens)
def statements(sql):
    result=[];pending=''
    for char in sql:
        pending+=char
        if char==';' and sqlite3.complete_statement(pending):result.append(pending.strip());pending=''
    if pending.strip():raise ValueError('Incomplete migration')
    return result

def schema_manifest():
    db=sqlite3.connect(':memory:')
    for p in sorted((ROOT/'foundation/migrations').glob('*.sql')):db.executescript(p.read_text())
    for p in ('categories.sql','schema.sql'):db.executescript((STAGING/p).read_text())
    legacy_sql=subprocess.run(['git','show','1aa32e1:foundation/staging/public-index.sql'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    db.executescript(legacy_sql)
    names=('items_group_value','history_record_recent','public_browse_index','public_index_insert','public_index_update','history_item_reference')
    def collect():return {name:normalize_sql(sql) for name,sql in db.execute('SELECT name,sql FROM sqlite_master WHERE name IN ('+','.join('?' for _ in names)+')',names)}
    baseline=collect();migration=(STAGING/'phase3c6-performance.sql').read_text();db.executescript(migration);expected=collect();db.close()
    return {'expected':expected,'legacy':baseline,'migration':migration,'migration_sha256':digest(migration),'migration_statements':statements(migration)}

def build(asset_directory=None):
    assets={};directory=Path(asset_directory) if asset_directory else ROOT/'foundation/.local/editor-dist'
    for p in sorted(directory.rglob('*')):
        if p.is_file():
            key='/'+p.relative_to(directory).as_posix()
            assets[key]={'body':p.read_text(),'type':'text/html; charset=utf-8' if p.suffix=='.html' else 'text/css; charset=utf-8' if p.suffix=='.css' else 'application/javascript; charset=utf-8'}
    if '/index.html' not in assets:raise ValueError('Build owner assets with Vite first')
    refs=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',assets['/index.html']['body'])
    if len(refs)<2 or any(ref not in assets for ref in refs):raise ValueError('Incomplete built assets')
    assets['/']=assets['/index.html'];generated='export const editorAssets='+canonical(assets)+';'
    modules={};pending=['free-review-wrapper.mjs']
    while pending:
        name=pending.pop()
        if name in modules:continue
        if '/' in name or name.startswith('.'):raise ValueError('Nonlocal module')
        modules[name]=generated if name=='editor-assets.js' else (STAGING/name).read_text()
        for ref in IMPORTS.findall(modules[name]):
            child=ref[2:]
            if '/' in child or not child.endswith(('.js','.mjs')):raise ValueError('Unexpected module import')
            pending.append(child)
    size=sum(len(v.encode()) for v in modules.values())
    if size>=3_000_000:raise ValueError('Free Worker module limit')
    commit=subprocess.run(['git','log','-1','--format=%H','--',*[str((STAGING/name).relative_to(ROOT)) for name in modules if name!='editor-assets.js'],'owner','site'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    package={'protocol':'minimal-free-six-v1','source_commit':commit,'main_module':'free-review-wrapper.mjs','modules':modules,'schema':schema_manifest()}
    manifest={'source_commit':commit,'main_module':package['main_module'],'module_bytes':size,'module_sha256':{k:digest(v) for k,v in sorted(modules.items())},'asset_sha256':{k:digest(v['body']) for k,v in sorted(assets.items())},'migration_sha256':package['schema']['migration_sha256'],'package_sha256':digest(canonical(package))}
    return package,manifest

def validate(package):
    if package.get('protocol')!='minimal-free-six-v1' or package.get('main_module')!='free-review-wrapper.mjs':raise ValueError('Wrong release protocol')
    modules=package['modules']
    if package['main_module'] not in modules or 'editor-assets.js' not in modules:raise ValueError('Missing entrypoint or editor assets')
    for name,source in modules.items():
        if '/' in name or not name.endswith(('.js','.mjs')):raise ValueError('Invalid module name')
        for ref in IMPORTS.findall(source):
            if ref[2:] not in modules:raise ValueError('Missing imported module')
    if sum(len(v.encode()) for v in modules.values())>=3_000_000:raise ValueError('Free Worker module limit')
    if digest(package['schema']['migration'])!=package['schema']['migration_sha256']:raise ValueError('Migration digest mismatch')
    if statements(package['schema']['migration'])!=package['schema']['migration_statements']:raise ValueError('Migration statement mismatch')
    return digest(canonical(package))

def main():
    parser=argparse.ArgumentParser(description='LOCAL ONLY: prepare source release, no Cloudflare access')
    parser.add_argument('--output',default='work/minimal-free-release.json');args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'work'):parser.error('Output must remain in ignored work/')
    package,manifest=build();validate(package);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(canonical(package)+'\n');output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
