# Local Cloudflare Free follow-up — owner review

This follow-up starts from `6412d76` and the Phase 3C.6 optimization in
`e3342c2`. Recurring hosting must remain **$0/month**. No Cloudflare API call,
D1 query, remote test, deployment, historical import, practice archival, staging
change or backup operation was performed. GitHub source commits are the only
remote work authorized here. Backup preparation remains postponed.

## Browser index-page 404

The actual Worker index route still has no 404 branch: valid cursors return 200,
including an empty final page; caught SQL failures return 503. Local checks now
exercise all **3,394 approved public listings**, seven pages, seven categories,
representative search and year/manufacturer filtering through the built browser.
The existing public display manifest is read into RAM and adapted for search;
it is not imported into D1 or a historical SQLite database. Separate synthetic
SQLite tests execute the real pagination SQL and verify authentication gates.

The loader rejects oversized/malformed pages, overlapping IDs and repeated or
inconsistent continuation cursors. It publishes records only after every page
succeeds. A simulated HTML 404 on page three produces an empty collection and
an explicit Retry; Retry starts a fresh seven-page load. There is no automatic
retry that could hide failures or consume quota repeatedly. Successful browsing
and existing editing controls retain their behavior.

Failed browser requests retain status, route, CF-Ray, Server and Content-Type
on the thrown error, plus the failing index page number/cursor. The disposable
HTTP review harness can retain the exact public index URL, those allowed headers
and a response SHA-256; it retains neither response bodies nor cookies or request
credentials. These evidence fields are tested without opening a connection.

The prior remote 404's cause remains **unproven**. Routing/endpoint availability
or an intermediate HTML response remains a plausible explanation; historical
size and later valid cursors do not reproduce it locally. Do not change production
routing based on that hypothesis. A future failure needs the exact URL and these
response fingerprints, correlated with the same invocation's Worker logs.

## Worker work and large owner responses

Phase 3C.6 already removed the 500-by-inventory scans, repeated per-item position
lookups and redundant projection rebuilds responsible for excessive Save query
work. This follow-up preserves those SQL improvements. Validation now reuses
allowed-value Sets and checks trimmed addition duplicates in per-group Sets,
avoiding a second array of concatenated group/value strings. Limits remain
**500 changes plus 500 additions in one atomic transaction**. No UI limit or
multi-request partial Save was introduced. Revisions, idempotency, Pending,
removed state, history, provenance, rollback and Undo remain covered by tests.

The previous owner query returned the entire inventory as one encoded D1 value.
Retained removed entries accumulate after Save/Undo, so that value can grow beyond
D1's documented 2 MB value/row limit. The query now returns encoded headers and
position-bucket chunks in **one consistent SQL statement**, assembled as JSON
text without constructing/re-serializing thousands of JavaScript item objects.
The schema permits three inventory fields and unique positions per group/field;
32-position buckets contain at most 96 entries, preserving the existing order.
All active and removed entries are returned; nothing is capped or silently omitted.

This is a deliberate safety tradeoff, not a free performance win: more result
rows, local SQL instructions and string assembly replace the single large value.
Unusually large individual legacy values or header metadata could still approach
D1 limits; item-count chunking is not an unlimited-byte guarantee. The tests cover
approved field types/escaping and 500-character Unicode additions, plus a
10,000-entry synthetic owner response exceeding 2 MB overall. Every encoded result
cell stays below 512 KB in that fixture. Maximum Save adds 500 entries, replay
changes nothing, and Undo exactly restores prior items while retaining additions
as removed. No real historical records were imported for this check.

## Local evidence

Machine-readable evidence: [local-free-followup.json](evidence/local-free-followup.json).
SQLite VM instructions count query/trigger work, **not billed D1 rows**:

| Operation | Approved Phase 3C.6 | Follow-up |
| --- | ---: | ---: |
| Owner open, 526 active / 1,503 removed | 91,916 | 152,724 |
| Notes Save | 640 | 640 |
| Normal combined Save | 50,591 | 50,591 |
| Maximum combined Save | 241,736 | 241,736 |
| Large Undo | 88,943 | 88,943 |

Owner open remains one SQL statement; its SQL-work increase is about 66%.
The cost checker requires an **explicit** owner budget of 1.8 times the original
pre-optimization baseline for this change; existing Save/Undo budgets remain.
The original default checker budget is unchanged. Maximum Save still uses 734,496
bound-parameter bytes, versus 972,528 before Phase 3C.6.

