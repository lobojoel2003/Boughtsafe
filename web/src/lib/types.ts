/** Shapes shared by the app, the service worker and the API. */

export type ListKind = 'home' | 'pantry';
export type ItemSource = 'scan' | 'receipt' | 'import' | 'manual';
export type Confidence = 'exact' | 'upc' | 'name';
export type LotStatus = 'matched' | 'all' | 'unknown';
export type MatchState = 'active' | 'resolved' | 'dismissed';

/** Something you own. Lives only in IndexedDB on this device. */
export interface Item {
	id: string;
	list: ListKind;
	name: string;
	brand?: string;
	/** Barcode digits as scanned or typed. */
	code?: string;
	/** Scanner symbology (upc_a, ean_13, upc_e, ...). */
	codeFormat?: string;
	/** Code copied off a receipt: ask the server to repair dropped check digits. */
	lenient?: boolean;
	/** Lot code or best-by date printed on the package. */
	lot?: string;
	quantity?: number;
	store?: string;
	/** YYYY-MM-DD */
	purchasedAt: string;
	/** ISO timestamp */
	addedAt: string;
	source: ItemSource;
	imageUrl?: string;
	donor?: string;
	note?: string;
}

export interface Gtin {
	gtin: string;
	display: string;
}

export interface Hazard {
	kind: 'pathogen' | 'allergen' | 'foreign' | 'chemical' | 'injury' | 'labeling' | 'other';
	label: string;
	allergens: string[];
}

export interface Recall {
	id: string;
	source: 'fda' | 'fsis' | 'cpsc';
	source_label: string;
	title: string;
	product: string;
	firm: string | null;
	reason: string;
	hazard: Hazard;
	classification: string | null;
	severity: 'high' | 'medium' | 'low';
	status: 'ongoing' | 'closed';
	codes: string;
	covers_all_codes: boolean;
	distribution: string | null;
	action: string;
	refund: { options: string[]; text: string; contact: string | null };
	url: string | null;
	image_url: string | null;
	recall_date: string | null;
	published_date: string | null;
	gtins: Gtin[];
}

export interface ApiMatch {
	item_id: string;
	confidence: Confidence;
	lot_status: LotStatus;
	score: number;
	matched_gtin: Gtin | null;
	matched_terms: string[];
	recall: Recall;
}

export interface RuledOut {
	item_id: string;
	recall_id: string;
	reason: 'lot_not_listed' | 'too_old';
	title: string;
}

export interface MatchResponse {
	matches: ApiMatch[];
	ruled_out: RuledOut[];
	catalog: { version: string; total: number; checked_at: string };
}

/** A match remembered on this device, with what you decided to do about it. */
export interface StoredMatch {
	key: string;
	itemId: string;
	recallId: string;
	confidence: Confidence;
	lotStatus: LotStatus;
	score: number;
	matchedGtin: Gtin | null;
	matchedTerms: string[];
	recall: Recall;
	firstSeenAt: string;
	state: MatchState;
	decidedAt?: string;
}

export interface StoredRuledOut extends RuledOut {
	key: string;
}

export interface SourceStatus {
	source: string;
	label: string;
	count: number;
	last_sync: string | null;
	last_ok: boolean | null;
	last_error: string | null;
}

export interface Meta {
	name: string;
	version: string;
	build: string;
	commit: string;
	catalog_version: string;
	sources: SourceStatus[];
	push_enabled: boolean;
	vapid_public_key: string | null;
}

export interface Product {
	gtin: string;
	display: string;
	found: boolean;
	name: string | null;
	brand: string | null;
	quantity: string | null;
	image_url: string | null;
	source: string | null;
}

export interface CheckSummary {
	checkedAt: string;
	items: number;
	catalogTotal: number;
	catalogVersion: string;
	newMatches: StoredMatch[];
}
