// Structural before/after profiling. Local SQLite timing is NOT Worker CPU.
// Writes only ignored disposable fixtures and a public count-only report.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {localD1} from '../tests/d1-local-adapter.mjs';
import * as current from './records.js';
const root=new URL('../../',import.meta.url),path='/tmp/wantlist-cpu-baseline';mkdirSync(path,{recursive:true});
for(const f of ['auth.js','records.js'])writeFileSync(path+'/'+f,execFileSync('git',['show','d89402e56449ac745e481db599b8514d1cb239ff:foundation/staging/'+f],{cwd:root}));
const original=await import(pathToFileURL(path+'/records.js'));
const source=JSON.parse(readFileSync(new URL('data/wantlists.json',root))).records;
const count=r=>[r,...r.mixed_lists||[],...r.sublists||[]].reduce((n,g)=>n+['card_numbers','items','card_ranges'].reduce((n,k)=>n+(g[k]||[]).length,0),0);
const large=source.reduce((a,b)=>count(a)>count(b)?a:b);
const fixtureJSON=execFileSync('python',['-c',`import json;from foundation import storage;b=storage.load_baseline();r=next(r for r in b['records'] if r['id']=='${large.id}');db=storage.connect();storage.apply_schema(db);storage.initialize(db,b);ex=storage.private_export(db);t=ex['tables'];g={g['id'] for g in t['record_groups'] if g['record_id']==r['id']};t['records']=[x for x in t['records'] if x['id']==r['id']];t['record_groups']=[x for x in t['record_groups'] if x['id'] in g];t['items']=[x for x in t['items'] if x['group_id'] in g];t['provenance']=[x for x in t['provenance'] if x['record_id']==r['id']];print(json.dumps(ex))`],{cwd:root,maxBuffer:2000000});
const fixtures=JSON.parse(fixtureJSON).tables;
async function fixture(module){
 const db=localD1();db.sqlite.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'test','test',1,1)");
 for(const [table,rows] of Object.entries(fixtures))for(const row of rows){const keys=Object.keys(row);db.sqlite.prepare('INSERT INTO '+table+'('+keys.join(',')+') VALUES('+keys.map(()=>'?').join(',')+')').run(...keys.map(k=>row[k]));}
 const r=await module.openRecord(db,large.id);db.sqlite.prepare('INSERT INTO public_records VALUES(?,?,?,?,?)').run(r.id,r.revision,r.updated_at,0,JSON.stringify(module.publicProjection(r)));return db;
}
function measured(db){
 const totals={binding_calls:0,batch_calls:0,sql_statements:0,bound_json_bytes:0,returned_json_bytes:0};
 const size=v=>Buffer.byteLength(JSON.stringify(v));
 function st(sql,args=[]){const raw=db.prepare(sql).bind(...args);return {raw,args,bind(...values){return st(sql,values);},async first(){totals.binding_calls++;totals.sql_statements++;totals.bound_json_bytes+=size(args);const row=await raw.first();totals.returned_json_bytes+=size(row);return row;},async all(){totals.binding_calls++;totals.sql_statements++;totals.bound_json_bytes+=size(args);const row=await raw.all();totals.returned_json_bytes+=size(row);return row;}};}
 return {totals,prepare:sql=>st(sql),async batch(statements){totals.binding_calls++;totals.batch_calls++;totals.sql_statements+=statements.length;totals.bound_json_bytes+=statements.reduce((n,s)=>n+size(s.args),0);return db.batch(statements.map(s=>s.raw));}};
}
const result={fixture_record:large.id,fixture_literal_count:count(large),timing:'Structural bytes/calls only. No Worker CPU or D1 billed rows inferred.',operations:{}};
for(const name of ['transition','add_1','add_20','edit_notes','remove_item','restore_item']){
 result.operations[name]={};
 for(const [label,module] of [['before',original],['after',current]]){
  const db=await fixture(module);try{
   let r=await module.openRecord(db,large.id);const item=r.groups.flatMap(g=>g.entries).filter(i=>i.actionable)[347];
   let input={request_id:crypto.randomUUID(),record_id:r.id,revision:r.revision};
   if(name==='transition'){
    if(item.state!=='wanted'){await module.mutate(db,{...input,op:'transition',item_id:item.id,state:'wanted'});input={...input,request_id:crypto.randomUUID(),revision:input.revision+1};}
    Object.assign(input,{op:'transition',item_id:item.id,state:'pending'});
   }else if(name.startsWith('add_'))Object.assign(input,{op:'add',state:'owned',values:Array.from({length:name==='add_1'?1:20},(_,n)=>'profile-new-'+n)});
   else if(name==='edit_notes')Object.assign(input,{op:'edit',metadata:{notes:['Disposable local profile note']}});
   else {if(name==='restore_item'){await module.mutate(db,{...input,op:'remove_item',item_id:item.id});input={...input,request_id:crypto.randomUUID(),revision:input.revision+1};}Object.assign(input,{op:name,item_id:item.id});}
   const wrapper=measured(db);await module.mutate(wrapper,input);result.operations[name][label]=wrapper.totals;
  }finally{db.close();}
 }
}
writeFileSync(new URL('./cpu-structural-profile-result.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
