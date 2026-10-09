# Phase 3C.6 — local Free-plan performance optimization

October 9, 2026. Branch `work`; baseline `1aa32e1`.

**Owner review required; Cloudflare Free compatibility remains unverified.**
This phase made no Cloudflare API calls, remote queries, load tests, mutations,
imports or deployments. Paid was not activated. Human-review staging, production,
practice records, authentication secrets and sessions were untouched. The previous
phase's disposable endpoint remains recorded as disabled; no new remote check was
made. Backup delivery remains paused. The completed output support report is
[OUTPUT_DIRECTORY_SUPPORT.md](OUTPUT_DIRECTORY_SUPPORT.md).

## Why maximum Save cost so much

The Phase 3C.5 diagnostic reported **2,430,969 billed D1 reads**, not just 1,000
edited entries. Before changing queries we replayed the actual baseline code on
synthetic local storage: 526 active entries, 1,503 removed 500-character entries
(the prior test's retained additions), plus 2,000 unrelated items. The maximum
normal combined request includes notes, one Pending change and one addition. The maximum
request changes 500 entries and adds 500 distinct 500-character values.

The specific causes, supported by SQL templates and EXPLAIN plans in
[evidence/phase3c6-local-performance.json](evidence/phase3c6-local-performance.json):

- Validation started from all stored items, then scanned `json_each(changes)` for
  each item. The 2,029 retained items therefore multiplied the 500-entry draft.
  Baseline validation alone executed **5,110,255 SQLite VM instructions**.
- The item UPDATE used repeated correlated `json_each(changes)` lookups for each
  SET expression: **3,443,782 instructions**. Several columns independently found
  the same draft entry.
- Addition INSERT recomputed `max(position)` over the group for every addition.
  The absent child index on `change_history.item_id` also made parent-key insert
  checks scan history. Combined INSERT cost: **5,144,529 instructions**.
- Duplicate validation joined existing inventory with the addition JSON rather
  than driving indexed value lookups from additions: **1,337,065 instructions**.
- Metadata and membership wrote the public projection separately, firing its
  browse-index trigger twice. That trigger repeatedly extracted the effective
  mode from the entire projection while iterating entries. Notes-only Save also
  rebuilt inventories even though membership did not change.

These identify the multiplying scans behind the remote result. SQLite VM counts
are a local algorithmic-work proxy, **not D1 billed rows**; they cannot reconcile
exactly to the remote total. Removed entries must remain recoverable and were not
purged to improve measurements.

## Changes and preserved behavior

Validation now drives primary-key lookups from draft JSON, with explicit join
order. Item UPDATE joins each draft once. Duplicate checks drive indexed
`items_group_value` lookups from scalar values. Addition JSON and group mappings
are built once; materialized CTEs compute positions once per group. The original
global addition ordinal and ordering are preserved, including removed positions.
A narrow partial `history_item_reference` index supports parent-key checks and
legacy individual-removal lookups.

Metadata and membership now publish in a single UPDATE. Header-only Save/Undo
preserve existing groups, and the browse-index trigger reuses search inventory
when groups and effective classification are unchanged. Missing indexes rebuild
instead. Classification approvals, mixed groups and special-section exclusions
remain in the generated SQL.

Owner opening now returns a lean JSON string from one consistent SQL read,
forwarded directly by the HTTP route. Previously 2,031 D1 result rows were decoded,
grouped into JavaScript objects, then serialized again; now one encoded-result
row is returned. Arrays are assembled from JSON-generated fragments to avoid
repeatedly parsing large nested arrays. This still returns all active and removed
entries and the same permitted metadata. Private source blobs remain excluded.

Authentication is unchanged. One D1 batch still contains the revision guard,
receipt, audit before-state, item changes, additions, record and public index.
Request hashes and replay/conflict behavior are unchanged. Undo restores original
item columns and metadata, retaining added items as removed with their history.
No interface, 500-change/500-addition limit or editing feature was reduced.

## Local measurements and regression checks

Same fixture and operation sequence, before and after; Python SQLite 3.53.1.
Counts include trigger and foreign-key work. Local Node CPU includes synchronous
SQLite execution and differs fundamentally from Worker CPU (remote D1 execution
is outside the Worker). Timings are single observations, not statistical claims.

| Operation | Baseline VM instructions | Optimized | Reduction |
|---|---:|---:|---:|
| Owner opening | 90,768 | 91,916 | 1.3% increase |
| Notes Save | 92,420 | 640 | 99.3% |
| Normal combined Save | 115,797 | 50,591 | 56.3% |
| 500 changes + 500 additions | 15,148,334 | 241,736 | 98.4% |
| Large Undo | 132,206 | 88,943 | 32.7% |

| Operation | Baseline local Node CPU ms | Optimized ms | SQL calls before → after |
|---|---:|---:|---:|
| Owner opening | 17.445 | 24.086 | 3 → 1 |
| Notes Save | 31.373 | 17.897 | 10 → 6 |
| Normal combined Save | 18.587 | 14.038 | 12 → 11 |
| 500 changes + 500 additions | 1,428.660 | 55.005 | 12 → 11 |
| Large Undo | 79.767 | 20.970 | 10 → 9 |

Maximum Save's bound SQL parameter strings/numbers fell from 972,528 to 734,496
bytes (24.5%). This is the sum across SQL calls, not the HTTP payload. A separate
200-iteration owner read-model check with predecoded D1 responses confirms equal
JSON content and isolates JavaScript grouping/serialization work; see evidence.
It excludes D1 execution, network, response decoding and HTTP construction.
Owner total local CPU did **not** improve in this snapshot; its intended Worker
benefit is fewer decoded result objects and no second inventory serialization.
Actual post-change Worker CPU has not been measured.

All 13 foundation Node test files pass. Seven new regression tests cover maximum
Save/replay/Undo and removed provenance; late-transaction rollback including both
projections; CAS races; notes/index reuse and repair; duplicate/Pending/501-entry
rejection; owner metadata types/escaping; seven-page 3,394-record local HTTP
pagination and unauthenticated denial; and mixed-group global addition positions.
Existing tests cover conversions, opaque
source states, category handling, auth, mixed groups and approved editing behavior.
No full historical import or importer rehearsal was performed.

Reproduce from repository root (all generated data stays in ignored `work/`):

```sh
mkdir -p work/phase3c6-baseline
git archive 1aa32e1 foundation/staging | tar -x -C work/phase3c6-baseline
node tools/profile_edit_queries.mjs baseline work/phase3c6-baseline
node tools/profile_edit_queries.mjs optimized
python tools/measure_sql_work.py baseline
python tools/measure_sql_work.py optimized
python tools/check_edit_query_cost.py
node tools/measure_owner_transport.mjs work/phase3c6-baseline
node --test foundation/tests/*.test.mjs
```

The cost checker enforces relative query-work budgets and maximum-request
parameter reduction. Evidence contains SQL templates and plans, no SQL parameter
values, database snapshots, credentials or private recovery materials.

## Maximum-size requests

Retain the approved maximum and one atomic HTTP Save. Internal SQL batching
removes the repeated work without introducing partial commits. Splitting a Save
into independent HTTP requests would create partial history, revision races and
inconsistent Undo. A future chunk-upload design would need private draft storage,
an idempotent final commit, revision validation, cleanup and recovery semantics;
it is not implemented. If one optimized maximum still exceeds 10 ms remotely,
review that design or an explicit owner-approved limit rather than silently
reducing functionality.

## Browser index 404, separately

The `/public/index` handler has no 404 branch: success returns 200; caught query
failures return 503. Its category-free cursor is independent of owner sessions.
Local full-collection pagination now passes seven pages, including the end.
The prior browser's two successful pages followed by 404 therefore suggest
endpoint availability/routing propagation or an intermediate response, especially
around repeated disposable endpoint toggling. This is a hypothesis, not a proven
cause; the retained evidence lacks the failing response's full URL, `CF-Ray`,
server/content-type headers and recognizable error code. Production was not
changed. Future evidence must capture those non-secret details and distinguish
Worker JSON errors from Cloudflare/proxy HTML. Probe this same index route after
one enable; a health-route success alone does not prove its readiness.

## Smallest future remote verification (not authorized or run here)

First confirm Free billing and account-wide daily quota headroom. Verify the
Worker name, sole D1 binding, database UUID, isolation flags and absence of custom
domains against the Phase 3C.5 disposable resources; stop on any mismatch. Use
only supported per-command network permission with existing proxy/TLS policy.
Review/apply `foundation/staging/phase3c6-performance.sql` **only to disposable
storage** alongside matching Worker code. It replaces existing triggers; merely
running `CREATE TRIGGER IF NOT EXISTS` would leave old behavior installed. The
migration creates an index and consumes quota; reserve for its existing-table
scan separately, and stop if that reserve/headroom cannot be established.
No existing schema or endpoint has been changed remotely by this phase.

For the smallest CPU retest, use the existing synthetic 526-active/1,503-removed
record; no new collection import or broad load sweep:

1. Enable once; check the actual index route once for readiness. Establish an
   owner session without changing the PIN or revoking sessions.
2. One raw owner-open, one raw Notes Save + Undo, one raw normal combined Save
   + Undo, and one raw maximum 500+500 Save + large Undo: **seven measured raw
   calls**. Join each serial invocation to actual Cloudflare CPU; do not use
   wrapped diagnostics as the raw CPU measurement.
3. One diagnostic maximum Save + diagnostic Undo records billed D1 reads/writes
   with existing tooling; do not repeat if any budget or CPU check fails. These
   are two additional measured calls, never owner/production storage mutations.
4. Disable in a finally/cleanup path even if blocked; verify disabled state,
   remove any temporary authentication wrapper/secret and restore normal modules.

Reserve at least 100,000 reads and 10,000 writes **after migration**, with an
operation budget of nine measured calls plus a separately counted setup/cleanup
cap. These are safety reserves, not predictions. Stop further benchmark work at
20,000 diagnostic reads or a 10 ms raw CPU breach; preserve necessary synthetic
cleanup and endpoint shutdown. Do not start while account-wide quota headroom is
unknown. One sample per route can falsify compatibility, not prove reliability;
a passing result would justify a separately approved small repeated sample.
A seven-page browser walk to diagnose the 404 is an optional separate read-only
check, not required for the initial four-route CPU retest.

Remaining owner decisions: review code and the disposable-only migration; confirm
quota headroom and Free billing before authorizing that retest. Historical import,
production deployment, practice archival and durable backup recovery remain gated
by the prior approvals and incomplete recovery work. $0/month reliable hosting
is still a goal, not an established outcome.
