// Temporary disposable-only authentication adapter. Never deployed to staging.
// Invokes the unchanged login handler without retrieving/exposing its PIN.
import worker from './worker.mjs';
export default {async fetch(request, env, context) {
  if (new URL(request.url).pathname !== '/test/free-review-login') {
    return worker.fetch(request, env, context);
  }
  const forbidden = () => Response.json({error: 'Forbidden'}, {status: 403});
  const url = new URL(request.url);
  if (env.ISOLATED_TEST_STORAGE !== 'true' || env.STAGING_ONLY !== 'true' ||
      url.hostname !== 'wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev' ||
      request.method !== 'POST' || request.headers.get('Origin') !== url.origin ||
      !env.FREE_HTTP_REVIEW_KEY || !env.OWNER_PIN) return forbidden();
  const digest = value => crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  const [actual, expected] = await Promise.all([
    digest(request.headers.get('X-Free-Review-Key') || ''), digest(env.FREE_HTTP_REVIEW_KEY),
  ]);
  if (!crypto.subtle.timingSafeEqual(actual, expected)) return forbidden();
  url.pathname = '/login';
  const headers = new Headers(request.headers);
  headers.delete('X-Free-Review-Key');
  headers.delete('Content-Length');
  headers.set('Content-Type', 'application/json');
  return worker.fetch(new Request(url, {method: 'POST', headers,
    body: JSON.stringify({credential: env.OWNER_PIN, remembered: true})}), env, context);
}};
