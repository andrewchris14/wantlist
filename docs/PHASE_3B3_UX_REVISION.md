# Phase 3B.3 staging UX revision

This revision continues from approved commit `504a96bc92458013de1fa8b153d68d0a18767a47`.
It changes only the isolated staging guest/owner interface and its supporting backend.
The production `site/App.jsx`, `site/RecordCard.jsx`, and `site/data-source.js` remain unchanged.
`npm run build` still builds the approved public static interface using `/wantlists.json`.
No full import, production editor, public D1 cutover, paid plan, or new Cloudflare resource is authorized here.

## Compact interface

One full-width row per listing, collapsed initially, with a large text WANT list/HAVE list/COMPLETE label.
Native expandable rows support keyboard operation. Contents render only after expansion.
Seven document categories replace the staging status/brand/taxonomy filters; OBC Wantlist opens first.
Within a category, year descends, then set name sorts alphabetically; undated listings follow dated ones.
Search is case-insensitive, client-side and explicitly scoped to the selected category. Buttons identify matches in other categories.
No search keystroke queries D1. The list is not paginated. Empty wanted/owned sections are omitted.
Names, numbered values, mixed lists, meaningful notes and completed subgroups remain available.

Owner Login reveals editing only after server authorization. Expand a row and choose **Edit this set**.
Dad can find a card, choose **Someone is sending this**, **Received**, or **Still need this**;
add multiple cards or one named item per line; remove/restore; edit notes and metadata;
create a future set; review Recent Changes and use supported Undo. No internal IDs/schema fields are shown.
An intentional **Edit list** workflow previews a fully entered replacement and requires acknowledgement.
It does not relabel an owned inventory as wanted and never calculates checklist complements.
For a mixed listing, choose the particular list to replace; unrelated groups remain intact.
Undo restores the original membership/list types. Old items remain recoverable rather than being physically deleted. Previous representation entries are
shown separately from individually removed cards. They cannot be individually reactivated under a
new group meaning: an opaque owned source entry must never become wanted just because its
group was converted. Restore of a normally removed opaque item also checks its original group
meaning. Whole-list Undo restores the original membership and meaning together. The restore-event lookup uses the existing record/date history index; it adds a bounded
check without a global item/history scan. This is a
data-correctness safeguard, not removal of routine Remove/Restore functionality.

## Reproducible source category mapping

`tools/build_display_wantlists.py` independently reads the original Word document, checks its extracted
paragraphs against the unchanged raw import, and derives an additive display snapshot.
It does not run or change Phase 2 normalization. `npm run build:owner` regenerates this view automatically.
The approved `data/wantlists.json` remains unchanged and independently recoverable.
`data/display-wantlists.json` retains every original record exactly once inside its view/source records;
`data/display-map.json` supplies membership/uncertainty display metadata.

The verified original paragraph boundaries are OBC 1–525; its Other Stuff 526–578;
Football 579–643; UV 644–3024; Bobbleheads 3025–3123;
Milwaukee photos 3124–3378; Eau Claire 3379–3382. No brand/keyword category inference is used.
All 3,392 historical records map confidently, with no unmapped historical entries.

| Category | Original records | Display listings |
|---|---:|---:|
| OBC Wantlist | 583 | 583 |
| UV Wantlist | 2,517 | 2,517 |
| Eau Claire Players | 1 | 1 |
| Milwaukee 8x10 List | 1 | 1 |
| Brewers Bobblehead Wantlist | 26 | 1 |
| Football Wantlist | 62 | 62 |
| Other Stuff | 202 | 202 |
| **Total** | **3,392** | **3,367** |

### Three special primary listings

- Eau Claire Players: one WANT listing, **112 original player-interest names**, original context and group headings.
- Milwaukee 8x10 List: one HAVE listing, **250 owned photo entries**; names containing commas remain one literal entry.
- Brewers Bobblehead Wantlist: one WANT listing, **35 wanted literal entries** in 26 original year groups, including 9 Complete groups.

