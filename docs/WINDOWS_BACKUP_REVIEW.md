# Owner-run Windows backup: technical review

October 9, 2026 (America/Chicago). Prepared on `work` after `e3342c2`.
**Code and synthetic local tests only. No real staging export, remote Cloudflare
operation, D1 query, deployment or backup transfer occurred.** GitHub was used
only to read the public API specification and push safe code/docs. The downloaded
Codex output directory was not retried. The $0/month recurring hosting requirement
and Free plan remain unchanged.

## Assessment and design

A browser-only HTML download cannot prove SQLite restoration and should not ask
for broad Cloudflare OAuth permissions. A native Cloudflare SQL export may block
D1 queries while it runs and normally introduces a plaintext download. Wrangler
adds CLI installation/login complexity. Neither is needed here.

The prepared alternative is a small, inspectable Python-standard-library
companion with a browser interface, under `tools/windows-backup/`. Windows needs
one free per-user Python 3.12+ installation and current Edge/Chrome; no Wrangler,
Node, third-party runtime packages, terminal commands, admin installation, paid
services, Cloudflare deployment or Google connection. This is **not zero-install**
if Python is absent. A signed standalone Windows executable would need a separate
build/security review and is not supplied or required.

Opening the `.pyw` launcher binds an ephemeral IPv4 loopback port and opens a
local page. Startup and recovery never access Cloudflare. Only the explicit
Create backup action can start the bounded remote read procedure, after owner
approval, Free/quota, quiescence and encrypted-PC confirmations. The user guide
explains exactly what to download, open and click. It is marked review-only.

## Minimum access, isolation and quota

The owner creates a separate expiring token, scoped to their one account, with
**D1 Read** and **Account Analytics Read** only. The latter is necessary for an
automatic account-wide quota check. No Global API Key, D1 Write, Worker editing,
billing or administrative scope is requested. The D1 token scope is account-wide;
the UI cannot claim it is limited to one database. The application is hard-coded
to `wantlist-staging`, UUID `81f241d4-b17d-4cd4-802d-177f982cc5e1`, and verifies the
API-reported name and UUID before SQL. It cannot accept arbitrary SQL, database
IDs, URLs or production restore requests.

