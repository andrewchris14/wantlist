// Local synthetic SQL capture and Node timings; neither is Cloudflare CPU/D1 billing.
import {performanceFixture,maximumBody,recordId,groupId} from '../foundation/tests/performance-fixture.mjs';
import {writeFileSync,mkdirSync,rmSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
const label=process.argv[2]||'current';mkdirSync('work',{recursive:true});
if(!/^[-a-z0-9]+$/.test(label))throw Error('Invalid measurement label');
rmSync('work/profile-'+label+'.sqlite',{force:true});
rmSync('work/profile-'+label+'-initial.sqlite',{force:true});
const baselineDirectory=process.argv[3]||null;
const moduleRoot=baselineDirectory||'.';
const {mutate}=await import(new URL('../'+moduleRoot+'/foundation/staging/records.js',import.meta.url));
const owner=await import(new URL('../'+moduleRoot+'/foundation/staging/owner.js',import.meta.url));
const db=performanceFixture('work/profile-'+label+'.sqlite',526,1503,baselineDirectory);
db.sqlite.exec("VACUUM INTO 'work/profile-"+label+"-initial.sqlite'");
const trace=[];let operation;
const wrap=(sql,args=[])=>{
 const raw=db.prepare(sql).bind(...args);
 const log=method=>{trace.push({operation,sql,args,method});};
 return {bind(...values){return wrap(sql,values);},async first(){log('first');return raw.first();},async all(){log('all');return raw.all();},async run(){log('run');return raw.run();},execute(){log('execute');return raw.execute();}};
};
const measured={sqlite:db.sqlite,prepare:wrap,batch:statements=>db.batch(statements)};
const observations=[];
async function measure(name,fn){operation=name;const wall=performance.now(),cpu=process.cpuUsage(),value=await fn(),used=process.cpuUsage(cpu);observations.push({operation:name,node_process_cpu_ms:(used.user+used.system)/1000,local_wall_ms:performance.now()-wall});return value;}
await measure('owner_large_record',()=>owner.ownerRecordJSON?owner.ownerRecordJSON(measured,recordId):owner.ownerRecord(measured,recordId).then(r=>JSON.stringify(r)));
let r=await measure('notes_save',()=>mutate(measured,{op:'edit_session',request_id:crypto.randomUUID(),record_id:recordId,revision:1,metadata:{notes:['Synthetic note']}}));
r=await measure('normal_save',()=>mutate(measured,{op:'edit_session',request_id:crypto.randomUUID(),record_id:recordId,revision:r.revision,metadata:{notes:['Synthetic ordinary Save']},changes:[{id:'synthetic-item-000525',state:'pending',removed:false}],additions:[{group_id:groupId,field_key:'items',state:'wanted',value:'Synthetic normal addition'}]}));
const body=maximumBody(r.revision);
r=await measure('maximum_save',()=>mutate(measured,body));
const h=db.sqlite.prepare("SELECT id FROM change_history WHERE record_id=? AND action='edit_session' AND json_extract(after_json,'$._record_revision')=?").get(recordId,r.revision);
await measure('large_undo',()=>mutate(measured,{op:'undo',request_id:crypto.randomUUID(),record_id:recordId,revision:r.revision,history_id:h.id}));
writeFileSync('work/trace-'+label+'.json',JSON.stringify(trace));
writeFileSync('work/timings-'+label+'.json',JSON.stringify(observations,null,2));
db.close();console.log(JSON.stringify(observations));
