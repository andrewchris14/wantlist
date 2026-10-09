# Phase 3C.1 — import readiness audit

**Recommendation: NO-GO for the full staging import at this checkpoint.**

The collection and local safety rehearsal reconcile. The current remote importer
cannot import the approved display model into edited staging. Cloudflare CPU
outliers persist, and actual maximum-size remote editing/billing have not been
verified in disposable Cloudflare resources. Complete those gates before import.
This report does not authorize or execute Phase 3C.2.

## Repository and scope

- Approved baseline and fetched `origin/work`: `9db0bfe7f414de7e1a8b569599e448c05575b546`.
- Repository: `andrewchris14/wantlist`; branch `work`; clean before audit.
- Phase 3B.5.3 current-Notes rendering, editor, classification/category defaults,
  category management, Pending, Bulk Edit, history and Undo remain present.
- Changes in this phase are audit tools, isolated test support, evidence and documentation.
  No public UI changes or deployment. Final audit commit is the commit containing this report.
- Human-review Worker remains `wantlist-staging`, with `STAGING_ONLY=true` and
  D1 `wantlist-staging`. Production still uses the separate static site/data;
  neither production nor protected Word/raw/Phase 2 files changed.

## Historical reconciliation

Independently rebuilding the derived view from the original Word archive and
protected Phase 2 data produces exactly the approved view. Its source ledger
covers all **3,392 unique normalized IDs**, represented as **3,394 display listings**.
There are no duplicate display IDs, unexplained missing source IDs, or new merges.

| Category | Listings | WANT | HAVE | COMPLETE | Literal item rows |
|---|---:|---:|---:|---:|---:|
| OBC Wantlist | 583 | 164 | 280 | 139 | 4,587 |
| UV Wantlist | 2,517 | 757 | 917 | 843 | 49,061 |
| Eau Claire Players | 3 | 3 | 0 | 0 | 112 |
| Milwaukee 8x10 List | 1 | 0 | 1 | 0 | 250 |
| Brewers Bobblehead Wantlist | 26 | 18 | 0 | 8 | 35 |
| Football Wantlist | 62 | 32 | 24 | 6 | 4,022 |
| Other Stuff | 202 | 26 | 166 | 10 | 1,031 |
| **Total** | **3,394** | **1,000** | **1,388** | **1,006** | **59,098** |

Literal rows comprise 56,769 card-number strings, 2,302 item strings and 27 literal
ranges. This is not the number of individual cards covered by ranges. Retained
source prose is also counted where the approved normalization stores it as a
literal; it is not automatically reinterpreted as an actionable identifier.

Eau Claire retains the actual three source headings: **Major League Players — 102**;
**Major League Managers — 3**; **EC Managers (but did not play for EC) with major
league experience — 7**. Milwaukee photos remain one HAVE inventory of 250 names.
The 26 Bobblehead year/event listings remain separate.

All seven decisions match: `p0060-l001`, `p0273-l029`, `p1996-l008`, `p2501-l001`,
`p2851-l007` COMPLETE; `p0273-l039` WANT; `p3022-l006` HAVE. All 16 distinct 1995
JSW listings remain separate; only `p1996-l008` is COMPLETE. The last approved
record's exact source literal is **“Complete? Have cards 1-96.”**; the rehearsal
preserves that text rather than substituting typographic characters or expanding
the range. Original uncertainty and availability qualifications remain in provenance.

There are **11 uncertain-year** and **178 unknown-year** listings. Literal labels
include `1990(?)`, `1972 (?)`, `1989 (ca.)`, and `1936?`. Numeric ordering places
1991 before `1990(?)` before `1989 (ca.)`; unknown years follow dated listings.
Ranges retain their literal text and the existing endpoint/year-filter behavior.

### Source anomalies requiring preservation or explicit review

- 16 source listings contain repeated identifiers within a group, with 18 excess
  occurrences. IDs and values are enumerated in [the audit evidence](../foundation/staging/phase3c1-audit.json).
  Nothing was deduplicated. Bulk Edit already rejects repeated input; owners must
  deliberately resolve these source repetitions before replacing such inventories.
