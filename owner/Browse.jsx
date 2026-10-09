import SearchableSelect from './SearchableSelect.jsx';
import {useEffect,useMemo,useState} from 'react';
import {request} from './api.js';
import {prepareRecords,queryMatches,yearSpan,asArray,normalize} from '../site/model.js';
import map from '../foundation/staging/historical-map.json';
import {browseRecord,recordYear,yearInfo,naturalCompare,titleOf,sourceNoteFields,effectiveCategory,effectiveListType,publicPrimaryEntry,currentNotesText,publicSearchRecord} from './model.js';
export const CATEGORIES=map.categories;
export const originalCategory=effectiveCategory;
export function compactStatus(r){return ({want_list:'WANT list',have_list:'HAVE list',complete:'COMPLETE'})[effectiveListType(r)]||'Notes';}
export function compactSort(a,b){return (yearInfo(recordYear(b)).sort??-1)-(yearInfo(recordYear(a)).sort??-1)||String(a.set_name||'').localeCompare(String(b.set_name||''),'en',{numeric:true,sensitivity:'base'});}
function CurrentNotes({record}){const text=currentNotesText(record);return text.trim()?<p className="owner-notes">{text}</p>:null;}
function Contents({record:r}){
 if(compactStatus(r)==='Notes')return <div className="listing-content"><CurrentNotes record={r}/></div>;
 const itemMode=['Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist'].includes(originalCategory(r));
 const inventories=r.logical_inventories||[{...r,list_type:effectiveListType(r),entries:[...asArray(r.card_numbers),...asArray(r.card_ranges),...(sourceNoteFields(r.id).includes('items')?[]:asArray(r.items))].map(value=>({value}))},...(r.mixed_lists||[]).map(g=>({...g,entries:asArray(g.items).map(value=>({value}))})),...(r.sublists||[]).map(g=>({...g,entries:asArray(g.items).map(value=>({value}))}))];
 const primary=inventories.filter(g=>!g.list_type||g.list_type===effectiveListType(r)).map(g=>({...g,entries:g.entries.filter(i=>publicPrimaryEntry(effectiveListType(r),i))}));
 const ordered=values=>r.entry_order==='original'?values:[...values].sort((a,b)=>naturalCompare(a.value,b.value));
 const pending=ordered(primary.flatMap(g=>g.entries.filter(i=>i.state==='pending')));
 return <div className="listing-content">{compactStatus(r)==='COMPLETE'?<p>Complete</p>:primary.map((g,n)=>{
 const entries=ordered(g.entries.filter(i=>i.state!=='pending'));
 if(!entries.length)return null;
 return <section key={n}>{g.label&&g.label!==r.set_name&&<h3>{g.label}</h3>}<p><strong>{compactStatus(r)==='HAVE list'?`${itemMode?'Items':'Cards'} I HAVE:`:`${itemMode?'Items':'Cards'} I NEED:`}</strong> {entries.map(i=>i.value).join(itemMode?'; ':', ')}</p></section>;
 })}{pending.length>0&&<p><strong>Pending:</strong> {pending.map(i=>i.value).join(', ')}</p>}<CurrentNotes record={r}/></div>;

}

function ListingRow({record:r,ownerAction}){
 const [open,setOpen]=useState(false),[detail,setDetail]=useState(null),[error,setError]=useState(false),[attempt,setAttempt]=useState(0);
 useEffect(()=>{let live=true;if(open&&r.index_only){setDetail(null);setError(false);request('/public/record?id='+encodeURIComponent(r.id)).then(p=>{if(live)setDetail(browseRecord(p));}).catch(()=>{if(live)setError(true);});}return()=>{live=false;};},[open,r.id,r.revision,r.index_only,attempt]);
 return <details className="listing-row" onToggle={e=>setOpen(e.currentTarget.open)}><summary><span className="listing-title">{titleOf(r)}{yearInfo(recordYear(r)).label&&<small className="year-note"> · {yearInfo(recordYear(r)).label}</small>}</span><strong className={'list-label '+r.list_type}>{compactStatus(r)}</strong></summary>{open&&<>{r.index_only&&!detail?<div className="listing-content">{error?<p>Could not load this listing. <button onClick={()=>setAttempt(a=>a+1)}>Try again</button></p>:<p role="status">Loading listing…</p>}</div>:<Contents record={r.index_only?detail:r}/>} {ownerAction&&<div className="listing-edit">{ownerAction(r)}</div>}</>}</details>;
}

