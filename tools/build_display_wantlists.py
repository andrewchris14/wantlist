"""Additive, reproducible website view of the protected Phase 2 snapshot.
Section membership comes ONLY from verified Word paragraph boundaries.
Never overwrites wantlists.json, raw extraction, or Phase 2 corrections.
"""
import copy,json,hashlib
from collections import Counter
from pathlib import Path
from import_docx import extract
ROOT=Path(__file__).resolve().parents[1]
CATEGORIES=['OBC Wantlist','UV Wantlist','Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist','Football Wantlist','Other Stuff']
# Verified literal headings in the original Word document, not keyword taxonomy.
BOUNDARIES=[(1,526,'OBC Wantlist'),(526,579,'Other Stuff'),(579,644,'Football Wantlist'),(644,3025,'UV Wantlist'),(3025,3124,'Brewers Bobblehead Wantlist'),(3124,3379,'Milwaukee 8x10 List'),(3379,3383,'Eau Claire Players')]
SPECIAL={'Eau Claire Players':'want_list','Milwaukee 8x10 List':'have_list','Brewers Bobblehead Wantlist':'want_list'}
def category(record):
 found={label for ref in record['source_refs'] for start,end,label in BOUNDARIES if start<=ref['paragraph']<end}
 if len(found)!=1:raise ValueError(f"Ambiguous source boundary: {record['id']}: {found}")
 return found.pop()
def build():
 baseline=json.loads((ROOT/'data/wantlists.json').read_text());raw=json.loads((ROOT/'data/raw/paragraphs.json').read_text())
 # Independently read the Word archive; do not rewrite the extracted source.
 original=extract()
 assert original['paragraphs']==raw['paragraphs']
 paragraph_text={p['paragraph']:p['text'] for p in raw['paragraphs']}
 for paragraph,heading in ((1,'OBC Wantlist'),(526,'Other stuff:'),(579,'FOOTBALL WANTLIST (work in progress)'),(644,'UV Wantlist'),(3025,'Brewers Bobblehead Wantlist'),(3124,'Milwaukee Baseball 8x10 Autographs'),(3379,'Eau Claire Players')):
  assert paragraph_text[paragraph].lstrip().startswith(heading),f'Section boundary changed: {paragraph}'
 records=[];mapping={};audit=[]
 for source in baseline['records']:
  r=copy.deepcopy(source);r['display_category']=category(r);mapping[r['id']]=r['display_category'];records.append(r)
  if r['list_type']=='uncertain':
   values=sum(len(g.get(k,[])) for g in [r,*r.get('mixed_lists',[]),*r.get('sublists',[])] for k in ('items','card_numbers','card_ranges'))
   # Explicit finite HAVE entries prove ownership, not completeness.
   label='have_list' if r.get('source_list_type')=='have_list' and values and r['id']!='p1996-l008' else None
   r['display_list_type']=label
   audit.append({'id':r['id'],'set_name':r['set_name'],'display_list_type':label,'requires_review':label is None,'reason':'Explicit HAVE inventory; completeness/other source uncertainty remains unchanged.' if label else 'Source uncertainty does not establish a definitive wanted inventory or completeness.','uncertainty':r['uncertainty'],'source_refs':r['source_refs']})
 for name,mode in SPECIAL.items():
  members=[r for r in records if r['display_category']==name];assert members
  aggregate={'id':'display-'+name.lower().replace(' ','-'),'year':None,'brand':None,'set_name':name,'category':members[0]['category'],'display_category':name,'section':members[0]['section'],'list_type':mode,'source_list_type':mode,'card_numbers':[],'items':[],'card_ranges':[],'notes':[],'prefixes':[],'uncertainty':[],'mixed_lists':[],'sublists':[],'source_refs':[ref for r in members for ref in r['source_refs']],'source_wording':[s for r in members for s in r['source_wording']],'source_records':members,'display_members':[r['id'] for r in members]}
  if len(members)==1:
   for k in ('card_numbers','items','card_ranges','notes','prefixes','uncertainty','mixed_lists','sublists'):aggregate[k]=copy.deepcopy(members[0].get(k,[]))
  else:
   aggregate['sublists']=[{**copy.deepcopy(r),'label':r['set_name']} for r in members]
  # All context prose in these source sections is retained, including intro notes.
  aggregate['source_section_context']=[x for x in baseline['context_notes'] if any(start<=x.get('source_ref',{}).get('paragraph',-1)<end and label==name for start,end,label in BOUNDARIES)]
  if name in ('Eau Claire Players','Milwaukee 8x10 List'):
   start,end=next((a,b) for a,b,c in BOUNDARIES if c==name)
   paragraphs=[x for x in raw['paragraphs'] if start<=x['paragraph']<end]
   groups=[];group={'label':name,'list_type':mode,'items':[],'source_refs':[]};groups.append(group)
   aggregate['notes']=[];aggregate['card_numbers']=[];aggregate['items']=[]
   ledger=[]
   for para in paragraphs:
    for number,line in enumerate(para['text'].splitlines(),1):
     line=line.strip()
     if not line:continue
     ref={'paragraph':para['paragraph'],'line':number}
     if name=='Milwaukee 8x10 List' and para['paragraph']<3128 or name=='Eau Claire Players' and (para['paragraph']==3379 or line.startswith("I'm interested")):
      aggregate['notes'].append(line);ledger.append({'source_ref':ref,'kind':'note','text':line});continue
     if line.endswith(':'):
      group={'label':line.rstrip(':'),'list_type':mode,'items':[],'source_refs':[ref]};groups.append(group);ledger.append({'source_ref':ref,'kind':'heading','text':line});continue
     group['items'].append(line);group['source_refs'].append(ref);ledger.append({'source_ref':ref,'kind':'item','text':line})
   aggregate['sublists']=[g for g in groups if g['items']];aggregate['section_line_ledger']=ledger
   aggregate['section_view_notes']=['Original section lines used without comma splitting; approved legacy parser representations retained in source_records.']

  records=[r for r in records if r['display_category']!=name]+[aggregate]
 assert sum(len(r.get('source_records',[r])) for r in records)==len(baseline['records'])
 return {'baseline_sha256':hashlib.sha256((ROOT/'data/wantlists.json').read_bytes()).hexdigest(),'categories':CATEGORIES,'mapping':mapping,'records':records,'uncertainty_audit':audit,'baseline_category_counts':dict(Counter(mapping.values())),'display_category_counts':dict(Counter(r['display_category'] for r in records))}
if __name__=='__main__':
 out=build();(ROOT/'data/display-wantlists.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(ROOT/'data/display-map.json').write_text(json.dumps({'categories':CATEGORIES,'mapping':out['mapping'],'uncertainty_display':{a['id']:a['display_list_type'] for a in out['uncertainty_audit']}},ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('baseline_category_counts','display_category_counts')},indent=2))
