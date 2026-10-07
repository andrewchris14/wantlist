# Phase 3B.3 — Dad-facing staging owner editor

Implementation starts from approved `ca20add0ae071ced1668ac9e255e88e2fa7388f5`
on `work`. **Staging only:** no full baseline import, production editor deployment,
public-data cutover, paid feature or new Cloudflare resource. The closure commit
containing this report is identified in Git history and the completion message.

## What Dad sees

This is the existing collector-friendly React/Vite wantlist, with optional owner
controls in a separate staging entry point. It is not a database dashboard.
Unsigned visitors see the familiar search, filters, cards and Owner Login link;
they cannot edit. Production `npm run build` and `npm run dev` still use the
approved static JSON. They do not import the owner entry point or contact D1.

Dad's staging workflow:

1. **Owner Login** → enter **Owner access code** → **Sign in**. **Keep me signed
   in on this computer** starts checked. The form explains when to uncheck it
   for a shared computer. Enter also submits the form.
2. Search normally, then **Open & edit this set**. No IDs, source blobs, SQL,
   deployment controls or authentication implementation details appear in forms.
3. Find a card using **Find a card in this set**. Needed cards have **Someone is
   sending this** and **Received**. Expected cards have **Received** and **Still
   need this**. Owned cards explicitly say **Already owned**; corrections are
   disclosed under **Correct a mistake**. No HAVE complements are generated.
4. **Add cards** opens a short form. Choose **Cards I need** or **Cards I have**.
   Numbers/codes accept spaces, commas or lines: `12 18 47 92`. Names use one full
   name per line; commas within names are retained. A preview says **Adding 4
   cards: 12, 18, 47, 92**. Ranges remain literal, never expanded.
5. **Edit set information** exposes Year or years, Brand, Set/name, the dataset's
   exact categories, the list description and Notes. Notes are explicitly public.
   Changing the description does not automatically change any card's state.
   Complete/Uncertain changes require an explicit checkbox. Complete also fails
   server-side if wanted/expected or unresolved wanted source entries remain.
6. **Add a new set** uses those same simple fields (only Set/name required).
   **Create set** opens its card-entry form immediately. Initial cards are entered
   in this second step; Dad need not close/search/reopen the new set. Owner-created
   records have creation/history metadata, not fabricated Word provenance.
7. **More → Remove** removes a mistaken item. **Recently removed cards → Restore**
   brings it back. Removing an entire set requires a separate confirmation;
   **Recent Changes → Removed sets → Restore set** recovers it.
8. **Recent Changes** uses readable descriptions, with **Undo** when safe.
   Newer changes to the same set prevent Undo. Card transitions, one-card adds,
   notes/metadata changes and removal/restoration are reversible. A multi-card
   addition directs Dad to remove the specific mistaken cards individually.
9. Confirmations include **47 marked Received**, **4 cards added**, **Set information
   saved** and **Change undone**. Log out removes editor controls immediately.

Large groups initially show 40 items plus a search and Show all control. Add-card
forms collapse after saving so card actions remain the focus. Historical named
prose/ranges that the foundation could not safely itemize stay visible with their
correct WANT/HAVE/uncertain relationship; they do not acquire guessed state buttons.
Owner-entered named items are individually actionable because their intent is explicit.

## Authentication and security

The approved architecture is unchanged: one owner, server-only Worker-secret
SHA-256 verifier/version and native constant-time comparison of a high-entropy
access code. No code expiration/forced rotation, account/password table,
registration or public reset endpoint. The submitted code is cleared from the form;
no code, verifier, API token or reusable session is saved in frontend storage.

D1 holds hashed, revocable random sessions. Secure/HttpOnly/SameSite=Strict cookies
provide approximately 90-day remembered and 8-hour non-remembered sessions.
Actual backend tests cover both durations, expiration and revocation. Browser
checks observe persistent 90-day cookie flags and authentication after reload.
An actually expired session triggers **This computer needs to be verified again.
Enter your Owner access code to continue.** The same non-expiring code signs in again.
No claim is made of physically restarting a computer during these tests.

`STAGING_EDITOR=true` opts the existing staging Worker into serving the owner bundle
and allowing normal login/public reads without the diagnostic operator header.
Owner/private reads and all writes still require a validated owner session.
Diagnostic `/test/*`, health and technical recovery routes retain the operator gate.
`STAGING_ONLY=true`, exact-origin checks, JSON input requirements, throttling,
revision validation, atomic D1 batches and mutation receipts remain intact.
The browser receives no operator key. Assets have a restrictive same-origin CSP,
no-store and nosniff headers; React escapes entered names and notes.

A simulated lost response **after a real D1 commit** was retried with the same
request ID; the receipt returned the existing result and only one card existed.
Unknown outcomes block new form submissions until retry or reopening/checking the
set. Errors are plain language, never raw SQL/HTTP exception details. Successful
confirmation is shown only after the backend confirms the transaction.

## Data layer and publication

