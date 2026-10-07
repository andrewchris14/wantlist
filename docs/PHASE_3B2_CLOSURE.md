# Phase 3B.2 definitive closure checkpoint

Reviewed 2026-10-07. Implementation/evidence baseline:
`cedb494ba35602db71eb76ef9c51f37029a323ca` on `work`.
The closure commit containing this document changes documentation only. Its SHA
is reported in the completion message and Git history; no self-referential SHA is
embedded here. Phase 3B.2 is closed with the owner's accepted limitations below.
**Phase 3B.3, production cutover, and the full import remain unauthorized.**

## Approved authentication

Exactly one owner; a high-entropy access-code SHA-256 verifier and credential
version are stored in the server-only `OWNER_AUTH_CONFIG` Worker secret.
Verification uses the approved native constant-time comparison. This is not a
fast-hash design for weak/common passwords or PINs. The access code has **no
expiration, forced rotation, password-age requirement, or periodic changes**.
It is checked only at login, never on ordinary editing requests. No password/user
account table, registration or public reset endpoint exists.

Random server-issued session tokens use Secure/HttpOnly/SameSite cookies; only
token hashes and authentication control are stored in D1. Remembered sessions
last approximately **90 days**; non-remembered sessions approximately **8 hours**.
Short sessions have no persistent cookie Max-Age. Server expiration always applies.
Logout, individual revocation, global revocation, credential-version checks,
generic login errors, throttling and origin/CSRF checks are preserved. Technical
recovery can rotate the secret/version and invalidate old sessions. Dad signs in
with the same access code after ordinary session expiration. No credential,
reusable session token or private export is committed or exposed publicly.

Actual Workers Free verifier measurements and session tests passed, as recorded
in [the original staging report](PHASE_3B2.md). Authentication is approved and
was not redesigned during CPU optimization or closure.

## CPU acceptance and known efficiency issue

The [CPU review](PHASE_3B2_CPU_REVIEW.md) contains the full measured table,
sample counts, wall time, D1 counters and evidence paths. Each of 11 ordinary
operations ran 20 times successfully, plus three successful diagnostic runs.
Measured median CPU ranges **2.150–3.684 ms**; maximum observed ordinary CPU
**8.305 ms**. Available analytics are sampled; missing samples are not invented.
Worker CPU excludes database/network waiting, and D1 duration is reported
separately. These empirical measurements do not guarantee every future request.

Five first edits after distinct redeployments all succeeded; CPU was 8.640,
**11.656**, 5.133, 5.923 and 4.642 ms. The owner explicitly accepts the 11.656 ms
observation as a Workers Free limitation/outlier, not a project blocker:
redeployment is administrative rather than Dad's ordinary workflow. This is not
an assertion that it complies with the documented 10 ms allowance or proof of a
cold isolate. Earlier 10.446/15.586 ms observations cannot be conclusively
attributed; instrumentation alone was disproved as their sole cause.

Targeted/delta mutations are approved. Authorization, validation, atomic audit,
revision checks, idempotency, soft deletion/restoration and publication remain
intact. No safeguards were removed to improve timings.

**Known restore efficiency issue:** measured item restoration consumed
**5,661–5,799 D1 rows read** and 9 written in the large-set case. Existing analysis
attributes this to iteration/sorting of the affected group's JSON virtual table
inside D1, not a global items-table scan. No correctness defect was found. At
Dad's expected frequency this is not presently a quota blocker. It is retained
for future review if usage grows; no restore optimization was performed here.

## Real D1 and publication verification

Actual D1 accepted the schema, indexes, constraints and atomic batch model.
Targeted record/item/session queries and query plans were verified, along with
revision races, duplicate retries, rollback, invalid transitions and soft deletion.
Edits atomically update the item/header, revision, history, receipt and affected
record-level public projection. **No complete snapshot is rebuilt after each edit.**
Public search remains client-side; the existing site does not query D1 at all.
Future public publication can use these incremental projections; occasional full
exports remain recovery operations, not per-edit work.

The fictional `2027 Topps` actual-D1 lifecycle passed: owner creation, wanted and
owned cards, later additions, Pending, Received/Owned, return to Wanted,
metadata/notes/status changes, soft deletion/restoration and export. Its expected
15 history actions were verified. Owner records require creation metadata, not
fabricated historical Word provenance. Mixed WANT/HAVE, uncertainty and unusual
collectibles remain lossless; HAVE lists never generate checklist complements.

## Import checkpoint and restrictions

