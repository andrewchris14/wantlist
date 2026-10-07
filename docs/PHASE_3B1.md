# Phase 3B.1: isolated, reversible foundation

## Safety boundary

The approved baseline is `d452f58d9006a498db7a8c65827c645b8f817703`.
`data/wantlists.json` SHA-256 is
`38a7ee7ad07ede1ae744dbe91b819c1bb78a294c70ca30f933bc66604d44c98a`.

The existing website, Vite plugin, `/wantlists.json`, Word source, raw import,
normalizer, correction logic, baseline JSON and existing tests are unchanged.
D1 is NOT the production source of truth. No account, remote database,
deployment, paid subscription or real owner credential has been created.

This phase supplies a D1-compatible SQLite schema and **local reference tooling**.
Python SQLite and Node SQLite are not Cloudflare D1/workerd emulators. Passing
their tests does not certify remote D1 limits, SQL import behavior, or Worker
runtime compatibility. There is no Wrangler dependency or deploy configuration.
The Worker deliberately refuses non-loopback hosts and requires
`FOUNDATION_MODE=local-test`; removing that guard needs a later reviewed phase.

## Cloudflare free-tier readiness: blocked on verification

Official documentation requests on October 7, 2026 were blocked by the network
gateway: `Tunnel connection failed: 403 Forbidden`. No current numerical quota,
credit-card requirement, inactivity policy or automatic-overage behavior has
been verified. A $0 production-readiness claim would therefore be premature.

Before creating resources, the technical maintainer must verify the following
in current official terms AND the actual account settings. Record the date,
applicable plan and findings; stop if any conflicts with $0 normal operation.

1. **Workers**: select the Free plan, no paid subscription or usage billing;
   confirm account setup does not require a card, daily request quota and CPU
   budget, and whether excess use fails/throttles rather than bills. Do not
   rely on a budget alert as a hard billing cap.
2. **D1**: confirm inclusion on that free account, per-database/account storage,
   reads/writes, query/import limits, and the exact exhaustion/reset behavior;
   no paid storage/compute or automatically enabled paid features.
3. **Pages/static hosting**: confirm a free provider subdomain, no custom domain
   requirement, build/asset limits and no required paid hosting subscription.
4. **Inactivity/account retention**: confirm whether Workers, D1 or the account
   can pause, expire, or be deleted due to inactivity, and what reactivation and
   data recovery would require. Do not infer D1 behavior from another product.
5. **Exports/recovery**: verify native SQL export support, backup/recovery
   retention on Free, export limits, and whether recovery incurs charges.
6. **Account billing**: inspect active subscriptions, trials/add-ons and payment
   settings; do not enroll in Workers Paid or any automatic upgrade. If a card
   is required or the account cannot guarantee no automatic charges, stop.
7. **Independent backups**: verify the proposed private destination's free
   storage/API/automation terms separately. No automated backup service exists
   yet; local export tools alone are not an off-provider backup system.

Official references:
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://developers.cloudflare.com/d1/platform/limits/
- https://developers.cloudflare.com/d1/reference/time-travel/
- https://developers.cloudflare.com/pages/platform/limits/
- https://developers.cloudflare.com/workers/runtime-apis/web-crypto/

The disposable baseline database is approximately 22 MiB, with 59,104 literal
rows. Compare the measured size and expected traffic with VERIFIED limits;
there is not yet evidence to certify "dramatically below" all Free quotas.
A future public API should serve a precomputed sanitized snapshot, not execute
the local exporter’s per-record queries on every public visit. Client-side
search remains possible; no API request is needed for each keystroke.

## Schema

- `records`: original IDs, list type, lossless editable metadata JSON, revision,
  created/updated times and soft deletion. Year text/ranges, brand, set,
  category, notes, prefixes/suffixes and uncertainty remain intact.
  Future owner-created records can have no import association; they need no
  fabricated historical source reference and will have creation history.
- `record_groups`: primary, mixed and sublist relationships, their ordering,
  list types, labels, descriptions, notes and preserved extension fields.
- `items`: textual identifiers, literal names/ranges, original field/order,
  Wanted/Pending/Owned state when safely actionable, pending/received dates,
  limitations and soft deletion. No numerical coercion or checklist inference.
- `provenance`: exact historical record, source references and semantic hash.
- `import_batches`: baseline commit/hash and all dataset-level historical
  metadata, including source ledger, context, policy and corrections.
- `private_details`: separate owner-only future trade information.
- `change_history`: before/after snapshots, actor, action and timestamps.
- `owners`, `sessions`, `login_limits`: one-owner verification, hashed session
  tokens/version revocation and login attempt counters.

