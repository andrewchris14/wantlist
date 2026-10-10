# Minimal disposable Cloudflare Free verification — prepared, not authorized

Prepared October 9, 2026 (America/Chicago), after reviewing `89edc45`,
`e3342c2`, [Phase 3C.6](PHASE_3C6.md) and the retained Phase 3C.5 remote evidence.
Permanent hosting must remain **$0/month**. This document replaces the earlier
nine-call proposal for the **first** verification; Notes/normal Save and full
browser coverage remain separate later approvals.

## Current status and scope

October 10 update: the owner reports Workers Free **Active**, no card/Paid, and
D1 reads/writes reset to zero. Local live-adapter preparation is now complete;
see [adapter, release manifest, fault tests and exact authorization](MINIMAL_FREE_ADAPTER.md).
No remote execution is authorized. A fresh complete quota snapshot is still required.

### Historical October 9 quota block

The owner reports D1 reads **6.55 million / 5 million**, writes
**52,750 / 100,000**, databases **3 / 10**, storage **35.04 MB / 5 GB**.
These are owner dashboard observations, not a new API check. Reads are exhausted;
spare storage and database capacity do not create read headroom. No exact capture
time, current accounting-window evidence or Workers request/billing confirmation
was supplied. A rounded 6.55m read display is treated conservatively as an upper
bound of 6.56m in local admission tests, never rounded downward to admit work.

**No Cloudflare operation is authorized now**, including metadata requests,
analytics, SQL, endpoint enablement, migrations, deployment or cleanup calls.
Nothing was enabled during preparation. A reset or new usage message is not
permission to execute. The owner will provide updated usage and separately
approve the specific disposable-only work.

The offline policy module remains credential/network free. A connected adapter
now exists separately and is locally fault-tested: see
[MINIMAL_FREE_ADAPTER.md](MINIMAL_FREE_ADAPTER.md). This specification governs
its eight-request/six-measurement protocol. Do not substitute the broad
`free_http_review.py` harness, which seeds and queries outside this budget.

## Admission, before any data-plane call

Owner approval must cover control-plane verification, the specific disposable
release, any separately bounded performance migration, this six-call protocol
and rollback/shutdown. No Paid switch, new API token or new database is needed.
Use supported per-command network permission, inherited proxy/CA trust and TLS
verification. Do not probe Cloudflare now to test connectivity.

1. Obtain current **account-wide** daily usage upper bounds for D1 reads/writes,
   Workers requests, total storage and database count. Confirm both Workers Free
   and D1 Free in the owner's dashboard. `usage_model=standard`, a 10ms comparison,
   a D1 Free email or a successful response does not prove Workers Free billing.
   Do not change plan/CPU settings to obtain an observation. Previous subscription
   API requests returned 403; unknown billing is a stop, not a reason to retry them.
2. Capture observation time and the verified start/end of Cloudflare's current
   daily accounting window in UTC. Reject missing data, future timestamps, stale
   data over five minutes, a prior window, or less than 15 minutes before the
   window changes. Do not infer a reset from elapsed time or the local date.
   Round usage displays upward; ambiguous dashboard date ranges must be clarified.
   Confirm competing bulk D1 jobs are paused; normal website traffic still needs
   the outside-work margin below. Pause for updated account evidence if it becomes
   stale during the test. Never roll into a new day automatically.
3. Require **3,000,000 reads and 40,000 writes remaining after migration**, and
   at least 1,000 Workers requests remaining. If migration is pending, require
   **3,100,000 reads and 50,000 writes before it**, with its scan/write upper bounds
   confirmed separately. Stop if its 100,000-read/10,000-write reserve cannot be
   established. Database count must be 1–10; do not create another database.
   Reserve 20 MB growth under both the account's conservative 5 GB ceiling and
   the disposable database's conservative 500 MB Free ceiling. If total account
   storage is small, its upper bound also safely bounds the disposable file size.
