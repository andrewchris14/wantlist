# Phase 3B.2 — actual staging verification, with an unresolved Free CPU gate

The current public site remains independent of this experiment. Its approved
Word/raw sources, normalization/corrections, `data/wantlists.json`, and static
loader were not changed. No editor, production deployment, custom domain, paid
plan, or Phase 3B.3 work was started.

## Outcome

The approved SHA-256 owner-secret verifier fits Workers Free in the measured
probe. Real D1 schema, representative import fidelity, atomic edits/history,
sessions, portable export/restore, and incremental publication were verified.
However, some actual targeted edits still exceeded the 10 ms Workers Free CPU
allowance. **Do not approve this backend for production or proceed to the editor
until that CPU issue is resolved and re-tested.** Both staging endpoints were
disabled at this checkpoint; the D1 database is retained for review.

## Resources and Free-plan evidence

- Staging Worker: `wantlist-staging` (new).
- Diagnostic Worker: `wantlist-staging-3b2-probe` (existing, updated for the probe).
- One D1 database: `wantlist-staging` (new).
- Neither Worker has a production route/custom domain. Both workers.dev endpoints
  and preview endpoints are disabled now.
- The owner manually verified Workers Free $0, 100,000 requests/day, 10 ms CPU;
  D1 Free 5 million reads/day, 100,000 writes/day, 5 GB total, 10 databases.
  No payment information was entered, no paid option was enabled.
- The restricted API token cannot independently inspect subscriptions/billing.
  Resource creation/query/secret behavior was directly verified, billing-plan
  identity relies on the user's dashboard verification.
- Official docs accessed during this phase confirm Free allowances, 500 MB per
  Free database, 7-day Time Travel, and Free-limit errors rather than paid overages.
  We did not deliberately exhaust a quota. Inactivity/long-term retention was not
  empirically tested and no contractual inactivity guarantee is claimed.

