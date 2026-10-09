import {test,expect} from '@playwright/test';import {readFileSync} from 'node:fs';
import {pageAfter,categoryCounts,indexRecords} from '../../foundation/tests/full-index-fixture.mjs';
const origin='https://local-full.invalid';
async function mock(page,failThird=false){
 const observations={pages:0,unexpected:[]};
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  if(url.origin!==origin){observations.unexpected.push(url.origin);await route.abort();return;}
  if(path==='/'||path.startsWith('/assets/')){await route.fulfill({contentType:path==='/'?'text/html':path.endsWith('.css')?'text/css':'application/javascript',body:readFileSync('foundation/.local/editor-dist'+(path==='/'?'/index.html':path))});return;}
  if(path==='/session'){await route.fulfill({status:401,json:{error:'AUTH_REQUIRED'}});return;}
  if(path==='/public/categories'){await route.fulfill({json:{categories:Object.keys(categoryCounts).map((name,i)=>({id:String(i),name,historical:1}))}});return;}
  if(path==='/public/index'){
   observations.pages++;if(failThird&&observations.pages===3){await route.fulfill({status:404,contentType:'text/html',headers:{'CF-Ray':'synthetic-ray'},body:'Synthetic upstream failure'});return;}
   await route.fulfill({json:pageAfter(url.searchParams.get('after'))});return;
  }
  observations.unexpected.push(path);await route.abort();
 });return observations;
}
test('built browser loads all seven pages, categories, search, year and manufacturer filters without remote access',async({page})=>{
 const observed=await mock(page);await page.goto(origin);
 await expect(page.getByRole('heading',{name:'OBC Wantlist (583)',exact:true})).toBeVisible();expect(observed.pages).toBe(7);
 for(const [category,count] of Object.entries(categoryCounts)){
  await page.getByRole('combobox',{name:'Category',exact:true}).selectOption(category);
  await expect(page.locator('.listing-row')).toHaveCount(count);
  const title=indexRecords.find(r=>r.display_category===category&&r.set_name).set_name;
  await page.getByLabel('Search this category').fill(title);await expect(page.locator('.listing-row').first()).toBeVisible();
  await page.getByLabel('Search this category').fill('');
 }
 await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('UV Wantlist');
 await page.getByLabel('Search this category').fill('Topps');await expect(page.locator('.listing-row').first()).toBeVisible();
 await page.getByLabel('Search this category').fill('impossible synthetic no match');await expect(page.locator('.listing-row')).toHaveCount(0);
 await page.getByLabel('Search this category').fill('');
 const example=indexRecords.find(r=>r.display_category==='UV Wantlist'&&r.brand==='Topps'&&/^\d{4}$/.test(r.year));expect(example).toBeTruthy();
 await page.getByRole('combobox',{name:'Year',exact:true}).fill(String(example.year));await page.getByRole('option',{name:String(example.year),exact:true}).click();
 await expect(page.locator('.listing-row').first()).toBeVisible();
 const yearCount=await page.locator('.listing-row').count();expect(yearCount).toBeGreaterThan(0);expect(yearCount).toBeLessThan(2517);
 await page.getByRole('combobox',{name:'Manufacturer',exact:true}).fill('Topps');await page.getByRole('option',{name:'Topps',exact:true}).click();
 await expect(page.getByRole('combobox',{name:'Manufacturer',exact:true})).toHaveValue('Topps');await expect(page.locator('.listing-row').first()).toBeVisible();
 expect(await page.locator('.listing-row').count()).toBeLessThanOrEqual(yearCount);expect(observed.unexpected).toEqual([]);expect(observed.pages).toBe(7);
});
test('third-page 404 displays no partial collection; explicit Retry starts a fresh complete load',async({page})=>{
 const observed=await mock(page,true);await page.goto(origin);
 await expect(page.getByRole('alert')).toContainText('could not be loaded');expect(observed.pages).toBe(3);await expect(page.locator('.listing-row')).toHaveCount(0);
 await page.getByRole('button',{name:'Try loading the list again'}).click();
 await expect(page.locator('.listing-row')).toHaveCount(583);expect(observed.pages).toBe(10);await expect(page.getByRole('alert')).toHaveCount(0);expect(observed.unexpected).toEqual([]);
});
