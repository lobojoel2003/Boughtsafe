/** Small RFC 4180 CSV reader/writer: quoted fields, embedded commas, quotes and newlines. */

export function parseCsv(text: string, delimiter?: string): string[][] {
	const src = text.replace(/^\uFEFF/, '');
	const delim = delimiter ?? guessDelimiter(src);
	const rows: string[][] = [];
	let row: string[] = [];
	let field = '';
	let quoted = false;
	for (let i = 0; i < src.length; i++) {
		const c = src[i];
		if (quoted) {
			if (c === '"') {
				if (src[i + 1] === '"') {
					field += '"';
					i++;
				} else quoted = false;
			} else field += c;
		} else if (c === '"' && field === '') quoted = true;
		else if (c === delim) {
			row.push(field);
			field = '';
		} else if (c === '\n' || c === '\r') {
			if (c === '\r' && src[i + 1] === '\n') i++;
			row.push(field);
			rows.push(row);
			row = [];
			field = '';
		} else field += c;
	}
	if (field !== '' || row.length) {
		row.push(field);
		rows.push(row);
	}
	return rows.filter((r) => r.some((f) => f.trim() !== ''));
}

function guessDelimiter(text: string): string {
	const head = text.split(/\r?\n/, 1)[0] ?? '';
	const counts = [',', ';', '\t', '|'].map((d) => [d, head.split(d).length] as const);
	return counts.sort((a, b) => b[1] - a[1])[0][0];
}

export function toCsv(rows: (string | number | null | undefined)[][]): string {
	const esc = (v: string | number | null | undefined) => {
		const s = v === null || v === undefined ? '' : String(v);
		return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	};
	return rows.map((r) => r.map(esc).join(',')).join('\r\n') + '\r\n';
}
