<script lang="ts">
	import { Boxes, Receipt, ScanBarcode, Upload, LockKeyhole } from '@lucide/svelte';
	import AllClear from '$lib/components/AllClear.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import RecallCard from '$lib/components/RecallCard.svelte';
	import { relativeTime } from '$lib/format';
	import { app } from '$lib/state.svelte';
</script>

<svelte:head><title>Boughtsafe</title></svelte:head>

{#if !app.loaded}
	<div class="loading" aria-busy="true"></div>
{:else if app.items.length === 0}
	<section class="welcome stack" data-testid="welcome">
		<Logo size={56} />
		<h1>Know when something in your kitchen is recalled.</h1>
		<p class="lead muted">
			Boughtsafe checks what you buy against every FDA, USDA and CPSC recall, then stays silent
			until one matches something you own.
		</p>
		<div class="ways stack">
			<a class="way" href="/add/scan">
				<span class="ico"><ScanBarcode size={22} /></span>
				<span
					><strong>Scan a barcode</strong><span class="small muted"
						>Most exact, especially with the lot code</span
					></span
				>
			</a>
			<a class="way" href="/add/receipt">
				<span class="ico"><Receipt size={22} /></span>
				<span
					><strong>Photograph a receipt</strong><span class="small muted"
						>Read on this device, never uploaded</span
					></span
				>
			</a>
			<a class="way" href="/add/import">
				<span class="ico"><Upload size={22} /></span>
				<span
					><strong>Import a store export</strong><span class="small muted"
						>Loyalty or order-history CSV</span
					></span
				>
			</a>
		</div>
		<p class="private small muted">
			<LockKeyhole size={15} /> Your purchases are stored on this device only.
		</p>
		<a class="pantry small" href="/pantry"
			><Boxes size={16} /> Run a food pantry? Check donated stock by UPC and lot.</a
		>
	</section>
{:else if app.alerts.length}
	<section class="alerts stack" aria-labelledby="alerts-title">
		<div class="intro">
			<h1 id="alerts-title">
				{app.alerts.length === 1
					? 'Something you own has been recalled.'
					: `${app.alerts.length} things you own have been recalled.`}
			</h1>
			<p class="muted">Here's what to do and how to get your money back.</p>
		</div>
		{#each app.alerts as alert (alert.match.key)}
			<RecallCard {alert} />
		{/each}
		<p class="faint small center">
			Last checked {relativeTime(app.last?.checkedAt)} ·
			<button class="link" onclick={() => app.check()} disabled={app.checking}>
				{app.checking ? 'checking…' : 'check again'}
			</button>
		</p>
	</section>
{:else}
	<AllClear />
{/if}

<style>
	.loading {
		min-height: 60vh;
	}
	.welcome {
		--gap: 1.1rem;
		padding-top: 2rem;
	}
	.welcome h1 {
		max-width: 20ch;
	}
	.lead {
		font-size: 1.05rem;
		max-width: 38ch;
	}
	.ways {
		--gap: 0.6rem;
		margin-top: 0.5rem;
	}
	.way {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		padding: 0.95rem 1rem;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: inherit;
		text-decoration: none;
		box-shadow: var(--shadow);
	}
	.way:hover {
		border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
	}
	.way > span:last-child {
		display: flex;
		flex-direction: column;
	}
	.ico {
		width: 44px;
		height: 44px;
		flex: none;
		border-radius: 12px;
		display: grid;
		place-items: center;
		background: var(--accent-soft);
		color: var(--accent);
	}
	.private,
	.pantry {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.alerts {
		padding-top: 1.25rem;
	}
	.intro h1 {
		color: var(--danger);
		font-size: 1.5rem;
		max-width: 22ch;
	}
	.intro p {
		margin-top: 0.4rem;
	}
	.center {
		text-align: center;
	}
	.link {
		background: none;
		border: 0;
		padding: 0;
		color: var(--accent);
		font: inherit;
		cursor: pointer;
		text-decoration: underline;
		text-underline-offset: 3px;
	}
</style>