Foreign keys, valid statuses, nonempty literals, revisions and unique identities
are constrained. Pending requires a timestamp. SQL constraints do not replace
API validation/authorization. There is no remotely accessible mutation API.
The local transition reference checks owner authorization, expected revisions,
legal transitions and deletion, and writes history atomically. A received item
does not automatically declare the set Complete. Soft deletion/restoration
preserve items and provenance and append history.

## Copy/import and reconciliation

Run from the repository root; Python 3 and the existing pinned Node runtime are
sufficient. No new dependencies are needed.

```sh
mkdir -p foundation/.local
python -m foundation.cli init --db foundation/.local/baseline.sqlite --allow-local
python -m foundation.cli reconcile --db foundation/.local/baseline.sqlite --allow-local
npm run test:foundation
```

The CLI accepts only local `.sqlite` files, never remote D1. Initialization is
atomic locally and hash-pinned to the approved baseline. It refuses a nonempty,
different, edited or non-reconciling database. An exact untouched rerun is a
verified no-op. There is no destructive reset/overwrite flag.

Remote D1 initialization is intentionally deferred. It must use an isolated
staging database, account-approved bindings, an import lock/state marker,
bounded batches that meet verified D1 limits, and reconciliation before marking
the import usable. Local transaction success is not evidence that a full import
fits in one remote D1 request.

`foundation/baseline-reconciliation.json` records the exact content comparison:

- 3,392 baseline and reconstructed records.
- WANT 997; HAVE 1,366; Complete 1,001; Uncertain 28; no needs-review records.
- Categories match exactly, including baseball cards 2,879 and non-sport 62.
- 3,458 groups; 61 records with mixed groups/sublists.
- 59,104 literal rows; 56,772 safely actionable item rows.
- 3,392 provenance records and all top-level historical metadata preserved.
- No omitted/added records, groups or values; no introduced duplicate IDs;
  no content/state/provenance differences.
- Griffey WANT/HAVE, all three Flagship fixes, each unusual category,
  representative HAVE/Complete/Uncertain records pass. Full equality verifies
  every imported record, not just those examples.

**No records lose content.** 380 records contain 2,332 literal values that are
not automatically actionable individual items. This conservative importer
leaves ranges and most names/prose intact, with group ownership/want semantics
preserved. It does not claim every name is ambiguous: it intentionally avoids
guessing whether a historical phrase names one tradable item. The two explicitly
reviewed Griffey variants are safely materialized. Exact IDs/titles for all 380
are listed in the reconciliation report. A later owner-reviewed conversion can
make literal names/ranges actionable without rewriting the historical baseline.
These are migration limitations, NOT newly asserted Phase 2 data errors.

Reconciliation reconstructs data from live columns/groups/items, not from the
provenance copy. It separately verifies provenance, header/import identity,
every group's relationship, every item’s initial state and unique IDs.
It detects deliberate corruption even when the original mirror remains intact.

## Remember this computer / security gate

The isolated Worker supplies local login, session inspection and logout only.
There is no login UI, editor, Pending UI, public-data route or public reset route.

- Remembered: 90-day **absolute** expiry and persistent cookie Max-Age.
- Not remembered: 8-hour absolute server expiry; cookie has no Max-Age.
- Opaque random 256-bit token; only SHA-256 of that token is stored server-side.
- `__Host-` cookie, Secure, HttpOnly, SameSite=Strict, Path=/, no Domain.
- Exact Origin checks on non-GET requests; no credentialed CORS.
- Server validation on every protected request, including owner credential
  version and revocation. No indefinite automatic session extension.
- Closing a browser/restarting the computer does not revoke a remembered
  session. Clearing cookies/private browsing can remove it. Browser session
  restoration can retain a non-remembered cookie, but its 8-hour server limit
  still applies. On expiration Dad signs in again.
- Passwords/tokens are not put in browser storage or response JSON. No real
  credentials are provisioned; test passphrases are disposable test data.
- Login attempt counters precede expensive verification: provisional limits
  are 5/IP and 25 globally per 15-minute fixed window, with cooldown response.
  Evaluate denial-of-service risks, cleanup of stale buckets/expired sessions,
  trusted platform IP headers and additional Free abuse protection before use.

Password verification uses standard Web Crypto PBKDF2-SHA256, random salt and
600,000 iterations. It passes local Node tests, but **Cloudflare support and
free CPU feasibility are not established**. Cloudflare can have an iteration
ceiling and/or CPU limit that makes this incompatible. Benchmark a supported
maintained verifier on the actual runtime before provision/deploy; do NOT reduce
the work factor or write custom cryptography to fit a quota. If incompatible,
stop for an architecture review. This is a production-readiness blocker, not
a claim that local sessions are production-ready.

