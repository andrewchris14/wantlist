import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chooseSnapshot } from '../worker/fallback.js';

const snapshot = { export_schema: 'wantlist-public-v1-foundation', revision: 'revision-1', updated_at: '2026-10-07T00:00:00Z', records: [] };
test('valid live snapshot takes precedence', () => {
  assert.equal(chooseSnapshot(snapshot, snapshot).source, 'live');
  assert.equal(chooseSnapshot(snapshot, snapshot).notice, null);
});
test('fallback is explicitly dated and labeled, never described as current live data', () => {
  const selected = chooseSnapshot(null, snapshot);
  assert.equal(selected.source, 'saved');
  assert.ok(selected.notice.includes(snapshot.updated_at));
  assert.ok(selected.notice.includes('temporarily unavailable'));
});
test('missing revision/time or wrong schema cannot be silently used as fallback', () => {
  for (const data of [null, {}, { ...snapshot, updated_at: null }, { ...snapshot, revision: null }, { ...snapshot, export_schema: 'private' }]) {
    assert.equal(chooseSnapshot(null, data).source, 'unavailable');
  }
});
