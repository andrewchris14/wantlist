# Phase 3C.5 — output support and isolated Free review

October 9, 2026 (America/Chicago). Approved baseline:
`f133dc55c9ddf8caa6ecf8b98c07010ac7a02505`, branch `work`.

**NO-GO for permanent Cloudflare Free operation.** Actual Cloudflare CPU exceeded
10 ms on four operations. Account-wide daily D1 reads also exceeded the Free
allowance. No Paid activation, historical import, practice archival, human-review
staging modification or production deployment occurred. Backup delivery is paused.

## Downloadable-output support report

[OUTPUT_DIRECTORY_SUPPORT.md](OUTPUT_DIRECTORY_SUPPORT.md) records both affected
task paths, the exact second-task error, and the required output-mount/attachment
repair. No further backup-delivery attempts were made after the owner paused them.
No Drive connection, backup publication or alternative transfer was attempted.
Durable backup recovery remains incomplete.

## Isolation and method

- Worker: `wantlist-test-3c2-bc5991ba`.
- D1: `wantlist-test-3c2-bc5991ba`, UUID
  `7cf1e9a2-f0b7-4d6b-bded-f5a3315c028c`.
- Cloudflare API verified the sole D1 binding, matching disposable database name,
  `STAGING_ONLY=true`, `ISOLATED_TEST_STORAGE=true`, and editor mode. The D1 UUID
  differs from human-review staging. No disposable custom domains were found.
- Used supported per-command network permission, preserving the configured
  restricted proxy, host policy and TLS verification. Current runtime reported
  enforced policy and ready credentials. No network-policy bypass occurred.
- Billing subscription reads returned HTTP 403. `usage_model=standard` does not
  prove Free billing or an enforced 10 ms cap. Results below compare actual Worker
  CPU with the Free limit; successful responses do not establish Free enforcement.
- Retained local credentials did not authenticate to the disposable Worker.
  Its PIN/version were preserved. A temporary, isolated-host-only wrapper with
  a fresh strong secret invoked the unchanged login handler internally, returning
  its ordinary cookie without retrieving/exposing the PIN. Login CPU includes
  this wrapper's gate overhead; direct successful owner-entered PIN login was
  not measured. The wrapper and its temporary secret were removed afterward.

The disposable database initially had 244 records, including 242 visible records.
Added **3,152 clearly synthetic public read-model fixtures**, giving **3,394 visible
listings**, the seven approved category counts and **59,098 projected entries**.
No historical importer was invoked. Only the synthetic 526-entry editable fixture
has matching item/group storage; the other added inventories are public read-model
fixtures. This is a collection-scale HTTP surrogate, **not the actual complete
historical collection or a full-table D1 import**. Existing disposable records
were not edited. All mutations targeted that synthetic fixture.

## Actual Worker CPU and HTTP results

Serial test window: **12:37:17–12:39:35 PM America/Chicago**
(`2026-10-09T17:37:17.267Z`–`17:39:35.015Z`). Cloudflare
`workersInvocationsAdaptive` provided CPU in microseconds, converted to ms.
Only unambiguous single-invocation second buckets were joined to operations.
Raw requests and diagnostic requests are reported separately. These small samples
are not population p95/p99 estimates or a guarantee of future performance.

| Operation | Raw requests | Observed maximum CPU, ms | 10 ms comparison |
|---|---:|---:|---|
| Full index, seven HTTP pages | 7 | 9.220 | Below in observed samples |
| Public details across all seven categories | 7 | 3.019 | Below in observed samples |
| Login through temporary wrapper | 1 | 4.943 | Below; includes wrapper overhead |
| Remembered session | 1 | 2.577 | Below in observed sample |
| Open 526-entry owner record | 2 | **17.246** | **FAIL: one outlier** |
| Notes Save through normal edit-session route | 2 | **14.321** | **FAIL: one outlier** |
| Normal combined Save: notes + one addition | 2 | **10.679** | **FAIL: one outlier** |
| Pending Save | 2 | 7.639 | Below in observed samples |
| Cancel Pending | 2 | 3.934 | Below in observed samples |
| Maximum Save: 500 changes + 500 additions | 2 | **29.792** | **FAIL: both samples** |
| Large Undo of maximum Save | 2 | 3.901 | Below in observed samples |

Maximum Save CPU was **17.952 ms and 29.792 ms**. Both used 500 Pending changes
and 500 distinct additions with 500-character values in one transaction. Each
successful Save produced 1,026 active entries and 500 Pending entries. Replay
returned the existing receipt without increasing the revision; stale revisions
returned 409. Undo restored the exact original active IDs/states and soft-removed
the additions. Notes, Pending/public projection, cancel and ordinary Save/Undo
also succeeded, including diagnostic verification.

The index returned all 3,394 distinct visible IDs in exactly seven pages, with
category counts 583/2,517/3/1/26/62/202. The application's search, numeric-item
search, negative search, category, year and manufacturer adapters passed over
that remote index. Search and filters run in the client; there is no separate
Worker search/filter route or additional Worker CPU per filter operation. No
local timing was presented as Worker CPU.

