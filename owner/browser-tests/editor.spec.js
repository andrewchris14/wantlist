import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFileSync,mkdirSync} from 'node:fs';
import AxeBuilder from '@axe-core/playwright';
const credential=(JSON.parse(readFileSync('foundation/.local/staging-access.json','utf8')).pin||JSON.parse(readFileSync('foundation/.local/staging-access.json','utf8')).credential);
const origin='https://wantlist-staging.andrewchris14.workers.dev';
// No traces/HAR/body logging. Actual Worker/D1, not mocked API responses.
test.beforeEach(async({page})=>{
 mkdirSync('docs/evidence/phase3b3-revision',{recursive:true});
 // Isolate disposable staging test cases; production throttling is unchanged.
 execFileSync('python',['-c',"from foundation.staging.cloudflare import query; from foundation.staging.runner import state; query(state()['database_id'],'DELETE FROM login_limits')"]);
 await page.route(origin+'/**',async route=>{
  const req=route.request();const u=new URL(req.url());
  const result=await fetch('http://127.0.0.1:5181',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:u.pathname+u.search,method:req.method(),headers:await req.allHeaders(),body:req.postData()})});
  if(!result.ok){await route.abort();return;}
  const r=await result.json();await route.fulfill({status:r.status,headers:r.headers,body:Buffer.from(r.body,'base64')});
 });
 await page.goto('/');await expect(page.getByRole('button',{name:'Owner Login'})).toBeVisible();
});
async function login(page){await page.getByRole('button',{name:'Owner Login'}).click();await expect(page.getByLabel('Keep me signed in on this computer')).toBeChecked();await page.getByLabel('Owner PIN',{exact:true}).fill(credential);await page.getByLabel('Owner PIN',{exact:true}).press('Enter');await expect(page.getByRole('button',{name:'Log out'})).toBeVisible();}
async function create(page,name,status='want_list'){
 await page.getByRole('button',{name:'Add a new set',exact:true}).click();const d=page.getByRole('dialog');await d.getByLabel('Year or years').fill('2027');await d.getByLabel('Brand',{exact:true}).fill('Topps');await d.getByLabel('Set/name').fill(name);
 if(status!=='want_list'){await d.getByLabel('How to describe this set').selectOption(status);if(status==='complete')await d.getByRole('checkbox').check();}
 await d.getByRole('button',{name:'Create set'}).click();await expect(d.getByRole('button',{name:'Add cards',exact:true})).toBeVisible();
}
async function add(page,cards,owned=false,names=false){const d=page.getByRole('dialog');if(!await d.getByLabel('These are').isVisible())await d.getByRole('button',{name:'Add cards',exact:true}).click();if(owned)await d.getByLabel('These are').selectOption('owned');if(names)await d.getByLabel('What are you entering?').selectOption('names');await d.getByLabel(names?'One name or item on each line':'Card numbers or codes').fill(cards);await page.keyboard.press('Tab');await expect(d.getByRole('button',{name:'Add cards',exact:true})).toBeFocused();await page.keyboard.press('Enter');await expect(d.getByLabel('These are')).toHaveCount(0);}
function item(page,value){return page.getByRole('dialog').locator('.owner-item').filter({has:page.locator('strong').filter({hasText:new RegExp('^'+value+'$')})});}
async function change(page,value,action,state){const row=item(page,value);await row.getByRole('button',{name:action,exact:true}).click();await expect(row.getByText(state,{exact:true})).toBeVisible();}
async function recent(page){await page.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Recent Changes',exact:true}).click();await expect(page.getByRole('dialog').locator('.recent-list li').first()).toBeVisible();}

test('Dad card lifecycle, new set, metadata, restoration, Undo, remembered login and logout',async({page,context},info)=>{
 await login(page);const cookies=await context.cookies(origin);const c=cookies.find(c=>c.name==='__Host-wantlist_owner');expect(c.httpOnly&&c.secure).toBe(true);expect(c.sameSite).toBe('Strict');expect(c.expires-Date.now()/1000).toBeGreaterThan(89*86400);
 const name='2027 Topps — Practice '+Date.now().toString().slice(-8);await create(page,name);
 await add(page,'47');await add(page,'12 18 92 99');await add(page,'KCR2 BCP-47',true);
 const d=page.getByRole('dialog');
 await change(page,'47','Someone is sending this','Someone is sending this');await change(page,'47','Received','Already owned');
 await change(page,'92','Someone is sending this','Someone is sending this');await change(page,'92','Still need this','Still needed');await change(page,'18','Received','Already owned');
 await item(page,'99').getByText('More',{exact:true}).click();await item(page,'99').getByRole('button',{name:'Remove',exact:true}).click();await expect(item(page,'99')).toHaveCount(0);await d.getByText('Recently removed cards',{exact:true}).click();await d.getByRole('button',{name:'Restore',exact:true}).click();await expect(item(page,'99')).toBeVisible();
 await d.getByRole('button',{name:'Edit set information'}).click();await d.getByLabel('Notes',{exact:true}).fill('Practice collection notes — owner entered');await d.getByLabel('Brand',{exact:true}).fill('Topps Practice');await d.getByRole('button',{name:'Save',exact:true}).click();await expect(d.getByText('Practice collection notes — owner entered',{exact:true})).toBeVisible();

 await change(page,'12','Someone is sending this','Someone is sending this');await recent(page);await d.locator('.recent-list li').first().getByRole('button',{name:'Undo',exact:true}).click();await d.locator('.recent-list li').first().getByRole('button',{name:'Open set',exact:true}).click();await expect(item(page,'12').getByText('Still needed',{exact:true})).toBeVisible();
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 mkdirSync('docs/evidence/phase3b3-revision',{recursive:true});await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-cards.png`});
 await d.getByRole('button',{name:'Close',exact:true}).click();await page.reload();await expect(page.getByRole('button',{name:'Log out'})).toBeVisible();await page.getByRole('searchbox',{name:'Search this category'}).fill(name);await page.locator('.compact-list .listing-row').filter({has:page.locator('.listing-title').filter({hasText:name})}).first().locator('summary').click();await page.getByRole('button',{name:'Edit this set',exact:true}).click();await expect(d.getByText('Practice collection notes — owner entered',{exact:true})).toBeVisible();
 await d.getByRole('button',{name:'Remove set',exact:true}).click();await d.getByRole('button',{name:'Yes, remove this set'}).click();await page.getByRole('button',{name:'Recent Changes',exact:true}).click();await d.getByRole('button',{name:'Restore set',exact:true}).first().click();await d.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('button',{name:'Log out'}).click();await expect(page.getByRole('button',{name:'Owner Login'})).toBeVisible();await expect(page.getByRole('button',{name:'Edit this set'})).toHaveCount(0);
 const unauthorized=await page.evaluate(async()=>{const r=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op:'create',metadata:{set_name:'unauthorized'},request_id:crypto.randomUUID()})});return r.status;});expect(unauthorized).toBe(401);
});

test('Complete, names/codes, HAVE safety and reviewed staging searches',async({page},info)=>{
 await login(page);const name='2027 Topps — Complete Practice '+Date.now().toString().slice(-8);await create(page,name);
 await add(page,'Blue Border Practice Griffey\nSigned Practice Postcard',false,true);await add(page,'Red Border Practice Griffey',true,true);
 await expect(item(page,'Red Border Practice Griffey').getByText('Already owned',{exact:true})).toBeVisible();await expect(item(page,'Red Border Practice Griffey').getByRole('button',{name:'Received'})).toHaveCount(0);
 for(const value of ['Blue Border Practice Griffey','Signed Practice Postcard'])await change(page,value,'Received','Already owned');
 const d=page.getByRole('dialog');await d.getByRole('button',{name:'Edit set information'}).click();await d.getByLabel('How to describe this set').selectOption('complete');await d.getByRole('checkbox').check();await d.getByRole('button',{name:'Save',exact:true}).click();await expect(d.getByText('Complete — nothing needed',{exact:true})).toBeVisible();await d.getByRole('button',{name:'Add cards',exact:true}).click();await expect(d.getByRole('button',{name:'Add cards',exact:true})).toBeDisabled();await d.getByRole('button',{name:'Hide add cards'}).click();
 await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-complete.png`});await d.getByRole('button',{name:'Close',exact:true}).click();
 for(const q of ['Griffey','Costco','BCP','postcard','football']){await page.getByRole('combobox',{name:'Category',exact:true}).selectOption(q==='football'?'Football Wantlist':'UV Wantlist');await page.getByRole('searchbox',{name:'Search this category'}).fill(q);if(await page.locator('.compact-list .listing-row').count()===0)await page.locator('.other-matches button').first().click();await expect(page.locator('.compact-list .listing-row').first()).toBeVisible();}
 await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('UV Wantlist');await page.getByRole('searchbox',{name:'Search this category'}).fill('Blue Border Griffey');const card=page.locator('.compact-list .listing-row').filter({hasText:/Ritz\/Oreo/});await card.locator('summary').click();await expect(card).toContainText('Blue Border Griffey');await expect(card).toContainText('Red Border Griffey');
 const evidence=JSON.parse(readFileSync('foundation/staging/cpu-investigation-result.json','utf8'));const baseline=JSON.parse(readFileSync('data/wantlists.json','utf8')).records.find(r=>r.id===evidence.large_record_id);
 await page.getByRole('searchbox',{name:'Search this category'}).fill(baseline.set_name);await page.locator('.compact-list .listing-row').first().locator('summary').click();await page.getByRole('button',{name:'Edit this set',exact:true}).click();
 await page.getByLabel('Find a card in this set').fill(evidence.target_literal);await expect(item(page,evidence.target_literal)).toBeVisible();await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-large-set.png`});await page.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('button',{name:'Log out'}).click();
});


test('a lost save response retries the same change without duplicate cards',async({page},info)=>{
 await login(page);await create(page,'2027 Topps — Retry Practice '+Date.now().toString().slice(-8));
 let lost=false;const ids=[];
 await page.route(origin+'/action',async route=>{
  const req=route.request(),body=req.postDataJSON();ids.push(body.request_id);
  const response=await fetch('http://127.0.0.1:5181',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:'/action',method:'POST',headers:await req.allHeaders(),body:req.postData()})});const r=await response.json();
  if(!lost&&r.status===200){lost=true;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Simulated lost response after real commit'})});}
  else await route.fulfill({status:r.status,headers:r.headers,body:Buffer.from(r.body,'base64')});
 });
 const d=page.getByRole('dialog');await d.getByLabel('Card numbers or codes').fill('47');await d.getByRole('button',{name:'Add cards',exact:true}).click();
 await expect(d.getByRole('button',{name:'Try saving again'})).toBeVisible();await expect(d.getByRole('button',{name:'Add cards',exact:true})).toBeDisabled();
 await d.getByRole('button',{name:'Try saving again'}).click();await expect(item(page,'47')).toHaveCount(1);expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1]);
 await d.getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Log out'}).click();
});

test('an actually expired session asks Dad to verify this computer again',async({page,context})=>{
 await login(page);await create(page,'2027 Topps — Session Practice '+Date.now().toString().slice(-8));await add(page,'47');
 const cookie=(await context.cookies(origin)).find(c=>c.name==='__Host-wantlist_owner');const digest=createHash('sha256').update(cookie.value).digest('hex');
 // Technical test control, never sent to the frontend or logs; disposable session only.
 execFileSync('python',['-c',"import sys,time; from foundation.staging.cloudflare import query; from foundation.staging.runner import state; query(state()['database_id'],'UPDATE sessions SET created_at=?,expires_at=? WHERE token_hash=?',[int(time.time())-100,int(time.time())-1,sys.stdin.read()])"],{input:digest});
 await item(page,'47').getByRole('button',{name:'Received',exact:true}).click();
 await expect(page.getByRole('dialog').getByRole('heading',{name:'Owner Login'})).toBeVisible();await expect(page.getByRole('alert')).toContainText('This computer needs to be verified again');
 await page.getByLabel('Owner PIN',{exact:true}).fill(credential);await page.getByLabel('Owner PIN',{exact:true}).press('Enter');await expect(page.getByRole('button',{name:'Log out'})).toBeVisible();
 await page.getByRole('button',{name:'Log out'}).click();
});

test('compact listing, HAVE/WANT replacement, Undo and reload retain exact entered contents',async({page},info)=>{
 await login(page);const name='2027 Replacement Practice '+Date.now().toString().slice(-8);await create(page,name,'have_list');await add(page,'1 3 5 7 9',true);
 const d=page.getByRole('dialog');await d.getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('searchbox',{name:'Search this category'}).fill(name);
 const row=page.locator('.compact-list .listing-row').first();await expect(row).not.toHaveAttribute('open','');await row.locator('summary').click();await expect(row.locator('.listing-content')).toContainText('Cards I have:');await expect(row.locator('.listing-content')).not.toContainText('Cards I need:');await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-expanded-have.png`});await row.getByRole('button',{name:'Edit this set',exact:true}).click();
 async function replace(mode,values){await d.getByRole('button',{name:'Edit list',exact:true}).click();await d.getByLabel('New list type').selectOption(mode);await d.getByLabel('Replacement entries').fill(values);await d.getByRole('checkbox',{name:/I checked this replacement/}).check();if(mode==='want_list')await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-list-replacement.png`});await d.getByRole('button',{name:'Save replacement list'}).click();await expect(d.getByLabel('Replacement entries')).toHaveCount(0);}
 await replace('want_list','6 8 10');await expect(item(page,'6').getByText('Still needed',{exact:true})).toBeVisible();await expect(item(page,'1')).toHaveCount(0);await d.getByText('Previous list entries',{exact:true}).click();await expect(d.getByRole('button',{name:'Restore',exact:true})).toHaveCount(0);
 await recent(page);await d.locator('.recent-list li').first().getByRole('button',{name:'Undo',exact:true}).click();await d.locator('.recent-list li').first().getByRole('button',{name:'Open set',exact:true}).click();await expect(item(page,'1').getByText('Already owned',{exact:true})).toBeVisible();
 await replace('want_list','6 8 10');await replace('have_list','2 4');await expect(item(page,'2').getByText('Already owned',{exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('button',{name:'Log out'})).toBeVisible();await page.getByRole('searchbox',{name:'Search this category'}).fill(name);await page.locator('.compact-list .listing-row').first().locator('summary').click();await expect(page.locator('.listing-content')).toContainText('2; 4');await expect(page.locator('.listing-content')).not.toContainText('Cards I need:');await page.getByRole('button',{name:'Log out'}).click();
});

test('seven document categories, single special lists, uncertainty, compact rows and accessibility',async({page},info)=>{
 await expect(page.getByRole('combobox',{name:'Category',exact:true})).toHaveValue('OBC Wantlist');await expect(page.getByRole('option')).toHaveCount(7);await expect(page.getByLabel('Status',{exact:true})).toHaveCount(0);
 await expect(page.locator('.compact-list .listing-row').first()).toBeVisible();await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-compact-list.png`});
 for(const [category,label,value] of [['Eau Claire Players','Items I need:','Henry Aaron'],['Milwaukee 8x10 List','Items I have:','Aaron, H'],['Brewers Bobblehead Wantlist','Items I need:',null]]){
  await page.getByRole('combobox',{name:'Category',exact:true}).selectOption(category);const rows=page.locator('.compact-list .listing-row');await expect(rows).toHaveCount(1);await rows.first().locator('summary').click();await expect(rows.first()).toContainText(label);if(value)await expect(rows.first()).toContainText(value);if(category==='Milwaukee 8x10 List')await expect(rows.first()).not.toContainText('Items I need:');if(category==='Brewers Bobblehead Wantlist')await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-special-list.png`});await rows.first().locator('summary').click();await expect(rows.first()).not.toHaveAttribute('open','');
 }
 await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('OBC Wantlist');await page.getByRole('searchbox',{name:'Search this category'}).fill('Green Mountain');const uncertain=page.locator('.compact-list .listing-row').first();await uncertain.locator('summary').click();await expect(uncertain).toContainText('purportedly');await expect(uncertain).toContainText('HAVE list');await expect(uncertain).not.toContainText('UNCERTAIN');
 await page.getByRole('searchbox',{name:'Search this category'}).fill('');await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('UV Wantlist');await page.getByRole('searchbox',{name:'Search this category'}).fill('Blue Border Griffey');await page.locator('.compact-list .listing-row').first().locator('summary').click();await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-expanded-want.png`});
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('special listing supports individual items and notes without artificial set fields',async({page},info)=>{
 await login(page);await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('Eau Claire Players');await page.locator('.compact-list .listing-row summary').click();await page.getByRole('button',{name:'Edit this set',exact:true}).click();const d=page.getByRole('dialog');
 await d.getByLabel('Find an item in this list').fill('Henry Aaron');await expect(item(page,'Henry Aaron').getByRole('button',{name:'Received',exact:true})).toHaveCount(0);await expect(item(page,'Henry Aaron')).toContainText('Still needed');
 await d.getByRole('button',{name:'Add items',exact:true}).click();const name='Practice player card '+Date.now().toString().slice(-8);await d.getByLabel('One name or item on each line').fill(name);await d.getByRole('button',{name:'Add items',exact:true}).click();await d.getByLabel('Find an item in this list').fill(name);await expect(item(page,name)).toBeVisible();await change(page,name,'Someone is sending this','Someone is sending this');await change(page,name,'Still need this','Still needed');await change(page,name,'Received','Already owned');await item(page,name).getByText('Correct a mistake',{exact:true}).click();await change(page,name,'Still need this','Still needed');await item(page,name).getByText('More',{exact:true}).click();await item(page,name).getByRole('button',{name:'Remove',exact:true}).click();await d.getByText('Recently removed items',{exact:true}).click();await d.locator('.owner-group details p').filter({hasText:name}).getByRole('button',{name:'Restore',exact:true}).click();await expect(item(page,name)).toBeVisible();await item(page,name).getByText('More',{exact:true}).click();await item(page,name).getByRole('button',{name:'Remove',exact:true}).click();
 await d.getByRole('button',{name:'Edit set information'}).click();await expect(d.getByLabel('Year or years')).toHaveCount(0);await expect(d.getByLabel('Brand',{exact:true})).toHaveCount(0);const original=await d.getByRole('textbox',{name:'Notes',exact:true}).inputValue();await d.getByRole('textbox',{name:'Notes',exact:true}).fill(original+'\nPractice UX review note');await page.screenshot({path:`docs/evidence/phase3b3-revision/${info.project.name}-special-editor.png`});await d.getByRole('button',{name:'Save',exact:true}).click();await expect(d.getByText('Practice UX review note',{exact:true})).toBeVisible();await recent(page);await d.locator('.recent-list li').first().getByRole('button',{name:'Undo',exact:true}).click();await d.locator('.recent-list li').first().getByRole('button',{name:'Open set',exact:true}).click();await expect(d.getByText('Practice UX review note',{exact:true})).toHaveCount(0);await d.getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Log out'}).click();
});
