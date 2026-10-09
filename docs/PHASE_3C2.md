# Phase 3C.2 — readiness evidence and remaining gates

Baseline: `a9f92c96f2328f735c89dc3b9de4d488938190fa`, branch `work`.
**NO-GO for the real staging import.** No Paid subscription was activated. No
human-review records were imported, archived, reset or edited. No staging UI
was deployed: actual isolated Worker CPU validation remains incomplete.

## Import implementation and evidence

`foundation/staging/historical_import.py` creates a checksummed manifest of the
approved derived display model. It uses D1 directly, avoiding Worker bulk CPU.
A single INSERT triggers the complete listing transaction: record, provenance,
groups, literal items, public projection, compact index and durable receipt.
Existing IDs are skipped even when removed; existing owner edits, current Notes,
Pending, order and removed items are never overwritten. Hidden source aliases
are provenance, not new visible roots. Receipt drift stops execution.

Reservations commit before payload execution. Ambiguous responses are resolved
by reading the receipt, not overwriting a record. Failed reservations remain
charged to the conservative ledger. The payload checksum is checked before
submission; duplicate/conflicting IDs roll back the listing transaction.
Manifests and receipts are database-resident, not just temporary progress files.

Execution is deliberately restricted to `wantlist-test-3c2-*` databases. This
phase does not provide a human-review execution switch. The current daily cap
is 60,000 conservative writes, maximum 80,000; raising it for an approved Paid
import and adding a reviewed staging-resource execution gate are remaining work.
Do not bypass either check by changing the system clock or database name.

Actual isolated Cloudflare D1: initial 20 listings used 903 reported writes;
14 further representative listings used 3,909 writes in 9.062 seconds of API wall
time. These include every category, all seven reviewed classifications and the
526-item 2007 Upper Deck listing. A committed-but-lost response was recovered
through its receipt; retry added zero duplicate listings. The disposable database
contains 36 records, not the full collection. Worker endpoint disabled after
validation; its separate D1 retains receipts. Staging/production bindings were
never substituted for disposable bindings.

The full local rehearsal uses **the same transaction SQL**, not the earlier
simplified importer. It has 3,394 records, 59,098 literal items, 3,461 groups and
3,394 receipts/projections/index rows. Replay adds zero rows. Complete restoration
checks table contents, foreign keys, indices, triggers and import state.
See `phase3c2-full-rehearsal.json`, `phase3c2-full-restore.json` and remote evidence
under `foundation/staging/`. Full remote-scale import is not claimed.

## Historical reconciliation

| Category | Listings | WANT | HAVE | COMPLETE | Literal items |
|---|---:|---:|---:|---:|---:|
| OBC Wantlist | 583 | 164 | 280 | 139 | 4,587 |
| UV Wantlist | 2,517 | 757 | 917 | 843 | 49,061 |
| Eau Claire Players | 3 | 3 | 0 | 0 | 112 |
| Milwaukee 8x10 List | 1 | 0 | 1 | 0 | 250 |
| Brewers Bobblehead Wantlist | 26 | 18 | 0 | 8 | 35 |
| Football Wantlist | 62 | 32 | 24 | 6 | 4,022 |
| Other Stuff | 202 | 26 | 166 | 10 | 1,031 |
| **Total** | **3,394** | **1,000** | **1,388** | **1,006** | **59,098** |

Phase 3C.1's Word/protected-normalization reconciliation remains authoritative:
3,392 distinct source records; three Eau Claire boundaries; 26 Bobbleheads; seven
approved overrides; 11 uncertain years; 178 unknown years. Literal ranges are not
expanded. Repeated source identifiers and same-title source listings remain
separate as documented in Phase 3C.1; they are not automatically deduplicated.
No protected source files or production assets changed.

## Collection loading and editing

A projection trigger maintains a compact public index atomically. Seven
500-row requests hydrate all listings/search/filter options; full inventory is
requested only when expanded. Index size is 1,453,928 uncompressed JSON bytes
(sum of rows; response framing is additional). Search receives the complete
collection, including identifiers, before interaction; pagination does not limit
search to visible rows. Current owner Notes are indexed; archived ownership and
historical annotations are excluded from ordinary presentation.

Detail errors have retry controls. Saves use the newly returned full record
rather than stale expanded-detail state. Authentication, revision conflicts,
Undo and category/classification behavior are retained. Existing page endpoint
remains for compatibility. Cache headers are hints, **not a verified shared
Cloudflare edge cache**. Local timings are never reported as Worker CPU.

