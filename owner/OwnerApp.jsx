import {useEffect,useMemo,useRef,useState} from 'react';
import Browse,{CATEGORIES,originalCategory} from './Browse.jsx';
import {categoryLabel} from '../site/model.js';
import {request,publicRecords} from './api.js';
import {browseRecord,parseCards,statusNames,titleOf,historyLabel,newSetCategory} from './model.js';

function Dialog({title,children,onClose,busy}){
 const ref=useRef();
 useEffect(()=>{ref.current.showModal();return()=>ref.current?.close();},[]);
 return <dialog ref={ref} aria-labelledby="owner-dialog-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><div className="dialog-header"><h2 id="owner-dialog-title">{title}</h2><button disabled={busy} onClick={onClose} aria-label="Close">Close</button></div>{children}</dialog>;
}
function MetadataForm({record,categories,onSave,busy,blocked=busy}){
 const special=record?.id?.startsWith('display-');
 const [form,setForm]=useState(()=>{const c=record?.content||{};return {year:c.year||'',brand:c.brand||'',set_name:c.set_name||'',category:c.category||'baseball_cards',display_category:originalCategory({id:record?.id,...c})||'OBC Wantlist',notes:(c.notes||[]).join('\n'),list_type:record?.list_type||'want_list'};});
 const [confirmed,setConfirmed]=useState(false);
 const change=k=>e=>{setForm({...form,[k]:e.target.value});if(k==='list_type')setConfirmed(false);};
 const broad=!special&&form.list_type==='complete'&&form.list_type!==record?.list_type;
 const choices=Object.entries({...statusNames,...(record?.list_type==='uncertain'?{uncertain:'Keep original source wording'}:{})}).filter(([k])=>(k!=='uncertain'||record?.list_type==='uncertain')&&(!record||k===record.list_type||k==='complete'||record.list_type==='complete'&&k==='want_list'));
 return <form onSubmit={e=>{e.preventDefault();const notes=form.notes.split('\n').filter(x=>x.trim());onSave(special?{notes}:{year:form.year||null,brand:form.brand||null,set_name:form.set_name.trim(),category:record?form.category:newSetCategory(form.display_category),display_category:form.display_category,notes},form.list_type);}}>
 <fieldset disabled={blocked}><div className="form-grid">{!special&&<><label>Year or years<input value={form.year} onChange={change('year')} placeholder="2027 or 2026–2027"/></label><label>Brand<input value={form.brand} onChange={change('brand')} placeholder="Topps"/></label><label className="wide">Set/name<input required maxLength={500} value={form.set_name} onChange={change('set_name')} placeholder="Topps"/></label><label>Category<select value={form.display_category} onChange={change('display_category')}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><label>How to describe this set<select value={form.list_type} onChange={change('list_type')}>{choices.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></>}
 <label className="wide">Notes<textarea value={form.notes} onChange={change('notes')} rows={4} aria-describedby="public-notes-help"/></label></div><p id="public-notes-help">Other collectors can see these notes.</p>{!special&&<p>Use Edit list to replace a WANT or HAVE list. Changing set details keeps existing cards.</p>}
 {broad&&<label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I have checked that nothing is still needed or expected. Existing wanted cards must be marked Received or removed first.</label>}
 <button className="primary-button" disabled={broad&&!confirmed}>{busy?'Saving…':record?'Save':'Create set'}</button>{!record&&<p>You can add cards as soon as this set is created.</p>}</fieldset></form>;
}

function AddCards({record,onSave,busy,blocked=busy}){
 const special=record.id?.startsWith('display-');
 const [input,setInput]=useState(''),[kind,setKind]=useState(special?'names':'numbers'),[state,setState]=useState(record.list_type==='have_list'?'owned':'wanted');
 let values=[],error='';try{values=parseCards(input,kind);}catch(e){error=e.message;}
 return <form onSubmit={async e=>{e.preventDefault();if(await onSave(values,state,kind==='names'?'items':'card_numbers'))setInput('');}}><fieldset disabled={blocked}><h3>{special?'Add items':'Add cards'}</h3><div className="form-grid"><label>These are<select value={state} onChange={e=>setState(e.target.value)}><option value="wanted">{special?'Items':'Cards'} I need</option><option value="owned">{special?'Items':'Cards'} I have</option></select></label><label>What are you entering?<select value={kind} onChange={e=>setKind(e.target.value)}><option value="numbers">Numbers or card codes</option><option value="names">Names or other items</option></select></label></div><label>{kind==='names'?'One name or item on each line':'Card numbers or codes'}<textarea value={input} onChange={e=>setInput(e.target.value)} placeholder={kind==='names'?'Blue Border Griffey\nSigned postcard':'12 18 47 92'} rows={3}/></label><p>{kind==='names'?'Keep each full name on its own line.':'Separate cards with spaces, commas or new lines. Ranges stay as written; they are not expanded.'}</p>{error?<p role="alert">{error}</p>:values.length>0&&<p>Adding {values.length} {kind==='names'?'items':'cards'}: {values.join(', ')}</p>}<button className="primary-button" disabled={!values.length||!!error||record.list_type==='complete'&&state==='wanted'}>{busy?'Saving…':special?'Add items':'Add cards'}</button>{record.list_type==='complete'&&state==='wanted'&&<p>Change this set from Complete before adding cards you need.</p>}</fieldset></form>;
}

function ReplaceList({record,onSave,busy,blocked}){
 const [gid,setGid]=useState(record.groups.length===1?record.groups[0].id:''),[mode,setMode]=useState('want_list'),[kind,setKind]=useState('numbers'),[input,setInput]=useState(''),[confirmed,setConfirmed]=useState(false);
 let values=[],error='';try{values=parseCards(input,kind);if(values.length>500)error='Please replace at most 500 entries at once. Larger historical lists need a reviewed migration.';}catch(e){error=e.message;}
 return <form onSubmit={e=>{e.preventDefault();onSave({group_id:gid,list_type:mode,values,field_key:kind==='names'?'items':'card_numbers'});}}><fieldset disabled={blocked}><h3>Edit list</h3><p>Enter the entire replacement list yourself. We never calculate missing cards. Previous entries stay recoverable; other lists and notes are kept.</p>{record.groups.length>1&&<label>Which list should change?<select value={gid} onChange={e=>{setGid(e.target.value);setConfirmed(false);}} required><option value="">Choose a list</option>{record.groups.map((g,i)=><option key={g.id} value={g.id}>{g.label||statusNames[g.list_type]||'Source information'}{g.label?'':' '+(i+1)}</option>)}</select></label>}<label>New list type<select value={mode} onChange={e=>{setMode(e.target.value);setConfirmed(false);}}><option value="want_list">WANT list</option><option value="have_list">HAVE list</option></select></label><label>Entry format<select value={kind} onChange={e=>{setKind(e.target.value);setConfirmed(false);}}><option value="numbers">Numbers or card codes</option><option value="names">Names or items, one per line</option></select></label><label>Replacement entries<textarea rows={3} value={input} onChange={e=>{setInput(e.target.value);setConfirmed(false);}}/></label><p>Proposed {mode==='want_list'?'WANT':'HAVE'} list: {values.length?values.join(', '):'(no entries)'}</p>{error&&<p role="alert">{error}</p>}<label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I checked this replacement list. It replaces only the selected list’s entries.</label><button className="primary-button" disabled={!gid||!confirmed||!!error}>{busy?'Saving…':'Save replacement list'}</button></fieldset></form>;
}

export default function OwnerApp(){
 const [records,setRecords]=useState(null),[signed,setSigned]=useState(false),[view,setView]=useState(null),[record,setRecord]=useState(null),[changes,setChanges]=useState([]),[removed,setRemoved]=useState([]),[notice,setNotice]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[retry,setRetry]=useState(null),[credential,setCredential]=useState(''),[remembered,setRemembered]=useState(true),[cardSearch,setCardSearch]=useState(''),[edit,setEdit]=useState(false),[confirmRemove,setConfirmRemove]=useState(false),[showAll,setShowAll]=useState(false),[addOpen,setAddOpen]=useState(false),[replaceOpen,setReplaceOpen]=useState(false);
 const locked=useRef(false), opener=useRef(null);
 useEffect(()=>{publicRecords().then(setRecords).catch(()=>setError('The practice list could not be loaded. Please try again.'));request('/session').then(()=>setSigned(true)).catch(e=>{if(e.status!==401)setError(e.message);});},[]);
 const browseRecords=useMemo(()=>(records||[]).map(browseRecord),[records]);
 const blocked=busy||!!retry;
 const categories=CATEGORIES;
 function close(){if(locked.current)return;setView(null);setError('');setEdit(false);setConfirmRemove(false);setCardSearch('');setTimeout(()=>{if(opener.current?.isConnected)opener.current.focus();else document.getElementById('collection-search')?.focus();},0);}
 function show(name,event){opener.current=event?.currentTarget;setView(name);setError('');setRetry(null);}
 async function open(id,event){opener.current=event?.currentTarget||opener.current;setError('');setRetry(null);try{const r=await request('/owner/record?id='+encodeURIComponent(id));setRecord(r);setAddOpen(false);setReplaceOpen(false);setCardSearch('');setShowAll(false);setEdit(false);setConfirmRemove(false);setView('record');}catch(e){setError(e.message);if(e.status===401){setSigned(false);setView('login');}}}
 async function refresh(id){const p=await request('/public/record?id='+encodeURIComponent(id));setRecords(old=>p.deleted?(old||[]).filter(r=>r.id!==id):(old||[]).some(r=>r.id===id)?(old||[]).map(r=>r.id===id?p:r):[...(old||[]),p]);return p;}
 async function run(body,message){
  if(locked.current)return false;locked.current=true;setBusy(true);setError('');setRetry(null);
  try{const saved=await request('/action',body);setNotice(message);setRetry(null);
   // Refresh only the affected record. No dataset-wide publication or reload.
   try{const projection=await refresh(saved.record_id);
    if(record?.id===saved.record_id&&['transition','remove_item','restore_item','edit','add','delete'].includes(body.op)){
     setRecord(current=>{
      let groups=current.groups.map(g=>({...g,entries:g.entries.map(i=>i.id===body.item_id?{...i,...(body.op==='transition'?{state:body.state}:body.op==='remove_item'?{deleted_at:'removed',individually_removed:1}:body.op==='restore_item'?{deleted_at:null,individually_removed:0}:{})}:i)}));
      if(saved.added_items){for(const i of saved.added_items){let group=groups.find(g=>g.id===i.group_id);if(!group){const p=projection.groups.find(g=>g.id===i.group_id);group={id:i.group_id,kind:p.kind,list_type:p.list_type,label:p.label,entries:[]};groups.push(group);}group.entries.push(i);}groups=groups.map(g=>({...g,entries:[...g.entries].sort((a,b)=>a.field_key.localeCompare(b.field_key)||a.position-b.position)})).sort((a,b)=>projection.groups.findIndex(g=>g.id===a.id)-projection.groups.findIndex(g=>g.id===b.id));}
      return {...current,revision:saved.revision,content:{...current.content,...body.metadata},list_type:body.list_type||current.list_type,groups};
     });
    }else setRecord(await request('/owner/record?id='+encodeURIComponent(saved.record_id)));
    if(body.op==='create'){setView('record');setEdit(false);setAddOpen(true);}if(body.op==='delete')setView(null);
   }
   catch{setError('Saved, but the updated view could not be opened. Reload to see it.');}
   return true;
  }catch(e){setError(e.message);if(e.retry)setRetry({body,message});if(e.status===401){setSigned(false);setCredential('');setView('login');}return false;}
  finally{locked.current=false;setBusy(false);}
 }
 const action=(op,extra={},message='Saved')=>run({op,record_id:record.id,revision:record.revision,request_id:crypto.randomUUID(),...extra},message);
 async function addCards(values,state,field_key){
  // Bounded requests, invisible to Dad; each confirmed chunk is durable.
  let current=record,done=0;
  for(let start=0;start<values.length;start+=20){
   const body={op:'add',record_id:current.id,revision:current.revision,request_id:crypto.randomUUID(),values:values.slice(start,start+20),state,field_key};
   if(!await run(body,`${done+body.values.length} ${record.id.startsWith('display-')?'items':'cards'} added`)){if(done)setError(`The first ${done} cards were saved. Reopen this set and check the list before adding the remaining cards.`);return false;}
   done+=body.values.length;current={...current,revision:current.revision+1};
  }setAddOpen(false);return true;
 }
 async function recent(event){show('recent',event);try{const r=await request('/owner/recent');setChanges(r.changes);setRemoved(r.removed);}catch(e){setError(e.message);}}
 return <><div className="staging-banner">Practice website · Changes here do not affect the public wantlist</div>
 <Browse records={records===null?null:browseRecords} toolbar={<div className="owner-toolbar"><p>{signed?'You’re signed in. Find a set to update your cards.':'Browse this staging sample, or sign in to practice editing.'}</p><div>{signed?<><button onClick={e=>show('new',e)}>Add a new set</button><button onClick={recent}>Recent Changes</button><button disabled={blocked} onClick={async()=>{try{await request('/logout',{});setSigned(false);setRecord(null);setView(null);setNotice('Signed out');}catch(e){setError(e.message);}}}>Log out</button></>:<button onClick={e=>show('login',e)}>Owner Login</button>}</div></div>} ownerAction={signed?r=><button className="edit-set" onClick={e=>open(r.id,e)}>Edit this set</button>:undefined}/>
 <div className="owner-feedback" role="status" aria-live="polite">{notice}</div>{!view&&error&&<div className="owner-feedback error" role="alert">{error}<button onClick={async()=>{try{setRecords(await publicRecords());setError('');}catch{setError('The list could not be loaded. Please try again shortly.');}}}>Try loading the list again</button></div>}
 {view&&<Dialog title={view==='login'?'Owner Login':view==='new'?'Add a new set':view==='recent'?'Recent Changes':titleOf(record)} onClose={close} busy={busy}>
  {error&&<p className="owner-error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{retry&&<button disabled={busy} onClick={async()=>{const pending=retry;if(await run(pending.body,pending.message)&&pending.body.op==='add')setAddOpen(false);}}>Try saving again</button>}
  {view==='login'&&<form onSubmit={async e=>{e.preventDefault();if(locked.current)return;locked.current=true;setBusy(true);setError('');try{await request('/login',{credential,remembered});setCredential('');setSigned(true);setView(null);setNotice('Signed in');}catch(e){setError(e.message);setCredential('');}finally{locked.current=false;setBusy(false);}}}><label>Owner PIN<input autoFocus type="password" autoComplete="current-password" inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={credential} onChange={e=>setCredential(e.target.value)} required/></label><label className="check"><input type="checkbox" checked={remembered} onChange={e=>setRemembered(e.target.checked)}/>Keep me signed in on this computer</label><p>Leave this checked on your private computer. Uncheck it on a shared computer.</p><button className="primary-button" disabled={blocked}>{busy?'Signing in…':'Sign in'}</button></form>}
  {view==='new'&&<MetadataForm categories={categories} busy={busy} blocked={blocked} onSave={(metadata,list_type)=>{if(['Eau Claire Players','Milwaukee 8x10 List','Brewers Bobblehead Wantlist'].includes(metadata.display_category)){setError('This category already has its own listing. Open it and add items there.');return;}return run({op:'create',metadata,list_type,request_id:crypto.randomUUID()},'Set created. Add your cards below.');}}/>}
  {view==='record'&&record?.deleted_at&&<><p>This set was removed. Restore it to make changes.</p><button disabled={blocked} onClick={()=>action('restore',{},'Set restored')}>Restore this set</button></>}
  {view==='record'&&record&&!record.deleted_at&&<>
   <p>{record.id.startsWith('display-')?statusNames[record.list_type]?.replace('Cards','Items'):statusNames[record.list_type]}{record.list_type==='have_list'?' · Listed cards are already owned. No missing cards are inferred.':''}</p>
   <div className="owner-actions"><button disabled={blocked} onClick={()=>setEdit(!edit)}>{edit?'Hide set information':'Edit set information'}</button>{!record.id.startsWith('display-')&&<button disabled={blocked} onClick={()=>setReplaceOpen(!replaceOpen)}>Edit list</button>}<button disabled={blocked} onClick={()=>setAddOpen(!addOpen)}>{addOpen?(record.id.startsWith('display-')?'Hide add items':'Hide add cards'):(record.id.startsWith('display-')?'Add items':'Add cards')}</button>{!record.id.startsWith('display-')&&<button disabled={blocked} onClick={()=>setConfirmRemove(true)}>Remove set</button>}</div>
   {confirmRemove&&<section className="remove-confirm"><p>Remove this whole set from the list? You can restore it in Recent Changes.</p><button disabled={blocked} onClick={()=>action('delete',{},'Set removed. You can restore it in Recent Changes.')}>Yes, remove this set</button><button onClick={()=>setConfirmRemove(false)}>Keep this set</button></section>}
   {edit&&<MetadataForm key={record.id} record={record} categories={categories} busy={busy} blocked={blocked} onSave={async(metadata,list_type)=>{if(await action('edit',{metadata,list_type},'Set information saved'))setEdit(false);}}/>}
   {record.content.uncertainty?.length>0&&<p>Uncertainty: {record.content.uncertainty.join(' ')}</p>}
   {record.id==='display-eau-claire-players'&&<p>Player names are broad interests. Use Add items to track a specific card or photo; receiving one card does not complete a player’s wantlist.</p>}
   {record.content.notes?.length>0&&<section><h3>Notes</h3>{record.content.notes.map((n,i)=><p key={i}>{n}</p>)}</section>}
   {replaceOpen&&<ReplaceList record={record} busy={busy} blocked={blocked} onSave={async extra=>{if(await action('replace_list',extra,'List replaced. Previous cards are kept for recovery.'))setReplaceOpen(false);}}/>}
   {addOpen&&<AddCards record={record} onSave={addCards} busy={busy} blocked={blocked}/>}
   <label>{record.id.startsWith('display-')?'Find an item in this list':'Find a card in this set'}<input type="search" value={cardSearch} onChange={e=>setCardSearch(e.target.value)} placeholder="Card number or name"/></label>
   {record.groups.filter(g=>!(g.kind==='primary'&&g.list_type==='complete'&&!g.entries.length&&record.list_type!=='complete')).map(g=><section key={g.id} className="owner-group"><h3>{g.label||(g.list_type==='want_list'&&g.entries.some(i=>!i.deleted_at&&i.state==='owned')?(record.id.startsWith('display-')?'Items in this list':'Cards in this list'):record.id.startsWith('display-')?statusNames[g.list_type]?.replace('Cards','Items'):statusNames[g.list_type])||'Original source information'}</h3>{g.description&&<p>{g.description}</p>}{(g.notes||[]).map((n,i)=><p key={i}>{n}</p>)}
    {g.entries.filter(i=>!i.deleted_at&&i.value.toLowerCase().includes(cardSearch.toLowerCase())).slice(0,showAll?undefined:40).map(i=><div className="owner-item" key={i.id}><div><strong>{i.value}</strong><span>{!i.actionable?(g.list_type==='have_list'?'Already owned · original listing':g.list_type==='want_list'?'Still needed · original listing':'Original source information'):i.state==='owned'?'Already owned':i.state==='pending'?'Someone is sending this':'Still needed'}</span></div><div className="item-actions">
     {!!i.actionable&&i.state==='wanted'&&<><button disabled={blocked} onClick={()=>action('transition',{item_id:i.id,state:'pending'},`${i.value}: Someone is sending this`)}>Someone is sending this</button><button disabled={blocked} onClick={()=>action('transition',{item_id:i.id,state:'owned'},`${i.value} marked Received`)}>Received</button></>}
     {!!i.actionable&&i.state==='pending'&&<><button disabled={blocked} onClick={()=>action('transition',{item_id:i.id,state:'owned'},`${i.value} marked Received`)}>Received</button><button disabled={blocked} onClick={()=>action('transition',{item_id:i.id,state:'wanted'},`${i.value}: Still need this`)}>Still need this</button></>}
     {!!i.actionable&&i.state==='owned'&&record.list_type!=='complete'&&<details><summary>Correct a mistake</summary><button disabled={blocked} onClick={()=>action('transition',{item_id:i.id,state:'wanted'},`${i.value}: Still need this`)}>Still need this</button></details>}
     <details><summary>More</summary><button disabled={blocked} onClick={()=>action('remove_item',{item_id:i.id},`${i.value} removed. Restore it below.`)}>Remove</button></details>
    </div></div>)}
    {!showAll&&g.entries.filter(i=>!i.deleted_at&&i.value.toLowerCase().includes(cardSearch.toLowerCase())).length>40&&<button onClick={()=>setShowAll(true)}>Show all cards in this group</button>}
    {g.entries.some(i=>i.deleted_at&&!i.individually_removed)&&<details><summary>Previous list entries</summary><p>These belong to an earlier list. Use Recent Changes to undo the latest list replacement, or Edit list to enter a new replacement. We keep their original meaning.</p><p>{g.entries.filter(i=>i.deleted_at&&!i.individually_removed).map(i=>i.value).join('; ')}</p></details>}
    {g.entries.some(i=>i.deleted_at&&i.individually_removed)&&<details><summary>Recently removed {record.id.startsWith('display-')?'items':'cards'}</summary>{g.entries.filter(i=>i.deleted_at&&i.individually_removed).map(i=><p key={i.id}>{i.value} <button disabled={blocked} onClick={()=>action('restore_item',{item_id:i.id},`${i.value} restored`)}>Restore</button></p>)}</details>}
   </section>)}
  </>}
  {view==='recent'&&<><p>Undo is available only when it won’t overwrite a newer change to that set.</p>{removed.length>0&&<section><h3>Removed sets</h3>{removed.map(r=><p key={r.id}>{titleOf(r)} <button disabled={blocked} onClick={()=>run({op:'restore',record_id:r.id,revision:r.revision,request_id:crypto.randomUUID()},'Set restored')}>Restore set</button></p>)}</section>}
   <ol className="recent-list">{changes.map(h=><li key={h.id}><strong>{titleOf(h)}</strong><p>{historyLabel(h)}</p><time>{new Date(h.created_at).toLocaleString()}</time><div><button disabled={blocked} onClick={e=>open(h.record_id,e)}>Open set</button>{h.undoable?<button disabled={blocked} onClick={async()=>{if(await run({op:'undo',history_id:h.id,record_id:h.record_id,revision:h.revision,request_id:crypto.randomUUID()},'Change undone')){try{const r=await request('/owner/recent');setChanges(r.changes);setRemoved(r.removed);}catch{setError('Change undone. Reopen Recent Changes to refresh the list.');}}}}>Undo</button>:<p className="undo-explanation">{h.undo_reason}</p>}</div></li>)}</ol>
  </>}
 </Dialog>}
 </>;
}
