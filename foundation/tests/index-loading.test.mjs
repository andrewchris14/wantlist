import test from 'node:test';import assert from 'node:assert/strict';
import {loadPublicIndex} from '../../owner/index-loader.js';import {request,publicRecords} from '../../owner/api.js';
import {indexRecords,pageAfter,categoryCounts,view} from './full-index-fixture.mjs';
import {prepareRecords,queryMatches} from '../../site/model.js';
import worker from '../staging/worker.mjs';

test('approved full public manifest: 3394 records, seven pages, every category and representative search/filter',async()=>{
 let calls=0;const records=await loadPublicIndex(async path=>{calls++;return pageAfter(new URL(path,'https://local.invalid').searchParams.get('after'));});
 assert.equal(calls,7);assert.equal(records.length,3394);assert.deepEqual(records,indexRecords);
 for(const [category,count] of Object.entries(categoryCounts))assert.equal(records.filter(r=>r.display_category===category).length,count);
 const prepared=prepareRecords(records);
 for(const category of Object.keys(categoryCounts)){
  const r=prepared.find(r=>r.display_category===category&&r.set_name);assert.ok(queryMatches(r,r.set_name));
 }
 for(const status of ['want_list','have_list','complete'])assert.ok(prepared.some(r=>r.list_type===status));
 assert.ok(prepared.some(r=>r.brand==='Topps'&&queryMatches(r,'Topps')));assert.ok(prepared.some(r=>r._years));
 assert.equal(view.records.length,3394);
});
test('real Worker route forwards complete in-memory manifest; later valid cursors have no 404 branch',async()=>{
 let calls=0;const db={prepare(sql){assert.match(sql,/FROM public_browse_index/);return {bind(after){return {async first(){calls++;const p=pageAfter(after);return {records:JSON.stringify(p.records),next:p.next};}};}};}};
 const records=await loadPublicIndex(async path=>{const r=await worker.fetch(new Request('https://local.invalid'+path),{STAGING_ONLY:'true',STAGING_EDITOR:'true',DB:db});assert.equal(r.status,200);return r.json();});
 assert.equal(records.length,3394);assert.equal(calls,7);
 const r=await worker.fetch(new Request('https://local.invalid/public/index?after='+indexRecords.at(-1).id),{STAGING_ONLY:'true',STAGING_EDITOR:'true',DB:db});assert.equal(r.status,200);assert.deepEqual(await r.json(),{records:[],next:null});
});
test('404 on third page fails atomically, preserves safe response evidence, and does not retry',async()=>{
 const original=globalThis.fetch;let calls=0;
 try{globalThis.fetch=async path=>{calls++;return calls===3?new Response('Upstream response',{status:404,headers:{'CF-Ray':'synthetic-ray','Server':'cloudflare','Content-Type':'text/html','Set-Cookie':'must-not-collect'}}):Response.json(pageAfter(new URL(path,'https://local.invalid').searchParams.get('after')));};
 await assert.rejects(publicRecords(),error=>{assert.equal(error.status,404);assert.equal(error.indexPage.number,3);assert.ok(error.indexPage.after);assert.deepEqual(error.diagnostic,{route:'/public/index',status:404,cf_ray:'synthetic-ray',server:'cloudflare',content_type:'text/html'});assert.ok(!JSON.stringify(error).includes('must-not-collect'));return true;});assert.equal(calls,3);
 }finally{globalThis.fetch=original;}
});
test('invalid cursor cycles, overlapping IDs, oversized pages and malformed schemas stop without more reads',async()=>{
 for(const page of [{records:[],next:'loop'},{records:[{id:'a'}],next:'b'},{records:[{id:'a'},{id:'a'}],next:null},{records:[],next:false},{records:Array.from({length:501},(_,n)=>({id:String(n)})),next:null},{records:null,next:null}]){
  let calls=0;await assert.rejects(loadPublicIndex(async()=>{calls++;return page;}),{code:'INVALID_INDEX_PAGE'});assert.equal(calls,1);
 }
 let calls=0;await assert.rejects(loadPublicIndex(async()=>{calls++;return {records:[{id:'a'}],next:'a'};}),{code:'INVALID_INDEX_PAGE'});assert.equal(calls,2);
});
test('index SQL failure is 503, not 404, and does not disclose its exception',async()=>{
 const r=await worker.fetch(new Request('https://local.invalid/public/index?after=any'),{STAGING_ONLY:'true',STAGING_EDITOR:'true',DB:{prepare(){throw Error('private fake SQL details');}}});assert.equal(r.status,503);assert.ok(!(await r.text()).includes('private fake'));
});
