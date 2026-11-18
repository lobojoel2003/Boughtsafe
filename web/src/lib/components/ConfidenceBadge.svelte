<script lang="ts">
	import type { Confidence, LotStatus } from '$lib/types';

	let { confidence, lotStatus }: { confidence: Confidence; lotStatus: LotStatus } = $props();

	const label = $derived(
		confidence === 'exact'
			? lotStatus === 'matched'
				? 'Exact match · UPC + lot'
				: 'Exact match · every lot'
			: confidence === 'upc'
				? 'UPC match · check the lot'
				: 'Possible match · name only'
	);
	const tone = $derived(confidence === 'exact' ? 'danger' : confidence === 'upc' ? 'warn' : 'info');
</script>

<span class="chip {tone}" data-confidence={confidence}>
	<span class="dot" aria-hidden="true"></span>{label}
</span>

<style>
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: currentColor;
	}
</style>
