"""Replay synthetic SQL with SQLite's progress handler to count VM instructions.

These are deterministic local query-work proxies, not billed D1 row reads.
No SQL parameters or database contents enter the committed measurement report.
"""
import argparse,json,sqlite3,collections,shutil,re
from pathlib import Path

def measure(label):
    if not re.fullmatch(r'[-a-z0-9]+',label):raise ValueError('Invalid measurement label')
    path=Path('work/profile-'+label+'-replay.sqlite')
    path.unlink(missing_ok=True)
    shutil.copyfile('work/profile-'+label+'-initial.sqlite',path)
    db=sqlite3.connect(path,isolation_level=None);db.execute('PRAGMA foreign_keys=ON')
    observations=[]
    for n,statement in enumerate(json.loads(Path('work/trace-'+label+'.json').read_text())):
        sql,args=statement['sql'],statement['args']
        plan=[r[3] for r in db.execute('EXPLAIN QUERY PLAN '+sql,args)]
        steps=0
        def progress():
            nonlocal steps
            steps+=1
            return 0
        db.set_progress_handler(progress,1)
        db.execute(sql,args).fetchall()
        db.set_progress_handler(None,0)
        observations.append({'operation':statement['operation'],'statement':n,'sql':sql,
                             'vm_instructions':steps,'query_plan':plan,
                             'bound_parameter_bytes':sum(len(v.encode()) if isinstance(v,str) else 8 if v is not None else 0 for v in args)})
    totals=collections.Counter()
    for row in observations:totals[row['operation']]+=row['vm_instructions']
    db.close()
    return {'label':label,'sqlite_version':sqlite3.sqlite_version,'local_only':True,
            'cloudflare_cpu_or_billed_reads':False,'vm_instructions':dict(totals),
            'query_counts':dict(collections.Counter(r['operation'] for r in observations)),
            'bound_parameter_bytes':{op:sum(r['bound_parameter_bytes'] for r in observations if r['operation']==op) for op in totals},
            'queries':observations,'node_timings':json.loads(Path('work/timings-'+label+'.json').read_text())}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('label');args=parser.parse_args()
    report=measure(args.label)
    Path('work/sql-cost-'+args.label+'.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['vm_instructions']))