Every nonempty original Eau Claire/photo section line is represented in a source line ledger.
All 26 bobblehead source records and their complete/noncomplete groups survive consolidation.
No artificial root year, manufacturer or card number was created. Special containers permit notes/items editing,
not misleading new year/brand fields or creation of duplicate primary section listings.
Their fixed primary containers cannot be removed through the ordinary owner UI/API (individual items can be removed/restored).
Archived source members are never automatically revealed as duplicate fallback listings.
Their fixed source-level types cannot be changed by a generic list replacement or header edit;
use individual additions/removals/states and notes instead. Manual WANT/HAVE replacement is for ordinary set listings.
Future ordinary sets choose one of the four set-oriented categories. Existing fixed special containers accept new items.

**Legacy parser artifacts, preserved rather than silently rewritten:** the original Milwaukee Phase 2 record includes
an extra `H` number from `Aaron, H`, and the original Eau Claire item array includes comma-split introductory prose/headings.
The derived view reads the actual source lines instead. The approved legacy records are retained unchanged in `source_records`
and database provenance, so neither historical representation is lost. These are documented display derivations, not
manual patches to the historical dataset.

**Eau Claire safety:** a player's name expresses broad collecting interest, not an individually identified card.
The original names remain opaque interests rather than actionable unique cards. A warning explains that receiving one
card does not complete a player's wantlist. Specific cards/photos added by the owner are actionable and can be Pending/Received.
Photos and year-specific bobblehead entries support individual actions when safely identified.

Only the three derived section samples were appended to the existing staging database. The original 27 imported sample
records, all original IDs/provenance, and pre-existing fictional fixtures remain. Existing older fictional test records
without a source section or owner-selected category appear in an owner-only **Older practice listings to organize** area.
Their categories were not guessed. Staging counts are samples, not the full historical display counts above.

## Historical uncertainty audit

All **28 original uncertain records remain unchanged**. Twenty-one have an explicit owned inventory and can be displayed
as HAVE list without claiming completeness; their uncertainty wording remains visible. Seven cannot be assigned a
confident ordinary type and display **Source note — review needed**. No normal UNCERTAIN selector or prominent badge is used.

| Record | Listing | Unresolved source wording |
|---|---|---|
| p0060-l001 | 1980 Unknown Manufacturer New York Yankees All-Time Greats | Believed to be complete |
| p0273-l029 | 1972 (?) TCMA Nu Grape World Champion Athletics 1929 | Complete? (likely only one in set) |
| p0273-l039 | 1972-73 TCMA 1940 Team Composites (unconfirmed wantlist--availability is unknown) | Brooklyn, Chicago Cubs, Chicago White Sox, Cleveland, New York Giants, New York Yankees, Pittsburgh, Washington |
| p1996-l008 | 1995 JSW — 35 Goudey 4-in-1's in Blue, Red, and Yellow | Believe to be complete |
| p2501-l001 | 1990(?) Negro Leagues Baseball Museum All Star Paige Postcard | Complete? |
| p2851-l007 | 1985(?) Pacific Trading Cards Babe Ruth Postcard | Complete? |
| p3022-l006 | Baseball All-Time Greats (unsure of make--Green border) | Complete? Have cards 1-96. |

These explicit inventories can display HAVE while retaining all original uncertainty:

