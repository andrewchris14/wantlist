// Derived classification decisions; checked against historical-map.json by regression tests.
const overrides={"p0023-l001": "have_list", "p0060-l001": "complete", "p0239-l017": "have_list", "p0239-l018": "have_list", "p0261-l003": "have_list", "p0273-l029": "complete", "p0273-l039": "want_list", "p0375-l001": "have_list", "p1809-l001": "have_list", "p1996-l007": "have_list", "p1996-l008": "complete", "p1996-l009": "have_list", "p1996-l010": "have_list", "p1996-l011": "have_list", "p1996-l012": "have_list", "p1996-l013": "have_list", "p1996-l014": "have_list", "p1996-l015": "have_list", "p1996-l016": "have_list", "p1996-l017": "have_list", "p1996-l018": "have_list", "p1996-l019": "have_list", "p1996-l020": "have_list", "p2501-l001": "complete", "p2529-l001": "have_list", "p2851-l007": "complete", "p2887-l001": "have_list", "p3022-l006": "have_list"};
export function effectiveListType(r){
 const c=r.content||r,raw=r.list_type||c.list_type||"uncertain";
 if(raw!=="uncertain")return raw; // Explicit live owner classifications take precedence.
 if(overrides[r.id])return overrides[r.id];
 const populated=r.has_entries||(r.groups||[]).some(g=>g.entries?.some(i=>!i.deleted_at))||(c.card_numbers||[]).length||(c.items||[]).length||(c.mixed_lists||[]).some(g=>g.items?.length);
 return c.source_list_type==="have_list"&&populated?"have_list":"uncertain";
}
