// Presentation adapter only; historical data is never normalized again here.
export function browseRecord(r) {
 const {groups=[],...header}=r;
 return {...header,card_numbers:[],items:[],card_ranges:[],mixed_lists:groups.flatMap(g=>{
  const entries=g.entries||[];
  if(g.kind==='primary'&&g.list_type==='complete'&&!entries.length&&header.list_type!=='complete')return [];
  if(g.list_type==='complete'&&!entries.length)return [{label:g.label,list_type:'complete',items:[],notes:g.notes||[],description:g.description}];
  return ['wanted','pending','owned','opaque'].map(state=>({
   label:[g.label,state==='pending'?'Someone is sending these':state==='opaque'?'Preserved source information':''].filter(Boolean).join(' · '),
   list_type:state==='wanted'?'want_list':state==='owned'?'have_list':state==='pending'?'pending':g.list_type||header.list_type,
   items:entries.filter(i=>state==='opaque'?!i.actionable:i.actionable&&i.state===state).map(i=>i.value),
   notes:g.notes||[],description:g.description,
  })).filter(g=>g.items.length);
 })};
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
export function sortedEntries(entries,original=false){return [...entries].sort(original?(a,b)=>a.field_key.localeCompare(b.field_key)||a.position-b.position:(a,b)=>naturalCompare(a.value,b.value));}
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
