# Minimal Free verification adapter — local preparation complete

Prepared October 10, 2026. **No Cloudflare operation was performed. Remote execution remains unapproved.** Hosting must remain $0/month.

The owner confirmed Workers Free **Active**, no credit card/Paid activation, and October 10 D1 reads/writes **0 / 5,000,000** and **0 / 100,000**. These are owner observations, not current API measurements or permission to run. Before execution, obtain a fresh account-wide snapshot (at most five minutes old), verified UTC daily window, Workers request usage, current storage/database usage, and confirmation that competing bulk jobs are paused. Do not invent a capture time from the date of the message.

This implements [the existing six-invocation protocol](MINIMAL_FREE_VERIFICATION.md), not another broad testing phase. It does not claim Free compatibility yet.

## Prepared locally

- `foundation/staging/minimal_free_runner.py`: explicit authorization, per-dispatch account headroom checks, persisted safe checkpoints, serial measurements, receipt-based recovery without Save/Undo replay, signal cancellation and an independent shutdown watchdog.
- `minimal_free_transport.py`: fixed disposable identities, method/path allowlists, inherited network proxy/TLS policy, no redirects, ten-second socket timeout, thirty-second response deadline with remaining-time socket adjustment, four-MB response cap, no automatic network retries except bounded shutdown attempts.
- `minimal_free_release.py`: local import-closure packaging, rebuilt owner assets, expected/legacy schema definitions and exact migration digest. No Cloudflare client or operations in the builder.
- `minimal_free_sql.py`: fixed verification SQL. Fixture inspection reads at most 2,030 inventory rows once; original-state verification uses item primary keys. Private synthetic responses remain in RAM and never enter reports.

Large-record opening includes the `89edc45` response chunking: the existing local owner-query evidence increased from 91,916 to 152,724 SQLite VM steps (+66%, 1 to 66 result rows). Those are **not billed D1 rows**. Both diagnostic and raw owner opens use this latest one-statement/chunked path; actual billed diagnostics and CPU must pass their gates before maximum Save. The setup envelope also includes the targeted baseline verification query.

The prepared release uses application source `3c881ddd7e33486ccccd6c56bcdba0c7ebf68163`, includes **14 modules / 651,549 source bytes**, and embeds rebuilt HTML, CSS and JavaScript with their exact referenced filenames. The module byte count is an offline size check, not a Cloudflare upload measurement. See [the committed digest manifest](evidence/minimal-free-release-manifest.json). Package SHA-256:

`35452fd6f7a98db0adc810555f9d594db013005e3392c04ab81fe66fdbfc4af0`

The package itself is generated in ignored `work/`, not committed. It contains application source/assets and schema SQL, **no database snapshot or recovery material**. Modules reachable from Worker imports are included even when the guarded test cannot invoke their maintenance routes. Maintenance capability bindings are prohibited.

Local validation: **47 Python tests** (28 adapter/SQL/transport tests plus 19 existing policy tests), and the existing wrapper and D1-diagnostic Node test files passed. Cases include interruptions before/after publication, Save/Undo response loss in both rounds, missing/ambiguous CPU, immediate excessive-read stops, missing cost metadata, stale quota, unknown schema, saturated scan bounds, failed migration, network error/timeout/oversized response, redirects, pagination, missing receipts, failed restore/key removal/shutdown, and watchdog parent death/expiry/stalled heartbeat. SQL tests use an in-memory synthetic 2,029-item database. Original metadata, groups, provenance, item state, removed counts and projection revisions/notes/membership are checked after Undo; JSON metadata comparison tolerates insignificant whitespace.

Importer rehearsals and completed full-browser tests were not repeated. No new actual Worker CPU or billed D1 values exist.

## Exact future remote authorization

Only Worker/D1 name `wantlist-test-3c2-bc5991ba`, D1 UUID `7cf1e9a2-f0b7-4d6b-bded-f5a3315c028c`. The human-review database, production and all other D1 UUIDs are excluded by the transport.

| Operation requiring separate approval | Bound and effect |
| --- | --- |
| Read settings, endpoint/previews, D1 metadata, custom domains and zone routes | Verify sole disposable DB binding, isolation flags, no production/public routing, disabled endpoint/previews, Free CPU configuration and storage. At most two accessible zones; pagination/incomplete inventories stop. |
| Read deployed modules | Capture previous source and nonsecret settings/bindings privately for restoration; secret bindings use `inherit`, never request or record PIN values. |
| Disposable schema/fixture SQL | Fixed `sqlite_master` names; saturating history count **1,001**; exact synthetic fixture with **526 active + 1,503 removed**, one group and matching projection revisions. A wrong/already-used fixture stops; it is never reset or reseeded. |
| Optional performance migration | Only exact `phase3c6-performance.sql`, SHA-256 `97fd78f0e9671c99066d52e2f2b6451f343b0219ca3e6351358432685e6f1c1d`. Separate explicit permission. Existing known base schema required; unknown definitions stop. History must be at most **1,000 rows**, bounding the index build. Replaces two browse triggers/adds the item-history index; no backfill or import. One attempt, then definition verification. Partial/ambiguous DDL stops without replay or a claim of success; no schema downgrade during cleanup. |
| Disposable release and temporary endpoint enablement | Upload precisely reviewed package, preserve compatibility/options and owner credential bindings. Verify downloaded modules and guarded configuration before one enable call. Ten-minute nonrenewable lease and RAM-only ephemeral review key. |
| Eight serial HTTP requests | Two readiness/login requests, then exactly six measured requests: diagnostic/raw owner open, diagnostic maximum Save/Undo, raw maximum Save/Undo. Saves include Notes, 500 Pending changes and 500 additions. No broad browsing, imports, replay tests or extra category calls. |
| CPU analytics | One singleton success bucket per invocation, errors zero; at most three polls, 15 seconds apart. Missing/aggregated/ambiguous CPU stops. Actual microseconds converted to ms; adaptive analytics are sampled evidence. Never substitute local CPU. |
| Exact-record recovery SQL and possibly one cleanup Undo | Targeted receipt/history and original-state reads. A committed Save may receive one inverse Undo within the remaining eight-request allowance. An ambiguous Undo gets receipt inspection, never another Undo. Missing receipts or unknown SQL costs require owner review. |
| Guaranteed **cleanup attempts**, including after cancellation | Two disable attempts with verification, restore prior modules/bindings/options **only after confirmed disabled**, remove temporary key, independently verify disabled/previews off plus restored modules/configuration. Watchdog uses only cleanup APIs, never SQL. Ten reserved cleanup calls. Failed control-plane shutdown cannot be guaranteed successful: retain lease guard, report incomplete, stop for immediate owner remediation. |

