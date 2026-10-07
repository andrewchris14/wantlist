"""Run all recreated Phase 2 checks and save the current validation outcome."""
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    data = json.loads((ROOT / 'data/wantlists.json').read_text())
    counts = Counter(r['list_type'] for r in data['records'])
    lines = ['# Phase 2 validation', '',
             'Commands: `python tools/normalize_wantlists.py` then `python tools/validate_wantlists.py`.', '',
             f"Result: **{'PASS' if result.wasSuccessful() else 'FAIL'}**", '',
             f'- Tests executed: {result.testsRun}',
             f'- Failures: {len(result.failures)}', f'- Errors: {len(result.errors)}',
             f'- Skipped: {len(result.skipped)}',
             f'- Expected failures: {len(result.expectedFailures)}',
             f'- Unexpected successes: {len(result.unexpectedSuccesses)}',
             f"- Records: {len(data['records'])}",
             f"- List types: {dict(sorted(counts.items()))}",
             f"- Source SHA-256: `{data['source']['sha256']}`", '',
             'Checks cover source references and complete line coverage, schema and IDs, all 23 reviewed decisions,',
             'merged-heading boundaries, number splits, blank items, HAVE ownership, completion, uncertainty,',
             'mixed lists, non-card material, and byte-for-byte deterministic generated output.', '',
             'No prior test files survived; these are the recreated checks. No website was built.', '']
    for case, error in result.failures + result.errors:
        lines += [f'## {case}', '', '```text', error, '```', '']
    (ROOT / 'data/VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': sys.exit(main())
