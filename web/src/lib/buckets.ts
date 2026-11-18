import { toGtin14 } from './gtin';
import type { Item } from './types';

/** Must match boughtsafe.gtin.BUCKET_SALT on the server. */
export const BUCKET_SALT = 'boughtsafe/v1:';

const hex = (buf: ArrayBuffer) =>
	Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');

/**
 * 16-bit watch bucket for one GTIN-14. Devices register buckets, never barcodes:
 * each bucket is shared by about 1/65,536 of all products, so the server can't
 * tell what you bought.
 */
export async function bucket(gtin14: string): Promise<string> {
	const data = new TextEncoder().encode(BUCKET_SALT + gtin14);
	return hex(await crypto.subtle.digest('SHA-256', data)).slice(0, 4);
}

export async function itemBuckets(items: Item[]): Promise<Map<string, Item[]>> {
	const out = new Map<string, Item[]>();
	for (const item of items) {
		const g = toGtin14(item.code, item.codeFormat);
		if (!g) continue;
		const b = await bucket(g);
		out.set(b, [...(out.get(b) ?? []), item]);
	}
	return out;
}
