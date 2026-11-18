"""Request and response models for the public HTTP API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import gtin as gtin_mod
from ..db import Recall
from ..sources import LABELS

Confidence = Literal["exact", "upc", "name"]
LotStatus = Literal["matched", "all", "unknown"]


class Gtin(BaseModel):
    gtin: str
    display: str


class Hazard(BaseModel):
    kind: str = "other"
    label: str = "Safety issue"
    allergens: list[str] = Field(default_factory=list)


class Refund(BaseModel):
    options: list[str] = Field(default_factory=list)
    text: str = ""
    contact: str | None = None


class RecallOut(BaseModel):
    id: str
    source: Literal["fda", "fsis", "cpsc"]
    source_label: str
    title: str
    product: str
    firm: str | None
    reason: str
    hazard: Hazard
    classification: str | None
    severity: Literal["high", "medium", "low"]
    status: Literal["ongoing", "closed"]
    codes: str
    covers_all_codes: bool
    distribution: str | None
    action: str
    refund: Refund
    url: str | None
    image_url: str | None
    recall_date: date | None
    published_date: date | None
    gtins: list[Gtin]

    @classmethod
    def of(cls, r: Recall) -> RecallOut:
        return cls(
            id=r.id,
            source=r.source,  # type: ignore[arg-type]
            source_label=LABELS.get(r.source, r.source.upper()),
            title=r.title,
            product=r.product,
            firm=r.firm,
            reason=r.reason,
            hazard=Hazard(**(r.hazard or {})),
            classification=r.classification,
            severity=r.severity,  # type: ignore[arg-type]
            status=r.status,  # type: ignore[arg-type]
            codes=r.codes,
            covers_all_codes=r.covers_all_codes or not r.has_codes,
            distribution=r.distribution,
            action=r.action,
            refund=Refund(**(r.refund or {})),
            url=r.url,
            image_url=r.image_url,
            recall_date=r.recall_date,
            published_date=r.published_date,
            gtins=[Gtin(gtin=g.gtin, display=gtin_mod.display(g.gtin)) for g in r.gtins],
        )


class ItemIn(BaseModel):
    """One thing you own. Only sent for the length of a request; never stored."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64, description="Opaque id chosen by the client.")
    code: str | None = Field(None, max_length=64, description="Barcode digits as scanned or typed.")
    code_format: str | None = Field(
        None, max_length=16, description="Scanner symbology, e.g. upc_e."
    )
    lenient: bool = Field(
        False, description="Repair codes copied from receipts (missing check digit)."
    )
    lot: str | None = Field(
        None, max_length=80, description="Lot code or best-by date on the package."
    )
    name: str | None = Field(None, max_length=300)
    brand: str | None = Field(None, max_length=120)
    purchased_at: date | None = None


class MatchRequest(BaseModel):
    items: list[ItemIn] = Field(max_length=2000)
    since: datetime | None = Field(
        None, description="Only report recalls added or changed after this time."
    )


class MatchOut(BaseModel):
    item_id: str
    confidence: Confidence
    lot_status: LotStatus
    score: int
    matched_gtin: Gtin | None
    matched_terms: list[str]
    recall: RecallOut


class RuledOutOut(BaseModel):
    item_id: str
    recall_id: str
    reason: Literal["lot_not_listed", "too_old"]
    title: str


class CatalogOut(BaseModel):
    version: str
    total: int
    checked_at: datetime


class MatchResponse(BaseModel):
    matches: list[MatchOut]
    ruled_out: list[RuledOutOut]
    catalog: CatalogOut


class SourceStatus(BaseModel):
    source: str
    label: str
    count: int
    last_sync: datetime | None
    last_ok: bool | None
    last_error: str | None


class Meta(BaseModel):
    name: str = "Boughtsafe"
    version: str
    build: str
    commit: str
    catalog_version: str
    sources: list[SourceStatus]
    push_enabled: bool
    vapid_public_key: str | None


class ProductOut(BaseModel):
    gtin: str
    display: str
    found: bool
    name: str | None = None
    brand: str | None = None
    quantity: str | None = None
    image_url: str | None = None
    source: str | None = None


class RecallPage(BaseModel):
    total: int
    items: list[RecallOut]


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=12, max_length=1000)
    keys: PushKeys
    buckets: list[str] = Field(default_factory=list, max_length=20000)

    @field_validator("buckets")
    @classmethod
    def _buckets(cls, v: list[str]) -> list[str]:
        out = sorted({b.lower() for b in v})
        for b in out:
            if len(b) != 4 or any(c not in "0123456789abcdef" for c in b):
                raise ValueError("buckets are 4 lowercase hex characters")
        return out


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=12, max_length=1000)
