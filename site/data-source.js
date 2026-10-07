import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

// The website reads the committed Phase 2 file. This projection only removes
// import/audit bulk; it never changes a record's meaning, status, or category.
const publicFields = ['id', 'year', 'brand', 'set_name', 'category', 'section',
  'list_type', 'source_list_type', 'card_numbers', 'items', 'card_ranges',
  'notes', 'prefixes', 'set_size', 'uncertainty', 'mixed_lists', 'sublists',
  'payload', 'normalized_wording', 'source_refs', 'completed_sets'];

export async function readPublicData() {
  const data = JSON.parse(await readFile(resolve('data/wantlists.json'), 'utf8'));
  if (!Array.isArray(data.records)) throw new Error('The Phase 2 dataset has no records array.');
  return { schema_version: data.schema_version, records: data.records.map(record =>
    Object.fromEntries(publicFields.filter(field => field in record).map(field => [field, record[field]]))) };
}

export function wantlistDataPlugin() {
  return {
    name: 'phase-2-wantlist-data',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url?.split('?')[0] !== '/wantlists.json') return next();
        try {
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(await readPublicData()));
        } catch {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: 'Unable to load the Phase 2 dataset.' }));
        }
      });
    },
    async generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'wantlists.json', source: JSON.stringify(await readPublicData()) });
    },
  };
}
