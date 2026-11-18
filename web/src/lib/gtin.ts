/**
 * Barcode helpers for the device. The server is the authority on matching; these
 * keep the UI tidy (dedupe, display) and compute watch buckets for push alerts.
 * Mirrors server/boughtsafe/gtin.py.
 */

export function digitsOnly(raw: string | null | undefined): string {
	return (raw ?? '').replace(/\D/g, '');
}

export function checkDigit(body: string): number {
	let total = 0;
	for (let i = 0; i < body.length; i++) {
		const n = body.charCodeAt(body.length - 1 - i) - 48;
		total += n * (i % 2 === 0 ? 3 : 1);
	}
	return (10 - (total % 10)) % 10;
}

export function isValid(digits: string): boolean {
	return (
		[8, 12, 13, 14].includes(digits.length) &&
		/^\d+$/.test(digits) &&
		checkDigit(digits.slice(0, -1)) === digits.charCodeAt(digits.length - 1) - 48
	);
}

export function upceToUpca(code: string): string | null {
	if (!/^[01]\d{7}$/.test(code)) return null;
	const ns = code[0];
	const d = code.slice(1, 7);
	const check = code[7];
	const last = d[5];
	let body: string;
	if ('012'.includes(last)) body = d.slice(0, 2) + last + '0000' + d.slice(2, 5);
	else if (last === '3') body = d.slice(0, 3) + '00000' + d.slice(3, 5);
	else if (last === '4') body = d.slice(0, 4) + '00000' + d[4];
	else body = d.slice(0, 5) + '0000' + last;
	const upca = ns + body + check;
	return isValid(upca) ? upca : null;
}

/** Strict normalization to GTIN-14, or null. */
export function toGtin14(raw: string | null | undefined, format?: string): string | null {
	const d = digitsOnly(raw);
	if (d.length === 8) {
		const upca = format === 'ean_8' ? null : upceToUpca(d);
		if (upca) return upca.padStart(14, '0');
		return format !== 'upc_e' && isValid(d) ? d.padStart(14, '0') : null;
	}
	if ([12, 13, 14].includes(d.length) && isValid(d)) return d.padStart(14, '0');
	return null;
}

/** "0 70552 00649 2" for UPC-A, "4 056489 722458" for EAN-13. */
export function display(gtin14: string): string {
	if (gtin14.startsWith('00')) {
		const u = gtin14.slice(2);
		return `${u[0]} ${u.slice(1, 6)} ${u.slice(6, 11)} ${u[11]}`;
	}
	if (gtin14.startsWith('0')) {
		const e = gtin14.slice(1);
		return `${e[0]} ${e.slice(1, 7)} ${e.slice(7, 13)}`;
	}
	return gtin14;
}

/** Format whatever the person typed; falls back to the raw digits. */
export function prettyCode(raw: string | undefined, format?: string): string {
	if (!raw) return '';
	const g = toGtin14(raw, format);
	return g ? display(g) : digitsOnly(raw) || raw;
}
