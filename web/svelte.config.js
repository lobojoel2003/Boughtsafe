import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// A single-page app: every route renders on the device, nothing on a server.
		adapter: adapter({ fallback: 'index.html', precompress: true }),
		serviceWorker: { register: false },
		// Hash-based CSP, emitted as a <meta> tag in the static pages. Tesseract.js
		// loads its worker, WASM core and language data from jsDelivr; product photos
		// come from Open Food Facts and the CPSC.
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'script-src': ['self', 'wasm-unsafe-eval', 'blob:', 'https://cdn.jsdelivr.net'],
				'worker-src': ['self', 'blob:'],
				'connect-src': ['self', 'https:', 'blob:', 'data:'],
				'img-src': ['self', 'data:', 'blob:', 'https:'],
				'media-src': ['self', 'blob:', 'mediastream:'],
				'style-src': ['self', 'unsafe-inline'],
				'font-src': ['self'],
				'manifest-src': ['self'],
				'object-src': ['none'],
				'base-uri': ['self'],
				'form-action': ['self']
			}
		},
		version: { name: process.env.GIT_SHA ?? undefined }
	}
};

export default config;
