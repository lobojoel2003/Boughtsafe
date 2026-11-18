"""Lot code, best-by and hazard normalization.

Recall notices describe affected units in prose: ``"Lot: 202526227 Exp. Date:
10-13-28"``, ``"Sell By Oct / 12 3B1 274"``, ``"All lots"``. Shoppers type what
they see on the package: ``"lot 3B1-274"``. Both sides are reduced to runs of
uppercase alphanumerics, and the notice is expanded into n-grams of adjacent
tokens so that codes split by spaces or slashes still compare equal.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from datetime import date

_TOKEN = re.compile(r"[A-Z0-9]+")
_LABELS = re.compile(
    r"^\s*(?:lot(?:\s*(?:code|number|no\.?|#))?|batch(?:\s*code)?|code|"
    r"best\s*(?:if\s*used\s*)?by|bb|use\s*by|sell\s*by|exp(?:iry|iration)?\.?(?:\s*date)?|"
    r"date\s*code)\s*[:#.\-]?\s*",
    re.IGNORECASE,
)
_ALL_CODES = re.compile(
    r"\ball\s+(?:\w+\s+){0,2}(?:lots?|lot\s*codes?|codes?|products?|best[\s\-]*(?:if\s*used\s*)?by|"
    r"use[\s\-]*by|sell[\s\-]*by|dates?|expiration|sizes|units|flavors|batches|packages)\b"
    r"|\bregardless of\b|\bentire (?:product line|inventory)\b|\bwithin expiry\b",
    re.IGNORECASE,
)
_NO_CODE = re.compile(r"^\s*(?:n/?a|none|not applicable|no codes?|-+)?\s*\.?\s*$", re.IGNORECASE)
_CPSC_CODED = re.compile(
    r"\b(?:lot|date code|batch|serial|manufactur(?:ed|e) (?:date|between|from)|production date|"
    r"model (?:numbers?|no))\b",
    re.IGNORECASE,
)

MAX_NGRAM = 4


def normalize_code(raw: str | None) -> str:
    """Normalize a code typed by a person: strip labels, keep ``[A-Z0-9]``."""
    if not raw:
        return ""
    s = raw.strip()
    prev = None
    while prev != s:
        prev = s
        s = _LABELS.sub("", s, count=1)
    return "".join(_TOKEN.findall(s.upper()))


def usable_code(norm: str) -> bool:
    """A code that is safe to match: long enough and not just a word."""
    return len(norm) >= 3 and any(c.isdigit() for c in norm)


def code_keys(text: str | None) -> set[str]:
    """All token n-grams (n <= 4) of a notice's code text that contain a digit."""
    if not text:
        return set()
    tokens = _TOKEN.findall(text.upper())
    keys: set[str] = set()
    for i in range(len(tokens)):
        acc = ""
        for j in range(i, min(i + MAX_NGRAM, len(tokens))):
            acc += tokens[j]
            if usable_code(acc):
                keys.add(acc)
    return keys


def covers_all_codes(text: str | None) -> bool:
    return bool(text) and bool(_ALL_CODES.search(text or ""))


def has_specific_codes(text: str | None) -> bool:
    if not text or _NO_CODE.match(text):
        return False
    if covers_all_codes(text):
        return False
    return bool(code_keys(text))


def cpsc_has_codes(description: str | None) -> bool:
    return bool(description) and bool(_CPSC_CODED.search(description or ""))


_CODE_WORDS = re.compile(
    r"\b(?:lots?|lot\s*codes?|batch|best[\s-]*(?:if\s*used\s*)?by|use[\s-]*by|sell[\s-]*by|"
    r"exp(?:iry|iration)?\.?(?:\s*dates?)?|packed\s*on|pack\s*date|case\s*codes?|date\s*codes?|"
    r"production\s*dates?|julian|serial)\b",
    re.IGNORECASE,
)


