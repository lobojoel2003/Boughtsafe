/**
 * GS1 element strings, as carried by GS1-128 case labels and GS1 DataMatrix codes:
 * one scan yields the GTIN, the lot and the expiry date. Useful at food pantries,
 * where donations often arrive by the case.
 */

export interface Gs1Data {
	gtin?: string;
	lot?: string;
	/** YYYY-MM-DD from AI 17 (expiry) or 15 (best before). */
	expiry?: string;
	serial?: string;
}

const GS = '\u001d';
// Fixed-length AIs we care about, plus how long their data is.
const FIXED: Record<string, number> = {
	'00': 18,
	'01': 14,
	'02': 14,
	'11': 6,
	'12': 6,
	'13': 6,
	'15': 6,
	'16': 6,
	'17': 6
};
const VARIABLE = new Set(['10', '21', '22', '240', '241', '30', '37']);

function yymmdd(s: string): string | undefined {
	if (!/^\d{6}$/.test(s)) return undefined;
	const y = 2000 + Number(s.slice(0, 2));
	const m = s.slice(2, 4);
	let d = s.slice(4, 6);
	if (d === '00') d = String(new Date(y, Number(m), 0).getDate()).padStart(2, '0');
	return `${y}-${m}-${d}`;
}

/** Parse "(01)00012345678905(10)ABC123" or raw "]C1010001234567890510ABC123<GS>17270131". */
export function parseGs1(raw: string): Gs1Data | null {
	let s = raw.trim();
	if (!s) return null;
	if (/^\(\d{2,4}\)/.test(s)) {
		const out: Gs1Data = {};
		for (const m of s.matchAll(/\((\d{2,4})\)([^(]*)/g)) assign(out, m[1], m[2]);
		return out.gtin || out.lot ? out : null;
	}
	s = s.replace(/^\][A-Za-z]\d/, ''); // symbology identifier, e.g. ]C1, ]d2, ]Q3
	if (!/^(01|02|10|17|15|21)/.test(s)) return null;
	const out: Gs1Data = {};
	let i = 0;
	while (i < s.length) {
		if (s[i] === GS) {
			i++;
			continue;
		}
		const ai2 = s.slice(i, i + 2);
		const ai3 = s.slice(i, i + 3);
		if (ai2 in FIXED) {
			const len = FIXED[ai2];
			assign(out, ai2, s.slice(i + 2, i + 2 + len));
			i += 2 + len;
		} else if (VARIABLE.has(ai3) || VARIABLE.has(ai2)) {
			const ai = VARIABLE.has(ai3) && !VARIABLE.has(ai2) ? ai3 : ai2;
			const start = i + ai.length;
			const end = s.indexOf(GS, start);
			const value = s.slice(start, end === -1 ? undefined : end).slice(0, 20);
			assign(out, ai, value);
			i = end === -1 ? s.length : end + 1;
		} else {
			break; // an AI we don't understand: stop rather than misread
		}
	}
	return out.gtin || out.lot ? out : null;
}

function assign(out: Gs1Data, ai: string, value: string) {
	if (ai === '01' || ai === '02') out.gtin = value;
	else if (ai === '10') out.lot = value;
	else if (ai === '17') out.expiry = yymmdd(value) ?? out.expiry;
	else if (ai === '15' && !out.expiry) out.expiry = yymmdd(value);
	else if (ai === '21') out.serial = value;
}