4. After authorization and the quota gate, verify fresh metadata against exactly:
   Worker/database **`wantlist-test-3c2-bc5991ba`**; sole D1 binding **DB**;
   UUID **`7cf1e9a2-f0b7-4d6b-bded-f5a3315c028c`**. It must differ from human-review
   staging **`81f241d4-b17d-4cd4-802d-177f982cc5e1`**. Require `STAGING_ONLY`,
   `STAGING_EDITOR`, `ISOLATED_TEST_STORAGE` all `true`; no duplicate binding names,
   extra D1/service/KV/R2/queue bindings, custom domains or zone routes. Require
   workers.dev and previews disabled before preparation. Do not proceed on any
   identity/metadata mismatch, unexpected CPU override or stale verification.
5. Verify matching reviewed modules and performance schema, including the
   `history_item_reference` partial index, `items_group_value`, and the exact
   approved public-index triggers. Verify definitions/digests rather than merely
   index names or `CREATE TRIGGER IF NOT EXISTS`. Use only separately budgeted
   metadata SQL; never fetch full source/provenance/history blobs. If absent,
   pause for the specifically approved disposable-only performance migration,
   account its billed metadata and recheck account headroom afterward. There is
   no migration in this preparation or automatic migration in the guards.
6. Verify the existing synthetic record **`synthetic-3c5-1-0000`**, sole group
   **`synthetic-3c5-1-0000-group`**, synthetic creation marker, 526 original active
   actionable wanted items and the retained removed count (previously 1,503).
   Use targeted record/group/indexed-item checks, not whole-account table scans.
   A different baseline requires local reprofiling/review; do not reseed, delete
   retained entries, reset revisions or import the historical collection.

These conditions are deliberately stricter than “usage is below five million.”
No application guard can cap rows read **within** one executing D1 statement.
The 3m read requirement includes 2.5m emergency headroom for one unexpectedly
expensive canary, informed by the previous **2,430,969-read** maximum Save.
It does not authorize spending that reserve or repeating a bad request. Concurrent
account activity and delayed analytics still prevent an absolute quota guarantee.

## Budgets and stop conditions

| Work | Budget / rule |
| --- | --- |
| Measured Worker calls | Exactly six below; no load loop or automatic retry |
| Other Worker calls | One diagnostic index-readiness call and one diagnostic login: **8 total** |
| Control-plane / metadata work | 40 calls total, including SQL lookup/verification, release and analytics; reserve 10 additional control-plane calls exclusively for shutdown/restoration |
| Normal read envelope | 100,000 reads: 60,000 measurements/projections + 10,000 setup/verification + 30,000 rollback reserve |
| Normal write envelope | 20,000 writes: 15,000 measurements/projections + 5,000 setup/rollback reserve |
| Diagnostic measured costs | Stop after any call above **12,000 reads or 3,500 writes**; stop at cumulative **20,000 reads or 5,000 writes** |
| Raw cost allowance | Debit **twice** each corresponding diagnostic cost as a conservative projection; label it unmeasured, never billed data |
| CPU | Halt further benchmarks at **9ms** reported CPU (safety margin); **10ms/exceededCpu** is a Free-limit failure |
| Analytics | At most three polls per measured invocation, at most 30s between polls; no next benchmark while CPU is unknown/ambiguous |
| Time | 10-minute test lease; no lease renewal in the run; no request starts near expiry or after quota evidence expires |

The earlier maximum Save wrote **2,512** rows and its Undo **1,012**; a 2,000-write
per-call ceiling would reject that known workload. The chosen envelope includes
index/trigger writes and auth/verification work, not just 1,000 item edits.
Reserve outside-work headroom separately: 400,000 reads and 20,000 writes.
Migration, normal-work and emergency allowances are accounting reserves, not
promises that queries will stay within them. Record actual setup/rollback SQL
metadata, and stop if those separate envelopes are exceeded.

