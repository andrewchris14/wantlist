# Phase 3B.1 additional lifecycle and query review

No Cloudflare resource, remote database, deployment, editor or live-data switch
was created. Historical source/data and the Phase 3A site remain unchanged.
All new owner-operation helpers are LOCAL reference/test code, not API routes.

## Future owner-created records

The schema allows `records.import_id=NULL`. New IDs and timestamps identify
owner-created records; creation is audited. No `provenance` or `import_batches`
row, Word reference, source wording or correction decision is invented.
Year/range text, brand, set, category, notes, prefixes, uncertainty, numbered
and explicitly named items, WANT/HAVE groups and sublists are supported.

The fictional 2027 Topps test creates wanted 12/18/47 and owned 9/24, retrieves
them, later adds 92/99, marks 12 Pending, receives 18, returns 12 to Wanted,
edits metadata/notes, marks/unmarks Uncertain, removes/restores an incorrect
item, receives remaining wanted cards, marks/unmarks Complete, soft-deletes and
restores the record, and round-trips private JSON into a separate empty database.
Public JSON and CSV include it. The test verifies all **18 ordered history
events**, current states, revision changes and absence of historical provenance.
Additional tests cover named postcards, prefixes, year ranges, sublists,
duplicate rejection, authorization, revision conflicts and Complete safeguards.
Complete cannot silently hide wanted/pending cards; it must be unmarked before
reactivating or adding wanted cards. No missing cards are inferred from HAVE.

This proves the schema/local lifecycle; a deployed editing API and Dad-facing
UI do not exist yet. Local `actor='owner'` is a trusted test/operator argument,
not an authentication mechanism. A future API MUST derive the owner identity
from the protected session, never accept a client-provided actor.

## Reproducing the local measurements

```sh
npm run test:foundation
python -m foundation.review_usage --db foundation/.local/another-new-review.sqlite
```

Use a NEW filename; the reviewer refuses to overwrite existing databases.
Fresh schema setup applies migrations 0001 and 0002. Older ignored disposable
databases are not automatically upgraded or overwritten.
`foundation/query-review.json` contains every parameterized SQL template,
EXPLAIN QUERY PLAN result, query count, returned-row count, logical table writes,
SQLite VM instruction count and size/growth experiment. It contains no secrets
or actual private trade data. SQL plans omit parameter values.

SQLite's **rows returned** are not rows examined or D1 billable rows read.
`total_changes` counts logical table writes but not index maintenance. VM
instructions are diagnostic work units, NOT row reads. D1 estimates below
include allowance for indexed probes, joins, foreign-key checks and indexes;
actual `meta.rows_read/rows_written` require approved staging and remain untested.

## Index/query findings

| Common operation | Supporting index/access path |
| --- | --- |
| Open/update/delete/restore one record | `records` primary key on `id` |
| List one record’s groups or allocate a sublist position | Existing UNIQUE `(record_id,kind,position)` |
| List one group’s items in field/position order; allocate next position | Existing UNIQUE `(group_id,field_key,position)` |
| Find a card/duplicate within known groups | New `items_group_value(group_id,value)` |
| Update/delete/restore one known item | `items` primary key; group/record primary-key joins |
| Recent Changes (all records), LIMIT 20 | New `history_recent(created_at DESC,id DESC)` |
| Recent Changes (one record), LIMIT 20 | New `history_record_recent(record_id,created_at DESC,id DESC)` |
| Login/session lookup/update | Existing primary keys on owner ID, session token hash and throttle bucket |

Migration 0002 removes redundant `groups_record` and `items_group` prefix
indexes. Their existing UNIQUE indexes already cover those lookups/orderings.
Only exact item lookup and the two real recent-history access paths get new
indexes. There is no global item-state index or index on updated timestamps,
notes, year or category. Session cleanup/index needs can be reviewed later.

Routine opening now uses `get_record(id)`, not the bulk `reconstruct()` importer
helper. A known-set card lookup explains as indexed SEARCH of that record’s
groups, followed by indexed SEARCH of `(group_id,value)`. State changes use
item/record primary keys. Tests prohibit global item/group scans in routine
operations, including removal/restoration.

The global Recent Changes plan says **SCAN ... USING INDEX history_recent**:
this is an ordered index walk stopped by LIMIT 20, not a full-history scan.
With 1,000+ history events it returns 20 rows in 248 VM instructions. Per-record
history uses indexed SEARCH and returns 20 in 278 instructions; neither sorts
all history in a temporary B-tree.

