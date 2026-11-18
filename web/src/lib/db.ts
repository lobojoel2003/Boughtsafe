/**
 * Everything you own is stored here, in IndexedDB on this device, and nowhere else.
 * Used by both the app and the service worker.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { Item, ListKind, MatchState, StoredMatch, StoredRuledOut } from './types';

export const DB_NAME = 'boughtsafe';
const DB_VERSION = 1;

interface Schema extends DBSchema {
	items: { key: string; value: Item; indexes: { list: ListKind } };
	matches: { key: string; value: StoredMatch; indexes: { itemId: string; state: MatchState } };
	ruledOut: { key: string; value: StoredRuledOut; indexes: { itemId: string } };
	kv: { key: string; value: unknown };
}

let handle: Promise<IDBPDatabase<Schema>> | null = null;

export function database(): Promise<IDBPDatabase<Schema>> {
	handle ??= openDB<Schema>(DB_NAME, DB_VERSION, {
		upgrade(db) {
			const items = db.createObjectStore('items', { keyPath: 'id' });
			items.createIndex('list', 'list');
			const matches = db.createObjectStore('matches', { keyPath: 'key' });
			matches.createIndex('itemId', 'itemId');
			matches.createIndex('state', 'state');
			const ruled = db.createObjectStore('ruledOut', { keyPath: 'key' });
			ruled.createIndex('itemId', 'itemId');
			db.createObjectStore('kv');
		},
		blocking() {
			// A newer version of the app wants to upgrade: let it.
			void handle?.then((db) => db.close());
			handle = null;
		}
	});
	return handle;
}

/** Close and forget the connection (tests, and before deleting the database). */
export async function closeDatabase(): Promise<void> {
	if (handle) (await handle).close();
	handle = null;
}

export const matchKey = (itemId: string, recallId: string) => `${itemId}|${recallId}`;

export function newId(): string {
	return (
		globalThis.crypto?.randomUUID?.() ??
		`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
	);
}

// --- items -----------------------------------------------------------------------

export async function allItems(list?: ListKind): Promise<Item[]> {
	const db = await database();
	const rows = list ? await db.getAllFromIndex('items', 'list', list) : await db.getAll('items');
	return rows.sort((a, b) => b.addedAt.localeCompare(a.addedAt));
}

export async function getItem(id: string): Promise<Item | undefined> {
	return (await database()).get('items', id);
}

export async function putItems(items: Item[]): Promise<void> {
	const tx = (await database()).transaction('items', 'readwrite');
	await Promise.all([...items.map((i) => tx.store.put(i)), tx.done]);
}

export async function deleteItems(ids: string[]): Promise<void> {
	const db = await database();
	const tx = db.transaction(['items', 'matches', 'ruledOut'], 'readwrite');
	for (const id of ids) {
		await tx.objectStore('items').delete(id);
		for (const key of await tx.objectStore('matches').index('itemId').getAllKeys(id)) {
			await tx.objectStore('matches').delete(key);
		}
		for (const key of await tx.objectStore('ruledOut').index('itemId').getAllKeys(id)) {
			await tx.objectStore('ruledOut').delete(key);
		}
	}
	await tx.done;
}

// --- matches ---------------------------------------------------------------------

export async function allMatches(): Promise<StoredMatch[]> {
	return (await database()).getAll('matches');
}

export async function allRuledOut(): Promise<StoredRuledOut[]> {
	return (await database()).getAll('ruledOut');
}

export async function setMatchState(key: string, state: MatchState): Promise<void> {
	const db = await database();
	const m = await db.get('matches', key);
	if (!m) return;
	m.state = state;
	m.decidedAt = state === 'active' ? undefined : new Date().toISOString();
	await db.put('matches', m);
}

/**
 * Store a check's results. Decisions you already made (resolved, not mine) are kept.
 * Active matches for the checked items that the server no longer reports are removed.
 * Returns the matches seen for the first time.
 */
export async function saveCheckResults(
	checkedItemIds: Set<string>,
	found: Omit<StoredMatch, 'firstSeenAt' | 'state'>[],
	ruled: StoredRuledOut[],
	prune: boolean
): Promise<StoredMatch[]> {
	const db = await database();
	const tx = db.transaction(['matches', 'ruledOut'], 'readwrite');
	const matches = tx.objectStore('matches');
	const now = new Date().toISOString();
	const fresh: StoredMatch[] = [];
	const seen = new Set<string>();
	for (const f of found) {
		seen.add(f.key);
		const prev = await matches.get(f.key);
		const next: StoredMatch = prev
			? { ...prev, ...f }
			: { ...f, firstSeenAt: now, state: 'active' };
		if (!prev) fresh.push(next);
		await matches.put(next);
	}
	if (prune) {
		for (const m of await matches.getAll()) {
			if (checkedItemIds.has(m.itemId) && m.state === 'active' && !seen.has(m.key)) {
				await matches.delete(m.key);
			}
		}
	}
	const ruledStore = tx.objectStore('ruledOut');
	for (const r of await ruledStore.getAll()) {
		if (checkedItemIds.has(r.item_id)) await ruledStore.delete(r.key);
	}
	for (const r of ruled) await ruledStore.put(r);
	await tx.done;
	return fresh;
}

// --- key/value settings ------------------------------------------------------------

export async function kvGet<T>(key: string, fallback: T): Promise<T> {
	const v = await (await database()).get('kv', key);
	return v === undefined ? fallback : (v as T);
}

export async function kvSet(key: string, value: unknown): Promise<void> {
	await (await database()).put('kv', value, key);
}

// --- backup ----------------------------------------------------------------------

export interface Backup {
	app: 'boughtsafe';
	format: 1;
	exportedAt: string;
	items: Item[];
	matches: StoredMatch[];
}

export async function exportBackup(): Promise<Backup> {
	return {
		app: 'boughtsafe',
		format: 1,
		exportedAt: new Date().toISOString(),
		items: await allItems(),
		matches: await allMatches()
	};
}

export function isBackup(value: unknown): value is Backup {
	const v = value as Backup;
	return !!v && v.app === 'boughtsafe' && v.format === 1 && Array.isArray(v.items);
}

export async function importBackup(b: Backup): Promise<number> {
	const db = await database();
	const tx = db.transaction(['items', 'matches'], 'readwrite');
	for (const i of b.items) await tx.objectStore('items').put(i);
	for (const m of b.matches ?? []) await tx.objectStore('matches').put(m);
	await tx.done;
	return b.items.length;
}

export async function wipeEverything(): Promise<void> {
	const db = await database();
	const tx = db.transaction(['items', 'matches', 'ruledOut', 'kv'], 'readwrite');
	await Promise.all([
		tx.objectStore('items').clear(),
		tx.objectStore('matches').clear(),
		tx.objectStore('ruledOut').clear(),
		tx.objectStore('kv').clear(),
		tx.done
	]);
}
