# Phase 3C.3 — final pre-import review

Approved starting commit: `4f4381dc3819aa5ba08ccd42dfe0a77f9d658c5f`,
repository `andrewchris14/wantlist`, branch `work`. Initial checkout was clean;
fetch confirmed the approved remote baseline. Review date: October 9, 2026.

**NO-GO for the real staging import or practice archival.** Remote D1 safety
checks progressed; actual Worker CPU/full-scale HTTP verification and durable
owner-controlled recovery are not complete. No purchase, real import, cleanup,
staging reset, production deployment, PIN/session change or source rewrite occurred.

## Readiness gates

| Gate | Result | Evidence/remaining step |
|---|---|---|
| Repository and protected historical collection | PASS | Word rebuild equals the approved view; all 3,392 normalized source IDs covered |
| Larger isolated remote importer rehearsal | PASS for tested subset | 200 new listings in ten batches; atomic rollback, interruption, replay and conflicts |
| Remote source/projection reconciliation | PASS for receipted subset | Exact table-row comparison against approved manifest; no full remote collection claimed |
| Real Worker CPU and 10 ms Free compatibility | BLOCKED | Proxy denies the disposable hostname; no new CPU samples |
| Seven-request index in deployed Worker | BLOCKED for HTTP | Code deployed in isolated Worker; full local browser check passes; D1 API query passes |
| Billing/cancellation documentation | VERIFIED | Official pages accessed successfully; account billing date/subscription view still needs owner confirmation |
| Resource downgrade eligibility | No identified project incompatibility | No Durable Objects; D1 size/count well below Free limits; account-wide subscriptions unavailable to scoped token |
| Fresh complete backup and local recovery | PASS locally | Matching stable read-only snapshot and exact restore, including authentication hashes |
| Durable encrypted Drive recovery | INCOMPLETE | Owner public key, authorized Drive connection/folder, transfer and durable-copy restore required |
| 202-record cleanup manifest | PASS, not executed | Exact active practice coverage, no historical IDs, no revision/content conflicts |

## Remote importer safety and actual usage

Target is only `wantlist-test-3c2-bc5991ba` and its own D1 database. Strict API
name checks prevent these tools from using human-review staging. No old benchmark
harness was re-enabled. Existing secrets on the disposable Worker were inherited.

Ten 20-listing batches imported **200 additional historical listings** in
**122.505 seconds** of serial API wall time. Successful responses report:

- **830 D1 API requests**;
- **13,255 rows read**;
- **9,258 rows written**, including reservation/attempt overhead;
- **645.9682 ms aggregate D1 execution duration**.

These are D1 billing counters and API timings, **not Worker CPU**. The earlier
payload-only write counter omitted reservation and attempt SQL. The importer now
meters every successful query/statement, exposes `reported_d1_usage`, and keeps
payload accounting separate. After an ambiguous execution response it reports
`actual_writes: null`, rather than inventing a complete charge total. Conservative
reservations remain intact, including failed attempts.

Remote safeguards passed:

1. A malformed payload rolled back record, provenance, groups, projection and
   receipt together. Its reservation remained charged. Correct retry succeeded.
2. An interruption after two committed listings resumed by replaying the first
   two and importing only the remaining two. A further retry wrote zero rows.
3. A removed, revision-12 owner-edit fixture was preserved exactly, including
   its classification and Notes; it was not resurrected.
4. A competing revision-17 record inserted after the importer's initial ID read
   survived unchanged. The import guard stopped without partial groups,
   provenance, public projection or receipt. Retry skipped it with zero writes.
5. A deliberately lost committed response was recovered from its durable
   receipt. Repeat execution added no duplicate and wrote zero rows.

The disposable database also contains deliberate owner/conflict fixtures;
these are not historical receipt counts or legitimate staging records. They
are excluded from source-payload reconciliation. Exact reconciliation compares
all receipted records, provenance, groups, literal items and public projections
with the manifest: **242 receipted listings, 2,407 items and 250 groups**.
Foreign-key checks and all seven approved classifications pass. Comparison
preserves multiplicity rather than sorting only on a
non-unique provenance record ID. See the machine-readable evidence below.

The 200-listing batch rate extrapolates to roughly **34 minutes for the 3,332
missing staging listings**, before backup, reconciliation, backoff and different
inventory sizes. Reserve a several-hour window; this is an estimate, not a
completed full remote import. One Paid day is technically plausible only after
approval, account quota checks and reviewed execution/budget changes. Current
execution still rejects staging, and its Free-safe daily cap is unchanged.

The conservative all-new reservation is **821,301 writes**; preserving the 62
existing historical roots reduces missing-data reservation to **806,001**.
The local 60,000/day schedule requires 14 virtual days. Virtual days exist only
in disposable SQLite; no remote dates or quota ledger were advanced artificially.
One month Paid includes 50 million D1 writes; this import bound alone is far below
that allowance, but account-wide use, backups, cleanup and taxes still matter.

