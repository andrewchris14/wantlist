import { describe, expect, it, vi } from 'vitest';
import { readPublicData } from '../data-source.js';
import { DEFAULT_FILTERS, facets, loadDataset, prepareRecords, selectRecords, yearSpan } from '../model.js';

const data = await readPublicData();
const records = prepareRecords(data.records);
const find = query => selectRecords(records, { ...DEFAULT_FILTERS, query });

describe('authoritative data and search', () => {
  it('loads every Phase 2 record without modifying normalized fields', () => {
    expect(records).toHaveLength(3392);
    expect(data.records.find(r => r.id === 'p1566-l003').items).toEqual(['Blue Border Griffey']);
    for (const id of ['p0672-l001', 'p0694-l001', 'p0730-l001']) {
      expect(data.records.find(r => r.id === id).category).toBe('baseball_cards');
    }
  });
  it.each(['Topps', '2012 Topps', 'Griffey', 'Blue Border Griffey', 'Milwaukee Brewers', 'BCP', 'postcard', 'bobblehead', 'football'])('finds the requested example %s', query => {
    expect(find(query).length).toBeGreaterThan(0);
  });
  it('ignores case, extra spaces, accents, and reasonable punctuation', () => {
    expect(find('  bLuE   Border   GRIFFEY ').map(r => r.id)).toEqual(find('Blue Border Griffey').map(r => r.id));
    expect(find('BCP-47').some(r => r.id === 'p1153-l001')).toBe(true);
  });
  it('matches all query words and exact numeric tokens rather than substrings', () => {
    const sample = prepareRecords([{ set_name: '2012 Topps', card_numbers: ['121'], notes: ['Scarce printing'] }]);
    expect(selectRecords(sample, { ...DEFAULT_FILTERS, query: '12' })).toHaveLength(0);
    expect(selectRecords(sample, { ...DEFAULT_FILTERS, query: 'scarce Topps' })).toHaveLength(1);
    expect(selectRecords(sample, { ...DEFAULT_FILTERS, query: 'scarce Fleer' })).toHaveLength(0);
  });
  it('searches notes and mixed owned/wanted components', () => {
    expect(find('Red Border Griffey').some(r => r.id === 'p1566-l003')).toBe(true);
    expect(find('Good enough').some(r => r.id === 'p0390-l001')).toBe(true);
  });
  it('does not index discarded raw merged headings', () => {
    expect(find('2012 1993').some(r => r.id === 'p0639-l001')).toBe(false);
  });
});

describe('filters, dates, and sorting', () => {
  it.each(['want_list', 'have_list', 'complete', 'uncertain'])('filters exactly by primary status %s', status => {
    const result = selectRecords(records, { ...DEFAULT_FILTERS, status });
    expect(result.length).toBeGreaterThan(0);
    expect(result.every(r => r.list_type === status)).toBe(true);
  });
  it('combines year, brand, category, status, and search', () => {
    const result = selectRecords(records, { ...DEFAULT_FILTERS, query: 'Topps', year: '2012', brand: 'Topps', category: 'football_cards', status: 'want_list' });
    expect(result.map(r => r.id)).toContain('p0639-l001');
    expect(result.every(r => r.brand === 'Topps' && r.category === 'football_cards')).toBe(true);
  });
  it('matches years inside explicit source ranges and keeps unknown years available', () => {
    expect(yearSpan('1980-87')).toEqual([1980, 1987]);
    expect(yearSpan('1973-1978')).toEqual([1973, 1978]);
    expect(yearSpan('1979-?')).toEqual([1979, 1979]);
    expect(yearSpan(null)).toBeNull();
    expect(selectRecords(records, { ...DEFAULT_FILTERS, year: '1984' }).some(r => r.id === 'p0008-l001')).toBe(true);
    expect(selectRecords(records, { ...DEFAULT_FILTERS, year: '__unknown' })).toHaveLength(176);
  });
  it('builds facets only from actual data and exposes missing brands', () => {
    const options = facets(records);
    expect(options.brands).toHaveLength(46);
    expect(options.categories).toHaveLength(18);
    expect(options.statuses).toEqual(['want_list', 'have_list', 'complete', 'uncertain']);
    expect(selectRecords(records, { ...DEFAULT_FILTERS, brand: '__unknown' }).every(r => !r.brand)).toBe(true);
  });
  it('orders newest, oldest, and alphabetical with unknown years retained', () => {
    const sample = prepareRecords([{ set_name: 'Zed', year: null }, { set_name: 'Beta', year: '2001' }, { set_name: 'Alpha', year: '1950' }]);
    expect(selectRecords(sample).map(r => r.set_name)).toEqual(['Beta', 'Alpha', 'Zed']);
    expect(selectRecords(sample, { ...DEFAULT_FILTERS, sort: 'oldest' }).map(r => r.set_name)).toEqual(['Alpha', 'Beta', 'Zed']);
    expect(selectRecords(sample, { ...DEFAULT_FILTERS, sort: 'alphabetical' }).map(r => r.set_name)).toEqual(['Alpha', 'Beta', 'Zed']);
  });
  it('resetting filters restores all records without mutating the input', () => {
    const ids = records.map(r => r.id);
    expect(selectRecords(records, { ...DEFAULT_FILTERS, query: 'impossible-set-abcdef' })).toHaveLength(0);
    expect(selectRecords(records, DEFAULT_FILTERS)).toHaveLength(3392);
    expect(records.map(r => r.id)).toEqual(ids);
  });
  it('handles missing optional fields, nulls, and invalid date labels', () => {
    const sample = prepareRecords([null, {}, { set_name: 55, notes: null, mixed_lists: [null], year: {} }]);
    expect(selectRecords(sample)).toHaveLength(2);
    expect(facets(sample).unknownYears).toBe(true);
  });
});

describe('dataset loading failures', () => {
  it('loads records over HTTP', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ records: [{}] }) }));
    expect(await loadDataset()).toEqual([{}]);
    vi.unstubAllGlobals();
  });
  it('reports unsuccessful HTTP and malformed dataset responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    await expect(loadDataset()).rejects.toThrow('could not be loaded');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ nope: [] }) }));
    await expect(loadDataset()).rejects.toThrow('unavailable');
    vi.unstubAllGlobals();
  });
});
