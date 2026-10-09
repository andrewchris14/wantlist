import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
const origin='http://127.0.0.1:9877';
const run=(code,input)=>execFileSync('python',['-c',code],{input:JSON.stringify(input),maxBuffer:20*1024*1024});
const setup="import sys,json,base64;sys.path.insert(0,'foundation/tests');from test_owner_windows_backup import FakeCloudflare,core;d=json.load(sys.stdin);c=FakeCloudflare();\ntry:\n raw,report=core.backup(c,d['approvals']);print(json.dumps({'plaintext_b64':base64.b64encode(raw).decode(),'report':report}))\nexcept core.Stop as e:print(json.dumps({'error':str(e)}))\nfinally:c.db.close()";
async function mount(page){
 const calls={backup:0,restore:0,unexpected:[],downloads:[]};
 page.on('download',d=>calls.downloads.push(d.suggestedFilename()));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==origin){calls.unexpected.push(url.href);return route.abort();}
  const files={'/':'backup.html','/backup.js':'backup.js','/crypto.js':'crypto.js'};
  if(files[url.pathname])return route.fulfill({contentType:url.pathname==='/'?'text/html':'text/javascript',headers:{'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'"},body:readFileSync(resolve('tools/windows-backup',files[url.pathname]))});
  if(url.pathname==='/backup'){
   calls.backup++;const result=run(setup,request.postDataJSON());const parsed=JSON.parse(result);return route.fulfill({status:parsed.error?409:200,contentType:'application/json',body:result});
  }
  if(url.pathname==='/restore'){
   calls.restore++;const result=run("import sys,json,base64;sys.path.insert(0,'tools/windows-backup');from core import restore_verify;d=json.load(sys.stdin);print(json.dumps({'report':restore_verify(json.loads(base64.b64decode(d['plaintext_b64'])))}))",request.postDataJSON());
   return route.fulfill({contentType:'application/json',body:result});
  }
  if(url.pathname==='/close')return route.fulfill({contentType:'application/json',body:'{}'});
  calls.unexpected.push(url.href);return route.abort();
 });
 await page.goto(origin+'/#synthetic-local-capability');
 await expect(page.getByRole('status')).toContainText('Ready.');
 return calls;
}
async function keys(page){return page.evaluate(async()=>{
 const {b64}=await import('/crypto.js'),encoder=new TextEncoder();
 const pair=await crypto.subtle.generateKey({name:'RSA-OAEP',modulusLength:3072,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['encrypt','decrypt']);
 const pub=await crypto.subtle.exportKey('jwk',pair.publicKey),raw=new Uint8Array(await crypto.subtle.exportKey('pkcs8',pair.privateKey));
 const password='synthetic-test-password-123456',salt=crypto.getRandomValues(new Uint8Array(16)),nonce=crypto.getRandomValues(new Uint8Array(12));
 const base=await crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveKey']);
 const key=await crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt,iterations:600000},base,{name:'AES-GCM',length:256},false,['encrypt']);
 const saved={format:'wantlist-recovery-key-v1',iterations:600000,salt:b64(salt),nonce:b64(nonce),ciphertext:b64(await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce},key,raw))};raw.fill(0);return {pub,saved,password};
});}
const file=(name,value)=>({name,mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
async function prepare(page,key){
 await page.locator('#public-key').setInputFiles(file('synthetic-public.json',key.pub));
 await page.locator('#account').fill('a'.repeat(32));await page.locator('#token').fill('synthetic-token');
 await page.locator('#reads').fill('100');await page.locator('#writes').fill('10');
 for(const id of ['approved','free','quiet','encrypted-pc'])await page.locator('#'+id).check();
}
test('default notice blocks; encrypted saved copy recovers offline with exact int64, blob, schema and no plaintext download',async({page})=>{
 const calls=await mount(page),key=await keys(page);expect(calls.backup).toBe(0);expect(calls.restore).toBe(0);
 await prepare(page,key);await page.getByRole('button',{name:'Create backup:'}).click();await expect(page.getByRole('status')).toContainText('D1-limit notice');
 await page.locator('#notice').uncheck();await page.locator('#token').fill('synthetic-token');
 await page.getByRole('button',{name:'Create backup:'}).click();await expect(page.getByRole('status')).toContainText('Encrypted backup ready');
 await expect(page.locator('#token')).toHaveValue('');
 const savedEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Save encrypted backup',exact:true}).click();const download=await savedEvent;
 const bytes=readFileSync(await download.path()),envelope=JSON.parse(bytes);
 // Independent Python decryption establishes compatibility with the existing
 // RSA-OAEP/AES-GCM envelope, not merely browser encrypt/decrypt self-consistency.
 const checked=run("import sys,json,base64,hashlib;from cryptography.hazmat.primitives.ciphers.aead import AESGCM;from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC;from cryptography.hazmat.primitives import hashes,serialization;from cryptography.hazmat.primitives.asymmetric import padding;d=json.load(sys.stdin);s=d['saved'];b=d['backup'];u=base64.b64decode;k=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=u(s['salt']),iterations=600000).derive(d['password'].encode());p=serialization.load_der_private_key(AESGCM(k).decrypt(u(s['nonce']),u(s['ciphertext']),None),None);a=p.decrypt(u(b['wrapped_key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None));raw=AESGCM(a).decrypt(u(b['nonce']),u(b['ciphertext']),u(b['aad']));assert hashlib.sha256(raw).hexdigest()==b['metadata']['plaintext_sha256'];snapshot=json.loads(raw);assert snapshot['tables']['owner_extra'][0]['values']['wide']==['integer',9223372036854775807];print('existing-envelope-compatible')",{saved:key.saved,password:key.password,backup:envelope});
 expect(checked.toString().trim()).toBe('existing-envelope-compatible');
 const expected=await page.evaluate(async value=>{const {sha256}=await import('/crypto.js');return sha256(new TextEncoder().encode(value));},bytes.toString());
 await page.locator('#backup-file').setInputFiles({name:download.suggestedFilename(),mimeType:'application/json',buffer:bytes});
 await page.locator('#private-key').setInputFiles(file('synthetic-recovery.ENCRYPTED.json',key.saved));
 await page.locator('#expected').fill('0'.repeat(64));await page.locator('#password').fill(key.password);
 await page.getByRole('button',{name:'Check saved copy'}).click();await expect(page.getByRole('status')).toContainText('checksum mismatch');expect(calls.restore).toBe(0);
 await page.locator('#expected').fill(expected);await page.locator('#private-key').setInputFiles(file('synthetic-recovery.ENCRYPTED.json',key.saved));await page.locator('#password').fill('wrong-password');
 await page.getByRole('button',{name:'Check saved copy'}).click();await expect(page.locator('#password')).toHaveValue('');await expect(page.getByRole('status')).toContainText('Recovery failed');expect(calls.restore).toBe(0);
 await page.locator('#private-key').setInputFiles(file('synthetic-recovery.ENCRYPTED.json',key.saved));await page.locator('#password').fill(key.password);
 await page.getByRole('button',{name:'Check saved copy'}).click();await expect(page.getByRole('status')).toContainText('Recovery succeeded');
 expect(calls.restore).toBe(1);expect(calls.backup).toBe(2);expect(calls.unexpected).toEqual([]);expect(calls.downloads).toEqual([download.suggestedFilename()]);
 await expect(page.locator('#password')).toHaveValue('');await expect(page.locator('#private-key')).toHaveValue('');
 await page.getByRole('button',{name:'Close and clear'}).click();await expect(page.locator('body')).toContainText('Local tool closed');
});
test('private key rejected before export; unavailable headroom creates no download',async({page})=>{
 const calls=await mount(page),key=await keys(page);await prepare(page,key);await page.locator('#notice').uncheck();
 await page.locator('#public-key').setInputFiles(file('not-public.json',{...key.pub,d:'private-field-rejected'}));
 await page.getByRole('button',{name:'Create backup:'}).click();await expect(page.getByRole('status')).toContainText('PUBLIC encryption key');expect(calls.backup).toBe(0);
 await page.locator('#public-key').setInputFiles(file('synthetic-public.json',key.pub));await page.locator('#token').fill('synthetic-token');await page.locator('#reads').fill('5000000');
 await page.getByRole('button',{name:'Create backup:'}).click();await expect(page.getByRole('status')).toContainText('Insufficient Free quota');expect(calls.downloads).toEqual([]);expect(calls.unexpected).toEqual([]);
});
