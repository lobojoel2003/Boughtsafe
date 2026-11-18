import { describe, expect, it } from 'vitest';
import { parseGs1 } from '../../src/lib/gs1';
import { interpret } from '../../src/lib/scanner';

describe('GS1 element strings', () => {
	it('parses human-readable form', () => {
		expect(parseGs1('(01)00012345678905(17)270131(10)ABC123')).toEqual({
			gtin: '00012345678905',
			expiry: '2027-01-31',
			lot: 'ABC123'
		});
	});

	it('parses raw scanner output with FNC1 separators', () => {
		const raw = ']C1010001234567890510LOT42\u001d17270100';
		expect(parseGs1(raw)).toEqual({ gtin: '00012345678905', lot: 'LOT42', expiry: '2027-01-31' });
	});

	it('handles best-before and serial', () => {
		expect(parseGs1('0100012345678905152606302112345')).toEqual({
			gtin: '00012345678905',
			expiry: '2026-06-30',
			serial: '12345'
		});
	});

	it('rejects non-GS1 data', () => {
		expect(parseGs1('https://example.com')).toBeNull();
		expect(parseGs1('')).toBeNull();
	});

	it('scanner interpretation keeps plain barcodes and unpacks GS1', () => {
		expect(interpret('860007132216', 'upc_a')).toEqual({
			code: '860007132216',
			format: 'upc_a',
			raw: '860007132216'
		});
		expect(interpret('(01)00860007132216(10)L1', 'data_matrix')).toMatchObject({
			code: '00860007132216',
			lot: 'L1'
		});
		expect(interpret('hello', 'qr_code')).toBeNull();
	});
});
