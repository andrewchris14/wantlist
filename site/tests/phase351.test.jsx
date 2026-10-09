import {it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {readFileSync} from 'node:fs';
import Browse,{originalCategory,compactStatus} from '../../owner/Browse.jsx';
import {editorDefaults,editorPayload,effectiveListType} from '../../owner/model.js';
const view=JSON.parse(readFileSync('foundation/staging/historical-view.json')).records;
const map=JSON.parse(readFileSync('foundation/staging/historical-map.json'));
it('all 3394 historical editor classifications agree with public display, including absent legacy display fields',()=>{
 expect(view).toHaveLength(3394);const seen=new Set();
 for(const r of view){const c={...r};if(!r.id.startsWith('display-'))delete c.display_category;delete c.display_list_type;const dto={id:r.id,list_type:r.list_type,content:c,groups:[]};const form=editorDefaults(dto);expect(form.display_category,r.id).toBe(originalCategory(r));expect(form.list_type,r.id).toBe(r.display_list_type||r.list_type);expect(compactStatus(r),r.id).toBe({want_list:'WANT list',have_list:'HAVE list',complete:'COMPLETE',uncertain:'Notes'}[form.list_type]);seen.add(form.display_category);expect(editorPayload(dto,form)).toEqual({metadata:{}});}
 expect([...seen].sort()).toEqual([...map.categories].sort());
 for(const [id,a] of Object.entries(map.classification_approvals))expect(editorDefaults({id,list_type:'uncertain',content:{}}).list_type).toBe(a.list_type);
});
it('unrelated saves retain Football category and HAVE type; explicit selections remain explicit',()=>{
 const r={id:'p0581-l001',list_type:'have_list',content:{year:'1951',brand:'Topps',set_name:'1951 Topps',category:'football_cards',notes:[]}};
 const initial=editorDefaults(r);expect(initial.display_category).toBe('Football Wantlist');expect(initial.list_type).toBe('have_list');
 for(const extra of [{},{notes:'A note'},{entry_order:'original'},{year:'1951(?)'}]){const p=editorPayload(r,{...initial,...extra});expect(p.metadata).not.toHaveProperty('display_category');expect(p).not.toHaveProperty('list_type');}
 expect(editorPayload(r,{...initial,display_category:'Other Stuff'}).metadata).toEqual({display_category:'Other Stuff'});
 expect(editorPayload(r,{...initial,list_type:'want_list'}).list_type).toBe('want_list');
});
it('explicit live categories and types take precedence over historical defaults; unmapped values are not guessed',()=>{
 for(const mode of ['want_list','have_list','complete']){const r={id:'p0060-l001',list_type:mode,content:{display_category:'Owner category'}};expect(editorDefaults(r).list_type).toBe(mode);expect(editorDefaults(r).display_category).toBe('Owner category');expect(editorPayload(r,{...editorDefaults(r),notes:'note'})).toEqual({metadata:{notes:['note']}});}
 expect(editorDefaults({id:'unknown',content:{}})).toMatchObject({display_category:'',list_type:'uncertain'});
 expect(effectiveListType({id:'p0023-l001',list_type:'uncertain',groups:[{list_type:'want_list',entries:[{state:'pending'}]}]})).toBe('have_list');
});
it('public contact link is accessible, uses mailto and retains OBC identity',()=>{
 render(<Browse records={[]}/>);expect(screen.getByRole('heading',{name:"Jason's Want List"})).toBeVisible();expect(screen.getByRole('link',{name:'jschris@triwest.net'})).toHaveAttribute('href','mailto:jschris@triwest.net');expect(screen.getByText(/OLD BASEBALL CARDS/)).toBeVisible();
});
