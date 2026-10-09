// Synthetic-only performance fixture. Never reads a backup or a remote database.
import {localD1} from './d1-local-adapter.mjs';
import {readFileSync} from 'node:fs';
export const recordId='synthetic-performance-large',groupId=recordId+'-primary';
export function performanceFixture(path=':memory:',size=526,removed=1503,baselineDirectory=null){
 const db=localD1(path);
 db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));
 db.sqlite.exec(readFileSync(baselineDirectory?baselineDirectory+'/foundation/staging/public-index.sql':new URL('../staging/public-index.sql',import.meta.url),'utf8'));
 if(!baselineDirectory)db.sqlite.exec(readFileSync(new URL('../staging/phase3c6-performance.sql',import.meta.url),'utf8'));
 db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'synthetic','synthetic',1,1)");
 const content={id:recordId,set_name:'Synthetic large inventory',year:'2026',brand:'Synthetic Maker',category:'baseball_cards',display_category:'UV Wantlist',notes:['Original synthetic note'],prefixes:[],source_list_type:'want_list',entry_order:'natural'};
 db.sqlite.prepare('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)').run(recordId,'want_list',JSON.stringify(content),'synthetic','synthetic');
 db.sqlite.prepare('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)').run(groupId,recordId,'primary',0,'want_list','{}','["items"]');
 const insert=db.sqlite.prepare('INSERT INTO items VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,?)');
 const entries=[];
 for(let n=0;n<size+removed;n++){
  const id='synthetic-item-'+String(n).padStart(6,'0'),value=n<size?'Synthetic literal '+n:('Synthetic removed '+n+' '+ 'R'.repeat(500)).slice(0,500);
  insert.run(id,groupId,'items',n,value,'wanted',n<size?null:'synthetic-removed');
  if(n<size)entries.push({id,value,position:n,field_key:'items',state:'wanted',actionable:1,pending_at:null,received_at:null});
 }
 db.sqlite.prepare('INSERT INTO public_records VALUES(?,1,?,0,?)').run(recordId,'synthetic',JSON.stringify({...content,list_type:'want_list',revision:1,updated_at:'synthetic',deleted:false,projection_version:2,groups:[{id:groupId,kind:'primary',list_type:'want_list',entries}]}));
 // Unrelated records expose accidental whole-database scans without real data.
 for(let n=0;n<100;n++){
  const id='synthetic-unrelated-'+n,g=id+'-group';
  db.sqlite.prepare('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)').run(id,'want_list',JSON.stringify({...content,id}),'synthetic','synthetic');
  db.sqlite.prepare('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)').run(g,id,'primary',0,'want_list','{}','["items"]');
  for(let j=0;j<20;j++)insert.run(g+'-'+j,g,'items',j,'Unrelated '+j,'wanted',null);
 }
 return db;
}
export function maximumBody(revision=1,count=500){return {op:'edit_session',request_id:crypto.randomUUID(),record_id:recordId,revision,metadata:{notes:['Synthetic maximum Save']},changes:Array.from({length:count},(_,n)=>({id:'synthetic-item-'+String(n).padStart(6,'0'),state:'pending',removed:false})),additions:Array.from({length:count},(_,n)=>({group_id:groupId,field_key:'items',state:'wanted',value:('Synthetic new '+String(n).padStart(3,'0')+' '+ 'X'.repeat(500)).slice(0,500)}))};}