def mentions_codes(text: str | None) -> bool:
    """True when prose talks about package codes at all (used for FSIS/CPSC text)."""
    return bool(text) and bool(_CODE_WORDS.search(text or "")) and not covers_all_codes(text)


# --- dates on packages --------------------------------------------------------------

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    )
}
_MON = r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?"
_DATE_PATTERNS = [
    # 2027-07-22, 2027/7/22
    (re.compile(r"(?<!\d)(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?!\d)"), "ymd"),
    # 07/22/2027, 7-22-27
    (re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})(?!\d)"), "mdy"),
    # JUL 22 27, Jul/22/2027, July 22, 2027
    (
        re.compile(
            _MON
            + r"\s*[/\-]?\s*(\d{1,2})(?:ST|ND|RD|TH)?(?:,\s*|\s+|\s*[/\-]\s*)(\d{4}|\d{2})(?!\d)"
        ),
        "Mdy",
    ),
    # 22 JUL 2027, 22JUL27
    (
        re.compile(r"(?<!\d)(\d{1,2})\s*[/\-]?\s*" + _MON + r"\s*[/\-]?\s*(\d{4}|\d{2})(?!\d)"),
        "dMy",
    ),
]
_RANGE_GLUE = re.compile(
    r"^[\s,;:]*(?:to|through|thru|until|-|\u2013|and\s+all\s+dates\s+through)[\s,;:]*"
    r"(?:(?:best|use|sell)\s*(?:if\s*used\s*)?by(?:\s*dates?)?|exp(?:iration)?\.?(?:\s*date)?)?[\s:]*$",
    re.IGNORECASE,
)