Stop immediately on unexpected HTTP status (including 404/401/409/429/5xx), Worker
errors, missing/invalid D1 metadata, ambiguous/missing CPU, any budget breach,
fixture/code mismatch, quota/billing uncertainty or unexpected outside traffic.
The acceptance ledger latches failures and preserves prior accepted samples.
Stop conditions prohibit further benchmarks; reserved synthetic rollback and
endpoint disablement remain necessary cleanup, subject to available quota.
Never attempt more SQL if the daily allowance is exhausted. Report pending Undo
and shut the endpoint down instead. No “retry until it passes,” silent diagnostic
fallback or session/PIN reset is allowed.

## Six measured invocations

Arm cleanup **before** any deployment/enable call. Preserve original disposable
modules and non-secret binding metadata privately; inherit existing owner secrets
without reading their values. The application release must include every imported
module and the rebuilt owner assets; do not deploy stale fallback editor assets.
Do not call human-review release/maintenance scripts.

For this test only, deploy the reviewed `free-review-wrapper.mjs` with
`MINIMAL_FREE_REVIEW=true`, a fixed ISO UTC `MINIMAL_FREE_REVIEW_UNTIL` ten minutes
in the future, `STAGING_METRICS=true`, and an ephemeral in-memory
`FREE_HTTP_REVIEW_KEY`. The minimal lease permits only the index, owner-record,
action and isolated-login paths/methods on the exact disposable host. Every call
also needs the temporary header key; unknown paths, wrong host/flags/key and
expired/malformed or overly long leases reject **before D1 access**. It cannot
be used as an import/maintenance endpoint. No dashboard/account credential goes
into the browser, request report or repository.

Before enabling, fetch disabled release metadata and run `verify_review_release`: require the exact wrapper main module and verified module digests, both minimal/metrics flags `true`, a secret-type temporary key binding, and a future lease no more than ten minutes away. A missing flag must not silently fall back to the legacy unleased wrapper.

Enable once. One diagnostic GET to **`/public/index?after=`** checks the actual
problem route, not `/health` or `/public/categories`. Check valid pagination schema
without recording contents. Fail/404 stops; do not cycle enablement. Then one
diagnostic POST to `/test/free-review-login` establishes an ordinary remembered
owner session via the existing isolated wrapper without changing/exposing the PIN
or revocation generation. Keep its cookie only in RAM; never output/commit it.

Every invocation is serial, occupies a distinct UTC second and has a recorded
start/end time and CF-Ray. Persist safe evidence before interpreting it. Wait for
unambiguous analytics before starting the next benchmark.

| Order | Invocation | Evidence / checks |
| --- | --- | --- |
| 1 | Diagnostic large owner open | Actual billed reads/writes including authentication; response bytes/hash, revision, active/removed counts; enforce diagnostic and CPU gates |
| 2 | Raw large owner open | `X-Staging-Metrics: off`; actual reported CPU; identical owner JSON hash/revision to call 1; no D1 billed-read claim |
| 3 | Diagnostic maximum Save | `maximum_payload()` builds exactly 500 Pending changes plus 500 distinct 500-character additions and Notes, from the verified synthetic record only; one revision increment; real billed reads/writes |
| 4 | Diagnostic large Undo | Resolve the one matching history ID with separately charged targeted metadata SQL; normal Undo/CAS; verify original active IDs/states/metadata restored |
| 5 | Raw maximum Save | Only if all prior gates passed; fresh request UUID and current revision; same 500+500 workload, instrumentation off; actual reported CPU |
| 6 | Raw large Undo | Normal inverse transaction; actual reported CPU; targeted verification of original active state, projections and metadata |

If a Save triggers a stop, its Undo is cleanup, not permission to continue calls
5–6. If a response is lost, assume the operation may have committed. Use the same
request UUID for a primary-key receipt lookup, then resolve the history/revision
and perform at most the permitted inverse. Do not blindly resubmit the Save or
use an older/newer revision. No receipt proof or a conflicting revision means
stop and report an unresolved disposable change. Cleanup never writes human-review
staging or production.

