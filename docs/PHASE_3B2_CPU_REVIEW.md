# Phase 3B.2 CPU investigation and quota-aware importer

Staging only. **Closure update, 2026-10-07:** the owner explicitly accepted the **11.656 ms** first-edit-after-redeployment observation as a documented Workers Free limitation rather than a blocker. Ordinary repeated edits have useful margin; successful responses do not prove every request fits 10 ms. No checks were weakened. See the definitive [Phase 3B.2 closure checkpoint](PHASE_3B2_CLOSURE.md). No editor or production cutover is authorized.

## Measurement and attribution

Cloudflare `workersInvocationsAdaptive` provides CPU and Worker wall time in microseconds. We convert to milliseconds. Analytics are sampled: the final 260 raw requests have 252 one-request observations; the three separate diagnostic executions per operation supply actual D1 row counters and SQL duration. Missing observations remain missing. P95/P99 below are empirical nearest-rank percentiles of the available observations, not precise population tail estimates. All raw and diagnostic requests succeeded. Reports preserve timestamps so coverage can be audited.

The final large record began with 1400 staged items. Its original approved baseline contains 526 literals. The final target was literal 704 at interior actionable index 347; literal 347 is absent in that set. This deliberately exercises interior JSON-path lookup. Synthetic additions are staging-only.

CPU is distinct from D1 SQL time (`meta.duration`) and client wall time (network/TLS/proxy/waiting included). The final diagnostic SQL durations range approximately 4–45 ms, while Worker CPU stays much lower in warmed requests. `performance.now()` is not used to claim Worker CPU. Tail/profiling access is unavailable, so no fabricated per-function CPU breakdown is provided.

Evidence and concrete costs:

- Disabling the D1 instrumentation wrapper and caching the operator verifier did **not** solve the problem alone: the ten-request control still observed 12.478, 15.158 and 11.073 ms. Diagnostics are a contributor/avoidable overhead, not a proven sole cause.
- Old additions/removal/restore opened every group/item, cloned inventories, generated a whole-record projection, and sent it back. A local structural profile of the exact 526-literal baseline found **134,102 bytes** returned for add-one, versus **219 bytes** after optimization; bound JSON falls from **102,603 to 1,472 bytes**. Those byte counts are local structural measurements, not Cloudflare CPU timings.
- Notes previously parsed/stringified historical `content_json`, including unrelated source inventories. It now extracts only changed old fields and patches metadata in SQLite. Returned structural bytes fall from 6,874 to 182.
- Session checks, import/idempotency controls and one targeted record/item lookup now use one read-only D1 batch. Authorization predicates, expiration/revocation, hashing and origin checks remain intact. Normal transitions/header/create use two binding round trips including commit, versus six/six/four previously. Add/remove/restore use three versus seven.
- Add/create consolidate inserts to at most 96 bindings/statement, below D1’s 100 limit. Add requests remain bounded at 20 values. Input validation, whitespace normalization, duplicate probes, audit JSON and hashing operate only on requested changes. No historical lists are re-normalized.
- One-card transitions never load, diff, validate or stringify unrelated cards. D1 patches only their saved public entry and record revision. Entry positions and `projection_version: 2` support exact restore order; incompatible old projections fail closed until explicitly republished.
- Public JSON path lookup still iterates part of **one** saved record in SQLite. Restore sorts the affected group’s JSON inside D1; its virtual-table read count grows with group size. These are database reads, not Worker array processing or scans of the global items table. No full dataset snapshot is generated after edits.

Prior 10.446/15.586 ms invocations cannot be retrospectively attributed to an individual function. The control disproves “instrumentation only”; reduced binding round trips/serialization improve the observed ordinary path; first-action variability persists despite small constant-size inputs. Post-deployment is an observed condition, not proof that a particular isolate was cold.

## Final repeated actual-Worker results

Each operation: 20 raw executions, 20 successes, zero failures; plus 3 separate successful diagnostics. CPU statistics reflect available one-request analytics. Wall is client median. Reads/writes are diagnostic actuals, not invented counters for uninstrumented requests.

| Operation | CPU samples / runs | Median CPU ms | P95 ms | P99 ms | Max ms | Wall median ms | D1 reads | D1 writes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wanted → Pending | 20/20 | 2.349 | 5.243 | 5.743 | 5.743 | 138.6 | 359 | 9 |
| Pending → Owned/Received | 19/20 | 2.150 | 7.857 | 7.857 | 7.857 | 149.0 | 359 | 9 |
| Pending → Wanted | 19/20 | 2.446 | 6.709 | 6.709 | 6.709 | 144.3 | 359 | 9 |
| Add 1 card | 20/20 | 3.684 | 5.341 | 5.361 | 5.361 | 162.3 | 13 | 12 |
| Add 2 cards | 17/20 | 3.316 | 5.432 | 5.432 | 5.432 | 169.9 | 17 | 16 |
| Add 20 cards | 19/20 | 3.656 | 8.305 | 8.305 | 8.305 | 173.4 | 71 | 88 |
| Remove item | 20/20 | 3.362 | 5.298 | 5.952 | 5.952 | 170.3 | 362 | 9 |
| Restore item | 20/20 | 3.056 | 5.065 | 6.137 | 6.137 | 196.0 | 5661–5799 | 9 |
| Edit notes | 19/20 | 3.017 | 6.043 | 6.043 | 6.043 | 143.6 | 9 | 8 |
| Edit metadata | 20/20 | 2.879 | 4.466 | 6.494 | 6.494 | 129.3 | 9 | 8 |
| Create future set + 20 cards | 19/20 | 2.972 | 6.473 | 6.473 | 6.473 | 124.2 | 46 | 93 |

