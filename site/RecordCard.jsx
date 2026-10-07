import { useState } from 'react';
import { STATUS, asArray, groups, text, categoryLabel, normalize } from './model.js';

function ItemList({ values, query, label }) {
  const [expanded, setExpanded] = useState(false);
  const tokens = normalize(query).split(' ').filter(Boolean);
  const matches = value => tokens.some(token => normalize(value).split(' ').includes(token));
  const shown = expanded ? values : values.filter((v, i) => i < 24 || matches(v));
  const remaining = values.length - shown.length;
  return <>
    <ul className="item-list" aria-label={label}>
      {shown.map((value, index) => <li className={matches(value) ? 'matched-item' : ''} key={`${value}-${index}`}>{value}</li>)}
    </ul>
    {(remaining > 0 || expanded && values.length > 24) &&
      <button type="button" className="text-button expand-items" onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}>{expanded ? 'Show fewer items' : `Show all ${values.length} items (${remaining} more)`}</button>}
  </>;
}

function ComponentList({ group, inherited, query }) {
  const status = text(group.list_type) || inherited;
  const values = [...asArray(group.card_numbers), ...asArray(group.card_ranges), ...asArray(group.items)];
  const type = status === 'uncertain' ? text(group.source_list_type) : status;
  const title = status === 'complete' ? 'Complete portion' : status === 'uncertain'
    ? `Uncertain ${type === 'have_list' ? 'owned items' : type === 'want_list' ? 'wanted items' : 'source information'}`
    : STATUS[status]?.heading || 'Source information';
  return <section className={`component-list ${status}`} aria-label={group.label || title}>
    <h4>{group.label ? `${group.label} · ` : ''}{title}</h4>
    {status !== 'complete' && values.length > 0 && <ItemList values={values} query={query} label={title} />}
    {text(group.description) && <p className="component-description">{group.description}</p>}
    {asArray(group.notes).map((note, i) => <p className="component-description" key={i}>{note}</p>)}
  </section>;
}

export default function RecordCard({ record, query = '' }) {
  const status = text(record.list_type) || 'needs_review';
  const info = STATUS[status] || STATUS.needs_review;
  const values = [...asArray(record.card_numbers), ...asArray(record.card_ranges), ...asArray(record.items)];
  const notes = [...new Set([...asArray(record.notes), ...asArray(record.uncertainty)])];
  const components = [...groups(record.mixed_lists), ...groups(record.sublists)];
  const hasDetails = Boolean(notes.length || record.payload || record.normalized_wording || groups(record.source_refs).length);
  const uncertainHeading = record.source_list_type === 'have_list' ? 'Listed as owned · source is uncertain' : 'Listed items · source is uncertain';
  return <article className={`record-card ${status}`} aria-labelledby={`heading-${record._key || record.id}`}>
    <div className="record-topline">
      <span className="record-category">{categoryLabel(record.category)}</span>
      <span className={`status-badge ${status}`}>{info.label}</span>
    </div>
    <h3 id={`heading-${record._key || record.id}`}>{text(record.set_name) || 'Untitled collecting list'}</h3>
    <p className="record-meta">{text(record.year) || 'Year unspecified'}{text(record.brand) && <> <span aria-hidden="true">·</span> {record.brand}</>}
      {asArray(record.prefixes).length > 0 && <> <span aria-hidden="true">·</span> Prefix: {asArray(record.prefixes).join(', ')}</>}
      {Number.isFinite(record.set_size) && <> <span aria-hidden="true">·</span> {record.set_size}-item set</>}
    </p>
    {status === 'complete' ? <p className="completion-note">Complete — nothing currently needed.</p> : <>
      <h4 className="list-heading">{status === 'uncertain' ? uncertainHeading : info.heading}</h4>
      {status === 'have_list' && <p className="ownership-note">These are owned items, not wants. No missing-card list is inferred.</p>}
      {status === 'uncertain' && <p className="uncertainty-note">{asArray(record.uncertainty).join(' ') || 'The source is uncertain; this is not a confirmed completion or want statement.'}</p>}
      {values.length > 0 ? <ItemList values={values} query={query} label={status === 'have_list' ? 'Owned cards and items' : status === 'uncertain' ? 'Uncertain source items' : 'Wanted cards and items'} />
        : <p className="empty-list-note">{status === 'have_list' ? 'No individual owned items listed.' : status === 'uncertain' ? 'No definitive item list.' : 'See the collecting request and notes below.'}</p>}
      {status === 'want_list' && !values.length && text(record.payload) && <p className="request-description">{record.payload}</p>}
    </>}
    {components.map((group, index) => <ComponentList key={index} group={group} inherited={record.source_list_type} query={query} />)}
    {asArray(record.completed_sets).length > 0 && <p className="completion-note">Completed sets: {record.completed_sets.join('; ')}</p>}
    {hasDetails && <details className="record-details">
      <summary>Notes &amp; list details{notes.length > 0 && ` (${notes.length})`}</summary>
      {notes.map((note, i) => <p key={i}>{note}</p>)}
      {text(record.normalized_wording) && <p><strong>Recorded wording:</strong> {record.normalized_wording}</p>}
      {!record.normalized_wording && text(record.payload) && <p>{record.payload}</p>}
      {groups(record.source_refs).length > 0 && <p className="source-reference">Source reference: {record.source_refs.map(ref => `paragraph ${ref.paragraph}, line ${ref.line}`).join('; ')}.</p>}
    </details>}
  </article>;
}