Owner read models select editable metadata rather than parsing/returning the
historical source blob. Indexed reads retrieve only the chosen record's groups/items.
The original provenance remains internally untouched when metadata changes.

Undo resolves the original history entry to an inverse delta and validates its
saved record revision against the requested revision. The existing atomic CAS
prevents intervening changes. This deliberately avoids timestamp/random-ID
ordering as a correctness dependency; a frozen-clock test covers multiple changes
in the same millisecond. Pre-3B.3 unversioned history cannot be automatically undone.
Undo receipt hashing uses the original request, so lost-response retries remain
idempotent. Owned → Pending is still rejected as an ordinary transition; it is
allowed only when validated Undo restores an earlier Pending state.

A correctness guard additionally rejects restoring unresolved wanted source wording
into a Complete set. It remains recoverable after intentionally changing the set's
status. No historical data was rewritten to implement this guard.

Every edit still atomically saves the revision, item/header, history, receipt and
**affected record-level public projection**. No entire public snapshot is rebuilt.
The editor refreshes only that public row (no browser cache reuse), and ordinary
item/header changes merge the confirmed delta into the open editor. Add replies
return at most 20 new item entries. Opening/reloading a set or Undo can fetch its
lean owner view, but ordinary one-card saves do not reload its entire item inventory.
Search/filtering and finding a card in an open set run in the browser, not D1 per key.

Inputs over 20 cards use sequential, bounded, individually atomic requests.
The UI shows confirmed progress and stops on failure, explaining that some cards
were saved and the remaining list must be checked. This is **not** one atomic
all-or-nothing large-set creation job. The private-draft protocol discussed in
Phase 3B.2 is still future work.

Actual D1 query plans (`foundation/staging/editor-query-plan-result.json`) show:

- Record header: records primary-key index.
- Groups: `(record_id,kind,position)` unique index.
- Items: indexed group lookup using `items_group_value`; ordering only within the
  chosen set, not a global items-table scan.
- Recent history: `history_recent`, with bounded timestamp-tie sorting; history
  entry lookup for Undo uses the history primary key.
- Removed sets: a small records-table scan/sort, no items scan. No speculative new
  indexes were added. This can be reconsidered if deleted-record volume grows.

The closure check caught D1 choosing the per-record history index for the global
Recent Changes query and sorting the history. The query now explicitly selects
the already-existing `history_recent` index. Actual D1 `EXPLAIN QUERY PLAN`
confirms sorting only the last two order terms (timestamp ties), with no new index.

The known large-group item restore cost (5,661–5,799 reads) remains documented and
unoptimized. The accepted 11.656 ms first-edit-after-redeployment outlier also remains
an accepted Free limitation; no security/correctness checks were removed.

## Actual staging evidence and performance

Existing resources only: `wantlist-staging` Worker/D1 and the existing disabled
`wantlist-staging-3b2-probe`; the quota-test D1 database is retained unchanged.
The main DB contains the previously imported **27 historical records** plus
fictional test sets/items. The full 3,392-record import remains unexecuted.
The conservative 80,000-write/day importer and six-or-more-day reservation plan
are unchanged. No billing/service plan, payment information, custom domain or
production route was changed. Free-plan identity still relies on the owner's
verified dashboard; the restricted token cannot inspect billing.

Actual owner API checks cover ungated owner login, protected writes/private reads,
diagnostic gate, origin rejection, future creation, lean reads, targeted additions,
Undo, stale rejection and logout. CPU and D1 evidence is in
`foundation/staging/editor-verification-result.json`. The raw benchmark used five
executions per operation and separate metered diagnostics. Missing sampled CPU
observations remain missing; wall time includes network/database waiting.

Final repeated targeted checks (five successful raw runs each; D1 costs from
separate instrumented requests, CPU from unambiguous one-request sampled buckets):

| Action | CPU samples | Median / max CPU ms | Median wall ms | D1 reads / writes |
| --- | ---: | ---: | ---: | ---: |
| Someone is sending this | 1/5 | 1.706 / 1.706 | 126.5 | 12 / 9 |
| Undo Pending | 3/5 | 4.222 / 9.788 | 181.1 | 13 / 9 |
| Add 1 | 2/5 | 2.494 / 2.592 | 157.2 | 15 / 12 |
| Add 2 | 2/5 | 2.686 / 2.800 | 146.8 | 19 / 16 |
| Add 20 | 3/5 | 3.238 / 3.356 | 169.7 | 73 / 88 |

The 9.788 ms sampled Undo is close to the documented 10 ms allowance. All
requests succeeded; medians remain below it. Sparse sampled observations are not
a complete CPU distribution or proof of a strict worst-case bound. Preserve the
accepted administrative-event outlier and monitor future staging behavior; no
security/correctness reduction was made.