The public [Cloudflare API schema](https://github.com/cloudflare/api-schemas/blob/main/openapi.json)
was inspected via GitHub, without contacting Cloudflare. It lists **D1 Read** and
**D1 Write** as accepted groups for `POST .../d1/database/{database_id}/query`,
and supports `{batch:[{sql:...}]}`. This is evidence for the minimum permission,
not proof that this account's future token will work. A 403 stops; the workflow
never upgrades permissions. The `export` endpoint description warns that the
DB can become unavailable during export, so that endpoint is not implemented.

Only three remote routes exist: the fixed staging database metadata GET,
account analytics GraphQL POST, and that staging database's SELECT-only query
POST. Tokens go only to `https://api.cloudflare.com`, with normal TLS validation;
redirects and arbitrary destinations are refused. No SDK/env credentials from
Codex are used. Tokens, SQL parameters, responses and errors are never logged or
saved. API errors expose only a safe status/message, not returned data.

Account analytics aggregates all databases over UTC midnight to now, with no
per-database filter or dimension. Missing/empty groups, errors, fractional or
missing counters, stale dashboard dates and a current D1-limit notice fail closed.
The higher of fresh owner-entered dashboard totals and analytics is used.
The owner must confirm all controlled D1 jobs/edits stopped for 30 minutes.

Limits remain 5,000,000 daily reads and 100,000 daily writes. The tool reserves
1,250,000 reads for its bounded workflow plus a 1,000,000 lag/activity margin.
Initial usage must therefore be at most 2,750,000 reads, with writes below their
limit. It rechecks analytics between full reads and conservatively adds its own
reported usage. Missing accounting, any reported write or read-budget overflow
stops. No automatic retry is implemented. This is not an atomic account quota
reservation: unrelated traffic or lag larger than the reserve remains a risk,
so a busy account cannot safely proceed just because one sample is low.

The snapshot result cap is 300,001 rows: reaching it rejects the entire backup,
never truncates and declares success. Discovery is bounded to 101 schema rows,
with the 101st rejected, and no more than 32 application tables/40 columns each.
SQL size is bounded below D1's 100 KB statement limit; API/snapshot memory size
is capped at 128 MiB. These bounds must be reviewed if future history/schema
outgrows them; they are not claims of measured D1 billing. Schema discovery and
column inspection are also counted. Local UNION queries scan each table once,
with a global LIMIT and no multiplying joins; two snapshots fit the conservative
read reservation structurally, but actual remote usage is not yet measured.

## Complete, consistent application snapshots

A preliminary schema/column read generates one single SELECT with UNION ALL
branches for application schema objects and every table. Each data row is
returned separately; the design avoids a giant JSON cell that could exceed D1's
per-value limits. This statement uses one SQLite read snapshot across all tables;
it does not rely on consistency across independent per-table API calls or on
undocumented batch transaction behavior. The two whole-database reads must match
canonically before encryption. Final schema must match discovery; concurrent
schema/data changes fail rather than becoming a successful backup.

All application tables are discovered dynamically, including future extra tables
within the reviewed limits. A minimum required set rejects incomplete/wrong
staging schemas. No filtering of removed data or authentication tables occurs.
The snapshot includes records, groups, items, Pending/removed fields, metadata,
provenance/private details, history, categories, import and mutation receipts,
public projections/index, hashed sessions, auth-control and login limits. It
cannot retrieve Worker secrets/configuration such as the PIN; these are not D1
rows and remain an owner-side deployment prerequisite for any real future recovery.

Table definitions, explicit indexes, triggers and views are retained. Cloudflare
managed `_cf_KV`/`_cf_METADATA`, their objects, automatic indexes and SQLite
statistics are excluded from the portable application snapshot; they are not
application records and are recreated/managed by their engines. `sqlite_sequence`
values are preserved when AUTOINCREMENT exists. Virtual tables are rejected for
separate review, never silently skipped.

The row encoding preserves SQLite value types, BLOB bytes, NULL, generated-column
values and 64-bit integers. It also preserves implicit rowids, so restoring does
not reorder categories or any other rowid-dependent behavior. WITHOUT ROWID
and AUTOINCREMENT tables are tested. Source row order is canonicalized only for
comparison; identifiers, item positions, implicit rowids and sequence counters
are restored exactly. The browser never parses/re-serializes plaintext records,
which would lose integers above JavaScript's exact-number range.

## Encryption, retention and recovery

The existing `wantlist-public-key.json` is selected on the owner's computer.
Private or unknown JWK fields and RSA sizes below 3072 bits are refused before any
remote request. The owner's retained 4096-bit public key needs no replacement.
The existing formats remain unchanged: `wantlist-encrypted-backup-v1` and
`wantlist-recovery-key-v1`, with PBKDF2-SHA256/600,000 for the protected recovery
key, fresh AES-256-GCM and nonce for each backup, RSA-OAEP-SHA256 key wrapping,
authenticated metadata and plaintext SHA-256. The protected private recovery key
and password are used only in the browser, never sent to the companion.

Pre-encryption restoration loads all data into a fresh `:memory:` SQLite database,
with foreign keys deferred until after loading and triggers installed afterward.
It verifies every row, value type, implicit rowid, column definition, sequence
and explicit schema object, then integrity and foreign keys. No file-backed DB,
plaintext temp export or plaintext download is created. Only ciphertext and
non-content receipts can be saved through browser buttons.

Recovery requires the **actual saved file** and its independently retained
ciphertext SHA-256 receipt. After local decryption/authentication and plaintext
checksum verification, plaintext bytes go only over protected loopback to the
companion for a second fresh in-memory restore. No token or Cloudflare operation
is needed. The report contains verification flags/table counts and checksum,
never rows, source blobs or authentication contents. The original legacy HTML
page still works as before and can download plaintext; instructions expressly
use the new tool for new memory-only recovery, not that old download button.
Older snapshot body formats are not silently converted by this tool.

A sandbox authorizer denies attached/file-backed databases, unsafe PRAGMAs,
virtual-table creation and file/extension functions before any backup-provided
SQL runs. SQLite extension loading is disabled; temporary storage is in memory.
One operation lock prevents simultaneous export/restoration. Loopback requests
require exact Host/Origin plus a random 256-bit capability in a custom header;
it is initially in the local URL fragment, then removed from browser history.
There is no CORS access, arbitrary file serving or generic SQL endpoint.
CSP blocks external browser requests/scripts and framing. Tokens/password fields
clear on completion/error; explicit Close clears UI and ends the companion.
An idle companion expires after 15 minutes.

Limits: the browser/Python/Windows can retain RAM copies or page/dump memory.
An encrypted private PC is required; no instantaneous memory-erasure claim is
made. This tool cannot defend against compromised software or administrator
access. AES-GCM authenticates encryption integrity, not the identity of whoever
possesses the public key; retain the original checksum receipt and use only
trusted files. USB/media loss or loss of recovery key/password remains a risk.

## Verification completed and remaining

- Twelve Python unit tests, synthetic data only: complete exact restoration,
  removed/Pending/history/provenance/auth coverage, int64/BLOB/generated columns,
  rowids/AUTOINCREMENT/WITHOUT ROWID, two-read mismatch, schema/foreign-key
  failures, row caps, missing/bad accounting, quota/notice/date/identity stops,
  account-wide analytics shape/unknown data, safe fixed routes, filesystem/SQL
  sandbox, authorized recovery report-only responses without Cloudflare access,
  and localhost Host/Origin/capability checks.
- Two Chromium browser tests with all external requests intercepted: default
  notice and insufficient headroom stop; private key rejected before export;
  encrypted-only download; independent Python decryption of browser output using
  existing envelope algorithms; checksum mismatch and wrong-password stop;
  correct saved-copy decryption and actual core in-memory restore preserving
  int64/BLOBs; cleared password/key/token fields; no unexpected browser request.
- No owner database, owner private/public key file or recovery password used.
  Only ephemeral test keys and a tiny artificial fixture were used.
- No historical importer/rehearsal or remote load test was run.

Commands for maintainers (the owner does not need these):

```sh
python -m unittest discover -s foundation/tests -p test_owner_windows_backup.py -v
node_modules/.bin/playwright test --config tools/windows-backup/playwright.config.mjs
```

Browser launch required the supported per-command network permission for local
Chromium sockets in this executor. The test page intercepted all network requests;
this did not authorize or make any Cloudflare call. Windows launch/file association,
its certificate store, real read-only token permission, actual telemetry/result
shape and remote read cost have **not** been tested. Any mismatch must stop for
review instead of broadening permissions, bypassing TLS or repeating queries.

Remaining owner review: accept the single Python-installation and account-read
permission tradeoffs; review the guide/tool. Do not run it during the current quota
pause. After explicit approval and confirmed quota headroom, run the owner-side
workflow once and verify the saved local/USB copy. Durable recovery remains
**incomplete** until that actual file passes decryption and isolated restoration.
No destructive staging operation, practice archival, full historical import,
production change or live restoration is authorized by preparing this workflow.
