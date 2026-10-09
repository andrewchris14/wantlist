// Synthetic, predecoded D1 replay. Includes JS validation/hash/UUID/SQL binding,
// excludes SQLite, D1 transport/decoding, HTTP and Cloudflare scheduling/CPU.
import {performanceFixture,maximumBody,recordId} from '../foundation/tests/performance-fixture.mjs';
import {writeFileSync} from 'node:fs';import assert from 'node:assert/strict';
const directory=process.argv[2];if(!directory)throw Error('Pass a locally exported approved baseline directory');
const modules=await Promise.all([directory,'.'].map(async root=>({
 owner:await import(new URL('../'+root+'/foundation/staging/owner.js',import.meta.url)),
 records:await import(new URL('../'+root+'/foundation/staging/records.js',import.meta.url))
})));
const observations=[];let expected;
for(const [n,module] of modules.entries()){
 const db=performanceFixture(),cached=new Map();let resultRows=0,maxCellBytes=0;
 const wrap=(sql,args=[])=>({bind(...values){return wrap(sql,values);},async first(){const value=await db.prepare(sql).bind(...args).first();cached.set(sql,{method:'first',value});if(value?.body){resultRows++;maxCellBytes=Math.max(maxCellBytes,Buffer.byteLength(value.body));}return value;},async all(){const value=await db.prepare(sql).bind(...args).all();cached.set(sql,{method:'all',value});resultRows+=value.results.length;for(const row of value.results)if(row.body)maxCellBytes=Math.max(maxCellBytes,Buffer.byteLength(row.body));return value;}});
 const capture={prepare:wrap,batch:async()=>[]};
 const encoded=await module.owner.ownerRecordJSON(capture,recordId),ownerRows=resultRows,ownerMaxCellBytes=maxCellBytes;
 if(n===0)expected=JSON.parse(encoded);else assert.deepEqual(JSON.parse(encoded),expected);
 const body=maximumBody(),notes={op:'edit_session',request_id:crypto.randomUUID(),record_id:recordId,revision:1,metadata:{notes:['Synthetic note']}};
 await module.records.mutate(capture,body);await module.records.mutate(capture,notes);
 const replay={prepare(sql){return {bind(){return this;},first:async()=>{const r=cached.get(sql);assert.equal(r?.method,'first');return r.value?{...r.value}:r.value;},all:async()=>{const r=cached.get(sql);assert.equal(r?.method,'all');return r.value;}};},batch:async()=>[]};
 for(const [operation,fn] of [['owner_open',()=>module.owner.ownerRecordJSON(replay,recordId)],['notes_save',()=>module.records.mutate(replay,notes)],['maximum_save',()=>module.records.mutate(replay,body)]]){
  for(let i=0;i<15;i++)await fn();const samples=[];
  for(let s=0;s<5;s++){const started=process.cpuUsage();for(let i=0;i<100;i++)await fn();const elapsed=process.cpuUsage(started);samples.push((elapsed.user+elapsed.system)/1000/100);}
  observations.push({version:n===0?'approved-6412d76':'followup',operation,iterations_per_sample:100,samples_ms:samples,median_cpu_ms_per_operation:[...samples].sort((a,b)=>a-b)[2],...(operation==='owner_open'?{response_bytes:Buffer.byteLength(encoded),returned_rows:ownerRows,max_body_cell_bytes:ownerMaxCellBytes}:{} )});
 }
 db.close();
}
const report={local_only:true,cloudflare_cpu_or_billed_reads:false,measurement:'Node process CPU, predecoded synthetic D1 replay; no database execution, response decoding, network or HTTP',node_version:process.version,observations};
writeFileSync('work/followup-local-cpu.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
