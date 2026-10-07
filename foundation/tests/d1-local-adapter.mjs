// Disposable D1-interface adapter, not a Cloudflare emulator.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';

export function localD1() {
  const sqlite = new DatabaseSync(':memory:');
  const directory = new URL('../migrations/', import.meta.url);
  for (const file of readdirSync(directory).filter(f => f.endsWith('.sql')).sort()) {
    sqlite.exec(readFileSync(new URL(file, directory), 'utf8'));
  }
  function statement(sql, args = []) {
    return {
      bind(...values) { return statement(sql, values); },
      async first() { return sqlite.prepare(sql).get(...args) || null; },
      async all() { return { results: sqlite.prepare(sql).all(...args) }; },
      async run() { const r = sqlite.prepare(sql).run(...args); return { success: true, results: [], meta: { changes: Number(r.changes) } }; },
      execute() {
        if (/\bRETURNING\b/i.test(sql) || /^SELECT\b/i.test(sql)) return { success: true, results: sqlite.prepare(sql).all(...args) };
        const r = sqlite.prepare(sql).run(...args);
        return { success: true, results: [], meta: { changes: Number(r.changes) } };
      },
    };
  }
  return {
    sqlite, prepare: statement,
    async batch(statements) {
      sqlite.exec('BEGIN');
      try { const rows = statements.map(s => s.execute()); sqlite.exec('COMMIT'); return rows; }
      catch (error) { sqlite.exec('ROLLBACK'); throw error; }
    },
    close() { sqlite.close(); },
  };
}