| Record | Explicit owned inventory |
|---|---|
| p0023-l001 | 1980 Green Mountain Press American Folk Heroes |
| p0239-l017 | 1974 TCMA Sporting News — 1909 |
| p0239-l018 | 1974 TCMA Sporting News — 1910 |
| p0261-l003 | 1973 TCMA Christmas Cards (possibly complete) |
| p0375-l001 | 1963 Jay Publishing Milwaukee Braves |
| p1809-l001 | 1997 Collect-a-sport/College Division |
| p1996-l007 | 1995 JSW — 33 Goudey Red Box |
| p1996-l009 | 1995 JSW — 48 Bowman B&W |
| p1996-l010 | 1995 JSW — 50 Bowman Black Border |
| p1996-l011 | 1995 JSW — 50 Bowman Red Border |
| p1996-l012 | 1995 JSW — 50 Bowman White Border |
| p1996-l013 | 1995 JSW — 51 Bowman |
| p1996-l014 | 1995 JSW — 52 Bowman |
| p1996-l015 | 1995 JSW — 52 Topps |
| p1996-l016 | 1995 JSW — 53 Bowman Black Box |
| p1996-l017 | 1995 JSW — 53 Bowman Script |
| p1996-l018 | 1995 JSW — 53 Topps Black Box |
| p1996-l019 | 1995 JSW — 53 Topps Red Box |
| p1996-l020 | 1995 JSW — 61 Topps |
| p2529-l001 | 1989 (ca.) Dairy Council of Wisconsin Milwaukee Brewers magnets (possibly complete) |
| p2887-l001 | 1984 TCMA Baseball Advertiser Roberto Clemente FDC |

The ambiguous unconfirmed wanted inventory, unknown set identity and questioned completion require human interpretation.
We have not converted any of these seven to WANT/HAVE/COMPLETE. For `p3022-l006`, the owned range remains literal
source information; neither its set identity nor completeness is proven. None of the ranges is expanded.

## PIN authentication: intentional security tradeoff

This is an explicitly approved **weak four-digit PIN** mode, not security equivalent to the prior random owner code.
There are only 10,000 PINs; a common PIN can be guessed correctly on the first attempt. Throttling cannot remove that risk.
The frontend, GitHub, URLs, public responses and logs contain neither the configured PIN nor its verifier.
The actual PIN is a server-side Worker **Secret** `OWNER_PIN`; `OWNER_PIN_VERSION` is a separate secret version identifier.
Verification uses SHA-256 and Workers' standard constant-time comparison. D1 stores only random-session hashes,
version/control data and throttle counters, not a PIN/user/password account table.

Existing origin/CSRF protections, generic login failures, five attempts/IP and 25 global attempts per 15-minute window remain.
Remembering is checked by default: Secure, HttpOnly, SameSite=Strict cookies and server-validated revocable sessions
last approximately 90 days; non-remembered sessions last approximately eight hours.
The PIN itself does not expire and has no age/forced-rotation requirement. Version rotation revokes old sessions.
Logout, individual/all-session revocation and technical recovery remain available.
The original high-entropy server verifier remains supported when PIN secrets are absent; operator protection is unchanged.
The revised Dad-facing login form is specifically a four-digit PIN form, not a strong-code login UI.

Actual staging tests used an isolated disposable PIN, never a production credential. **The requested permanent PIN has
not been copied from this chat into Cloudflare.** Configure it directly in the dashboard without sharing it here.

### Technical maintainer: configure or change the staging PIN

1. Sign in to Cloudflare and open **Workers & Pages → wantlist-staging → Settings → Variables and Secrets**.
2. Edit/add `OWNER_PIN`, choose **Secret**, and type the chosen four-digit PIN privately. Keep leading zeroes.
   Do not create a public environment variable or a Vite variable. Do not paste it into ChatGPT, GitHub or a terminal command.
3. Edit/add `OWNER_PIN_VERSION`, choose **Secret**, and enter a new unique version label of 16–100 letters/numbers/hyphens/underscores
   (for example `owner-pin-review-version-two`). This label is not the PIN. Change it whenever deliberately rotating access.
4. Save/deploy the updated secrets. Do not change the D1 binding, plans, `OWNER_AUTH_CONFIG`, or operator secret.
5. During an authorized preview window, Dad opens the staging website, selects **Owner Login**, enters the PIN,
   and leaves **Keep me signed in on this computer** checked. No Cloudflare/developer operation is part of Dad's workflow.

Repository deployment tooling uses Cloudflare's documented **inherit** secret binding for already configured secrets;
it will preserve dashboard-configured credentials instead of resetting them from the disposable local checkpoint.
After manual PIN rotation, automated tests need a matching securely supplied disposable credential; do not overwrite
maintainer secrets merely to make a stale test checkpoint work.

### Preview boundary