Sources: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/),
[Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/),
[Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/),
[CPU metrics caveat](https://developers.cloudflare.com/workers/observability/metrics-and-analytics/).

## Authentication

`foundation/staging/auth.js` implements the newly approved architecture, not the
historical local PBKDF2 prototype under `foundation/worker/`.

- `OWNER_AUTH_CONFIG` is a Worker secret containing a SHA-256 digest and credential
  version. No original owner access code or verifier is stored in D1.
- Provision ONLY a cryptographically generated code with at least 128 bits of
  entropy. The test codes used 256 random bits. Minimum text length is an input
  bound, **not** an entropy test; a weak human password must never be provisioned.
- The access code has **no expiration, password-age requirement, or forced
  rotation**. Dad reuses it after a session expires unless technical recovery
  intentionally changes it.
- Login uses native SHA-256 and `crypto.subtle.timingSafeEqual`.
- Actual correct/incorrect disposable-code probe: 30 checks passed. Cloudflare's
  probe window (31 requests including warm-up) reported CPU P50 0.711 ms and P99
  2.122 ms. Client wall time median 53.84 ms, range 34.52–189.41 ms. This was
  credential/session-crypto work without D1; actual D1 login was tested separately.
- Remembered sessions: 90 days (7,776,000 seconds), persistent host-only
  `__Host-` cookie with Secure/HttpOnly/SameSite=Strict. Regular sessions: absolute
  8 hours (28,800 seconds), browser-session cookie without Max-Age.
- D1 stores only token hashes, credential versions, revocation generations,
  lifetimes/timestamps, and revocation flags. `auth_control` supports revoke-all.
  There is no `owners`/password table in the final staging schema.
- Actual login, wrong code, global throttle, expiration, logout replay, individual
  revocation, revoke-all, and credential-version revocation were verified.
- Manual secret rotation was tested with disposable credentials; the old code and
  session were rejected and the new code worked after deployment propagation.
  No automatic rotation is implemented. Resetting access is a technical secret
  update/redeployment plus session revocation, never a public reset endpoint.
- The egress proxy changes source IPs. Global throttling was tested on Cloudflare;
  deterministic per-IP window behavior was covered locally.
- No credentials/session tokens enter reports or source. Local disposable access
  state is ignored under `foundation/.local/` with mode 0600.

The isolated backend additionally requires a server-only operator secret for all
staging routes. Public-projection test reads need no owner session but retain this
operator gate. **The diagnostic SQL batch endpoint is not a production API.**
Do not remove the gate and publish this diagnostic Worker as a production backend.

## Schema and import

The original foundation migrations were accepted on actual D1, followed by
`foundation/staging/schema.sql`, which removes the old empty local-prototype
owner/session tables and creates secret-version sessions, auth control, import
checkpoints, mutation receipts, and public record projections. Existing record,
group, item, source/provenance, uncertainty, soft-delete, and history constraints
remain intact. D1 batch transactions and CHECK rollback were verified.

Full historical baseline: 3,392 records. Actual D1 import: **27 representative
records**, 30 groups, 960 literal values, 656 actionable items. All 17 non-baseball
categories plus baseball, all four list types, mixed information, and the largest
526-value set were represented. Source list-type counts in the sample: WANT 11,
HAVE 10, Complete 5, Uncertain 1. Provenance coverage: 27/27.

Content reconciliation passed with no missing/extra records, duplicate IDs,
changed fields, missing groups/items, provenance errors, or state mismatches.
Griffey Blue wanted/Red owned and all three 2023–2025 Costco Flagship categories
were explicitly verified. HAVE complements were never inferred. Ten sample
records include 304 literal values that cannot safely be made actionable; those
are retained losslessly with limitations, not guessed.

The import used three transactional D1 batches. Actual import writes: **4,060**
(including indexes/ledger). A rerun skipped all three completed chunks and added
zero import writes. A partial import rejects owner edits. Rerunning initialization
once edits/history exist is refused. Chunk IDs/checksums/data commit together;
reconciliation must pass before `completed=1`.

The sample importer has a conservative 12,000-write budget and intentionally does
not enable a full-baseline import. Official D1 pricing counts INSERT imports and
index maintenance; no free import bypass is claimed. The prior full import
estimate (~260,000 indexed writes) remains plausible: plan at least three daily
allowances, with margin and persisted daily account usage, before a full import.
A full resumable, multi-day scheduler/account-wide quota ledger is **not** claimed
implemented by this representative-only tool.

## Actual query costs and publication

These are measured D1 metadata, not SQLite estimates. Reads include session checks
where applicable; indexed writes, receipts, history, and projections are included.

| Action | Rows read | Rows written |
| --- | ---: | ---: |
| Remembered login | 5 | 4 |
| Session validation | 2 | 0 |
| Open small set | 7 | 0 |
| Open 526-value set | 534 | 0 |
| Find card within known set (direct indexed query) | 4 | 0 |
| Pending / back to Wanted | 16 | 9 |
| Received | 17 | 9 |
| Large-set targeted state benchmark | 12 | 9 |
| Add two wanted cards | 42 | 16 |
| Add twenty wanted cards | 80 | 88 |
| Edit notes | 9 | 8 |
| Create 20 wanted + 2 owned cards | 52 | 104 |
| Recent Changes (20 entries) | 22 | 0 |
| Duplicate-save retry | 3 | 0 |
| Public record projection | 1 | 0 |

Set/public catalogs intentionally read the current record count once; they do
not scan the item table. The actual 32-record test catalog/page read 32 rows.
Actual EXPLAIN plans use record/session/public primary-key indexes, the groups
record/kind/position unique index, `items_group_value`, and `history_recent`.
Recent Changes traverses a bounded history index; that is not a full item scan.
No ordinary targeted operation scans the global ~56,000-item baseline.

Each successful mutation commits item/record change, history, retry receipt, and
**only that record's public projection** in one D1 transaction. Common card-state
changes patch the affected JSON entry within D1 instead of fetching/serializing
all items. Notes/status/deletion patch the projection header similarly. Stale
revisions and duplicate retries were verified, including concurrent saves (one
success, one conflict). Pending became visible through the test public endpoint
immediately after the save response. No full 66,000–75,000-row snapshot ran per edit.

Public design: fetch a revision catalog and keyset pages (50 public projections
per page), search/filter in the browser, refresh changed projections, use short
public cache lifetimes/ETags. No query per search keystroke. Initial complete
publication/export remains an occasional bounded operation. The existing dated,
revisioned public-only fallback reference remains unactivated; the actual public
site continues using its independent approved static snapshot.

### CPU blocker

Initial JavaScript large-set projection rebuilds exceeded Free CPU. Targeted D1
JSON patches reduced reads from 541 to 12 for the benchmarked item, while writes
remained 9. However, the final isolated ten-save benchmark still had nine available
per-invocation analytics groups; two showed **10.446 ms** and **15.586 ms** CPU
(median among observed groups 6.828 ms). All ten HTTP saves succeeded, with no
reported execution errors, but Cloudflare documents rollover CPU allowance.
Success therefore does **not** prove reliable operation within 10 ms.

These were staging requests with diagnostic/operator instrumentation. Its CPU
contribution has not been isolated. Further scoped performance investigation is
needed; this phase does not claim an impossible Cloudflare architecture, nor does
it approve a backend dependent on rollover or propose upgrading to paid Workers.
No additional remote edits were made after identifying this remaining gate.

## Lifecycle, recovery, and failures

- Actual fictional 2027 set: create, retrieve, add Wanted/Owned, Pending, Received,
  Pending back to Wanted, notes, Uncertain/unmark, item deletion/restoration,
  record soft-delete/restore, export, and 15 expected history actions passed.
  No Word provenance was fabricated. Complete/unmark was tested on an owned-only
  future set; Complete rejects existing Wanted/Pending items.
- D1 generated a native SQL export successfully. Its temporary signed URL was
  saved only in ignored private storage; the download host is blocked by the
  environment's network allowlist. Native SQL download/restore is not claimed.
- Actual D1 content was exported through parameterized API reads into private JSON,
  sanitized public JSON, CSV, and portable SQL. JSON and SQL restored into NEW
  disposable local SQLite with exact core-table equality and valid foreign keys.
  No second D1 restore database was created. Authentication material is excluded;
  recovery provisions new authentication and public projections.
- Private fixture details were retained in the private backup and excluded from
  public projections/exports. Private files were not committed.
- Unauthorized writes, bad origin, expired/revoked sessions, stale revision,
  invalid transitions, duplicate retry, partial import, and actual transactional
  constraint rollback were verified. Errors are generic; no save success precedes
  database confirmation. D1 service-unavailability was fault-injected locally,
  not deliberately caused on Cloudflare. Worker-unavailability was directly
  checked after endpoint disable (HTTP 404); the static site remains independent.
- Seven-day Time Travel is documented, not empirically restored. A Time Travel
  info API probe returned 404; no restore operation or recovery guarantee is claimed.
- Final staging database size: 1,658,880 bytes (~1.58 MiB), including test fixtures,
  history, indexes and projections. The full local baseline's ~22.7 MB remains a
  separate size estimate, not the size of a full actual D1 import.

## Regression checks and reproducibility

- Phase 2 validation: 21 passed.
- Foundation: 34 Python + 23 Node = 57 passed, including eight new staging tests.
- Website: 36 passed.
- Desktop/mobile browser: 16 passed. Its configured server runs the production
  build first; that build passed.
- Baseline sources/site/configuration checked byte-for-byte against approved
  commits; dataset hash remains
  `38a7ee7ad07ede1ae744dbe91b819c1bb78a294c70ca30f933bc66604d44c98a`.
- Existing backup archive retained. No public data loader was changed.

All new implementation and non-sensitive evidence are under `foundation/staging/`;
new local tests are `foundation/tests/staging.test.mjs`. The legacy Worker README
now points to the approved secret architecture. No dependencies were added.

Future browser integration must keep the login/API and public app on the same
origin (for example a static-assets Worker or a same-origin server proxy). The
current isolated Worker requires its own Origin; cross-site Pages-to-Worker
cookies are not a tested/supported production login arrangement. No hosting
cutover or routing configuration was added here.

Technical reproduction uses the existing Network secret/API account binding:
`python -m foundation.staging.provision --confirm-free-manually-verified` is
NEW-account/staging-only provisioning and refuses existing checkpoints/resources.
`runner.deploy_staging()` is an explicit operator deployment helper;
`python -m foundation.staging.import_baseline` imports only the sample;
`python -m foundation.staging.verify_staging` runs actual staging fixtures;
`python -m foundation.staging.manual_checks` intentionally rotates ONLY disposable
staging credentials; `python -m foundation.staging.benchmark_edits` measures edits.
Do not run these again without reviewing the CPU gate and staging-only settings.
Historical 600,000-iteration PBKDF2 probe evidence remains preserved from commit
`1722eb0`; it is not the current deployed authentication implementation.

## Subsequent CPU/import review

See [PHASE_3B2_CPU_REVIEW.md](PHASE_3B2_CPU_REVIEW.md) for the optimized repeated actual-Worker measurements, remaining first-action CPU outlier, and durable quota-aware native D1 import. This remains staging-only; no Phase 3B.3 or production cutover.
