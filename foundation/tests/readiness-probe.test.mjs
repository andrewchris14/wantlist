import test from 'node:test';
import assert from 'node:assert/strict';
import {timingSafeEqual} from 'node:crypto';
import probe from '../staging/readiness-probe.mjs';
Object.defineProperty(crypto.subtle,'timingSafeEqual',{value:(a,b)=>timingSafeEqual(Buffer.from(a),Buffer.from(b)),configurable:true});
const origin='https://wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev';
const nonce='a'.repeat(32),key=crypto.randomUUID()+crypto.randomUUID();
function env(){return {MINIMAL_FREE_REVIEW:'true',MINIMAL_FREE_REVIEW_UNTIL:new Date(Date.now()+9*60*1000).toISOString(),STAGING_ONLY:'true',STAGING_EDITOR:'true',ISOLATED_TEST_STORAGE:'true',FREE_HTTP_REVIEW_KEY:key,READINESS_PROBE_NONCE:nonce,get DB(){throw Error('Probe must never access DB');},get OWNER_PIN(){throw Error('Probe must never access credentials');}};}
const request=(path='/public/index?after=',headers={})=>new Request(origin+path,{headers});
test('authorized exact URL yields correlated marker without DB or subrequests',async()=>{
 const fetchBefore=globalThis.fetch;globalThis.fetch=()=>{throw Error('No outbound fetch');};
 try{const r=await probe.fetch(request(undefined,{'X-Free-Review-Key':key}),env());assert.equal(r.status,200);assert.equal(r.headers.get('X-Wantlist-Readiness-Nonce'),nonce);assert.equal(r.headers.get('Cache-Control'),'no-store');assert.deepEqual(await r.json(),{probe:'wantlist-readiness-no-d1-v1',nonce,authorized:true});}finally{globalThis.fetch=fetchBefore;}
});
test('browser without private header can identify the handler, with no privileged response',async()=>{
 const r=await probe.fetch(request(),env());assert.equal(r.status,403);const b=await r.json();assert.equal(b.nonce,nonce);assert.equal(b.authorized,false);assert.ok(!JSON.stringify(b).includes(key));
});
test('expired/missing/long lease or incorrect isolation denies before marker or DB',async()=>{
 for(const patch of [{MINIMAL_FREE_REVIEW:'false'},{ISOLATED_TEST_STORAGE:'false'},{STAGING_EDITOR:'false'},{STAGING_ONLY:'false'},{FREE_HTTP_REVIEW_KEY:undefined},{READINESS_PROBE_NONCE:'bad'},{MINIMAL_FREE_REVIEW_UNTIL:new Date(0).toISOString()},{MINIMAL_FREE_REVIEW_UNTIL:new Date(Date.now()+11*60*1000).toISOString()}]){
  const e=env();Object.assign(e,patch);const r=await probe.fetch(request(),e);assert.equal(r.status,403);assert.equal(r.headers.get('X-Wantlist-Readiness'),null);
 }
});
test('wrong path/query/method/host never invokes the application or DB',async()=>{
 for(const r of [request('/'),request('/owner/record?id=synthetic-3c5-1-0000'),request('/public/index?after=x'),request('/public/index?after=&extra=1'),new Request(origin+'/public/index?after=',{method:'POST'}),new Request('https://wantlist-staging.andrewchris14.workers.dev/public/index?after=')]){const reply=await probe.fetch(r,env());assert.equal(reply.status,403);assert.equal(reply.headers.get('X-Wantlist-Readiness'),null);}
});
