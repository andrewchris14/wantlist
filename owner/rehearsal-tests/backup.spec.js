import {test,expect} from '@playwright/test';
import {resolve} from 'node:path';
import {readFileSync} from 'node:fs';
test('owner-local backup setup offers separate encrypted recovery and public key downloads without network access',async({page})=>{
 const remote=[];page.on('request',r=>{if(/^https?:/.test(r.url())&&r.url()!=='https://isolated.wantlist.test/backup-setup')remote.push(r.url());});await page.route('https://isolated.wantlist.test/backup-setup',route=>route.fulfill({contentType:'text/html',body:readFileSync(resolve('tools/backup-recovery.html'),'utf8')}));await page.goto('https://isolated.wantlist.test/backup-setup');
 await page.getByLabel('Recovery password',{exact:true}).first().fill('ephemeral-test-only-password-123');await page.getByLabel('Repeat recovery password').fill('ephemeral-test-only-password-123');await page.getByRole('button',{name:'Generate recovery files'}).click();
 const publicButton=page.getByRole('button',{name:'Download wantlist-public-key.json',exact:true});await expect(publicButton).toBeVisible({timeout:30000});const ready=page.waitForEvent('download');await publicButton.click();expect((await ready).suggestedFilename()).toBe('wantlist-public-key.json');
 const privateReady=page.waitForEvent('download');await page.getByRole('button',{name:'Download wantlist-private-recovery-key.ENCRYPTED.json',exact:true}).click();expect((await privateReady).suggestedFilename()).toContain('ENCRYPTED');expect(remote).toEqual([]);await expect(page.getByLabel('Repeat recovery password')).toHaveValue('');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
