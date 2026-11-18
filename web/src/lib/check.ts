/** Check what you own against the recall catalog. Shared by the app and service worker. */
import { api } from './api';
import { allItems, getItem, kvGet, kvSet, matchKey, saveCheckResults } from './db';
import type { CheckSummary, Item, StoredMatch, StoredRuledOut } from './types';

const CHUNK = 2000;

export interface LastCheck {
	checkedAt: string;
	items: number;
	catalogTotal: number;
	catalogVersion: string;
}

export async function lastCheck(): Promise<LastCheck | null> {
	return kvGet<LastCheck | null>('lastCheck', null);
}

/**
 * Run a check. With ``itemIds`` only those items are checked (after you add or
 * edit something); otherwise everything is. ``since`` limits the answer to
 * recalls changed after that time (used by background checks).
 */
export async function runCheck(
	opts: { itemIds?: string[]; since?: string; items?: Item[] } = {}
): Promise<CheckSummary> {
	const everything = !opts.itemIds && !opts.items;
	const items =
		opts.items ??
		(opts.itemIds
			? ((await Promise.all(opts.itemIds.map(getItem))).filter(Boolean) as Item[])
			: await allItems());

	let catalogTotal = 0;
	let catalogVersion = '';
	const found: Omit<StoredMatch, 'firstSeenAt' | 'state'>[] = [];
	const ruled: StoredRuledOut[] = [];
	for (let i = 0; i < items.length; i += CHUNK) {
		const res = await api.match(items.slice(i, i + CHUNK), opts.since);
		catalogTotal = res.catalog.total;
		catalogVersion = res.catalog.version;
		for (const m of res.matches) {
			found.push({
				key: matchKey(m.item_id, m.recall.id),
				itemId: m.item_id,
				recallId: m.recall.id,
				confidence: m.confidence,
				lotStatus: m.lot_status,
				score: m.score,
				matchedGtin: m.matched_gtin,
				matchedTerms: m.matched_terms,
				recall: m.recall
			});
		}
		for (const r of res.ruled_out) ruled.push({ ...r, key: matchKey(r.item_id, r.recall_id) });
	}

	const checked = new Set(items.map((i) => i.id));
	// A "since" check only sees new recalls, so it must not prune older matches.
	const newMatches = await saveCheckResults(checked, found, ruled, !opts.since);

	const checkedAt = new Date().toISOString();
	const prev = await lastCheck();
	const total = everything ? items.length : (await allItems()).length;
	if (items.length === 0 && prev) {
		catalogTotal = prev.catalogTotal;
		catalogVersion = prev.catalogVersion;
	}
	await kvSet('lastCheck', { checkedAt, items: total, catalogTotal, catalogVersion });
	return { checkedAt, items: total, catalogTotal, catalogVersion, newMatches };
}

/** Recheck when it's been a while; the catalog refreshes hourly on the server. */
export async function isStale(maxAgeMinutes = 15): Promise<boolean> {
	const last = await lastCheck();
	if (!last) return true;
	return Date.now() - Date.parse(last.checkedAt) > maxAgeMinutes * 60_000;
}
