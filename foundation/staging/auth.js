// Staging-only approved owner-secret authentication. Access codes NEVER expire.
// Strong-code mode remains unchanged. Explicit PIN-secret mode intentionally
// has only 10,000 possibilities; it is not equivalent to a strong credential.
export const COOKIE = '__Host-wantlist_owner';
export const REMEMBERED = 90 * 86400;
export const SHORT = 8 * 3600;
const enc = new TextEncoder();
export const hex = bytes => [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
export const random = () => hex(crypto.getRandomValues(new Uint8Array(32)));
export const hash = async value => hex(new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(value))));
export function config(env) {
  if(env.OWNER_PIN!==undefined){
    if(!/^\d{4}$/.test(env.OWNER_PIN)||!/^[-\w]{16,100}$/.test(env.OWNER_PIN_VERSION||''))throw Error('Invalid PIN secret configuration');
    return {algorithm:'SHA-256',version:env.OWNER_PIN_VERSION,pin:true};
  }
  const c = JSON.parse(env.OWNER_AUTH_CONFIG);
  if (c.algorithm !== 'SHA-256' || !/^[a-f0-9]{64}$/.test(c.digest) || !/^[\w-]{16,100}$/.test(c.version)) throw Error('Invalid secret configuration');
  return c;
}
export async function verifyCredential(value, env) {
  const c=config(env);
  if(typeof value!=='string'||(c.pin?!/^\d{4}$/.test(value):value.length>256||value.length<20))return false;
  const actual = await crypto.subtle.digest('SHA-256', enc.encode(value));
  const expected = c.pin ? new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(env.OWNER_PIN))) : Uint8Array.from(c.digest.match(/../g), x => parseInt(x, 16));
  return crypto.subtle.timingSafeEqual(actual, expected);
}
export async function throttle(db, ip) {
  const window = Math.floor(Date.now() / 900000) * 900;
  const buckets = [{key: 'owner-global', limit: 25}, {key: `ip:${await hash(ip || 'unknown')}`, limit: 5}];
  const rows = await db.batch(buckets.map(b => db.prepare(`INSERT INTO login_limits VALUES (?,?,1)
    ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN window_start=excluded.window_start THEN attempts+1 ELSE 1 END,
    window_start=excluded.window_start RETURNING attempts`).bind(b.key, window)));
  return rows.every((r, i) => r.results[0].attempts <= buckets[i].limit);
}
export async function issue(db, env, remembered) {
  const token = random(), now = Math.floor(Date.now() / 1000), expires = now + (remembered ? REMEMBERED : SHORT);
  // INSERT ... SELECT binds the session to the current revocation generation.
  const result = await db.prepare(`INSERT INTO sessions(token_hash,credential_version,revocation_generation,remembered,created_at,expires_at,last_seen_at)
    SELECT ?,?,generation,?,?,?,? FROM auth_control WHERE id=1`).bind(await hash(token), config(env).version, remembered ? 1 : 0, now, expires, now).run();
  if (result.meta.changes !== 1) throw Error('Session not persisted');
  return {token, expires, cookie: `${COOKIE}=${token}; Path=/; Secure; HttpOnly; SameSite=Strict${remembered ? `; Max-Age=${REMEMBERED}` : ''}`};
}
export function cookieToken(request) {
  const cookies = (request.headers.get('Cookie') || '').split(';').map(x => x.trim()).filter(x => x.startsWith(`${COOKIE}=`));
  if (cookies.length !== 1) return null;
  const token = cookies[0].slice(COOKIE.length + 1);
  return /^[a-f0-9]{64}$/.test(token) ? token : null;
}
export async function validate(db, env, token, readStatements=[]) {
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return null;
  const statement = db.prepare(`SELECT s.* FROM sessions s JOIN auth_control a ON a.id=1 AND a.generation=s.revocation_generation
    WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND s.credential_version=?`).bind(await hash(token), Math.floor(Date.now()/1000), config(env).version);
  if(readStatements.length){
    // Same authentication predicate; batch read-only preflight with it to avoid
    // extra Worker/D1 binding round trips. No mutation runs before authorization.
    const results=await db.batch([statement,...readStatements]);
    return {session:results[0].results[0]||null,reads:results.slice(1)};
  }
  return await statement.first() || null;
}
export const logoutCookie = `${COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0`;
