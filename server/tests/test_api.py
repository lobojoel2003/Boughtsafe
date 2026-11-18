from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from boughtsafe.api import create_app
from boughtsafe.config import Settings
from boughtsafe.db import ProductCache, PushSubscription
from boughtsafe.push import generate_vapid_keys, notify

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
KEYS = {"p256dh": "B" * 87, "auth": "A" * 22}


def test_health(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["X-Boughtsafe-Version"]
    assert client.get("/readyz").json()["recalls"] > 0


def test_meta(client: TestClient) -> None:
    body = client.get("/v1/meta").json()
    assert body["name"] == "Boughtsafe"
    assert {s["source"] for s in body["sources"]} == {"fda", "fsis", "cpsc"}
    counts = {s["source"]: s["count"] for s in body["sources"]}
    assert counts["fda"] == 12 and counts["cpsc"] == 4 and counts["fsis"] == 2
    assert body["push_enabled"] is False
    assert body["vapid_public_key"] is None


def test_match_end_to_end(client: TestClient) -> None:
    r = client.post(
        "/v1/match",
        json={
            "items": [
                {
                    "id": "cheddar",
                    "code": "860007132216",
                    "lot": "JUL 22 27",
                    "name": "Raw cheddar",
                },
                {"id": "rolls", "name": "WINCO HOAGIE ROLLS", "purchased_at": "2026-10-01"},
                {"id": "milk", "name": "whole milk"},
                {"id": "lot", "code": "860007132216", "lot": "AUG 01 27"},
            ]
        },
    )
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    body = r.json()
    got = [(m["item_id"], m["confidence"]) for m in body["matches"]]
    assert got == [("cheddar", "exact"), ("rolls", "name")]
    card = body["matches"][0]["recall"]
    assert card["source_label"] == "FDA"
    assert card["hazard"]["label"] == "E. coli"
    assert card["gtins"] == [{"gtin": "00860007132216", "display": "8 60007 13221 6"}]
    assert body["matches"][0]["matched_gtin"]["display"] == "8 60007 13221 6"
    assert body["ruled_out"] == [
        {
            "item_id": "lot",
            "recall_id": "fda:H-0197-2027",
            "reason": "lot_not_listed",
            "title": card["title"],
        }
    ]
    assert body["catalog"]["total"] == 18


def test_match_validates(client: TestClient) -> None:
    assert client.post("/v1/match", json={"items": [{"id": ""}]}).status_code == 422
    too_many = [{"id": str(i)} for i in range(2001)]
    assert client.post("/v1/match", json={"items": too_many}).status_code == 422


def test_recalls_list_and_filters(client: TestClient) -> None:
    page = client.get("/v1/recalls", params={"limit": 5}).json()
    assert page["total"] == 18 and len(page["items"]) == 5
    fda = client.get("/v1/recalls", params={"source": "cpsc"}).json()
    assert fda["total"] == 4
    q = client.get("/v1/recalls", params={"q": "hoagie"}).json()
    assert [i["id"] for i in q["items"]] == ["fda:H-0196-2027"]
    code = client.get("/v1/recalls", params={"code": "0 70552 00649 2"}).json()
    assert [i["id"] for i in code["items"]] == ["fda:H-0196-2027"]
    assert client.get("/v1/recalls", params={"code": "12"}).json()["total"] == 0
    assert client.get("/v1/recalls", params={"source": "nope"}).status_code == 422


def test_get_recall(client: TestClient) -> None:
    r = client.get("/v1/recalls/cpsc:26006")
    assert r.status_code == 200
    assert r.json()["refund"]["options"]
    assert client.get("/v1/recalls/fda:missing").status_code == 404


@respx.mock
def test_product_lookup_and_cache(client: TestClient, seeded: Session, settings: Settings) -> None:
    route = respx.get(f"{settings.off_url}/0737628064502.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": 1,
                "product": {
                    "product_name": "Thai peanut noodle kit",
                    "brands": "Simply Asia, Thai Kitchen",
                    "quantity": "155 g",
                    "image_front_small_url": "https://images.openfoodfacts.org/x.jpg",
                },
            },
        )
    )
    r = client.get("/v1/products/737628064502")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "gtin": "00737628064502",
        "display": "7 37628 06450 2",
        "found": True,
        "name": "Thai peanut noodle kit",
        "brand": "Simply Asia",
        "quantity": "155 g",
        "image_url": "https://images.openfoodfacts.org/x.jpg",
        "source": "openfoodfacts",
    }
    client.get("/v1/products/737628064502")
    assert route.call_count == 1  # second call served from cache
    seeded.expire_all()
    assert seeded.get(ProductCache, "00737628064502") is not None