- Three source pairs share an exact title: `p0185-l001`/`p0187-l001` (different
  COMPLETE/WANT meaning), `p1056-l005`/`p1058-l001`, and `p1056-l007`/`p1060-l007`
  (different wanted inventories). The Hometown Heroes pair has identical inventories
  at distinct Word references; it needs review, not an automatic merge.
- Normalized data contains 59,104 literals, six more than the approved Word-line
  display: photos 251 → 250 and Eau Claire 117 → 112. Those are the existing approved
  special-collection representations, not losses introduced by this audit. Full
  original records and the exact Word-line ledger remain in derived provenance.
- Historical prose, supplemental ownership, archived annotations and group notes
  remain internally recoverable. Public browsing renders only the current root
  Notes field. Import must not copy group annotations into that field.

## Existing staging inventory — read-only

The consistent snapshot contains **268 stored / 265 active records**, 369 groups,
5,639 item rows (**3,992 active**), 65 provenance rows, 2,239 history events and
2,200 mutation receipts. All seven category registry entries remain historical.

Active records comprise **62 approved derived IDs**, **one hidden legacy photo
source member**, and **202 owner-created practice listings**. Three removed roots
remain recoverable: the superseded Bobblehead container, superseded Eau Claire
container, and one owner-created listing. No duplicate database primary IDs exist.

The **86 fixture-title candidates** remain exactly the previously reported review
set. None has an active known `cpu-test-`, `cpu-first-`, `test-`, or `fixture-`
identifier. An unusual title alone is not deletion evidence. Candidate IDs/titles
are included in the audit JSON; all are preserved, including legitimate practice
sets. Do not delete the 202 owner records wholesale.

All **1,403 confirmed benchmark rows remain soft-removed**, with zero active
`cpu-test-` rows. `p1237-l004` is now revision **801** with original 2007/Upper Deck
metadata; later legitimate history is retained. Do not rerun the old revision-795
cleanup. Two current Pending entries in owner-created listings are preserved.

Nine matching historical records have revision >1: photo aggregate; `p0019-l001`,
`p0526-l006`, `p0531-l001`, `p0581-l001`, `p0645-l005`, `p1237-l004`, `p3029-l001`,
`p3117-l001`. Preserve all 62 existing matching records, not just those nine.
Raw `p0023-l001` remains `uncertain` while the authoritative effective type is HAVE;
that is intentional, not an import discrepancy.

**Cleanup recommendation:** no cleanup prerequisite is established by this audit.
Preserve existing practice listings and all candidates unless the owner approves
an ID-specific, history-backed cleanup manifest. Keep hidden legacy members and
removed containers archived; do not import them as new display roots.

## Importer findings and isolated rehearsals

The existing `quota_import.py` has durable daily reservations, checksummed chunks,
atomic payload/receipt transactions, lost-response checks and fail-closed guards.
However, it initializes the **3,392-record protected normalization**, requires an
empty/unedited database, does not emit the 3,394-listing derived model/current public
projections, and cannot reconcile live edits. Its execute CLI remains sample-only.
It is **not an approved Phase 3C.2 importer**.

A full local run of that actual legacy SQL engine completed in seven simulated
UTC days: 318 chunks, 471,733 conservative reserved writes, exact 59,104-literal
source reconciliation, and an idempotent retry with zero writes. Existing suites
also test failed atomic chunks and lost-response recovery. Partial record counts
alone are misleading: all record roots can exist before their item chunks finish.

New `import_rehearsal.py` is explicitly **local-only**, with no remote transport or
execution flag. It supplies a derived-data safety reference:

- Clean full rehearsal: **3,394 records, 3,461 groups, 59,098 literals**, exact rows
  and provenance hashes match; zero foreign-key errors.
- Staging-copy rehearsal: **3,332 missing listings** added, **62 existing matches**
  untouched, **3,600 stored records** afterwards. Every pre-existing application row
  compares exactly, including notes, category/type edits, Pending, ordering, deleted
  items, history, receipts, provenance, categories and private details.
