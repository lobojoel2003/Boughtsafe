"""Mirror upstream recall feeds into the database."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx
from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import gtin as gtin_mod
from .config import Settings
from .db import Recall, RecallGtin, SyncRun, aware, utcnow
from .sources import NormalizedRecall, Source, build_sources

log = logging.getLogger(__name__)

BATCH = 500


@dataclass
class SyncResult:
    source: str
    mode: str
    ok: bool = True
    fetched: int = 0
    created: int = 0
    updated: int = 0
    error: str | None = None
    changed_buckets: set[str] = field(default_factory=set)


def _apply(rec: Recall, n: NormalizedRecall) -> None:
    rec.source = n.source
    rec.source_id = n.source_id
    rec.event_id = n.event_id
    rec.title = n.title
    rec.product = n.product
    rec.firm = n.firm
    rec.brand_text = n.brand_text
    rec.reason = n.reason
    rec.hazard = n.hazard
    rec.classification = n.classification
    rec.severity = n.severity
    rec.status = n.status
    rec.codes = n.codes
    rec.covers_all_codes = n.covers_all_codes
    rec.has_codes = n.has_codes
    rec.distribution = n.distribution
    rec.action = n.action
    rec.refund = n.refund
    rec.url = n.url
    rec.image_url = n.image_url
    rec.recall_date = n.recall_date
    rec.published_date = n.published_date
    rec.content_hash = n.content_hash
    rec.raw = n.raw
    rec.updated_at = utcnow()
    existing = {g.gtin for g in rec.gtins}
    wanted = list(dict.fromkeys(n.gtins))
    if existing != set(wanted):
        rec.gtins = [RecallGtin(gtin=g, bucket=gtin_mod.bucket(g)) for g in wanted]


def upsert(session: Session, batch: list[NormalizedRecall], result: SyncResult) -> None:
    if not batch:
        return
    unique = {n.id: n for n in batch}
    existing = {r.id: r for r in session.scalars(select(Recall).where(Recall.id.in_(list(unique))))}
    for rid, n in unique.items():
        rec = existing.get(rid)
        if rec is None:
            rec = Recall(id=rid, first_seen_at=utcnow())
            _apply(rec, n)
            session.add(rec)
            result.created += 1
        elif rec.content_hash != n.content_hash:
            _apply(rec, n)
            result.updated += 1
        else:
            continue
        result.changed_buckets.update(gtin_mod.bucket(g) for g in n.gtins)
    session.flush()


def last_success(session: Session, source: str) -> SyncRun | None:
    return session.scalars(
        select(SyncRun)
        .where(SyncRun.source == source, SyncRun.ok.is_(True))
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    ).first()


def last_full(session: Session, source: str) -> SyncRun | None:
    return session.scalars(
        select(SyncRun)
        .where(SyncRun.source == source, SyncRun.ok.is_(True), SyncRun.mode == "full")
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    ).first()


def _since(session: Session, source: Source, settings: Settings, full: bool | None) -> date | None:
    if full:
        return None
    prev = last_success(session, source.name)
    full_prev = last_full(session, source.name)
    if prev is None or full_prev is None:
        return None
    if full is None and utcnow() - aware(full_prev.started_at) > timedelta(
        hours=settings.full_refresh_hours
    ):
        return None
    return aware(prev.started_at).date() - timedelta(days=source.lookback_days)


def dedupe_fda_unclassified(session: Session) -> int:
    """Drop provisional FDA rows once the same product is published with a recall number.

    openFDA lists some products before classification without a recall number;
    those rows get a synthetic id and would otherwise linger as duplicates.
    """
    removed = 0
    provisional = session.scalars(
        select(Recall).where(Recall.source == "fda", Recall.source_id.like("%-%"))
    ).all()
    for p in provisional:
        if not p.event_id or p.source_id.startswith(("H-", "F-")):
            continue
        siblings = session.scalars(
            select(Recall).where(
                Recall.source == "fda", Recall.event_id == p.event_id, Recall.id != p.id
            )
        ).all()
        for s in siblings:
            if (
                s.source_id.startswith(("H-", "F-"))
                and fuzz.token_set_ratio(p.product, s.product) >= 90
            ):
                session.delete(p)
                removed += 1
                break
    return removed


def sync_source(
    session: Session,
    source: Source,
    settings: Settings,
    *,
    client: httpx.Client,
    full: bool | None = None,
) -> SyncResult:
    since = _since(session, source, settings, full)
    mode = "full" if since is None else "incremental"
    result = SyncResult(source=source.name, mode=mode)
    run = SyncRun(source=source.name, mode=mode, started_at=utcnow())
    session.add(run)
    session.commit()
    started = time.perf_counter()
    log.info("sync %s (%s%s)", source.name, mode, f" since {since}" if since else "")
    batch: list[NormalizedRecall] = []
    try:
        for raw in source.fetch(client, since):
            result.fetched += 1
            n = source.normalize(raw)
            if n is not None:
                batch.append(n)
            if len(batch) >= BATCH:
                upsert(session, batch, result)
                session.commit()
                batch = []
        upsert(session, batch, result)
        if source.name == "fda":
            dedupe_fda_unclassified(session)
        session.commit()
    except Exception as exc:  # keep other sources running
        session.rollback()
        result.ok = False
        result.error = f"{type(exc).__name__}: {exc}"[:2000]
        log.warning("sync %s failed: %s", source.name, result.error)
    run = session.merge(run)
    run.finished_at = utcnow()
    run.ok = result.ok
    run.fetched, run.created, run.updated = result.fetched, result.created, result.updated
    run.error = result.error
    session.commit()
    log.info(
        "sync %s done in %.1fs: fetched=%d created=%d updated=%d ok=%s",
        source.name,
        time.perf_counter() - started,
        result.fetched,
        result.created,
        result.updated,
        result.ok,
    )
    return result


def sync_all(
    session: Session,
    settings: Settings,
    *,
    names: Iterable[str] | None = None,
    full: bool | None = None,
    client: httpx.Client | None = None,
) -> list[SyncResult]:
    own = client is None
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
        timeout=settings.http_timeout,
        follow_redirects=True,
    )
    try:
        return [
            sync_source(session, s, settings, client=client, full=full)
            for s in build_sources(settings, list(names) if names else None)
        ]
    finally:
        if own:
            client.close()


def prune_runs(session: Session, keep: int = 500) -> None:
    ids = session.scalars(select(SyncRun.id).order_by(SyncRun.id.desc()).offset(keep)).all()
    if ids:
        session.execute(delete(SyncRun).where(SyncRun.id.in_(ids)))
        session.commit()
