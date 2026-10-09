# Phase 3B.5.3 — Only current owner Notes

Approved baseline verified: `95cc053d23378a6737ed78fd2d50624afa9969da`, clean `work` checkout of `andrewchris14/wantlist`, matching fetched remote.

Public listings now have one Notes rendering path: the current `notes` field, joined exactly as it appears in the owner editor. Whitespace and line breaks are preserved. Empty Notes produce no note and no historical fallback. Group descriptions/annotations, source supplements, uncertainty explanations, archived ownership and source prose are not rendered as additional public notes. COMPLETE, unresolved, historical, special-category and owner-created listings follow the same rule. Active variant labels remain where needed to distinguish current inventory groups; literal identifiers/ranges, ordering, Pending and classifications retain their meanings.

The ordinary editor has one Notes field. Its Historical notes section, group annotation paragraphs and uncertainty annotation paragraphs have been removed. Source text is never merged into the editable field. Existing recovery, revision checks, history/Undo and backups remain supported. Search indexes current visible content rather than archived source payloads, descriptions or annotations. The legacy source-note adapter remains an audit utility, with no ordinary browsing/editor rendering path.

## Ritz/Oreo verification

Actual staging record: `p1566-l003`, revision 1, WANT, UV Wantlist. Public display is now:

> Cards I NEED: Blue Border Griffey
>
> Red Border Griffey already owned

The latter is the existing current Notes field, rendered once. “User-confirmed owned variant.” and the separate “Owned: Red Border Griffey” line are hidden. The HAVE group's original description and Red Border Griffey item remain stored unchanged. No staging record was edited to accomplish this refinement.

## Audit and data preservation

[Read-only audit](../foundation/staging/phase353-audit.mjs) and [results](../foundation/staging/phase353-public-audit.json) cover all 265 active staging public projections: 58 contain current Notes, four had source supplements, three had group annotations, and 17 contain uncertainty metadata. Classification and current-note mismatches after adaptation: **zero**. Inputs remain unchanged.

The full 3,394 derived historical collection also passed classification/current-note/input preservation checks. All seven categories, owner-created categories, three Eau Claire listings, the photo listing, 26 Bobblehead listings and seven approved classifications remain intact. Neither archived notes nor unusual source prose are reinterpreted as active entries. Listings whose only descriptive text is archived prose now omit that prose unless it is already in the current Notes field. Existing text actually stored in current Notes remains visible even if originally source-derived; only the owner can choose to edit or clear it.

A disposable SQLite regression verifies that Notes update/clear/Undo changes only the current Notes metadata and its audit history. Original groups, item states, ownership evidence and the complete provenance row are compared exactly before/after; all remain identical. A clear is recoverable through supported Undo. Original Word/raw/Phase 2 data remains unchanged.

## Tests and screenshots

227 tests passed: 71 website/model/render tests; 67 Node backend/model tests; 48 Python foundation tests; 21 protected-source tests; 20 desktop/mobile browser tests. Coverage includes both live-projection and derived-source paths, Ritz/Oreo, exactly one editor Notes field, save/reload, clearing without fallback, Undo, Pending/cancellation, all historical classifications, all categories, COMPLETE/unresolved listings, archived-text search exclusion, read-only public access and authentication/concurrency protections. Desktop/mobile axe WCAG checks reported zero violations and overflow checks passed. The staging owner build and whitespace checks passed.

Browser and backend write tests ran only in disposable local SQLite. No automated write test touched human-review D1.

Screenshots use the tested staging application with the actual source-defined Ritz/Oreo fixture in isolated storage; no owner Notes were changed on human-review staging:

- [Desktop Ritz/Oreo public view](evidence/phase3b5.3/owner-desktop-ritz-public.png)
- [Mobile Ritz/Oreo public view](evidence/phase3b5.3/owner-mobile-ritz-public.png)
- [Desktop ordinary editor](evidence/phase3b5.3/owner-desktop-ritz-editor.png)
- [Mobile ordinary editor](evidence/phase3b5.3/owner-mobile-ritz-editor.png)

## Staging release

[Release verification](../foundation/staging/phase353-release-result.json) records the exact deployed asset match and confirms unchanged record contents/revisions, public projections, history count, sessions and authentication generation. Ritz/Oreo remains revision 1 with both Blue/Red items and the original source description intact. Existing secrets are inherited; private rollback modules remain available.

No unresolved presentation issues were found. This phase performs no source/data migration or cleanup, full historical import, deletion, paid-feature enablement, PIN/session change, production update or cutover. Production/static site and protected historical sources remain unchanged. Stop for human review.