- Expected visible result if approved: 3,394 historical + 202 active owner listings
  = **3,596 visible listings**. The remaining four stored roots are the hidden source
  member and three removed records. Actual item totals retain existing owner edits
  and therefore need not equal a pristine historical count.
- Per-listing transactions keep roots, groups, items, provenance and receipts
  together. Failed listings roll back; earlier committed listings and owner work
  survive. Retrying skips even soft-deleted existing IDs. Dataset drift stops replay.
- The Node Worker rehearsal publishes all 3,394 actual projections and verifies
  effective categories/types and current Notes. Photo, Eau Claire, Ritz and largest
  listing edits/Undo pass; history/provenance are retained. A 500-entry Pending save
  and Undo pass against the 526-entry largest inventory.

**Important boundary:** the local reference does not yet coordinate real D1
reservations, remote compare-and-swap guards, atomic public publication and remote
receipts. Those must be implemented together and tested in isolated D1 before GO.
Do not port its simple SQLite insertion loop directly into human-review staging.

## Backup and recovery verification

A fresh consistent **18-table private backup** includes application metadata,
categories, listings, groups, active/removed items, provenance, private details,
history, receipts, import state, auth generation, hashed sessions and rate limits.
Two complete reads matched. A new in-memory SQLite restore matched **every row**
and passed foreign-key checks. Session hashes stay in the private 0600 file; none
are committed or displayed. PIN/Worker secret values were neither read nor changed.

[Backup manifest](../foundation/staging/phase3c1-complete-backup.json) records the
private location and checksum; backup SHA-256 is
`bc31e4c4b02db9df9ff192bb84cbde9430a9e946489101d9fae182bae2b85e27`.
The overlay's complete application backup also restored exactly, including the
new rehearsal receipt table. Remote staging was not restored, reset or replaced.

**Durability caveat:** these fresh backups currently reside in this execution
workspace. Copy a verified encrypted backup to the owner's durable private recovery
storage before the real import. Do not place backup contents in the public GitHub
repository. Existing Worker secrets remain in Cloudflare; preserve their bindings.
Native D1 backup/Time Travel restoration was **not tested**.

For recovery, the operator first restores into a new isolated database and compares
it with the backup. For a failed import batch, inspect its receipt before retrying;
do not infer failure from a timeout. For rollback, pause import, then identify only
new IDs bearing that import's receipt. Preserve any listing with subsequent owner
edits. An approved revision-checked soft-archive operation may remove unchanged
import-created listings from public projections while preserving rows/history.
Never wholesale-restore over newer owner edits or replace live auth/session tables.

## Cloudflare Free budget and performance

