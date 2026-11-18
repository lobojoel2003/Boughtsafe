/**
 * Turn the text Tesseract reads off a receipt into purchase lines.
 * Receipts are messy, so the result is always shown for review before saving.
 */

export interface ReceiptLine {
	raw: string;
	name: string;
	code?: string;
	price?: number;
}

export interface ParsedReceipt {
	store?: string;
	date?: string;
	lines: ReceiptLine[];
}

const STORES = [
	'Walmart',
	'Target',
	'Kroger',
	'Costco',
	"Sam's Club",
	'Safeway',
	"Trader Joe's",
	'Whole Foods',
	'Aldi',
	'Lidl',
	'Publix',
	'H-E-B',
	'Meijer',
	'Albertsons',
	'Wegmans',
	'Food Lion',
	'Giant',
	'Stop & Shop',
	'Sprouts',
	'WinCo',
	'Hy-Vee',
	'ShopRite',
	'Harris Teeter',
	'Ralphs',
	"Fry's",
	'King Soopers',
	'Vons',
	'Jewel-Osco',
	"Smith's",
	'Winn-Dixie',
	'Piggly Wiggly',
	'Food 4 Less',
	'Dollar General',
	'Family Dollar',
	'CVS',
	'Walgreens',
	'Rite Aid',
	"BJ's",
	'Market Basket',
	'Hannaford',
	'Price Chopper',
	"Raley's",
	'Save A Lot',
	'Grocery Outlet',
	'Natural Grocers',
	'Fresh Market',
	'Stater Bros',
	'Weis',
	'Ingles',
	'Dillons',
	"Mariano's",
	'Amazon Fresh'
];

/** Common shelf-tag abbreviations, expanded so names match recall notices. */
export const ABBREVIATIONS: Record<string, string> = {
	GV: 'Great Value',
	KS: 'Kirkland Signature',
	KRKLND: 'Kirkland',
	TJ: "Trader Joe's",
	TJS: "Trader Joe's",
	MM: "Member's Mark",
	ORG: 'Organic',
	ORGN: 'Organic',
	NAT: 'Natural',
	WHL: 'Whole',
	MLK: 'Milk',
	CHS: 'Cheese',
	CHSE: 'Cheese',
	CHED: 'Cheddar',
	MOZZ: 'Mozzarella',
	SHRD: 'Shredded',
	CHKN: 'Chicken',
	CHIC: 'Chicken',
	BRST: 'Breast',
	BNLS: 'Boneless',
	SKNLS: 'Skinless',
	GRD: 'Ground',
	BF: 'Beef',
	TRKY: 'Turkey',
	TKY: 'Turkey',
	SAUS: 'Sausage',
	BCN: 'Bacon',
	SLCD: 'Sliced',
	SMKD: 'Smoked',
	RSTD: 'Roasted',
	YGRT: 'Yogurt',
	YOG: 'Yogurt',
	BRD: 'Bread',
	SPNCH: 'Spinach',
	LETT: 'Lettuce',
	TOM: 'Tomato',
	TOMS: 'Tomatoes',
	POT: 'Potato',
	BNNA: 'Banana',
	BAN: 'Banana',
	STRWB: 'Strawberry',
	STRAWB: 'Strawberries',
	BLUEB: 'Blueberries',
	PNT: 'Peanut',
	PNUT: 'Peanut',
	BTR: 'Butter',
	BUTR: 'Butter',
	CRM: 'Cream',
	CRMR: 'Creamer',
	CHOC: 'Chocolate',
	VAN: 'Vanilla',
	FRZ: 'Frozen',
	FRZN: 'Frozen',
	VEG: 'Vegetable',
	VEGS: 'Vegetables',
	SDLS: 'Seedless',
	GRP: 'Grape',
	PB: 'Peanut Butter',
	OJ: 'Orange Juice',
	LG: 'Large',
	SM: 'Small',
	MED: 'Medium',
	DZ: 'Dozen',
	CKY: 'Cookies',
	CKIES: 'Cookies',
	CRKR: 'Crackers',
	CRL: 'Cereal',
	SWT: 'Sweet',
	SPCY: 'Spicy',
	SNK: 'Snack',
	JCE: 'Juice',
	WTR: 'Water',
	SPRK: 'Sparkling',
	CHPS: 'Chips',
	TORT: 'Tortilla',
	SLSA: 'Salsa',
	HUMM: 'Hummus',
	AVO: 'Avocado',
	ONI: 'Onion',
	CUC: 'Cucumber',
	CUKE: 'Cucumber',
	SPRT: 'Sprouts',
	ALM: 'Almond',
	ALMD: 'Almond',
	WLNT: 'Walnut',
	RSN: 'Raisin',
	HNY: 'Honey',
	GF: 'Gluten Free',
	RTE: 'Ready to Eat',
	ICECRM: 'Ice Cream',
	IC: 'Ice Cream',
	PZZ: 'Pizza',
	PIZ: 'Pizza',
	GRNOLA: 'Granola',
	BKD: 'Baked',
	FRSH: 'Fresh'
};

