"""Database models and session handling (SQLAlchemy 2.0, Postgres in production)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from .config import get_settings

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo; treat naive timestamps as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class Recall(Base):
    """One recalled product, normalized across FDA, FSIS and CPSC."""

    __tablename__ = "recalls"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # "fda:H-0197-2027"
    source: Mapped[str] = mapped_column(String(8), index=True)  # fda | fsis | cpsc
    source_id: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    product: Mapped[str] = mapped_column(Text)
    firm: Mapped[str | None] = mapped_column(Text)
    brand_text: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    hazard: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    classification: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8), default="medium")  # high | medium | low
    status: Mapped[str] = mapped_column(String(16), default="ongoing")  # ongoing | closed
    codes: Mapped[str] = mapped_column(Text, default="")
    covers_all_codes: Mapped[bool] = mapped_column(Boolean, default=False)
    has_codes: Mapped[bool] = mapped_column(Boolean, default=False)
    distribution: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, default="")
    refund: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    recall_date: Mapped[date | None] = mapped_column(Date, index=True)
    published_date: Mapped[date | None] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONType)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    gtins: Mapped[list[RecallGtin]] = relationship(
        back_populates="recall", cascade="all, delete-orphan", lazy="selectin"
    )


class RecallGtin(Base):
    __tablename__ = "recall_gtins"

    recall_id: Mapped[str] = mapped_column(
        ForeignKey("recalls.id", ondelete="CASCADE"), primary_key=True
    )
    gtin: Mapped[str] = mapped_column(String(14), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(4), index=True)

    recall: Mapped[Recall] = relationship(back_populates="gtins")

    __table_args__ = (Index("ix_recall_gtins_gtin", "gtin"),)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(8), index=True)
    mode: Mapped[str] = mapped_column(String(12))  # incremental | full
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class PushSubscription(Base):
    """A browser push endpoint plus the 16-bit watch buckets it asked for.

    No purchases, names or barcodes are stored here.
    """

    __tablename__ = "push_subscriptions"

    endpoint: Mapped[str] = mapped_column(Text, primary_key=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    buckets: Mapped[list[str]] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductCache(Base):
    """Open Food Facts lookups, cached so each barcode is fetched rarely."""

    __tablename__ = "product_cache"

    gtin: Mapped[str] = mapped_column(String(14), primary_key=True)
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def get_engine(url: str | None = None) -> Engine:
    return _engine(url or get_settings().database_url)


@lru_cache
def _engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn: Any, _rec: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


@lru_cache
def _sessionmaker(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=_engine(url), expire_on_commit=False)


@contextmanager
def session_scope(url: str | None = None) -> Iterator[Session]:
    session = _sessionmaker(url or get_settings().database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all(url: str | None = None) -> None:
    Base.metadata.create_all(get_engine(url))
