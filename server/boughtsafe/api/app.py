"""FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import __version__, gtin, products, push
from ..config import Settings, get_settings
from ..db import PushSubscription, Recall, RecallGtin, SyncRun, aware, session_scope, utcnow
from ..matching import CatalogHolder, Item
from ..sources import LABELS
from .schemas import (
    CatalogOut,
    EndpointIn,
    Gtin,
    MatchOut,
    MatchRequest,
    MatchResponse,
    Meta,
    ProductOut,
    RecallOut,
    RecallPage,
    RuledOutOut,
    SourceStatus,
    SubscriptionIn,
)

log = logging.getLogger("boughtsafe.api")

# Push services browsers actually use. Subscriptions elsewhere are refused so the
# server can't be used to POST to arbitrary hosts.
PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
    "push.apple.com",
)


def db_session(request: Request) -> Iterator[Session]:
    with session_scope(request.app.state.settings.database_url) as s:
        yield s


DbSession = Annotated[Session, Depends(db_session)]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    holder = CatalogHolder(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.http = httpx.Client(
            headers={"User-Agent": settings.user_agent}, timeout=10.0, follow_redirects=True
        )
        yield
        app.state.http.close()

    app = FastAPI(
        title="Boughtsafe API",
        version=__version__,
        summary="Recall alerts matched to what you actually bought.",
        description=(
            "Boughtsafe mirrors the openFDA food enforcement, USDA FSIS and CPSC recall feeds. "
            "`POST /v1/match` checks a list of purchases against them. Purchases are processed "
            "in memory for the length of the request and never written to disk or logs."
        ),
        license_info={"name": "AGPL-3.0-or-later", "identifier": "AGPL-3.0-or-later"},
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.catalog = holder
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type"],
        max_age=86400,
    )

    @app.middleware("http")
    async def headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Boughtsafe-Version"] = __version__
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if request.url.path.startswith(("/v1/match", "/v1/push")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz", tags=["ops"])
    def readyz(session: DbSession) -> dict[str, object]:
        count = session.scalar(select(func.count(Recall.id))) or 0
        return {"status": "ok", "recalls": count}

    @app.get("/v1/meta", response_model=Meta, tags=["catalog"])
    def meta(session: DbSession) -> Meta:
        counts = dict(
            session.execute(
                select(Recall.source, func.count(Recall.id)).group_by(Recall.source)
            ).all()
        )
        sources = []
        for name, label in LABELS.items():
            last = session.scalars(
                select(SyncRun)
                .where(SyncRun.source == name)
                .order_by(SyncRun.started_at.desc())
                .limit(1)
            ).first()
            sources.append(
                SourceStatus(
                    source=name,
                    label=label,
                    count=counts.get(name, 0),
                    last_sync=aware(last.finished_at) if last and last.finished_at else None,
                    last_ok=last.ok if last else None,
                    last_error=(last.error or None) if last else None,
                )
            )
        return Meta(
            version=__version__,
            build=settings.build_number,
            commit=settings.git_sha,
            catalog_version=holder.get(session).version,
            sources=sources,
            push_enabled=settings.push_enabled,
            vapid_public_key=settings.vapid_public_key if settings.push_enabled else None,
        )

    @app.post("/v1/match", response_model=MatchResponse, tags=["match"])
    def match(body: MatchRequest, session: DbSession) -> MatchResponse:
        """Check purchases against every recall. Nothing in the request is stored."""
        if len(body.items) > settings.max_items_per_request:
            raise HTTPException(413, "too many items")
        catalog = holder.get(session)
        items = [
            Item(
                id=i.id,
                code=i.code,
                code_format=i.code_format,
                lenient=i.lenient,
                lot=i.lot,
                name=i.name,
                brand=i.brand,
                purchased_at=i.purchased_at,
            )
            for i in body.items
        ]
        result = catalog.match(items, since=aware(body.since) if body.since else None)
        ids = {m.recall_id for m in result.matches} | {r.recall_id for r in result.ruled_out}
        recalls = (
            {r.id: r for r in session.scalars(select(Recall).where(Recall.id.in_(ids)))}
            if ids
            else {}
        )
        out = [
            MatchOut(
                item_id=m.item_id,
                confidence=m.confidence,  # type: ignore[arg-type]
                lot_status=m.lot_status,  # type: ignore[arg-type]
                score=m.score,
                matched_gtin=Gtin(gtin=m.gtin, display=gtin.display(m.gtin)) if m.gtin else None,
                matched_terms=m.tokens,
                recall=RecallOut.of(recalls[m.recall_id]),
            )
            for m in result.matches
            if m.recall_id in recalls
        ]
        ruled = [
            RuledOutOut(
                item_id=r.item_id,
                recall_id=r.recall_id,
                reason=r.reason,  # type: ignore[arg-type]
                title=recalls[r.recall_id].title,
            )
            for r in result.ruled_out
            if r.recall_id in recalls
        ]
        log.info("match: %d item(s) -> %d match(es)", len(items), len(out))
        return MatchResponse(
            matches=out,
            ruled_out=ruled,
            catalog=CatalogOut(version=catalog.version, total=len(catalog), checked_at=utcnow()),
        )

    @app.get("/v1/recalls", response_model=RecallPage, tags=["catalog"])
    def list_recalls(
        session: DbSession,
        source: Annotated[str | None, Query(pattern="^(fda|fsis|cpsc)$")] = None,
        q: Annotated[str | None, Query(max_length=100)] = None,
        code: Annotated[str | None, Query(max_length=32, description="Barcode to look up")] = None,
        since: date | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> RecallPage:
        stmt = select(Recall)
        if source:
            stmt = stmt.where(Recall.source == source)
        if since:
            stmt = stmt.where(Recall.published_date >= since)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(func.lower(Recall.title).like(like), func.lower(Recall.product).like(like))
            )
        if code:
            cands = gtin.gtin_candidates(code, lenient=True)
            if not cands:
                return RecallPage(total=0, items=[])
            stmt = stmt.where(
                Recall.id.in_(select(RecallGtin.recall_id).where(RecallGtin.gtin.in_(cands)))
            )
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(Recall.published_date.desc().nulls_last(), Recall.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return RecallPage(total=total, items=[RecallOut.of(r) for r in rows])

    @app.get("/v1/recalls/{recall_id:path}", response_model=RecallOut, tags=["catalog"])
    def get_recall(recall_id: str, session: DbSession) -> RecallOut:
        r = session.get(Recall, recall_id)
        if r is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "recall not found")
        return RecallOut.of(r)

    @app.get("/v1/products/{code}", response_model=ProductOut, tags=["products"])
    def get_product(
        code: str, request: Request, session: DbSession, format: str | None = None
    ) -> ProductOut:
        """Barcode to product name via Open Food Facts (cached)."""
        g = gtin.normalize(code, hint=format) or next(
            iter(gtin.gtin_candidates(code, lenient=True)), None
        )
        if g is None:
            raise HTTPException(422, "not a valid UPC/EAN barcode")
        p = products.lookup(session, settings, request.app.state.http, g)
        session.commit()
        return ProductOut(**p.__dict__)

    # --- push --------------------------------------------------------------------

    def _check_endpoint(endpoint: str) -> None:
        u = urlparse(endpoint)
        host = (u.hostname or "").lower()
        if u.scheme != "https" or not any(
            host == s or host.endswith("." + s) for s in PUSH_HOST_SUFFIXES
        ):
            raise HTTPException(422, "unsupported push service")

    @app.post("/v1/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT, tags=["push"])
    def subscribe(body: SubscriptionIn, session: DbSession) -> Response:
        """Register (or update) a device and the watch buckets it wants alerts for."""
        if not settings.push_enabled:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "push is not configured")
        _check_endpoint(body.endpoint)
        sub = session.get(PushSubscription, body.endpoint)
        if sub is None:
            sub = PushSubscription(endpoint=body.endpoint, created_at=utcnow())
            session.add(sub)
        sub.p256dh, sub.auth = body.keys.p256dh, body.keys.auth
        sub.buckets = body.buckets
        sub.updated_at = utcnow()
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.delete("/v1/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT, tags=["push"])
    def unsubscribe(body: EndpointIn, session: DbSession) -> Response:
        sub = session.get(PushSubscription, body.endpoint)
        if sub is not None:
            session.delete(sub)
            session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/v1/push/test", status_code=status.HTTP_202_ACCEPTED, tags=["push"])
    def push_test(body: EndpointIn, session: DbSession) -> dict[str, bool]:
        """Send a test notification to an already-registered device."""
        sub = session.get(PushSubscription, body.endpoint)
        if sub is None or not settings.push_enabled:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "subscription not found")
        ok = push.send(settings, sub, {"t": "test"})
        if not ok:
            session.delete(sub)
            session.commit()
        return {"sent": ok}

    return app
