from __future__ import annotations

import base64
from pathlib import Path

import pytest

from boughtsafe import cli
from boughtsafe.config import get_settings

FIXTURE = Path(__file__).parent / "fixtures" / "recalls.json"


@pytest.fixture
def env_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("BOUGHTSAFE_DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert capsys.readouterr().out.startswith("boughtsafe ")


def test_vapid_keys(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["vapid-keys"]) == 0
    out = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    pub = base64.urlsafe_b64decode(out["BOUGHTSAFE_VAPID_PUBLIC_KEY"] + "==")
    priv = base64.urlsafe_b64decode(out["BOUGHTSAFE_VAPID_PRIVATE_KEY"] + "==")
    assert len(pub) == 65 and pub[0] == 4
    assert len(priv) == 32


def test_migrate_and_seed(env_db: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["migrate"]) == 0
    assert cli.main(["seed", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "fda   seeded created=12" in out
    assert "cpsc  seeded created=4" in out
    # seeding twice is idempotent
    assert cli.main(["seed", str(FIXTURE)]) == 0
    assert "created=0" in capsys.readouterr().out


def test_sync_command(
    env_db: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    import boughtsafe.ingest as ingest
    from tests.test_ingest import FakeFDA

    rows = json.loads(FIXTURE.read_text())["fda"]
    monkeypatch.setattr(ingest, "build_sources", lambda s, names: [FakeFDA(s, rows)])
    assert cli.main(["migrate"]) == 0
    assert cli.main(["sync", "--source", "fda"]) == 0
    assert "fda   full        fetched=12 created=12 updated=0 ok" in capsys.readouterr().out

    monkeypatch.setattr(ingest, "build_sources", lambda s, names: [FakeFDA(s, [], fail=True)])
    assert cli.main(["sync"]) == 1
    assert "FAILED (RuntimeError: upstream down)" in capsys.readouterr().out