const SKIP = new RegExp(
	[
		'SUB\\s*-?\\s*TOTAL',
		'\\bTOTAL\\b',
		'\\bTAX\\b',
		'BALANCE',
		'CHANGE\\s*(?:DUE)?',
		'\\bCASH\\b',
		'\\bVISA\\b',
		'MASTER\\s*CARD',
		'\\bDEBIT\\b',
		'\\bCREDIT\\b',
		'\\bAMEX\\b',
		'DISCOVER',
		'\\bAUTH',
		'APPROV',
		'THANK',
		'SAVINGS',
		'YOU SAVED',
		'COUPON',
		'DISCOUNT',
		'\\bMEMBER',
		'REWARD',
		'POINTS',
		'\\bTEL\\b',
		'PHONE',
		'STORE\\s*#',
		'\\bST#',
		'\\bTC#',
		'\\bTR#',
		'CASHIER',
		'REGISTER',
		'ITEMS? SOLD',
		'ACCOUNT',
		'\\bCARD\\b',
		'\\bCHIP\\b',
		'\\bPIN\\b',
		'\\bREF\\b',
		'TERMINAL',
		'WWW\\.',
		'\\.COM\\b',
		'RETURN',
		'POLICY',
		'SURVEY',
		'DEPOSIT',
		'BAG FEE',
		'\\bCRV\\b',
		'RECEIPT',
		'TRANS',
		'SIGNATURE REQ',
		'OPEN \\d',
		'MANAGER',
		'TIP\\b',
		'\\bPAID\\b',
		'\\bDUE\\b'
	].join('|'),
	'i'
);

const PRICE_END = /(-?\$?\s?\d{1,4}[.,]\d{2})\s*(?:[A-Z]{1,2}|\*)?\s*$/;
const QTY = /\b\d+\s*@\s*\$?\d+[.,]\d{2}\b|\b\d+(?:\.\d+)?\s*(?:LB|LBS|KG)\s*@.*$/i;
const CODE = /(?<!\d)(\d{11,14})(?!\d)/;
const DATE = /(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?!\d)/;

function titleCase(s: string): string {
	return s
		.toLowerCase()
		.replace(/\b([a-z])([a-z']*)/g, (_, a: string, b: string) => a.toUpperCase() + b)
		.replace(/\b(Of|And|With|In|The)\b/g, (w) => w.toLowerCase())
		.replace(/^./, (c) => c.toUpperCase());
}

export function expandAbbreviations(name: string): string {
	return name
		.split(/\s+/)
		.map((w) => ABBREVIATIONS[w.toUpperCase().replace(/[^A-Z]/g, '')] ?? w)
		.join(' ');
}

export function cleanName(raw: string): string {
	let s = raw.replace(QTY, ' ');
	s = s.replace(PRICE_END, ' ');
	s = s.replace(CODE, ' ');
	s = s.replace(/^\s*\d{1,6}\s+(?=[A-Za-z])/, ''); // leading item / PLU number
	s = s
		.replace(/[^A-Za-z0-9&'%\-. ]+/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
	s = s.replace(/(?:\s+\b[A-Z]{1,2}\b)+$/, ''); // trailing tax flags such as "F", "N", "KF"
	const expanded = expandAbbreviations(s);
	// Receipts print in capitals; keep names someone typed in mixed case as they are.
	return /[a-z]/.test(s) ? expanded : titleCase(expanded);
}

function detectStore(lines: string[]): string | undefined {
	const head = lines.slice(0, 10).join(' \n ').toLowerCase().replace(/[’`]/g, "'");
	for (const store of STORES) {
		const pattern = store
			.toLowerCase()
			.replace(/[-\s']/g, "[-\\s']?")
			.replace(/&/g, '&');
		if (new RegExp(`(^|[^a-z])${pattern}([^a-z]|$)`).test(head)) return store;
	}
	return undefined;
}

function detectDate(text: string): string | undefined {
	const m = text.match(DATE);
	if (!m) return undefined;
	const [, mm, dd, y] = m;
	const yy = y.length === 2 ? `20${y}` : y;
	const month = Number(mm);
	const day = Number(dd);
	if (month < 1 || month > 12 || day < 1 || day > 31) return undefined;
	return `${yy}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`;
}

export function parseReceipt(text: string): ParsedReceipt {
	const rawLines = text
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter(Boolean);
	const store = detectStore(rawLines);
	const date = detectDate(text);
	const priced = rawLines.filter((l) => PRICE_END.test(l));
	const candidates = priced.length >= 2 ? priced : rawLines;
	const lines: ReceiptLine[] = [];
	for (const raw of candidates) {
		if (SKIP.test(raw)) continue;
		if (store && raw.toLowerCase().includes(store.toLowerCase()) && !PRICE_END.test(raw)) continue;
		const letters = raw.replace(/[^A-Za-z]/g, '');
		if (letters.length < 3) continue;
		const price = raw.match(PRICE_END)?.[1];
		if (price && price.trim().startsWith('-')) continue; // discounts
		const code = raw.match(CODE)?.[1];
		const name = cleanName(raw);
		if (name.replace(/[^A-Za-z]/g, '').length < 3) continue;
		lines.push({
			raw,
			name,
			code,
			price: price ? Number(price.replace(/[$\s]/g, '').replace(',', '.')) : undefined
		});
	}
	return { store, date, lines };
}
