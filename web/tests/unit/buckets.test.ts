import { describe, expect, it } from 'vitest';
import { bucket, itemBuckets } from '../../src/lib/buckets';
import type { Item } from '../../src/lib/types';

describe('watch buckets', () => {
	it('matches the server implementation', async () => {
		// Same vector as server/tests/test_gtin.py::test_bucket_is_stable_and_short
		expect(await bucket('00860007132216')).toBe('2675');
	});

	it('groups items by bucket and skips items without barcodes', async () => {
		const base = {
			list: 'home',
			purchasedAt: '2026-11-01',
			addedAt: '',
			source: 'manual'
		} as const;
		const items: Item[] = [
			{ ...base, id: 'a', name: 'Cheddar', code: '860007132216' },
			{ ...base, id: 'b', name: 'Bananas' }
		];
		const map = await itemBuckets(items);
		expect([...map.keys()]).toEqual(['2675']);
		expect(map.get('2675')?.map((i) => i.id)).toEqual(['a']);
	});
});