The predecoded synthetic D1 replay measured median Node process CPU per operation
(over five samples of 100 iterations): owner open **0.003 → 0.593 ms**, Notes Save
**0.111 → 0.074 ms**, maximum Save **3.758 → 3.576 ms**. The owner response is
1,194,225 bytes in both versions; result rows change from 1 to 66, with a largest
chunk of 22,945 bytes. CPU samples overlap and prior local runs varied materially;
**no reliable maximum Save speedup is established**. Against the original
pre-Phase-3C.6 object-building owner implementation, the separate 200-iteration
transport comparison measured 4.010 → 0.698 ms, with equal response semantics.
Neither benchmark includes D1 transport/response decoding, HTTP/authentication or
Cloudflare scheduling. These are **not actual Worker CPU measurements**.

Validation passed: **84 foundation Node tests**, two safe-response-evidence Python
tests, two fully intercepted browser tests, owner Vite build, and synthetic SQL
budgets. The build did not invoke the display importer or a Cloudflare operation.
Completed historical importer rehearsals were not repeated.

Local reproduction (developer commands, no Cloudflare access):

```sh
mkdir -p work/phase3c6-approved work/phase3c6-baseline
git archive 6412d76 foundation/staging | tar -x -C work/phase3c6-approved
git archive 1aa32e1 foundation/staging | tar -x -C work/phase3c6-baseline
node tools/profile_edit_queries.mjs baseline work/phase3c6-baseline
python tools/measure_sql_work.py baseline
node tools/profile_edit_queries.mjs approved work/phase3c6-approved
python tools/measure_sql_work.py approved
node tools/profile_edit_queries.mjs followup
python tools/measure_sql_work.py followup
python tools/check_edit_query_cost.py baseline followup --owner-ratio 1.8
node tools/measure_local_cpu.mjs work/phase3c6-approved
node tools/measure_owner_transport.mjs work/phase3c6-baseline
node --test foundation/tests/*.test.mjs
python -m unittest foundation.tests.test_response_evidence -v
node_modules/.bin/vite build --config owner/vite.config.js
node_modules/.bin/playwright test --config owner/local-full.config.js
```

Ignored `work/` files contain only synthetic local traces/databases. The new
browser suite has no relay, server, Cloudflare credentials or remote requests.
It requires Chromium's local sockets, using supported per-command permissions in
restricted environments. Do not run `free_http_review.py` to reproduce these
local tests: its broad remote review is outside this phase's authorization.

## Before the next small remote test

The reported five-million-read Free daily limit was reached. **Do not remotely
query or test now.** Owner review must precede confirmation of Free billing and
account-wide read/write headroom, including a separate migration reserve.
Then explicitly authorize the disposable-only procedure in
[PHASE_3C6.md](PHASE_3C6.md#smallest-future-remote-verification-not-authorized-or-run-here):
verify Worker name, D1 UUID/binding and isolation flags; stop on mismatch; enable
once; probe the actual index route; establish a session; collect seven raw
owner/Notes/normal/maximum Save+Undo invocations and two diagnostic maximum
Save+Undo invocations. Reserve 100,000 reads/10,000 writes after migration; stop
benchmarking at 20,000 diagnostic reads or a 10 ms raw CPU breach. Setup,
authentication, migration, cleanup and metrics queries need separately bounded
budgets. Always disable the endpoint and remove temporary instrumentation even
when blocked. No remote endpoint was enabled by this follow-up.

Apply the approved performance SQL and matching Worker modules only to verified
disposable storage. Rebuild the owner assets and include that build in the future
disposable release; the checked-in fallback `editor-assets.js` was not replaced
or deployed here. Do not invoke human-review staging release/maintenance scripts
as a shortcut. Do not repeat the broad Phase 3C.5 harness, reseed the full collection
or create a 10,000-entry remote fixture for the initial CPU test.

If the readiness probe fails, capture the new safe response evidence and stop.
A separate seven-page browser walk is optional after approval; it is not needed
for the initial four-route CPU verification. A passing one-shot test would justify
review of a small repeated sample, not prove reliable Free hosting. Actual updated
Worker CPU, billed reads/writes, concurrent editing cost, and the remote 404 cause
remain unresolved. A verified recoverable backup outside Cloudflare is still
required before destructive staging changes, archival or historical import;
Google Drive is optional, and backup storage was not implemented in this phase.
