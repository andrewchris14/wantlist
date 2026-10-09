"""Regression budgets for the synthetic baseline/current replay (not D1 billing)."""
import json, argparse, re
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('before',nargs='?',default='baseline');parser.add_argument('after',nargs='?',default='optimized');parser.add_argument('--owner-ratio',type=float,default=1.1,help='Explicit owner-read budget; bounded response chunks trade extra SQL work for safe transport')
args=parser.parse_args()
for label in (args.before,args.after):
    if not re.fullmatch(r'[-a-z0-9]+',label):raise ValueError('Invalid measurement label')
before=json.loads(Path('work/sql-cost-'+args.before+'.json').read_text())
after=json.loads(Path('work/sql-cost-'+args.after+'.json').read_text())
for operation,maximum_ratio in [('notes_save',.02),('normal_save',.6),('maximum_save',.03),('large_undo',.8),('owner_large_record',args.owner_ratio)]:
    ratio=after['vm_instructions'][operation]/before['vm_instructions'][operation]
    assert ratio<maximum_ratio,(operation,ratio,maximum_ratio)
assert after['query_counts']['owner_large_record']==1
assert after['bound_parameter_bytes']['maximum_save']<.8*before['bound_parameter_bytes']['maximum_save']
print('Synthetic SQL-work and transport budgets passed; no Cloudflare compatibility claim.')
