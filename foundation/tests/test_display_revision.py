import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from build_display_wantlists import build,SPECIAL,ROOT
class DisplayRevisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.view=build();cls.baseline=json.loads((ROOT/'data/wantlists.json').read_text())
 def test_every_baseline_record_retained_exactly_once(self):
  recovered=[r for d in self.view['records'] for r in d.get('source_records',[d])]
  self.assertEqual(len(recovered),3392);self.assertEqual(len({r['id'] for r in recovered}),3392)
  original={r['id']:r for r in self.baseline['records']}
  for r in recovered:
   clone=copy.deepcopy(r);clone.pop('display_category',None);clone.pop('display_list_type',None);clone.pop('display_year',None);self.assertEqual(clone,original[r['id']])
 def test_seven_categories_and_boundary_assignments(self):
  self.assertEqual(len(self.view['categories']),7);self.assertEqual(self.view['mapping']['p0531-l001'],'Other Stuff');self.assertEqual(self.view['mapping']['p0581-l001'],'Football Wantlist');self.assertEqual(self.view['mapping']['p0672-l001'],'UV Wantlist')
 def test_special_sections_are_single_listings_and_word_lines_have_exact_coverage(self):
  raw=json.loads((ROOT/'data/raw/paragraphs.json').read_text())['paragraphs']
  for name,mode in SPECIAL.items():
   rows=[r for r in self.view['records'] if r['display_category']==name];self.assertEqual(len(rows),3 if name=='Eau Claire Players' else 1);r=rows[0];self.assertEqual(r['list_type'],mode)
   if 'section_line_ledger' in r:
    bounds=(3124,3379) if name=='Milwaukee 8x10 List' else (3379,3383)
    lines=[(p['paragraph'],n,s.strip()) for p in raw if bounds[0]<=p['paragraph']<bounds[1] for n,s in enumerate(p['text'].splitlines(),1) if s.strip()]
    ledger=[(v['source_ref']['paragraph'],v['source_ref']['line'],v['text']) for row in rows for v in row['section_line_ledger']];
    if name=='Eau Claire Players':lines=[v for v in lines if v[0]!=3379 and not v[2].startswith("I'm interested")]
    self.assertEqual(ledger,lines)
 def test_bobblehead_groups_and_uncertainty_are_lossless(self):
  r=next(r for r in self.view['records'] if r['display_category']=='Brewers Bobblehead Wantlist');rows=[r for r in self.view['records'] if r['display_category']=='Brewers Bobblehead Wantlist'];self.assertEqual(len(rows),26)
  original={r['id']:r for r in self.baseline['records']}
  for r in rows:self.assertEqual(r['items'],original[r['id']]['items']);self.assertEqual(r['list_type'],original[r['id']]['list_type'])
  self.assertEqual(len(self.view['uncertainty_audit']),28)
 def test_deterministic_view_and_protected_snapshot(self):self.assertEqual(build(),self.view)
