import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {timingSafeEqual} from 'node:crypto';
import {localD1} from './d1-local-adapter.mjs';
import {mutate,openRecord} from '../staging/records.js';
import {ownerRecord,recentOwner} from '../staging/owner.js';
import worker from '../staging/worker.mjs';
import * as auth from '../staging/auth.js';
Object.defineProperty(crypto.subtle,'timingSafeEqual',{value:(a,b)=>timingSafeEqual(Buffer.from(a),Buffer.from(b)),configurable:true});
async function fixture(){const db=localD1();db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',0,1)");const code='disposable-'+crypto.randomUUID();const env={DB:db,STAGING_ONLY:'true',STAGING_EDITOR:'true',PROBE_KEY:'operator-'+crypto.randomUUID(),OWNER_AUTH_CONFIG:JSON.stringify({algorithm:'SHA-256',digest:await auth.hash(code),version:'staging-test-version-0001'})};return {db,env,code};}
const action=(db,input)=>mutate(db,{request_id:crypto.randomUUID(),...input});
test('owner preview rejects public writes, private reads, diagnostics and cross-origin login without exposing gate',async()=>{
 const {db,env,code}=await fixture();try{
 const req=(path,body,headers={})=>new Request('https://staging.example'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json',Origin:'https://staging.example'}:{}),...headers},...(body?{body:JSON.stringify(body)}:{})});
 for(const path of ['/action','/owner/record','/owner/recent'])assert.equal((await worker.fetch(req(path,path==='/action'?{op:'create'}:null),env)).status,401);
 assert.equal((await worker.fetch(req('/test/batch',{statements:[]}),env)).status,403);
 assert.equal((await worker.fetch(req('/login',{credential:code,remembered:true},{Origin:'https://evil.example'}),env)).status,403);
 const login=await worker.fetch(req('/login',{credential:code,remembered:true}),env);assert.equal(login.status,200);assert.match(login.headers.get('Set-Cookie'),/Secure; HttpOnly; SameSite=Strict; Max-Age=7776000/);
 const cookie=login.headers.get('Set-Cookie').split(';')[0];
 assert.equal((await worker.fetch(req('/owner/recent',null,{Cookie:cookie}),env)).status,200);
 await worker.fetch(req('/logout',{}, {Cookie:cookie}),env);
 assert.equal((await worker.fetch(req('/owner/recent',null,{Cookie:cookie}),env)).status,401);
 }finally{db.close();}
});
test('targeted Undo replays safely and rejects a newer change without modifying it',async()=>{
 const {db}=await fixture();try{
 const r=await action(db,{op:'create',metadata:{set_name:'2027 Topps',notes:['Original']},wanted:['47','92']});
 let record=await openRecord(db,r.record_id),item=record.groups[0].entries[0];
 let saved=await action(db,{op:'transition',record_id:r.record_id,revision:1,item_id:item.id,state:'pending'});
 const h=(await recentOwner(db)).changes[0];assert.equal(h.undoable,true);
 const undo={op:'undo',history_id:h.id,record_id:r.record_id,revision:saved.revision,request_id:crypto.randomUUID()};
 saved=await mutate(db,undo);assert.equal((await mutate(db,undo)).replayed,true);assert.equal((await ownerRecord(db,r.record_id)).groups[0].entries[0].state,'wanted');
 await action(db,{op:'edit',record_id:r.record_id,revision:saved.revision,metadata:{notes:['Newer']}});
 await assert.rejects(action(db,{op:'undo',history_id:h.id,record_id:r.record_id,revision:saved.revision+1}),e=>e.code==='CONFLICT');
 assert.deepEqual((await ownerRecord(db,r.record_id)).content.notes,['Newer']);
 }finally{db.close();}
});
test('Received Undo preserves earlier Pending state; removals restore and multi-add Undo is honest',async()=>{
 const {db}=await fixture();try{
 const r=await action(db,{op:'create',metadata:{set_name:'test'},wanted:['47'],owned:['R1']});let rev=1;
 let item=(await openRecord(db,r.record_id)).groups[0].entries[0];
 for(const state of ['pending','owned']){rev=(await action(db,{op:'transition',record_id:r.record_id,revision:rev,item_id:item.id,state})).revision;}
 let h=(await recentOwner(db)).changes[0];rev=(await action(db,{op:'undo',history_id:h.id,record_id:r.record_id,revision:rev})).revision;
 assert.equal((await ownerRecord(db,r.record_id)).groups[0].entries[0].state,'pending');
 rev=(await action(db,{op:'remove_item',record_id:r.record_id,revision:rev,item_id:item.id})).revision;h=(await recentOwner(db)).changes[0];
 rev=(await action(db,{op:'undo',history_id:h.id,record_id:r.record_id,revision:rev})).revision;assert.equal((await ownerRecord(db,r.record_id)).groups[0].entries[0].deleted_at,null);
 await action(db,{op:'add',record_id:r.record_id,revision:rev,values:['12','18']});h=(await recentOwner(db)).changes[0];assert.equal(h.undoable,false);assert.match(h.undo_reason,/individually/);
 assert.equal(db.sqlite.prepare('SELECT count(*) n FROM provenance WHERE record_id=?').get(r.record_id).n,0);
 }finally{db.close();}
});
test('owner reads omit historical blobs/private data and HAVE cards remain owned',async()=>{
 const {db}=await fixture();try{
 const r=await action(db,{op:'create',metadata:{set_name:'Owned'},list_type:'have_list',owned:['KCR2']});
 db.sqlite.prepare("UPDATE records SET content_json=json_set(content_json,'$.source_wording','historical-secret-sentinel','$.private_trade','private-sentinel') WHERE id=?").run(r.record_id);
 const view=await ownerRecord(db,r.record_id);assert.equal(view.groups[0].entries[0].state,'owned');assert.equal(JSON.stringify(view).includes('sentinel'),false);
 assert.equal(JSON.stringify(await recentOwner(db)).includes('sentinel'),false);
 }finally{db.close();}
});

test('ordinary Owned to Pending remains invalid; old unversioned history cannot be undone',async()=>{
 const {db}=await fixture();try{
 const created=await action(db,{op:'create',metadata:{set_name:'transition rules'},wanted:['47']});const r=await ownerRecord(db,created.record_id),item=r.groups[0].entries[0];
 const saved=await action(db,{op:'transition',record_id:r.id,revision:1,item_id:item.id,state:'owned'});
 await assert.rejects(action(db,{op:'transition',record_id:r.id,revision:saved.revision,item_id:item.id,state:'pending'}),e=>e.code==='INVALID');
 const h=(await recentOwner(db)).changes[0];db.sqlite.prepare("UPDATE change_history SET after_json=json_remove(after_json,'$._record_revision') WHERE id=?").run(h.id);
 assert.equal((await recentOwner(db)).changes[0].undoable,false);
 await assert.rejects(action(db,{op:'undo',record_id:r.id,revision:saved.revision,history_id:h.id}),e=>e.code==='CONFLICT');
 assert.equal((await ownerRecord(db,r.id)).groups[0].entries[0].state,'owned');
 }finally{db.close();}
});

test('Complete cannot restore opaque historical wanted wording; source stays recoverable',async()=>{
 const {db}=await fixture();try{
 const created=await action(db,{op:'create',metadata:{set_name:'Opaque wanted fixture'},wanted:['10–12 source range']});let r=await openRecord(db,created.record_id),item=r.groups[0].entries[0];
 // Disposable stand-in for a literal historical range, never alter baseline data.
 db.sqlite.prepare("UPDATE items SET actionable=0,state=NULL,limitation='Preserved range' WHERE id=?").run(item.id);
 r=await openRecord(db,r.id);const {publicProjection}=await import('../staging/records.js');db.sqlite.prepare('UPDATE public_records SET public_json=? WHERE record_id=?').run(JSON.stringify(publicProjection(r)),r.id);
 let saved=await action(db,{op:'remove_item',record_id:r.id,revision:1,item_id:item.id});saved=await action(db,{op:'edit',record_id:r.id,revision:saved.revision,metadata:{},list_type:'complete'});
 await assert.rejects(action(db,{op:'restore_item',record_id:r.id,revision:saved.revision,item_id:item.id}),e=>e.code==='INVALID');
 assert.ok((await ownerRecord(db,r.id)).groups[0].entries[0].deleted_at);
 saved=await action(db,{op:'edit',record_id:r.id,revision:saved.revision,metadata:{},list_type:'want_list'});await action(db,{op:'restore_item',record_id:r.id,revision:saved.revision,item_id:item.id});
 assert.equal((await ownerRecord(db,r.id)).groups[0].entries[0].value,'10–12 source range');
 }finally{db.close();}
});

test('same-millisecond history uses saved revision, not random IDs, for Undo safety',async()=>{
 const {db}=await fixture(),RealDate=Date;
 globalThis.Date=class extends RealDate{constructor(...args){super(...(args.length?args:['2026-10-07T12:00:00.000Z']));}static now(){return new RealDate('2026-10-07T12:00:00.000Z').getTime();}};
 try{
 const created=await action(db,{op:'create',metadata:{set_name:'Same timestamp fixture'},wanted:['47']});const r=await ownerRecord(db,created.record_id),item=r.groups[0].entries[0];
 await action(db,{op:'transition',record_id:r.id,revision:1,item_id:item.id,state:'pending'});const saved=await action(db,{op:'transition',record_id:r.id,revision:2,item_id:item.id,state:'owned'});
 const changes=(await recentOwner(db)).changes;assert.equal(changes[0].after.state,'owned');assert.equal(changes[0].undoable,true);assert.equal(changes[1].undoable,false);
 await action(db,{op:'undo',record_id:r.id,revision:saved.revision,history_id:changes[0].id});assert.equal((await ownerRecord(db,r.id)).groups[0].entries[0].state,'pending');
 }finally{globalThis.Date=RealDate;db.close();}
});

test('diagnostic republishing a removed set preserves restore inventory without public leakage',async()=>{
 const {db,env}=await fixture();try{
 const created=await action(db,{op:'create',metadata:{set_name:'Recovery fixture'},wanted:['47'],owned:['92']});const removed=await action(db,{op:'delete',record_id:created.record_id,revision:1});
 const req=(path,body)=>new Request('https://staging.example'+path,{method:body?'POST':'GET',headers:{'X-Staging-Probe':env.PROBE_KEY,...(body?{Origin:'https://staging.example','Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 assert.equal((await worker.fetch(req('/test/publish',{record_id:created.record_id}),env)).status,200);
 const hidden=await worker.fetch(req('/public/record?id='+created.record_id),env);assert.deepEqual((await hidden.json()).groups,[]);
 await action(db,{op:'restore',record_id:created.record_id,revision:removed.revision});
 const restored=await worker.fetch(req('/public/record?id='+created.record_id),env);assert.deepEqual((await restored.json()).groups.flatMap(g=>g.entries).map(i=>i.value),['47','92']);
 }finally{db.close();}
});
