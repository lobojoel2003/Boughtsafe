"""openFDA food enforcement reports (https://open.fda.gov/apis/food/enforcement/)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx

from .. import codes, gtin
from .base import FOOD_REFUND, NormalizedRecall, Source, matching_text, parse_date, short_name

log = logging.getLogger(__name__)

PAGE = 1000
MAX_SKIP = 25000  # openFDA refuses skip beyond this; partition the date range instead.

SEVERITY = {"Class I": "high", "Class II": "medium", "Class III": "low"}
IRES_EVENT = "https://www.accessdata.fda.gov/scripts/ires/index.cfm?Event={}"


class OpenFDASource(Source):
    name = "fda"
    label = "FDA"
    lookback_days = 45

    def _windows(self, since: date | None) -> list[tuple[date, date]]:
        today = date.today()
        if since:
            return [(since, today)]
        return [
            (date(y, 1, 1), date(y, 12, 31))
            for y in range(self.settings.backfill_from_year, today.year + 1)
        ]

    def fetch(self, client: httpx.Client, since: date | None) -> Iterator[dict[str, Any]]:
        stack = list(reversed(self._windows(since)))
        while stack:
            start, end = stack.pop()
            skip = 0
            while True:
                params: dict[str, Any] = {
                    "search": f"report_date:[{start:%Y%m%d} TO {end:%Y%m%d}]",
                    "limit": PAGE,
                    "skip": skip,
                    "sort": "report_date:asc",
                }
                if self.settings.openfda_api_key:
                    params["api_key"] = self.settings.openfda_api_key
                r = client.get(self.settings.openfda_url, params=params)
                if r.status_code == 404:  # "No matches found!"
                    break
                r.raise_for_status()
                body = r.json()
                total = int(body["meta"]["results"]["total"])
                if skip == 0 and total > MAX_SKIP + PAGE and start < end:
                    mid = start + (end - start) / 2
                    stack.append((mid + timedelta(days=1), end))
                    stack.append((start, mid))
                    log.info("openFDA window %s..%s has %d rows; splitting", start, end, total)
                    break
                results = body.get("results", [])
                yield from results
                skip += len(results)
                if not results or skip >= total:
                    break

    def normalize(self, raw: dict[str, Any]) -> NormalizedRecall | None:
        desc = raw.get("product_description") or ""
        if not desc:
            return None
        event_id = str(raw.get("event_id") or "") or None
        number = (raw.get("recall_number") or "").strip()
        source_id = number or f"{event_id}-{hashlib.sha1(desc.encode()).hexdigest()[:10]}"  # noqa: S324
        firm = (raw.get("recalling_firm") or "").strip() or None
        code_text = " ".join(
            filter(None, [raw.get("code_info", "").strip(), raw.get("more_code_info", "").strip()])
        )
        name = short_name(desc)
        classification = raw.get("classification") or None
        status_raw = (raw.get("status") or "").lower()
        gtins = gtin.extract_gtins(f"{desc} {code_text}")

        return NormalizedRecall(
            source=self.name,
            source_id=source_id,
            event_id=event_id,
            title=f"{firm} recalls {name}" if firm else name,
            product=desc,
            firm=firm,
            brand_text=matching_text(name, desc, firm),
            reason=(raw.get("reason_for_recall") or "").strip(),
            classification=classification,
            severity=SEVERITY.get(classification or "", "medium"),
            status="ongoing" if status_raw == "ongoing" else "closed",
            codes=code_text,
            covers_all_codes=codes.covers_all_codes(code_text)
            or not codes.has_specific_codes(code_text),
            has_codes=codes.has_specific_codes(code_text),
            distribution=raw.get("distribution_pattern") or None,
            refund=dict(FOOD_REFUND),
            url=IRES_EVENT.format(event_id) if event_id else None,
            recall_date=parse_date(raw.get("recall_initiation_date")),
            published_date=parse_date(raw.get("report_date")),
            gtins=gtins,
            raw=raw,
        ).finalize()