Intentional whole-data reads remain: initial owner catalog, complete exports,
reconciliation, and a full public-snapshot build. They are not per-card actions.
The initial catalog reads approximately 3,392 record summaries, not all items;
later set-search/filtering in memory performs zero SQL. Full snapshot generation
was changed from repeated record/group/item traversal to THREE bulk table reads,
each once. It is not connected to the website or a request handler.

Adding 20 cards now takes **9 SQL statements**, using bounded duplicate probes
and inserts of at most 10 rows/60 bound values per statement, instead of one
round-trip per card. Creating a 20-card set takes 8 statements. Actual D1
statement/binding/CPU limits must still be verified before implementing the API;
large input batches will need an explicit tested bound/queued workflow.

## Per-action measurements and D1 estimates

The sample future set initially has 5 cards and 2 groups. The largest historical
record is **2007 Upper Deck (`p1237-l004`)**, with 526 literal rows. Measurements
exclude fetching a revision already held by the form. Mutation estimates below
exclude the separately listed session validation and any later public publication.

| Action | Local SQL statements | Local returned rows | Local logical writes | Estimated D1 rows read | Estimated D1 writes, including indexes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Login SQL (not password CPU) | 4 | 3 | 3 | 5–15 | 4–6 |
| Session validation | 1 | 1 | 0 | 2–4 | 0; daily last-seen touch adds 1 |
| Initial owner catalog | 1 | 3,393* | 0 | ~3,400–6,800 | 0 |
| Subsequent search/filter in memory | 0 | 0 | 0 | 0 | 0 |
| Open small set | 4 | 8 | 0 | ~8–20 | 0 |
| Open largest historical set | 3 | 528 | 0 | ~530–1,100 | 0 |
| Find one card in known set | 1 | 1 | 0 | ~3–10 | 0 |
| Received | 6 | 3 | 3 | ~8–20 | ~6–10 |
| Pending | 6 | 3 | 3 | ~8–20 | ~6–10 |
| Pending back to Wanted | 6 | 3 | 3 | ~8–20 | ~6–10 |
| Add 2 wanted cards | 8 | 5 | 4 | ~10–25 | ~13–20 |
| Add 20 wanted cards | 9 | 5 | 22 | ~30–80 | ~85–100 |
| Edit notes | 3 | 1 | 2 | ~3–8 | ~5–8 |
| Create set with 20 wanted cards | 8 | 2 | 23 | ~25–80 | ~89–110 |
| Remove/restore one item | 5 / 7 | 2 / 3 | 3 | ~6–20 | ~6–10 |
| Delete/restore one record | 4 | 2 | 2 | ~3–8 | ~5–8 |
| Recent Changes, LIMIT 20 | 1 | 20 | 0 | ~20–40 | 0 |
| Full public snapshot generation | 3 | 66,006* | 0 | ~66,000–75,000 | 0 for generation; publication writes separate |

*The measurement database includes disposable future records/cards. The pristine
baseline full-export total is 3,392 + 3,458 + 59,104 = **65,954** table rows.
Duplicate probes may return no rows while still visiting indexed entries;
foreign-key checks on inserts likewise are not included in returned-row counts.
These are conservative estimates, not billing measurements or hard guarantees.

## Write amplification

Received/Pending/back-to-Wanted perform 3 logical writes: item update, record
revision update and history insert. Item state/time and record revision/time
are NOT indexed. The history insert adds its primary key and two history indexes:
approximately **6 row/index writes**, budgeted at **6–10** pending real D1 data.

Each new item has its base row plus primary key, group/field/position UNIQUE
index and group/value index: approximately 4 writes per item. With one record
revision update and one history insert (4 writes), adding N items to an existing
group is approximately **4N + 5**: 13 for 2, 85 for 20. A newly needed group adds
about 3 writes. Creating a new set adds the record and group plus history:
approximately **4N + 9**, or 89 for 20. Safety/history remain worth that cost.

## Free-tier planning and public search

Use the user-supplied assumptions ONLY: 5M rows read/day, 100K rows written/day,
500 MB per database, 5 GB total storage, 7-day Time Travel, and hard failures
rather than automatic paid overages. Actual account/plan settings remain a gate.
This review does not independently certify those terms or other Worker limits.

