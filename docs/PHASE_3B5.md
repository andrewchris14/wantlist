# Phase 3B.5 — staging review checkpoint

Implemented on `work` after fetching and verifying the exact approved baseline `1e62f8b43412d72e8c1e8c6d1d5c49929058bb46`. The local checkout was clean and matched remote `work` before development. The Phase 3B.4 report and contamination audit were reviewed first. The implementation commit and final synchronized branch status are supplied in the completion message.

Deployed to **https://wantlist-staging.andrewchris14.workers.dev/**. Production was not deployed. No full historical import or cutover was performed. Stop here for human review.

## Editing and list meaning

Every existing-listing edit now uses a draft and one **Save changes** transaction: metadata, category, list type, notes, additions, removals, Pending, Bulk Edit, and entry order. Save is disabled when unchanged, shows a saving state, prevents duplicate submissions, and confirms success. Revision checks reject stale saves without losing the draft or overwriting newer data. Lost responses retry the same receipt. Expired sessions can be reauthenticated while retaining the draft.

Sticky Close and Save controls remain accessible on long desktop/mobile lists. Closing a dirty editor asks exactly **“You have unsaved changes. Are you sure you want to discard them?”**, with Keep editing and Discard changes. Discard makes no write. Page departure uses the browser's supported native before-unload confirmation; browsers control its wording.

Ordinary WANT entries have only **Mark Pending** and **Remove**. Pending entries have Cancel Pending and confirmed removal. No Mark Received button remains. Pending stays in the same WANT inventory, never creates an ownership inventory, and appears once publicly as **Pending: 2, 15, 47** in the saved presentation order. It is omitted from ordinary needed entries, hidden when empty, and searchable. Removing an item soft-removes its membership, without creating another list type. Existing ownership statements remain supplemental historical notes, not a second editable primary list.

Natural/Original order persists in record metadata and public projections, and applies after Save/reload, to ordinary and pending entries, and to additions. Natural examples: `1, 3, 5, 2 → 1, 2, 3, 5`; `10, KB-12, 2, KB-2, 1 → 1, 2, 10, KB-2, KB-12`; `Yount, Aaron, Molitor → Aaron, Molitor, Yount`. Original order preserves historical sequence and intentional insertion order without changing source identities or positions.

WANT/HAVE conversion requires explicitly entered/confirmed replacement identifiers. It never calculates missing cards or transfers owned identifiers silently. COMPLETE requires confirmation and preserves earlier entries for recovery. A coordinated save has one revision, one audit event and a transactional projection. Supported latest-change Undo restores prior metadata, item states, pending timestamps and membership. Existing authentication, Origin/CSRF checks, rate limiting, receipts and category guards remain.

Bulk Edit loads the complete logical inventory, previews additions/removals/unchanged entries, retains unchanged pending states, warns about pending removals, and applies to the draft only. Final Save persists it. Cancel does nothing. Names remain one per line, including spaces/commas; literal ranges remain literal. **The 500-entry Bulk Edit limit is disclosed and larger lists are never truncated.** A Save supports up to 500 existing-entry changes and 500 additions, disclosed if exceeded; larger operations require smaller editing sessions. Individual display starts with 40 entries, with search and Show all.

## Historical inventories and counts

Related source and owner-added entries now share a logical inventory while their original group/item references remain intact. Milwaukee 8x10 has one HAVE inventory: adding **Megill, T** appears beside the original 250 names, and Bulk Edit includes both. Tests cover this, additions to Eau Claire, and yearly bobblehead listings. Genuinely distinct variant groups remain separate. Missing years/manufacturers are permitted. Special collections use the ordinary editor, including notes, search, ordering, Pending where applicable, Bulk Edit, Save and recoverable removal.

The Eau Claire Word headings were independently checked against raw paragraphs 3380–3381:

| Source-defined listing | Original entries |
|---|---:|
| Major League Players | 102 |
| Major League Managers | 3 |
| EC Managers (but did not play for EC) with major league experience | 7 |
| **Total** | **112** |

The live split moved the existing three source groups into three derived listing records. It preserved every item ID and source reference, retained the original introduction/qualifications, and made the player-interest entries ordinary WANT items without treating them as ownership or completeness claims. The revision-139 original container became an archived revision-140 record; all 138 earlier owner history events and its 15 already-removed owner-added practice entries remain. No ambiguous owner additions were assigned to an invented group. A tested, guarded rollback restores the exact earlier grouping and opaque states, and refuses rollback after newer owner edits. Newly added players stay in their chosen listing.

| Historical category | Derived display listings |
|---|---:|
| OBC Wantlist | 583 |
| UV Wantlist | 2,517 |
| Eau Claire Players | 3 |
| Milwaukee 8x10 List | 1 |
| Brewers Bobblehead Wantlist | 26 |
| Football Wantlist | 62 |
| Other Stuff | 202 |
| **Total** | **3,394** |

Effective historical types: **1,000 WANT / 1,388 HAVE / 1,006 COMPLETE**. This is the complete derived historical view, not a D1 import. All 26 original bobblehead listings and the seven historical categories remain. Owner-created categories continue to work.

