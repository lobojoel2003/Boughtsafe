<script lang="ts">
	import { app } from '$lib/state.svelte';
	import { fly } from 'svelte/transition';
</script>

<div class="toasts no-print" aria-live="polite">
	{#each app.toasts as t (t.id)}
		<div class="toast {t.tone}" transition:fly={{ y: 16, duration: 180 }}>{t.text}</div>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		inset: auto 0 calc(var(--nav-h) + 16px + env(safe-area-inset-bottom)) 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		pointer-events: none;
		z-index: 60;
		padding: 0 1rem;
	}
	.toast {
		max-width: 30rem;
		background: var(--text);
		color: var(--bg);
		padding: 0.7rem 1rem;
		border-radius: 14px;
		font-size: 0.92rem;
		font-weight: 550;
		box-shadow: var(--shadow);
	}
	.toast.danger {
		background: var(--danger);
		color: #fff;
	}
</style>