The original actual backend regression was rerun, including the 15-action future-set
lifecycle, indexed D1 behavior, atomic failures, retry/stale guards, sessions and
portable private JSON/sanitized public JSON/CSV/SQL export with disposable local
restore/equality and foreign-key checks. Native signed D1 download/remote restore
and Time Travel remain unverified; this phase does not claim to resolve them.

During closure, the isolated diagnostic republisher was corrected to retain a
removed record's internal projection inventory. Public responses still hide the
removed record/items; restoring it recovers that inventory. A regression test
covers remove → diagnostic republish → public-hidden → restore. Ordinary editing
already retained this inventory. No historical baseline or schema was rewritten.

## Browser evidence and regressions

The owner browser suite uses real staging Worker/D1, not mocked responses. Chromium
cannot directly use this cloud's egress proxy, so a loopback-only technical test
relay carries requests via urllib while retaining the real HTTPS workers.dev URL,
Origin header and browser cookie origin. It is not deployed or part of Dad's website.
No HAR, traces, login screenshots or credential bodies are persisted. Disposable
staging throttle counters are reset between isolated test cases, not bypassed by
application code. The recovery/session suites and performance runs execute
sequentially to avoid invalidating the benchmark's session.

Desktop (1440×1000) and phone (390×844) tests cover the required card lifecycle,
new sets, names/codes, notes/metadata, Complete/Uncertain, restoration, safe Undo,
persistence, keyboard submission, logout, direct unauthorized API attempts, lost
save response/retry and actual session expiration. Search tests include Griffey,
Costco, BCP, postcards and football; a large-set search is checked on both sizes.
Axe WCAG A/AA checks pass for the active owner dialog; layout checks find no horizontal
overflow. This is not a full manual accessibility audit or an Opera-specific test.

Visual evidence, captured and inspected:

- [Desktop cards](evidence/phase3b3/owner-desktop-cards.png)
- [Phone cards](evidence/phase3b3/owner-mobile-cards.png)
- [Desktop Complete](evidence/phase3b3/owner-desktop-complete.png)
- [Phone Complete](evidence/phase3b3/owner-mobile-complete.png)
- [Desktop large-set search](evidence/phase3b3/owner-desktop-large-set.png)
- [Phone large-set search](evidence/phase3b3/owner-mobile-large-set.png)

Final test counts and resource state are saved in
`foundation/staging/editor-checkpoint-result.json` and summarized in the completion
message. Passed: Phase 2 21; foundation 39 Python + 35 Node; website 43;
public browser 16; real staging owner browser 8; actual backend checks 330;
actual owner API checks 21. Production and isolated owner builds passed. The
owner-specific eight Node tests and real owner browser/API suites were also
rerun after selecting the chronological history index. No existing assertions
were weakened.

## Human UX review and temporary exposure

**Recommend Dad's hands-on review before any full import or production cutover.**
Observe whether he independently finds a set, marks a promise/receipt, adds several
cards, and recovers a mistake. Check his actual browser too; automated tests use
Chromium, not Opera on Windows. Staging data includes earlier benchmark fixtures;
the permanent public wantlist remains independent.

Both staging endpoints/previews are disabled at completion. For a separately
approved review window, the technical recovery person can run from `work`:

```sh
npm ci
npm run build:owner
python -m foundation.staging.editor_preview --enable
```

This exposes only `https://wantlist-staging.andrewchris14.workers.dev`, using the
existing staging DB and server secrets. Dad opens that staging site and enters the
disposable staging access code through Owner Login. Supply it privately, never in
a URL, source file or GitHub. Do not use a production credential. The operator
requires the existing ignored secure checkpoint/scoped environment bindings; if
those are lost, use technical recovery to intentionally reprovision a staging
credential/checkpoint, not a public password-reset endpoint.

Immediately after review:

```sh
python -m foundation.staging.editor_preview --disable
```

No production website change, full import or paid feature is part of either command.
The public build stays on `site/data-source.js` and its static dataset asset.

## Remaining limitations and next approval

- Recent Changes and removed sets each show the latest 20 entries; no history
  paging/full archive UI yet. Older data remains in the DB/backups.
- Automatic Undo is limited to a current versioned change and supported inverses.
  Multi-add correction is individual removal; old unversioned history is not
  automatically reversible through this UI.
- Unstructured historical names/prose/ranges remain lossless, without guessed
  card actions. A later explicitly reviewed itemization workflow may be useful.
- Additions use the existing primary applicable WANT/HAVE group. Labels/sublists
  and mixed information are displayed/preserved, but a group-management editor,
  prefix editor and private trade-detail forms are not included.
- Public visitors with an already-open staging tab reload to see another owner's
  changes; no real-time subscription/polling was added. The saving browser updates
  immediately after confirmation.
- There is no hidden database cutover, full import, production owner interface,
  scheduled backup service, trade workflow or automatic large draft-save protocol.

Sources preserved: the Word/raw files, all Phase 2 normalization/corrections and
approved `wantlists.json` remain byte-identical to the approved baseline. The Phase 2
backup archive is retained. No production data dependency was added.
