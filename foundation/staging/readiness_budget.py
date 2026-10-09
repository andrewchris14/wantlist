"""LOCAL planning estimate; not a Cloudflare billing meter or remote importer."""
import json
import math
from pathlib import Path
from . import import_rehearsal as rehearsal

def estimate(view,existing=(),budget=60000):
    if not isinstance(budget,int) or not 100<=budget<=80000:raise ValueError('Invalid daily budget')
    db=rehearsal.fresh()
    costs={t:1+2*len(db.execute('PRAGMA index_list('+t+')').fetchall()) for t in ('records','provenance','record_groups','items','public_records')}
    costs['rehearsal_receipts']=3;db.close()
    plans=[]
    for record in view['records']:
        rows=rehearsal.rows_for(record)
        bound=64+sum(len(data)*costs[table] for table,data in rows.items())+costs['public_records']+costs['rehearsal_receipts']
        plans.append({'id':record['id'],'bound':bound,'literal_rows':len(rows['items']),'payload_bytes':len(rehearsal.storage.dumps(rows).encode())})
    missing=[p for p in plans if p['id'] not in set(existing)]
    return {'estimate_only':True,'d1_billing_verified':False,'per_listing_overhead_reservation':64,'cost_formula':'1 + 2 * SQLite index count per inserted row; projection + receipt + 64 overhead per listing','index_row_costs':costs,'full_reserved_writes':sum(p['bound'] for p in plans),'missing_reserved_writes':sum(p['bound'] for p in missing),'recommended_daily_budget':budget,'estimated_days_for_missing':math.ceil(sum(p['bound'] for p in missing)/budget),'missing_literal_rows':sum(p['literal_rows'] for p in missing),'largest_listing_reservation':max(p['bound'] for p in plans),'largest_payload_bytes':max(p['payload_bytes'] for p in plans),'maximum_listings_per_operator_batch':20,'pending_chunk_implementation':True}

def main():
    evidence=Path(__file__).with_name('phase3c1-audit.json')
    existing=json.loads(evidence.read_text())['staging']['preserved_historical_ids']
    report=estimate(rehearsal.load_view(),existing)
    Path(__file__).with_name('phase3c1-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