## Free-plan and billing gates

Official Workers pricing/limits and D1 pricing/import documentation reviewed:

- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://developers.cloudflare.com/d1/platform/limits/
- https://developers.cloudflare.com/d1/best-practices/import-export-data/

Free: 10 ms Worker CPU/request, 100,000 Worker requests/day, D1 5 million rows
read/day, 100,000 rows written/day, 500 MB/database, 5 GB/account, 10 databases.
The full isolated SQLite database is 39,849,984 bytes (about 38 MiB),
comfortably below 500 MB; this is not a measured full-scale remote D1 size.
Index maintenance counts toward writes. The import documentation's charge
exemption for `_cf_KV` does **not** exempt ordinary collection imports.

Workers Paid minimum is $5/month, not a hard spending cap. Included Workers
usage: 10 million requests and 30 million CPU ms; excess is $0.30/million requests
and $0.02/million CPU ms. D1 included: 25 billion reads, 50 million writes, 5 GB
storage; excess $0.001/million reads, $1/million writes, $0.75/GB-month storage.
Allow for account-wide usage and applicable taxes. No purchase is authorized.

All-new conservative import reservation: 821,301 writes. With the 62 existing
historical IDs preserved, 3,332 missing listings reserve 806,001 writes. The 60,000/day local
rehearsal needs 14 virtual days. Initial import and index initialization must
also leave headroom for manual use, backups and account-wide usage. API pilot
suggests a one-day Paid import is plausible, but is **not an established runtime
or billing guarantee**. Validate a larger remote rehearsal, higher approved
budget, actual D1 usage and account-wide remaining quotas first. Avoid bulk Worker
execution. Check quotas before each batch and pause on errors or unexpected usage.

Actual new Worker CPU could not be measured: the environment proxy rejects
`wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev`. Owner/environment administrator
must allow that exact hostname. No alternate-host or staging-test workaround was
used. Earlier p99 outliers up to 20.484 ms remain unresolved; normal-operation
Free gate is **not passed**. Largest inventory browse/notes save passed locally;
Bulk Edit retains the disclosed 500-entry limit and never truncates larger lists.

Official billing cancellation/change-plan pages returned HTTP 403 in this
runtime, and scoped subscription API returned 403. Therefore renewal timing,
cancellation effective date, downgrade eligibility and account charges are
**not verified**. Check these official pages and the owner's dashboard before
paying: `/billing/manage/cancel-subscription/`, `/billing/manage/change-plan/`,
`/billing/understand/billing-policy/`, `/billing/manage/budget-alerts/`.
Budget alerts are not assumed hard caps. Do not promise automatic $0 operation
just because Paid was canceled. Remove any Paid-only settings/resources (including
key-value-backed Durable Object namespaces if present), verify Free database
size/CPU/quotas, confirm effective downgrade and dashboard $0 recurring charge.

## Practice cleanup plan — not executed

Fresh read-only snapshot: 268 stored/265 active roots, 62 matching historical
listings, one hidden legacy photo member, 202 active owner-created practice
listings and three removed roots. 5,639 item rows/3,992 active; all 1,403 benchmark
items remain removed. History: 2,239 events; mutation receipts: 2,200.

`foundation/staging/phase3c2-practice-manifest.json` identifies all 202 practice
roots by stable owner-record IDs, expected revisions, content checksums and no
historical provenance. It includes a manifest checksum. The earlier 86 title
candidates are not a separate deletion rule: practice status comes from the
owner's explicit clarification and verified ID/provenance, not unusual wording.
Historical records and aliases are excluded. Recheck revisions before execution;
any change requires fresh review. Proposed soft archival must update projection
atomically, add recoverable history and retain all items, receipts and prior
history. Do not hard-delete or resurrect removed roots/items. No cleanup code
has been executed.

## Private Google Drive backup setup — incomplete

Drive is the intended owner-controlled destination. No connection or upload was
attempted. The fresh complete snapshot restores exactly locally and includes
categories, records, items, removed state, provenance, metadata, history, receipts
and hashed authentication/session rows. Worker secrets/PIN were not read. New
backup tooling also retains SQL indices/triggers/views and import state tables.
The existing owner's Worker secrets remain necessary for disaster recovery;
restoring a database alone is not permission to rotate PIN or sessions.

