import test from 'node:test';import assert from 'node:assert/strict';import worker from '../staging/worker.mjs';
const env=DB=>({DB,STAGING_ONLY:'true',STAGING_EDITOR:'true',STAGING_METRICS:'true'});
const request=(metrics='on')=>new Request('https://isolated.invalid/public/index?after=',{headers:{'X-Staging-Metrics':metrics}});
const fake=meta=>({prepare(){return {bind(){return this;},async all(){return {results:[{records:'[]',next:null}],...(meta?{meta}:{})};},async first(){return {records:'[]',next:null};}};}});

test('diagnostics preserve known billed D1 reads and mark them complete',async()=>{
 const r=await worker.fetch(request(),env(fake({rows_read:12,rows_written:0,duration:1.5})));
 assert.equal(r.status,200);assert.equal(r.headers.get('X-Staging-D1-Complete'),'true');assert.equal(r.headers.get('X-Staging-D1-Reads'),'12');assert.equal(r.headers.get('X-Staging-D1-Writes'),'0');assert.equal(r.headers.get('X-Staging-D1-Ms'),'1.5');
});
test('missing or malformed D1 metadata is unknown rather than zero',async()=>{
 for(const meta of [null,{rows_read:12,rows_written:0},{rows_read:-1,rows_written:0,duration:1},{rows_read:12,rows_written:'0',duration:1}]){
 const r=await worker.fetch(request(),env(fake(meta)));assert.equal(r.status,200);assert.equal(r.headers.get('X-Staging-D1-Complete'),'false');assert.equal(r.headers.get('X-Staging-D1-Reads'),'unknown');assert.equal(r.headers.get('X-Staging-D1-Writes'),'unknown');assert.equal(r.headers.get('X-Staging-D1-Ms'),'unknown');
 }
});
test('failed D1 execution never advertises a measured zero cost or exception body',async()=>{
 const DB={prepare(){return {bind(){return this;},async all(){throw Error('private fake failure');}};}};
 const r=await worker.fetch(request(),env(DB));assert.equal(r.status,503);assert.equal(r.headers.get('X-Staging-D1-Complete'),'false');assert.equal(r.headers.get('X-Staging-D1-Reads'),'unknown');assert.ok(!(await r.text()).includes('private fake'));
});
test('raw path retains its response and has no diagnostic metadata processing',async()=>{
 const r=await worker.fetch(request('off'),env(fake(null)));assert.equal(r.status,200);assert.equal(r.headers.get('X-Staging-D1-Complete'),null);assert.deepEqual(await r.json(),{records:[],next:null});
});
