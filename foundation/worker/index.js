import { allowLogin, createSession, logoutCookie, readCookie, revokeSession, validateSession, verifyPassword } from './auth.js';

const response = (body, status = 200, headers = {}) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...headers },
});
const sameOrigin = request => request.headers.get('origin') === new URL(request.url).origin;
async function limitedText(request) {
  if (!request.body) return null;
  const reader = request.body.getReader(), chunks = [];
  let total = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > 4096) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { return null; }
}

export default {
  async fetch(request, env) {
    // Fail closed outside disposable local tests. This is deliberately NOT a
    // deployment-ready authentication service while free-tier/KDF gates remain.
    const url = new URL(request.url);
    if (env?.FOUNDATION_MODE !== 'local-test' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
      return response({ error: 'Foundation is local-only; readiness approval required.' }, 503);
    }
    try {
      if (url.pathname === '/foundation/health' && request.method === 'GET') return response({ mode: 'local-foundation', production_data_source: 'unchanged' });
      if (request.method !== 'GET' && !sameOrigin(request)) return response({ error: 'Forbidden' }, 403);
      if (url.pathname === '/owner/login' && request.method === 'POST') {
        if (!await allowLogin(env.DB, request.headers.get('CF-Connecting-IP'))) return response({ error: 'Please wait before trying again.' }, 429, { 'Retry-After': '900' });
        if (!request.headers.get('content-type')?.startsWith('application/json')) return response({ error: 'Invalid request' }, 400);
        const text = await limitedText(request);
        if (text === null) return response({ error: 'Invalid request' }, 400);
        let body;
        try { body = JSON.parse(text); } catch { return response({ error: 'Invalid request' }, 400); }
        if (typeof body.password !== 'string' || typeof body.remembered !== 'boolean') return response({ error: 'Invalid request' }, 400);
        const owner = await env.DB.prepare("SELECT * FROM owners WHERE id='owner'").first();
        if (!owner || !await verifyPassword(body.password, JSON.parse(owner.password_verifier_json))) return response({ error: 'Could not log in.' }, 401);
        const session = await createSession(env.DB, owner, body.remembered);
        return response({ signed_in: true, remembered: body.remembered, expires_at: session.expires }, 200, { 'Set-Cookie': session.cookie });
      }
      if (url.pathname.startsWith('/owner/')) {
        const token = readCookie(request), session = await validateSession(env.DB, token);
        if (!session) return response({ error: 'Owner login required.' }, 401);
        if (url.pathname === '/owner/session' && request.method === 'GET') return response({ signed_in: true, remembered: Boolean(session.remembered), expires_at: session.expires_at });
        if (url.pathname === '/owner/logout' && request.method === 'POST') {
          await revokeSession(env.DB, token);
          return response({ signed_in: false }, 200, { 'Set-Cookie': logoutCookie });
        }
        // No editor, public-data route, or remotely writable data API in 3B.1.
        return response({ error: 'Not implemented in this phase.' }, 404);
      }
      return response({ error: 'Not found' }, 404);
    } catch {
      // Do not disclose SQL, verifier data, tokens, or request bodies.
      return response({ error: 'Service temporarily unavailable.' }, 503);
    }
  },
};
