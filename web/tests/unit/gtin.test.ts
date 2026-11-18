import { describe, expect, it } from 'vitest';
import { checkDigit, display, isValid, prettyCode, toGtin14, upceToUpca } from '../../src/lib/gtin';

describe('gtin', () => {
	it('computes GS1 check digits', () => {
		expect(checkDigit('03600029145')).toBe(2);
		expect(isValid('036000291452')).toBe(true);
		expect(isValid('036000291453')).toBe(false);
		expect(isValid('4006381333931')).toBe(true);
	});

	it('expands UPC-E like the server', () => {
		expect(upceToUpca('04252614')).toBe('042100005264');
		expect(upceToUpca('01234558')).toBe('012345000058');
		expect(upceToUpca('01234133')).toBe('012300000413');
		expect(upceToUpca('01234505')).toBe('012000003455');
		expect(upceToUpca('01234500')).toBeNull();
	});

	it('normalizes to GTIN-14', () => {
		expect(toGtin14('0 36000 29145 2')).toBe('00036000291452');
		expect(toGtin14('04252614', 'upc_e')).toBe('00042100005264');
		expect(toGtin14('96385074', 'ean_8')).toBe('00000096385074');
		expect(toGtin14('123')).toBeNull();
	});

	it('formats for people', () => {
		expect(display('00070552006492')).toBe('0 70552 00649 2');
		expect(display('04056489722458')).toBe('4 056489 722458');
		expect(prettyCode('860007132216')).toBe('8 60007 13221 6');
		expect(prettyCode('12345')).toBe('12345');
	});
});
