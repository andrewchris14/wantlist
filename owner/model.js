// Presentation adapter only; historical data is never normalized again here.
export function browseRecord(r) {
 const {groups=[],...header}=r;
 return {...header,card_numbers:[],items:[],card_ranges:[],mixed_lists:groups.flatMap(g=>{
  const entries=g.entries||[];
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
export const statusNames={want_list:'Cards I need',have_list:'Cards I have',complete:'Complete — nothing needed',uncertain:'Uncertain'};
export function titleOf(r){const c=r.content||r,name=c.set_name||'Untitled set',lower=name.toLowerCase();return [c.year&&!lower.includes(String(c.year).toLowerCase())?c.year:null,c.brand&&!lower.includes(c.brand.toLowerCase())?c.brand:null,name].filter(Boolean).join(' · ');}
export function historyLabel(h){
 const value=h.after?.value||h.before?.value;
 if(h.action==='transition')return `Marked ${value} as ${h.after.state==='owned'?'Received':h.after.state==='pending'?'Someone is sending this':'Still need this'}`;
 if(h.action==='add')return `Added cards ${(h.after.items||[]).map(i=>i.value).join(', ')}`;
 if(h.action==='create')return 'Created this set';
 if(h.action==='edit')return Object.keys(h.after.metadata||{}).length===1&&h.after.metadata.notes?'Changed notes':'Changed set information';
 return ({remove_item:`Removed ${value}`,restore_item:`Restored ${value}`,delete:'Removed this set',restore:'Restored this set'})[h.action]||'Updated this set';
}
