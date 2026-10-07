// Web Crypto primitives only; no bespoke password hashing/encryption algorithm.
// Local reference. Cloudflare PBKDF2 support/CPU budget must pass the readiness
// gate before deployment. Never reduce the work factor to fit a free quota.
export const REMEMBERED_SECONDS = 90 * 24 * 60 * 60;
export const SHORT_SECONDS = 8 * 60 * 60;
export const PASSWORD_ITERATIONS = 600_000;
export const COOKIE_NAME = '__Host-wantlist_owner';
const encoder = new TextEncoder();
const hex = bytes => [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
const unhex = s => {
  if (typeof s !== 'string' || !/^(?:[0-9a-f]{2})+$/.test(s)) throw new Error('Invalid encoding');
  return Uint8Array.from(s.match(/../g), x => parseInt(x, 16));
};
const random = count => hex(crypto.getRandomValues(new Uint8Array(count)));
export async function tokenHash(token) {
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(token))));
}
async function derive(password, salt, iterations) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, 256));
}
export async function passwordVerifier(password) {
  if (typeof password !== 'string' || password.length < 14 || password.length > 256) throw new Error('Use a long passphrase (14–256 characters)');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return { algorithm: 'PBKDF2-SHA256', iterations: PASSWORD_ITERATIONS, salt: hex(salt), hash: hex(await derive(password, salt, PASSWORD_ITERATIONS)) };
}
export async function verifyPassword(password, verifier) {
  if (typeof password !== 'string' || password.length > 256 || !verifier || verifier.algorithm !== 'PBKDF2-SHA256' || verifier.iterations !== PASSWORD_ITERATIONS) return false;
  try {
    const salt = unhex(verifier.salt), expected = unhex(verifier.hash);
    if (salt.length !== 16 || expected.length !== 32) return false;
    const actual = await derive(password, salt, verifier.iterations);
    let diff = 0;
    for (let i = 0; i < actual.length; i++) diff |= actual[i] ^ expected[i];
    return diff === 0;
  } catch { return false; }
}
export async function createSession(db, owner, remembered, clock = Date.now) {
  const now = Math.floor(clock() / 1000), token = random(32);
  const expires = now + (remembered ? REMEMBERED_SECONDS : SHORT_SECONDS);
  await db.prepare('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,NULL)').bind(await tokenHash(token), owner.id, owner.auth_version, remembered ? 1 : 0, now, expires, now).run();
  return { token, expires, cookie: `${COOKIE_NAME}=${token}; Path=/; Secure; HttpOnly; SameSite=Strict${remembered ? `; Max-Age=${REMEMBERED_SECONDS}` : ''}` };
}
export function readCookie(request) {
  const parts = (request.headers.get('cookie') || '').split(';').map(s => s.trim());
  const matches = parts.filter(s => s.startsWith(`${COOKIE_NAME}=`));
  if (matches.length !== 1) return null;
  const token = matches[0].slice(COOKIE_NAME.length + 1);
  return /^[0-9a-f]{64}$/.test(token) ? token : null;
}
export async function validateSession(db, token, clock = Date.now) {
  if (!token || !/^[0-9a-f]{64}$/.test(token)) return null;
  const row = await db.prepare('SELECT s.*,o.auth_version AS current_version FROM sessions s JOIN owners o ON o.id=s.owner_id WHERE token_hash=?').bind(await tokenHash(token)).first();
  const now = Math.floor(clock() / 1000);
  if (!row || row.revoked_at !== null || row.expires_at <= now || row.auth_version !== row.current_version) return null;
  if (now - row.last_seen_at >= 86400) {
    await db.prepare('UPDATE sessions SET last_seen_at=? WHERE token_hash=?').bind(now, row.token_hash).run();
  }
  return row;
}
export async function revokeSessionByHash(db, hash, clock = Date.now) {
  if (!/^[0-9a-f]{64}$/.test(hash)) throw new Error('Invalid session identifier');
  await db.prepare('UPDATE sessions SET revoked_at=? WHERE token_hash=?').bind(Math.floor(clock() / 1000), hash).run();
}
export async function revokeSession(db, token, clock = Date.now) {
  if (token) await revokeSessionByHash(db, await tokenHash(token), clock);
}
export async function revokeAll(db, clock = Date.now) {
  await db.batch([
    db.prepare("UPDATE owners SET auth_version=auth_version+1 WHERE id='owner'"),
    db.prepare('UPDATE sessions SET revoked_at=? WHERE revoked_at IS NULL').bind(Math.floor(clock() / 1000)),
  ]);
}
export async function replacePassword(db, verifier, clock = Date.now) {
  if (!verifier || verifier.algorithm !== 'PBKDF2-SHA256' || verifier.iterations !== PASSWORD_ITERATIONS || unhex(verifier.hash).length !== 32 || unhex(verifier.salt).length !== 16) throw new Error('Invalid verifier');
  await db.batch([
    db.prepare("UPDATE owners SET password_verifier_json=?,auth_version=auth_version+1 WHERE id='owner'").bind(JSON.stringify(verifier)),
    db.prepare('UPDATE sessions SET revoked_at=? WHERE revoked_at IS NULL').bind(Math.floor(clock() / 1000)),
  ]);
}
export async function allowLogin(db, ip, clock = Date.now) {
  const now = Math.floor(clock() / 1000), window = Math.floor(now / 900) * 900;
  // CF-Connecting-IP is platform-provided on Cloudflare. No client-supplied
  // X-Forwarded-For. Both limits count attempts BEFORE expensive password work.
  const buckets = [{ key: 'owner-global', limit: 25 }, { key: `ip:${await tokenHash(ip || 'unknown')}`, limit: 5 }];
  const rows = await db.batch(buckets.map(b => db.prepare(`INSERT INTO login_limits VALUES (?,?,1)
    ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN window_start=excluded.window_start THEN attempts+1 ELSE 1 END,
    window_start=excluded.window_start RETURNING attempts`).bind(b.key, window)));
  return rows.every((r, i) => r.results[0].attempts <= buckets[i].limit);
}
export const logoutCookie = `${COOKIE_NAME}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0`;
