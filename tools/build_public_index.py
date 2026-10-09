"""Regenerate the SQL index from authoritative display classifications; run from repo root."""
import json
from pathlib import Path
m=json.loads(Path('foundation/staging/historical-map.json').read_text());overrides={**{k:v for k,v in m['uncertainty_display'].items() if v},**{k:v['list_type'] for k,v in m['classification_approvals'].items()}}
override=json.dumps(overrides,separators=(',',':')).replace("'","''")
mode="CASE WHEN json_extract(NEW.public_json,'$.list_type')='uncertain' THEN COALESCE(json_extract('"+override+"','$.'||NEW.record_id),json_extract(NEW.public_json,'$.source_list_type'),'uncertain') ELSE json_extract(NEW.public_json,'$.list_type') END"
header=['id','year','display_year','brand','set_name','category','display_category','section','notes','prefixes','entry_order','source_list_type']
parts=[]
for k in header:parts.extend(["'"+k+"'",("json(" if k in ['notes','prefixes'] else '')+"json_extract(NEW.public_json,'$."+k+"')"+(')' if k in ['notes','prefixes'] else '')])
parts.extend(["'list_type'",mode,"'revision'","NEW.revision","'index_only'","json('true')","'card_numbers'","json('[]')","'items'","json_array(COALESCE((SELECT group_concat(value,' ') FROM (SELECT json_extract(e.value,'$.value') value FROM json_each(NEW.public_json,'$.groups') g JOIN json_each(g.value,'$.entries') e WHERE ("+mode+") IN ('want_list','have_list') AND (json_extract(g.value,'$.list_type')=("+mode+") OR json_extract(g.value,'$.kind')='primary' AND json_extract(g.value,'$.list_type')='uncertain') AND (json_extract(e.value,'$.state') IS NULL OR json_extract(e.value,'$.state') IN (CASE WHEN ("+mode+")='have_list' THEN 'owned' ELSE 'wanted' END,CASE WHEN ("+mode+")='want_list' THEN 'pending' ELSE 'owned' END)) AND NOT(NEW.record_id='p0526-l006' AND json_extract(g.value,'$.kind')='primary' AND json_extract(e.value,'$.field_key')='items') UNION ALL SELECT json_extract(g.value,'$.label') value FROM json_each(NEW.public_json,'$.groups') g WHERE json_extract(g.value,'$.list_type')=("+mode+"))),''))"])
body='INSERT INTO public_browse_index VALUES(NEW.record_id,NEW.revision,NEW.deleted,json_object('+','.join(parts)+')) ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,deleted=excluded.deleted,index_json=excluded.index_json;'
sql="-- Public search index is updated atomically by projection writes, never by a separate job.\nCREATE TABLE IF NOT EXISTS public_browse_index(record_id TEXT PRIMARY KEY REFERENCES public_records(record_id) ON DELETE CASCADE, revision INTEGER NOT NULL,deleted INTEGER NOT NULL,index_json TEXT NOT NULL CHECK(json_valid(index_json)));\n"
for action in ['INSERT','UPDATE']:sql+='CREATE TRIGGER IF NOT EXISTS public_index_'+action.lower()+' AFTER '+action+' ON public_records BEGIN '+body+' END;\n'
Path('foundation/staging/public-index.sql').write_text(sql)
print(len(sql),'SQL bytes')
