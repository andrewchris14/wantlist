import {useMemo,useState} from 'react';
import {prepareRecords,queryMatches,yearSpan,asArray,normalize} from '../site/model.js';
import map from '../data/display-map.json';
import {titleOf} from './model.js';
export const CATEGORIES=map.categories;
export function originalCategory(r){return r.display_category||map.mapping[r.id]||(r.id?.startsWith('display-')?CATEGORIES.find(c=>'display-'+c.toLowerCase().replaceAll(' ','-')===r.id):null);}
export function compactStatus(r){if(r.list_type==='uncertain'){if(Object.hasOwn(map.uncertainty_display||{},r.id))return map.uncertainty_display[r.id]==='have_list'?'HAVE list':'Source note — review needed';const values=[...(r.card_numbers||[]),...(r.items||[]),...(r.mixed_lists||[]).flatMap(g=>g.items||[])];return r.source_list_type==='have_list'&&values.length?'HAVE list':'Source note — review needed';}return ({want_list:'WANT list',have_list:'HAVE list',complete:'COMPLETE'})[r.list_type]||'Source note — review needed';}
export function compactSort(a,b){return (yearSpan(b.year)?.[1]??-1)-(yearSpan(a.year)?.[1]??-1)||String(a.set_name||'').localeCompare(String(b.set_name||''),'en',{numeric:true,sensitivity:'base'});}
function Contents({record:r}){
 if(r.list_type==='uncertain'&&compactStatus(r)==='Source note — review needed'){const notes=[...asArray(r.uncertainty),...asArray(r.notes),...asArray(r.items),...(r.mixed_lists||[]).flatMap(g=>asArray(g.items))];return <div className="listing-content source-note"><strong>Original source information:</strong>{[...new Set(notes)].map((s,i)=><p key={i}>{s}</p>)}</div>;}
 const itemMode=['Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist'].includes(originalCategory(r));
 const blocks=[{...r,label:null},...(r.mixed_lists||[]),...(r.sublists||[])];
 return <div className="listing-content">{r.list_type==='complete'?<p>Complete</p>:blocks.map((g,n)=>{
  const values=[...asArray(g.card_numbers),...asArray(g.card_ranges),...asArray(g.items)];
  if(!values.length&&g.list_type!=='complete')return null;
  const declared=g.list_type||r.list_type;const mode=declared==='uncertain'&&compactStatus(r)==='HAVE list'?'have_list':declared;
  return <section key={n}>{g.label&&<h3>{itemMode?g.label.replace(/ · Preserved source information$/, ''):g.label}</h3>}{g.description&&<p>{g.description}</p>}{mode==='complete'?<p>Complete</p>:<p><strong>{mode==='pending'?'Already expected — please do not send duplicates:':mode==='have_list'?`${itemMode?'Items':'Cards'} I have:`:mode==='want_list'?`${itemMode?'Items':'Cards'} I need:`:'Preserved source information:'}</strong> {values.join(g.items?.length&&!g.card_numbers?.length?'; ':', ')}</p>}{(n?asArray(g.notes):[]).map((s,i)=><p key={i}>{s}</p>)}</section>;
 })}{asArray(r.notes).filter(n=>!itemMode||!['Milwaukee Baseball 8x10 Autographs','Milwaukee Baseball 8x10 HAVE list','Eau Claire Players',r.set_name].includes(n)&&!/^_+$/.test(n)).map((s,i)=><p key={'note'+i}>{s}</p>)}{asArray(r.uncertainty).length>0&&<p className="source-note">Original wording: {r.uncertainty.join(' ')}</p>}</div>;
}

function ListingRow({record:r,ownerAction}){
 const [open,setOpen]=useState(false);
 return <details className="listing-row" onToggle={e=>setOpen(e.currentTarget.open)}><summary><span className="listing-title">{titleOf(r)}</span><strong className={'list-label '+r.list_type}>{compactStatus(r)}</strong></summary>{open&&<><Contents record={r}/>{ownerAction&&<div className="listing-edit">{ownerAction(r)}</div>}</>}</details>;
}

export default function Browse({records,toolbar,ownerAction}){
 const [category,setCategory]=useState(CATEGORIES[0]),[query,setQuery]=useState('');
 const prepared=useMemo(()=>prepareRecords(records||[]).map(r=>{const display_category=originalCategory(r),label=normalize(display_category||'');return {...r,display_category,_search:r._search+' '+label,_words:new Set([...r._words,...label.split(' ')])};}),[records]);
 // Legacy source members remain archived in D1; they never become duplicate
 // public listings if an aggregate is temporarily missing/deleted.
 const special=['Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist'];
 const visible=prepared.filter(r=>!special.includes(map.mapping[r.id])||r.id?.startsWith('display-'));
 const matches=visible.filter(r=>queryMatches(r,query));
 const rows=matches.filter(r=>r.display_category===category).sort(compactSort);
 const other=matches.filter(r=>r.display_category!==category&&r.display_category);
 const unmapped=prepared.filter(r=>!r.display_category);
 return <main className="traditional-list"><header className="compact-header"><div><small>OLD BASEBALL CARDS · OBC</small><h1>Baseball Card Want List</h1></div>{toolbar}</header>
 <div className="browse-controls"><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}>{CATEGORIES.map(c=><option key={c}>{c}</option>)}</select></label><label>Search this category<input id="collection-search" type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Year, set, player or card"/></label>{query&&<button onClick={()=>setQuery('')}>Clear search</button>}</div>
 <p className="browse-help">Searching {category}. WANT list = needed; HAVE list = owned, not complete. No missing cards are calculated.</p>
 {query&&other.length>0&&<p className="other-matches">Also found in other categories: {[...new Set(other.map(r=>r.display_category))].map(c=><button key={c} onClick={()=>setCategory(c)}>{c} ({other.filter(r=>r.display_category===c).length})</button>)}</p>}

 <h2>{category} <small>({rows.length})</small></h2>{records===null?<p>Loading the list…</p>:!rows.length?<p>No matching listings. Try fewer words or another category.</p>:<div className="compact-list">{rows.map(r=><ListingRow key={r.id} record={r} ownerAction={ownerAction}/>)}</div>}
 {ownerAction&&unmapped.length>0&&<details className="unmapped-practice"><summary>Older practice listings to organize ({unmapped.length})</summary><p>Choose a category through Edit set information. No historical category was guessed.</p>{unmapped.filter(r=>queryMatches(r,query)).sort(compactSort).map(r=><ListingRow key={r.id} record={r} ownerAction={ownerAction}/>)}</details>}
 </main>;
}
