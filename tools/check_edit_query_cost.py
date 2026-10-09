"""Regression budgets for the synthetic baseline/current replay (not D1 billing)."""
import json
from pathlib import Path
before=json.loads(Path('work/sql-cost-baseline.json').read_text())
after=json.loads(Path('work/sql-cost-optimized.json').read_text())
for operation,maximum_ratio in [('notes_save',.02),('normal_save',.6),('maximum_save',.03),('large_undo',.8),('owner_large_record',1.1)]:
    ratio=after['vm_instructions'][operation]/before['vm_instructions'][operation]
    assert ratio<maximum_ratio,(operation,ratio,maximum_ratio)
assert after['query_counts']['owner_large_record']==1
assert after['bound_parameter_bytes']['maximum_save']<.8*before['bound_parameter_bytes']['maximum_save']
print('Synthetic SQL-work and transport budgets passed; no Cloudflare compatibility claim.')
