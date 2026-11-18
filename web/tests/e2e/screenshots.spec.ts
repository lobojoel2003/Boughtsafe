/**
 * Regenerates the README images in docs/images from a running Boughtsafe API.
 * Run against a fully synced catalog for realistic numbers:
 *   boughtsafe sync && boughtsafe serve   (in server/)
 *   npm run screenshots                     (in web/)
 */
import { expect, test, type Browser, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const OUT = fileURLToPath(new URL('../../../docs/images/', import.meta.url));
const PHONE = {
	viewport: { width: 390, height: 844 },
	deviceScaleFactor: 2,
	isMobile: true,
	hasTouch: true
};

test.skip(!process.env.SCREENSHOTS, 'set SCREENSHOTS=1 to regenerate README images');
test.describe.configure({ mode: 'serial' });

const GROCERIES = [
	'Bananas',
	'Whole milk 1 gal',
	'Large eggs dozen',
	'Sourdough bread',
	'Baby spinach',
	'Greek yogurt plain',
	'Ground coffee',
	'Rolled oats',
	'Peanut butter creamy',
	'Strawberry jam',
	'Pasta penne',
	'Marinara sauce',
	'Black beans',
	'Brown rice',
	'Cheddar cheese block',
	'Chicken thighs',
	'Frozen peas',
	'Olive oil',
	'Honey',
	'Granola',
	'Apples',
	'Carrots',
	'Hummus',
	'Tortilla chips'
];

async function phone(browser: Browser, colorScheme: 'light' | 'dark' = 'light') {
	const ctx = await browser.newContext({ ...PHONE, colorScheme });
	return ctx.newPage();
}

async function importCsv(page: Page, csv: string, list: 'home' | 'pantry' = 'home') {
	await page.goto(`/add/import${list === 'pantry' ? '?list=pantry' : ''}`);
	await page
		.locator('input[type=file]')
		.setInputFiles({ name: 'export.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
	await page.getByRole('button', { name: /^Import \d+ items?$/ }).click();
	await page.waitForURL(/\/(items|pantry)?$/);
}

async function addManual(
	page: Page,
	item: { name: string; code?: string; lot?: string; store?: string; date: string }
) {
	await page.goto('/add/manual');
	await page.getByLabel('Product name').fill(item.name);
	if (item.code) await page.getByLabel('Barcode (UPC / EAN)').fill(item.code);
	if (item.lot) await page.getByPlaceholder('e.g. LOT 3B1 274').fill(item.lot);
	await page.locator('input[type=date]').fill(item.date);
	if (item.store) await page.getByLabel('Store').fill(item.store);
	await page.getByTestId('save-item').click();
	await page.waitForURL('/');
}

const shot = (page: Page, name: string) =>
	page.screenshot({ path: OUT + name, animations: 'disabled' });

test('README screenshots', async ({ browser }) => {
	test.setTimeout(180_000);
	const page = await phone(browser);
	await page.goto('/');
	await expect(page.getByTestId('welcome')).toBeVisible();
	await shot(page, 'welcome.png');

	const csv = ['Date,Product,Store', ...GROCERIES.map((g) => `2026-11-02,${g},Kroger`)].join('\n');
	await importCsv(page, csv);
	await page.goto('/');
	await expect(page.getByText('Nothing you own is on a recall list.')).toBeVisible();
	await page.waitForTimeout(700);
	await shot(page, 'all-clear.png');

	await page.goto('/add/receipt');
	await page.getByText('Paste receipt text instead').click();
	await page
		.locator('textarea')
		.fill(
			'WinCo Foods\n10/01/26\nWINCO HOAGIE ROLLS 6CT 2.98 F\nGV WHL MLK 3.48 N\nBANANAS 1.24 N\nORG BABY SPNCH 3.97 N\nTOTAL 11.67'
		);
	await page.getByRole('button', { name: 'Read text' }).click();
	await shot(page, 'receipt.png');
	await page.getByRole('button', { name: /^Add \d+ items$/ }).click();
	await page.waitForURL('/');

	await addManual(page, {
		name: 'Family Farmstead Mild Raw Cheddar',
		code: '860007132216',
		lot: 'Best by JUL 22 27',
		store: 'Kroger',
		date: '2026-10-20'
	});
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.waitForTimeout(400);
	await shot(page, 'alert.png');

	// Element shots: hide the sticky header and tab bar so they don't overlap the card.
	const hideChrome = () =>
		page.addStyleTag({ content: '.top,.tabs{visibility:hidden !important}' });
	await hideChrome();
	const cards = page.getByTestId('recall-card');
	await cards.nth(1).scrollIntoViewIfNeeded();
	await cards.nth(1).screenshot({ path: OUT + 'name-match.png', animations: 'disabled' });

	await addManual(page, {
		name: 'Gelatelli Coffee & Vanilla Gelato',
		code: '4056489722458',
		store: 'Lidl',
		date: '2026-11-01'
	});
	await hideChrome();
	const upc = page.getByTestId('recall-card').filter({ hasText: 'UPC match' });
	await upc.scrollIntoViewIfNeeded();
	await upc.screenshot({ path: OUT + 'upc-check.png', animations: 'disabled' });

	await page.goto('/items');
	await shot(page, 'items.png');

	const pantry = [
		'Item Description,UPC,Lot #,Qty,Donor',
		'Gelatelli coffee gelato,4056489722458,085261,6,Holiday food drive',
		'Gelatelli coffee gelato,4056489722458,091102,4,Holiday food drive',
		'J. Higgs bacon cheddar chips,051933316454,,12,Corner Market',
		'Black beans 15 oz,036000291452,L2611,48,County food bank',
		'Peanut butter 16 oz,051500255162,2026-02,30,County food bank'
	].join('\n');
	await importCsv(page, pantry, 'pantry');
	await page.goto('/pantry');
	await page.waitForTimeout(400);
	await shot(page, 'pantry.png');

	await page.goto('/settings');
	await expect(page.getByText(/Connected to Boughtsafe/)).toBeVisible();
	await shot(page, 'settings.png');

	const dark = await phone(browser, 'dark');
	await addManual(dark, {
		name: 'Family Farmstead Mild Raw Cheddar',
		code: '860007132216',
		lot: 'Best by JUL 22 27',
		store: 'Kroger',
		date: '2026-10-20'
	});
	await dark.waitForTimeout(400);
	await shot(dark, 'alert-dark.png');
});

test('README hero image', async ({ browser }) => {
	const img = (n: string) => `data:image/png;base64,${readFileSync(OUT + n).toString('base64')}`;
	const page = await browser.newPage({
		viewport: { width: 1280, height: 720 },
		deviceScaleFactor: 2
	});
	await page.setContent(`<!doctype html><html><head><style>
		body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:radial-gradient(120% 120% at 20% 0%,#e8f1ec 0%,#f6f4ee 55%,#efe9dc 100%);width:1280px;height:720px;overflow:hidden;color:#1c2420}
		.wrap{display:flex;align-items:center;height:100%;padding:0 64px;gap:56px}
		.copy{width:380px}
		.mark{display:flex;align-items:center;gap:14px;font-weight:750;font-size:30px;letter-spacing:-.02em}
		h1{font-size:44px;line-height:1.08;letter-spacing:-.03em;margin:26px 0 16px}
		p{font-size:19px;line-height:1.5;color:#5d6963;margin:0}
		.phones{display:flex;gap:26px;align-items:flex-start}
		.phone{width:236px;border-radius:34px;padding:8px;background:#151a17;box-shadow:0 30px 60px -28px rgba(20,30,25,.55),0 2px 6px rgba(0,0,0,.15)}
		.phone img{width:100%;display:block;border-radius:27px}
		.phone:nth-child(2){margin-top:46px}
	</style></head><body><div class="wrap">
		<div class="copy">
			<div class="mark"><img src="${img('../../web/static/icons/logo-256.png')}" width="52" height="52">Boughtsafe</div>
			<h1>Silent until something you bought is recalled.</h1>
			<p>FDA, USDA FSIS and CPSC recalls matched to your receipts, barcodes and lot codes. Your purchases never leave your phone.</p>
		</div>
		<div class="phones">
			<div class="phone"><img src="${img('all-clear.png')}"></div>
			<div class="phone"><img src="${img('alert.png')}"></div>
			<div class="phone"><img src="${img('pantry.png')}"></div>
		</div>
	</div></body></html>`);
	await page.waitForTimeout(300);
	await page.screenshot({ path: OUT + 'hero.png' });
});