All seven approved classifications remain verified in derived data and actual D1: `p0060-l001` COMPLETE; `p0273-l029` COMPLETE; `p0273-l039` WANT; `p1996-l008` COMPLETE; `p2501-l001` COMPLETE; `p2851-l007` COMPLETE; `p3022-l006` HAVE. Original uncertainty wording, unconfirmed availability and literal `1–96` source range remain. Only the 1995 JSW Goudey 4-in-1 variants listing is COMPLETE; other distinct 1995 JSW groups remain separate and unchanged.

“Preserved Source Information” is removed from the public display. A provenance-linked presentation rule treats `p0526-l006`'s Brewers/Braves/Pilots ownership-and-interest prose as readable notes, never needed identifiers. The original words remain visible and preserved in protected source/provenance data.

Year and Manufacturer now have compact searchable, keyboard-accessible comboboxes with partial/case-insensitive matching, selection and clear/reset. Options come from actual records and combine with Category/Search. Uncertain years retain their literal wording and numeric position: `1991 → 1990(?) → 1989 (ca.) → 1972 (?) → undated`; ranges retain their meaning and genuinely undated entries use Unknown year. The header/tab title is **Jason's Want List**, with **Jason Christopherson** beneath it, retaining OBC attribution and the vintage styling. There is no status filter.

## Confirmed cleanup and recovery

[Exact cleanup manifest](../foundation/staging/phase35-cleanup-manifest.json) links every one of the 1,403 item IDs to its addition history event. The audit reproduced all **61 UUID rounds**, each with the exact **1 + 2 + 20** signature, **183 addition events**, **61 year/manufacturer edits**, and **61 benchmark-note edits**. No later event referenced a benchmark item. The earlier year/manufacturer were 2007/Upper Deck; the earlier notes were empty. No later legitimate metadata/notes edits superseded them. Later legitimate Pending changes were separately verified and preserved.

Immediately before maintenance, all 15 application tables were read twice and compared for consistency. A fresh private authentication-free backup passed exact-row restoration, counts and foreign-key checks in disposable SQLite. SHA-256: `d4e416cee93ab4c9d8a114a7d587d2ae2299e4b9d20cca43098c84bb45e42a1b`. The backup is retained in ignored operator storage at `foundation/.local/phase35-pre-maintenance.json`, mode 0600; Worker rollback modules are separately retained at `foundation/.local/phase35-worker-rollback.json`. Private data is not published in GitHub.

A six-statement, revision-checked transaction soft-removed exactly the manifested 1,403 entries from **p1237-l004**, revision **795 → 796**, restored verified metadata/notes and rebuilt its projection atomically. Item and history rows remain. Its legitimate card `1` remains Pending. **Zero active cpu-test entries remain anywhere in staging.** Cleanup has supported latest-change Undo; local tests restore all removed entries and prior metadata exactly. Subsequent owner edits prevent unsafe automatic Undo. The private backup and retained audit rows support separately reviewed recovery thereafter.

The full staging scan also found **86 other fixture-title candidates**, including 61 “CPU staging” titles; their IDs, titles, counts and review status are in the manifest and [verification result](../foundation/staging/phase35-verification-result.json). They contain zero other scanned known-prefix active entries and no duplicate values in those candidate records. Unusual titles alone do not establish deletion authority. **All 202 owner-created records remain**, including legitimate human practice sets. No blanket cleanup ran. These candidates require individual review before any further removal. The full group audit also identifies one pre-existing source-backed duplicate value (`38`, two original p1237 item IDs) and 114 retained owner-generated groups across 70 records with empty active membership or different group/root types. Such recovery/mixed groups can be legitimate; the verification result lists their exact IDs and counts without labeling them all contamination or deleting them.

The split used 25 transactional statements. Post-maintenance comparison verifies all prior history and provenance unchanged, all unaffected record rows identical, all other item properties identical, and no lost/duplicated source items. Actual D1 now has **267 records / 264 active**, **5,629 retained item rows**, and **2,221 history events**. Only three derived listing records were added; no full collection import ran.

The one-time maintenance gate was removed after both operations. Existing secret bindings were inherited without retrieving PIN values; session counts/creation boundaries and authentication generation were verified unchanged. Automated writes remain isolated in disposable local SQLite. Human-review staging rejects diagnostic writes, and deployment still refuses its test-storage capability.

Evidence: [release](../foundation/staging/phase35-release-result.json), [post-release verification](../foundation/staging/phase35-verification-result.json), [integrity hashes](../foundation/staging/phase35-integrity-result.json). Live root/categories returned 200, unauthenticated owner read 401, disabled maintenance and diagnostic writes 403. Deployed HTML matched the tested build; public API projections verified cleanup, retained Pending and the three Eau inventories. Existing owner PIN/session editing should now be reviewed by the owner; no live owner login or write-producing automated test was used.

## Tests and screenshots