Full baseline: **3,392 records**. Full import remains **unexecuted and unapproved**;
the full-execution CLI guard remains enabled. Plan-only tooling reserves
**471,733 writes over 318 chunks**, largest chunk 2,164, with the conservative
default **80,000 writes per UTC day**. This implies **at least six budget days**,
potentially more for packing, retries or other account usage. This is a reservation
estimate, not actual full-import metering. The earlier approximately 260,000
indexed-write estimate is not a measured replacement for that reservation.

Atomic daily reservations, chunk checksums/completion ledger and initialization
guards make import resumable/idempotent. Failed or unknown attempts retain their
reservations; completed retries add no data. Partial imports are detectable and
not editable. Initialization rejects live edits, changed revisions, owner-created
records, deletions or baseline mismatches. Account-wide usage must be checked:
the project ledger is not Cloudflare's account-wide quota meter. Never maximize
the 100,000/day limit or bypass Free quotas; lower the budget if necessary.

Real quota-test sample: 27 records, 30 groups, 960 preserved literals, 656 actionable
items; provenance 27/27, no omissions/additions/duplicates/content/state differences.
304 opaque values were preserved without guessing. Griffey Blue wanted/Red owned,
2023–2025 Costco Flagship baseball category, HAVE/Complete/Uncertain and oddball
cases reconciled. The artificial test budget paused at 2,584 then resumed under
12,000; this did not change the production default or Cloudflare limits.
Reservations were 9,813; successful chunk writes 4,087, plus small control writes.
All seven completed chunks were skipped on rerun, with zero new data writes.
Local virtual-day rollover passed; actual next-day rollover was not waited for.

## Recovery, resources and Free-plan limitations

Actual D1 portable private JSON, sanitized public JSON, CSV and SQL export paths
were exercised; disposable local SQLite restoration/equality and foreign-key
checks passed. Private future trade details must not enter public projections,
fallback snapshots or public GitHub. The historical baseline remains independent.

Native D1 export generation worked, but signed download from the R2 export host
remains network-blocked. Native remote restore and Time Travel restoration are
**unverified**. Documented Free Time Travel is seven days, not a tested recovery
guarantee. Portable export/local restore remains the working recovery path.

Read-only Cloudflare API closure checks confirm:

| Resource | State |
|---|---|
| `wantlist-staging` Worker | workers.dev disabled; previews disabled |
| `wantlist-staging-3b2-probe` Worker | workers.dev disabled; previews disabled |
| `wantlist-staging` D1 | retained staging data; 4,931,584 bytes |
| `wantlist-staging-import-budget` D1 | retained quota-test sample; 1,286,144 bytes |

Last recorded main contents: 96 records including fictional fixtures, 3,768 items,
916 history entries; quota DB 27 records/960 items/no history. No database became
operational truth. D1 API metadata's `version: production` denotes its backend
version, not a project production cutover. No endpoints were enabled during closure.

Workers Free $0 and D1 Free were manually verified by the owner; no payment
information was required. Documentation confirms Free limits and fail-on-quota
behavior, not automatic paid overages. The scoped token cannot inspect billing.
No paid features, custom domains or production editor were enabled. Long-term
inactivity and deliberate quota exhaustion were not empirically tested.

## Preservation and regression checkpoint

Public Phase 3A still uses its original static JSON loader, independent of staging.
Word/raw source, reviewed corrections, Phase 2 scripts and approved dataset are
unchanged. `data/`, `tools/` and `site/` remain byte-identical to approved
`d452f58d9006a498db7a8c65827c645b8f817703`. Dataset SHA-256:
`38a7ee7ad07ede1ae744dbe91b819c1bb78a294c70ca30f933bc66604d44c98a`.
The independent Phase 2 backup archive remains retained.

Previously completed regression results at the implementation checkpoint:

- Phase 2 validation: 21 checks passed.
- Foundation: 39 Python and 27 Node tests passed (66 total).
- Website: 36 tests passed.
- Desktop/mobile browser tests: 16 passed, including production build.
- Actual Worker/D1 regression: 248 assertions passed, plus final staging smoke.
- Portable export/restore and exact sample reconciliation passed.

Closure changes only these reports; no implementation changed, so those suites
were not rerun and no staging writes/deployments were performed. Closure checks
verify documentation links, whitespace, protected-file equality, endpoint state
and repository synchronization. Original measured JSON artifacts are unchanged,
including their historical open-gate wording; this accepted closure supersedes it.

Next phase requires separate approval. Large draft-save UX/protocol, native remote
recovery and Time Travel remain future work/limitations, not silently verified
features. Full import also requires its own explicit authorization.
