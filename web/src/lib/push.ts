/** Web Push: register the device and the watch buckets of what it owns. */
import { api } from './api';
import { itemBuckets } from './buckets';
import { allItems, kvGet, kvSet } from './db';

export type AlertState = 'enabled' | 'denied' | 'unsupported' | 'server-disabled' | 'error';

export function pushSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window
	);
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
	const padding = '='.repeat((4 - (base64.length % 4)) % 4);
	const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
	const out = new Uint8Array(new ArrayBuffer(raw.length));
	for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
	return out;
}

export async function alertsEnabled(): Promise<boolean> {
	return kvGet('notifications', false);
}

/** Register every bucket the device owns. Call after items change. */
export async function syncBuckets(sub?: PushSubscription | null): Promise<number> {
	if (!pushSupported()) return 0;
	const reg = await navigator.serviceWorker.ready;
	sub ??= await reg.pushManager.getSubscription();
	if (!sub) return 0;
	const buckets = [...(await itemBuckets(await allItems())).keys()];
	await api.subscribe(sub.toJSON(), buckets);
	return buckets.length;
}

export async function enableAlerts(): Promise<AlertState> {
	if (!pushSupported()) return 'unsupported';
	const meta = await api.meta();
	if (!meta.push_enabled || !meta.vapid_public_key) return 'server-disabled';
	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return 'denied';
	try {
		const reg = await navigator.serviceWorker.ready;
		const sub =
			(await reg.pushManager.getSubscription()) ??
			(await reg.pushManager.subscribe({
				userVisibleOnly: true,
				applicationServerKey: urlBase64ToUint8Array(meta.vapid_public_key)
			}));
		await syncBuckets(sub);
		await kvSet('notifications', true);
		await kvSet('pushEndpoint', sub.endpoint);
		// Daily on-device check where supported (installed Chromium apps).
		const periodic = (
			reg as ServiceWorkerRegistration & {
				periodicSync?: { register(tag: string, o: { minInterval: number }): Promise<void> };
			}
		).periodicSync;
		await periodic?.register('boughtsafe-daily', { minInterval: 24 * 3600 * 1000 }).catch(() => {});
		return 'enabled';
	} catch {
		return 'error';
	}
}

export async function disableAlerts(): Promise<void> {
	await kvSet('notifications', false);
	if (!pushSupported()) return;
	const reg = await navigator.serviceWorker.ready;
	const sub = await reg.pushManager.getSubscription();
	if (sub) {
		await api.unsubscribe(sub.endpoint).catch(() => {});
		await sub.unsubscribe();
	}
}

export async function sendTestAlert(): Promise<boolean> {
	const reg = await navigator.serviceWorker.ready;
	const sub = await reg.pushManager.getSubscription();
	if (!sub) return false;
	return (await api.testPush(sub.endpoint)).sent;
}