export default function Browse({records,toolbar,ownerAction,categories=CATEGORIES}){
 const [category,setCategory]=useState(CATEGORIES[0]),[query,setQuery]=useState(''),[year,setYear]=useState(''),[manufacturer,setManufacturer]=useState('');
 const prepared=useMemo(()=>prepareRecords((records||[]).map(publicSearchRecord)).map((r,i)=>{const record=records[i],display_category=originalCategory(record),label=normalize([display_category,...(record.logical_inventories||[]).flatMap(g=>g.entries.filter(i=>i.state==='pending').map(i=>i.value))].filter(Boolean).join(' '));return {...record,display_category,_search:r._search+' '+label,_words:new Set([...r._words,...label.split(' ')])};}),[records]);
 // Legacy source members remain archived in D1; they never become duplicate
 // public listings if an aggregate is temporarily missing/deleted.
 const special=['Eau Claire Players','Milwaukee 8x10 List'];
 const visible=prepared.filter(r=>r.id!=='display-brewers-bobblehead-wantlist'&&!(r.id==='display-eau-claire-players'&&prepared.some(row=>/^display-eau-claire-[123]$/.test(row.id)))&&(!special.includes(map.mapping[r.id])||r.id?.startsWith('display-')));
 const years=[...new Set(visible.flatMap(r=>yearInfo(recordYear(r)).keys))].sort((a,b)=>a==='unknown'?1:b==='unknown'?-1:Number(b)-Number(a));
 const manufacturers=[...new Set(visible.map(r=>r.brand).filter(Boolean))].sort(naturalCompare);
 const matches=visible.filter(r=>queryMatches(r,query)&&(!year||yearInfo(recordYear(r)).keys.includes(year))&&(!manufacturer||(r.brand||'__missing')===manufacturer));
 const rows=matches.filter(r=>r.display_category===category).sort(compactSort);
 const other=matches.filter(r=>r.display_category!==category&&r.display_category);
 const unmapped=prepared.filter(r=>!r.display_category);
 return <main className="traditional-list"><header className="compact-header"><div><small>OLD BASEBALL CARDS · OBC</small><h1>Jason's Want List</h1><p className="owner-name">Jason Christopherson · <a href="mailto:jschris@triwest.net">jschris@triwest.net</a></p></div>{toolbar}</header>
 <div className="browse-controls"><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><label>Search this category<input id="collection-search" type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Year, set, player or card"/></label><SearchableSelect label="Year" value={year} onChange={setYear} all="All years" options={years.map(y=>({value:y,label:y==='unknown'?'Unknown year':y}))}/><SearchableSelect label="Manufacturer" value={manufacturer} onChange={setManufacturer} all="All manufacturers" options={[...manufacturers.map(m=>({value:m,label:m})),...(visible.some(r=>!r.brand)?[{value:'__missing',label:'Unspecified manufacturer'}]:[])]}/>{query&&<button onClick={()=>setQuery('')}>Clear search</button>}</div>
 <p className="browse-help">Searching {category}. WANT list = needed; HAVE list = owned, not complete. No missing cards are calculated.</p>
 {query&&other.length>0&&<p className="other-matches">Also found in other categories: {[...new Set(other.map(r=>r.display_category))].map(c=><button key={c} onClick={()=>setCategory(c)}>{c} ({other.filter(r=>r.display_category===c).length})</button>)}</p>}

 <h2>{category} <small>({rows.length})</small></h2>{records===null?<p>Loading the list…</p>:!rows.length?<p>No matching listings. Try fewer words or another category.</p>:<div className="compact-list">{rows.map(r=><ListingRow key={r.id} record={r} ownerAction={ownerAction}/>)}</div>}
 {ownerAction&&unmapped.length>0&&<details className="unmapped-practice"><summary>Older practice listings to organize ({unmapped.length})</summary><p>Choose a category in the editor. No historical category was guessed.</p>{unmapped.filter(r=>queryMatches(r,query)).sort(compactSort).map(r=><ListingRow key={r.id} record={r} ownerAction={ownerAction}/>)}</details>}
 </main>;
}