**199 tests passed**: 21 protected normalization/source tests, 48 Python foundation/backup/isolation tests, 60 Node backend/auth/category/history/migration tests, 56 website/model/filter tests, and 14 desktop/mobile browser workflows. Owner and production builds passed; the production build was verification only. Tests cover atomic rollback, receipts/retry, expiry with preserved drafts, stale concurrent saves, Undo, explicit conversions, pending cancellation/removal, special inventory membership, source counts/prose, natural/original reload persistence, combined searchable filters, category create/rename/move/protected deletion and public authorization boundaries.

Chromium desktop 1440×1000 and mobile 390×844 checks found **zero axe WCAG 2A/2AA/2.1AA violations** in tested views and no page/dialog horizontal overflow. Sticky controls were asserted in viewport at the end of the 526-entry historical sample. These are measured checks, not a claim of testing every browser/screen reader.

Screenshots show the released UI/Worker against disposable local fixtures, without creating human-review staging test data or revealing the existing PIN:

| View | Desktop | Mobile |
|---|---|---|
| Simplified actions | [image](evidence/phase3b5/owner-desktop-simplified-actions.png) | [image](evidence/phase3b5/owner-mobile-simplified-actions.png) |
| Public Pending | [image](evidence/phase3b5/owner-desktop-public-pending.png) | [image](evidence/phase3b5/owner-mobile-public-pending.png) |
| Sticky Save/Close | [image](evidence/phase3b5/owner-desktop-sticky-controls.png) | [image](evidence/phase3b5/owner-mobile-sticky-controls.png) |
| Unified editor | [image](evidence/phase3b5/owner-desktop-unified-editor.png) | [image](evidence/phase3b5/owner-mobile-unified-editor.png) |
| Bulk Edit | [image](evidence/phase3b5/owner-desktop-bulk-edit.png) | [image](evidence/phase3b5/owner-mobile-bulk-edit.png) |
| Searchable Year | [image](evidence/phase3b5/owner-desktop-searchable-year.png) | [image](evidence/phase3b5/owner-mobile-searchable-year.png) |
| Searchable Manufacturer | [image](evidence/phase3b5/owner-desktop-searchable-manufacturer.png) | [image](evidence/phase3b5/owner-mobile-searchable-manufacturer.png) |
| Branding/combined filters | [image](evidence/phase3b5/owner-desktop-branding-filters.png) | [image](evidence/phase3b5/owner-mobile-branding-filters.png) |
| New category | [image](evidence/phase3b5/owner-desktop-new-category.png) | [image](evidence/phase3b5/owner-mobile-new-category.png) |

## Free-plan findings and remaining limits

[Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/) still document **10 ms Free CPU**. The earlier **10.781 ms** replacement remains an unresolved outlier. New grouped analytics returned a limited sample of 1,000 historical groups, of which **33 had p99 above 10 ms**, up to **24.443 ms**. This is an incomplete 24-hour sample and does not attribute peaks to particular routes/actions. Raw GraphQL time values are **microseconds**, converted to milliseconds in this report. No unsupported first-isolate explanation is asserted.

The release window's four measured groups had no p99 above 10 ms; the single-request seconds associated with cleanup and split were **7.708 ms** and **8.255 ms**. Their D1/wall durations are separate from Worker CPU. This does not prove maximum-sized ordinary Save/Undo requests will always fit Free CPU. A dedicated isolated Cloudflare benchmark remains necessary before full import/cutover; no benchmark writes were made to human-review D1. [Raw CPU evidence](../foundation/staging/phase35-cpu-result.json).

The new Save path validates item changes through aggregate SQL and captures before-state/rebuilds projections inside D1, without deserializing unchanged large inventories in the Worker. Recent history and session Undo also avoid retrieving entire membership snapshots. A 500-addition save uses at most nine transactional statements; authorization/preflight/read checks keep ordinary saves well below D1 Free's 50-query request allowance. Bound parameters stay below 100 and SQL/row/function sizes stay within documented limits. Atomicity, authentication and audit safeguards were retained.

Actual staging database size is **9,121,792 bytes**. Its UTC October 9 analytics through 02:34:38 report **175,311 rows read** and **2,896 written** (577 read queries / 250 write queries), below the Free daily allowances of 5 million reads and 100,000 writes for this database's contribution. These are not an account-wide usage claim. [D1 analytics](../foundation/staging/phase35-d1-usage-result.json).

Remaining limits: the disclosed 500-entry Bulk Edit/draft-operation bounds; 86 preserved fixture candidates requiring review; older CPU-limit exceedances and unmeasured maximum-size remote editing CPU; browser-controlled page-departure wording; owner review with the existing live session/PIN. Remote disaster restore/Time Travel was not exercised, and no live cleanup Undo or split rollback was performed—their recovery behavior was verified locally against the same code.

Protected Word/raw/Phase 2 data, existing production static JSON and production source files are byte-for-byte unchanged against the approved baseline. No production deployment, D1 cutover, PIN/session rotation, paid feature, resource replacement, force push or full import occurred. **Stop for human review.**
