<script lang="ts">
	import { ExternalLink, TriangleAlert } from '@lucide/svelte';
	import ConfidenceBadge from './ConfidenceBadge.svelte';
	import { formatDate } from '$lib/format';
	import { prettyCode } from '$lib/gtin';
	import { app, type Alert } from '$lib/state.svelte';

	let { alert, compact = false }: { alert: Alert; compact?: boolean } = $props();

	const item = $derived(alert.item);
	const m = $derived(alert.match);
	const r = $derived(m.recall);
	const severityLabel = $derived(
		r.classification
			? r.classification
			: r.severity === 'high'
				? 'Serious hazard'
				: r.severity === 'low'
					? 'Low risk'
					: 'Hazard'
	);
	const refundText = $derived(
		r.source !== 'cpsc' && item.store
			? `Take it back to ${item.store} for a full refund.`
			: r.refund.text || 'Return it to the store where you bought it for a full refund.'
	);

	const norm = (t: string) => t.toLowerCase().replace(/[^a-z0-9]/g, '');
	const showReason = $derived(!!r.reason && norm(r.reason) !== norm(r.hazard.label));

	let code = $state('');
	let checking = $state(false);

	async function checkCode(e: SubmitEvent) {
		e.preventDefault();
		if (!code.trim()) return;
		checking = true;
		await app.saveItem({ ...item, lot: code.trim() });
		checking = false;
		const still = app.alerts.some((a) => a.match.key === m.key);
		app.toast(
			still ? 'That code is on the recall.' : "Good news: your package isn't affected.",
			still ? 'danger' : 'ok'
		);
	}

	async function resolve() {
		await app.decide(m.key, 'resolved');
		app.toast('Marked as handled.');
	}
	async function dismiss() {
		await app.decide(m.key, 'dismissed');
		app.toast("Got it. We won't show this one again.");
	}
</script>

<article class="recall sev-{r.severity}" data-testid="recall-card" aria-labelledby="t-{m.key}">
	<header class="row wrap spread">
		<ConfidenceBadge confidence={m.confidence} lotStatus={m.lotStatus} />
		<span class="chip">{r.source_label} · {severityLabel}</span>
	</header>

	<div class="what">
		<h2 id="t-{m.key}">{item.name}</h2>
		<p class="muted small">
			{[item.brand, item.store ? `Bought at ${item.store}` : null, formatDate(item.purchasedAt)]
				.filter(Boolean)
				.join(' · ')}
		</p>
	</div>

	<div class="hazard">
		<span class="icon" aria-hidden="true"><TriangleAlert size={18} /></span>
		<div>
			<p class="label">{r.hazard.label}</p>
			{#if showReason}<p class="small muted">{r.reason}</p>{/if}
		</div>
	</div>

	{#if m.confidence === 'upc'}
		<form class="codecheck" onsubmit={checkCode}>
			<p class="small">
				<strong>Check the code on your package.</strong> This recall covers only some packages:
				<span class="mono">{r.codes}</span>
			</p>
			<div class="row">
				<input
					class="grow"
					placeholder="Lot or best-by code"
					aria-label="Lot or best-by code on your package"
					bind:value={code}
				/>
				<button class="btn" disabled={checking || !code.trim()}>Check</button>
			</div>
		</form>
	{:else if m.confidence === 'name'}
		<p class="note small">
			<strong>Matched by name only.</strong> Compare the brand, size and codes on your package with the
			notice before you throw anything away.
		</p>
	{/if}

	<section>
		<h3>What to do</h3>
		<p>{r.action}</p>
	</section>

	<section>
		<h3>Refund</h3>
		<p>{refundText}</p>
		{#if r.refund.contact}
			<p class="small muted contact">{r.refund.contact}</p>
		{/if}
	</section>

	{#if !compact}
		<details class="why small">
			<summary>Why this matched</summary>
			<ul>
				{#if m.matchedGtin}
					<li>Your barcode <span class="mono">{m.matchedGtin.display}</span> is on the notice.</li>
				{/if}
				{#if m.lotStatus === 'matched'}
					<li>Your code <span class="mono">{item.lot}</span> is listed.</li>
				{:else if m.lotStatus === 'all'}
					<li>The notice covers every lot and date.</li>
				{/if}
				{#if m.matchedTerms.length}
					<li>Name words in common: {m.matchedTerms.join(', ')} ({m.score}/100).</li>
				{/if}
				<li>
					Notice: {r.title}{#if r.recall_date}, {formatDate(r.recall_date)}{/if}.
				</li>
				{#if alert.related.length}
					<li>
						{alert.related.length} related notice{alert.related.length > 1 ? 's' : ''} also match.
					</li>
				{/if}
			</ul>
		</details>
	{/if}

	<footer class="row wrap actions no-print">
		<button class="btn primary" onclick={resolve}>I've dealt with it</button>
		<button class="btn" onclick={dismiss}>Not mine</button>
		<span class="grow"></span>
		{#if r.url}
			<a class="btn ghost" href={r.url} target="_blank" rel="noopener noreferrer">
				Official notice <ExternalLink size={15} />
			</a>
		{/if}
		<a class="btn ghost" href="/recall/{encodeURIComponent(r.id)}?item={item.id}">Details</a>
	</footer>
	{#if item.code}
		<p class="tiny faint">
			Your barcode: <span class="mono">{prettyCode(item.code, item.codeFormat)}</span>
		</p>
	{/if}
</article>

<style>
	.recall {
		--sev: var(--danger);
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		padding: 1.15rem 1.2rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		position: relative;
		overflow: hidden;
	}
	.recall::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 5px;
		background: var(--sev);
	}
	.sev-medium {
		--sev: var(--warn);
	}
	.sev-low {
		--sev: var(--faint);
	}
	.what h2 {
		font-size: 1.35rem;
	}
	.hazard {
		display: flex;
		gap: 0.7rem;
		align-items: flex-start;
		background: var(--danger-soft);
		border-radius: var(--radius-sm);
		padding: 0.75rem 0.85rem;
	}
	.sev-medium .hazard {
		background: var(--warn-soft);
	}
	.sev-low .hazard {
		background: var(--surface-2);
	}
	.hazard .icon {
		color: var(--sev);
		margin-top: 2px;
	}
	.hazard .label {
		font-weight: 700;
		color: var(--sev);
	}
	section h3 {
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--faint);
		margin-bottom: 0.2rem;
	}
	.codecheck {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		border: 1px dashed color-mix(in srgb, var(--warn) 50%, var(--line));
		border-radius: var(--radius-sm);
		padding: 0.75rem;
	}
	.codecheck .mono {
		word-break: break-word;
	}
	.note {
		background: var(--info-soft);
		color: var(--text);
		border-radius: var(--radius-sm);
		padding: 0.7rem 0.85rem;
	}
	.contact {
		margin-top: 0.3rem;
		word-break: break-word;
	}
	.why summary {
		cursor: pointer;
		color: var(--muted);
		font-weight: 600;
	}
	.why ul {
		margin: 0.5rem 0 0;
		padding-left: 1.1rem;
		color: var(--muted);
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.actions {
		--gap: 0.5rem;
		padding-top: 0.25rem;
	}
</style>
