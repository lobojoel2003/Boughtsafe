<script lang="ts">
	import { Keyboard, Receipt, ScanBarcode, Upload } from '@lucide/svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	const ways = [
		{
			href: '/add/scan',
			icon: ScanBarcode,
			title: 'Scan a barcode',
			text: 'Point your camera at the UPC. Add the lot code for an exact match.'
		},
		{
			href: '/add/receipt',
			icon: Receipt,
			title: 'Photograph a receipt',
			text: 'Reads every line on this device. Nothing is uploaded.'
		},
		{
			href: '/add/import',
			icon: Upload,
			title: 'Import a file',
			text: 'Store loyalty or order-history CSV, or a Boughtsafe backup.'
		},
		{
			href: '/add/manual',
			icon: Keyboard,
			title: 'Type it in',
			text: 'Name, barcode and lot code by hand.'
		}
	];
</script>

<svelte:head><title>Add · Boughtsafe</title></svelte:head>

<PageHeader title="Add what you bought" subtitle="Everything stays on this device." />

<div class="grid">
	{#each ways as w (w.href)}
		<a class="way card" href={w.href}>
			<span class="ico"><w.icon size={24} /></span>
			<strong>{w.title}</strong>
			<span class="small muted">{w.text}</span>
		</a>
	{/each}
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 0.75rem;
	}
	.way {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		text-decoration: none;
		color: inherit;
	}
	.way:hover {
		border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
	}
	.ico {
		width: 46px;
		height: 46px;
		border-radius: 13px;
		display: grid;
		place-items: center;
		background: var(--accent-soft);
		color: var(--accent);
		margin-bottom: 0.35rem;
	}
</style>
