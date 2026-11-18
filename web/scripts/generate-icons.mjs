// Render the Boughtsafe mark to the PNG icons the web app manifest needs.
// Usage: node scripts/generate-icons.mjs   (needs Playwright's Chromium)
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';

const out = fileURLToPath(new URL('../static/icons/', import.meta.url));
const GREEN = '#1e6a49';
const mark = (fg, cut) => `
  <path d="M13 18.5h22l-1.6 17.2a3 3 0 0 1-3 2.8H17.6a3 3 0 0 1-3-2.8L13 18.5z" fill="${fg}"/>
  <path d="M19 18.5v-2a5 5 0 0 1 10 0v2" fill="none" stroke="${fg}" stroke-width="2.6" stroke-linecap="round"/>
  <path d="M19.2 28.2l3.4 3.4 6.4-6.6" fill="none" stroke="${cut}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>`;

const icons = [
	// Rounded tile, transparent corners.
	{
		name: 'icon-192.png',
		size: 192,
		svg: `<rect x="2" y="2" width="44" height="44" rx="13" fill="${GREEN}"/>${mark('#fff', GREEN)}`
	},
	{
		name: 'icon-512.png',
		size: 512,
		svg: `<rect x="2" y="2" width="44" height="44" rx="13" fill="${GREEN}"/>${mark('#fff', GREEN)}`
	},
	// Full-bleed background, mark inside the 80% safe zone.
	{
		name: 'maskable-512.png',
		size: 512,
		svg: `<rect width="48" height="48" fill="${GREEN}"/><g transform="translate(24 24) scale(0.78) translate(-24 -26)">${mark('#fff', GREEN)}</g>`
	},
	{
		name: 'apple-touch-icon.png',
		size: 180,
		svg: `<rect width="48" height="48" fill="${GREEN}"/><g transform="translate(24 24) scale(0.92) translate(-24 -26)">${mark('#fff', GREEN)}</g>`
	},
	// Monochrome notification badge (Android uses only the alpha channel).
	{
		name: 'badge-72.png',
		size: 72,
		svg: `<g transform="translate(24 24) scale(1.25) translate(-24 -27)">${mark('#fff', 'transparent')}</g>`,
		transparent: true
	},
	{
		name: 'logo-256.png',
		size: 256,
		svg: `<rect x="2" y="2" width="44" height="44" rx="13" fill="${GREEN}"/>${mark('#fff', GREEN)}`
	}
];

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const icon of icons) {
	await page.setViewportSize({ width: icon.size, height: icon.size });
	await page.setContent(
		`<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="${icon.size}" height="${icon.size}">${icon.svg}</svg></body></html>`
	);
	await page.screenshot({ path: out + icon.name, omitBackground: true });
	console.log('wrote', icon.name);
}
await browser.close();
