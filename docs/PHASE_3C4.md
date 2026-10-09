# Phase 3C.4 — owner readiness checklist

Review date: October 9, 2026 (America/Chicago).
Approved baseline: `9db890035d5b777b5074ba3288c0019584eea141`, branch `work`.

**Decision: NO-GO. Stop for human review. Permanent Workers Free operation has
not yet been demonstrated. No Paid activation, historical import, practice
archival, staging-data modification or production deployment occurred.**

## What changed in this environment

The startup policy file now lists
`wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev` in restricted HTTP egress.
However, the runtime-status tool reports current observations with network
policy state **unknown**, and Cloudflare token/account-variable readiness
**unknown**. A listed host is not proof of enforced policy or credential readiness.

Two normal-proxy requests to the test hostname failed immediately with curl
exit 7: **Failed to connect to proxy port 8080**. A Cloudflare API request and
Git fetch failed the same way. No HTTP response was received: this is a proxy
connectivity failure, not the previous HTTP 403 destination denial. No request
reached the Worker, and no CPU results exist for this phase.

The managed environment reports running/connected, but that status does not
resolve the observed proxy failure. An environment administrator must repair
the configured proxy/runtime setup and confirm policy state enforced and
credentials ready. Do not bypass the proxy or change staging to diagnose this.
Once repaired, retest the exact hostname and re-enable only the disposable
endpoint through the Cloudflare API; Phase 3C.3 left that endpoint disabled.

The workspace checkout is stale at `33ffe970b2c9772df1144556c002dd706022a20f`.
Git fetch cannot update it while the proxy is unreachable. The three requested
documents and recovery HTML were reviewed through the GitHub connector; the
recovery HTML was read at the approved baseline. Documentation is published
through that connector rather than building or testing the stale checkout.
No passing importer/browser/restore rehearsal was repeated.

## Readiness checklist

| Check | Status | What is still needed |
|---|---|---|
| Actual Worker Free CPU, including earlier 20.484 ms p99 outliers | BLOCKED | Isolated Cloudflare measurements; Free CPU limit is 10 ms/request |
| Normal browsing, login and remembered authentication | UNVERIFIED remotely | Raw request CPU/error samples, separated from diagnostics |
| Search, filtering and seven-request full collection index | PASS locally in 3C.3; UNVERIFIED remotely | Full 3,394-listing HTTP/browser test on disposable resources |
| Notes, normal Save, Pending/cancel and Undo | PASS locally in 3C.3; UNVERIFIED remotely | Actual Worker CPU, authorization, history and D1 usage |
| Maximum combined Save and large Undo | UNVERIFIED remotely | 500 changes plus 500 additions together, maximum identifier lengths, replay, stale revisions and failure recovery |
| Import safety | PASS for prior tested subset | Keep prior rollback, conflict, interruption and receipt evidence; do not repeat just because HTTP is blocked |
| Complete snapshot and exact isolated restore | PASS locally in 3C.3 | Fresh snapshot before any approved destructive operation |
| Encrypted Google Drive backup recovery | INCOMPLETE | Owner public key, Restricted folder authorization, upload/download, checksum, owner decryption and isolated restore |
| 202-record practice manifest | REVIEWED in 3C.3; NOT EXECUTED | Fresh revision/content check and separate owner approval |
| Account billing, quotas and effective downgrade date | OWNER CHECK REQUIRED | Confirm in Cloudflare dashboard before any purchase |
| Permanent $0/month site | NOT ESTABLISHED | Pass real Free tests and verify actual Free plan/usage after any future downgrade |

Do not optimize from invented timings. Optimize only measured failing operations
and retest affected routes while preserving authorization, edit history, atomicity,
historical integrity, the simple interface and seven index requests. Free limits
recorded in 3C.2/3C.3: 100,000 Worker requests/day; D1 5 million rows read/day,
100,000 written/day, 500 MB/database, 5 GB/account and 10 databases. Account-wide
usage counts. Prior full local database size was about 38 MiB, not a full remote
size measurement. Shared edge caching remains unverified.

## Jason's private backup steps

