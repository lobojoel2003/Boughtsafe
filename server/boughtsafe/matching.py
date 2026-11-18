"""Match purchases against the recall catalog.

Three confidence levels, from most to least certain:

``exact``
    The barcode matches and either the package code (lot, best-by date) is
    listed in the notice or the notice covers every code.
``upc``
    The barcode matches, but we don't know the package code and the notice only
    covers some codes. The card asks the person to check the package.
``name``
    No barcode on one side; the product name and brand match closely. Used for
    receipt lines and notices that print no UPC.

The matcher is tuned for silence: a match is only reported when it would be
worth interrupting someone for. Barcode matches whose package code is *not* in
the notice are reported separately as ``ruled_out`` so the client can explain
them on the item page without raising an alert.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache

from rapidfuzz import fuzz, process
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import codes, gtin
from .config import Settings
from .db import Recall, RecallGtin, aware

log = logging.getLogger(__name__)

CONFIDENCE_ORDER = {"exact": 0, "upc": 1, "name": 2}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
NAME_MATCHES_PER_ITEM = 3

STOPWORDS = frozenset(
    """
    a an and or the of in on with for to by from at as is are be this that these those it
    its new our your all each per plus only no not non free oz fl floz lb lbs g gr kg mg ml
    l ltr liter litre qt pt gal ct count pk pack packs pc pcs piece pieces net wt weight
    size sizes bag bags box boxes bottle bottles can cans jar jars carton cartons tray trays
    case cases container containers package packages packaged packed pouch pouches tub tubs
    unit units retail label labels labeled each ea value recall recalls recalled recalling
    due possible potential potentially contamination contaminated product products company
    inc llc ltd co corp corporation foods food brand brands distributed distributor
    distribution manufactured manufacturer undeclared allergen allergens risk hazard hazards
    serious injury injuries death because sold reads part front back side white clear
    plastic printed approximately usda est establishment number lot code best by use sell
    date dates upc item items various assorted
    """.split()
)

_WORD = re.compile(r"[a-z0-9]+")


def _stem(w: str) -> str:
    """Tiny plural/-y stemmer: berries/berry -> berri, cookies/cookie -> cooki."""
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "i"
    elif len(w) > 4 and w.endswith(("ches", "shes", "xes", "sses")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 3 and w.endswith(("y", "ie")):
        w = w[:-2] + "i" if w.endswith("ie") else w[:-1] + "i"
    return w


# Words so common on grocery shelves that, on their own, they say nothing about
# which product you bought. They still count toward coverage, with a low weight.
GENERIC = frozenset(
    """
    organic natural fresh frozen raw cooked whole sliced diced chopped shredded ground mini
    original classic regular light lite large small medium family style premium select
    choice chicken beef pork turkey ham bacon sausage meat fish salmon tuna shrimp egg eggs
    milk cheese cheddar mozzarella cream butter yogurt ice dairy bread bun roll tortilla
    cracker cookie cake pie chip snack bar cereal granola pasta noodle rice bean soup sauce
    salsa dip dressing oil spice seasoning mix powder flour sugar salt fruit apple banana
    berry strawberry blueberry orange lemon peach mango grape cherry vegetable salad lettuce
    spinach onion pepper tomato potato carrot corn pea broccoli sprout mushroom nut peanut
    almond walnut cashew seed chocolate candy vanilla juice water drink tea coffee soda
    smoothie supplement capsule tablet sweet spicy hot mild sharp honey maple smoked roasted
    grilled baked fried red green yellow black blue brown dark toy toys kid kids children
    baby infant set kit
    """.split()
)
GENERIC = GENERIC | frozenset(_stem(w) for w in GENERIC)


@lru_cache(maxsize=65536)
def _clean_word(w: str) -> str | None:
    if len(w) < 2 or w in STOPWORDS or any(c.isdigit() for c in w):
        return None
    s = _stem(w)
    return None if s in STOPWORDS else s


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub("['\u2019`]", "", text)
    out: list[str] = []
    for w in _WORD.findall(text):
        c = _clean_word(w)
        if c and c not in out:
            out.append(c)
    return out


# --- data types -------------------------------------------------------------------------


@dataclass(slots=True)
class Entry:
    id: str
    source: str
    gtins: frozenset[str]
    tokens: frozenset[str]
    text: str
    codes_text: str
    covers_all: bool
    has_codes: bool
    recall_date: date | None
    severity: str
    updated_at: datetime | None
    _codes: codes.NoticeCodes | None = None

    def notice_codes(self) -> codes.NoticeCodes:
        if self._codes is None:
            self._codes = codes.parse_notice_codes(self.codes_text)
        return self._codes

    def code_status(self, item_code: str | None) -> str:
        """``all``, ``matched``, ``not_listed`` or ``unknown``."""
        if self.covers_all or not self.has_codes:
            return "all"
        if not item_code:
            return "unknown"
        notice = self.notice_codes()
        if notice.empty:
            return "unknown"
        return codes.compare_code(notice, item_code)


@dataclass(slots=True)
class Item:
    id: str
    code: str | None = None
    code_format: str | None = None
    lenient: bool = False
    lot: str | None = None
    name: str | None = None
    brand: str | None = None
    purchased_at: date | None = None


@dataclass(slots=True)
class Match:
    item_id: str
    recall_id: str
    confidence: str
    lot_status: str
    score: int
    gtin: str | None = None
    tokens: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RuledOut:
    item_id: str
    recall_id: str
    reason: str  # lot_not_listed | too_old


@dataclass
class MatchResult:
    matches: list[Match]
    ruled_out: list[RuledOut]


@dataclass
class _Row:
    id: str
    source: str
    title: str
    brand_text: str
    codes: str
    covers_all_codes: bool
    has_codes: bool
    recall_date: date | None
    severity: str
    updated_at: datetime | None


# --- catalog ------------------------------------------------------------------------------


class Catalog:
    """In-memory index over every recall, rebuilt when the database changes."""

    def __init__(
        self, rows: Iterable[_Row], gtins: dict[str, set[str]], version: str, settings: Settings
    ):
        self.version = version
        self.settings = settings
        self.entries: list[Entry] = []
        self.by_gtin: dict[str, list[int]] = defaultdict(list)
        self.postings: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            text = f"{r.title} {r.brand_text}"
            toks = frozenset(tokenize(text))
            e = Entry(
                id=r.id,
                source=r.source,
                gtins=frozenset(gtins.get(r.id, ())),
                tokens=toks,
                text=" ".join(sorted(toks)),
                codes_text=r.codes or "",
                covers_all=r.covers_all_codes,
                has_codes=r.has_codes,
                recall_date=r.recall_date,
                severity=r.severity or "medium",
                updated_at=r.updated_at,
            )
            idx = len(self.entries)
            self.entries.append(e)
            for g in e.gtins:
                self.by_gtin[g].append(idx)
            for t in toks:
                self.postings[t].append(idx)
        self.n = len(self.entries)
        # Smooth IDF as if the catalog held at least 10k notices, so a small or
        # freshly seeded catalog doesn't treat every word as rare.
        self._n_eff = max(self.n, 10_000)
        self._max_df = max(50, int(0.02 * self.n))
        self.vocab = sorted(self.postings)
        self._fix_cache: dict[str, str | None] = {}
        self._by_id = {e.id: e for e in self.entries}

    def __len__(self) -> int:
        return self.n

    # weights ---------------------------------------------------------------

    def weight(self, token: str) -> float:
        df = len(self.postings.get(token, ()))
        if df == 0:
            return 3.0  # unknown to the catalog: weak evidence against a match
        w = math.log(self._n_eff / (df + 0.5))
        return min(w, 2.5) if token in GENERIC else w

    def _correct(self, token: str) -> str:
        """Fix OCR/abbreviation typos against the catalog vocabulary."""
        if token in self.postings or len(token) < 5:
            return token
        if token not in self._fix_cache:
            hit = process.extractOne(token, self.vocab, scorer=fuzz.ratio, score_cutoff=88)
            self._fix_cache[token] = hit[0] if hit else None
        return self._fix_cache[token] or token

    # matching --------------------------------------------------------------

    def match(
        self, items: Sequence[Item], *, since: datetime | None = None, today: date | None = None
    ) -> MatchResult:
        today = today or date.today()
        matches: list[Match] = []
        ruled: list[RuledOut] = []
        for item in items:
            m, r = self._match_item(item, since=since, today=today)
            matches.extend(m)
            ruled.extend(r)
        matches.sort(
            key=lambda m: (
                CONFIDENCE_ORDER[m.confidence],
                SEVERITY_ORDER.get(self._entry(m.recall_id).severity, 1),
                -(self._entry(m.recall_id).recall_date or date.min).toordinal(),
            )
        )
        return MatchResult(matches, ruled)

    def _entry(self, recall_id: str) -> Entry:
        return self._by_id[recall_id]

    def _fresh(self, e: Entry, since: datetime | None) -> bool:
        return since is None or (e.updated_at is not None and aware(e.updated_at) >= since)

    def _match_item(
        self, item: Item, *, since: datetime | None, today: date
    ) -> tuple[list[Match], list[RuledOut]]:
        s = self.settings
        purchased = item.purchased_at or today
        found: list[Match] = []
        ruled: list[RuledOut] = []
        seen: set[str] = set()

        item_gtins = (
            gtin.gtin_candidates(item.code, hint=item.code_format, lenient=item.lenient)
            if item.code
            else []
        )
        for g in item_gtins:
            for idx in self.by_gtin.get(g, ()):
                e = self.entries[idx]
                if e.id in seen:
                    continue
                seen.add(e.id)
                status = e.code_status(item.lot)
                if status == "not_listed":
                    ruled.append(RuledOut(item.id, e.id, "lot_not_listed"))
                    continue
                if (
                    e.recall_date
                    and (purchased - e.recall_date).days > s.upc_match_max_age_days
                    and status != "matched"
                ):
                    ruled.append(RuledOut(item.id, e.id, "too_old"))
                    continue
                if not self._fresh(e, since):
                    continue
                conf = "exact" if status in ("matched", "all") else "upc"
                found.append(Match(item.id, e.id, conf, status, 100, gtin=g))

        q = tokenize(f"{item.brand or ''} {item.name or ''}")
        if not item_gtins:
            q = list(dict.fromkeys(self._correct(t) for t in q))
        if len(q) >= 2:
            found.extend(self._name_matches(item, q, item_gtins, purchased, seen, since))
        return found, ruled

    def _name_matches(
        self,
        item: Item,
        q: list[str],
        item_gtins: list[str],
        purchased: date,
        seen: set[str],
        since: datetime | None,
    ) -> list[Match]:
        s = self.settings
        weights = {t: self.weight(t) for t in q}
        total = sum(weights.values())
        rare = [
            t for t in q if t not in GENERIC and 0 < len(self.postings.get(t, ())) <= self._max_df
        ]
        if not rare:
            return []
        rare.sort(key=lambda t: len(self.postings[t]))
        cand: set[int] = set()
        for t in rare:
            cand.update(self.postings[t])
            if len(cand) > 4000:
                break
        lo = purchased - timedelta(days=s.name_match_days_before_purchase)
        hi = purchased + timedelta(days=s.name_match_days_after_purchase)
        q_text = " ".join(sorted(q))
        scored: list[Match] = []
        for idx in cand:
            e = self.entries[idx]
            if e.id in seen or not e.recall_date or not (lo <= e.recall_date <= hi):
                continue
            if item_gtins and e.gtins:
                continue  # the notice lists barcodes and ours isn't one of them
            matched = [t for t in q if t in e.tokens]
            if len(matched) < 2 or not any(t not in GENERIC for t in matched):
                continue
            wm = sum(weights[t] for t in matched)
            cov = wm / total
            if cov < 0.8 or wm < s.name_match_min_weight:
                continue
            ratio = fuzz.token_set_ratio(q_text, e.text)
            score = round(60 * cov + 0.4 * ratio)
            if score < s.name_match_min_score:
                continue
            status = e.code_status(item.lot)
            if status == "not_listed" or not self._fresh(e, since):
                continue
            scored.append(Match(item.id, e.id, "name", status, score, tokens=matched))
        scored.sort(key=lambda m: -m.score)
        return scored[:NAME_MATCHES_PER_ITEM]


# --- loading ------------------------------------------------------------------------------


def catalog_version(session: Session) -> str:
    count, latest = session.execute(
        select(func.count(Recall.id), func.max(Recall.updated_at))
    ).one()
    stamp = int(aware(latest).timestamp()) if latest else 0
    return f"{count}-{stamp}"


def load_catalog(session: Session, settings: Settings) -> Catalog:
    started = time.perf_counter()
    version = catalog_version(session)
    rows = [
        _Row(*r)  # type: ignore[call-arg]
        for r in session.execute(
            select(
                Recall.id,
                Recall.source,
                Recall.title,
                Recall.brand_text,
                Recall.codes,
                Recall.covers_all_codes,
                Recall.has_codes,
                Recall.recall_date,
                Recall.severity,
                Recall.updated_at,
            )
        )
    ]
    gtins: dict[str, set[str]] = defaultdict(set)
    for rid, g in session.execute(select(RecallGtin.recall_id, RecallGtin.gtin)):
        gtins[rid].add(g)
    cat = Catalog(rows, gtins, version, settings)
    log.info(
        "catalog %s loaded: %d recalls in %.2fs", version, len(cat), time.perf_counter() - started
    )
    return cat


class CatalogHolder:
    """Process-wide catalog, refreshed at most every ``catalog_refresh_seconds``."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._catalog: Catalog | None = None
        self._checked = 0.0
        self._lock = threading.Lock()

    def get(self, session: Session) -> Catalog:
        now = time.monotonic()
        cat = self._catalog
        if cat is not None and now - self._checked < self.settings.catalog_refresh_seconds:
            return cat
        with self._lock:
            if (
                self._catalog is not None
                and now - self._checked < self.settings.catalog_refresh_seconds
            ):
                return self._catalog
            version = catalog_version(session)
            if self._catalog is None or self._catalog.version != version:
                self._catalog = load_catalog(session, self.settings)
            self._checked = time.monotonic()
            return self._catalog

    def invalidate(self) -> None:
        with self._lock:
            self._checked = 0.0