Only existing `wantlist-staging` and its existing staging D1 are used.
Temporary review URL: https://wantlist-staging.andrewchris14.workers.dev
Both main and probe endpoints/previews are disabled at completion unless a separate review window is explicitly opened.
Technical maintainer may use `python -m foundation.staging.editor_preview --enable` for an authorized review and
`python -m foundation.staging.editor_preview --disable` afterwards. Enabling preserves current Worker secrets.
The production/public site remains independent and static throughout.

## Backend integrity and performance

Ordinary item edits keep the approved targeted/delta mutation path. Manual list replacement reads and updates only
its affected group and record, uses existing group/record/history indexes, CAS revision checks and mutation receipts,
and commits changed items, history and incremental record publication in one D1 atomic batch.
Old representation membership is captured by SQL, without cloning the old whole set inside the Worker.
No per-edit full snapshot regeneration is introduced. Public reads search in the browser after fetching public projections.
The new metadata `display_category` is public-safe and is included in portable public exports; private trade details remain excluded.

Manual representation replacement is bounded to **500 entries** per request. Larger replacement/draft publication is not
implemented in this revision; ordinary additions retain bounded 20-card batches behind the simple Save workflow.
Repeated actual Worker measurements and D1 metering are recorded in `foundation/staging/revision-verification-result.json`.
Prior accepted 11.656 ms first-edit-after-redeployment outlier and approximately 5,661–5,799 item-restore reads remain
known documented limitations, not silently changed. Free limits and retained 80,000-write/day import budget remain unchanged.
The full import reservation remains 471,733 writes (at least six budget days), and full import remains unexecuted.

Portable private JSON, sanitized public JSON, CSV and SQL restoration are regression-tested in disposable local storage.
Native signed D1 download/remote restore and Time Travel remain unverified from this environment; they are not claimed as tested.

## Evidence and verification

Screenshots are in `docs/evidence/phase3b3-revision/`, including desktop/mobile compact rows, expanded WANT/HAVE,
bobblehead listing, replacement preview and owner item/notes editing.
Browser tests use actual HTTPS staging Worker/D1 through the scoped test relay because Chromium cannot directly use
the cloud network-secret egress transport. This is not mock storage. Authentication origins/cookies remain real;
traces/HAR and login-body logging are disabled. Chromium was tested, not Opera-specific behavior.

Final counts, regression results, resource state, source checksums and staging measurements are saved in
`foundation/staging/revision-checkpoint-result.json`. Existing Phase 2/foundation/website/public-browser suites remain intact.

## Review before migration

Human desktop/phone review is recommended before any full import or production switch. In particular review compact density,
item naming, mixed list selection, seven unresolved source notes, the weak PIN risk and the Eau Claire interest distinction.
Undo is offered only where a latest history entry can safely be reversed; Undo of Undo is not a general redo system.
Legacy opaque values are retained rather than turned into fabricated actionable checklists.
The current public site still has its approved Phase 3A interface until a separately approved production UI cutover.


## Final regression and new-operation measurements

All checks passed: Phase 2 21; foundation Python 44 and Node 42; website 49;
public desktop/mobile browser 16; staging owner desktop/mobile browser 14, plus
4 final affected presentation/special-item rechecks. Both public and staging builds passed.
Real D1/Worker backend regression: 518 assertions, including the 15-change future-set lifecycle.
New revision backend checks: 24 assertions. Automated axe checks found no violations
in the inspected screens; phone layouts had no horizontal overflow. Keyboard login,
form submission, and native expand/collapse were exercised. These checks do not
substitute for Dad's own browser usability review.

The following CPU timings are actual Cloudflare analytics for five uninstrumented
requests per type, each isolated in its own one-request analytics bucket. D1 rows
are from a separate instrumented representative request, not inferred from wall time.
Samples are too few for a reliable P95/P99 claim. These are small intentional replacements;
we do not extrapolate a maximum-size 500-entry CPU guarantee from them.