## Full historical and local browser rehearsal

Independent Word-derived regeneration equals the approved derived dataset.
All 3,392 source identities remain covered. The new transaction SQL was exercised
again through all **3,394 listings, 59,098 literal items and 3,461 groups**.
Idempotent replay added zero records. Complete local restore checks table rows,
foreign keys, indices, triggers and import state. No source range was expanded.

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

All seven approved corrections and prior source-year/category mappings remain
unchanged. No historical/production source file was changed. The local database
is about 38 MiB, below the 500 MB Free database limit; this is not a measured
full-collection remote D1 size.

Ten desktop/mobile browser tests pass against the full isolated local database:
category counts, searchable filters, seven index requests with lazy details,
photo additions joining historical inventory, Eau Claire Pending, 526-item
browsing/Notes save, explicit 500-entry Bulk Edit limit, accessibility checks,
no horizontal overflow, and browser backup recovery/tamper rejection.
Frontend unit tests: **71 passed**. Foundation: **62 Python tests and 11 Node
suites passed**. Local functional and timing results do not satisfy the remote
CPU gate.

## Actual Worker and loading limitations

The latest approved Worker/editor assets were deployed **only to the disposable
resource**. Its existing secret bindings were inherited. Module source is
644,961 uncompressed bytes, below the conservative 3 MB build check. Its public
endpoint remains disabled while access is unresolved. No staging UI deployment
was made.

The runtime's enforced policy still contains only the old staging hosts plus
API/documentation domains. It omits:
`wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev`.
A request through the normal proxy fails with `Tunnel connection failed: 403
Forbidden`, before reaching Cloudflare. This is separate from the disabled
endpoint. No alternate hostname, forwarding, proxy bypass, project-file change
or staging write workaround was used.

The exact index SQL executed successfully through the D1 API: **241 rows read,
zero writes, 102,791 JSON bytes**, D1 duration 7.9957 ms. That is a subset query,
not seven HTTP requests or Worker CPU. The full local index is 1,453,928 bytes
before response framing. If full cold loads read approximately 3,394 rows, the
5-million/day read allowance accommodates roughly 1,473 such loads before
other usage; this remains an extrapolation. Shared edge caching is not verified.

No actual new CPU measurements exist for index/detail/login/remembered session,
normal Save, Pending/cancel, maximum Save or Undo. Earlier p99 outliers up to
20.484 ms remain unresolved. No speculative CPU optimization or Free-plan pass
is claimed. Future tests must sample raw requests separately from diagnostic
instrumentation, identify routes/time windows, report errors and analytics
sampling gaps, and never substitute Node or D1 wall time for Worker CPU.
Maximum session validation permits up to 500 changes and 500 additions; test
that combined case, not just a Notes save on a large record. Also test maximum
identifier lengths, replay, stale revisions, failure recovery and large Undo.

### Fixing environment access

