import test from 'node:test';
import assert from 'node:assert/strict';
import {timingSafeEqual} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {localD1} from './d1-local-adapter.mjs';
import * as auth from '../staging/auth.js';
import {mutate,openRecord,publicProjection} from '../staging/records.js';
import worker from '../staging/worker.mjs';
Object.defineProperty(crypto.subtle,'timingSafeEqual',{value:(a,b)=>timingSafeEqual(Buffer.from(a),Buffer.from(b)),configurable:true});
const code='disposable-generated-owner-code-'+crypto.randomUUID();
async function fixture(){
  const db=localD1();db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));
  db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',0,1)");
  const env={DB:db,STAGING_ONLY:'true',PROBE_KEY:'operator-only-disposable-'+crypto.randomUUID(),OWNER_AUTH_CONFIG:JSON.stringify({algorithm:'SHA-256',digest:await auth.hash(code),version:'disposable-version-0001'})};
  return {db,env};
}
const action=(db,input)=>mutate(db,{request_id:crypto.randomUUID(),...input});
test('secret verifier uses generated credential, no expiry or account/password table',async()=>{
 const {db,env}=await fixture();try{
  assert.equal(await auth.verifyCredential(code,env),true);assert.equal(await auth.verifyCredential(code+'wrong',env),false);
  assert.equal(await auth.verifyCredential('1234',env),false);
  assert.equal(db.sqlite.prepare("SELECT count(*) n FROM sqlite_master WHERE name='owners'").get().n,0);
  assert.deepEqual(Object.keys(auth.config(env)).sort(),['algorithm','digest','version']);
 }finally{db.close();}
});
test('real data-layer 2027 lifecycle preserves owner origin, states, undo and history',async()=>{
 const {db}=await fixture();try{
  let saved=await action(db,{op:'create',metadata:{year:'2027',brand:'Topps',set_name:'2027 Topps',category:'baseball_cards'},wanted:['1','2','3'],owned:['4','5']});const id=saved.record_id;
  const apply=async input=>{saved=await action(db,{record_id:id,revision:saved.revision,...input});};
  let r=await openRecord(db,id);assert.equal(r.import_id,null);assert.equal(r.content.creation_origin,'owner');assert.equal(r.content.source_refs,undefined);
  await apply({op:'add',values:['6','7']});r=await openRecord(db,id);const items=r.groups.flatMap(g=>g.entries);
  await apply({op:'transition',item_id:items.find(i=>i.value==='1').id,state:'pending'});
  await apply({op:'transition',item_id:items.find(i=>i.value==='2').id,state:'owned'});
  await apply({op:'transition',item_id:items.find(i=>i.value==='1').id,state:'wanted'});
  await apply({op:'edit',metadata:{notes:['Corrected notes']},list_type:'uncertain'});
  await assert.rejects(apply({op:'edit',list_type:'complete',metadata:{}}));
  await apply({op:'edit',list_type:'want_list',metadata:{}});
  await apply({op:'remove_item',item_id:items.find(i=>i.value==='7').id});
  await apply({op:'restore_item',item_id:items.find(i=>i.value==='7').id});
  await apply({op:'delete'});assert.ok((await openRecord(db,id)).deleted_at);
  await apply({op:'restore'});r=await openRecord(db,id);assert.equal(r.deleted_at,null);
  assert.equal(db.sqlite.prepare('SELECT count(*) n FROM provenance WHERE record_id=?').get(id).n,0);
  assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history WHERE record_id=?').get(id).n,11);
  const projection=JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(id).public_json);
  assert.equal(projection.revision,r.revision);assert.deepEqual(projection,publicProjection(r));
 }finally{db.close();}
});
test('duplicate retry is idempotent, stale revision and invalid transition leave no partial writes',async()=>{
 const {db}=await fixture();try{
  const input={request_id:crypto.randomUUID(),op:'create',metadata:{set_name:'test'},wanted:['1']};const created=await mutate(db,input);
  assert.equal((await mutate(db,input)).replayed,true);
  await assert.rejects(mutate(db,{...input,metadata:{set_name:'different'}}));
  const r=await openRecord(db,created.record_id),item=r.groups[0].entries[0];
  await assert.rejects(action(db,{op:'transition',record_id:r.id,revision:99,item_id:item.id,state:'pending'}));
  await assert.rejects(action(db,{op:'transition',record_id:r.id,revision:1,item_id:item.id,state:'wanted'}));
  assert.equal((await openRecord(db,r.id)).revision,1);
 }finally{db.close();}
});
test('transactional revision guard rejects an intervening write without changing items/history/projection',async()=>{
 const {db}=await fixture();try{
  const saved=await action(db,{op:'create',metadata:{set_name:'race'},wanted:['1']});const r=await openRecord(db,saved.record_id);
  const original=db.batch.bind(db);let once=true;db.batch=async statements=>{if(once){once=false;db.sqlite.prepare('UPDATE records SET revision=2 WHERE id=?').run(r.id);}return original(statements);};
  await assert.rejects(action(db,{op:'transition',record_id:r.id,revision:1,item_id:r.groups[0].entries[0].id,state:'pending'}));
  assert.equal((await openRecord(db,r.id)).groups[0].entries[0].state,'wanted');
  assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n,1);
  assert.equal(db.sqlite.prepare('SELECT revision FROM public_records').get().revision,1);
 }finally{db.close();}
});
test('remembered/short sessions expire, rotation and generation revoke, credential itself has no clock',async()=>{
 const {db,env}=await fixture();try{
  const long=await auth.issue(db,env,true),short=await auth.issue(db,env,false);
  assert.ok(long.cookie.includes('Max-Age=7776000'));assert.ok(!short.cookie.includes('Max-Age'));
  assert.ok(await auth.validate(db,env,long.token));assert.equal(long.expires-short.expires,auth.REMEMBERED-auth.SHORT);
  const rotated={...env,OWNER_AUTH_CONFIG:JSON.stringify({...auth.config(env),version:'disposable-version-0002'})};assert.equal(await auth.validate(db,rotated,long.token),null);
  db.sqlite.exec('UPDATE auth_control SET generation=generation+1');assert.equal(await auth.validate(db,env,long.token),null);
  assert.equal(await auth.verifyCredential(code,env),true);
  const expired=await auth.issue(db,env,true);db.sqlite.prepare('UPDATE sessions SET expires_at=created_at-1,created_at=created_at-100 WHERE token_hash=?').run(await auth.hash(expired.token));
  assert.equal(await auth.validate(db,env,expired.token),null);
 }finally{db.close();}
});
test('throttling blocks before expensive work and resets its time window',async()=>{
 const {db}=await fixture();try{
  for(let i=0;i<5;i++)assert.equal(await auth.throttle(db,'same-ip'),true);
  assert.equal(await auth.throttle(db,'same-ip'),false);
  db.sqlite.exec('UPDATE login_limits SET window_start=0');assert.equal(await auth.throttle(db,'same-ip'),true);
 }finally{db.close();}
});
test('staging endpoint fails closed without gate, owner session, correct origin, or database',async()=>{
 const {db,env}=await fixture();try{
  const make=(path,body,extra={})=>new Request('https://staging.example'+path,{method:body?'POST':'GET',headers:{'X-Staging-Probe':env.PROBE_KEY,'Origin':'https://staging.example','Content-Type':'application/json',...extra},...(body?{body:JSON.stringify(body)}:{})});
  assert.equal((await worker.fetch(make('/action',{op:'edit'}),env)).status,401);
  assert.equal((await worker.fetch(make('/login',{credential:code,remembered:true},{Origin:'https://evil.example'}),env)).status,403);
  assert.equal((await worker.fetch(new Request('https://staging.example/health'),env)).status,403);
  const broken={...env,DB:{prepare(){throw Error('private DB message');}}};
  const response=await worker.fetch(make('/login',{credential:code,remembered:true}),broken);
  assert.equal(response.status,503);assert.ok(!(await response.text()).includes('private DB message'));
 }finally{db.close();}
});
test('large-set state changes use targeted item and JSON-path queries, not a full item-list fetch',async()=>{
 const {db}=await fixture();try{
  let saved=await action(db,{op:'create',metadata:{set_name:'large test'},wanted:Array.from({length:20},(_,i)=>String(i))});
  for(let batch=1;batch<10;batch++)saved=await action(db,{op:'add',record_id:saved.record_id,revision:saved.revision,values:Array.from({length:20},(_,i)=>String(batch*20+i))});
  const r=await openRecord(db,saved.record_id),item=r.groups.flatMap(g=>g.entries).at(-1),queries=[];
  const prepare=db.prepare.bind(db);db.prepare=sql=>{queries.push(sql);return prepare(sql);};
  await action(db,{op:'transition',record_id:r.id,revision:r.revision,item_id:item.id,state:'pending'});
  assert.ok(queries.some(sql=>sql.includes('WHERE i.id=?')));
  assert.ok(queries.some(sql=>sql.includes('json_each')));
  assert.ok(!queries.some(sql=>sql.includes('WHERE g.record_id=? ORDER BY')));
  const now=await openRecord(db,r.id);assert.deepEqual(JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(r.id).public_json),publicProjection(now));
 }finally{db.close();}
});
test('delta additions/removal/restore preserve numbered and named ordering without loading inventories',async()=>{
 const {db}=await fixture();try{
  let saved=await action(db,{op:'create',metadata:{set_name:'Mixed literals',notes:['Historical note']},wanted:['1','2'],wanted_names:['Blue Border Griffey'],owned_names:['Red Border Griffey']});
  const apply=async input=>saved=await action(db,{record_id:saved.record_id,revision:saved.revision,...input});
  await apply({op:'add',values:['3','4']});await apply({op:'add',values:['Signed postcard'],field_key:'items'});
  const initial=await openRecord(db,saved.record_id),queries=[],prepare=db.prepare.bind(db);db.prepare=sql=>{queries.push(sql);return prepare(sql);};
  const wanted=initial.groups.find(g=>g.list_type==='want_list').entries;
  await apply({op:'remove_item',item_id:wanted[0].id});await apply({op:'remove_item',item_id:wanted[2].id});
  await apply({op:'restore_item',item_id:wanted[0].id});await apply({op:'restore_item',item_id:wanted[2].id});
  await apply({op:'edit',metadata:{notes:['Changed note'],year:'2027'}});
  assert.ok(!queries.some(sql=>sql.includes('WHERE g.record_id=? ORDER BY')));
  assert.ok(!queries.some(sql=>sql.includes('SELECT * FROM records')));
  const after=await openRecord(db,saved.record_id),projection=JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(after.id).public_json);
  assert.deepEqual(projection,publicProjection(after));assert.equal(after.groups.flatMap(g=>g.entries).length,initial.groups.flatMap(g=>g.entries).length);
 }finally{db.close();}
});
test('delta additions reject duplicates and CAS races without partial publication/history',async()=>{
 const {db}=await fixture();try{
  const saved=await action(db,{op:'create',metadata:{set_name:'Add guard'},wanted:['1']});
  await assert.rejects(action(db,{op:'add',record_id:saved.record_id,revision:1,values:['1']}));
  await assert.rejects(action(db,{op:'add',record_id:saved.record_id,revision:1,values:['2',' 2 ']}));
  const original=db.batch.bind(db);db.batch=async statements=>{db.sqlite.prepare('UPDATE records SET revision=2 WHERE id=?').run(saved.record_id);return original(statements);};
  await assert.rejects(action(db,{op:'add',record_id:saved.record_id,revision:1,values:['2']}));
  assert.equal(db.sqlite.prepare('SELECT count(*) n FROM items').get().n,1);
  assert.equal(db.sqlite.prepare('SELECT count(*) n FROM change_history').get().n,1);
  assert.equal(db.sqlite.prepare('SELECT revision FROM public_records').get().revision,1);
 }finally{db.close();}
});
test('batched session/preflight keeps authorization and CSRF checks with diagnostics on/off',async()=>{
 const {db,env}=await fixture();try{
  const make=(body,cookie,metrics='off')=>new Request('https://staging.example/action',{method:'POST',headers:{'X-Staging-Probe':env.PROBE_KEY,'Origin':'https://staging.example','Content-Type':'application/json','Cookie':cookie,'X-Staging-Metrics':metrics},body:JSON.stringify(body)});
  const input={request_id:crypto.randomUUID(),op:'create',metadata:{set_name:'Session-batched'},wanted:['47']};
  assert.equal((await worker.fetch(make(input,''),env)).status,401);
  const session=await auth.issue(db,env,true);let response=await worker.fetch(make(input,auth.COOKIE+'='+session.token),{...env,STAGING_METRICS:'true'});
  assert.equal(response.status,200);assert.equal(response.headers.get('X-Staging-D1-Reads'),null);
  response=await worker.fetch(make(input,auth.COOKIE+'='+session.token,'on'),{...env,STAGING_METRICS:'true'});assert.equal(response.status,200);assert.equal((await response.json()).replayed,true);
  db.sqlite.exec('UPDATE auth_control SET generation=generation+1');
  assert.equal((await worker.fetch(make({...input,request_id:crypto.randomUUID()},auth.COOKIE+'='+session.token),env)).status,401);
 }finally{db.close();}
});
test('new mixed group preserves primary/mixed/sublist order and existing sublist metadata',async()=>{
 const {db}=await fixture();try{
  let saved=await action(db,{op:'create',metadata:{set_name:'Historical grouped shape'},owned:['1']});
  const gid='source-shape-sublist';db.sqlite.prepare('INSERT INTO record_groups VALUES(?,?,\'sublist\',0,\'have_list\',?,?)').run(gid,saved.record_id,JSON.stringify({label:'Special owned sublist',notes:['Meaningful note']}),'[]');
  let r=await openRecord(db,saved.record_id);db.sqlite.prepare('UPDATE public_records SET public_json=? WHERE record_id=?').run(JSON.stringify(publicProjection(r)),r.id);
  saved=await action(db,{op:'add',record_id:r.id,revision:r.revision,values:['47']});r=await openRecord(db,r.id);
  const projection=JSON.parse(db.sqlite.prepare('SELECT public_json FROM public_records WHERE record_id=?').get(r.id).public_json);
  assert.deepEqual(projection,publicProjection(r));assert.deepEqual(projection.groups.map(g=>g.kind),['primary','mixed','sublist']);
  assert.equal(projection.groups[2].label,'Special owned sublist');
 }finally{db.close();}
});