Maximum final ordinary observed CPU: **8.305 ms**. Two additional transition/setup types each ran 20 times and stayed below 10 ms too. This ordinary sample has useful margin, but it does not erase the accepted first-action limitation.

Five distinct staging redeployments, with health checks verifying distinct non-secret deployment markers, each performed one first observed card edit. CPU: **8.640, 11.656, 5.133, 5.923, 4.642 ms**; 5/5 succeeded. Median **5.923 ms**, empirical P95/P99/max **11.656 ms**; client wall median **190.374 ms**. D1 counters were not instrumented on these five requests. No claim of forcing a cold isolate. A universal below-10-ms guarantee is not established; the owner has accepted this administrative-event outlier.

## Security and correctness

Atomic D1 batches still commit revision checks, item/metadata changes, audit history, idempotency receipts and incremental public projection together. Stale saves, invalid transitions, duplicate values, duplicate retries and concurrent revision races are rejected/rolled back. Session lookup uses the same token hash, generation, credential version, expiration and revocation predicate. Read-only prefetch never authorizes a mutation; a valid session is required before `mutate` runs. Origin/CSRF and the extra staging operator gate remain.

Credential verification architecture is unchanged: server-only SHA-256 verifier/version secret, one owner, indefinite access-code validity, 90-day remembered and 8-hour short sessions. No password/account table or forced rotation. The extra operator verifier is cached server-side, never exposed. Diagnostic wrapping is opt-in (`X-Staging-Metrics: on` plus enabled staging binding); ordinary requests bypass it. The operator harness explicitly opts in when collecting D1 counters.

## Large saves

The tested normal create has 20 cards and fits warmed Free CPU. Foundation input limits reject oversized per-field lists rather than attempting an unbounded save. Very large new sets must eventually use a private draft job: upload bounded 20-item chunks with receipt/checksum tracking, keep the draft out of public reads, then commit records/groups/items/history/projection using bounded prepared SQL/`INSERT ... SELECT` inside one D1 transaction. The final Worker request must not rebuild or serialize the entire draft. A future UI would show one “Saving…” then “Saved,” and retain the draft for retry on failure. This is a proposed protocol, **not an implemented editor or tested owner bulk-save workflow**; it requires review before implementation. The native SQL import trigger below demonstrates the relevant atomic database-side bulk primitive.

## Resumable initial import

`python -m foundation.staging.quota_import` is plan-only by default. It currently reports **318 chunks**, **471,733 conservative reserved writes**, largest chunk **2,164**, and at least **6 UTC budget days** at 80,000/day. Actual full-import metering remains unmeasured; reservations deliberately count indexes twice and include control overhead. The earlier approximately 260,000 indexed-write estimate remains an estimate. Chunk packing may leave unused daily headroom.

Full remote execution is **disabled in the CLI pending separate approval**. `--execute --database-id <staging UUID> --budget <budget>` imports the representative 27-record sample only. The underlying resumable engine plans/handles the complete baseline. No full production/staging baseline import was executed.

