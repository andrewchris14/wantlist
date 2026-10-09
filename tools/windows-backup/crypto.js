// Same envelope and protected recovery-key formats as tools/backup-recovery.html.
// Plaintext remains bytes; never parse/re-serialize its int64 database values here.
const enc=new TextEncoder(),dec=new TextDecoder('utf-8',{fatal:true});
export const hex=buffer=>Array.from(new Uint8Array(buffer),b=>b.toString(16).padStart(2,'0')).join('');
export const sha256=async bytes=>hex(await crypto.subtle.digest('SHA-256',bytes));
export const un64=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
export function b64(bytes){let parts=[];const view=new Uint8Array(bytes);for(let i=0;i<view.length;i+=8192)parts.push(String.fromCharCode(...view.subarray(i,i+8192)));return btoa(parts.join(''));}
export function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
export async function publicKey(jwk){
 const allowed=new Set(['kty','n','e','alg','key_ops','ext']);
 if(!jwk||jwk.kty!=='RSA'||Object.keys(jwk).some(k=>!allowed.has(k))||
    (jwk.alg&&jwk.alg!=='RSA-OAEP-256')||(jwk.key_ops&&(!Array.isArray(jwk.key_ops)||jwk.key_ops.some(k=>k!=='encrypt')||!jwk.key_ops.includes('encrypt'))))throw Error('Choose your existing PUBLIC encryption key, never a private recovery key.');
 const n=un64(jwk.n.replaceAll('-','+').replaceAll('_','/'));
 if(n.length<384||n.length>1024||(n.length===384&&n[0]<128))throw Error('Public RSA key must be at least 3072 bits.');
 const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSA-OAEP',hash:'SHA-256'},false,['encrypt']);
 return {key,fingerprint:await sha256(enc.encode(canonical(jwk)))};
}
export async function encrypt(bytes,recipient){
 const metadata={format:'wantlist-encrypted-backup-v1',plaintext_sha256:await sha256(bytes),key_fingerprint:recipient.fingerprint};
 const aad=enc.encode(canonical(metadata)),nonce=crypto.getRandomValues(new Uint8Array(12));
 const aes=await crypto.subtle.generateKey({name:'AES-GCM',length:256},true,['encrypt']);
 const raw=new Uint8Array(await crypto.subtle.exportKey('raw',aes));
 try{return {metadata,aad:b64(aad),nonce:b64(nonce),wrapped_key:b64(await crypto.subtle.encrypt({name:'RSA-OAEP'},recipient.key,raw)),ciphertext:b64(await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce,additionalData:aad},aes,bytes))};}
 finally{raw.fill(0);}
}
export async function decrypt(envelope,saved,password){
 if(saved?.format!=='wantlist-recovery-key-v1'||saved.iterations!==600000||envelope.metadata?.format!=='wantlist-encrypted-backup-v1')throw Error('Unsupported recovery files.');
 const aad=un64(envelope.aad),authenticated=JSON.parse(dec.decode(aad));
 if(canonical(authenticated)!==canonical(envelope.metadata)||!/^[a-f0-9]{64}$/.test(authenticated.plaintext_sha256))throw Error('Backup metadata has changed.');
 const salt=un64(saved.salt),nonce=un64(saved.nonce);
 if(salt.length!==16||nonce.length!==12||un64(envelope.nonce).length!==12)throw Error('Invalid recovery files.');
 const passwordBytes=enc.encode(password);
 let raw,unwrapped;
 try{
  const base=await crypto.subtle.importKey('raw',passwordBytes,'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt,iterations:saved.iterations},base,{name:'AES-GCM',length:256},false,['decrypt']);
  raw=new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:nonce},key,un64(saved.ciphertext)));
  const privateKey=await crypto.subtle.importKey('pkcs8',raw,{name:'RSA-OAEP',hash:'SHA-256'},false,['decrypt']);
  unwrapped=new Uint8Array(await crypto.subtle.decrypt({name:'RSA-OAEP'},privateKey,un64(envelope.wrapped_key)));
  const aes=await crypto.subtle.importKey('raw',unwrapped,{name:'AES-GCM'},false,['decrypt']);
  const plaintext=new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:un64(envelope.nonce),additionalData:aad},aes,un64(envelope.ciphertext)));
  if(await sha256(plaintext)!==authenticated.plaintext_sha256){plaintext.fill(0);throw Error('Plaintext checksum mismatch.');}
  return plaintext;
 }finally{passwordBytes.fill(0);raw?.fill(0);unwrapped?.fill(0);}
}
