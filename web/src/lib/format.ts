/** Local calendar date, YYYY-MM-DD. */
export function today(d = new Date()): string {
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${y}-${m}-${day}`;
}

export function formatDate(value: string | null | undefined): string {
	if (!value) return '';
	const [y, m, d] = value.slice(0, 10).split('-').map(Number);
	if (!y || !m || !d) return value;
	return new Date(y, m - 1, d).toLocaleDateString(undefined, {
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	});
}

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
	if (!iso) return 'never';
	const secs = Math.round((now - Date.parse(iso)) / 1000);
	if (secs < 45) return 'just now';
	const mins = Math.round(secs / 60);
	if (mins < 60) return `${mins} min ago`;
	const hours = Math.round(mins / 60);
	if (hours < 24) return `${hours} hr ago`;
	const days = Math.round(hours / 24);
	if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
	return formatDate(iso);
}

export function plural(n: number, one: string, many = `${one}s`): string {
	return `${n.toLocaleString()} ${n === 1 ? one : many}`;
}

export function download(filename: string, content: string, type: string): void {
	const url = URL.createObjectURL(new Blob([content], { type }));
	const a = Object.assign(document.createElement('a'), { href: url, download: filename });
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
