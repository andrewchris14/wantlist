import { expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readPublicData } from '../data-source.js';
import App from '../App.jsx';
import RecordCard from '../RecordCard.jsx';

const { records } = await readPublicData();
const record = id => records.find(r => r.id === id);

it('renders a WANT card with wanted items', () => {
  render(<RecordCard record={record('p0177-l001')} />);
  expect(screen.getByText('WANT')).toBeVisible();
  expect(screen.getByRole('list', { name: 'Wanted cards and items' })).toHaveTextContent('107');
});
it('renders HAVE cards as owned, never as wanted', () => {
  render(<RecordCard record={record('p0099-l001')} />);
  expect(screen.getByText('HAVE')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Cards / items I have' })).toBeVisible();
  expect(screen.getByText(/These are owned items, not wants/)).toBeVisible();
  expect(screen.queryByRole('list', { name: 'Wanted cards and items' })).not.toBeInTheDocument();
});
it('renders Complete without a fictitious item list', () => {
  render(<RecordCard record={record('p0918-l003')} />);
  expect(screen.getByText('Complete — nothing currently needed.')).toBeVisible();
  expect(screen.queryByRole('list')).not.toBeInTheDocument();
});
it('preserves uncertainty rather than rendering it as complete', () => {
  render(<RecordCard record={record('p0060-l001')} />);
  expect(screen.getByText('UNCERTAIN')).toBeVisible();
  expect(screen.getAllByText('Believed to be complete').length).toBeGreaterThan(0);
  expect(screen.queryByText('Complete — nothing currently needed.')).not.toBeInTheDocument();
});
it('presents Blue Border Griffey as wanted and Red Border Griffey as owned', () => {
  render(<RecordCard record={record('p1566-l003')} />);
  expect(within(screen.getByRole('list', { name: 'Wanted cards and items' })).getByText('Blue Border Griffey')).toBeVisible();
  const owned = screen.getByRole('region', { name: 'Cards / items I have' });
  expect(within(owned).getByText('Red Border Griffey')).toBeVisible();
  expect(within(owned).queryByText('Blue Border Griffey')).not.toBeInTheDocument();
});
it('renders missing and malformed optional fields without crashing', () => {
  render(<RecordCard record={{ card_numbers: null, notes: {}, mixed_lists: [null, {}], source_refs: null }} />);
  expect(screen.getByRole('heading', { name: 'Untitled collecting list' })).toBeVisible();
  expect(screen.getByText('NEEDS REVIEW')).toBeVisible();
});
it('reveals long lists and keeps searched items visible even before expanding', async () => {
  const user = userEvent.setup();
  render(<RecordCard record={{ id: 'long', set_name: 'Long set', list_type: 'have_list', card_numbers: Array.from({ length: 100 }, (_, i) => String(i + 1)) }} query="90" />);
  expect(screen.getByText('90')).toBeVisible();
  expect(screen.queryByText('89')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /Show all 100 items/ }));
  expect(screen.getByText('89')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Show fewer items' }));
  expect(screen.queryByText('89')).not.toBeInTheDocument();
});
it('searches the full collection and clearing search and filters restores it', async () => {
  const user = userEvent.setup();
  render(<App initialRecords={records} />);
  expect(screen.getByRole('status')).toHaveTextContent('3,392 lists');
  await user.type(screen.getByRole('searchbox'), 'Blue Border Griffey');
  expect(screen.getByRole('status')).toHaveTextContent('1 list of 3,392');
  expect(screen.getByText('Blue Border Griffey', { selector: 'li' })).toBeVisible();
  await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'complete');
  expect(screen.getByRole('heading', { name: 'No matching lists' })).toBeVisible();
  await user.click(screen.getAllByRole('button', { name: 'Clear search & filters' })[0]);
  expect(screen.getByRole('searchbox')).toHaveValue('');
  expect(screen.getByRole('combobox', { name: 'Status' })).toHaveValue('');
  expect(screen.getByRole('status')).toHaveTextContent('3,392 lists');
});
it('keeps pagination bounded and resets pages when filters change', async () => {
  const user = userEvent.setup();
  Element.prototype.scrollIntoView = vi.fn();
  render(<App initialRecords={records} />);
  expect(screen.getAllByRole('article')).toHaveLength(30);
  await user.click(screen.getByRole('button', { name: 'Next →' }));
  expect(screen.getByText('Page 2 of 114')).toBeVisible();
  await user.selectOptions(screen.getByRole('combobox', { name: 'Category' }), 'bobbleheads');
  expect(screen.getByRole('status')).toHaveTextContent('26 lists of 3,392');
  expect(screen.queryByRole('navigation', { name: 'Result pages' })).not.toBeInTheDocument();
});
it('loads the site data asynchronously and provides retry on failure', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: false })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ records: [record('p1566-l003')] }) }));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  await user.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Blue Border Griffey', { selector: 'li' })).toBeVisible();
  vi.unstubAllGlobals();
});

it('supplied records update when a staging read or save finishes', async () => {
  const {rerender}=render(<App initialRecords={[]} />);
  rerender(<App initialRecords={[{id:'new-owner-record',year:'2027',brand:'Topps',set_name:'Future practice set',category:'baseball_cards',list_type:'want_list',card_numbers:['47']}]} />);
  expect(await screen.findByRole('heading',{name:'Future practice set'})).toBeInTheDocument();
});
