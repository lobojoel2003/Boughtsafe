from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from boughtsafe.config import Settings
from boughtsafe.sources import CPSCSource, FSISSource, OpenFDASource


def _by(raws: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    return next(r for r in raws if r.get(key) == value)


# --- openFDA ------------------------------------------------------------------------


def test_fda_normalizes_real_record(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    raw = _by(raw_fixtures["fda"], "recall_number", "H-0197-2027")
    n = OpenFDASource(settings).normalize(raw)
    assert n is not None
    assert n.id == "fda:H-0197-2027"
    assert n.gtins == ["00860007132216"]
    assert n.severity == "high"
    assert n.status == "closed"  # FDA marked this recall "Completed"
    assert n.hazard["kind"] == "pathogen"
    assert n.hazard["label"] == "E. coli"
    assert n.recall_date == date(2026, 10, 14)
    assert n.published_date == date(2026, 11, 11)
    assert n.has_codes and not n.covers_all_codes
    assert n.title.startswith(
        "Family Farmstead Dairy, LLC recalls Family Farmstead Mild Raw Cheddar"
    )
    assert n.url and n.url.endswith("Event=100137")
    assert "refund" in n.refund["text"]


def test_fda_unclassified_record_gets_stable_id(
    settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    raw = next(r for r in raw_fixtures["fda"] if not r["recall_number"])
    a = OpenFDASource(settings).normalize(raw)
    b = OpenFDASource(settings).normalize(dict(raw))
    assert a and b
    assert a.id == b.id
    assert a.source_id.startswith(f"{raw['event_id']}-")
    assert a.gtins == ["00099482520991"]


def test_fda_allergen_action_names_allergen(
    settings: Settings, raw_fixtures: dict[str, Any]
) -> None:
    raw = _by(raw_fixtures["fda"], "recall_number", "H-0090-2027")
    n = OpenFDASource(settings).normalize(raw)
    assert n and n.hazard["allergens"] == ["soy"]
    assert "allergic to soy" in n.action


def test_fda_no_upc_notice(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    raw = _by(raw_fixtures["fda"], "recall_number", "H-0141-2027")
    n = OpenFDASource(settings).normalize(raw)
    assert n and n.gtins == []
    assert n.has_codes


def test_fda_skips_empty(settings: Settings) -> None:
    assert OpenFDASource(settings).normalize({"product_description": ""}) is None


@respx.mock
def test_fda_fetch_paginates_and_handles_empty_years(settings: Settings) -> None:
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        if "2025" in params["search"]:
            skip = int(params["skip"])
            total = 1500
            n = min(1000, total - skip)
            return httpx.Response(
                200,
                json={
                    "meta": {"results": {"skip": skip, "limit": 1000, "total": total}},
                    "results": [{"i": skip + i} for i in range(n)],
                },
            )
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    respx.get(settings.openfda_url).mock(side_effect=handler)
    with httpx.Client() as c:
        rows = list(OpenFDASource(settings).fetch(c, None))
    assert len(rows) == 1500
    assert [c["skip"] for c in calls if "2025" in c["search"]] == ["0", "1000"]
    assert any("2026" in c["search"] for c in calls)


@respx.mock
def test_fda_fetch_incremental_window(settings: Settings) -> None:
    route = respx.get(settings.openfda_url).mock(
        return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
    )
    with httpx.Client() as c:
        assert list(OpenFDASource(settings).fetch(c, date(2026, 11, 1))) == []
    assert route.calls.last.request.url.params["search"].startswith("report_date:[20261101 TO ")


@respx.mock
def test_fda_fetch_uses_api_key(settings: Settings) -> None:
    settings.openfda_api_key = "k123"
    route = respx.get(settings.openfda_url).mock(return_value=httpx.Response(404, json={}))
    with httpx.Client() as c:
        list(OpenFDASource(settings).fetch(c, date(2026, 11, 1)))
    assert route.calls.last.request.url.params["api_key"] == "k123"


@respx.mock
def test_fda_fetch_raises_on_server_error(settings: Settings) -> None:
    respx.get(settings.openfda_url).mock(return_value=httpx.Response(500))
    with httpx.Client() as c, pytest.raises(httpx.HTTPStatusError):
        list(OpenFDASource(settings).fetch(c, date(2026, 11, 1)))


# --- CPSC ---------------------------------------------------------------------------


def test_cpsc_normalizes_upc_and_remedy(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    raw = _by(raw_fixtures["cpsc"], "RecallNumber", "26006")
    n = CPSCSource(settings).normalize(raw)
    assert n is not None
    assert n.id == "cpsc:26006"
    assert n.gtins == ["00070257522266"]
    assert n.hazard["kind"] == "injury"
    assert n.refund["options"]
    assert n.url and n.url.startswith("https://www.cpsc.gov/")
    assert n.covers_all_codes


def test_cpsc_without_upc(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    raw = _by(raw_fixtures["cpsc"], "RecallNumber", "27082")
    n = CPSCSource(settings).normalize(raw)
    assert n and n.gtins == []
    assert n.image_url and n.image_url.startswith("https://")
    assert n.has_codes  # description mentions a lot code sticker
    assert "Refund" in n.refund["options"]


@respx.mock
def test_cpsc_fetch_modes(settings: Settings) -> None:
    route = respx.get(settings.cpsc_url).mock(return_value=httpx.Response(200, json=[{"x": 1}]))
    with httpx.Client() as c:
        assert list(CPSCSource(settings).fetch(c, date(2026, 11, 1))) == [{"x": 1}]
        assert route.calls.last.request.url.params["LastPublishDateStart"] == "2026-11-01"
        rows = list(CPSCSource(settings).fetch(c, None))
    years = date.today().year - settings.backfill_from_year + 1
    assert len(rows) == years
    assert route.calls.last.request.url.params["RecallDateEnd"].endswith("-12-31")


# --- FSIS ---------------------------------------------------------------------------


def test_fsis_normalizes_recall(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    raw = raw_fixtures["fsis"][0]
    n = FSISSource(settings).normalize(raw)
    assert n is not None
    assert n.id == "fsis:099-2026"
    assert n.reason == "Possible Listeria Contamination"
    assert n.hazard["label"] == "Listeria"
    assert n.severity == "high"
    assert n.status == "ongoing"
    assert n.url == (
        "https://www.fsis.usda.gov/recalls-alerts/"
        "example-farms-recalls-smoked-chicken-sausage-products-due-possible-listeria"
    )
    assert "urged not to consume" in n.action
    assert n.has_codes and "26300" in n.codes


def test_fsis_skips_spanish(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    assert FSISSource(settings).normalize(raw_fixtures["fsis"][1]) is None


def test_fsis_public_health_alert(settings: Settings, raw_fixtures: dict[str, Any]) -> None:
    n = FSISSource(settings).normalize(raw_fixtures["fsis"][2])
    assert n is not None
    assert n.source_id.startswith("PHA-2026-10-01-")
    assert n.classification == "Public Health Alert"
    assert n.covers_all_codes
    assert n.hazard["kind"] == "allergen"


def test_fsis_fetch_from_file(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "fsis.json"
    path.write_text(json.dumps([{"field_title": "A"}]))
    settings.fsis_url = f"file://{path}"
    with httpx.Client() as c:
        assert list(FSISSource(settings).fetch(c, None)) == [{"field_title": "A"}]


@respx.mock
def test_fsis_fetch_http_and_wrapper(settings: Settings) -> None:
    respx.get(settings.fsis_url).mock(return_value=httpx.Response(200, json={"data": [{"a": 1}]}))
    with httpx.Client() as c:
        assert list(FSISSource(settings).fetch(c, None)) == [{"a": 1}]


@respx.mock
def test_fsis_blocked_raises(settings: Settings) -> None:
    respx.get(settings.fsis_url).mock(return_value=httpx.Response(403, text="Access Denied"))
    with httpx.Client() as c, pytest.raises(httpx.HTTPStatusError):
        list(FSISSource(settings).fetch(c, None))
