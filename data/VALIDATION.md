# Phase 2 validation

Commands: `python tools/normalize_wantlists.py` then `python tools/validate_wantlists.py`.

Result: **PASS**

- Tests executed: 21
- Failures: 0
- Errors: 0
- Skipped: 0
- Expected failures: 0
- Unexpected successes: 0
- Records: 3392
- List types: {'complete': 1001, 'have_list': 1366, 'uncertain': 28, 'want_list': 997}
- Source SHA-256: `75d968d267b9ee551e3d45343d7ce8966e7ee81f82ff26a62eac5a7239e3cda7`

Checks cover source references and complete line coverage, schema and IDs, all 23 reviewed decisions,
merged-heading boundaries, number splits, blank items, HAVE ownership, completion, uncertainty,
mixed lists, non-card material, and byte-for-byte deterministic generated output.

No prior test files survived; these are the recreated checks. No website was built.