Technical recovery helpers can revoke one token, revoke all sessions, or replace
the password verifier while incrementing credential version and revoking prior
sessions. Their secure operator interface is a later task; no insecure public
reset route exists. Dad need only use the eventual website. A replacement
computer signs in normally; the technical maintainer can revoke the lost device.

## Export/restore and privacy

All exports below are written to ignored local storage, with owner-only file
permissions and exclusive creation (no accidental file overwrite).

```sh
python -m foundation.cli export-private --db foundation/.local/baseline.sqlite --allow-local --output foundation/.local/private.json
python -m foundation.cli export-public --db foundation/.local/baseline.sqlite --allow-local --output foundation/.local/public.json
python -m foundation.cli export-csv --db foundation/.local/baseline.sqlite --allow-local --output foundation/.local/items.csv
python -m foundation.cli export-records-csv --db foundation/.local/baseline.sqlite --allow-local --output foundation/.local/records.csv
python -m foundation.cli export-sql --db foundation/.local/baseline.sqlite --allow-local --output foundation/.local/private.sql
python -m foundation.cli restore --db foundation/.local/restored.sqlite --allow-local --input foundation/.local/private.json
python -m foundation.cli reconcile --db foundation/.local/restored.sqlite --allow-local
```

Full private JSON includes live content, provenance, private details and history.
It deliberately excludes credentials, session tokens/hashes and throttle state;
a restore requires fresh owner provisioning and old sessions remain invalid.
The SQL export follows the same rule and includes the schema. SQLite SQL
restore has foreign keys disabled while loading alphabetically ordered tables,
then enabled and checked; never run it against a live/existing database.
Native remote D1/SQL export commands must be verified later before use.

Public JSON is an allowlist export; it does not copy arbitrary private extension
fields, private details, provenance mirrors, audit history or auth data. Its new
versioned contract exposes actual entry states rather than rendering a received
card as wanted based on its historical group. It is NOT wired to Phase 3A.
Notes/labels in public fields are public by definition; future editor controls
must clearly separate them from the private details field.

Two CSV files cover records (including empty Complete records) and literal/item
rows with group relationships/current states. Formula-like spreadsheet cells are
escaped. CSV is a convenience, not the only lossless recovery format.
Tests restore both an untouched baseline and edited/private disposable data,
verify exports, refuse restores into nonempty databases, and test SQL round-trip.

There is not yet an automated off-provider backup job. Before enabling real
editing, approve a free private destination, schedule and retention; provision
its credentials outside Git/frontend and prove a separate-database restoration.
Never commit future private exports/trade data to this public repository.

## Future public fallback — prepared, inactive

`public_export` includes a revision and last-updated timestamp. The isolated
`chooseSnapshot` contract prefers valid live data, otherwise labels dated saved
data explicitly, or reports unavailable if neither is valid. No fallback is
enabled in the current website.

A later approved publication process must atomically publish the last successful
sanitized snapshot to static storage independently of D1 availability. A
first-time visitor must not depend only on their browser cache. Background
publication/retry and plain-language freshness notices are later work; never
show an old snapshot as if it were live.

## Validation and next gate

The foundation tests cover full migration fidelity, corruption detection,
initialization guards, constraints, item transitions/history, revision conflicts,
soft delete/restore, private/public separation, exports and restores, password
verification, sessions/expiry/revocation, login throttling, denied writes and
fallback selection. Existing Phase 2 and website suites are retained unchanged.

Verified results for this phase:

| Check | Result |
| --- | --- |
| Local storage/migration/recovery | 24 tests passed |
| Local authentication/Worker handler | 12 tests passed |
| Inactive fallback contract | 3 tests passed |
| Existing Phase 2 validation | 21 tests passed |
| Existing website unit/component tests | 36 tests passed |
| Existing desktop/mobile production browser checks | 16 tests passed |
| Production Vite build | Passed; existing public assets/data path unchanged |
| CLI full JSON export/new-database restore | Exact reconciliation passed |
| Protected repository files | All 24 source/data/site/config files checked byte-identical to baseline |

No tests were skipped or disabled. Cloudflare runtime, remote D1, actual
trusted-device browser persistence and external hosting remain untested; the
cookie/session contract is tested locally, with no Dad-facing login UI yet.

Before Phase 3B.2: approve this local result and the conservative literal-value
policy; verify all Free terms/account settings; resolve actual Worker password
verifier compatibility/CPU budget; approve isolated staging resources and backup
destination. Do not remove the Worker guard or change the public loader merely
because local tests passed. Production source switching requires a separate
explicit later approval.
