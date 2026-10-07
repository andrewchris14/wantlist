export const STATUS = {
  want_list: { label: 'WANT', heading: 'Cards / items wanted', explanation: 'Listed cards are wanted.' },
  have_list: { label: 'HAVE', heading: 'Cards / items I have', explanation: 'Listed cards are owned. No missing cards are inferred.' },
  complete: { label: 'COMPLETE', heading: 'Complete', explanation: 'Nothing currently needed.' },
  uncertain: { label: 'UNCERTAIN', heading: 'Source uncertainty', explanation: 'Original uncertainty is preserved.' },
  needs_review: { label: 'NEEDS REVIEW', heading: 'Unresolved source information', explanation: 'An interpretation needs review.' },
};
export const DEFAULT_FILTERS = Object.freeze({ query: '', status: '', year: '', brand: '', category: '', sort: 'newest' });
export const PAGE_SIZE = 30;
export const asArray = value => Array.isArray(value) ? value.filter(v => typeof v === 'string' && v.trim()) : [];
export const groups = value => Array.isArray(value) ? value.filter(v => v && typeof v === 'object') : [];
export const text = value => typeof value === 'string' ? value : '';
export const categoryLabel = value => text(value).replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()) || 'Unspecified category';
export const normalize = value => text(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');

export function yearSpan(year) {
  const match = text(year).match(/(18\d{2}|19\d{2}|20\d{2})(?:\s*[-–]\s*(\d{2,4}))?/);
  if (!match) return null;
  const start = Number(match[1]);
  let end = match[2] ? Number(match[2]) : start;
  if (match[2]?.length === 2) end += Math.floor(start / 100) * 100;
  if (end < start) end = start; // Keep an unusual date label; never invent its intended year.
  return [start, end];
}

function groupSearch(group) {
  return [group.label, group.description, ...asArray(group.card_numbers), ...asArray(group.items),
    ...asArray(group.card_ranges), ...asArray(group.notes), group.list_type, group.source_list_type].filter(Boolean).join(' ');
}

export function prepareRecords(records) {
  return groups(records).map((record, index) => {
    const components = [...groups(record.mixed_lists), ...groups(record.sublists)];
    const aliases = asArray(record.prefixes).flatMap(prefix => asArray(record.card_numbers)
      .flatMap(number => [`${prefix}${number}`, `${prefix.replace(/-$/, '')}${number}`]));
    // Corrected fields only: the uncorrected source wording is intentionally
    // not indexed, since it can contain discarded duplicate headings/numbers.
    const search = normalize([record.year, record.brand, record.set_name, record.category,
      categoryLabel(record.category), record.section, record.payload, record.normalized_wording,
      ...asArray(record.card_numbers), ...asArray(record.items), ...asArray(record.card_ranges),
      ...asArray(record.notes), ...asArray(record.uncertainty), ...asArray(record.prefixes),
      ...asArray(record.completed_sets), ...aliases, ...components.map(groupSearch)].filter(Boolean).join(' '));
    return { ...record, _key: text(record.id) || `record-${index}`, _search: search,
      _words: new Set(search.split(' ')), _years: yearSpan(record.year), _index: index };
  });
}

export function queryMatches(record, query) {
  return normalize(query).split(' ').filter(Boolean).every(token =>
    /^\d+$/.test(token) ? record._words.has(token) : record._search.includes(token));
}

const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
export function selectRecords(records, filters = DEFAULT_FILTERS) {
  const result = records.filter(record =>
    (!filters.status || record.list_type === filters.status) &&
    (!filters.brand || (filters.brand === '__unknown' ? !text(record.brand) : record.brand === filters.brand)) &&
    (!filters.category || record.category === filters.category) &&
    (!filters.year || (filters.year === '__unknown' ? !record._years :
      record._years && Number(filters.year) >= record._years[0] && Number(filters.year) <= record._years[1])) &&
    queryMatches(record, filters.query));
  return result.sort((a, b) => {
    if (filters.sort !== 'alphabetical') {
      if (!a._years && b._years) return 1;
      if (a._years && !b._years) return -1;
      const years = (a._years?.[0] ?? 0) - (b._years?.[0] ?? 0);
      if (years) return filters.sort === 'oldest' ? years : -years;
    }
    return collator.compare(text(a.set_name), text(b.set_name)) || a._index - b._index;
  });
}

export function facets(records) {
  const years = new Set();
  for (const r of records) {
    if (r._years) for (let year = r._years[0]; year <= r._years[1]; year++) years.add(String(year));
  }
  return {
    years: [...years].sort((a, b) => Number(b) - Number(a)),
    brands: [...new Set(records.map(r => text(r.brand)).filter(Boolean))].sort(collator.compare),
    categories: [...new Set(records.map(r => text(r.category)).filter(Boolean))].sort(collator.compare),
    statuses: Object.keys(STATUS).filter(status => records.some(r => r.list_type === status)),
    unknownYears: records.some(r => !r._years), unknownBrands: records.some(r => !text(r.brand)),
  };
}

export async function loadDataset(signal) {
  const response = await fetch(new URL('wantlists.json', document.baseURI), { signal });
  if (!response.ok) throw new Error('The want list could not be loaded. Please try again.');
  const data = await response.json();
  if (!Array.isArray(data?.records)) throw new Error('The want list is unavailable. Please try again.');
  return data.records;
}
