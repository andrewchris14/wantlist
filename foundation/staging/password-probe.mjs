// Staging diagnostic only. No D1, owner account, editor or public data route.
import { passwordVerifier } from './auth.js';
export default {
  async fetch(request, env) {
    if (request.method !== 'POST' || request.headers.get('X-Staging-Probe') !== env.PROBE_KEY) {
      return new Response('Forbidden', { status: 403 });
    }
    let result;
    try {
      await passwordVerifier('disposable staging test passphrase');
      result = { supported: true, algorithm: 'PBKDF2-SHA256', iterations: 600000 };
    } catch (error) {
      result = { supported: false, algorithm: 'PBKDF2-SHA256', iterations: 600000,
        error_name: error.name, error_message: error.message };
    }
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  },
};
