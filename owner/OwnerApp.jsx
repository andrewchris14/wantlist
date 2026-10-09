import {useEffect,useMemo,useRef,useState} from 'react';
import ListingEditor from './ListingEditor.jsx';
import CategoryManager from './CategoryManager.jsx';
import Browse,{CATEGORIES,originalCategory,compactStatus} from './Browse.jsx';
import {request,publicRecords} from './api.js';
import {browseRecord,statusNames,titleOf,historyLabel,newSetCategory,recordYear} from './model.js';

function Dialog({title,children,onClose,busy}){
 const ref=useRef();
 useEffect(()=>{ref.current.showModal();const header=ref.current.querySelector('.dialog-header');const observer=new ResizeObserver(()=>ref.current?.style.setProperty('--dialog-header-height',header.offsetHeight+'px'));observer.observe(header);return()=>{observer.disconnect();ref.current?.close();};},[]);
 return <dialog ref={ref} aria-labelledby="owner-dialog-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><div className="dialog-header"><h2 id="owner-dialog-title">{title}</h2><button disabled={busy} onClick={onClose} aria-label="Close">Close</button></div>{children}</dialog>;
}
function MetadataForm({record,categories,onSave,busy,blocked=busy}){
 const special=record?.id?.startsWith('display-');
 const derivedType=record?.list_type==='uncertain'?({'HAVE list':'have_list','WANT list':'want_list','COMPLETE':'complete'}[compactStatus({id:record.id,...record.content,list_type:record.list_type})]||''):record?.list_type||'want_list';
 const fields=()=>{const c=record?.content||{};return {year:recordYear(c)||'',brand:c.brand||'',set_name:c.set_name||'',category:c.category||'baseball_cards',display_category:originalCategory({id:record?.id,...c})||'OBC Wantlist',notes:(c.notes||[]).join('\n'),list_type:derivedType};};
 const [form,setForm]=useState(fields),previous=useRef(fields());
 useEffect(()=>{const next=fields(),prior=previous.current;setForm(current=>Object.fromEntries(Object.keys(next).map(k=>[k,current[k]===prior[k]?next[k]:current[k]])));previous.current=next;},[record?.revision]);
 const [confirmed,setConfirmed]=useState(false);
 const change=k=>e=>{setForm({...form,[k]:e.target.value});if(k==='list_type')setConfirmed(false);};
 const completeChange=!special&&form.list_type==='complete'&&form.list_type!==record?.list_type;
 const emptyConversion=record&&!record.groups.length&&['want_list','have_list'].includes(form.list_type)&&form.list_type!==record.list_type;
 const broad=completeChange||emptyConversion;
 const choices=Object.entries(statusNames).filter(([k])=>k!=='uncertain');
 return <form onSubmit={e=>{e.preventDefault();const notes=form.notes.split('\n').filter(x=>x.trim());onSave(special?{notes}:{year:form.year||null,brand:form.brand||null,set_name:form.set_name.trim(),category:record?form.category:newSetCategory(form.display_category),display_category:form.display_category,notes},record?.list_type==='uncertain'&&form.list_type===derivedType?'uncertain':form.list_type,confirmed);}}>
 <fieldset disabled={blocked}><div className="form-grid">{!special&&<><label>Year or years<input value={form.year} onChange={change('year')} placeholder="2027 or 2026–2027"/></label><label>Manufacturer<input value={form.brand} onChange={change('brand')} placeholder="Topps"/></label><label className="wide">Set name<input required maxLength={500} value={form.set_name} onChange={change('set_name')} placeholder="Topps"/></label><label>Category<select value={form.display_category} onChange={change('display_category')}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><label>List type<select value={form.list_type} onChange={change('list_type')}>{!form.list_type&&<option value="" disabled>Choose a list type</option>}{choices.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></>}
 <label className="wide">Notes<textarea value={form.notes} onChange={change('notes')} rows={4} aria-describedby="public-notes-help"/></label></div><p id="public-notes-help">Other collectors can see these notes.</p>
 {broad&&<label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{emptyConversion?'I confirm the new represented list is empty.':'I confirm this set is COMPLETE. Prior entries remain recoverable and are not marked Received automatically.'}</label>}
 <button className="primary-button" disabled={broad&&!confirmed}>{busy?'Saving…':record?'Save changes':'Create set'}</button>{!record&&<p>You can add cards as soon as this set is created.</p>}</fieldset></form>;
}

export default function OwnerApp(){
 const [records,setRecords]=useState(null),[signed,setSigned]=useState(false),[view,setView]=useState(null),[record,setRecord]=useState(null),[changes,setChanges]=useState([]),[removed,setRemoved]=useState([]),[notice,setNotice]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[retry,setRetry]=useState(null),[credential,setCredential]=useState(''),[remembered,setRemembered]=useState(true),[confirmRemove,setConfirmRemove]=useState(false),[categoryRows,setCategoryRows]=useState(CATEGORIES.map((name,i)=>({id:String(i),name,historical:1})));
 const [reauth,setReauth]=useState(false);
 const [dirty,setDirty]=useState(false),[discard,setDiscard]=useState(false);
 useEffect(()=>{const handler=e=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[dirty]);
 const locked=useRef(false), opener=useRef(null);
 useEffect(()=>{publicRecords().then(setRecords).catch(()=>setError('The practice list could not be loaded. Please try again.'));request('/session').then(()=>setSigned(true)).catch(e=>{if(e.status!==401)setError(e.message);});},[]);
 const browseRecords=useMemo(()=>(records||[]).map(browseRecord),[records]);
 const blocked=busy||!!retry||reauth;
 const categories=categoryRows.map(c=>c.name);
 async function loadCategories(){const r=await request('/public/categories');setCategoryRows(r.categories);const p=await publicRecords();setRecords(p);}
 useEffect(()=>{request('/public/categories').then(r=>setCategoryRows(r.categories)).catch(()=>{});},[]);
 function close(force=false){if(locked.current)return;if(dirty&&force!==true){setDiscard(true);return;}setDirty(false);setDiscard(false);setView(null);setError('');setConfirmRemove(false);setTimeout(()=>{if(opener.current?.isConnected)opener.current.focus();else document.getElementById('collection-search')?.focus();},0);}
 function show(name,event){opener.current=event?.currentTarget;setView(name);setError('');setRetry(null);}
 async function open(id,event){opener.current=event?.currentTarget||opener.current;setError('');setRetry(null);try{const r=await request('/owner/record?id='+encodeURIComponent(id));setRecord(r);setConfirmRemove(false);setView('record');}catch(e){setError(e.message);if(e.status===401){setSigned(false);setView('login');}}}
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
    }else {try{setRecord(await request('/owner/record?id='+encodeURIComponent(saved.record_id)));}catch{setRecord({id:saved.record_id,revision:saved.revision,list_type:projection.list_type,deleted_at:projection.deleted?'removed':null,content:projection,groups:projection.groups.map(g=>({...g,entries:g.entries.map(i=>({...i,group_id:g.id,deleted_at:null}))}))});setError('Saved. Sign in again if your session has expired.');}}
    if(body.op==='create'){setView('record');}if(body.op==='delete')setView(null);
   }
   catch{setError('Saved, but the updated view could not be opened. Reload to see it.');}
   return true;
  }catch(e){setError(e.message);if(e.retry)setRetry({body,message});if(e.status===401){setSigned(false);setCredential('');if(view==='record'){setReauth(true);setTimeout(()=>document.querySelector('dialog').scrollTop=0,0);}else setView('login');}return false;}
  finally{locked.current=false;setBusy(false);}
 }
 const action=(op,extra={},message='Saved')=>run({op,record_id:record.id,revision:record.revision,request_id:crypto.randomUUID(),...extra},message);
 async function recent(event){show('recent',event);try{const r=await request('/owner/recent');setChanges(r.changes);setRemoved(r.removed);}catch(e){setError(e.message);}}
 return <><div className="staging-banner">Practice website · Changes here do not affect the public wantlist</div>
 <Browse categories={categories} records={records===null?null:browseRecords} toolbar={<div className="owner-toolbar"><p>{signed?'You’re signed in. Find a set to update your cards.':'Browse this staging sample, or sign in to practice editing.'}</p><div>{signed?<><button onClick={e=>show('new',e)}>Add a new set</button><button onClick={e=>show('categories',e)}>Manage categories</button><button onClick={recent}>Recent Changes</button><button disabled={blocked} onClick={async()=>{try{await request('/logout',{});setSigned(false);setRecord(null);setView(null);setNotice('Signed out');}catch(e){setError(e.message);}}}>Log out</button></>:<button onClick={e=>show('login',e)}>Owner Login</button>}</div></div>} ownerAction={signed?r=><button className="edit-set" onClick={e=>open(r.id,e)}>Edit this set</button>:undefined}/>
 <div className="owner-feedback" role="status" aria-live="polite">{notice}</div>{!view&&error&&<div className="owner-feedback error" role="alert">{error}<button onClick={async()=>{try{setRecords(await publicRecords());setError('');}catch{setError('The list could not be loaded. Please try again shortly.');}}}>Try loading the list again</button></div>}
 {view&&<Dialog title={view==='login'?'Owner Login':view==='new'?'Add a new set':view==='recent'?'Recent Changes':view==='categories'?'Manage categories':titleOf(record)} onClose={()=>close()} busy={busy}>
  {error&&<p className="owner-error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{retry&&<button disabled={busy} onClick={async()=>{const pending=retry;await run(pending.body,pending.message)}}>Try saving again</button>}
  {(view==='login'||reauth)&&<form onSubmit={async e=>{e.preventDefault();if(locked.current)return;locked.current=true;setBusy(true);setError('');try{await request('/login',{credential,remembered});setCredential('');setSigned(true);if(reauth)setReauth(false);else setView(null);setNotice('Signed in');}catch(e){setError(e.message);setCredential('');}finally{locked.current=false;setBusy(false);}}}><label>Owner PIN<input autoFocus type="password" autoComplete="current-password" inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={credential} onChange={e=>setCredential(e.target.value)} required/></label><label className="check"><input type="checkbox" checked={remembered} onChange={e=>setRemembered(e.target.checked)}/>Keep me signed in on this computer</label><p>Leave this checked on your private computer. Uncheck it on a shared computer.</p><button className="primary-button" disabled={busy}>{busy?'Signing in…':'Sign in'}</button></form>}
  {view==='categories'&&<CategoryManager categories={categoryRows} onChanged={loadCategories}/>}
  {view==='new'&&<MetadataForm categories={categories} busy={busy} blocked={blocked} onSave={(metadata,list_type)=>{if(['Eau Claire Players','Milwaukee 8x10 List'].includes(metadata.display_category)){setError('This category already has its own listing. Open it and add items there.');return;}return run({op:'create',metadata,list_type,request_id:crypto.randomUUID()},'Set created. Add your cards below.');}}/>}
  {view==='record'&&record?.deleted_at&&<><p>This set was removed. Restore it to make changes.</p><button disabled={blocked} onClick={()=>action('restore',{},'Set restored')}>Restore this set</button></>}
  {view==='record'&&record&&!record.deleted_at&&<>
   {discard&&<section className="discard-confirm" role="alertdialog" aria-label="Unsaved changes"><p>You have unsaved changes. Are you sure you want to discard them?</p><button onClick={()=>setDiscard(false)}>Keep editing</button><button onClick={()=>close(true)}>Discard changes</button></section>}
   <ListingEditor key={record.id+':'+record.revision} record={record} categories={categories} blocked={blocked} onDirty={setDirty} onSave={async extra=>{const ok=await action('edit_session',extra,'Changes saved');if(ok)setDirty(false);return ok;}} onRemove={()=>setConfirmRemove(true)}/>
   {confirmRemove&&<section className="remove-confirm"><p>Remove this whole set? Unsaved edits will be discarded. You can restore it in Recent Changes.</p><button disabled={blocked} onClick={async()=>{if(await action('delete',{},'Set removed')){setDirty(false);setConfirmRemove(false);}}}>Yes, remove this set</button><button onClick={()=>setConfirmRemove(false)}>Keep this set</button></section>}
  </>}
  {view==='recent'&&<><p>Undo is available only when it won’t overwrite a newer change to that set.</p>{removed.length>0&&<section><h3>Removed sets</h3>{removed.map(r=><p key={r.id}>{titleOf(r)} <button disabled={blocked} onClick={()=>run({op:'restore',record_id:r.id,revision:r.revision,request_id:crypto.randomUUID()},'Set restored')}>Restore set</button></p>)}</section>}
   <ol className="recent-list">{changes.map(h=><li key={h.id}><strong>{titleOf(h)}</strong><p>{historyLabel(h)}</p><time>{new Date(h.created_at).toLocaleString()}</time><div><button disabled={blocked} onClick={e=>open(h.record_id,e)}>Open set</button>{h.undoable?<button disabled={blocked} onClick={async()=>{if(await run({op:'undo',history_id:h.id,record_id:h.record_id,revision:h.revision,request_id:crypto.randomUUID()},'Change undone')){try{const r=await request('/owner/recent');setChanges(r.changes);setRemoved(r.removed);}catch{setError('Change undone. Reopen Recent Changes to refresh the list.');}}}}>Undo</button>:<p className="undo-explanation">{h.undo_reason}</p>}</div></li>)}</ol>
  </>}
 </Dialog>}
 </>;
}
