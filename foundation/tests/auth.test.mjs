import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { localD1 } from './d1-local-adapter.mjs';
import worker from '../worker/index.js';
import { allowLogin, COOKIE_NAME, createSession, passwordVerifier, PASSWORD_ITERATIONS,
  readCookie, REMEMBERED_SECONDS, replacePassword, revokeAll, revokeSession,
  SHORT_SECONDS, tokenHash, validateSession, verifyPassword, revokeSessionByHash } from '../worker/auth.js';

let verifier;
const password = 'a long test-only passphrase';
before(async () => { verifier = await passwordVerifier(password); });
async function fixture() {
  const db = localD1();
  await db.prepare('INSERT INTO owners VALUES (?,?,1)').bind('owner', JSON.stringify(verifier)).run();
  return db;
}
const request = (path, body, headers = {}) => new Request(`https://localhost${path}`, {
  method: 'POST', headers: { Origin: 'https://localhost', 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
});
test('standard password verifier validates correct password, rejects wrong/malformed/weak settings', async () => {
  assert.equal(await verifyPassword(password, verifier), true);
  assert.equal(await verifyPassword('wrong password', verifier), false);
  assert.equal(await verifyPassword(password, { ...verifier, iterations: 1 }), false);
  assert.equal(await verifyPassword(password, { ...verifier, salt: 'bad' }), false);
  assert.equal(await verifyPassword(null, verifier), false);
  await assert.rejects(passwordVerifier('1234'));
  assert.equal(verifier.iterations, PASSWORD_ITERATIONS);
  assert.equal(JSON.stringify(verifier).includes(password), false);
});
test('remembered cookie persists 90 days, has required flags, token stored hashed', async () => {
  const db = await fixture();
  try {
    const clock = () => 1_700_000_000_000;
    const session = await createSession(db, { id: 'owner', auth_version: 1 }, true, clock);
    assert.equal(session.expires, clock() / 1000 + REMEMBERED_SECONDS);
    for (const flag of ['Secure', 'HttpOnly', 'SameSite=Strict', 'Path=/', `Max-Age=${REMEMBERED_SECONDS}`]) assert.ok(session.cookie.includes(flag));
    const stored = await db.prepare('SELECT * FROM sessions').first();
    assert.equal(stored.token_hash, await tokenHash(session.token));
    assert.notEqual(stored.token_hash, session.token);
    assert.ok(await validateSession(db, session.token, clock));
    assert.equal(await validateSession(db, session.token, () => session.expires * 1000), null);
  } finally { db.close(); }
});
test('non-remembered cookie is a browser session cookie with absolute 8 hour server expiry', async () => {
  const db = await fixture();
  try {
    const session = await createSession(db, { id: 'owner', auth_version: 1 }, false, () => 0);
    assert.equal(session.expires, SHORT_SECONDS);
    assert.equal(session.cookie.includes('Max-Age'), false);
    assert.equal(await validateSession(db, session.token, () => SHORT_SECONDS * 1000), null);
  } finally { db.close(); }
});
test('forged, missing, malformed and duplicate session cookies rejected', async () => {
  const db = await fixture();
  try {
    assert.equal(await validateSession(db, '0'.repeat(64)), null);
    assert.equal(await validateSession(db, null), null);
    assert.equal(readCookie(new Request('https://localhost')), null);
    assert.equal(readCookie(new Request('https://localhost', { headers: { Cookie: `${COOKIE_NAME}=bad` } })), null);
    assert.equal(readCookie(new Request('https://localhost', { headers: { Cookie: `${COOKIE_NAME}=${'a'.repeat(64)}; ${COOKIE_NAME}=${'b'.repeat(64)}` } })), null);
  } finally { db.close(); }
});
test('individual revocation preserves other remembered device', async () => {
  const db = await fixture();
  try {
    const a = await createSession(db, { id: 'owner', auth_version: 1 }, true);
    const b = await createSession(db, { id: 'owner', auth_version: 1 }, true);
    await revokeSessionByHash(db, await tokenHash(a.token));
    assert.equal(await validateSession(db, a.token), null);
    assert.ok(await validateSession(db, b.token));
  } finally { db.close(); }
});
test('revoke all and password replacement invalidate prior devices', async () => {
  const db = await fixture();
  try {
    const a = await createSession(db, { id: 'owner', auth_version: 1 }, true);
    await revokeAll(db);
    assert.equal(await validateSession(db, a.token), null);
    const b = await createSession(db, { id: 'owner', auth_version: 2 }, true);
    await replacePassword(db, verifier);
    assert.equal(await validateSession(db, b.token), null);
    assert.equal((await db.prepare('SELECT * FROM owners').first()).auth_version, 3);
  } finally { db.close(); }
});
test('IP throttle counts attempts and resets after window', async () => {
  const db = await fixture();
  try {
    for (let i = 0; i < 5; i++) assert.equal(await allowLogin(db, '192.0.2.1', () => 0), true);
    assert.equal(await allowLogin(db, '192.0.2.1', () => 0), false);
    assert.equal(await allowLogin(db, '192.0.2.1', () => 900_000), true);
  } finally { db.close(); }
});
test('global throttle applies across different addresses', async () => {
  const db = await fixture();
  try {
    for (let i = 0; i < 25; i++) assert.equal(await allowLogin(db, `192.0.2.${i}`, () => 0), true);
    assert.equal(await allowLogin(db, '198.51.100.1', () => 0), false);
  } finally { db.close(); }
});
test('Worker refuses non-local use regardless of credentials', async () => {
  const db = await fixture();
  try {
    assert.equal((await worker.fetch(new Request('https://example.com/foundation/health'), { DB: db, FOUNDATION_MODE: 'local-test' })).status, 503);
    assert.equal((await worker.fetch(new Request('https://localhost/foundation/health'), { DB: db })).status, 503);
  } finally { db.close(); }
});
test('unauthorized write and cross-origin login rejected', async () => {
  const db = await fixture();
  try {
    const env = { DB: db, FOUNDATION_MODE: 'local-test' };
    assert.equal((await worker.fetch(request('/owner/edit', {}), env)).status, 401);
    assert.equal((await worker.fetch(request('/owner/login', { password, remembered: true }, { Origin: 'https://evil.example' }), env)).status, 403);
    assert.equal((await worker.fetch(new Request('https://localhost/owner/login', { method: 'POST', body: '{}' }), env)).status, 403);
  } finally { db.close(); }
});
test('login, session inspection, logout and replay rejection work together', async () => {
  const db = await fixture();
  try {
    const env = { DB: db, FOUNDATION_MODE: 'local-test' };
    const bad = await worker.fetch(request('/owner/login', { password: 'wrong', remembered: true }), env);
    assert.equal(bad.status, 401);
    const login = await worker.fetch(request('/owner/login', { password, remembered: true }), env);
    assert.equal(login.status, 200);
    const body = await login.json();
    assert.equal('token' in body, false);
    assert.equal('password' in body, false);
    const cookie = login.headers.get('set-cookie').split(';')[0];
    const inspected = await worker.fetch(new Request('https://localhost/owner/session', { headers: { Cookie: cookie } }), env);
    assert.equal(inspected.status, 200);
    assert.equal((await inspected.json()).remembered, true);
    const noEditor = await worker.fetch(request('/owner/edit', {}, { Cookie: cookie }), env);
    assert.equal(noEditor.status, 404);
    const logout = await worker.fetch(request('/owner/logout', {}, { Cookie: cookie }), env);
    assert.equal(logout.status, 200);
    assert.ok(logout.headers.get('set-cookie').includes('Max-Age=0'));
    assert.equal((await worker.fetch(new Request('https://localhost/owner/session', { headers: { Cookie: cookie } }), env)).status, 401);
  } finally { db.close(); }
});
test('bad request types and malformed JSON do not authenticate', async () => {
  const db = await fixture();
  try {
    const env = { DB: db, FOUNDATION_MODE: 'local-test' };
    assert.equal((await worker.fetch(request('/owner/login', { password, remembered: 'true' }), env)).status, 400);
    assert.equal((await worker.fetch(request('/owner/login', { password, remembered: true }, { 'Content-Type': 'text/plain' }), env)).status, 400);
    assert.equal((await worker.fetch(new Request('https://localhost/owner/login', {
      method: 'POST', headers: { Origin: 'https://localhost', 'Content-Type': 'application/json' }, body: '{',
    }), env)).status, 400);
    assert.equal((await worker.fetch(request('/owner/login', { password: 'x'.repeat(5000), remembered: true }), env)).status, 400);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM sessions').first()).n, 0);
  } finally { db.close(); }
});
