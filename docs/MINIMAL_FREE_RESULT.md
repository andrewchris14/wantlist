# Minimal disposable Free verification — stopped at readiness

Attempt October 10, 2026, approximately 02:56 UTC, using reviewed commit `f881076` and the exact approved release. **Compatibility remains unverified. No retry was performed.** Evidence: [sanitized attempt report](evidence/minimal-free-attempt-20261010.json).

## Admission and changes

Owner screenshots captured approximately October 9 at 9:55 P.M. CDT (October 10 **02:55 UTC**) showed Workers Free Active, D1 daily reads/writes zero, Workers **Requests today** zero, three databases and 35.04 MB storage. The October 1–10 request total was not used as today's usage. The owner confirmed no competing bulk jobs. Rounded storage was conservatively bounded upward. Evidence was within the five-minute gate when calls began.

Live checks confirmed the fixed Worker `wantlist-test-3c2-bc5991ba`, sole D1 binding `7cf1e9a2-f0b7-4d6b-bded-f5a3315c028c`, isolation flags, no custom domains/routes, endpoint/previews initially disabled, compatible original configuration, and disposable storage within its bound. The schema was recognized as the approved legacy schema needing the performance migration. The synthetic fixture matched **526 active / 1,503 removed**, one group, revision **25** and matching projection revisions. The history scan found **24 rows**, below the 1,000-row migration bound.

The exact authorized performance migration ran once and the resulting definitions matched the reviewed expected schema. The optimized 14-module release, rebuilt assets and expiring/key-protected configuration were uploaded and verified against the reviewed package before one endpoint enablement. Release package SHA-256: `35452fd6f7a98db0adc810555f9d594db013005e3392c04ab81fe66fdbfc4af0`.

## Failure and measurements

The first and only HTTP request, diagnostic `/public/index?after=`, ran **02:56:29.636–02:56:29.824 UTC** and returned **404**, `text/plain; charset=UTF-8`, 17 bytes, without D1 diagnostic headers. The adapter stopped with `HTTP_RESULT_UNKNOWN` before login or any of the six measurements. Response bodies were not retained. The safe fingerprint, CF-Ray and headers are in the evidence.

This establishes a readiness/routing failure, not a Free CPU failure. Immediate endpoint-enable propagation is a possible cause, as is hostname/routing or an intermediary response. A local application `/public/index` route exists in the verified release. Available evidence does not establish which layer returned the 404. Do not reinterpret the successful local route tests as remote success or add readiness retries without owner review.

| Evidence | Actual observed value |
| --- | --- |
| Setup/verification SQL | **4,212 rows read / 0 written** |
| Performance migration SQL | **150 rows read / 3 written** |
| Total reported API SQL costs | **4,362 rows read / 3 written** |
| HTTP D1 diagnostics | **Unavailable**, not zero |
| Actual Worker CPU | **Unmeasured** |
| Six measured requests | **0 attempted** |
| Login, maximum Save, Undo | **Not attempted** |
| Adapter call counts | **16 control / 1 HTTP / 7 cleanup** |

The six read-only admission calls from the preceding quota-blocked attempt were also retained in ignored local evidence. Including those, 22 normal control calls were used across both attempts, below the 40-call cap; cleanup remained within its separate ten-call reserve.

Subtracting only the observed SQL costs from the screenshot totals gives a provisional **4,995,638 reads / 99,997 writes** remaining. This is **not reconciled account-wide remaining quota**: the readiness request had unknown D1 cost and delayed billing/outside activity cannot be excluded. Final account-wide reconciliation is **incomplete**, not a full pass. Do not replace it with empty adaptive analytics.

## Verified cleanup and stopping point

Cleanup completed by approximately **02:56:31.866 UTC**, with independent checks confirming:

- Disposable endpoint and previews **disabled**.
- Original disposable Worker modules, nonsecret settings/options and owner credential bindings **restored**.
- Temporary review key and lease bindings **removed**.

No Save or Undo was dispatched and no owner login/session was created. No human-review staging, production, historical or practice records were changed. The approved disposable performance migration remains installed; cleanup intentionally does not downgrade schema. No Paid activation, import, archival or backup operation occurred.

Next essential action: review the 404 and determine its cause before authorizing another bounded readiness attempt. Fresh post-run dashboard usage is needed for account-wide reconciliation and again before future execution. Do not repeat migrations or successful preflight work without a concrete verification need, reset fixtures, or start broad load testing. Stop for owner review.
