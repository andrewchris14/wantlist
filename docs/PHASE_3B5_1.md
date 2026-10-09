# Phase 3B.5.1 — Editor defaults and public contact

Approved baseline: `9999362b490e656b9703bc79b5161d14c0646b21`, branch `work`, repository `andrewchris14/wantlist`.

The editor used `content.display_category || 'OBC Wantlist'`, while public browsing resolved missing metadata through the historical ID/category map. Every Save serialized the fallback, even for unrelated changes. List type similarly used raw source uncertainty instead of the effective owner-reviewed classification. The editor now shares public category resolution and a tested, shared effective list-type resolver. Explicit live classifications take precedence over historical defaults. Only fields changed in the editing session are submitted; category/list type are omitted unless deliberately changed. Unmapped records show a category prompt and retain source uncertainty rather than receiving invented defaults.

The backend uses effective classifications to validate the represented inventory while preserving the stored classification when no explicit conversion was requested. Legacy uncertain primary groups remain source-linked and editable under the approved effective type. Pending activation retains a before-state for exact Undo, including the historical limitation. Explicit conversion/replacement, COMPLETE confirmation, revisions, idempotency, atomic history/projections, authorization and Undo remain enforced.

## Audit

[Reproducible audit](../foundation/staging/phase351-audit.mjs) consumes a private, read-only D1 snapshot. [Results and affected IDs](../foundation/staging/phase351-audit-result.json) contain classifications/history references, without card values or credentials.

| Population | Category mismatches before → after | List-type mismatches before → after |
|---|---:|---:|
| 3,394 derived historical listings, simulating legacy owner metadata without newer display fields | 2,807 → 0 | 28 → 0 |
| 267 actual staging stored records/public projections | 8 → 0 | 1 → 0 |

The 2,807 count is the **legacy-metadata fallback risk**, not 2,807 corrupt derived records. The full derived view already has category display fields; direct initialization of those explicit fields was correct. The audit exercises their source-ID mapping when those fields are absent, as in legacy D1 imports. The 28 type discrepancies comprise 21 historical HAVE interpretations and the seven approved decisions. All 3,394 defaults now match public categories and effective types. No historical classification data was rewritten.

Actual category mismatches: `p0531-l001`, `p0581-l001`, `p0645-l005`, `p0672-l001`, `p0694-l001`, `p0730-l001`, `p1566-l003`, `p3128-l001`. The last is a preserved, suppressed original photo source member; it was included in the stored-record audit. Actual type mismatch: `p0023-l001` (effective HAVE, stored uncertainty). These corrections are read-model corrections, not D1 recategorizations.

The reported Football listing is `p0581-l001`, revision 3, HAVE. Its category remains source-derived Football Wantlist, with no category-changing edit in history. Its Pending behavior was tested using an explicit WANT fixture; the actual historical HAVE listing does not offer Pending.

History contained **two** incidental OBC saves on UV record `p1237-l004` at 03:06:35 and 03:07:51 UTC on October 9, each followed by `undo_session`. A third save at 03:08:27 explicitly selected UV Wantlist. The record is currently correct. This corrects the earlier progress update's count: two OBC saves, not three. `p0526-l006`'s explicit Other Stuff metadata agrees with the source mapping. No currently incorrect historical category/type warranted a data correction, so no staging data was changed.

All 2,234 history events were inspected. There were 157 type transitions: 78 legacy metadata edits across 61 owner-created records, 64 explicit replacement events and 15 representation restores. None of the metadata type transitions involved a historical record; they predate this baseline's unified editor. Their history does not establish accidental changes from this bug. Owner-created records and their classifications were preserved; their IDs/event references remain in the audit for review. No blanket reversion was performed.

Historical counts remain 3,394: OBC 583; UV 2,517; Eau Claire Players 3; Milwaukee 8x10 List 1; Brewers Bobblehead 26; Football 62; Other Stuff 202. All seven approved classifications and 1995 JSW separation remain unchanged.

## Contact and screenshots

The compact header displays **Jason Christopherson · jschris@triwest.net**. The email is an accessible `mailto:` link, wraps on narrow screens and is unrelated to authentication. Jason's Want List, vintage styling and OBC attribution remain.

Screenshots use the tested staging application and real historical Football fixture in isolated SQLite, not write-producing tests on human-review D1:

- [Corrected desktop editor](evidence/phase3b5.1/owner-desktop-football-editor.png)
- [Corrected mobile editor](evidence/phase3b5.1/owner-mobile-football-editor.png)
- [Desktop header/contact](evidence/phase3b5.1/owner-desktop-header.png)
- [Mobile header/contact](evidence/phase3b5.1/owner-mobile-header.png)

## Verification and limits

211 tests passed: 21 protected-source tests, 48 Python foundation tests, 66 Node backend/model tests, 60 website tests and 16 desktop/mobile browser tests. Football addition, removal, notes, order and reload retain Football/HAVE. Backend WANT fixtures also cover Pending retention; marking a HAVE entry Pending remains prohibited. Tests cover all seven categories, owner categories, all three types, seven overrides, intentional category moves, confirmed conversions, stale revisions, atomicity, idempotency, supported Undo, email accessibility, read-only public access and special-collection inventory preservation. Desktop/mobile axe WCAG checks reported no violations; no horizontal overflow was observed. The owner build and whitespace checks passed.

Automated writes ran exclusively in disposable local SQLite. No remote benchmark or test write was issued. The new effective-mode lookup remains bounded to the edited record and uses no additional D1 query; transaction statement count limits remain tested. Existing Free-plan CPU concerns documented in Phase 3B.5 remain unresolved: no new remote write benchmark was run against human-review staging to claim a CPU improvement.

[Staging release verification](../foundation/staging/phase351-release-result.json) records the deployed version and exact asset match. Deployment preserves secret bindings and verifies unchanged record contents/revisions, history count, sessions and authentication generation. Worker rollback modules are retained privately. No data migration or cleanup was necessary for this phase. Production/static site and protected Word/raw/Phase 2 sources remain unchanged, and no full import, paid features, PIN/session rotation or production cutover was performed.

Stop for human review on staging. Older owner-created practice/test history remains preserved; this phase does not authorize guessing at its intent or deleting those records.
