// Existing approved public display manifest, read in RAM. No importer, SQLite
// historical fixture, auth data, remote source or staging snapshot is used.
import {readFileSync} from 'node:fs';
import {effectiveListType,publicSearchRecord} from '../../owner/model.js';
export const view=JSON.parse(readFileSync(new URL('../staging/historical-view.json',import.meta.url),'utf8'));
export const categoryCounts={'OBC Wantlist':583,'UV Wantlist':2517,'Eau Claire Players':3,'Milwaukee 8x10 List':1,'Brewers Bobblehead Wantlist':26,'Football Wantlist':62,'Other Stuff':202};
export const indexRecords=view.records.map(r=>{
 const searchable=publicSearchRecord(r),mode=effectiveListType(r);
 const values=[...(searchable.card_numbers||[]),...(searchable.card_ranges||[]),...(searchable.items||[]),...[...(searchable.mixed_lists||[]),...(searchable.sublists||[])].flatMap(g=>[...(g.items||[]),...(g.label?[g.label]:[])])];
 return {id:r.id,year:r.year,display_year:r.display_year,brand:r.brand,set_name:r.set_name,category:r.category,display_category:r.display_category,notes:r.notes,prefixes:r.prefixes,entry_order:r.entry_order,source_list_type:r.source_list_type,list_type:mode,revision:1,index_only:true,card_numbers:[],items:[values.join(' ')]};
}).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
export function pageAfter(after=''){const records=indexRecords.filter(r=>r.id>after).slice(0,500);return {records,next:records.length===500?records.at(-1).id:null};}
