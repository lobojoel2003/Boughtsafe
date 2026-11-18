import { kvGet } from './db';
import type { Item, MatchResponse, Meta, Product, Recall } from './types';

export const DEFAULT_API_BASE: string = import.meta.env.VITE_API_BASE || '/api';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

export async function apiBase(): Promise<string> {
	const custom = await kvGet<string>('apiBase', '');
	return (custom || DEFAULT_API_BASE).replace(/\/+$/, '');
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const base = await apiBase();
	let r: Response;
	try {
		r = await fetch(base + path, {
			...init,
			headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) }
		});
	} catch {
		throw new ApiError(0, "Can't reach the Boughtsafe server. Check your connection.");
	}
	if (!r.ok) {
		let detail = r.statusText;
		try {
			const body = await r.json();
			detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
		} catch {
			/* not JSON */
		}
		throw new ApiError(r.status, detail || `HTTP ${r.status}`);
	}
	return (r.status === 204 ? undefined : await r.json()) as T;
}

/** The fields the server needs to match an item. Sent per request, never stored there. */
export function toApiItem(i: Item) {
	return {
		id: i.id,
		code: i.code || null,
		code_format: i.codeFormat || null,
		lenient: !!i.lenient,
		lot: i.lot || null,
		name: i.name || null,
		brand: i.brand || null,
		purchased_at: i.purchasedAt || null
	};
}

export const api = {
	meta: () => request<Meta>('/v1/meta'),
	match: (items: Item[], since?: string) =>
		request<MatchResponse>('/v1/match', {
			method: 'POST',
			body: JSON.stringify({ items: items.map(toApiItem), since: since ?? null })
		}),
	product: (code: string, format?: string) =>
		request<Product>(
			`/v1/products/${encodeURIComponent(code)}${format ? `?format=${encodeURIComponent(format)}` : ''}`
		),
	recall: (id: string) => request<Recall>(`/v1/recalls/${encodeURIComponent(id)}`),
	subscribe: (sub: PushSubscriptionJSON, buckets: string[]) =>
		request<void>('/v1/push/subscriptions', {
			method: 'POST',
			body: JSON.stringify({ endpoint: sub.endpoint, keys: sub.keys, buckets })
		}),
	unsubscribe: (endpoint: string) =>
		request<void>('/v1/push/subscriptions', {
			method: 'DELETE',
			body: JSON.stringify({ endpoint })
		}),
	testPush: (endpoint: string) =>
		request<{ sent: boolean }>('/v1/push/test', {
			method: 'POST',
			body: JSON.stringify({ endpoint })
		})
};