The final serial suite made **72 HTTP requests: 45 raw and 27 diagnostic**.
All returned their expected statuses, including 401 and 409 negative cases.
Late analytics returned 71 invocations with **zero Worker errors**. One raw
ordinary-Undo invocation lacked an unambiguous CPU observation; no timing was
invented for it. No mutations were repeated just to fill that telemetry gap.

A separate read-only Chromium check used the actual deployed assets and Worker
responses through a loopback test relay and inherited HTTPS proxy. It stopped
during initial pagination: two index requests returned 200 and a later one
returned **404** while testing. Thus browser completion, category selection and
combined UI filters remain **UNVERIFIED**. Preliminary attempts also encountered
endpoint propagation/routing 404s. Do not equate the serial HTTP/model checks
with a completed browser test. Further testing stopped after the usage finding.

## D1 usage and budget limitation

| Diagnostic operation | Rows read | Rows written |
|---|---:|---:|
| Notes Save | 6,717 | 12 |
| Normal combined Save | 8,778 | 16 |
| Pending Save | 7,724 | 11 |
| Maximum combined Save | **2,430,969** | 2,512 |
| Large Undo | 9,130 | 1,012 |

Maximum Save's diagnostic aggregate D1 duration was 3,095.9292 ms; this is **not
Worker CPU**. One such request reported about 48.6% of the Free daily read
allowance. Diagnostic totals were **2,485,790 reads / 3,599 writes**. Uninstrumented
mutation usage must not be inferred as identical to those diagnostic figures.

Setup and direct verification used 106 D1 API queries, reporting **95,570 reads /
24,171 writes**. The original harness capped serial HTTP requests at 160, API
queries at 150, and setup/direct API usage at 750,000 reads / 50,000 writes.
**Those bounds did not adequately constrain total account-wide D1 reads**:
diagnostics were run after two raw maximum Saves, revealing the expensive route
too late to prevent those executions. This is a test-budget limitation.

At **12:46:54 PM America/Chicago**, account-wide Cloudflare D1 analytics reported
**6,551,633 reads / 52,754 writes** for the UTC quota day beginning
`2026-10-09T00:00:00Z`. This includes prior tasks and other account activity and
may lag ingestion; it is not all attributed to this task. It exceeds the Free
5-million-read daily allowance. No further Worker test requests or mutations
were made after this observation. Final disposable database size: 24,596,480 bytes.

The committed harness now profiles diagnostics before repeated raw mutations,
stops after an unexpectedly expensive diagnostic request (with isolated Undo
first), and refuses automatic reruns when review evidence already exists.
These safeguards were added after the recorded run; the evidence is unchanged.
Future tests need an account-wide quota-headroom check and conservative per-route
reservation before enabling mutations. Do not repeat this expensive suite as-is.

## Cleanup and remaining review

Cloudflare API verified the disposable endpoint **disabled**, including previews.
The original 13 deployed modules were restored exactly; binding names/types and
the D1 binding match the initial configuration. The temporary review secret is
absent. No owner PIN change or session invalidation was performed. Synthetic
fixtures remain only in the disposable database; no backup or authentication
values were committed.

Safe evidence: [HTTP/CPU](../foundation/staging/phase3c5-http-review.json),
[D1 usage](../foundation/staging/phase3c5-d1-usage.json),
[browser limitation](../foundation/staging/phase3c5-browser-review.json),
[cleanup](../foundation/staging/phase3c5-cleanup.json).

Owner review remains necessary for measured CPU failures, maximum Save's D1 read
cost, quota headroom, billing/cap confirmation, browser routing/full UI completion,
and eventual testing with the actual complete historical collection. Existing
importer rehearsals were not repeated. No historical execution, practice cleanup
or production cutover is authorized by these results. Backup delivery stays
paused pending support repair; durable Drive recovery remains incomplete.

## Resume after the usage-limit interruption

Before new work, reviewed the conversation, saved reports, private scratch logs,
repository status and recent commits. A supported network-permission Git fetch
confirmed remote `work` still at the approved baseline. The serial test suite,
CPU collection, D1 usage collection and remote cleanup had completed before the
interruption. The support report and this review were drafted but uncommitted.
The browser check was incomplete; no interrupted operation was assumed to pass.

At **1:13:34 PM America/Chicago** on October 9, reverified the disposable Worker,
sole D1 binding and isolation markers through the Cloudflare API. Its endpoint
and previews remained disabled, and the temporary review secret was absent.
Account-wide usage reported **6,552,133 reads / 52,754 writes** for the same UTC
quota day. Because reads still exceed the Free allowance, the endpoint was not
re-enabled and no completed tests were repeated. Remaining remote UI tests are
blocked pending quota headroom and routing diagnosis; successful direct PIN login
and actual complete historical-collection tests remain unverified.

Added narrow local tests for the temporary adapter's host/isolation/origin/secret
guards and ordinary remembered-session behavior. These are security validation,
not Worker CPU evidence. Syntax checks and the automatic-rerun refusal were
also verified locally. Existing remote results were preserved unchanged.

[Resume verification](../foundation/staging/phase3c5-resume-verification.json)
records the current binding/endpoint and usage observations. Safe documentation,
sanitized evidence and harness changes are prepared for commit to `work`. No
encrypted-backup delivery was retried. Stop for owner review.
