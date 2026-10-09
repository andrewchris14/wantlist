import {useState} from 'react';
import {parseCards} from './model.js';
export default function BulkEdit({group,record,blocked,onApply,onCancel,conversion}){
 const active=group.entries.filter(i=>!i.deleted_at),names=active.some(i=>i.field_key==='items');
 const [kind,setKind]=useState(names?'names':'numbers'),[mode,setMode]=useState(conversion||group.list_type),[text,setText]=useState(conversion?'':active.map(i=>i.value).join(names?'\n':' ')),[confirm,setConfirm]=useState(false);
 let values=[],error='';try{values=parseCards(text,kind);if(values.length>500)error='At most 500 entries can be replaced at once. Larger source lists require a reviewed migration.';}catch(e){error=e.message;}
 const same=mode===group.list_type,removed=active.filter(i=>!same||!values.includes(i.value)),added=values.filter(v=>!same||!active.some(i=>i.value===v)),pending=removed.filter(i=>i.state==='pending');
 return <section className="bulk-editor"><h3>{conversion?'Confirm new represented list':'Bulk Edit'}</h3><p>{conversion?'Enter the new represented identifiers explicitly. Existing entries will remain in history.':'Apply updates the draft. Save changes persists it. Notes and unrelated inventories stay intact. Literal ranges are not expanded.'}</p>
 <label hidden={!conversion}>New list type<select disabled={blocked} value={mode} onChange={e=>{setMode(e.target.value);setText('');setConfirm(false);}}><option value="want_list">WANT list</option><option value="have_list">HAVE list</option></select></label>
 <label>Entry format<select disabled={blocked} value={kind} onChange={e=>{setKind(e.target.value);setConfirm(false);}}><option value="numbers">Numbers or codes</option><option value="names">Names, one per line</option></select></label>
 <label>Current cards/items<textarea disabled={blocked} value={text} rows={6} onChange={e=>{setText(e.target.value);setConfirm(false);}}/></label>
 <p>Bulk Edit supports up to 500 entries; larger lists are never truncated.</p><p role="status">{added.length} added · {removed.length} removed · {same?active.length-removed.length:0} unchanged</p>{pending.length>0&&<p className="source-note">Warning: {pending.length} pending entries will be removed: {pending.map(i=>i.value).join('; ')}</p>}
 {error&&<p role="alert">{error}</p>}<label className="check"><input type="checkbox" disabled={blocked} checked={confirm} onChange={e=>setConfirm(e.target.checked)}/>{same?'I confirm these identifiers and changes. Unchanged entries keep their current states.':`I confirm these identifiers represent my ${mode==='have_list'?'owned':'needed'} items.`}{pending.length?' I also confirm the removal of pending entries.':''}</label>
 <button disabled={blocked||!confirm||!!error||!['want_list','have_list'].includes(mode)} onClick={()=>onApply({group_id:group.id,list_type:mode,values,field_key:kind==='names'?'items':'card_numbers',confirm_pending_removal:confirm})}>Apply changes</button><button disabled={blocked} onClick={onCancel}>Cancel</button></section>;
}