Official documentation checked October 9, 2026:
[Workers limits](https://developers.cloudflare.com/workers/platform/limits/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/).

| Relevant Free constraint | Audit result / safeguard |
|---|---|
| Worker CPU 10 ms/request; memory 128 MB | CPU risk remains; isolate maximum edits, public paging, auth and Undo before import. |
| Worker requests 100,000/day; 50 subrequests/request | Imports should use an operator/D1 transport, not public Worker initialization. Current edit batches are bounded. |
| D1 reads 5,000,000/day; writes 100,000/day | Account-wide allowance; read/write and index maintenance count. Reserve import budget durably and retain failed-attempt reservations. |
| D1 500 MB/database, 5 GB/account; 10 databases | Current staging 9,154,560 bytes. Pristine full local DB with projections and test history ~34.43 MiB; not a remote storage guarantee. Check account storage/database count before provisioning tests. |
| SQL 100 KB; 100 bound parameters; row/value 2 MB; query 30 s | Use static SQL with bound JSON, never expanded SQL literals or giant full-import transactions. Largest rehearsal listing payload ~125,452 bytes. |

Conservative missing-data estimate: **682,717 reserved writes**, including index
allowances, public projection and receipt rows, plus 64 overhead writes per listing.
Whole pristine collection: 695,723. Proposed import budget **60,000/day**, leaving
40,000 for ordinary use/other databases; estimate **12 UTC days**, allowing extra days
for retries and per-listing budget fragmentation. These are conservative planning
figures, **not measured D1 billing**. Reduce the budget when account-wide usage rises.
Never enable paid features to bypass a limit.

Read-only account analytics through 14:20 UTC show 369,767 rows read, 3,141 written
and 332 sampled staging Worker requests. There were zero reported Worker errors,
but **13 sampled groups had CPU p99 >10 ms**, maximum **20.484 ms**. Group aggregates
do not identify the exact route or imply every request exceeded the limit. The
earlier 10.781-ms replacement outlier is not resolved by these observations.

Local diagnostics: a 500-entry Pending save used ~414 ms wall / ~412 ms Node process
CPU including local SQLite execution; Undo ~8.5 ms wall. Those timings include work
that remote D1 performs outside Worker CPU and **cannot be compared directly to the
10-ms Worker allowance**. Preserve transactional correctness. If isolated remote
testing exceeds CPU, reduce input/delta limits or improve measured JSON/SQL work,
then retest Save/retry/Undo; do not split one user Save into unsafe partial commits.

Public full collection projections total ~11.83 MB uncompressed. Current hydration
needs **68 sequential 50-record page requests** (about 72 for the staging overlay),
plus category/session/assets requests. Roughly 1,400 cold loads/day could approach
either request or D1 read allowances before other traffic. Local desktop/mobile
checks pass; real mobile cold-load latency, compression and cache effectiveness
remain unverified. Consider a compact cached browse/search index plus lazy detail
loading in a separately tested change; do not assume response headers provide a
verified shared edge cache. Backup/restore reads/writes also consume allowances.

## Tests and accessibility

- 71 website unit tests; 67 Node backend regressions; 48 existing Python foundation
  tests plus five new safety tests; 21 protected-source tests; 20 existing desktop/
  mobile browser tests; six full-collection desktop/mobile scenarios: **238 tests**.
- New full-collection checks exercise all seven category counts, searchable filters,
  keyboard year selection, Ritz current Notes, photo additions in the existing
  inventory, natural/original persistence, Eau Pending, the 526-entry editor and
  explicit non-truncating 500-entry Bulk Edit restriction.
- WCAG A/AA axe checks and desktop/mobile overflow checks pass for tested full-scale
  public/editor states. This is automated coverage, not a complete manual screen-reader audit.
- Existing browser tests confirm stale revision rejection, lost-response idempotency,
  owner authentication, explicit conversions, category moves, discard protection,
  sticky Save/Close and Undo. Guest staging owner-record request returned 401;
  public Ritz request returned 200. Automated writes stayed entirely local.
- No UI deployment; protected source hashes and production files remain unchanged.

Full-scale isolated evidence: [desktop filters](evidence/phase3c1/phase3c1-owner-desktop-filters.png),
[mobile filters](evidence/phase3c1/phase3c1-owner-mobile-filters.png),
[desktop editor](evidence/phase3c1/phase3c1-owner-desktop-editor.png),
[mobile editor](evidence/phase3c1/phase3c1-owner-mobile-editor.png).

Operator-only reproduction uses `python -m foundation.staging.import_rehearsal
--output work/NEW-REHEARSAL.sqlite` (requires a new file), the offline
`readiness_audit` / `readiness_budget` modules, and `owner/rehearsal.config.js`.
The browser config expects the prepared `work/phase3c1-full.sqlite`; its server
copies that file before each test and never opens a remote connection.
`readiness_snapshot` makes a fresh read-only staging backup and tests only a local
restore. Old benchmark and import execution commands are not part of this procedure.

## Exact operator plan for Phase 3C.2 — only after approval

The owner approves the record decisions and starts/stops the work through this
conversation. The operator handles technical steps; the owner does not run terminal
commands. Pause and provide a report whenever a guard fails.

1. **Resolve readiness gates first.** Implement the derived remote importer;
   verify it against an isolated Cloudflare database and Worker, with actual billing
   and CPU for maximum edits, Undo, auth and full paging. Existing remote benchmark
   provisioning is disabled; keep human-review write tests blocked. Reassess cold
   public loading. Retain duplicate sources unless the owner separately approves corrections.
2. **Confirm baseline and resources again.** Fetch `work`; check the approved dataset
   checksum, seven categories, 3,394 IDs, staging DB identity, Free plan and account-wide
   quotas. Generate a new reconciliation manifest showing existing, missing, removed
   and conflicting IDs. Current expected missing count is 3,332; do not assume it later.
3. **Take and secure backups.** Make two matching complete read-only snapshots,
   verify an exact isolated restore/FKs, save the checksum and staging Worker code/
   configuration, and place the backup in durable private recovery storage. Keep PIN
   and session bindings intact. If an owner edits during snapshotting, retry.
4. **Approve precise exceptions.** Present the 86 candidates, 16 repeated-identifier
   listings and three same-title pairs. Default is preservation; no cleanup is needed
   merely to import. Do not recreate removed containers or import hidden source aliases.
5. **Freeze the import manifest, not owner editing.** Stable dataset/source IDs and
   provenance hashes define new rows. Existing IDs are skipped unconditionally,
   including removed roots. Capture current revisions for reporting; never overwrite
   a record because it differs from baseline. A collision appearing after planning
   must atomically abort/skip that listing and appear in the reconciliation report.
6. **Run controlled batches.** At most 20 listings per operator batch, each listing
   committed atomically with groups/items/provenance/projection/receipt. Bind JSON
   under a proposed 256-KiB per-listing transport cap; reject oversize payloads rather
   than truncate. This transport/transaction cap is proposed and still needs remote
   validation. Start with a small isolated pilot before the approved human-review run.
7. **Enforce daily reservations.** Before each transaction, atomically reserve its
   conservative indexed-write bound in a durable UTC-day ledger. Maximum 60,000/day
   or a lower account-remaining budget. Stop before exceeding it. Compare actual D1
   metadata to the bound; stop immediately if exceeded. Retain reservations after
   failures or uncertain responses; do not refund guesses. Plan approximately 12 days.
8. **Resume safely.** Read checksummed receipts after every restart or timeout. Skip
   committed IDs without touching their subsequent owner edits. Retry only a proven
   uncommitted transaction against the same manifest; stop on checksum drift. Resume
   automatically on the next UTC day only within the explicitly approved import phase.
9. **Verify each batch.** Check created counts, source/provenance hash coverage,
   literal/group identities, FKs, projection revisions and categories/types. Compare
   pre-existing application rows/revisions; legitimate intervening owner edits must
   survive and be reported separately. Confirm no benchmark identifier reappears.
10. **Final reconciliation.** Check all 3,394 intended historical display IDs or
    separately approved omissions, plus every existing owner listing. New data must
    match the manifest exactly; existing edits must match live/history-backed state.
    Verify classifications, all special collections, current Notes, Pending, order,
    filters, read-only public access and representative large/small editor Saves/Undo.
11. **Recover when needed.** Pause on an error, inspect atomic receipts, verify the
    isolated backup restore, and retry only uncommitted work. For an approved rollback,
    soft-archive unchanged import-created IDs with revision guards/audit/projections;
    retain post-import owner-edited records for individual review. Never reset D1.
12. **Declare success and stop.** Require zero unexplained reconciliation differences,
    no changed pre-existing state attributable to import, no resurrected deleted test
    items, verified backup durability/recovery and demonstrated Free-plan compatibility.
    Provide the final counts and budget report for owner review. No production switch.

Evidence: [collection/staging audit](../foundation/staging/phase3c1-audit.json),
[local Worker diagnostics](../foundation/staging/phase3c1-local-worker.json),
[read-only Cloudflare analytics](../foundation/staging/phase3c1-cloudflare-readonly.json),
[write-budget estimate](../foundation/staging/phase3c1-budget.json),
[legacy full-import rehearsal](../foundation/staging/phase3c1-legacy-import-rehearsal.json).

**Nothing has been imported into human-review staging. No staging records were
deleted or changed, no sessions invalidated, no secrets changed, and no production
or historical source files modified. Stop for human review.**
