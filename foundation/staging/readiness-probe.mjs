// Proposed temporary disposable-only probe; never deployed by local preparation.
// Standalone module: no imports, fetch subrequests, DB access or owner credentials.
const hostname='wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev';
const encoder=new TextEncoder();
export default {async fetch(request,env){
 const url=new URL(request.url),until=Date.parse(env.MINIMAL_FREE_REVIEW_UNTIL||''),now=Date.now();
 const deny=()=>Response.json({error:'Forbidden'},{status:403,headers:{'Cache-Control':'no-store'}});
 if(url.hostname!==hostname||env.MINIMAL_FREE_REVIEW!=='true'||env.STAGING_ONLY!=='true'||env.STAGING_EDITOR!=='true'||env.ISOLATED_TEST_STORAGE!=='true'||!Number.isFinite(until)||until<=now||until-now>10*60*1000||!env.FREE_HTTP_REVIEW_KEY||!/^[a-f0-9]{32}$/.test(env.READINESS_PROBE_NONCE||''))return deny();
 // The nonce is a PUBLIC correlation value, never an authentication credential.
 if(request.method!=='GET'||url.pathname!=='/public/index'||url.search!=='?after=')return deny();
 const actual=encoder.encode(request.headers.get('X-Free-Review-Key')||''),expected=encoder.encode(env.FREE_HTTP_REVIEW_KEY);
 const authorized=actual.length===expected.length&&crypto.subtle.timingSafeEqual(actual,expected);
 return Response.json({probe:'wantlist-readiness-no-d1-v1',nonce:env.READINESS_PROBE_NONCE,authorized},{status:authorized?200:403,headers:{'Cache-Control':'no-store','X-Wantlist-Readiness':'no-d1-v1','X-Wantlist-Readiness-Nonce':env.READINESS_PROBE_NONCE}});
}};
