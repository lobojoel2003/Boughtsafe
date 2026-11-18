<script lang="ts">
	import { ArrowLeft } from '@lucide/svelte';
	import type { Snippet } from 'svelte';

	let {
		title,
		subtitle,
		back,
		actions
	}: { title: string; subtitle?: string; back?: string; actions?: Snippet } = $props();
</script>

<header class="ph">
	{#if back}
		<a class="btn ghost back no-print" href={back} aria-label="Back"><ArrowLeft size={20} /></a>
	{/if}
	<div class="grow">
		<h1>{title}</h1>
		{#if subtitle}<p class="muted">{subtitle}</p>{/if}
	</div>
	{#if actions}<div class="row no-print">{@render actions()}</div>{/if}
</header>

<style>
	.ph {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 1.25rem 0 1rem;
	}
	.back {
		margin-left: -0.6rem;
		margin-top: -0.1rem;
	}
	p {
		margin-top: 0.35rem;
	}
</style>
