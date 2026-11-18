from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from boughtsafe.config import Settings
from boughtsafe.db import Recall, SyncRun, utcnow
from boughtsafe.ingest import dedupe_fda_unclassified, prune_runs, sync_all, sync_source
from boughtsafe.sources import OpenFDASource


class FakeFDA(OpenFDASource):
    def __init__(self, settings: Settings, rows: list[dict[str, Any]], fail: bool = False):
        super().__init__(settings)
        self.rows = rows
        self.fail = fail
        self.since: list[date | None] = []

    def fetch(self, client: httpx.Client, since: date | None) -> Iterator[dict[str, Any]]:
        self.since.append(since)
        if self.fail:
            raise RuntimeError("upstream down")
        yield from self.rows


def test_sync_creates_then_skips_unchanged(
    db: Session, settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    src = FakeFDA(settings, raw_fixtures["fda"])
    with httpx.Client() as c:
        first = sync_source(db, src, settings, client=c)
        second = sync_source(db, src, settings, client=c)
    assert first.mode == "full"
    assert first.created == len(raw_fixtures["fda"])
    assert first.changed_buckets
    assert second.mode == "incremental"
    assert (second.created, second.updated) == (0, 0)
    assert src.since[1] == date.today() - timedelta(days=src.lookback_days)
    runs = db.scalars(select(SyncRun).order_by(SyncRun.id)).all()
    assert [r.ok for r in runs] == [True, True]


def test_sync_updates_changed_records(
    db: Session, settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    rows = [dict(r) for r in raw_fixtures["fda"]]
    with httpx.Client() as c:
        sync_source(db, FakeFDA(settings, rows), settings, client=c)
        rows[0]["status"] = "Terminated"
        rows[0]["product_description"] += " UPC 0 36000 29145 2"
        res = sync_source(db, FakeFDA(settings, rows), settings, client=c, full=True)
    assert res.updated == 1
    rec = db.get(Recall, f"fda:{rows[0]['recall_number']}")
    assert rec is not None and rec.status == "closed"
    assert "00036000291452" in {g.gtin for g in rec.gtins}


def test_sync_failure_is_recorded(db: Session, settings: Settings) -> None:
    with httpx.Client() as c:
        res = sync_source(db, FakeFDA(settings, [], fail=True), settings, client=c)
    assert not res.ok
    assert "upstream down" in (res.error or "")
    run = db.scalars(select(SyncRun)).one()
    assert run.ok is False and run.finished_at is not None


def test_full_refresh_after_interval(
    db: Session, settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    src = FakeFDA(settings, raw_fixtures["fda"][:2])
    with httpx.Client() as c:
        sync_source(db, src, settings, client=c)
        run = db.scalars(select(SyncRun)).one()
        run.started_at = utcnow() - timedelta(hours=settings.full_refresh_hours + 1)
        db.commit()
        res = sync_source(db, src, settings, client=c)
    assert res.mode == "full"


def test_dedupe_provisional_fda_rows(
    db: Session, settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    provisional = next(r for r in raw_fixtures["fda"] if not r["recall_number"])
    classified = dict(provisional, recall_number="H-9999-2027", classification="Class II")
    with httpx.Client() as c:
        sync_source(db, FakeFDA(settings, [provisional]), settings, client=c)
        assert db.scalar(select(func.count(Recall.id))) == 1
        sync_source(db, FakeFDA(settings, [classified]), settings, client=c, full=True)
    assert [r.id for r in db.scalars(select(Recall))] == ["fda:H-9999-2027"]
    assert dedupe_fda_unclassified(db) == 0


def test_sync_all_isolates_failures(db: Session, settings: Settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import boughtsafe.ingest as ingest

    monkeypatch.setattr(
        ingest, "build_sources", lambda s, names: [FakeFDA(s, [], fail=True), FakeFDA(s, [])]
    )
    results = sync_all(db, settings)
    assert [r.ok for r in results] == [False, True]


def test_prune_runs(db: Session) -> None:
    for _ in range(5):
        db.add(SyncRun(source="fda", mode="full", ok=True))
    db.commit()
    prune_runs(db, keep=2)
    assert db.scalar(select(func.count(SyncRun.id))) == 2
