import historicalMap from '../foundation/staging/historical-map.json' with {type:'json'};
export const sourceNoteFields=id=>historicalMap.source_note_fields?.[id]?.fields||[];
// Presentation adapter only; historical data is never normalized again here.
export function logicalInventories(r){
 const c=r.content||r,mode=r.list_type;
 const same=(r.groups||[]).map(g=>({...g,entries:g.entries.filter(i=>g.kind!=='primary'||!sourceNoteFields(r.id).includes(i.field_key))})).filter(g=>(g.list_type||mode)===mode);
 const special=['Milwaukee 8x10 List','Eau Claire Players'].includes(c.display_category);
 if(special)same.sort((a,b)=>(a.kind==='sublist'?0:1)-(b.kind==='sublist'?0:1));
 if(special)return [{id:same.find(g=>g.entries.some(i=>!i.deleted_at))?.id||same[0]?.id||'new-primary',label:c.set_name,notes:same.flatMap(g=>[...(g.notes||[]),...(g.description?[g.description]:[])]),entries:same.flatMap(g=>g.entries.map(i=>({...i,group_id:g.id}))),groups:same}];
 const primary=same.filter(g=>g.kind!=='sublist'&&!g.label),variants=same.filter(g=>g.kind==='sublist'||g.label);
 return [...(primary.length?[{id:primary[0].id,notes:primary.flatMap(g=>[...(g.notes||[]),...(g.description?[g.description]:[])]),entries:primary.flatMap(g=>g.entries.map(i=>({...i,group_id:g.id}))),groups:primary}]:[]),...variants.map(g=>({...g,groups:[g]}))].filter(g=>g.entries.some(i=>!i.deleted_at)||g.list_type!=='complete');
}
export function browseRecord(r) {
 const {groups=[],...header}=r;
 const inventories=logicalInventories(r);
 const supplemental=groups.flatMap(g=>{
  const opposite=g.list_type!==r.list_type;
  const values=g.entries.filter(i=>!i.deleted_at&&(opposite||i.state==='owned'&&r.list_type==='want_list'||g.kind==='primary'&&sourceNoteFields(r.id).includes(i.field_key))).map(i=>i.value);
  const qualifications=opposite?[...(g.notes||[]),...(g.description?[g.description]:[])].map(n=>(g.label?g.label+': ':'')+n):[];
  return [...qualifications,...(values.length?[`${g.label?g.label+': ':''}${g.list_type==='have_list'||r.list_type==='want_list'&&values.some(v=>g.entries.some(i=>i.value===v&&i.state==='owned'))?'Historical owned information':g.list_type==='want_list'&&opposite?'Historical wanted information':'Historical note'}: ${values.join('; ')}`]:[])];
 });
 return {...header,card_numbers:[],items:[],card_ranges:[],logical_inventories:inventories.map(g=>({...g,entries:sortedEntries(g.entries.filter(i=>!i.deleted_at&&(r.list_type!=='want_list'||i.state!=='owned')),r.entry_order==='original')})),supplemental_notes:[...supplemental,...groups.filter(g=>g.kind==='sublist'&&g.list_type==='complete').map(g=>(g.label||'Historical group')+': Complete')],mixed_lists:[...groups.filter(g=>g.kind==='sublist'&&g.list_type==='complete').map(g=>({...g,items:[]})),...inventories.map(g=>({label:g.label,list_type:r.list_type,items:g.entries.filter(i=>!i.deleted_at&&i.state!=='pending'&&(r.list_type!=='want_list'||i.state!=='owned')).map(i=>i.value)}))]};
}
export function parseCards(input,kind='numbers') {
 // Names are one per line; commas may be part of an item name. No range expansion.
 const values=(kind==='names'?input.split(/\r?\n/):input.split(/[\s,]+/)).map(x=>x.trim()).filter(Boolean);
 if(values.some(v=>v.length>500))throw Error('One entry is too long. Please shorten it.');
 if(new Set(values).size!==values.length)throw Error('A card is listed twice. Please remove the repeated entry.');
 return values;
}
export const statusNames={want_list:'WANT list',have_list:'HAVE list',complete:'COMPLETE',uncertain:'Original source wording'};
export function titleOf(r={}){const c=r.content||r,name=c.set_name||'Untitled set',lower=name.toLowerCase();return [c.year&&!lower.includes(String(c.year).toLowerCase())?c.year:null,c.brand&&!lower.includes(c.brand.toLowerCase())?c.brand:null,name].filter(Boolean).join(' · ');}
export function historyLabel(h){
 const value=h.after?.value||h.before?.value;
 if(h.action==='edit_session')return 'Saved set information and list changes';
 if(h.action==='benchmark_cleanup')return 'Removed verified benchmark entries';
 if(h.action==='transition')return `Marked ${value} as ${h.after.state==='owned'?'Received':h.after.state==='pending'?'Someone is sending this':'Still need this'}`;
 if(h.action==='add')return `Added cards ${(h.after.items||[]).map(i=>i.value).join(', ')}`;
 if(h.action==='replace_list')return h.before?.list_type&&h.after?.list_type?`Replaced ${h.before.list_type==='have_list'?'HAVE':'WANT'} list with ${h.after.list_type==='have_list'?'HAVE':'WANT'} list`:'Replaced WANT/HAVE list';
 if(h.action==='restore_representation')return 'Restored previous list';
 if(h.action==='create')return 'Created this set';
 if(h.action==='edit')return Object.keys(h.after.metadata||{}).length===1&&h.after.metadata.notes?'Changed notes':'Changed set information';
 return ({remove_item:`Removed ${value}`,restore_item:`Restored ${value}`,delete:'Removed this set',restore:'Restored this set'})[h.action]||'Updated this set';
}

// Explicit owner-selected section defaults for NEW sets only; never reclassifies
// historical records from their brand/name or alters preserved source categories.
export function newSetCategory(section){return section==='Football Wantlist'?'football_cards':section==='Other Stuff'?'other_collectibles':'baseball_cards';}

const collator=new Intl.Collator('en',{numeric:true,sensitivity:'base'});
export const naturalCompare=(a,b)=>collator.compare(String(a),String(b));
export function sortedEntries(entries,original=false){return [...entries].sort(original?(a,b)=>(a.source_order??entries.indexOf(a))-(b.source_order??entries.indexOf(b)):(a,b)=>naturalCompare(a.value,b.value));}
export function yearInfo(value){
 const text=String(value||'');
 const match=text.match(/\b((?:18|19|20)\d{2})(?:\s*[-–—/]\s*(\d{2,4}))?/);
 if(!match)return {label:'Year unknown',keys:['unknown'],sort:null};
 const start=Number(match[1]);let end=match[2]?Number(match[2]):start;
 if(match[2]?.length===2)end+=Math.floor(start/100)*100+(end<start%100?100:0);
 // A backwards full-year range remains literal; endpoints only, no guessed dates.
 const keys=end>=start&&end-start<=100?Array.from({length:end-start+1},(_,i)=>String(start+i)):[String(start),String(end)];
 return {label:/\?|\bca\.?|circa|approx/i.test(text)?'Year uncertain':null,keys,sort:Math.max(start,end)};
}

export function recordYear(r){
 const year=r.year;
 const prefix=String(r.set_name||'').match(/^((?:18|19|20)\d{2}(?:\s*[-–]\s*\d{2,4})?(?:\s*\((?:\?|ca\.?|circa|approx\.?)\))?)/i)?.[1];
 const literal=r.display_year||prefix;
 return year&&literal&&yearInfo(literal).sort===yearInfo(year).sort?literal:year;
}
