import { defineConfig, devices } from '@playwright/test';

const screenshots = !!process.env.SCREENSHOTS;

export default defineConfig({
	testDir: 'tests/e2e',
	testMatch: screenshots ? /screenshots\.spec\.ts/ : /app\.spec\.ts/,
	fullyParallel: false,
	workers: 1,
	retries: process.env.CI ? 1 : 0,
	reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
	use: {
		baseURL: 'http://localhost:4173',
		trace: 'off',
		...devices['Pixel 7'],
		// One browser everywhere: the Pixel profile defaults to Chromium.
		browserName: 'chromium'
	},
	webServer: [
		{
			command: screenshots ? 'echo "using running API"' : 'bash tests/e2e/start-api.sh',
			url: 'http://127.0.0.1:8000/healthz',
			reuseExistingServer: true,
			timeout: 60_000
		},
		{
			command: 'npm run build && npx vite preview --port 4173 --strictPort',
			url: 'http://localhost:4173',
			reuseExistingServer: !process.env.CI,
			timeout: 180_000
		}
	]
});
