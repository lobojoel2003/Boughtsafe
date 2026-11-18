/**
 * Import purchases from store loyalty / order-history exports (CSV) and from
 * Boughtsafe backups (JSON). Column names differ by retailer, so they're
 * guessed and the person can correct the mapping before importing.
 */
import { newId } from './db';
import { digitsOnly } from './gtin';
import { today } from './format';
import type { Item, ListKind } from './types';

export type Field = 'name' | 'brand' | 'code' | 'lot' | 'date' | 'store' | 'quantity' | 'donor';
export type Mapping = Partial<Record<Field, number>>;

export const FIELD_LABELS: Record<Field, string> = {
	name: 'Product name',
	brand: 'Brand',
	code: 'UPC / barcode',
	lot: 'Lot or best-by code',
	date: 'Purchase date',
	store: 'Store',
	quantity: 'Quantity',
	donor: 'Donor'
};

const PATTERNS: [Field, RegExp][] = [
	['code', /\b(upc|gtin|ean|barcode|bar code)\b/i],
	['lot', /\b(lot|batch|best[\s-]?by|expir|use[\s-]?by)\b/i],
	['brand', /\bbrand\b/i],
	['date', /\b(date|purchased|ordered|order date|transaction)\b/i],
	['store', /\b(store|retailer|merchant|seller|location|sold by)\b/i],
	['quantity', /\b(qty|quantity|count|units)\b/i],
	['donor', /\b(donor|donated by|source)\b/i],
	['name', /\b(product|item|description|name|title)\b/i]
];

export function guessMapping(header: string[]): Mapping {
	const mapping: Mapping = {};
	const used = new Set<number>();
	for (const [field, re] of PATTERNS) {
		const idx = header.findIndex((h, i) => !used.has(i) && re.test(h));
		if (idx >= 0) {
			mapping[field] = idx;
			used.add(idx);
		}
	}
	return mapping;
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

/** Parse the date formats retailers export into YYYY-MM-DD. */
export function parseDate(raw: string | undefined): string | undefined {
	const s = (raw ?? '').trim();
	if (!s) return undefined;
	let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
	if (m) return iso(+m[1], +m[2], +m[3]);
	m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})/);
	if (m) return iso(m[3].length === 2 ? 2000 + +m[3] : +m[3], +m[1], +m[2]);
	m = s.match(/^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})/);
	if (m && MONTHS.includes(m[1].toLowerCase()))
		return iso(+m[3], MONTHS.indexOf(m[1].toLowerCase()) + 1, +m[2]);
	m = s.match(/^(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})/);
	if (m && MONTHS.includes(m[2].toLowerCase()))
		return iso(+m[3], MONTHS.indexOf(m[2].toLowerCase()) + 1, +m[1]);
	const t = Date.parse(s);
	return Number.isNaN(t) ? undefined : new Date(t).toISOString().slice(0, 10);
}

function iso(y: number, mo: number, d: number): string | undefined {
	if (mo < 1 || mo > 12 || d < 1 || d > 31) return undefined;
	return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

export function rowsToItems(
	rows: string[][],
	mapping: Mapping,
	opts: { list: ListKind; store?: string } = { list: 'home' }
): Item[] {
	const get = (row: string[], f: Field) => {
		const i = mapping[f];
		return i === undefined ? '' : (row[i] ?? '').trim();
	};
	const now = new Date().toISOString();
	const out: Item[] = [];
	for (const row of rows) {
		const name = get(row, 'name');
		const code = digitsOnly(get(row, 'code'));
		if (!name && code.length < 8) continue;
		const qty = Number.parseFloat(get(row, 'quantity'));
		out.push({
			id: newId(),
			list: opts.list,
			name: name || `Barcode ${code}`,
			brand: get(row, 'brand') || undefined,
			code: code.length >= 8 ? code : undefined,
			lenient: code.length >= 8 ? true : undefined,
			lot: get(row, 'lot') || undefined,
			store: get(row, 'store') || opts.store || undefined,
			quantity: Number.isFinite(qty) && qty > 0 ? qty : undefined,
			donor: get(row, 'donor') || undefined,
			purchasedAt: parseDate(get(row, 'date')) ?? today(),
			addedAt: now,
			source: 'import'
		});
	}
	return out;
}
