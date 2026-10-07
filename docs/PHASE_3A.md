# Phase 3A: public read-only wantlist

Baseline: `6f74ee6a0b0403f4fe87ab7d090a40554f3d1ea4` on `work`.
The Phase 3A baseline preserved Phase 2. The subsequent user-approved maintenance correction
regenerated the dataset to fix exactly three categories, leaving the raw source, card lists, and statuses unchanged.

## Implemented behavior

- React/Vite static site, system fonts, CSS baseball-card motif, and no third-party requests at runtime.
- Search over normalized year, brand, title, names, card IDs/ranges, notes, category, prefixes, and explicit components.
- Case, whitespace, accents, and punctuation are normalized. All query words must match; numeric tokens are exact.
- Facets use the actual dataset: four primary statuses, 46 brands, 18 categories, source years/ranges, and unknown year/brand options.
- Newest, oldest, and alphabetical sorting; range start years determine chronological order, and unknown years remain last.
- Thirty results per page; long item lists expand on request and searched IDs are exposed without expansion.
- HAVE lists explicitly state ownership and are never turned into missing-card complements.
- Complete means nothing currently needed. Uncertainty retains the source statement and ownership context.
- The Ritz/Oreo record shows wanted Blue Border Griffey and owned Red Border Griffey in separate labeled sections.
- Explicit mixed/sublists, non-card material, notes, completed-set descriptions, and source references remain accessible.
- Semantic headings/labels, text status badges, keyboard controls, focus styles, skip link, live result counts, and responsive layouts.
- Loading, error/retry, empty results, and missing optional data are handled without editing data.

## Validation evidence

- 36 Vitest tests: real dataset loading, requested searches, exact card tokens, facets, sort/reset, primary status rendering,
  mixed variants, long lists, malformed optional fields, async loading/retry, and pagination.
- 16 Playwright checks against the production build, across desktop and phone projects. They also exercise widths
  320, 768, and 1024, representative eras, ownership distinctions, filtering/sorting/reset, and keyboard navigation.
- Automated axe checks cover WCAG 2 A/AA and 2.1 AA on representative search results.
- Desktop and mobile screenshots are visually inspected, including the Griffey mixed record. Search appears before the
  explanatory guide to make it easier to reach on phones; owned matched items use their own blue treatment and labels.
- All 21 Phase 2 tests pass (the original 20 plus a category-boundary regression); original Word source and raw import remain unchanged, and dataset differences are limited to the three approved category changes.
- The production build emits all 3,392 records and static HTML, JS, and CSS. No deployment has been performed.
- In this environment, indexing took about 121 ms and 100 representative selections averaged 2.6 ms each.
  These are local measurements, not guarantees for every device. Public JSON is about 2.38 MB uncompressed,
  about 311 KB with gzip; compression depends on the eventual host.

## User-approved category correction

The non-sport matcher now uses whole-word/phrase boundaries, while preserving plurals such as
Westerns, Valentines, and Presidents. This avoids matching “flags” inside “Flagship” and similar
fragments such as “jets” inside “objects”. The normalizer was rerun; no generated JSON was patched.

Exactly these three categories changed from `non_sport_cards` to `baseball_cards`:

| Record | Title | Source reference |
| --- | --- | --- |
| `p0672-l001` | 2025 Topps Flagship (Costco) | paragraph 672, line 1 |
| `p0694-l001` | 2024 Topps Flagship (Costco Exclusive) | paragraph 694, line 1 |
| `p0730-l001` | 2023 Topps Flagship (Costco Exclusive) | paragraph 730, line 1 |

Total records remain 3,392; WANT 997, HAVE 1,366, COMPLETE 1,001, UNCERTAIN 28, NEEDS REVIEW 0.
Baseball cards changed 2,876 → 2,879; non-sport cards changed 65 → 62. All other categories are unchanged.
The original Word document and raw import are unchanged. The existing 36 website unit/component and
16 production-browser checks pass with the regenerated dataset.

## Live development verification

The development server uses `npm run dev -- --host 0.0.0.0 --port 5173 --strictPort`.
`tools/check_dev_preview.mjs` checks rendered homepage, search, all filters, visible result cards,
Griffey search, HAVE filtering, and the corrected Flagship category on the actual development server.
It saves a screenshot and fails on page errors. `WANTLIST_PREVIEW_URL` can target an externally
provided platform preview route instead of the internal live server.

Internal live-development rendering and interactions are verified in Chromium. This session exposes
no cloud preview/open-port tool or external preview URL, so the Codex UI forwarding route cannot be
verified here. This is a verification/access limitation, not evidence of a browser-specific failure.
The server's host and port are pinned to prevent silent fallback to a port different from the forwarded one.

## Limitations reserved for future decisions

- Status filtering uses the primary record status; mixed owned/wanted components are searchable but are not separate result rows.
- Brand/category metadata is conservative and inherited from Phase 2; missing values remain selectable rather than guessed.
- Explicit source ranges and open-ended requests remain expressions. Exact numeric search does not enumerate range members.
- No typo/fuzzy search or saved/shareable filter URLs yet. Unknown/range dates keep their original source labels.
- The site loads the collection once before client-side searching; gzip/Brotli can be enabled when hosting is chosen.
- No editing, authentication, PINs, Pending status, accounts, trade workflow, database, Blogger synchronization,
  external checklist research, deployment, or Phase 3B functionality is included.
