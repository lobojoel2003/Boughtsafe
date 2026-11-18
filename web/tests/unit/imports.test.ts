import { describe, expect, it } from 'vitest';
import { parseCsv, toCsv } from '../../src/lib/csv';
import { guessMapping, parseDate, rowsToItems } from '../../src/lib/imports';

describe('csv', () => {
	it('handles quotes, commas, CRLF and BOM', () => {
		const text = '\uFEFFname,upc\r\n"Cheddar, raw",860007132216\r\n"Say ""hi""",\r\n';
		expect(parseCsv(text)).toEqual([
			['name', 'upc'],
			['Cheddar, raw', '860007132216'],
			['Say "hi"', '']
		]);
	});

	it('guesses semicolons and tabs', () => {
		expect(parseCsv('a;b\n1;2')).toEqual([
			['a', 'b'],
			['1', '2']
		]);
		expect(parseCsv('a\tb\n1\t2')[1]).toEqual(['1', '2']);
	});

	it('round-trips', () => {
		const rows = [
			['a,b', 'c"d', 'e'],
			['1', '', '3']
		];
		expect(parseCsv(toCsv(rows))).toEqual(rows);
	});
});

describe('loyalty imports', () => {
	it('guesses columns from common export headers', () => {
		expect(guessMapping(['Order Date', 'Product Name', 'UPC', 'Qty', 'Store'])).toEqual({
			date: 0,
			name: 1,
			code: 2,
			quantity: 3,
			store: 4
		});
		expect(guessMapping(['Item Description', 'Brand', 'Lot #', 'Donor'])).toEqual({
			name: 0,
			brand: 1,
			lot: 2,
			donor: 3
		});
	});

	it('parses retailer date formats', () => {
		expect(parseDate('2026-03-14')).toBe('2026-03-14');
		expect(parseDate('3/14/2026')).toBe('2026-03-14');
		expect(parseDate('3/14/26')).toBe('2026-03-14');
		expect(parseDate('Mar 14, 2026')).toBe('2026-03-14');
		expect(parseDate('14 March 2026')).toBe('2026-03-14');
		expect(parseDate('nonsense')).toBeUndefined();
	});

	it('maps rows to items', () => {
		const rows = [
			['2026-10-01', 'WinCo Hoagie Rolls', '070552006492', '2', 'WinCo'],
			['', '', '', '', ''],
			['2026-10-02', '', '12', '1', '']
		];
		const items = rowsToItems(
			rows,
			{ date: 0, name: 1, code: 2, quantity: 3, store: 4 },
			{
				list: 'pantry'
			}
		);
		expect(items).toHaveLength(1);
		expect(items[0]).toMatchObject({
			list: 'pantry',
			name: 'WinCo Hoagie Rolls',
			code: '070552006492',
			lenient: true,
			quantity: 2,
			store: 'WinCo',
			purchasedAt: '2026-10-01',
			source: 'import'
		});
	});
});
