/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
/**
 * Offline shell, plus the private half of push alerts: the server only says
 * "a recall touched these watch buckets"; this worker checks the device's own
 * items and notifies only if something you own really matches.
 */
import { build, files, version } from '$service-worker';
import { itemBuckets } from '$lib/buckets';
import { runCheck } from '$lib/check';
import { allItems } from '$lib/db';
import type { Item, StoredMatch } from '$lib/types';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `boughtsafe-${version}`;
const ASSETS = ['/', ...build, ...files.filter((f) => !f.endsWith('.map'))];
const ICON = '/icons/icon-192.png';
const BADGE = '/icons/badge-72.png';

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((c) => c.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key);
			await sw.clients.claim();
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);
	if (url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;

	event.respondWith(
		(async () => {
			const cache = await caches.open(CACHE);
			if (ASSETS.includes(url.pathname) && url.pathname !== '/') {
				const hit = await cache.match(url.pathname);
				if (hit) return hit;
			}
			try {
				const res = await fetch(req);
				if (res.ok && res.type === 'basic' && !req.headers.has('range')) {
					void cache.put(req, res.clone());
				}
				return res;
			} catch (err) {
				const hit =
					(await cache.match(req)) ??
					(req.mode === 'navigate' ? await cache.match('/') : undefined);
				if (hit) return hit;
				throw err;
			}
		})()
	);
});

async function tellClients() {
	for (const c of await sw.clients.matchAll({ type: 'window' }))
		c.postMessage({ type: 'matches-updated' });
}

async function showMatches(fresh: StoredMatch[], items: Item[]) {
	const byId = new Map(items.map((i) => [i.id, i]));
	for (const m of fresh.filter((f) => f.state === 'active')) {
		const item = byId.get(m.itemId);
		await sw.registration.showNotification(`Recall: ${item?.name ?? m.recall.title}`, {
			body: `${m.recall.hazard.label}. ${m.recall.action}`,
			tag: m.key,
			icon: ICON,
			badge: BADGE,
			data: { url: '/' },
			requireInteraction: m.recall.severity === 'high'
		});
	}
	await tellClients();
}

async function onRecallPush(buckets: string[]) {
	const items = await allItems();
	const byBucket = await itemBuckets(items);
	const candidates = [...new Set(buckets.flatMap((b) => byBucket.get(b) ?? []))];
	let fresh: StoredMatch[] = [];
	if (candidates.length) {
		try {
			fresh = (await runCheck({ items: candidates })).newMatches;
		} catch {
			fresh = [];
		}
	}
	if (fresh.some((f) => f.state === 'active')) return showMatches(fresh, items);
	// Browsers require every push to show a notification. A bucket is shared by
	// many products, so most wake-ups are for something you don't own: show the
	// required notification silently and remove it straight away.
	await sw.registration.showNotification('Boughtsafe', {
		body: 'Checked a new recall. Nothing you own is affected.',
		tag: 'boughtsafe-quiet',
		silent: true,
		icon: ICON,
		badge: BADGE
	});
	for (const n of await sw.registration.getNotifications({ tag: 'boughtsafe-quiet' })) n.close();
}

sw.addEventListener('push', (event) => {
	let data: { t?: string; b?: string[] } = {};
	try {
		data = event.data?.json() ?? {};
	} catch {
		/* not JSON */
	}
	if (data.t === 'test') {
		event.waitUntil(
			sw.registration.showNotification('Boughtsafe alerts are on', {
				body: "You'll only hear from us when something you own is recalled.",
				tag: 'boughtsafe-test',
				icon: ICON,
				badge: BADGE
			})
		);
		return;
	}
	event.waitUntil(onRecallPush(data.b ?? []));
});

// Daily on-device check (installed Chromium apps): no notification unless a match.
sw.addEventListener('periodicsync', (event) => {
	const e = event as ExtendableEvent & { tag: string };
	if (e.tag !== 'boughtsafe-daily') return;
	e.waitUntil(
		(async () => {
			const items = await allItems();
			if (!items.length) return;
			const { newMatches } = await runCheck();
			if (newMatches.length) await showMatches(newMatches, items);
		})().catch(() => {})
	);
});

sw.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const target = (event.notification.data?.url as string | undefined) ?? '/';
	event.waitUntil(
		(async () => {
			const windows = await sw.clients.matchAll({ type: 'window', includeUncontrolled: true });
			const open = windows.find((w) => new URL(w.url).origin === sw.location.origin);
			if (open) {
				await open.focus();
				return open.navigate(target).catch(() => {});
			}
			return sw.clients.openWindow(target);
		})()
	);
});