Routine editing is comfortably small. Even 200 daily operations budgeted at
110 writes each would be about **22,000 writes/day**, well below 100K. Ordinary
single-card operations would usually be much less. Add auth/publication/backup
costs to a staging budget; do not confuse local logical writes with D1 charging.

**Initial migration is not ordinary editing.** A rough indexed-write budget is
4 × 59,104 item rows, 3 × 3,458 groups, 2 × 3,392 records and 2 × 3,392 provenance
rows, plus tiny metadata: approximately **260K row/index writes**. That exceeds
100K/day if the import is metered like ordinary writes. Plan at least **three
quota days**, bounded batches and resumable initialization, while the existing
static site remains live. Verify whether native D1 import has different metering;
do not assume an exemption, enable paid billing or weaken data fidelity to rush
the import. Remote restore/index creation also needs a quota-aware recovery plan.

**Do NOT regenerate the full dataset on every save.** At ~66K reads per rebuild,
200 rebuilds would use about **13.2M reads/day**, exceeding 5M. Full builds are
initialization/recovery/occasional integrity work; later publication should
update only the affected record’s bounded public chunk and manifest. Coalescing
or an explicit rate budget can bound occasional full rebuilds. As an example,
12 full builds/day would consume ~792K reads plus ordinary traffic, but is not
a substitute for incremental publication.

Public visitors should fetch a cached/static sanitized snapshot and search,
sort and filter in the browser: **no D1 request for each keystroke**. Static/edge
cache hits cause zero D1 reads. Cache misses should read published bounded
chunks, not regenerate the entire wantlist. Polling a tiny revision manifest
can identify updates. Future public chunk format/atomic publication are design
requirements, not activated features in this review.

The full foundation JSON snapshot measures ~10.53 MB uncompressed, unlike the
smaller Phase 3A projection. Do not assume it can be stored in one D1 value or
returned/constructed in one free Worker execution. Verify row/value/response
and CPU limits, use bounded chunks (for example <=256 KiB, subject to actual
limits), retain whole-client search, and measure compression before cutover.
Retain a bounded active/previous snapshot rather than a full 10 MB copy per edit;
the item history already supplies fine-grained recovery.

## Actual size and growth experiment

- Baseline with justified indexes: **22,695,936 bytes** = 22.70 decimal MB /
  21.64 MiB; about **4.54%** of a conservative decimal 500 MB allowance.
- Headroom: **477,304,064 bytes**, approximately **477.3 MB / 95.46%**.
- After representative edits, 1,000 extra item-history events, 100 new sets
  with 20 wanted items each, and 50 Pending changes: **25,534,464 bytes**
  (25.53 MB), leaving approximately **474.47 MB**.
- Measured 1,000-history-event growth: **1,458,176 bytes** (~1.46 MB).
- Measured 100-new-set/2,000-card growth including creation history:
  **1,261,568 bytes** (~1.26 MB).
- Measured 50 Pending updates WITH their history: **77,824 bytes** (~0.078 MB).

These are synthetic local SQLite file/page measurements, not remote allocation
guarantees. Larger notes, private details, different histories and fragmentation
change growth. Rough planning: 10K similar history entries might add ~10–20 MB;
1K similar 20-card sets might add ~10–20 MB. Do not promise indefinite history
within a fixed free allowance. Monitor storage and approve export/archival policy
well before limits; Time Travel is short recovery, not an independent backup.
One active and one previous ~10.53 MB public snapshot could add roughly another
21 MB plus chunk/index overhead. This still leaves substantial room, but must
be included in the real staging storage budget.

`dbstat` measurements and all object/index page sizes are in the JSON report.
The replacement exact-item index is ~2.33 MB in the grown sample; history indexes
are ~0.44 MB combined there. No speculative status/category indexes were added.

## Remaining gates before Phase 3B.2

Validation after these changes: **49 foundation tests** (34 Python + 15 Node),
**21 Phase 2 checks**, **36 website tests**, **16 desktop/mobile browser checks**
and the production build all passed. No checks were disabled or weakened.
All 24 protected source/data/site/config files checked are byte-identical to
the approved static baseline. The public loader remains unchanged.

Confirm Free account/billing/inactivity settings and other Worker/D1 limits.
Resolve the previously documented password-verifier/CPU compatibility gate.
Then measure actual D1 query metadata and implement/verify atomic mutation
batches on the real runtime: Python transactions do not prove Worker/D1 atomic
semantics. Approve incremental bounded public publication, independent backup
destination and eventual editor UX. None of these steps began in this review.
