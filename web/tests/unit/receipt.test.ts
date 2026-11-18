import { describe, expect, it } from 'vitest';
import { cleanName, expandAbbreviations, parseReceipt } from '../../src/lib/receipt';

const WALMART = `
Walmart >|<
Save money. Live better.
( 555 ) 555 - 0100
ST# 01234 OP# 009 TE# 12 TR# 04321
GV WHL MLK 007874235186 F 3.48 N
WINCO HOAGIE ROLLS 6CT 2.98 F
BANANAS 000000004011 KF 1.24 N
2 @ 0.98
ORG BABY SPNCH 068826175045 F 3.97 N
COUPON 1.00-
SUBTOTAL 11.67
TAX 1 7.000 % 0.21
TOTAL 11.88
VISA TEND 11.88
CHANGE DUE 0.00
11/02/26 14:22:41
`;

describe('receipt parsing', () => {
	it('finds store, date and item lines', () => {
		const r = parseReceipt(WALMART);
		expect(r.store).toBe('Walmart');
		expect(r.date).toBe('2026-11-02');
		expect(r.lines.map((l) => l.name)).toEqual([
			'Great Value Whole Milk',
			'Winco Hoagie Rolls 6ct',
			'Bananas',
			'Organic Baby Spinach'
		]);
		expect(r.lines[0]).toMatchObject({ code: '007874235186', price: 3.48 });
		expect(r.lines[2].code).toBe('000000004011');
	});

	it('expands abbreviations', () => {
		expect(expandAbbreviations('KS ORG PB')).toBe('Kirkland Signature Organic Peanut Butter');
	});

	it('cleans quantities, prices and tax flags', () => {
		expect(cleanName('1234 CHKN BRST BNLS 2 @ 4.99 9.98 F')).toBe('Chicken Breast Boneless');
		expect(cleanName('Trader Joe’s cheddar')).toBe('Trader Joe s cheddar');
	});

	it('falls back to every line when no prices were read', () => {
		const r = parseReceipt("Trader Joe's\nUNEXPECTED CHEDDAR\nMANDARIN ORANGE CHICKEN");
		expect(r.store).toBe("Trader Joe's");
		expect(r.lines.map((l) => l.name)).toEqual(['Unexpected Cheddar', 'Mandarin Orange Chicken']);
	});
});
