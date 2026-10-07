# OBC wantlists — Phase 2

Reproducible normalized collecting data rebuilt from the user-provided **Wantlists 10-5-26.docx**.
The Word document and the user's 23 reviewed interpretations are authoritative. No external checklists or
Blogger data were used. Website development is intentionally outside this phase.

## Rebuild and validate

Python 3.10+ is the only prerequisite; no third-party packages or network access are needed.
From the existing checkout (cloud tasks already have an isolated workspace; no worktree is needed):

```sh
python tools/normalize_wantlists.py
python tools/validate_wantlists.py
```

The normalizer first verifies the original document's pinned SHA-256, reimports it, then regenerates
JSON and Markdown. The validator runs all recreated regression checks, returns a failing exit code on
failure, and saves `data/VALIDATION.md`. The suite can also run with
`python -m unittest discover -s tests -v`.

## Repository files

- `data/raw/Wantlists 10-5-26.docx`: exact original binary; do not edit.
- `data/raw/paragraphs.json`: reproducible import with original text, line breaks, bold runs, and hyperlinks.
- `tools/import_docx.py`: standard-library DOCX importer and source checksum.
- `tools/source_corrections.py`: wording-matched, user-confirmed corrections and decision ledger.
- `tools/normalize_wantlists.py`: parser, source relationships, structured data, and review generator.
- `data/wantlists.json`: generated dataset, context, and complete source-line ledger.
- `data/DATA_REVIEW.md`: counts, resolved decisions, and preserved uncertainty.
- `tests/test_normalization.py`: all recreated Phase 2 validation checks.
- `tools/validate_wantlists.py` and `data/VALIDATION.md`: validation runner and saved outcome.

## Schema and interpretation

The top-level JSON object contains `schema_version`, `source`, `policy`, `correction_decisions`,
`records`, `context_notes`, and `source_ledger`. Records have stable source-location IDs;
`year` preserves a year/range string, including uncertain dates, and `brand` is nullable search metadata.
`set_name` retains the titled identity and variants, including the year and inherited group title.
`category` and `section` distinguish baseball, football, tobacco cards, and other collectibles.

Primary `list_type` is one of `want_list`, `have_list`, `complete`, `uncertain`, and `needs_review`.
`source_list_type` retains the ownership/request designation beneath an uncertain completion statement.
`card_numbers` holds source identifiers as strings, preserving prefixes/suffixes and panel identifiers.
`items` holds named collectibles; `card_ranges` stores explicit source ranges without expanding them.
`prefixes` stores heading prefixes such as HW-, BCP-, SDC-, and SCC-. `set_size` is nullable;
no checklist size is researched or inferred. Carreras 1937 is 54 by user decision, and the Gallaher
1934 Red Back count is unknown.

`mixed_lists` and `sublists` preserve distinct explicit owned/wanted components and labeled lists.
They contain only source-stated information, including explicitly mentioned uncertain wants;
**HAVE lists are never converted into calculated missing-card lists**. A complete primary record has
no listed cards/items/ranges. Partial completion and requested upgrades remain in notes or components.
`completed_sets`, when present, describes named completed sets rather than wanted items.

`payload`, `normalized_wording`, `notes`, `uncertainty`, `source_wording`, `source_refs`, and
`corrections` retain details and provenance. Source refs use one-based paragraph and line numbers,
including empty lines. Original wording is always preserved alongside interpreted wording.
`review_status` and `review_reasons` distinguish accepted, user-resolved, and genuinely unresolved cases.
Uncertainty is not automatically a parser error or a request for human review.

Every nonempty source line is accounted for in `source_ledger`. Broad collecting interests,
updates, acknowledgments, and historical links remain as context. Autographs and player-based
requests are grouped records; bobbleheads are grouped by year. Group headings are not duplicate sets.
Word line breaks are preserved so adjacent entries cannot accidentally merge. Child WANT designations
override inherited HAVE headings. Source-stated possible missing cards remain separate from owned cards.

## Remaining data considerations

Uncertain dates, claimed completion, potential variants, and source-spelled names remain unchanged;
the document does not justify resolving them externally. Brand/category labels are conservative and
should be refined from source wording if needed. Explicit ranges and open-ended requests stay as
expressions instead of invented enumerations. The football 1993 Topps wantlist and baseball 1993
Topps complete set are distinct records, not duplicates.

Never manually edit generated JSON to correct source interpretation: change the normalization or
reviewed correction logic, then regenerate and run the checks.
