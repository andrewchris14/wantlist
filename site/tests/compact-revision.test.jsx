import {newSetCategory,browseRecord} from '../../owner/model.js';
import {describe,it,expect} from 'vitest';import {render,screen,fireEvent} from '@testing-library/react';import Browse,{compactSort,compactStatus,CATEGORIES} from '../../owner/Browse.jsx';
const r=(id,name,year,list_type,values=[])=>({id,set_name:name,year,list_type,display_category:'OBC Wantlist',card_numbers:values,items:[],notes:[]});
describe('compact reference list',()=>{
 it('defaults to OBC, has exactly seven categories, removes status filter and initially collapses contents',()=>{
  const {container}=render(<Browse records={[r('x','2027 Topps','2027','want_list',['47'])]}/>);expect(screen.getByLabelText('Category')).toHaveValue('OBC Wantlist');expect(screen.getByLabelText('Category').options).toHaveLength(7);expect(screen.queryByLabelText(/Status/)).toBeNull();expect(container.querySelector('details').open).toBe(false);expect(screen.getByText('WANT list')).toBeVisible();fireEvent.click(container.querySelector('summary'));expect(container.querySelector('details').open).toBe(true);
 });
 it('search scope is explicit and cross-category matches offer navigation',()=>{
  render(<Browse records={[r('a','Topps','2027','have_list',['1']),{...r('b','Topps UV','2026','want_list',['2']),display_category:'UV Wantlist'}]}/>);fireEvent.change(screen.getByLabelText('Search this category'),{target:{value:'Topps'}});expect(screen.getByText(/Searching OBC Wantlist/)).toBeVisible();fireEvent.click(screen.getByRole('button',{name:'UV Wantlist (1)'}));expect(screen.getByLabelText('Category')).toHaveValue('UV Wantlist');
 });
 it('sorts newest then set alphabetically and unknown dates last',()=>{const rows=[r('b','Z','2027','complete'),r('c','A','2027','have_list'),r('a','Old','1951','want_list'),r('d','Undated',null,'want_list')].sort(compactSort);expect(rows.map(r=>r.id)).toEqual(['c','b','a','d']);});
 it('uncertainty is truthful, not a completion claim; explicit owned inventory can display HAVE with wording retained',()=>{expect(compactStatus({...r('a','Maybe',null,'uncertain'),source_list_type:'want_list'})).toBe('Notes');expect(compactStatus({...r('b','Owned',null,'uncertain',['1']),source_list_type:'have_list'})).toBe('HAVE list');expect(CATEGORIES).toContain('Milwaukee 8x10 List');});
});

it('new-set category defaults follow explicit owner selection, not brand/name inference',()=>{expect(newSetCategory('Football Wantlist')).toBe('football_cards');expect(newSetCategory('Other Stuff')).toBe('other_collectibles');expect(newSetCategory('OBC Wantlist')).toBe('baseball_cards');});

it('reopening a historical Complete set does not falsely label it complete, while completed year sublists survive',()=>{const groups=[{kind:'primary',list_type:'complete',entries:[]},{kind:'mixed',list_type:'want_list',entries:[{value:'47',state:'wanted',actionable:1}]}];expect(browseRecord({list_type:'want_list',groups}).mixed_lists.map(g=>g.list_type)).toEqual(['want_list']);expect(browseRecord({list_type:'want_list',groups:[{kind:'sublist',label:'2001',list_type:'complete',entries:[]}]}).mixed_lists[0].list_type).toBe('complete');});