Undo preserves audit history, receipts and added entries as removed. Therefore
call 5 starts with **500 additional removed entries** compared with call 3, and
the final fixture retains 1,000 more removed entries. Record cohort sizes and
current revisions; do not call those snapshots identical or delete retained state
to manufacture matching timings. Compare restored original active items/metadata,
not the entire database byte-for-byte. If current sizes differ from the known
local fixtures, profile that size locally before interpreting remote results.

## Actual CPU and billed D1 evidence

Collect Cloudflare `workersInvocationsAdaptive` data, not wall time, local Node
CPU, D1 duration or a fabricated HTTP CPU header. Minute-align the retrieval
window as required by existing tooling, including the request's starting second;
filter all buckets throughout its start/end seconds, including intermediate
seconds. Require exactly one successful singleton bucket (`sum.requests=1`,
`sum.errors=0`) and no competing invocation in that interval. Convert reported
`cpuTimeP50` microseconds to milliseconds. Missing/sampled-out, aggregate or
ambiguous buckets are **incomplete**, not zero CPU. Preserve the sampling/quantile
qualification: this is Cloudflare-reported CPU for the singleton observation,
not a sustained-load maximum. Never reuse a bucket for two calls.

Read billed costs only from complete D1 metadata. New diagnostics explicitly set
`X-Staging-D1-Complete`; absent metadata, malformed values or an execution failure
produce **`unknown`**, rather than silently adding zero. Require complete headers
and valid nonnegative integer counts. Diagnostic calls include wrapper/D1 metadata
collection overhead; raw calls bypass it. The short host/key/expiry guard still
runs on both, so raw CPU here is conservatively measured **with that small test
protection**, not claimed to be the exact unwrapped production-handler CPU.

Account-wide before/after usage is a cross-check, not a per-route attribution:
it includes raw calls, preflight, cleanup, migration and unrelated traffic and can
lag. Raw billed costs remain unmeasured projections unless independently resolved
from authorized D1 telemetry. If fresh account totals are unavailable, do not
claim the quota gate or complete cost reconciliation passed.

Chunking increased local owner query work **91,916 → 152,724 SQLite VM steps**,
about 66%, and result rows **1 → 66** for the 526-active/1,503-removed fixture.
It avoided one oversized result value and preserved all removed entries. D1 wire
response decoding and JSON string assembly are precisely why both diagnostic
owner reads and **raw** owner CPU are included first. The VM ratio is not a billed
D1-read multiplier or a Worker CPU prediction. Maximum Save query work remained
241,736 VM steps after the earlier 98.4% optimization; that is not proof of Free
compatibility. This canary tests neither a full historical D1 import nor a new
10,000-entry remote fixture. Scaling remains a separate review gate.

## Cleanup, including failures and interruptions

The protected scope always attempts shutdown after entering its verified action,
including enable timeouts, work exceptions, budget stops and graceful interrupts.
The prepared live adapter binds SIGINT/SIGTERM to graceful cancellation. Keep the
cleanup call reserve independent of exhausted work budgets. Disable workers.dev
and previews; verify the control-plane state. Retry disable/verification at most
twice. **Confirm disabled before restoring normal modules**. Otherwise restoration
could remove the expiring guard while leaving the endpoint publicly enabled.
Remove the temporary key even if restoration fails; after confirmed shutdown,
restore original modules/bindings and verify no temporary key, wrapper, minimal
lease or metrics override remains. Test schema/index improvements and normal
Undo-retained history do not need destructive rollback.

A finally block guarantees an **attempt**, not a successful Cloudflare operation
under API failure, process kill or lost connectivity. The short lease separately
prevents further SQL after expiry; it does **not** disable workers.dev. If shutdown
cannot be confirmed, retain the expiring guarded modules, report cleanup incomplete
and request owner dashboard action to disable workers.dev and previews on exactly
this disposable Worker. Do not claim disabled because requests now return 403.
A hard-killed process cannot run finally; the prepared live adapter includes an
independent bounded cleanup supervisor/owner recovery instructions. No such
supervisor was installed remotely during this phase.

