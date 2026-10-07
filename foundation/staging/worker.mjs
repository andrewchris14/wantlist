// Isolated staging backend. No production site integration or Dad-facing editor.
import {verifyCredential, throttle, issue, validate, cookieToken, hash, config, logoutCookie} from './auth.js';
import {mutate, openRecord, catalog, publicProjection} from './records.js';
const json = (body, status=200, headers={}) => Response.json(body,{status,headers:{'Cache-Control':'no-store',...headers}});
async function handle(request,env){
  if(env.STAGING_ONLY !== 'true') return json({error:'Staging only'},503);
  const url=new URL(request.url), origin=url.origin;
  // Operator gate isolates ALL staging routes, including the test-only batch tool.
  // Comparing digests avoids ordinary string comparison of the operator secret.
  const supplied=request.headers.get('X-Staging-Probe') || '';
  if(!env.PROBE_KEY || !await verifyCredential(supplied,{OWNER_AUTH_CONFIG:JSON.stringify({algorithm:'SHA-256',digest:await hash(env.PROBE_KEY),version:'staging-operator-gate'})})) return json({error:'Forbidden'},403);
  if(request.method!=='GET' && request.headers.get('Origin')!==origin) return json({error:'Forbidden'},403);
  try {
    if(url.pathname==='/health') return json({staging:true});
    if(request.method==='POST') {
      if(!(request.headers.get('Content-Type') || '').startsWith('application/json')) return json({error:'Invalid request'},400);
      if(Number(request.headers.get('Content-Length'))>2000000) return json({error:'Too large'},413);
    }
    const body=request.method==='POST'?await request.json():null;
    if(url.pathname==='/login' && request.method==='POST') {
      if(typeof body.remembered!=='boolean')return json({error:'Unable to sign in'},400);
      if(!await throttle(env.DB,request.headers.get('CF-Connecting-IP')))return json({error:'Unable to sign in'},429);
      if(!await verifyCredential(body.credential,env))return json({error:'Unable to sign in'},401);
      const session=await issue(env.DB,env,body.remembered);
      return json({signed_in:true,expires:session.expires},200,{'Set-Cookie':session.cookie});
    }
    // Operator diagnostics exist only on staging and never accept owner secrets
    // or session tokens in JSON responses. No production route exposes this API.
    if(url.pathname==='/test/batch' && request.method==='POST') {
      if(!Array.isArray(body.statements)||!body.statements.length||body.statements.length>44) return json({error:'Invalid batch'},400);
      const statements=body.statements.map(s=>env.DB.prepare(s.sql).bind(...(s.params||[])));
      return json({results:await env.DB.batch(statements)});
    }
    if(url.pathname==='/public/catalog')return json({records:(await env.DB.prepare('SELECT record_id,revision,updated_at,deleted FROM public_records ORDER BY record_id').all()).results});
    if(url.pathname==='/public/record') {
      const row=await env.DB.prepare('SELECT * FROM public_records WHERE record_id=?').bind(url.searchParams.get('id')).first();
      if(row?.deleted)return json({id:row.record_id,revision:row.revision,updated_at:row.updated_at,deleted:true,groups:[]});
      return row?new Response(row.public_json,{headers:{'Content-Type':'application/json','Cache-Control':'public, max-age=30','ETag':`"${row.record_id}:${row.revision}"`}}):json({error:'Not found'},404);
    }
    if(url.pathname==='/public/page') {
      const rows=(await env.DB.prepare('SELECT record_id,revision,updated_at,deleted,public_json FROM public_records WHERE record_id>? ORDER BY record_id LIMIT 50').bind(url.searchParams.get('after')||'').all()).results;
      return new Response('{"records":['+rows.filter(r=>!r.deleted).map(r=>r.public_json).join(',')+'],"next":'+JSON.stringify(rows.length===50?rows.at(-1).record_id:null)+'}',{headers:{'Content-Type':'application/json','Cache-Control':'public, max-age=30'}});
    }
    if(url.pathname==='/test/publish' && request.method==='POST') {
      const r=await openRecord(env.DB,body.record_id);if(!r)return json({error:'Not found'},404);
      // Guard baseline projection publication against stale reads atomically.
      const id='publish-guard-'+crypto.randomUUID();
      await env.DB.batch([
        env.DB.prepare("INSERT INTO foundation_meta VALUES(?,CASE WHEN (SELECT revision FROM records WHERE id=?)=? THEN '1' ELSE NULL END)").bind(id,r.id,r.revision),
        env.DB.prepare('INSERT INTO public_records VALUES(?,?,?,?,?) ON CONFLICT(record_id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at,deleted=excluded.deleted,public_json=excluded.public_json').bind(r.id,r.revision,r.updated_at,r.deleted_at?1:0,JSON.stringify(publicProjection(r))),
        env.DB.prepare('DELETE FROM foundation_meta WHERE key=?').bind(id)
      ]);
      return json({published:true,revision:r.revision});
    }
    const session=await validate(env.DB,env,cookieToken(request));
    if(!session)return json({error:'Sign in required'},401);
    if(url.pathname==='/session')return json({signed_in:true,remembered:!!session.remembered,expires:session.expires_at});
    if(url.pathname==='/logout' && request.method==='POST') {
      await env.DB.prepare('UPDATE sessions SET revoked_at=? WHERE token_hash=?').bind(Math.floor(Date.now()/1000),session.token_hash).run();
      return json({signed_in:false},200,{'Set-Cookie':logoutCookie});
    }
    if(url.pathname==='/revoke-all' && request.method==='POST') {
      await env.DB.prepare('UPDATE auth_control SET generation=generation+1 WHERE id=1').run();
      return json({revoked:true},200,{'Set-Cookie':logoutCookie});
    }
    if(url.pathname==='/catalog')return json({records:await catalog(env.DB)});
    if(url.pathname==='/record')return json(await openRecord(env.DB,url.searchParams.get('id')));
    if(url.pathname==='/recent')return json({changes:(await env.DB.prepare('SELECT id,record_id,action,created_at FROM change_history ORDER BY created_at DESC,id DESC LIMIT 20').all()).results});
    if(url.pathname==='/action' && request.method==='POST')return json(await mutate(env.DB,body));
    return json({error:'Not found'},404);
  }catch(error){
    // Do not include SQL, credentials, private data, or exception messages.
    return json({error:error.code==='CONFLICT'?'Changed since you opened it':error.code==='INVALID'?'Invalid change':'Unable to save; try again'},error.code==='CONFLICT'?409:error.code==='INVALID'?400:503);
  }
}
export default {async fetch(request,env){
 const totals={rows_read:0,rows_written:0};
 const collect=r=>{totals.rows_read+=r.meta?.rows_read||0;totals.rows_written+=r.meta?.rows_written||0;return r;};
 const raw=env.DB;
 const wrap=st=>({raw:st,bind(...args){return wrap(st.bind(...args));},async all(){return collect(await st.all());},async first(){const r=collect(await st.all());return r.results[0]||null;},async run(){return collect(await st.run());}});
 const db={prepare(sql){return wrap(raw.prepare(sql));},async batch(statements){return (await raw.batch(statements.map(s=>s.raw))).map(collect);}};
 const response=await handle(request,{...env,DB:db});
 const headers=new Headers(response.headers);headers.set('X-Staging-D1-Reads',String(totals.rows_read));headers.set('X-Staging-D1-Writes',String(totals.rows_written));
 return new Response(response.body,{status:response.status,headers});
}};
