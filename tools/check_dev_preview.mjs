// Test the live Vite server, independently of a production build.
// Set WANTLIST_PREVIEW_URL to an externally provided cloud preview URL to
// exercise that forwarding route too; never fabricate a public preview URL.
import { chromium } from '@playwright/test';
import { existsSync, mkdirSync } from 'node:fs';

const address = process.env.WANTLIST_PREVIEW_URL || 'http://127.0.0.1:5173';
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
const browser = await chromium.launch({ executablePath, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(address, { waitUntil: 'networkidle' });
  for (const locator of [page.getByRole('heading', { name: 'Baseball Card Want List' }),
    page.getByRole('searchbox'), page.getByRole('combobox', { name: 'Status' }),
    page.getByRole('combobox', { name: 'Year' }), page.getByRole('combobox', { name: 'Brand' }),
    page.getByRole('combobox', { name: 'Category' }), page.getByRole('article').first()]) {
    await locator.waitFor({ state: 'visible' });
  }
  await page.getByRole('searchbox').fill('Griffey');
  await page.getByRole('article').first().waitFor({ state: 'visible' });
  console.log('Live development browser: homepage, search, all filters, and result card rendered.');
  console.log('Griffey:', await page.getByRole('status').textContent());
  await page.getByRole('combobox', { name: 'Status' }).selectOption('have_list');
  await page.getByRole('article').first().waitFor({ state: 'visible' });
  if (await page.getByRole('article').first().getByRole('list', { name: 'Wanted cards and items' }).count()) {
    throw new Error('Owned record incorrectly rendered as a want list.');
  }
  console.log('HAVE filter:', await page.getByRole('status').textContent());
  await page.getByRole('button', { name: 'Clear search & filters' }).click();
  await page.getByRole('searchbox').fill('2025 Topps Flagship');
  await page.getByRole('combobox', { name: 'Category' }).selectOption('baseball_cards');
  await page.getByRole('article').first().waitFor({ state: 'visible' });
  console.log('Corrected Flagship baseball filter:', await page.getByRole('status').textContent());
  if (errors.length) throw new Error(errors.join('\n'));
  mkdirSync('test-results', { recursive: true });
  await page.getByRole('article').first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/live-development.png' });
  console.log('No browser page errors. Live-development screenshot saved.');
  console.log(process.env.WANTLIST_PREVIEW_URL ? 'Provided preview route tested.' :
    'Internal live server tested. External Codex forwarding route is not verified without its URL/open-port mechanism.');
} finally {
  await browser.close();
}
