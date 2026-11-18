<script lang="ts">
	import { Download, FileUp, Printer, RefreshCw, ScanBarcode, Trash2 } from '@lucide/svelte';
	import ItemRow from '$lib/components/ItemRow.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Scanner from '$lib/components/Scanner.svelte';
	import { api } from '$lib/api';
	import { toCsv } from '$lib/csv';
	import { newId } from '$lib/db';
	import { download, plural, relativeTime, today } from '$lib/format';
	import { prettyCode, toGtin14 } from '$lib/gtin';
	import type { ScanResult } from '$lib/scanner';
	import { app } from '$lib/state.svelte';
	import type { Item } from '$lib/types';

	const stock = $derived(app.items.filter((i) => i.list === 'pantry'));
	const units = $derived(stock.reduce((n, i) => n + (i.quantity ?? 1), 0));
	const pull = $derived(app.alerts.filter((a) => a.item.list === 'pantry'));

	let receiving = $state(false);
	let session = $state<Item[]>([]);
	let donor = $state('');
	let saving = $state(false);

	async function onscan(r: ScanResult) {
		const g = toGtin14(r.code, r.format);
		const lot = r.lot ?? (r.expiry ? `EXP ${r.expiry}` : undefined);
		const same = session.find(
			(s) => toGtin14(s.code, s.codeFormat) === g && (s.lot ?? '') === (lot ?? '')
		);
		if (same) {
			same.quantity = (same.quantity ?? 1) + 1;
			return;
		}
		const line: Item = {
			id: newId(),
			list: 'pantry',
			name: `Barcode ${prettyCode(r.code, r.format)}`,
			code: r.code,
			codeFormat: r.format,
			lot,
			quantity: 1,
			purchasedAt: today(),
			addedAt: new Date().toISOString(),
			source: 'scan'
		};
		session = [line, ...session];
		try {
			const p = await api.product(r.code, r.format);
			const target = session.find((s) => s.id === line.id);
			if (target && p.found) {
				target.name = [p.name, p.quantity].filter(Boolean).join(' ');
				target.brand = p.brand ?? undefined;
			}
		} catch {
			/* offline: keep the barcode as the name */
		}
	}

	async function finish() {
		saving = true;
		const items = $state.snapshot(session).map((s) => ({ ...s, donor: donor || undefined }));
		const found = await app.addItems(items);
		saving = false;
		receiving = false;
		session = [];
		app.toast(
			found.length
				? `${plural(found.length, 'item')} must be pulled from the shelves.`
				: `Received ${plural(items.length, 'line')}. Nothing is recalled.`,
			found.length ? 'danger' : 'ok'
		);
	}

	function exportPull() {
		const rows = [
			[
				'product',
				'brand',
				'upc',
				'lot',
				'quantity',
				'received',
				'donor',
				'hazard',
				'match',
				'recall',
				'notice'
			],
			...pull.map(({ item, match }) => [
				item.name,
				item.brand,
				item.code,
				item.lot,
				item.quantity ?? 1,
				item.purchasedAt,
				item.donor,
				match.recall.hazard.label,
				match.confidence,
				match.recall.title,
				match.recall.url
			])
		];
		download(`boughtsafe-pull-list-${today()}.csv`, toCsv(rows), 'text/csv');
	}

	function exportStock() {
		const rows = [
			['product', 'brand', 'upc', 'lot', 'quantity', 'received', 'donor'],
			...stock.map((i) => [i.name, i.brand, i.code, i.lot, i.quantity ?? 1, i.purchasedAt, i.donor])
		];
		download(`boughtsafe-pantry-${today()}.csv`, toCsv(rows), 'text/csv');
	}
</script>

<svelte:head><title>Pantry · Boughtsafe</title></svelte:head>

<PageHeader
	title="Pantry mode"
	subtitle="Check donated stock by UPC and lot code before it goes out the door."
/>