`tools/backup-recovery.html` operates in the owner's browser without network
calls. It generates RSA-4096 keys and downloads the public key separately from
a password-protected private recovery-key file. PBKDF2-SHA256 (600,000 iterations)
and AES-256-GCM protect the recovery key. `encrypted_backup.py` accepts only a
public key, verifies local restoration, then encrypts the entire snapshot with
a fresh AES-256-GCM key wrapped using RSA-OAEP-SHA256. Checksums and authenticated
encryption detect corruption. Python dependency: `cryptography`.

Owner's simple remaining steps:

1. Open the backup setup page locally in an up-to-date browser. Choose and retain
   a strong recovery password in a password manager.
2. Download both files. Keep the encrypted private recovery key on a secure USB
   or other owner-controlled location **outside GitHub and this workspace**, separate
   from Drive backups. Keep a second safe recovery copy. Share **only the public key**.
3. Choose a private Drive folder and explicitly authorize the connection, folder
   and encrypted-backup uploads. Do not send private keys/passwords to the operator.
4. Operator encrypts the fresh verified snapshot; uploads only ciphertext;
   downloads it again and verifies the ciphertext checksum.
5. Owner uses the recovery page/password/key to verify recovery; authorized operator
   verifies the recovered database in isolated private storage. Recovered plaintext
   must remain private. Only then mark durable recovery passed.

No owner private key was generated in the agent workspace. Cryptography tests
use ephemeral artificial keys/data. Present gate: **temporary local backup only;
no durable external copy and no durable-copy restore demonstrated**. Never commit
private snapshots, key files, authentication rows or plaintext database exports.
Cloudflare Time Travel/native backup was not tested or claimed.

## Next steps for an actual import

1. Resolve network/billing access and finish actual isolated CPU/performance tests;
   optimize failing routes without weakening transaction/history/authentication.
2. Complete a larger remote rehearsal and quota reconciliation; demonstrate remote
   conflicts, failures, maximum Save/Undo and full index behavior under Free limits.
3. Complete owner-controlled encrypted Drive backup and durable-copy restore.
4. Owner reviews exact 202-ID archival manifest and historical preservation report.
5. Obtain separate approval for Paid ($5 minimum plus possible usage/tax), archival
   and the full staging import. None is implied by this preparation request.
6. Before payment confirm cancellation/effective downgrade timing and quotas. Only
   then add/review explicit staging execution and Paid daily-budget gates.
7. Fresh consistent backup; recheck manifest revisions. Archive approved practice
   roots with recoverable history, then import missing historical roots in batches
   of 20, stopping on quota/receipt/conflict anomalies. Preserve all existing
   historical edits and removed IDs. Track receipts and reservations after every
   batch; retry reads receipts and skips committed roots.
8. Reconcile expected IDs, 59,098 source literal rows and approved categories/types.
   Source baseline counts and edited live counts may differ: report legitimate
   existing owner edits rather than silently replacing them to force source counts.
9. Verify public/editing/Undo/backup on Free constraints; retain pre-import and
   post-import encrypted durable backups. On failure stop new batches, compare
   receipts and owner changes, restore first into isolated storage; never replace
   newer owner edits blindly.
10. Downgrade only after Free compatibility and eligible resources are established;
    confirm dashboard plan/effective date/$0 recurring charge and retest live site.
    Owner handles dashboard payment decisions; operator handles terminal work.

## Verification results

- 71 existing frontend unit tests passed.
- 59 Python foundation tests and 11 Node foundation suites passed, including
  atomic failure rollback, lost responses, owner-edit preservation, receipt
  replay, index privacy and encryption round-trip/tamper rejection.
- 20 owner browser tests passed across desktop/mobile: authentication, draft
  Save, stale revisions, Undo, category/type defaults, Pending and current Notes.
- Six full-collection desktop/mobile browser tests passed, including all seven
  category counts, searchable filters, photo additions, Eau Pending, 526-item
  editing, accessibility checks and no horizontal overflow.
- Four new desktop/mobile tests verified seven index requests, one lazy detail
  request and owner-local key download controls with no remote transmission.
- Remote D1 tests and full local restoration described above passed. No stress
  or automated write-producing tests targeted human-review staging.
- Private backup and temporary paths remain ignored. Branch/source diff checks
  show no production/protected-source edits. No UI deployment was attempted.

**Human review required. No full import, Paid activation, practice archival or
production cutover is authorized by this report.**
