from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from boughtsafe.api import create_app
from boughtsafe.config import Settings
from boughtsafe.db import Base, get_engine, session_scope
from boughtsafe.ingest import SyncResult, upsert
from boughtsafe.sources import build_sources

FIXTURES = Path(__file__).parent / "fixtures"
# Set to a Postgres URL (as CI does) to run the suite against Postgres instead of SQLite.
TEST_DATABASE_URL = os.environ.get("BOUGHTSAFE_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def raw_fixtures() -> dict[str, Any]:
    return json.loads((FIXTURES / "recalls.json").read_text(encoding="utf-8"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL or f"sqlite:///{tmp_path / 'test.db'}",
        cors_origins=["http://testserver"],
        off_url="https://off.test/api/v2/product",
        openfda_url="https://fda.test/food/enforcement.json",
        cpsc_url="https://cpsc.test/Recall",
        fsis_url="https://fsis.test/api/recall/v/1",
        backfill_from_year=2025,
        catalog_refresh_seconds=0,
    )


@pytest.fixture
def db(settings: Settings) -> Iterator[Session]:
    engine = get_engine(settings.database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with session_scope(settings.database_url) as s:
        yield s


@pytest.fixture
def seeded(db: Session, settings: Settings, raw_fixtures: dict[str, Any]) -> Session:
    for source in build_sources(settings):
        batch = [n for n in (source.normalize(r) for r in raw_fixtures[source.name]) if n]
        upsert(db, batch, SyncResult(source.name, "seed"))
    db.commit()
    return db


@pytest.fixture
def client(settings: Settings, seeded: Session) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