The agent has a read-only runtime-status tool, not a configuration mutation tool.
The current [official Cloud environments guide](https://learn.chatgpt.com/docs/environments/cloud-environments)
identifies **Settings → Codex Cloud → Environments → environment ⋯ → Edit**.
Under **Internet access → Additional allowed domains**, add the exact hostname,
save, and republish. Missing controls require checking account/workspace access
or an administrator. Published updates may require a new task; existing tasks
retain their own state. Verify the new task's enforced runtime policy before
re-enabling the disposable endpoint. Do not add credentials to broaden domains.

## Billing and permanent $0 operation

Official pages were successfully accessed with a normal browser User-Agent;
the prior documentation HTTP 403 blocker is resolved:

- [Cancel subscriptions](https://developers.cloudflare.com/billing/manage/cancel-subscription/)
- [Billing policy](https://developers.cloudflare.com/billing/understand/billing-policy/)
- [Budget alerts](https://developers.cloudflare.com/billing/manage/budget-alerts/)
- [Workers pricing and downgrade restrictions](https://developers.cloudflare.com/workers/platform/pricing/)
- [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)
- [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)

Paid is a recurring subscription with a minimum one-month obligation. Cancellation
and downgrade take effect at the current billing-period end; unused time is not
refunded. Billing dates are UTC; request cancellation at least 24 hours before
the billing date. Record the UTC date and its America/Chicago equivalent in the
owner's reminder. The actual date cannot be filled in before dashboard review.

Workers Paid starts at **$5/month**, plus applicable taxes/overages. Budget alerts
are notifications, not hard spending caps. Do not upgrade a domain plan instead
of the Workers subscription. The domain-plan page's Page Rule instructions are
not a Workers downgrade procedure. The owner must confirm the Workers-specific
subscription/effective Free date in **Billing → Subscriptions**, then retain
confirmation of cancellation/non-renewal and the final invoice.

No Durable Object namespaces exist in the account, so none of the documented
key-value-backed Durable Object downgrade blockers was found. Project Worker
bindings contain only D1, plain text and secrets; no paid-only resource binding
or custom CPU limit was found. Three D1 databases fit the Free count/storage
limits. Scoped subscription API still returns 403: account-wide subscriptions,
actual billing date/charges and other product usage remain owner-dashboard checks.

Before any one-month payment: pass real Free CPU tests, validate owner recovery,
confirm account-wide quotas and checkout price, and obtain explicit approval.
After the approved import and verification, select cancellation/downgrade early
in that paid month. Paid remains active until its confirmed period end. At the
end verify **Workers Free**, no recurring Workers charge, no other accidental
paid subscriptions, Free D1 size/usage, and successful public/editor requests.
Canceling alone is not proof the website works on Free. No billing action occurred.

## Cleanup and durable recovery

Fresh human-review snapshot has the same checksum as Phase 3C.2:
`da0a62a460b9ae4696a622839eb4f6f3495f175a52a9e3042ab34720a3e13dc1`.
This was read-only; it restores exactly, including hashed sessions/authentication
rows, removed records, item provenance, history and metadata. No PIN was read.
It remains private in ignored temporary storage; no native Time Travel claim.

The cleanup manifest checksum is:
`948205eb0376c739d3a958ae17b153113885acc9ea6a2a7b6150fa9ce565625b`.
All **202** active practice IDs are covered. No Word/derived/source alias or
approved correction is included. There are **zero revision/content conflicts**.
All **1,403** benchmark item rows remain removed, with zero active benchmark rows.
Prior 86 title candidates are not an independent deletion rule. No archival
was executed. Recheck this manifest against a fresh snapshot immediately before
an approved cleanup; do not overwrite later owner edits.

[Owner backup setup instructions](BACKUP_SETUP.md) explain local recovery-key
generation, safe key/password retention and private Drive-folder authorization.
No owner public key, authorized Drive folder or upload connection has been supplied.
No Drive access/upload was attempted. Browser/Python interoperability and tamper
rejection now pass using ephemeral artificial keys/data only. Durable verification
requires retrieving the actual encrypted Drive copy, validating its checksum,
owner-side decryption and an isolated exact database restore. Until that succeeds,
backup/archival/import approval must remain pending.

## Exact next steps

1. Apply the domain permission using the published environment workflow; resume
   in a new task if necessary. Do not spend money or alter staging to fix access.
2. Re-enable only the disposable endpoint for tests. Measure actual Cloudflare
   CPU/error/D1 results for each required route and maximum Save/Undo. Complete
   full-scale HTTP index/search/filter verification under a bounded Free budget.
   Resolve CPU outliers and repeat affected regressions; disable endpoint afterward.
3. Owner generates recovery files, securely retains the private file/password,
   provides only the public key, and authorizes a Restricted Drive folder/connection.
   Operator handles encryption, transfer, checksum comparison and isolated restore.
4. Owner confirms current billing, renewal timing and account-wide quota headroom.
   Review a final GO report and the exact revision-checked 202-ID cleanup manifest.
5. Obtain separate explicit approvals for the one-month Workers payment, archival
   and historical import. Add/review guarded staging execution and higher Paid
   import budget only then; current tools remain disposable-only.
6. Fresh verified durable backup precedes revision-checked, recoverable soft
   archival. Import missing historical IDs in controlled batches, tracking receipts,
   daily reservations and real D1 counters. Preserve historical owner edits/removed
   state. Report live-vs-source item differences instead of forcing counts by rewrite.
7. Reconcile final collection and editing, retain encrypted post-import backup,
   schedule/confirm Free downgrade, and verify $0 recurring operation and live site.
   Production/full cutover remains a separate future decision.

## Evidence

All JSON evidence is under `foundation/staging/`:
`phase3c3-remote-rehearsal.json`, `phase3c3-remote-conflict.json`,
`phase3c3-remote-lost-response.json`, `phase3c3-remote-reconciliation.json`,
`phase3c3-index-sql.json`, `phase3c3-full-rehearsal.json`,
`phase3c3-full-restore.json`, `phase3c3-complete-backup.json`,
`phase3c3-cleanup-review.json`, `phase3c3-billing-review.json`, and
`phase3c3-isolated-deployment.json`. None contains private database contents,
credentials or owner recovery keys. The approved cleanup manifest remains the
Phase 3C.2 file; its contents were not rewritten.

**Stop for owner review. NO-GO remains until the blocked gates are demonstrably
passed. No real import, cleanup or Paid activation is authorized by this report.**
