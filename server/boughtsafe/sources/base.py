"""Shared types and helpers for recall feed adapters."""

from __future__ import annotations

import hashlib
import html
import json
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from .. import codes as codes_mod
from ..config import Settings


@dataclass
class NormalizedRecall:
    source: str
    source_id: str
    title: str
    product: str
    raw: dict[str, Any]
    event_id: str | None = None
    firm: str | None = None
    brand_text: str = ""
    reason: str = ""
    classification: str | None = None
    severity: str = "medium"
    status: str = "ongoing"
    codes: str = ""
    covers_all_codes: bool = False
    has_codes: bool = False
    distribution: str | None = None
    action: str = ""
    refund: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    image_url: str | None = None
    recall_date: date | None = None
    published_date: date | None = None
    gtins: list[str] = field(default_factory=list)
    hazard: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def content_hash(self) -> str:
        blob = json.dumps(self.raw, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def finalize(self) -> NormalizedRecall:
        if not self.hazard:
            self.hazard = codes_mod.classify_hazard(self.reason).as_dict()
        if not self.action:
            self.action = default_action(self.source, self.hazard)
        self.title = squash(self.title)[:300] or "Recalled product"
        self.product = squash(self.product)
        return self


class Source(ABC):
    name: str
    label: str

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def fetch(self, client: httpx.Client, since: date | None) -> Iterator[dict[str, Any]]:
        """Yield raw upstream records changed on/after ``since`` (all when ``None``)."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedRecall | None:
        """Convert one raw record, or return ``None`` to skip it."""

    #: How far before the last successful run an incremental sync should reach back,
    #: to pick up records the agency back-dated or reclassified.
    lookback_days: int = 30


# --- text helpers -----------------------------------------------------------------

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def squash(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


def clean_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", text)
    return squash(html.unescape(_TAG.sub(" ", text)))


def smart_title(text: str) -> str:
    """Title-case text that arrived in ALL CAPS; leave mixed case alone."""
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        small = {"and", "or", "of", "the", "a", "an", "in", "with", "for", "to", "by"}
        words = text.lower().split(" ")
        return " ".join(
            w if (i and w in small) else (w[:1].upper() + w[1:]) for i, w in enumerate(words)
        )
    return text


_CUT = re.compile(
    r"(?i)\s*(?:[,;(]|\.\s|\bUPC\b|\bnet\s*w|\bpacked\b|\bpackaged\b|\bsold\s+in\b|\bin\s+(?:a|an)\s+"
    r"|\bingredients\b|\bdistributed\b|\bitem\s*(?:#|no)|\bSKU\b|\bASIN\b|\d+(?:\.\d+)?\s?(?:oz|lb|g|ml)\b)"
)


def short_name(description: str, limit: int = 90) -> str:
    """First meaningful phrase of a long FDA product description."""
    text = squash(description).strip("\"' ")
    m = re.search(r'reads? in part[^"]*"([^"]{6,})', text, re.IGNORECASE)
    if m:
        text = m.group(1)
    head = _CUT.split(text, maxsplit=1)[0].strip(" -:\"'")
    if len(head) < 4:
        head = text
    if len(head) > limit:
        head = head[:limit].rsplit(" ", 1)[0] + "…"
    return smart_title(head)


def matching_text(*parts: str | None, limit: int = 600) -> str:
    """Text used for fuzzy name matching: product words, not ingredients or addresses."""
    out = []
    for p in parts:
        if not p:
            continue
        p = re.split(r"(?i)\bingredients?\b|\bdistributed by\b|\bmanufactured (?:by|for)\b", p)[0]
        out.append(squash(p)[:limit])
    return " ".join(out)


def parse_date(value: Any) -> date | None:
    """Parse ``20261014``, ``2026-10-14``, ``2026-10-14T00:00:00`` or ``10/14/2026``."""
    if not value:
        return None
    s = str(value).strip()
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if not m:
            return None
        mo, d, y = (int(g) for g in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def first_sentences(text: str, n: int = 2, limit: int = 420) -> str:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", squash(text))
    out = " ".join(parts[:n])
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"


def load_json_url(client: httpx.Client, url: str, **params: Any) -> Any:
    """GET JSON over HTTP(S), or read it from a ``file://`` URL / plain path."""
    if url.startswith("file://") or url.startswith("/"):
        path = Path(url.removeprefix("file://"))
        return json.loads(path.read_text(encoding="utf-8"))
    r = client.get(url, params=params or None)
    r.raise_for_status()
    return r.json()


def default_action(source: str, hazard: dict[str, Any]) -> str:
    kind = hazard.get("kind")
    if source == "cpsc":
        return "Stop using it. Follow the company's remedy to get a refund, repair or replacement."
    if kind == "allergen" and hazard.get("allergens"):
        who = ", ".join(hazard["allergens"])
        return (
            f"The risk is to people allergic to {who}. If that's anyone you feed, don't eat it: "
            "throw it away or take it back to the store for a refund."
        )
    if kind in {"pathogen", "foreign", "chemical"}:
        return (
            "Don't eat it, even if it looks and smells fine. Throw it away or take it back to the "
            "store for a refund, then wash surfaces it touched."
        )
    return "Don't eat it. Throw it away or take it back to the store where you bought it."


FOOD_REFUND = {
    "options": ["Refund"],
    "text": "Return it to the store where you bought it for a full refund.",
    "contact": None,
}
