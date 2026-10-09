// All browser writes execute the real Worker in disposable in-memory SQLite.
// No Cloudflare credentials, remote relay, or D1 API are used.
import http from 'node:http';
import {readFileSync,existsSync} from 'node:fs';
import {timingSafeEqual} from 'node:crypto';
import {localD1} from '../foundation/tests/d1-local-adapter.mjs';
import worker from '../foundation/staging/worker.mjs';
import {mutate,openRecord,publicProjection} from '../foundation/staging/records.js';
const origin='https://isolated.wantlist.test';
Object.defineProperty(crypto.subtle,'timingSafeEqual',{value:(a,b)=>timingSafeEqual(Buffer.from(a),Buffer.from(b)),configurable:true});
function fixture(){
 const db=localD1();db.sqlite.exec(readFileSync('foundation/staging/schema.sql','utf8'));db.sqlite.exec("INSERT INTO staging_import_state VALUES(1,'isolated','isolated',0,1)");
 const view=JSON.parse(readFileSync('foundation/staging/historical-view.json','utf8'));
 const extra=view.records.find(r=>r.brand==='Topps'),year1951=view.records.find(r=>r.year==='1951');
 const chosen=view.records.filter(r=>r.display_category==='Brewers Bobblehead Wantlist'||r.id===year1951.id||r.id===extra.id||r.id==='p0581-l001'||r.id==='p0060-l001'||r.id==='p1237-l004'||r.id==='p1996-l008'||r.id==='p2501-l001'||r.id.startsWith('display-'));
 chosen.push({id:'owner-record-public-remnant',year:'2028',brand:'Bowman',set_name:'2028 Bowman Chrome Test',category:'baseball_cards',display_category:'UV Wantlist',list_type:'want_list',notes:['just collecting the first 10 cards'],card_numbers:['2','4','6','8','10']});
 const stamp=new Date().toISOString();
 for(const r of chosen){
  const mode=r.display_list_type||r.list_type,content={...r};for(const k of ['card_numbers','items','card_ranges','mixed_lists','sublists','source_records','source_wording'])delete content[k];
  if(r.id==='p0581-l001')delete content.display_category;
  db.sqlite.prepare('INSERT INTO records VALUES(?,NULL,?,?,1,?,?,NULL)').run(r.id,mode,JSON.stringify(content),stamp,stamp);
  const groups=[{...r,kind:'primary',position:0},...(r.mixed_lists||[]).map((g,i)=>({...g,kind:'mixed',position:i})),...(r.sublists||[]).map((g,i)=>({...g,kind:'sublist',position:i}))];
  for(const g of groups){
   const gid=r.id+':'+g.kind+':'+g.position,gm=g.kind==='primary'?mode:g.list_type||mode;
   db.sqlite.prepare('INSERT INTO record_groups VALUES(?,?,?,?,?,?,?)').run(gid,r.id,g.kind,g.position,gm,JSON.stringify({label:g.label,notes:r.id==='owner-record-public-remnant'?[]:g.notes||[],description:g.description}),'["card_numbers","items","card_ranges"]');
   for(const field of ['card_numbers','items','card_ranges'])for(const [i,value] of (g[field]||[]).entries()){
    const actionable=field!=='card_ranges'&&['want_list','have_list'].includes(gm)&&r.id!=='display-eau-claire-players';
    db.sqlite.prepare('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,NULL,NULL,NULL)').run(gid+':'+field+':'+i,gid,field,i,value,r.id==='owner-record-public-remnant'&&value==='2'?'owned':actionable?(gm==='have_list'?'owned':'wanted'):null,actionable?1:0,actionable?null:'Preserved source');
   }
  }
 }
 return db;
}
let db=fixture();
async function publish(){for(const {id} of db.sqlite.prepare('SELECT id FROM records').all()){const r=await openRecord(db,id);db.sqlite.prepare('INSERT INTO public_records VALUES(?,?,?,?,?)').run(id,r.revision,r.updated_at,0,JSON.stringify(publicProjection(r)));}}
await publish();
const env=()=>({DB:db,STAGING_ONLY:'true',STAGING_EDITOR:'true',OWNER_PIN:'4826',OWNER_PIN_VERSION:'isolated-test-only'});
http.createServer(async(req,res)=>{
 try{
  const data=[];for await(const chunk of req)data.push(chunk);
  const body=Buffer.concat(data).toString();
  if(req.url==='/reset'&&req.method==='POST'){db.close();db=fixture();await publish();res.end('reset');return;}
  if(req.url==='/external-edit'&&req.method==='POST'){const {id}=JSON.parse(body),r=await openRecord(db,id);await mutate(db,{op:'edit_session',request_id:crypto.randomUUID(),record_id:id,revision:r.revision,metadata:{notes:['Other device edit']}});res.end('saved');return;}
  if(req.url==='/expire'&&req.method==='POST'){const now=Math.floor(Date.now()/1000);db.sqlite.prepare('UPDATE sessions SET created_at=?,expires_at=?').run(now-100,now-1);res.end('expired');return;}
  if(req.url==='/relay'&&req.method==='POST'){
   const call=JSON.parse(body),path=call.path;
   if(!path.startsWith('/')||path.startsWith('//'))throw Error('path');
   const filename='foundation/.local/editor-dist'+(path==='/'?'/index.html':path.split('?')[0]);
   let response;
   if(call.method==='GET'&&existsSync(filename))response=new Response(readFileSync(filename),{headers:{'Content-Type':filename.endsWith('.html')?'text/html':filename.endsWith('.css')?'text/css':'application/javascript'}});
   else response=await worker.fetch(new Request(origin+path,{method:call.method,headers:call.headers,body:call.method==='POST'?call.body:undefined}),env());
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify({status:response.status,headers:Object.fromEntries(response.headers),body:Buffer.from(await response.arrayBuffer()).toString('base64')}));return;
  }
  res.end('isolated browser fixture ready');
 }catch(e){res.statusCode=500;res.end('Isolated fixture failed');process.stderr.write(String(e)+'\n');}
}).listen(5181,'127.0.0.1');
