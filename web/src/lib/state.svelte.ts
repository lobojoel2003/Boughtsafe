/** App-wide reactive state, backed by IndexedDB. */
import { lastCheck, runCheck, type LastCheck } from './check';
import { allItems, allMatches, allRuledOut, deleteItems, putItems, setMatchState } from './db';
import { alertsEnabled, syncBuckets } from './push';
import type { Item, MatchState, StoredMatch, StoredRuledOut } from './types';

const CONFIDENCE = { exact: 0, upc: 1, name: 2 } as const;
const SEVERITY = { high: 0, medium: 1, low: 2 } as const;

export function byUrgency(a: StoredMatch, b: StoredMatch): number {
	return (
		CONFIDENCE[a.confidence] - CONFIDENCE[b.confidence] ||
		SEVERITY[a.recall.severity] - SEVERITY[b.recall.severity] ||
		(b.recall.recall_date ?? '').localeCompare(a.recall.recall_date ?? '')
	);
}

export interface Alert {
	item: Item;
	match: StoredMatch;
	/** Other notices that matched the same item (e.g. several sizes of one product). */
	related: StoredMatch[];
}

export interface Toast {
	id: number;
	text: string;
	tone: 'ok' | 'info' | 'danger';
}

class AppState {
	items = $state<Item[]>([]);
	matches = $state<StoredMatch[]>([]);
	ruledOut = $state<StoredRuledOut[]>([]);
	last = $state<LastCheck | null>(null);
	loaded = $state(false);
	checking = $state(false);
	error = $state<string | null>(null);
	toasts = $state<Toast[]>([]);

	// Rebuilt whenever items change, never mutated, so a plain Map is fine here.
	itemsById = $derived(new Map(this.items.map((i) => [i.id, i])));

	/** One alert per item you own, most urgent first. */
	alerts: Alert[] = $derived.by(() => {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity
		const byItem = new Map<string, StoredMatch[]>();
		for (const m of this.matches) {
			if (m.state !== 'active' || !this.itemsById.has(m.itemId)) continue;
			byItem.set(m.itemId, [...(byItem.get(m.itemId) ?? []), m]);
		}
		return [...byItem.entries()]
			.map(([itemId, ms]) => {
				const sorted = ms.sort(byUrgency);
				return { item: this.itemsById.get(itemId)!, match: sorted[0], related: sorted.slice(1) };
			})
			.sort((a, b) => byUrgency(a.match, b.match));
	});

	async load(): Promise<void> {
		await this.reload();
		this.loaded = true;
	}

	async reload(): Promise<void> {
		const [items, matches, ruled, last] = await Promise.all([
			allItems(),
			allMatches(),
			allRuledOut(),
			lastCheck()
		]);
		this.items = items;
		this.matches = matches;
		this.ruledOut = ruled;
		this.last = last;
	}

	async check(opts: { itemIds?: string[]; quiet?: boolean } = {}): Promise<StoredMatch[]> {
		if (this.checking && !opts.itemIds) return [];
		this.checking = true;
		this.error = null;
		try {
			const summary = await runCheck({ itemIds: opts.itemIds });
			await this.reload();
			return summary.newMatches;
		} catch (e) {
			this.error = e instanceof Error ? e.message : String(e);
			if (!opts.quiet) this.toast(this.error, 'danger');
			return [];
		} finally {
			this.checking = false;
		}
	}

	async addItems(items: Item[]): Promise<StoredMatch[]> {
		if (!items.length) return [];
		await putItems(items);
		await this.reload();
		const found = await this.check({ itemIds: items.map((i) => i.id) });
		void this.syncAlerts();
		return found;
	}

	async saveItem(item: Item): Promise<StoredMatch[]> {
		return this.addItems([item]);
	}

	async removeItems(ids: string[]): Promise<void> {
		await deleteItems(ids);
		await this.reload();
		void this.syncAlerts();
	}

	async decide(key: string, state: MatchState): Promise<void> {
		await setMatchState(key, state);
		await this.reload();
	}

	async syncAlerts(): Promise<void> {
		if (await alertsEnabled()) await syncBuckets().catch(() => 0);
	}

	toast(text: string, tone: Toast['tone'] = 'ok'): void {
		const id = Date.now() + Math.random();
		this.toasts = [...this.toasts, { id, text, tone }];
		setTimeout(() => (this.toasts = this.toasts.filter((t) => t.id !== id)), 4200);
	}
}

export const app = new AppState();
