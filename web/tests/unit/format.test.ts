import { describe, expect, it } from 'vitest';
import { plural, relativeTime, today } from '../../src/lib/format';

describe('format', () => {
	it('relative times', () => {
		const now = Date.parse('2026-11-18T12:00:00Z');
		expect(relativeTime('2026-11-18T11:59:30Z', now)).toBe('just now');
		expect(relativeTime('2026-11-18T11:55:00Z', now)).toBe('5 min ago');
		expect(relativeTime('2026-11-18T09:00:00Z', now)).toBe('3 hr ago');
		expect(relativeTime('2026-11-17T12:00:00Z', now)).toBe('1 day ago');
		expect(relativeTime(null, now)).toBe('never');
	});

	it('plurals and dates', () => {
		expect(plural(1, 'item')).toBe('1 item');
		expect(plural(34251, 'recall')).toBe('34,251 recalls');
		expect(today(new Date(2026, 0, 5))).toBe('2026-01-05');
	});
});
