import { useEffect, useMemo, useRef, useState } from 'react';
import RecordCard from './RecordCard.jsx';
import { STATUS, DEFAULT_FILTERS, PAGE_SIZE, categoryLabel, facets, loadDataset, prepareRecords, selectRecords } from './model.js';

function ArrowIcon() {
  return <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4 12 12 4M4 4h8v8" stroke="currentColor" strokeWidth="1.4" /></svg>;
}

function SearchIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.8" /><path d="m16 16 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

export default function App({ initialRecords, ownerToolbar, ownerAction, modeLabel = "Read-only" }) {
  const [data, setData] = useState(initialRecords ?? null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });
  const [page, setPage] = useState(1);
  const resultsHeading = useRef(null);
  const searchInput = useRef(null);
  useEffect(() => {
    if (initialRecords !== undefined) { setData(initialRecords); return; }
    const controller = new AbortController();
    setError(''); setData(null);
    loadDataset(controller.signal).then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [initialRecords, retry]);
  const records = useMemo(() => prepareRecords(data), [data]);
  const options = useMemo(() => facets(records), [records]);
  const result = useMemo(() => selectRecords(records, filters), [records, filters]);
  const pageCount = Math.max(1, Math.ceil(result.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageRecords = result.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const filtered = ['query', 'status', 'year', 'brand', 'category'].some(key => filters[key]);
  function update(key, value) { setFilters(previous => ({ ...previous, [key]: value })); setPage(1); }
  function clear() { setFilters({ ...DEFAULT_FILTERS }); setPage(1); searchInput.current?.focus(); }
  function changePage(next) {
    setPage(next);
    resultsHeading.current?.focus({ preventScroll: true });
    resultsHeading.current?.scrollIntoView({ behavior: 'instant', block: 'start' });
  }
  return <>
    <a className="skip-link" href="#results">Skip to results</a>
    <header className="site-header">
      <div className="header-inner"><a className="brand-mark" href="./" aria-label="Baseball Card Want List home"><span className="diamond-mark" aria-hidden="true"><span>OBC</span></span><span>THE COLLECTOR’S LIST<small>Old Baseball Cards community</small></span></a>
        <a className="how-link" href="#how-it-works">How to read the list <ArrowIcon /></a></div>
    </header>
    <main>
      {ownerToolbar}
      <section className="hero" aria-labelledby="page-title">
        <div className="hero-text"><p className="eyebrow">FOR THE LOVE OF THE CARDS</p><h1 id="page-title">Baseball Card<br /><em>Want List</em></h1>
          <p className="hero-description">Have something to trade? Find a set, a player, or a card number and see what’s on the list.</p>
          <p className="collection-meta"><span className="live-dot" aria-hidden="true" />{data === null ? 'Loading collection' : `${records.length.toLocaleString()} sets & collecting lists`}<span aria-hidden="true">·</span>{modeLabel}</p></div>
        <div className="hero-art" aria-hidden="true"><div className="collector-card"><div className="card-corner">OBC <span>CARD BY CARD</span></div><div className="baseball-diamond"><div className="diamond-line" /><span className="base home" /><span className="base first" /><span className="base second" /><span className="base third" /><div className="ball"><span /><span /></div></div><p>GOOD CARDS.<br />GOOD COMPANY.</p><div className="card-rule" /><small>A COLLECTOR’S TRADITION</small></div></div>
      </section>
      <section className="search-panel" aria-label="Search and filter the want list">
        <label className="search-label" htmlFor="collection-search">Search the collection</label>
        <div className="search-input-wrap"><SearchIcon /><input ref={searchInput} id="collection-search" type="search" autoComplete="off" value={filters.query} placeholder="Try “2012 Topps”, “Griffey”, or a card number" onChange={e => update('query', e.target.value)} aria-describedby="search-help" />{filters.query && <button type="button" className="clear-search" aria-label="Clear search" onClick={() => { update('query', ''); searchInput.current?.focus(); }}>×</button>}</div>
        <p id="search-help" className="search-help">Search sets, years, players, card numbers, prefixes, categories, and notes.</p>
        <div className="filters">
          <label>Status<select value={filters.status} onChange={e => update('status', e.target.value)}><option value="">All statuses</option>{options.statuses.map(value => <option key={value} value={value}>{STATUS[value].label}</option>)}</select></label>
          <label>Year<select value={filters.year} onChange={e => update('year', e.target.value)}><option value="">All years</option>{options.years.map(value => <option key={value} value={value}>{value}</option>)}{options.unknownYears && <option value="__unknown">Year unspecified</option>}</select></label>
          <label>Brand<select value={filters.brand} onChange={e => update('brand', e.target.value)}><option value="">All brands</option>{options.brands.map(value => <option key={value} value={value}>{value}</option>)}{options.unknownBrands && <option value="__unknown">Brand unspecified</option>}</select></label>
          <label>Category<select value={filters.category} onChange={e => update('category', e.target.value)}><option value="">All categories</option>{options.categories.map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}</select></label>
        </div>
      </section>
      <section id="how-it-works" className="list-guide" aria-label="How to read the list">
        {['want_list', 'have_list', 'complete', 'uncertain'].map(status => <div className="guide-item" key={status}><span className={`status-badge ${status}`}>{STATUS[status].label}</span><p>{STATUS[status].explanation}</p></div>)}
      </section>
      <section id="results" className="results-section" aria-labelledby="results-title">
        <div className="results-toolbar"><div><h2 id="results-title" ref={resultsHeading} tabIndex="-1">{filtered ? 'Matching lists' : 'Browse the collection'}</h2><p role="status" aria-live="polite" aria-atomic="true">{data === null ? error ? 'Collection unavailable' : 'Loading lists…' : `${result.length.toLocaleString()} ${result.length === 1 ? 'list' : 'lists'}${filtered ? ` of ${records.length.toLocaleString()}` : ''}`}</p></div>
          <div className="result-actions">{filtered && <button type="button" className="reset-button" onClick={clear}>Clear search &amp; filters</button>}<label className="sort-label">Sort by<select value={filters.sort} onChange={e => update('sort', e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="alphabetical">Alphabetical</option></select></label></div></div>
        {error ? <div className="empty-state" role="alert"><h3>The list couldn’t be loaded</h3><p>{error}</p><button className="primary-button" onClick={() => setRetry(retry + 1)}>Try again</button></div>
          : data === null ? <div className="loading-state">Opening the card box…</div>
          : result.length === 0 ? <div className="empty-state"><span aria-hidden="true">⌕</span><h3>No matching lists</h3><p>Try fewer words or a different year, brand, or category.</p><button className="primary-button" onClick={clear}>Clear search &amp; filters</button></div>
          : <><div className="results-grid">{pageRecords.map(record => <RecordCard key={record._key} record={record} query={filters.query} ownerAction={ownerAction?.(record)} />)}</div>
            {pageCount > 1 && <nav className="pagination" aria-label="Result pages"><button type="button" onClick={() => changePage(currentPage - 1)} disabled={currentPage === 1}>← Previous</button><span>Page {currentPage} of {pageCount}<small>Showing {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, result.length)} of {result.length.toLocaleString()}</small></span><button type="button" onClick={() => changePage(currentPage + 1)} disabled={currentPage === pageCount}>Next →</button></nav>}</>}
      </section>
    </main>
    <footer className="site-footer"><p>A list for collectors, by a collector.</p><span>Old Baseball Cards community · Read-only want list</span><a href="https://baseballjason.blogspot.com/2010/03/im-back.html">Historical Blogger page <ArrowIcon /></a></footer>
  </>;
}
