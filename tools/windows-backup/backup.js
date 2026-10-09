import {publicKey,encrypt,decrypt,sha256,b64,un64} from './crypto.js';
const el=id=>document.getElementById(id),capability=location.hash.slice(1),enc=new TextEncoder();
history.replaceState(null,'',location.pathname);
const day=new Date().toISOString().slice(0,10);el('day').textContent='Cloudflare quota day: '+day+' UTC (not your local calendar day).';
let encryptedBytes,receipt,recoveryReceipt,busy=false;
function status(message){el('status').textContent=message;}
function download(name,bytes,type='application/json'){
 const url=URL.createObjectURL(new Blob([bytes],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
async function local(path,data){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-WantList-Local':capability},body:JSON.stringify(data),cache:'no-store',credentials:'omit'});
 const result=await response.json();if(!response.ok)throw Error(result.error||'Local operation stopped.');return result;
}
async function fileJSON(id,limit=65536){const file=el(id).files[0];if(!file||file.size>limit)throw Error('Selected file is missing or exceeds the reviewed size limit.');try{return JSON.parse(await file.text());}catch{throw Error('Selected file is not valid JSON. No data was sent.');}}
function lock(value){busy=value;for(const form of [el('export-form'),el('recover-form')])for(const button of form.querySelectorAll('button'))button.disabled=value;el('close').disabled=value;}
el('export-form').onsubmit=async event=>{
 event.preventDefault();if(busy)return;lock(true);el('ready').hidden=true;el('verified').hidden=true;encryptedBytes?.fill(0);encryptedBytes=null;receipt=null;let plaintext;
 try{
  // Validate the public key before any network/data read.
  const recipient=await publicKey(await fileJSON('public-key'));
  status('Checking account quota and staging identity. Then two complete read-only snapshots and a memory-only restoration…');
  const data={account:el('account').value.trim(),token:el('token').value.trim(),approvals:{reviewed:el('approved').checked,free:el('free').checked,quiet:el('quiet').checked,encrypted_pc:el('encrypted-pc').checked,quota_day:day,email_today:el('notice').checked,dashboard_reads:Number(el('reads').value),dashboard_writes:Number(el('writes').value)}};
  let result;try{result=await local('/backup',data);}finally{data.token='';el('token').value='';}
  plaintext=un64(result.plaintext_b64);result.plaintext_b64='';
  status('All rows and schema restored exactly in isolated memory. Encrypting locally with your public key…');
  encryptedBytes=enc.encode(JSON.stringify(await encrypt(plaintext,recipient)));
  const filename='wantlist-staging-'+new Date().toISOString().replaceAll(':','-').replaceAll('.','-')+'.ENCRYPTED.json';
  receipt={filename,encrypted_bytes:encryptedBytes.length,encrypted_sha256:await sha256(encryptedBytes),public_key_fingerprint:recipient.fingerprint,...result.report,created_utc:new Date().toISOString(),durable_recovery_complete:false};
  el('checksum').textContent='Filename: '+filename+'\nSize: '+receipt.encrypted_bytes+' bytes\nSHA-256: '+receipt.encrypted_sha256;
  el('ready').hidden=false;status('Encrypted backup ready to save. Save both files, then verify the actual saved copy below.');
 }catch(error){status(error.message||'Backup stopped. Nothing saved.');}
 finally{plaintext?.fill(0);el('token').value='';lock(false);}
};
el('download').onclick=()=>{if(encryptedBytes)download(receipt.filename,encryptedBytes);};
el('receipt').onclick=()=>{if(receipt)download(receipt.filename+'.receipt.json',JSON.stringify(receipt,null,2));};
el('recover-form').onsubmit=async event=>{
 event.preventDefault();if(busy)return;lock(true);el('verified').hidden=true;recoveryReceipt=null;status('Checking the actual saved file checksum…');let plaintext;
 try{
  const file=el('backup-file').files[0];if(!file||file.size>192*1024*1024)throw Error('Backup file exceeds the reviewed size limit.');
  const bytes=new Uint8Array(await file.arrayBuffer()),checksum=await sha256(bytes);
  if(checksum!==el('expected').value.trim().toLowerCase())throw Error('Saved-file checksum mismatch. Recovery stopped.');
  status('Saved-file checksum matched. Unlocking locally and verifying authenticated encryption…');
  let envelope;try{envelope=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{throw Error('Encrypted backup is not valid JSON.');}
  plaintext=await decrypt(envelope,await fileJSON('private-key'),el('password').value);
  el('password').value='';
  status('Decryption verified. Testing all rows and schema in a new isolated in-memory database…');
  const result=await local('/restore',{plaintext_b64:b64(plaintext)});
  recoveryReceipt={filename:file.name,encrypted_sha256:checksum,encrypted_bytes:file.size,verified_utc:new Date().toISOString(),...result.report,recovery_verified:true,durable_copy:'Owner-selected actual local/USB file; no Cloudflare change'};
  el('recovery-result').textContent='SHA-256: '+checksum+'\nEncryption and plaintext checksum: verified\nExact rows and schema: verified\nDatabase integrity and foreign keys: verified\nTables: '+Object.keys(result.report.table_counts).length+'\nPlaintext file saved: no\nLive website changed: no';
  el('verified').hidden=false;status('Recovery succeeded for this saved copy. Save the verification receipt and keep the backup safe.');
 }catch(error){status('Recovery failed: '+(error.message||'Check the password and files.')+' No live database was changed.');}
 finally{plaintext?.fill(0);el('password').value='';el('private-key').value='';lock(false);}
};
el('proof').onclick=()=>{if(recoveryReceipt)download(recoveryReceipt.filename+'.recovery-verified.json',JSON.stringify(recoveryReceipt,null,2));};
el('close').onclick=async()=>{if(busy)return;encryptedBytes?.fill(0);encryptedBytes=null;receipt=null;recoveryReceipt=null;for(const input of document.querySelectorAll('input'))if(input.type!=='checkbox')input.value='';try{await local('/close',{});}finally{document.body.replaceChildren();const p=document.createElement('p');p.textContent='Local tool closed. Close this browser tab. Keep only your encrypted backup and receipts.';document.body.append(p);}};
