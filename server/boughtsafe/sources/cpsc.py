"""CPSC recalls via the SaferProducts.gov REST service.

https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx

from .. import codes, gtin
from .base import (
    NormalizedRecall,
    Source,
    first_sentences,
    load_json_url,
    matching_text,
    parse_date,
)

_DEATH = re.compile(r"\b(?:death|deaths|died|fatal|fatalities|killed)\b", re.IGNORECASE)
_ORG_TAIL = re.compile(r",\s+of\s+.+$")


def _names(raw: dict[str, Any], key: str, field: str = "Name") -> list[str]:
    return [str(x.get(field) or "").strip() for x in raw.get(key) or [] if x.get(field)]


class CPSCSource(Source):
    name = "cpsc"
    label = "CPSC"
    lookback_days = 14

    def fetch(self, client: httpx.Client, since: date | None) -> Iterator[dict[str, Any]]:
        url = self.settings.cpsc_url
        if since:
            yield from load_json_url(
                client, url, format="json", LastPublishDateStart=since.isoformat()
            )
            return
        for year in range(self.settings.backfill_from_year, date.today().year + 1):
            yield from load_json_url(
                client,
                url,
                format="json",
                RecallDateStart=f"{year}-01-01",
                RecallDateEnd=f"{year}-12-31",
            )

    def normalize(self, raw: dict[str, Any]) -> NormalizedRecall | None:
        number = str(raw.get("RecallNumber") or raw.get("RecallID") or "").strip()
        title = (raw.get("Title") or "").strip()
        if not number or not title:
            return None
        products = _names(raw, "Products")
        models = _names(raw, "Products", "Model")
        description = (raw.get("Description") or "").strip()
        firms = [
            _ORG_TAIL.sub("", n)
            for key in ("Manufacturers", "Importers", "Distributors")
            for n in _names(raw, key)
        ]
        hazards = " ".join(_names(raw, "Hazards"))
        injuries = " ".join(_names(raw, "Injuries"))
        remedies = " ".join(_names(raw, "Remedies"))
        options = [o for o in _names(raw, "RemedyOptions", "Option") if o]
        retailers = " ".join(_names(raw, "Retailers")).replace("Sold At:", "").strip()
        images = [i.get("URL") for i in raw.get("Images") or [] if i.get("URL")]

        upcs: list[str] = []
        for u in _names(raw, "ProductUPCs", "UPC"):
            for g in gtin.gtin_candidates(u, lenient=True):
                if g not in upcs:
                    upcs.append(g)
        for g in gtin.extract_gtins(f"{description} {' '.join(models)}"):
            if g not in upcs:
                upcs.append(g)

        coded = codes.cpsc_has_codes(description)
        code_text = " ".join(filter(None, [description if coded else "", " ".join(models)]))

        return NormalizedRecall(
            source=self.name,
            source_id=number,
            title=title,
            product="; ".join(products) or title,
            firm=firms[0] if firms else None,
            brand_text=matching_text(" ".join(products), title, " ".join(firms), " ".join(models)),
            reason=first_sentences(hazards, n=1) or title,
            classification=None,
            severity="high" if _DEATH.search(f"{hazards} {injuries} {title}") else "medium",
            status="ongoing",
            codes=code_text,
            covers_all_codes=not coded,
            has_codes=coded,
            distribution=retailers or None,
            action=first_sentences(remedies, n=1) if remedies else "",
            refund={
                "options": options,
                "text": first_sentences(remedies, n=3) if remedies else "",
                "contact": (raw.get("ConsumerContact") or "").strip() or None,
            },
            url=(raw.get("URL") or "").strip() or None,
            image_url=images[0] if images else None,
            recall_date=parse_date(raw.get("RecallDate")),
            published_date=parse_date(raw.get("LastPublishDate")),
            gtins=upcs,
            raw=raw,
        ).finalize()
