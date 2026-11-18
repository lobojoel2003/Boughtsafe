import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

async function addManual(
	page: Page,
	item: { name: string; code?: string; lot?: string; date?: string; store?: string }
) {
	await page.goto('/add/manual');
	await page.getByLabel('Product name').fill(item.name);
	if (item.code) await page.getByLabel('Barcode (UPC / EAN)').fill(item.code);
	if (item.lot) await page.getByPlaceholder('e.g. LOT 3B1 274').fill(item.lot);
	await page.locator('input[type=date]').fill(item.date ?? '2026-10-20');
	if (item.store) await page.getByLabel('Store').fill(item.store);
	await page.getByTestId('save-item').click();
}

test('silent until something matches, then one clear card', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('welcome')).toBeVisible();

	// Something that isn't recalled: stays quiet.
	await addManual(page, { name: 'Oat milk', code: '036000291452' });
	await expect(page.getByText(/Not on any recall/)).toBeVisible();
	await page.goto('/');
	await expect(page.getByText('Nothing you own is on a recall list.')).toBeVisible();
	await expect(page.getByTestId('status')).toHaveText(/All clear/);

	// A real FDA recall, exact UPC and best-by date.
	await addManual(page, {
		name: 'Family Farmstead Mild Raw Cheddar',
		code: '860007132216',
		lot: 'Best by JUL 22 27',
		store: 'Kroger'
	});
	await expect(page).toHaveURL('/');
	const card = page.getByTestId('recall-card');
	await expect(card).toHaveCount(1);
	await expect(card.getByText('Exact match · UPC + lot')).toBeVisible();
	await expect(card.getByText('E. coli', { exact: true })).toBeVisible();
	await expect(card.getByText('Take it back to Kroger for a full refund.')).toBeVisible();
	await expect(page.getByTestId('status')).toHaveText('1 recall');

	await card.getByRole('button', { name: "I've dealt with it" }).click();
	await expect(page.getByText('Nothing you own is on a recall list.')).toBeVisible();
});

test('UPC-only match clears when the package code is not listed', async ({ page }) => {
	await addManual(page, { name: 'Raw cheddar', code: '8 60007 13221 6' });
	const card = page.getByTestId('recall-card');
	await expect(card.getByText('UPC match · check the lot')).toBeVisible();
	await card.getByLabel('Lot or best-by code on your package').fill('Best by AUG 01 27');
	await card.getByRole('button', { name: 'Check' }).click();
	await expect(page.getByText("Good news: your package isn't affected.")).toBeVisible();
	await expect(page.getByTestId('recall-card')).toHaveCount(0);

	// The item page explains why it was ruled out.
	await page.goto('/items');
	await page.getByTestId('item-row').first().click();
	await expect(page.getByText(/your code .* isn't listed/)).toBeVisible();
});

test('receipt text becomes items and name-only matches are labelled', async ({ page }) => {
	await page.goto('/add/receipt');
	await page.getByText('Paste receipt text instead').click();
	await page
		.locator('textarea')
		.fill('WinCo Foods\n10/01/26\nWINCO HOAGIE ROLLS 6CT 2.98 F\nGV WHL MLK 3.48 N\nTOTAL 6.46');
	await page.getByRole('button', { name: 'Read text' }).click();
	await expect(page.getByLabel('Store')).toHaveValue('WinCo');
	await page.getByRole('button', { name: 'Add 2 items' }).click();
	await expect(page).toHaveURL('/');
	const card = page.getByTestId('recall-card');
	await expect(card.getByText('Possible match · name only')).toBeVisible();
	await expect(card.getByText('Undeclared sesame')).toBeVisible();
	await card.getByRole('button', { name: 'Not mine' }).click();
	await expect(page.getByTestId('recall-card')).toHaveCount(0);
});

test('pantry imports stock by UPC and lot and builds a pull list', async ({ page }) => {
	await page.goto('/add/import?list=pantry');
	const csv = [
		'Item Description,UPC,Lot #,Qty,Donor',
		'Gelatelli coffee gelato,4056489722458,085261,6,Food drive',
		'Gelatelli coffee gelato,4056489722458,999999,4,Food drive',
		'Canned beans,036000291452,L123,24,Grocer'
	].join('\n');
	await page.locator('input[type=file]').setInputFiles({
		name: 'inventory.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(csv)
	});
	await expect(page.getByRole('button', { name: 'Import 3 items' })).toBeVisible();
	await page.getByRole('button', { name: 'Import 3 items' }).click();
	await expect(page).toHaveURL('/');

	await page.goto('/pantry');
	const pull = page.getByRole('region', { name: 'Pull from shelves' });
	await expect(pull.getByRole('listitem')).toHaveCount(1); // only the listed lot
	await expect(pull.getByText('085261')).toBeVisible();
	await expect(pull.getByText('UPC + lot')).toBeVisible();

	const [download] = await Promise.all([
		page.waitForEvent('download'),
		pull.getByRole('button', { name: 'CSV' }).click()
	]);
	const text = readFileSync((await download.path())!, 'utf8');
	expect(text).toContain('085261');
	expect(text).not.toContain('999999');
});

test('settings shows the server, its sources and the build', async ({ page }) => {
	await page.goto('/settings');
	await expect(page.getByText(/Connected to Boughtsafe/)).toBeVisible();
	await expect(page.getByRole('cell', { name: 'FDA' })).toBeVisible();
	await expect(page.getByText(/12 recalls/)).toBeVisible();
	await expect(page.getByText(/build/).first()).toBeVisible();
});

test('works offline after the first visit', async ({ page, context }) => {
	await page.goto('/');
	await page.evaluate(() => navigator.serviceWorker.ready);
	await page.reload();
	await context.setOffline(true);
	await page.goto('/items');
	await expect(page.getByRole('heading', { name: 'Your items' })).toBeVisible();
	await context.setOffline(false);
});