- An atomic durable daily reservation precedes every data chunk; CHECK constraints prevent exceeding the configured project budget. UTC day comes from D1, not the client clock. Budget maximum is 80,000, reserving at least 20,000 of the account’s 100,000 Free allowance for other work. Operators must verify account-wide remaining quota/other databases and lower this project budget if needed; the ledger is not an account-wide billing meter.
- Completed chunk SHA/data/ledger commit atomically. Lost-response retries inspect the completion ledger instead of inserting twice. Unknown/failed attempts retain reservations conservatively. Partial imports cannot be edited or marked complete. Initialization refuses mismatched baselines, live edits, owner-created rows, modified revisions or deletions.
- SQL text-size limits exposed an actual failure in the first native API attempt. The preserved baseline header is approximately 744 KB; it must not be truncated. The solution sends bounded JSON as a **bound parameter** to one SQL insert and uses a fixed allowlisted staging trigger to apply rows, enforce constraints and record completion atomically. The HTTP D1 API—not Worker—performs the import, avoiding Free Worker CPU limits. The trigger discards transient payloads after success.
- Chunks are also byte bounded (60 KB target; exceptional lossless rows <=1 MB). All fixed table/column routing is generated from the approved foundation schema and committed in `import_payload.sql`. Progress prints each completed chunk.
- Real `wantlist-staging-import-budget` started with an artificially small 2,584-write test budget, stopped, and skipped completed chunks on retry. The failed SQL-text attempt’s 2,322 reservation was retained. We then explicitly raised only this test budget to 12,000 (not a Cloudflare plan/limit change) and resumed the sample. Final reservations **9,813**, actual successful chunk writes **4,087**, plus small reservation/completion control writes. The complete rerun skipped all **7 chunks**, with zero additional chunk/data writes.
- Exact real-D1 reconciliation: **27 records, 30 groups, 960 literals, 656 actionable items, 27/27 provenance**; WANT 11/HAVE 10/Complete 5/Uncertain 1; all 18 categories; no omissions/additions/duplicates/content or state differences. All reviewed Griffey/Flagship/HAVE/Complete/uncertain/oddball edge cases match. 304 opaque literals stay lossless rather than guessed into actionable cards.
- Local virtual-day tests demonstrate safe multi-day resume; actual next-day quota rollover was not waited for/tested. Local tests also cover rollback, lost response, idempotency, changed-data refusal, quoting and the budget cap. HAVE lists are never expanded into inferred missing cards.

## Regressions, resources and recovery

Passed: 21 Phase 2 checks; 39 Python + 27 Node foundation tests (66); 36 website tests; 16 desktop/mobile browser tests including production build. Changed staging/session and quota tests rerun after the final small diagnostic/progress changes. Real staging regression: **248 assertions**, including the 2027 lifecycle, 15 history actions, authorization/CSRF/session/throttle, atomic failure, idempotency/stale saves, public sanitization and portable JSON/CSV/SQL export/local restore. No tests were weakened.

Both `wantlist-staging` and `wantlist-staging-3b2-probe` workers.dev endpoints/previews are disabled again. Main staging DB: 96 records (27 historical plus fictional tests), 3,768 items, 916 history rows, 4,931,584 bytes. New quota-test DB: 27 historical records, 960 items, no edit history, 1,286,144 bytes. Neither database is production or operational truth. No paid features, payment details, custom domains or frontend deployments.

The blocked native export download host and untested Time Travel remain documented limitations; working portable JSON/CSV/SQL recovery is retained and rechecked. All `data/`, normalization `tools/` and public `site/` files remain byte-identical to the approved baseline; dataset SHA-256 is `38a7ee7ad07ede1ae744dbe91b819c1bb78a294c70ca30f933bc66604d44c98a`. The Word/raw source and independent backup archive are unchanged. The public React site still loads its committed static JSON and has no staging dependency.

Closure decision: the owner explicitly accepted the first-action CPU outlier; further optimization is not required to close Phase 3B.2. These results do not justify claiming every editing request reliably fits 10 ms. Large-draft save UX/data-layer work also remains separate. No Phase 3B.3 work was begun.

## Evidence and commands

Reports: `cpu-investigation-result.json`, `cpu-first-edit-result.json`, `cpu-structural-profile-result.json`, earlier control/optimization reports, `quota-import-result.json`, `quota-import-pause-result.json`, `cpu-regression-verification-result.json`, `cpu-resource-result.json`, `cpu-final-smoke-result.json` under `foundation/staging/`. No access codes, reusable session tokens or API secrets are included. Private exports/checkpoints stay ignored under `foundation/.local/`.

- `node foundation/staging/profile_local.mjs`: disposable local structural before/after comparison.
- `python -m foundation.staging.benchmark_cpu --rounds 20`: actual staging edits; requires deliberately enabled staging endpoint and checkpoint.
- `python -m foundation.staging.benchmark_cpu --collect`: retrieve sampled CPU analytics without edits.
- `python -m foundation.staging.benchmark_first_edit` / `--collect`: staging redeployment first-action tests.
- `python -m foundation.staging.quota_import`: safe plan-only full import; does not create resources or import remotely.
- `python tools/validate_wantlists.py`; `npm run test:foundation`; `npm test`; `npm run test:browser`.

The original historical local PBKDF2 prototype tests remain for regression history; it is not deployed or used by the approved staging authentication.

Final staging smoke also verifies new mixed-group ordering and preservation of meaningful sublists. Distinct non-secret deployment markers are required for readiness; an initial invalid-operation assertion immediately after upload failed before its status was captured. Version-confirmed rechecks correctly return 400 (unauthorized requests 401). A later public fixture read also returned an unexpected body before its status was captured; its database projection was valid and both raw/diagnostic rechecks returned 200 with the expected groups. These transient symptoms are not attributed to a specific cause. No partial data or false transaction result was found; these historical transient observations remain documented; the first-edit CPU outlier is now explicitly accepted. Phase 3B.3 still requires separate approval.
