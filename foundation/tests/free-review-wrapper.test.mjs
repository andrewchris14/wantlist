import test from 'node:test';
import assert from 'node:assert/strict';
import {randomInt, timingSafeEqual} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {localD1} from './d1-local-adapter.mjs';
import wrapper from '../staging/free-review-wrapper.mjs';

Object.defineProperty(crypto.subtle, 'timingSafeEqual', {
  value: (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b)), configurable: true,
});
const origin = 'https://wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev';
const key = crypto.randomUUID() + crypto.randomUUID();
const pin = String(randomInt(10000)).padStart(4, '0');
const base = {STAGING_ONLY: 'true', ISOLATED_TEST_STORAGE: 'true',
  STAGING_EDITOR: 'true', FREE_HTTP_REVIEW_KEY: key,
  OWNER_PIN: pin, OWNER_PIN_VERSION: 'local-disposable-version-0001'};
const request = (url = origin, method = 'POST', headers = {}) => new Request(
  url + '/test/free-review-login', {method,
    headers: {Origin: url, 'X-Free-Review-Key': key, ...headers}});

test('temporary login adapter rejects staging, wrong host, wrong origin and invalid gate before DB access', async () => {
  const forbiddenDB = {prepare() {throw Error('Unauthorized DB access');},
    batch() {throw Error('Unauthorized DB access');}};
  const cases = [
    [request(), {...base, STAGING_ONLY: 'false'}],
    [request(), {...base, ISOLATED_TEST_STORAGE: 'false'}],
    [request('https://wantlist-staging.andrewchris14.workers.dev'), base],
    [request(origin, 'GET'), base],
    [request(origin, 'POST', {Origin: 'https://unapproved.invalid'}), base],
    [request(), {...base, FREE_HTTP_REVIEW_KEY: undefined}],
    [request(origin, 'POST', {'X-Free-Review-Key': 'incorrect'}), base],
    [request(), {...base, OWNER_PIN: undefined}],
  ];
  for (const [req, env] of cases) {
    const response = await wrapper.fetch(req, {...env, DB: forbiddenDB});
    assert.equal(response.status, 403);
    assert.deepEqual(await response.json(), {error: 'Forbidden'});
  }
});

test('authorized local adapter uses ordinary remembered login without exposing PIN or changing revocation generation', async () => {
  const db = localD1();
  try {
    db.sqlite.exec(readFileSync(new URL('../staging/schema.sql', import.meta.url), 'utf8'));
    const before = db.sqlite.prepare('SELECT generation FROM auth_control WHERE id=1').get().generation;
    const response = await wrapper.fetch(request(), {...base, DB: db});
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.signed_in, true);
    assert.deepEqual(Object.keys(body).sort(), ['expires', 'signed_in']);
    assert.ok(response.headers.get('Set-Cookie').includes('Secure; HttpOnly; SameSite=Strict; Max-Age='));
    assert.equal(db.sqlite.prepare('SELECT remembered FROM sessions').get().remembered, 1);
    assert.equal(db.sqlite.prepare('SELECT generation FROM auth_control WHERE id=1').get().generation, before);
  } finally {db.close();}
});

test('minimal review lease rejects every route before D1 on expiry, missing key, wrong storage or host',async()=>{
 const noDB={prepare(){throw Error('Forbidden D1 access');},batch(){throw Error('Forbidden D1 access');}};
 const lease={...base,DB:noDB,MINIMAL_FREE_REVIEW:'true',MINIMAL_FREE_REVIEW_UNTIL:new Date(Date.now()+10*60*1000).toISOString()};
 const read=(path='/public/index',headers={'X-Free-Review-Key':key},host=origin,method='GET')=>new Request(host+path,{method,headers});
 for(const [req,env] of [
  [read(),{...lease,MINIMAL_FREE_REVIEW_UNTIL:new Date(0).toISOString()}],
  [read(),{...lease,MINIMAL_FREE_REVIEW_UNTIL:undefined}],
  [read(),{...lease,MINIMAL_FREE_REVIEW_UNTIL:'invalid'}],
  [read(),{...lease,MINIMAL_FREE_REVIEW_UNTIL:new Date(Date.now()+60*60*1000).toISOString()}],
  [read(),{...lease,ISOLATED_TEST_STORAGE:'false'}],
  [read(),{...lease,STAGING_EDITOR:'false'}],
  [read('/owner/record',{}),lease],
  [read('/action',{'X-Free-Review-Key':key},origin,'POST'),{...lease,FREE_HTTP_REVIEW_KEY:undefined}],
  [read('/public/index',{'X-Free-Review-Key':'wrong'}),lease],
  [read('/public/index',{'X-Free-Review-Key':key},'https://wantlist-staging.andrewchris14.workers.dev'),lease],
  [read('/operator/phase34-migration',{'X-Free-Review-Key':key},origin,'POST'),lease],
  [read('/public/index',{'X-Free-Review-Key':key},origin,'POST'),lease],
 ]){
  const r=await wrapper.fetch(req,env);assert.equal(r.status,403);const text=await r.text();assert.deepEqual(JSON.parse(text),{error:'Forbidden'});assert.ok(!text.includes(key));
 }
});

test('valid short review lease preserves normal login and passes public index through unchanged',async()=>{
 const db=localD1();try{
 db.sqlite.exec(readFileSync(new URL('../staging/schema.sql',import.meta.url),'utf8'));
 db.sqlite.exec(readFileSync(new URL('../staging/public-index.sql',import.meta.url),'utf8'));
 const env={...base,DB:db,MINIMAL_FREE_REVIEW:'true',MINIMAL_FREE_REVIEW_UNTIL:new Date(Date.now()+10*60*1000).toISOString()};
 const login=await wrapper.fetch(request(),env);assert.equal(login.status,200);assert.ok(login.headers.get('Set-Cookie'));
 const r=await wrapper.fetch(new Request(origin+'/public/index?after=',{headers:{'X-Free-Review-Key':key}}),env);
 assert.equal(r.status,200);assert.deepEqual(await r.json(),{records:[],next:null});
 assert.equal(db.sqlite.prepare('SELECT generation FROM auth_control WHERE id=1').get().generation,1);
 }finally{db.close();}
});
