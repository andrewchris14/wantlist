# Phase 3B.5.2 — Compact public labels and readable notes

Baseline verified: `568cc5a84dfe1aa60ed3ab5d4278d3134d41f513`, clean `work` checkout of `andrewchris14/wantlist`, matching fetched remote.

The public adapter previously promoted retained owned WANT entries and superseded groups into “Historical owned information” notes. It now presents only the listing's current primary inventory, Pending for WANT listings, and relevant notes. Received entries and owner-created secondary inventories remain accessible in the authenticated editor/history and recoverable with supported Undo, but are not promoted into public notes. HAVE inventories also exclude stale wanted/pending states.

All public card/item inventory labels now use **Cards I HAVE**, **Cards I NEED**, **Items I HAVE**, and **Items I NEED**. WANT list / HAVE list / COMPLETE and Pending retain their meanings. Technical “Historical owned/wanted information”, “Historical note”, “Original source information” and “Original wording” prefixes have been removed from staging public templates. Unclassified records retain their classification and use the neutral public label **Notes**. Owner-only history/editor terminology remains available.

Genuine source prose is retained verbatim as readable paragraphs. Original opposite-meaning source groups remain concise notes with ordinary **Owned** or **Needed** wording and their actual variant labels/qualifications. Source group/item identities distinguish these from later owner additions and received remnants; no records, items, source fields, classification or provenance were rewritten. The derived-data browsing fallback follows the same presentation rules and does not create a second editable/public inventory for source supplements.

## Read-only staging audit

[Audit script](../foundation/staging/phase352-audit.mjs) and [results](../foundation/staging/phase352-public-audit.json) cover all 265 active public projections observed at the start of this task:

- 24 WANT records contained retained owned remnants, now omitted publicly.
- 69 records contained retained owner-created secondary groups, now omitted publicly.
- Four records retain relevant original source supplements: `p0010-l001`, `p0136-l001`, `p0526-l006`, `p1566-l003`.
- Original input objects and owner notes remain unchanged during adaptation.

The actual `2028 Bowman Chrome Test` record is `owner-record-a38f266f-8883-4579-a2fb-e1c3f2f62fea`, revision 19. Its public view now shows **Cards I NEED: 4, 6, 8, 10** and **just collecting the first 10 cards**. The retained owned `2` remains in storage/recovery and is omitted from the public view. No staging data cleanup was performed.

The full derived historical collection remains 3,394 listings, with all seven categories, seven approved classifications, three Eau Claire listings and 26 Bobblehead listings intact.

## Verification

219 regression tests passed: 66 website/model/render tests; 66 Node backend/model tests; 48 Python foundation tests; 21 protected-source tests; 18 desktop/mobile browser tests. Coverage includes the Bowman example, current WANT/HAVE inventory, Pending accuracy, owner notes, meaningful historical prose, original source mixed meanings, all seven categories, special item labels, default preservation, Undo, authentication/public read-only access, concurrency protections, and desktop/mobile accessibility. Axe WCAG checks reported zero violations and overflow checks passed. The owner build and whitespace checks passed.

Browser writes ran only against disposable local SQLite. Adding the Bowman fixture changed the first UV row, so the existing long-list browser regression was adjusted to select 2007 Upper Deck explicitly rather than assume the first row was the large list. No automated test writes were issued to human-review D1.

Screenshots of the tested staging application in isolated storage:

- [Desktop Bowman public view](evidence/phase3b5.2/owner-desktop-bowman-public.png)
- [Mobile Bowman public view](evidence/phase3b5.2/owner-mobile-bowman-public.png)

[Release verification](../foundation/staging/phase352-release-result.json) records the exact deployed asset match and verifies unchanged record contents/revisions, history count, sessions and authentication generation. Staging public projections are also compared byte-for-byte before/after deployment, including the recoverable Bowman owned entry. Existing secrets are inherited, and rollback modules remain private.

No unresolved presentation exceptions were found. Original source qualifications intentionally remain plain notes; unclassified practice records display Notes rather than an invented list type. Production/static site, protected Word/raw/Phase 2 data, existing PIN/secrets/sessions and historical sources remain unchanged. No full import, paid feature, deletion or production cutover was performed. Stop for human review.
