import { verifyCredential, random, hash, REMEMBERED } from './auth.js';
export default {async fetch(request, env) {
  if (request.method !== 'POST' || request.headers.get('X-Staging-Probe') !== env.PROBE_KEY) return new Response('Forbidden', {status:403});
  const input = await request.json();
  const valid = await verifyCredential(input.credential, env);
  // Compute session work without persistence. D1 is intentionally not provisioned.
  if (valid) await hash(random());
  return Response.json({valid, session_crypto_completed: valid, remembered_seconds:REMEMBERED}, {headers:{'Cache-Control':'no-store'}});
}};
