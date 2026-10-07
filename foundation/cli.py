"""Explicit local-only commands. No account, remote database or deployment access."""
import argparse
import json
import os
from pathlib import Path

from .storage import (apply_schema, connect, initialize, items_csv, load_baseline,
                      private_export, public_export, reconcile, restore, sql_export, records_csv)


def write_new(path, content):
    # Exclusive creation, owner-only mode: no accidentally overwriting a backup.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        f.write(content)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('init', 'reconcile', 'export-private', 'export-public', 'export-csv', 'export-records-csv', 'export-sql', 'restore'))
    p.add_argument('--db', required=True, help='Disposable LOCAL SQLite path only')
    p.add_argument('--allow-local', action='store_true', required=True, help='Explicit local-only acknowledgement')
    p.add_argument('--output')
    p.add_argument('--input')
    args = p.parse_args()
    path = Path(args.db).resolve()
    if path.suffix != '.sqlite' or '://' in args.db:
        p.error('Use a local .sqlite file; this tool does not support remote D1')
    existed = path.exists()
    db = connect(path)
    if args.command in ('init', 'restore') and not existed:
        apply_schema(db)
    if args.command == 'init':
        print(initialize(db, load_baseline()))
    elif args.command == 'reconcile':
        report = reconcile(db, load_baseline())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['passed']:
            raise SystemExit(1)
    elif args.command == 'restore':
        if not args.input:
            p.error('--input is required')
        restore(db, json.loads(Path(args.input).read_text()))
        print('Restored to an empty LOCAL database; owner credentials/sessions were not restored.')
    else:
        if not args.output:
            p.error('--output is required (use private storage, not the public repository)')
        if args.command == 'export-csv':
            content = items_csv(db)
        elif args.command == 'export-records-csv':
            content = records_csv(db)
        elif args.command == 'export-sql':
            content = sql_export(db)
        else:
            content = json.dumps(private_export(db) if args.command == 'export-private' else public_export(db), ensure_ascii=False, indent=2)
        write_new(args.output, content)
        print('Export created with owner-only permissions. SQL/full JSON must remain private.')
    db.close()


if __name__ == '__main__':
    main()
