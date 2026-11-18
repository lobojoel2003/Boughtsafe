"""Turn barcodes into product names with Open Food Facts, cached in the database."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from . import gtin as gtin_mod
from .config import Settings
from .db import ProductCache, aware, utcnow

log = logging.getLogger(__name__)

HIT_TTL = timedelta(days=30)
MISS_TTL = timedelta(days=2)
FIELDS = "product_name,product_name_en,generic_name,brands,quantity,image_front_small_url"


@dataclass
class Product:
    gtin: str
    display: str
    found: bool
    name: str | None = None
    brand: str | None = None
    quantity: str | None = None
    image_url: str | None = None
    source: str | None = None


def _from_cache(row: ProductCache) -> Product:
    return Product(
        gtin=row.gtin,
        display=gtin_mod.display(row.gtin),
        found=row.found,
        name=row.name,
        brand=row.brand,
        quantity=row.quantity,
        image_url=row.image_url,
        source="openfoodfacts" if row.found else None,
    )


def _off_code(g14: str) -> str:
    """OFF keys products by EAN-13 (UPC-A gets a leading zero)."""
    return g14[1:] if g14.startswith("0") else g14


def lookup(session: Session, settings: Settings, client: httpx.Client, g14: str) -> Product:
    row = session.get(ProductCache, g14)
    if row is not None:
        ttl = HIT_TTL if row.found else MISS_TTL
        if utcnow() - aware(row.fetched_at) < ttl:
            return _from_cache(row)
    if not settings.off_enabled:
        return Product(gtin=g14, display=gtin_mod.display(g14), found=False)

    found, name, brand, quantity, image = False, None, None, None, None
    try:
        r = client.get(f"{settings.off_url}/{_off_code(g14)}.json", params={"fields": FIELDS})
        if r.status_code == 200:
            body = r.json()
            p = body.get("product") or {}
            if body.get("status") == 1 and p:
                name = (
                    p.get("product_name") or p.get("product_name_en") or p.get("generic_name") or ""
                ).strip() or None
                brand = (p.get("brands") or "").split(",")[0].strip() or None
                quantity = (p.get("quantity") or "").strip() or None
                image = p.get("image_front_small_url") or None
                found = bool(name or brand)
        elif r.status_code != 404:
            log.info("open food facts returned %s for %s", r.status_code, g14)
            return Product(gtin=g14, display=gtin_mod.display(g14), found=False)
    except httpx.HTTPError as exc:
        log.info("open food facts lookup failed: %s", exc)
        return Product(gtin=g14, display=gtin_mod.display(g14), found=False)

    if row is None:
        row = ProductCache(gtin=g14)
        session.add(row)
    row.found, row.name, row.brand, row.quantity, row.image_url = (
        found,
        name,
        brand,
        quantity,
        image,
    )
    row.fetched_at = utcnow()
    session.flush()
    return _from_cache(row)