<div class="stack">
	<div class="stats card row wrap">
		<div>
			<strong>{stock.length.toLocaleString()}</strong><span class="small muted">products</span>
		</div>
		<div><strong>{units.toLocaleString()}</strong><span class="small muted">units</span></div>
		<div>
			<strong class:bad={pull.length}>{pull.length}</strong><span class="small muted">to pull</span>
		</div>
		<div class="grow small faint last">Checked {relativeTime(app.last?.checkedAt)}</div>
	</div>

	<div class="row wrap actions no-print">
		<button class="btn primary" onclick={() => (receiving = !receiving)} aria-pressed={receiving}>
			<ScanBarcode size={18} />
			{receiving ? 'Close scanner' : 'Receive stock'}
		</button>
		<a class="btn" href="/add/import?list=pantry"><FileUp size={18} /> Import inventory</a>
		<button class="btn" onclick={() => app.check()} disabled={app.checking || !stock.length}>
			<RefreshCw size={18} />
			{app.checking ? 'Checking…' : 'Check all stock'}
		</button>
	</div>

	{#if receiving}
		<section class="card stack receive">
			<h2>Receive stock</h2>
			<p class="small muted">
				Scan each product. Case labels with GS1 barcodes fill in the lot and expiry for you.
				Scanning the same product and lot again adds to its count.
			</p>
			<Scanner {onscan} continuous />
			<label class="field"
				>Donor for this batch <input bind:value={donor} placeholder="Optional" /></label
			>
			{#if session.length}
				<div class="panel lines">
					{#each session as line (line.id)}
						<div class="line">
							<div class="grow">
								<input class="name" bind:value={line.name} aria-label="Product name" />
								<p class="tiny faint mono">{prettyCode(line.code, line.codeFormat)}</p>
							</div>
							<input
								class="lot"
								bind:value={line.lot}
								placeholder="Lot / best by"
								aria-label="Lot code"
							/>
							<input
								class="qty"
								type="number"
								min="1"
								bind:value={line.quantity}
								aria-label="Quantity"
							/>
							<button
								class="btn ghost"
								aria-label="Remove"
								onclick={() => (session = session.filter((s) => s.id !== line.id))}
							>
								<Trash2 size={16} />
							</button>
						</div>
					{/each}
				</div>
				<button class="btn primary lg" onclick={finish} disabled={saving}>
					{saving ? 'Checking…' : `Save and check ${plural(session.length, 'line')}`}
				</button>
			{/if}
		</section>
	{/if}

	{#if pull.length}
		<section class="stack pull" aria-labelledby="pull-title">
			<div class="row spread wrap">
				<h2 id="pull-title">Pull from shelves</h2>
				<div class="row no-print">
					<button class="btn" onclick={exportPull}><Download size={16} /> CSV</button>
					<button class="btn" onclick={() => print()}><Printer size={16} /> Print</button>
				</div>
			</div>
			<ul class="panel pulls" data-testid="pull-list">
				{#each pull as { item, match } (match.key)}
					<li class="pullrow">
						<div class="grow">
							<a class="pname" href="/items/{item.id}">{item.name}</a>
							<p class="small muted">
								{match.recall.hazard.label} · Lot <span class="mono">{item.lot ?? '—'}</span> · Qty
								{item.quantity ?? 1}{item.donor ? ` · ${item.donor}` : ''}
							</p>
							<p class="tiny faint mono">{prettyCode(item.code, item.codeFormat)}</p>
						</div>
						<span
							class="chip {match.confidence === 'exact'
								? 'danger'
								: match.confidence === 'upc'
									? 'warn'
									: 'info'}"
						>
							{match.confidence === 'exact'
								? 'UPC + lot'
								: match.confidence === 'upc'
									? 'UPC only'
									: 'Name only'}
						</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section class="stack">
		<div class="row spread">
			<h2>Stock on hand</h2>
			{#if stock.length}<button class="btn ghost small no-print" onclick={exportStock}
					><Download size={16} /> Export</button
				>{/if}
		</div>
		{#if stock.length}
			<div class="panel list">
				{#each stock as item (item.id)}
					<ItemRow {item} flagged={pull.some((p) => p.item.id === item.id)} />
				{/each}
			</div>
		{:else}
			<p class="muted card">
				No pantry stock yet. Receive a delivery with the scanner, or import your inventory
				spreadsheet.
			</p>
		{/if}
	</section>
</div>

<style>
	.stats {
		--gap: 1.75rem;
	}
	.stats > div:not(.last) {
		display: flex;
		flex-direction: column;
	}
	.stats strong {
		font-size: 1.6rem;
		line-height: 1.1;
	}
	.stats .bad {
		color: var(--danger);
	}
	.last {
		text-align: right;
	}
	.actions {
		--gap: 0.5rem;
	}
	.lines {
		overflow: hidden;
	}
	.line {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.6rem;
		border-top: 1px solid var(--line);
	}
	.line:first-child {
		border-top: 0;
	}
	.line .name {
		border-color: transparent;
		padding: 0.3rem 0.4rem;
		min-height: 36px;
	}
	.line .lot {
		width: 9rem;
	}
	.line .qty {
		width: 4.5rem;
	}
	.pull h2 {
		color: var(--danger);
	}
	.list {
		overflow: hidden;
	}
	.pulls {
		list-style: none;
		margin: 0;
		padding: 0;
		overflow: hidden;
	}
	.pullrow {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.8rem 1rem;
		border-top: 1px solid var(--line);
	}
	.pullrow:first-child {
		border-top: 0;
	}
	.pname {
		font-weight: 650;
		color: var(--text);
		text-decoration: none;
	}
	.pname:hover {
		text-decoration: underline;
	}
</style>
