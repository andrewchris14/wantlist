import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText('3,392 lists');
});

test('production data loads and layout fits the viewport', async ({ page }, testInfo) => {
  await expect(page.getByRole('heading', { name: 'Baseball Card Want List' })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(30);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `test-results/${testInfo.project.name}-homepage.png`, fullPage: false });
});

test('representative searches, notes, and statuses remain available', async ({ page }) => {
  for (const query of ['Topps', '2012 Topps', 'Milwaukee Brewers', 'BCP', 'postcard', 'bobblehead', 'football', 'Good enough']) {
    await page.getByRole('searchbox').fill(query);
    await expect(page.getByRole('article').first()).toBeVisible();
  }
  await page.getByRole('searchbox').fill('1980 Unknown Manufacturer');
  const uncertain = page.getByRole('article').first();
  await expect(uncertain.getByText('UNCERTAIN', { exact: true })).toBeVisible();
  await expect(uncertain.getByText('Believed to be complete', { exact: true }).first()).toBeVisible();
});

test('Griffey variants retain separate wanted and owned labels', async ({ page }, testInfo) => {
  await page.getByRole('searchbox').fill('  bLuE  Border   GRIFFEY  ');
  await expect(page.getByRole('status')).toHaveText('1 list of 3,392');
  const card = page.getByRole('article');
  await expect(card.getByRole('list', { name: 'Wanted cards and items' }).getByText('Blue Border Griffey')).toBeVisible();
  await expect(card.getByRole('region', { name: 'Cards / items I have' }).getByText('Red Border Griffey')).toBeVisible();
  await card.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `test-results/${testInfo.project.name}-griffey.png`, fullPage: false });
});

test('HAVE and Complete labels cannot be mistaken for wanted lists', async ({ page }) => {
  await page.getByRole('searchbox').fill('1978 Burger King Tigers');
  const owned = page.getByRole('article');
  await expect(owned.getByText('HAVE', { exact: true })).toBeVisible();
  await expect(owned.getByText(/These are owned items, not wants/)).toBeVisible();
  await expect(owned.getByRole('list', { name: 'Owned cards and items' })).toHaveText(/9.*12.*18.*19/);
  await expect(owned.getByRole('list', { name: 'Wanted cards and items' })).toHaveCount(0);
  await page.getByRole('searchbox').fill('2019 Topps Holiday');
  await expect(page.getByRole('article').getByText('Complete — nothing currently needed.')).toBeVisible();
  await expect(page.getByRole('article').getByRole('list')).toHaveCount(0);
});

test('filters, sorting, pagination, and clear restore expected results', async ({ page }) => {
  await page.getByRole('button', { name: 'Next →' }).click();
  await expect(page.getByText('Page 2 of 114', { exact: false })).toBeVisible();
  await page.getByRole('combobox', { name: 'Category' }).selectOption('bobbleheads');
  await expect(page.getByRole('status')).toHaveText('26 lists of 3,392');
  await page.getByRole('combobox', { name: 'Status' }).selectOption('want_list');
  await page.getByRole('combobox', { name: 'Year' }).selectOption('2026');
  await expect(page.getByRole('article')).toHaveCount(1);
  await expect(page.getByRole('article').getByText('Hello Kitty', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Clear search & filters' }).click();
  await expect(page.getByRole('status')).toHaveText('3,392 lists');
  await page.getByRole('combobox', { name: 'Sort by' }).selectOption('oldest');
  await expect(page.getByRole('article').first()).toContainText('1914-18');
});

test('keyboard controls, no horizontal overflow, and accessible contrast', async ({ page }) => {
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to results' })).toBeFocused();
  await page.getByRole('searchbox').focus();
  await page.keyboard.type('Griffey');
  await expect(page.getByRole('article').first()).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('no browser errors during search or malformed-record rendering', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/wantlists.json', route => route.fulfill({ json: { records: [{ id: 'broken', notes: null, mixed_lists: [null, {}] }] } }));
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Untitled collecting list' })).toBeVisible();
  await page.getByRole('searchbox').fill('nonexistent');
  await expect(page.getByRole('heading', { name: 'No matching lists' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('narrow phones and tablets retain usable controls and fit the viewport', async ({ page }) => {
  for (const width of [320, 768, 1024]) {
    await page.setViewportSize({ width, height: 1024 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole('searchbox').fill('Griffey');
    await page.getByRole('combobox', { name: 'Status' }).selectOption('want_list');
    await expect(page.getByRole('article').first()).toBeVisible();
  }
});