Safe report fields: commit/schema/module digests, disposable identifiers, verified
quota period and numeric bounds, actual costs and separately labeled projections,
HTTP status, bytes/hash, allowed response headers, exact public index URL/page
cursor, timing/analytics attribution, counters, fixed stop codes, synthetic cohort
counts and cleanup status. No response bodies, listings, history blobs, secrets,
keys, PIN, auth cookies/headers or arbitrary exception text enter public evidence.
An interrupted action remains incomplete until its receipt/state is checked.

## 404 diagnostics and readiness

The Worker route still returns 200 on valid pagination/end, 503 on caught SQL
failures; local 3,394-record/seven-page browser tests did not reproduce a 404.
The prior remote cause remains unresolved. Preserve exact URL/cursor, page number,
CF-Ray, Server, Content-Type, status, response size/hash and related Worker
analytics. Do not preserve HTML/JSON body contents or cookies. These fields help
distinguish route/availability/proxy failure from Worker/D1 errors; they do not
prove a cause alone. Do not change production routing on a hypothesis.

The initial one-page readiness check cannot prove the later-page issue is fixed.
A separate seven-page diagnostic HTTP walk, using the same atomic loader rules
and no reseeding, requires later approval and its own small budget. Avoid loading
the entire editor UI during this eight-request canary, since that adds uncounted
session/category/assets calls. Full category/search/filter correctness is already
covered locally; real index/detail CPU remains relevant to future browser testing.

## Ready versus still gated

**Ready locally:** protocol, fixed target identifiers, quota/resource admission
functions, synthetic maximum payload builder, strict measurement acceptance,
separate call/cleanup budgets, fail-latched samples, locally tested expiry/key
protection, missing-D1-cost handling and safe 404 evidence. Validation: 19 offline
policy/fault-injection tests, four expiry/login-wrapper tests, four D1-diagnostic
tests, two safe-evidence tests and all 15 foundation Node test files passed.
Completed importer rehearsals and successful full-browser tests were not repeated.
No updated Worker CPU or billed D1 measurements exist.

**Needs owner review and subsequent authorization:** this six-call canary, more
conservative reserves, ephemeral disposable release/lease and any performance
migration. **Still needed before execution:** fresh accounting/billing/request
usage, migration scan bounds, current disposable metadata/schema/fixture checks,
the prepared adapter release reviewed for authorization, and a separately bounded
account-wide final reconciliation. Adapter fault tests now exist; see the linked
October 10 preparation report. Approval
of a plan does not remove these execution prerequisites.

Additional work safe to pursue locally:

- Benchmark the actual Worker response path with JSON-encoded/decoded synthetic
  D1 replies, auth and Response construction; the existing predecoded benchmark
  excludes that cost. Interleave before/after runs to reduce GC/scheduling bias.
- Explore removing redundant chunk-query sorts/materialization and string copies,
  preserving one consistent read, exact ordering, typed metadata and all removed
  state. Re-run query budgets and response equivalence before accepting a change.
- Add byte-bound stress cases for large Unicode inventory values and unusually
  large notes/group metadata; item-count chunking is not a universal byte guarantee.
- Extend local rollback/response-loss fault tests to transport checkpoints, verify
  no automatic maximum Save retries, and cover sparse/mixed-group inventories.
- Reuse the full public manifest browser fixture for 404 on the final page,
  malformed JSON and special-character cursors. No historical D1 import is needed.

Passing one sample per route permits only review of a separately bounded next
sample; it does not establish reliable $0 hosting. Notes, normal Save, full-browser
404 investigation, historical-size scaling and concurrency remain additional
verification scope. Destructive changes, archival and historical import still
require a verified recoverable backup outside Cloudflare and their own approval.
No backup transfer or storage implementation was prepared here.