@respx.mock
def test_product_not_found_and_invalid(client: TestClient, settings: Settings) -> None:
    respx.get(f"{settings.off_url}/0036000291452.json").mock(return_value=httpx.Response(404))
    r = client.get("/v1/products/036000291452")
    assert r.status_code == 200 and r.json()["found"] is False
    assert client.get("/v1/products/123").status_code == 422


@respx.mock
def test_product_upstream_error_not_cached(client: TestClient, settings: Settings) -> None:
    route = respx.get(f"{settings.off_url}/0036000291452.json").mock(
        side_effect=httpx.ConnectError("down")
    )
    assert client.get("/v1/products/036000291452").json()["found"] is False
    client.get("/v1/products/036000291452")
    assert route.call_count == 2


def test_push_disabled_by_default(client: TestClient) -> None:
    r = client.post(
        "/v1/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS, "buckets": ["2675"]}
    )
    assert r.status_code == 503


def _push_app(settings: Settings, seeded: Session) -> TestClient:
    pub, priv = generate_vapid_keys()
    settings.vapid_public_key, settings.vapid_private_key = pub, priv
    return TestClient(create_app(settings))


def test_push_subscribe_flow(settings: Settings, seeded: Session) -> None:
    with _push_app(settings, seeded) as c:
        assert c.get("/v1/meta").json()["vapid_public_key"] == settings.vapid_public_key
        r = c.post(
            "/v1/push/subscriptions",
            json={"endpoint": ENDPOINT, "keys": KEYS, "buckets": ["2675", "ABCD", "2675"]},
        )
        assert r.status_code == 204
        seeded.expire_all()
        sub = seeded.get(PushSubscription, ENDPOINT)
        assert sub is not None and sub.buckets == ["2675", "abcd"]

        bad_host = {"endpoint": "https://evil.example.com/x", "keys": KEYS, "buckets": []}
        assert c.post("/v1/push/subscriptions", json=bad_host).status_code == 422
        bad_bucket = {"endpoint": ENDPOINT, "keys": KEYS, "buckets": ["xyz"]}
        assert c.post("/v1/push/subscriptions", json=bad_bucket).status_code == 422

        with patch("pywebpush.webpush") as wp:
            assert c.post("/v1/push/test", json={"endpoint": ENDPOINT}).json() == {"sent": True}
            assert wp.call_count == 1
        assert c.post("/v1/push/test", json={"endpoint": ENDPOINT + "x"}).status_code == 404

        assert (
            c.request("DELETE", "/v1/push/subscriptions", json={"endpoint": ENDPOINT}).status_code
            == 204
        )
        seeded.expire_all()
        assert seeded.get(PushSubscription, ENDPOINT) is None


def test_notify_only_wakes_matching_buckets(settings: Settings, seeded: Session) -> None:
    pub, priv = generate_vapid_keys()
    settings.vapid_public_key, settings.vapid_private_key = pub, priv
    seeded.add_all(
        [
            PushSubscription(endpoint=ENDPOINT, p256dh="p", auth="a", buckets=["2675", "0000"]),
            PushSubscription(endpoint=ENDPOINT + "2", p256dh="p", auth="a", buckets=["ffff"]),
        ]
    )
    seeded.commit()
    sent: list[dict[str, Any]] = []
    with patch("pywebpush.webpush", side_effect=lambda **kw: sent.append(kw)):
        assert notify(seeded, settings, {"2675", "1234"}, "v1") == 1
    assert len(sent) == 1
    assert sent[0]["subscription_info"]["endpoint"] == ENDPOINT
    assert sent[0]["data"] == '{"t":"recall","b":["2675"],"v":"v1"}'


def test_notify_drops_gone_subscriptions(settings: Settings, seeded: Session) -> None:
    from pywebpush import WebPushException

    pub, priv = generate_vapid_keys()
    settings.vapid_public_key, settings.vapid_private_key = pub, priv
    seeded.add(PushSubscription(endpoint=ENDPOINT, p256dh="p", auth="a", buckets=["2675"]))
    seeded.commit()
    gone = WebPushException("gone", response=httpx.Response(410))
    with patch("pywebpush.webpush", side_effect=gone):
        assert notify(seeded, settings, {"2675"}, "v1") == 0
    assert seeded.scalars(select(PushSubscription)).all() == []


def test_cors(client: TestClient) -> None:
    r = client.options(
        "/v1/match",
        headers={"Origin": "http://testserver", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers["access-control-allow-origin"] == "http://testserver"
