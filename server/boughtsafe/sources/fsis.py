"""USDA FSIS recalls and public health alerts (https://www.fsis.usda.gov/science-data/developer-resources/recall-api).

The FSIS API returns the complete list on every call, so there is no incremental
mode. Its CDN is known to reject some automated clients and data-center IPs; if
that happens, download the JSON by other means and point
``BOUGHTSAFE_FSIS_URL`` at a ``file://`` path.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx

from .. import codes, gtin
from .base import (
    FOOD_REFUND,
    NormalizedRecall,
    Source,
    clean_html,
    first_sentences,
    load_json_url,
    matching_text,
    parse_date,
)

BASE = "https://www.fsis.usda.gov"
_ACTION = re.compile(
    r"[^.]*\b(?:urged not to (?:consume|eat)|should be thrown away|"
    r"returned to the place of purchase|not to consume|throw (?:them|it) away)\b[^.]*\.",
    re.IGNORECASE,
)
_CODE_SENTENCE = re.compile(
    r"[^.]*\b(?:lot|use[\s-]*by|best[\s-]*by|sell[\s-]*by|establishment number|EST\.|P-\d|"
    r"case code|packed on|production date|UPC)\b[^.]*\.",
    re.IGNORECASE,
)


def _flag(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes"}


def _severity(risk: str, classification: str) -> str:
    text = f"{risk} {classification}".lower()
    if "high" in text or ("class i" in text and "class ii" not in text):
        return "high"
    if "marginal" in text or "class iii" in text:
        return "low"
    return "medium"


def _product_phrase(title: str) -> str:
    m = re.search(
        r"\bRecalls?\s+(.+?)(?:\s+(?:Due to|Because|for Possible|That|Produced)\b|$)", title
    )
    return m.group(1) if m else title


class FSISSource(Source):
    name = "fsis"
    label = "USDA FSIS"

    def fetch(self, client: httpx.Client, since: date | None) -> Iterator[dict[str, Any]]:
        data = load_json_url(client, self.settings.fsis_url)
        if isinstance(data, dict):  # tolerate {"data": [...]} wrappers
            data = data.get("data") or data.get("results") or []
        yield from data

    def normalize(self, raw: dict[str, Any]) -> NormalizedRecall | None:
        lang = (raw.get("langcode") or "English").strip().lower()
        if lang not in {"english", "en"}:
            return None
        title = (raw.get("field_title") or "").strip()
        if not title:
            return None
        number = (raw.get("field_recall_number") or "").strip()
        recall_date = parse_date(raw.get("field_recall_date"))
        recall_type = (raw.get("field_recall_type") or "").strip()
        if not number:
            digest = hashlib.sha1(title.encode()).hexdigest()[:8]  # noqa: S324
            number = f"PHA-{recall_date or 'undated'}-{digest}"
        summary = clean_html(raw.get("field_summary"))
        items = clean_html(raw.get("field_product_items"))
        firm = (raw.get("field_establishment") or "").strip() or None
        reason_m = re.search(r"\b(?:Due to|Because of)\s+(.+)$", title, re.IGNORECASE)
        reason = reason_m.group(1) if reason_m else (raw.get("field_recall_reason") or "")
        classification = (raw.get("field_recall_classification") or "").strip()
        if "health alert" in recall_type.lower():
            classification = "Public Health Alert"
        code_text = " ".join(
            [items] + [m.group(0).strip() for m in _CODE_SENTENCE.finditer(summary)]
        ).strip()
        actions = [m.group(0).strip() for m in _ACTION.finditer(summary)]
        url = (raw.get("field_recall_url") or "").strip() or None
        if url and url.startswith("/"):
            url = BASE + url
        active = _flag(raw.get("field_active_notice")) or "active" in recall_type.lower()
        product = items or _product_phrase(title)

        return NormalizedRecall(
            source=self.name,
            source_id=number,
            title=title,
            product=product,
            firm=firm,
            brand_text=matching_text(_product_phrase(title), items, firm),
            reason=reason.strip().rstrip("."),
            classification=classification or None,
            severity=_severity(raw.get("field_risk_level") or "", classification),
            status="ongoing" if active and not _flag(raw.get("field_archive_recall")) else "closed",
            codes=code_text,
            covers_all_codes=codes.covers_all_codes(code_text)
            or not codes.mentions_codes(code_text),
            has_codes=codes.mentions_codes(code_text),
            distribution=(raw.get("field_states") or "").strip() or None,
            action=first_sentences(" ".join(actions), n=2) if actions else "",
            refund=dict(FOOD_REFUND),
            url=url,
            recall_date=recall_date,
            published_date=parse_date(raw.get("field_last_modified_date")) or recall_date,
            gtins=gtin.extract_gtins(f"{items} {summary}"),
            raw=raw,
        ).finalize()
