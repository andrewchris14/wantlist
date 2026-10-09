// Temporary disposable-only authentication adapter. Never deployed to staging.
// Invokes the unchanged login handler without retrieving/exposing its PIN.
import worker from './worker.mjs';
const minimalMethods=Object.freeze({'/public/index':'GET','/owner/record':'GET','/action':'POST','/test/free-review-login':'POST'});
const reviewEncoder=new TextEncoder();
export default {async fetch(request, env, context) {
  const requestURL=new URL(request.url);
  // Opt-in short lease for the future minimal review. This wrapper is never
  // deployed by local preparation. Protect every allowed route before D1 access;
  // expiry is a fallback SQL kill switch, not proof of endpoint disablement.
  if (env.MINIMAL_FREE_REVIEW === 'true') {
    const url = requestURL, until = Date.parse(env.MINIMAL_FREE_REVIEW_UNTIL || ''), now = Date.now();
    const forbidden = () => Response.json({error: 'Forbidden'}, {status: 403});
    if (env.ISOLATED_TEST_STORAGE !== 'true' || env.STAGING_ONLY !== 'true' || env.STAGING_EDITOR !== 'true' ||
        url.hostname !== 'wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev' ||
        !Number.isFinite(until) || until <= now || until - now > 15 * 60 * 1000 ||
        minimalMethods[url.pathname] !== request.method || !env.FREE_HTTP_REVIEW_KEY) return forbidden();
    const encode = value => reviewEncoder.encode(value);
    const actual = encode(request.headers.get('X-Free-Review-Key') || ''), expected = encode(env.FREE_HTTP_REVIEW_KEY);
    if (actual.length !== expected.length || !crypto.subtle.timingSafeEqual(actual, expected)) return forbidden();
  }
  if (requestURL.pathname !== '/test/free-review-login') {
    return worker.fetch(request, env, context);
  }
  const forbidden = () => Response.json({error: 'Forbidden'}, {status: 403});
  const url = requestURL;
  if (env.ISOLATED_TEST_STORAGE !== 'true' || env.STAGING_ONLY !== 'true' ||
      url.hostname !== 'wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev' ||
      request.method !== 'POST' || request.headers.get('Origin') !== url.origin ||
      !env.FREE_HTTP_REVIEW_KEY || !env.OWNER_PIN) return forbidden();
  const digest = value => crypto.subtle.digest('SHA-256', reviewEncoder.encode(value));
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
