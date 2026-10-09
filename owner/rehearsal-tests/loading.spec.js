import {test,expect} from '@playwright/test';
test('whole collection index uses seven pages and lazily fetches inventory details',async({page})=>{
 await fetch('http://127.0.0.1:5181/reset',{method:'POST'});const requests=[];const origin='https://isolated.wantlist.test';
 await page.route(origin+'/**',async route=>{const req=route.request(),path=new URL(req.url()).pathname+new URL(req.url()).search;requests.push(path);const r=await(await fetch('http://127.0.0.1:5181/relay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,method:req.method(),headers:await req.allHeaders(),body:req.postData()})})).json();await route.fulfill({status:r.status,headers:r.headers,body:Buffer.from(r.body,'base64')});});
 await page.goto(origin);await expect(page.locator('.listing-row')).toHaveCount(583);
 expect(requests.filter(p=>p.startsWith('/public/index'))).toHaveLength(7);expect(requests.filter(p=>p.startsWith('/public/record'))).toHaveLength(0);expect(requests.filter(p=>p.startsWith('/public/page'))).toHaveLength(0);
 await page.getByRole('combobox',{name:'Category',exact:true}).selectOption('Milwaukee 8x10 List');await page.locator('.listing-row summary').click();await expect(page.locator('.listing-content')).toContainText('Aaron');expect(requests.filter(p=>p.startsWith('/public/record'))).toHaveLength(1);
});