Normal control-plane/SQL/analytics budget: **40 calls**, cleanup budget **10 separate calls**, HTTP budget **8**. A straightforward successful run uses approximately 27 control calls, plus up to two zone-route calls and two migration/verification calls. Delayed analytics can exhaust the cap; stop rather than enlarge it.

## Quota and stop rules

- Admission reserve: **3.1 million reads / 50,000 writes / 1,000 Worker requests**, including optional migration. Also require 20 MB storage growth headroom and existing disposable database below the Free 500 MB limit with that margin. Keep the conservative migration reserve throughout the run.
- Normal test envelope: **100,000 reads / 20,000 writes** (measurement 60k/15k; setup 10k reads; rollback 30k reads; setup/rollback writes together at most 5k). Migration separately at most **100,000 reads / 10,000 writes**. The adapter uses stricter setup-write cap 1k and observed/projection checks.
- Diagnostic per request: stop above **12,000 reads or 3,500 writes**; measured diagnostic total above **20,000 reads or 5,000 writes**. Charge observed costs before proceeding to any further SQL.
- Stop at actual CPU **≥9 ms**, HTTP/Worker errors, unknown costs/results, incorrect bindings/revisions/schema/fixture, stale evidence, deadline/lease proximity, or unverified billing/quota. The Free CPU ceiling remains 10 ms.
- Reserve **2.5 million reads / 15,000 writes** for an ambiguous mutation, in addition to known usage/projections. Unknown SQL consumption prohibits further recovery SQL. A lost response cannot safely mean “nothing happened.”
- Raw requests do not expose actual billed D1 counts. Their two-times diagnostic projections are reserved at dispatch, even if later CPU analytics fail, and remain explicitly labeled estimates. Require a fresh **post-run account-wide dashboard/verified-analytics reconciliation**, covering raw requests, SQL, setup and migration, before declaring this canary successful. No automatic quota API or invented totals.
- An in-flight D1 statement cannot be canceled or capped by the client. The reserve includes the earlier 2,430,969-read failure; these safeguards are conservative stop mechanisms, not a guarantee against unrelated account activity or delayed billing.
- Fresh evidence expires after five minutes. If analytics delay takes longer, stop unless the owner supplies a new verified snapshot. No request starts within 35 seconds of lease expiry or in the last fifteen minutes of the daily accounting window.

A hard-killed parent can lose its RAM cookie and baseline. The independent watchdog can disable/restore the Worker but cannot safely invent an Undo. Its pending receipt identifiers remain privately checkpointed and require owner review. If both processes or their network access disappear, the Worker lease still rejects requests before D1; this does **not** prove the URL was disabled. Failed cleanup is a blocker.

Each maximum Save/Undo retains 500 new removed synthetic items and history/receipts. A successful run ends with **526 active / 2,503 removed**, four new record revisions, original items/metadata restored and projections consistent. Do not reset this fixture or repeat the canary automatically.

## Local-only commands and later execution gate

Rebuild without the importer-coupled `npm run build:owner` script:

```sh
node_modules/.bin/vite build --config owner/vite.config.js
python -m foundation.staging.minimal_free_release --output work/minimal-free-release.json
python -m unittest foundation.tests.test_minimal_free_adapter foundation.tests.test_minimal_free_plan
node --test foundation/tests/free-review-wrapper.test.mjs foundation/tests/d1-diagnostics.test.mjs
python -m foundation.staging.minimal_free_runner --help
```

These commands are offline. Do not run `--run` now. Templates are [authorization](evidence/minimal-free-authorization.template.json) and [quota](evidence/minimal-free-quota.template.json); authorization switches default **false**, unknown usage/times default null. The historical owner zero-usage report is intentionally not turned into fresh admission evidence.

Only after explicit approval, copy/review the templates into ignored `work/`, fill current verified bounds/timestamps and approved release hash, create a new session path, and execute the following **using the previously supported per-command network permission**, with the configured proxy/TLS/credentials retained. No policy bypass, credential printing, token creation or permission broadening:

```sh
python -m foundation.staging.minimal_free_runner --run \
  --authorization work/minimal-free-authorization.json \
  --quota work/minimal-free-quota.json \
  --release work/minimal-free-release.json \
  --session work/minimal-free-session-NEW
```

Reports/checkpoints remain private ignored files. Publish only reviewed sanitized counts, CPU measurements, response fingerprints and cleanup status. A successful command still leaves final account reconciliation incomplete until separately verified.

**Ready for review:** adapter, local fault coverage, release/asset digests and bounded SQL. **Still required:** the owner's authorization of the operations above, a fresh complete quota snapshot, then live identity/schema/fixture verification within the approved preflight. Billing confirmation is already supplied by the owner. No Paid, historical import, practice archival, staging/production changes or backup delivery belongs in this authorization.