def _mk_date(y: int, m: int, d: int) -> date | None:
    if y < 100:
        y += 2000
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[int, int, date]]:
    """(start, end, date) for every package date in ``text``, in order."""
    up = (text or "").upper()
    hits: list[tuple[int, int, date]] = []
    taken: list[tuple[int, int]] = []
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(up):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            g = m.groups()
            if kind == "ymd":
                dt = _mk_date(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "mdy":
                dt = _mk_date(int(g[2]), int(g[0]), int(g[1]))
            elif kind == "Mdy":
                dt = _mk_date(int(g[2]), _MONTHS[g[0]], int(g[1]))
            else:
                dt = _mk_date(int(g[2]), _MONTHS[g[1]], int(g[0]))
            if dt:
                hits.append((m.start(), m.end(), dt))
                taken.append((m.start(), m.end()))
    hits.sort()
    return hits


@dataclass
class NoticeCodes:
    lot_keys: set[str]
    dates: set[date]
    ranges: list[tuple[date, date]]

    @property
    def empty(self) -> bool:
        return not (self.lot_keys or self.dates or self.ranges)


def parse_notice_codes(text: str | None) -> NoticeCodes:
    text = text or ""
    hits = find_dates(text)
    ranges: list[tuple[date, date]] = []
    for (_, a_end, a), (b_start, _, b) in itertools.pairwise(hits):
        if _RANGE_GLUE.match(text[a_end:b_start]) and a <= b:
            ranges.append((a, b))
    stripped = text
    for start, end, _ in reversed(hits):
        stripped = stripped[:start] + " " + stripped[end:]
    stripped = _LABEL_WORDS.sub(" ", stripped)
    return NoticeCodes(code_keys(stripped), {d for _, _, d in hits}, ranges)


_LABEL_WORDS = re.compile(
    r"\b(?:lots?|codes?|best|use|sell|by|if|used|exp(?:iry|iration)?|dates?|and|through|to)\b",
    re.IGNORECASE,
)


def parse_item_code(raw: str | None) -> tuple[str, date | None]:
    """Normalized code plus the date it names, when the whole entry is a date."""
    norm = normalize_code(raw)
    hits = find_dates(raw or "")
    if len(hits) == 1:
        start, end, dt = hits[0]
        rest = normalize_code((raw or "")[:start] + (raw or "")[end:])
        if not rest:
            return norm, dt
    return norm, None


def compare_code(notice: NoticeCodes, raw_item_code: str | None) -> str:
    """``matched``, ``not_listed`` or ``unknown`` for one package code.

    Like is only compared with like: a best-by date is checked against the
    notice's dates and date ranges, a lot code against its lot codes. When the
    notice lists only the other kind, the answer is ``unknown`` rather than a
    reassuring ``not_listed``.
    """
    norm, dt = parse_item_code(raw_item_code)
    if dt is not None:
        if notice.dates or notice.ranges:
            if dt in notice.dates or any(a <= dt <= b for a, b in notice.ranges):
                return "matched"
            return "not_listed"
        return "unknown"
    if not usable_code(norm):
        return "unknown"
    if notice.lot_keys:
        return "matched" if norm in notice.lot_keys else "not_listed"
    return "unknown"


# --- hazards ----------------------------------------------------------------------

ALLERGENS = {
    "milk": r"milk|dairy|casein|whey|lactose",
    "egg": r"\beggs?\b",
    "peanut": r"peanuts?",
    "tree nuts": r"tree nuts?|almonds?|walnuts?|cashews?|pecans?|pistachios?|hazelnuts?|"
    r"macadamia|brazil nuts?|pine nuts?|coconut",
    "wheat": r"wheat|gluten",
    "soy": r"\bsoy|soybeans?|soya",
    "fish": r"\bfish\b|anchov|salmon(?!ella)|tuna|cod\b|pollock|tilapia",
    "shellfish": r"shellfish|shrimp|crab|lobster|crustacean|mollus",
    "sesame": r"sesame",
}

_PATHOGENS = [
    ("Listeria", r"listeria"),
    ("Salmonella", r"salmonella"),
    ("E. coli", r"e\.?\s?coli|stec|o157"),
    ("Botulism", r"botulin|botulism|clostridium"),
    ("Cyclospora", r"cyclospora"),
    ("Hepatitis A", r"hepatitis"),
    ("Norovirus", r"norovirus"),
    ("Cronobacter", r"cronobacter"),
    ("Mold", r"\bmold|mould|mycotoxin|aflatoxin|patulin"),
    ("Bacterial contamination", r"bacteria|pathogen|microbial|5-log"),
]

_FOREIGN = (
    r"foreign (?:material|matter|object)|glass|metal|plastic|rubber|wood|rock|stone|bone fragment"
)
_CHEMICAL = r"\blead\b|arsenic|cadmium|mercury|chemical|pesticide|sulfite|elevated levels|benzene"
_INJURY = (
    r"fire|burn|shock|electrocut|chok|strangul|entrapment|laceration|fall hazard|tip-over|"
    r"crush|poison|ingestion|drowning|suffocat|overheat|explos|injur"
)


@dataclass
class Hazard:
    kind: str  # pathogen | allergen | foreign | chemical | injury | labeling | other
    label: str
    allergens: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "label": self.label, "allergens": self.allergens}


def classify_hazard(reason: str | None) -> Hazard:
    text = (reason or "").lower()
    for label, pattern in _PATHOGENS:
        if re.search(pattern, text):
            return Hazard("pathogen", label)
    if re.search(r"allerg|undeclared|undisclosed|not declared|unreported|mislabel", text):
        found = [name for name, pat in ALLERGENS.items() if re.search(pat, text)]
        if found or "allerg" in text:
            label = "Undeclared " + (", ".join(found) if found else "allergen")
            return Hazard("allergen", label, found)
        return Hazard("labeling", "Labeling error")
    if re.search(_FOREIGN, text):
        return Hazard("foreign", "Foreign material")
    if re.search(_CHEMICAL, text):
        return Hazard("chemical", "Chemical contamination")
    if re.search(_INJURY, text):
        return Hazard("injury", "Injury hazard")
    if re.search(r"label|misbrand|ingredient|inspection|without benefit|import", text):
        return Hazard("labeling", "Labeling or inspection issue")
    return Hazard("other", "Safety issue")
