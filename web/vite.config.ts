import { readFileSync } from 'node:fs';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const version = readFileSync(new URL('../VERSION', import.meta.url), 'utf8').trim();
const api = process.env.BOUGHTSAFE_API_PROXY ?? 'http://127.0.0.1:8000';
const proxy = {
	'/api': { target: api, changeOrigin: true, rewrite: (p: string) => p.replace(/^\/api/, '') }
};

export default defineConfig({
	plugins: [sveltekit()],
	define: {
		__APP_VERSION__: JSON.stringify(version),
		__BUILD_NUMBER__: JSON.stringify(process.env.BUILD_NUMBER ?? 'dev'),
		__GIT_SHA__: JSON.stringify((process.env.GIT_SHA ?? 'local').slice(0, 12)),
		__BUILD_DATE__: JSON.stringify(new Date().toISOString().slice(0, 10))
	},
	server: { proxy },
	preview: { proxy },
	build: { target: 'es2022', sourcemap: true },
	test: {
		include: ['tests/unit/**/*.test.ts'],
		environment: 'jsdom',
		setupFiles: ['tests/unit/setup.ts']
	}
});
