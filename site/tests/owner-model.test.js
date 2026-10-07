import {describe,it,expect,vi,afterEach} from 'vitest';
import {browseRecord,parseCards,historyLabel} from '../../owner/model.js';
import {request} from '../../owner/api.js';
import {prepareRecords,selectRecords} from '../model.js';
afterEach(()=>vi.unstubAllGlobals());
describe('owner input and public presentation',()=>{
 it('accepts numbers/codes without splitting names or expanding ranges',()=>{
  expect(parseCards('12 18,47\n92 BCP-8 KCR2 10-12')).toEqual(['12','18','47','92','BCP-8','KCR2','10-12']);
  expect(parseCards('Blue Border Griffey\nSmith, John','names')).toEqual(['Blue Border Griffey','Smith, John']);
  expect(()=>parseCards('12 12')).toThrow(/twice/);
 });
 it('keeps wanted, pending, owned and unstructured source information distinct and searchable',()=>{
  const r=browseRecord({id:'r',year:'2001',brand:'Fleer',set_name:'Ritz/Oreo',category:'baseball_cards',list_type:'want_list',groups:[{label:'Variants',entries:[{value:'Blue Border Griffey',state:'wanted',actionable:1},{value:'Red Border Griffey',state:'owned',actionable:1},{value:'47',state:'pending',actionable:1},{value:'Names/prose preserved',state:null,actionable:0}]}]});
  expect(r.mixed_lists.find(g=>g.list_type==='have_list').items).toEqual(['Red Border Griffey']);
  expect(r.mixed_lists.find(g=>g.list_type==='pending').items).toEqual(['47']);
  expect(r.mixed_lists.find(g=>g.label.includes('Preserved')).items).toEqual(['Names/prose preserved']);
  expect(selectRecords(prepareRecords([r]),{query:'blue border griffey'})).toHaveLength(1);
 });
 it('HAVE never creates wanted or inferred missing values',()=>{
  const r=browseRecord({list_type:'have_list',groups:[{entries:[{value:'KCR2',state:'owned',actionable:1}]}]});
  expect(r.mixed_lists).toHaveLength(1);expect(r.mixed_lists[0].list_type).toBe('have_list');expect(r.card_numbers).toEqual([]);
 });
 it('formats history with plain language',()=>{
  expect(historyLabel({action:'transition',after:{value:'47',state:'owned'}})).toBe('Marked 47 as Received');
  expect(historyLabel({action:'add',after:{items:[{value:'12'},{value:'18'}]}})).toBe('Added cards 12, 18');
 });
});
describe('owner connection errors',()=>{
 it('does not expose backend SQL or authentication internals',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:503,json:async()=>({error:'SQL secret details'})})));
  await expect(request('/action',{})).rejects.toThrow('We couldn’t confirm your change');
 });
 it('expired login asks for verification again',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:401})));
  await expect(request('/session')).rejects.toThrow('This computer needs to be verified again');
 });
});