1. Follow [BACKUP_SETUP.md](BACKUP_SETUP.md). Download
   [backup-recovery.html](https://github.com/andrewchris14/wantlist/blob/9db890035d5b777b5074ba3288c0019584eea141/tools/backup-recovery.html)
   using **Download raw file**, save it on your computer and open it in a current
   browser. Generate the two recovery files locally.
2. Save the strong recovery password (at least 16 characters) in your password
   manager. Retain the encrypted private recovery-key file on secure storage
   separate from Drive backups, with a second safe copy. Keep the recovery page.
   Losing either the private file or password can prevent recovery.
3. Provide **only `wantlist-public-key.json`**. Do not send the private recovery
   key or password to this workspace, GitHub or the operator.
4. Create **Want List Private Backups** in Google Drive and keep sharing
   **Restricted**. Identify the exact folder and explicitly authorize encrypted
   uploads/downloads. If no suitable Drive connection is available, manually
   upload/download operator-provided ciphertext through Drive's browser interface.
5. The operator first verifies a fresh consistent snapshot by isolated restoration,
   then encrypts it using your public key. Only ciphertext goes into Drive.
   Download that actual Drive copy and have its ciphertext checksum compared.
6. Use **Recover an encrypted backup** locally with your retained private key
   and password. Keep the recovered plaintext private. An authorized operator
   must then restore it into isolated private storage and compare all tables,
   history, removed state, provenance, metadata, authentication hashes, import
   receipts and schema objects. Agree on a private recovery channel first.
   Do not replace the live database or newer owner edits during this check.

The reviewed HTML forbids network connections via its content security policy;
it generates RSA-4096 keys, protects the private file with PBKDF2-SHA256
(600,000 iterations) and AES-256-GCM, and verifies authenticated backup metadata
and plaintext checksum on recovery. Previous artificial-data interoperability
and tamper tests passed in 3C.3. This review generated no owner key and performed
no Drive connection, transfer or durable-copy restoration. That portion stops
pending owner participation. Native Cloudflare Time Travel is not claimed.

## Historical counts already confirmed

These are the approved source/local reconciliation counts from 3C.3, not a new
live-data measurement. Preserve legitimate existing owner edits and removed IDs.

| Category | Listings | Literal items |
|---|---:|---:|
| OBC Wantlist | 583 | 4,587 |
| UV Wantlist | 2,517 | 49,061 |
| Eau Claire Players | 3 | 112 |
| Milwaukee 8x10 List | 1 | 250 |
| Brewers Bobblehead Wantlist | 26 | 35 |
| Football Wantlist | 62 | 4,022 |
| Other Stuff | 202 | 1,031 |
| **Total** | **3,394** | **59,098** |

Total classifications: **1,000 WANT, 1,388 HAVE, 1,006 COMPLETE**;
**3,461 groups**, covering **3,392 distinct normalized source identities**.
Literal ranges remain unexpanded and seven approved corrections remain intact.

## Reviewed practice cleanup

The [exact 202-ID manifest](../foundation/staging/phase3c2-practice-manifest.json)
has checksum
`948205eb0376c739d3a958ae17b153113885acc9ea6a2a7b6150fa9ce565625b`.
Phase 3C.3 confirmed complete active-practice coverage, no historical IDs and
zero revision/content conflicts. This is prior evidence, not a fresh 3C.4
snapshot. The 202 historical Other Stuff listings above are a separate set;
matching counts do not authorize their removal. The prior 86 title candidates
are not a deletion rule.

Immediately before any separately approved cleanup, check every stable ID,
revision, content checksum and provenance against a fresh consistent snapshot.
Changed entries require fresh review. Only recoverable soft archival is proposed:
retain items, history and receipts and update projection atomically.
All 1,403 benchmark items were already removed in 3C.3; do not resurrect them.
No archival has occurred.

## Import duration and usage

Prior actual isolated D1 pilot: **200 additional listings in 122.505 seconds**,
**830 API requests, 13,255 rows read and 9,258 rows written**, including
reservation/attempt overhead. Aggregate D1 execution duration was 645.9682 ms;
none of these numbers is Worker CPU. Exact prior remote reconciliation covered
242 receipted listings, 2,407 items and 250 groups, not the full collection.

Preserving the 62 existing historical roots leaves an estimated **3,332 missing
listings**, conservatively reserving **806,001 writes** (821,301 if all new).
The pilot rate suggests about **34 minutes**, with a **several-hour window**
for backup, differing inventory sizes, backoff and reconciliation. This is an
estimate, not a runtime or cost guarantee. At the unchanged 60,000/day import
budget, prior local scheduling required **14 virtual days**; real quota days
must never be advanced artificially. Leave headroom for all account usage.

Execution tools remain disposable-only. A reviewed staging execution gate and
any higher Paid budget would be separate future work after approval. Import
only in controlled batches with receipts, quota checks and stop-on-error rules;
never overwrite existing historical edits to force source totals.

## Optional Workers Paid: owner decision only

Prior verified official documentation in 3C.3 records **$5/month minimum**,
plus applicable taxes and overages; it is recurring and not a hard spending cap.
Included Workers usage: 10 million requests and 30 million CPU ms/month.
Excess: $0.30/million requests and $0.02/million CPU ms.
D1 includes 25 billion reads, 50 million writes and 5 GB storage;
excess is $0.001/million reads, $1/million writes and $0.75/GB-month storage.
Reconfirm checkout prices and account-wide use before approval.

If approved later, use **Billing → Subscriptions** to manage the **Workers**
subscription, rather than a domain plan. Prior verified rules: minimum one-month
obligation; cancellation/downgrade at billing-period end; unused time not refunded.
Request cancellation at least 24 hours before the UTC billing date and retain
confirmation, effective Free date and final invoice. Record the actual UTC date
and America/Chicago equivalent; no account date is known yet. Budget alerts only
notify. Verify eligible resources, Workers Free, $0 recurring Workers charges,
other subscriptions and successful Free-constrained browsing/editing afterward.

[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[cancellation](https://developers.cloudflare.com/billing/manage/cancel-subscription/),
[billing policy](https://developers.cloudflare.com/billing/understand/billing-policy/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/).
These were verified in 3C.3, not re-fetched during this proxy outage.
No Paid subscription was activated.

## Explicit approvals still required

- [ ] Authorize the exact Restricted Drive folder and ciphertext transfer.
- [ ] Confirm durable-copy decryption and isolated restoration have passed.
- [ ] Review actual isolated Worker Free measurements and account-wide quota headroom.
- [ ] If desired, separately approve Workers Paid at the confirmed checkout price,
      with cancellation/downgrade timing understood.
- [ ] Separately approve the exact freshly revision-checked 202-ID soft archival.
- [ ] Separately approve the guarded historical staging import after all gates pass.
- [ ] Any production deployment/cutover requires a separate future decision.

**Remaining blockers:** unreachable configured proxy; policy enforcement and
credential readiness unknown; real Worker CPU/full-collection HTTP/max Save/Undo
unverified; owner-controlled durable Drive recovery incomplete; account billing
and quota confirmation outstanding. Human review is required before proceeding.
