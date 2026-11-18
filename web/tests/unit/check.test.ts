import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { runCheck, lastCheck } from '../../src/lib/check';
import {
	allMatches,
	allRuledOut,
	closeDatabase,
	deleteItems,
	putItems,
	setMatchState,
	wipeEverything
} from '../../src/lib/db';
import type { ApiMatch, Item, MatchResponse, Recall } from '../../src/lib/types';

const recall: Recall = {
	id: 'fda:H-0197-2027',
	source: 'fda',
	source_label: 'FDA',
	title: 'Family Farmstead Dairy recalls raw cheddar',
	product: 'Raw milk cheddar',
	firm: 'Family Farmstead Dairy, LLC',
	reason: 'E. coli',
	hazard: { kind: 'pathogen', label: 'E. coli', allergens: [] },
	classification: 'Class I',
	severity: 'high',
	status: 'ongoing',
	codes: 'Best By JUL 22 27',
	covers_all_codes: false,
	distribution: null,
	action: "Don't eat it.",
	refund: { options: ['Refund'], text: 'Return it.', contact: null },
	url: null,
	image_url: null,
	recall_date: '2026-10-14',
	published_date: '2026-11-11',
	gtins: [{ gtin: '00860007132216', display: '8 60007 13221 6' }]
};

const item = (id: string, extra: Partial<Item> = {}): Item => ({
	id,
	list: 'home',
	name: 'Raw cheddar',
	code: '860007132216',
	purchasedAt: '2026-10-20',
	addedAt: new Date().toISOString(),
	source: 'manual',
	...extra
});

function respond(matches: ApiMatch[], ruled: MatchResponse['ruled_out'] = []) {
	const body: MatchResponse = {
		matches,
		ruled_out: ruled,
		catalog: { version: '18-1', total: 18, checked_at: new Date().toISOString() }
	};
	return vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
}

const match = (itemId: string): ApiMatch => ({
	item_id: itemId,
	confidence: 'exact',
	lot_status: 'matched',
	score: 100,
	matched_gtin: recall.gtins[0],
	matched_terms: [],
	recall
});

describe('runCheck', () => {
	beforeEach(async () => {
		await wipeEverything();
	});
	afterEach(async () => {
		vi.unstubAllGlobals();
		await closeDatabase();
	});

	it('stores new matches and reports them once', async () => {
		await putItems([item('a')]);
		const fetchMock = respond([match('a')]);
		vi.stubGlobal('fetch', fetchMock);

		const first = await runCheck();
		expect(first.newMatches.map((m) => m.key)).toEqual(['a|fda:H-0197-2027']);
		const body = JSON.parse(
			(fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string
		);
		expect(body.items[0]).toMatchObject({
			id: 'a',
			code: '860007132216',
			purchased_at: '2026-10-20'
		});

		const second = await runCheck();
		expect(second.newMatches).toEqual([]);
		expect((await lastCheck())?.catalogTotal).toBe(18);
	});

	it('keeps your decision when the match is reported again', async () => {
		await putItems([item('a')]);
		vi.stubGlobal('fetch', respond([match('a')]));
		await runCheck();
		await setMatchState('a|fda:H-0197-2027', 'dismissed');
		await runCheck();
		expect((await allMatches())[0].state).toBe('dismissed');
	});

	it('prunes active matches the server no longer reports', async () => {
		await putItems([item('a')]);
		vi.stubGlobal('fetch', respond([match('a')]));
		await runCheck();
		vi.stubGlobal(
			'fetch',
			respond(
				[],
				[{ item_id: 'a', recall_id: recall.id, reason: 'lot_not_listed', title: recall.title }]
			)
		);
		await runCheck({ itemIds: ['a'] });
		expect(await allMatches()).toEqual([]);
		expect((await allRuledOut()).map((r) => r.reason)).toEqual(['lot_not_listed']);
	});

	it('does not prune on incremental (since) checks', async () => {
		await putItems([item('a')]);
		vi.stubGlobal('fetch', respond([match('a')]));
		await runCheck();
		vi.stubGlobal('fetch', respond([]));
		await runCheck({ since: new Date().toISOString() });
		expect(await allMatches()).toHaveLength(1);
	});

	it('deleting an item removes its matches', async () => {
		await putItems([item('a')]);
		vi.stubGlobal('fetch', respond([match('a')]));
		await runCheck();
		await deleteItems(['a']);
		expect(await allMatches()).toEqual([]);
	});

	it('surfaces server errors', async () => {
		await putItems([item('a')]);
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response('{"detail":"boom"}', { status: 500 }))
		);
		await expect(runCheck()).rejects.toThrow('boom');
	});
});