| Operation | Successful runs | Median CPU ms | Max CPU ms | Median wall ms | D1 reads | D1 writes |
|---|---:|---:|---:|---:|---:|---:|
| want_list replacement | 5/5 | 5.509 | 7.239 | 177.875 | 115 | 23 |
| have_list replacement | 5/5 | 3.772 | 10.781 | 161.275 | 121 | 20 |

Actual D1 EXPLAIN for replacement position/projection uses the `(group_id,field_key,position)`
unique index; history membership uses `items_group_value`; record projection uses its primary
key. None scans the global items table. All publication changes remain limited to the affected
record/group and atomic with edit/history/receipt. Supplemental section rerun added zero records
and wrote zero rows, preserving post-sample edits.

Visual evidence:

- [Desktop compact list](evidence/phase3b3-revision/owner-desktop-compact-list.png)
- [Phone compact list](evidence/phase3b3-revision/owner-mobile-compact-list.png)
- [Expanded WANT/mixed Griffey](evidence/phase3b3-revision/owner-desktop-expanded-want.png)
- [Expanded HAVE](evidence/phase3b3-revision/owner-desktop-expanded-have.png)
- [One bobblehead listing](evidence/phase3b3-revision/owner-desktop-special-list.png)
- [Reviewed replacement workflow](evidence/phase3b3-revision/owner-desktop-list-replacement.png)
- [Special-item notes editor](evidence/phase3b3-revision/owner-desktop-special-editor.png)

Files changed: `owner/Browse.jsx`, `owner/OwnerApp.jsx`, `owner/api.js`, `owner/model.js`,
`owner/styles.css`, owner browser tests; staging `auth.js`, `owner.js`, `records.js`,
`replace-list.js`, `runner.py`, `revision_samples.py`, `revision_verify.py`;
`foundation/storage.py` public metadata allowlist; new source/display and backend tests;
`tools/build_display_wantlists.py`; two derived JSON views; README/package build command;
this report, screenshots, and three actual-staging result/checkpoint reports.
No migrations/dependencies or protected historical/public-loader files were changed.


### Final performance limitation and staging state

The final repeated conversion batch completed 10/10 raw saves, plus two instrumented saves.
Cloudflare exposed CPU for all five WANT requests and four of five HAVE requests;
one HAVE request crossed the client/analytics second boundary, so no CPU was assigned to it.
The first HAVE replacement in this batch measured **10.781 ms**, above the documented 10 ms Free
allowance. Its cause is not established. It is not automatically treated as the previously approved
11.656 ms first-edit-after-redeployment observation. The earlier conversion batch was below 10 ms
(max WANT 5.907 ms, max HAVE 3.166 ms); the final batch demonstrates runtime variability.
We do not claim every manual replacement stays below 10 ms merely because all saves completed.
Regular targeted card mutations retain the approved architecture, and no security/correctness checks
were removed. This new conversion outlier merits review before production; maximum-size 500-entry
replacement CPU has not been benchmarked. No additional CPU optimization/cutover is inferred as approved.

Both staging Workers have workers.dev endpoints and version previews **disabled** at completion.
The existing D1 databases are retained, and the Worker DB binding still points only to `wantlist-staging`.
All 27 original historical samples remain, alongside fictional fixtures and three derived section containers.
No full import was run. The exact final staging counts and size are in the checkpoint JSON.
Existing server PIN/version secrets survived an actual deployment with no local PIN checkpoint, and
subsequent login/logout succeeded. The permanent requested PIN still requires direct dashboard entry
by the technical maintainer; automated tests used only a disposable PIN.

Empty historical primary Complete placeholders are not presented as current completion after reopening a set as WANT; meaningful completed-year sublists remain. The fixed special-container delete API was tested against actual staging and rejected without changing data.

Some legacy source-text entries remain non-actionable until their individual identity is confirmed through explicit owner entry/list replacement. Their literal contents are preserved; no card identity or checklist complement is guessed. Human UX review should include these exceptional entries.

The meaningful Milwaukee “Autographs” qualifier remains visible in the expanded photograph list. A final desktop/mobile category-browser recheck passed (2/2); staging endpoints and previews were disabled again afterward.
