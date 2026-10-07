# OBC wantlists — read-only website

Reproducible normalized collecting data rebuilt from the user-provided **Wantlists 10-5-26.docx**.
The Word document and the user's 23 reviewed interpretations are authoritative. No external checklists or
Blogger data were used. The Phase 3A public website reads the committed dataset without changing
normalization semantics. Editing and authentication are reserved for later phases.

## Website development

Use Node.js 24 (pinned in `.node-version`) and npm. From the existing `work` checkout:

```sh
npm ci
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
```

Vite prints the local development address. The app is React with plain CSS; all 3,392 records are
searched in the browser, with 30 results rendered per page. No database, credentials, backend service,
or external card database is needed. There are no editing, authentication, Pending, or trade features.

Run the website tests:

```sh
npm test
npm run test:browser
```

The first command runs Vitest model/component tests. The second builds the production site, starts a
temporary local preview server, and runs Playwright on desktop and phone viewports, including tablet
and narrow-phone layout checks and axe accessibility checks. It uses `/usr/bin/chromium` when available;
otherwise install Playwright's Chromium with `npx playwright install chromium`. Set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to use another existing Chromium executable.

Build and inspect the production site:

```sh
npm run build
npm run preview
```

`dist/` contains the static production site and `wantlists.json`. The data asset is a build-time
projection of `data/wantlists.json`: all records and public semantic fields are preserved, while raw
import/audit bulk is omitted. There is no handwritten copy of the dataset. Both development and
production use `site/data-source.js`; `npm run build` refreshes the data asset after an intentional
Phase 2 regeneration. The original Phase 2 file and Word source are not modified by any npm command.
Relative asset paths support a later choice of static hosting; no hosting or deployment is configured.

The maintenance flow is:

```text
raw Word source → import_docx.py → normalization + reviewed corrections
                → data/wantlists.json → website build → browser search and display
```

`site/model.js` handles indexing, selection, facets, and sorting independently of React.
`site/RecordCard.jsx` renders record and component ownership semantics; `site/App.jsx` contains
the read-only browse controls. A future data service can replace the loader without replacing these
public components. No future admin or trade infrastructure has been implemented speculatively.

Search is case/spacing/punctuation tolerant and requires all entered words to match across normalized
fields, names, notes, prefixes, and explicit mixed components. Numeric tokens match exactly: `12` does
not match card `121`. Prefix aliases like `BCP-47` refer only to explicitly listed source cards.
Uncorrected raw wording is not indexed, because it includes the discarded 1993 merged list.

Filters cover the primary status, year, brand, and the dataset's exact categories. Mixed components
retain separate owned/wanted labels within each result; a status filter applies to the record's primary
status. Year filters include explicit year ranges. Unknown years/brands are selectable. Sorting supports
newest, oldest, and alphabetical; dated sorting uses the first year of a range, with unknown dates last.
Long lists can be expanded, and matching card IDs are visible even before expansion.

## Phase 3A findings and validation

See `docs/PHASE_3A.md` for the acceptance checks and maintenance results. The Flagship category
false positive has been corrected in the normalizer using whole-word/phrase matching. Regeneration
changed only the three 2023–2025 Costco Flagship categories to `baseball_cards`; list contents and
statuses remain unchanged. There are now 2,879 baseball-card and 62 non-sport-card records.

For the live development server, run `node tools/check_dev_preview.mjs`. This uses Chromium to check
actual rendering and interactive search/filter behavior independently of the production build.
To test a platform-provided external preview route, set `WANTLIST_PREVIEW_URL` to that URL before
running it. The development server binds to `0.0.0.0:5173` and fails rather than silently moving to
a different port. An external cloud preview still requires the platform to expose/forward port 5173;
starting a local server does not itself configure that route.

The Phase 2 backup archive has been retained. Keep all meaningful changes committed and push `work`
before leaving a cloud workspace. No branch merge is part of Phase 3A.

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
