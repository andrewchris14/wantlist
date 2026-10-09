// Compare only JavaScript owner read-model/serialization CPU with predecoded D1
// responses. Excludes D1 CPU, network and runtime response decoding; not Worker CPU.
import {performanceFixture,recordId} from '../foundation/tests/performance-fixture.mjs';
import {ownerRecordJSON} from '../foundation/staging/owner.js';
import {writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const directory=process.argv[2];if(!directory)throw Error('Pass locally exported baseline directory');
const {ownerRecord}=await import(new URL('../'+directory+'/foundation/staging/owner.js',import.meta.url));
const db=performanceFixture();const cached=new Map();let rows=0;
const wrap=(sql,args=[])=>({bind(...values){return wrap(sql,values);},async first(){const r=await db.prepare(sql).bind(...args).first();const copy={...r};cached.set(sql,()=>({...copy}));rows+=r?1:0;return r;},async all(){const r=await db.prepare(sql).bind(...args).all();cached.set(sql,()=>r);rows+=r.results.length;return r;}});
const expected=JSON.stringify(await ownerRecord({prepare:wrap},recordId)),baselineRows=rows;
const encoded=await ownerRecordJSON(db,recordId);assert.deepEqual(JSON.parse(encoded),JSON.parse(expected));
const replay={prepare(sql){return {bind(){return this;},first:async()=>cached.get(sql)(),all:async()=>cached.get(sql)()};}};
const optimizedReplay={prepare(){return {bind(){return this;},first:async()=>({body:encoded})};}};
const iterations=200;
async function measure(fn){for(let n=0;n<10;n++)await fn();const start=process.cpuUsage();for(let n=0;n<iterations;n++)await fn();const c=process.cpuUsage(start);return (c.user+c.system)/1000/iterations;}
const result={local_only:true,not_cloudflare_cpu:true,iterations,baseline_returned_rows:baselineRows,optimized_returned_rows:1,baseline_js_cpu_ms_per_open:await measure(async()=>JSON.stringify(await ownerRecord(replay,recordId))),optimized_js_cpu_ms_per_open:await measure(()=>ownerRecordJSON(optimizedReplay,recordId))};
writeFileSync('work/owner-transport.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));db.close();
