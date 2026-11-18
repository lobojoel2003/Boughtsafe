from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from boughtsafe.config import Settings
from boughtsafe.matching import Catalog, CatalogHolder, Item, load_catalog, tokenize


@pytest.fixture
def catalog(seeded: Session, settings: Settings) -> Catalog:
    return load_catalog(seeded, settings)


def ids(result) -> list[tuple[str, str, str, str]]:  # type: ignore[no-untyped-def]
    return [(m.item_id, m.recall_id, m.confidence, m.lot_status) for m in result.matches]


def test_tokenize() -> None:
    assert tokenize("Trader Joe\u2019s Unexpected Cheddar 8oz BLOCKS") == [
        "trader",
        "joe",
        "unexpected",
        "cheddar",
        "block",
    ]
    assert tokenize("The 12 oz. pack of Cookies") == tokenize("cookie") == ["cooki"]
    assert tokenize("berries") == tokenize("Berry") == ["berri"]


def test_exact_upc_and_best_by(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="860007132216", lot="Best by JUL 22 27")])
    assert ids(r) == [("a", "fda:H-0197-2027", "exact", "matched")]


def test_upc_only_when_code_unknown(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="8 60007 13221 6")])
    assert ids(r) == [("a", "fda:H-0197-2027", "upc", "unknown")]
    assert r.matches[0].gtin == "00860007132216"


def test_lot_not_listed_is_silent_but_explained(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="860007132216", lot="AUG 01 27")])
    assert r.matches == []
    assert [(x.recall_id, x.reason) for x in r.ruled_out] == [("fda:H-0197-2027", "lot_not_listed")]


def test_best_by_inside_range(catalog: Catalog) -> None:
    # Gearharts: "BEST BY OCT 1 2026 to BEST BY OCT 21 2026"
    r = catalog.match([Item("a", code="898111002057", lot="10/10/2026")])
    assert ids(r) == [("a", "fda:H-0096-2027", "exact", "matched")]


def test_upc_missing_check_digit_in_notice(catalog: Catalog) -> None:
    # The notice printed "UPC 8 98111 00206" without its check digit.
    r = catalog.match([Item("a", code="898111002064")])
    assert ids(r) == [("a", "fda:H-0096-2027", "upc", "unknown")]


def test_ean13_import(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="4056489722458", lot="085261")])
    assert ids(r) == [("a", "fda:H-0193-2027", "exact", "matched")]


def test_cpsc_upc_covers_all_units(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="070257522266", purchased_at=date(2025, 9, 1))])
    assert ids(r) == [("a", "cpsc:26006", "exact", "all")]


def test_old_recall_ignored_for_new_purchase(catalog: Catalog) -> None:
    r = catalog.match([Item("a", code="070257522266", purchased_at=date(2030, 1, 1))])
    assert r.matches == []
    assert r.ruled_out[0].reason == "too_old"


def test_receipt_name_match(catalog: Catalog) -> None:
    r = catalog.match([Item("a", name="WINCO HOAGIE ROLLS 6CT", purchased_at=date(2026, 10, 1))])
    assert ids(r) == [("a", "fda:H-0196-2027", "name", "unknown")]
    assert set(r.matches[0].tokens) >= {"winco", "hoagi"}


def test_ocr_typo_is_corrected(catalog: Catalog) -> None:
    r = catalog.match(
        [Item("a", name="Famly Farmsteed raw chedar", purchased_at=date(2026, 10, 20))]
    )
    assert [m.recall_id for m in r.matches] == ["fda:H-0197-2027"]


def test_generic_names_stay_silent(catalog: Catalog) -> None:
    items = [
        Item("1", name="cheddar cheese"),
        Item("2", name="hoagie rolls"),
        Item("3", name="milk"),
        Item("4", name="organic chicken breast"),
    ]
    assert catalog.match(items, today=date(2026, 10, 20)).matches == []


def test_name_match_outside_window_is_silent(catalog: Catalog) -> None:
    r = catalog.match([Item("a", name="WinCo hoagie rolls", purchased_at=date(2020, 1, 1))])
    assert r.matches == []


def test_barcode_listed_but_different_suppresses_name(catalog: Catalog) -> None:
    # A WinCo hoagie roll with a different barcode is not the recalled product.
    r = catalog.match(
        [Item("a", code="036000291452", name="WinCo hoagie rolls", purchased_at=date(2026, 10, 1))]
    )
    assert r.matches == []


def test_name_match_with_lot_not_listed_is_silent(catalog: Catalog) -> None:
    r = catalog.match(
        [
            Item(
                "a",
                name="Gluten Free EAT GANGSTER pizza crust flat bread mix",
                lot="999999",
                purchased_at=date(2026, 9, 1),
            )
        ]
    )
    assert r.matches == []


def test_since_filters_old_recalls(catalog: Catalog) -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    assert catalog.match([Item("a", code="860007132216")], since=future).matches == []
    past = datetime.now(UTC) - timedelta(days=1)
    assert len(catalog.match([Item("a", code="860007132216")], since=past).matches) == 1


def test_ordering_puts_exact_first(catalog: Catalog) -> None:
    r = catalog.match(
        [
            Item("n", name="WinCo hoagie rolls", purchased_at=date(2026, 10, 1)),
            Item("e", code="860007132216", lot="JUL 22 27"),
        ]
    )
    assert [m.confidence for m in r.matches] == ["exact", "name"]


def test_holder_reloads_on_change(seeded: Session, settings: Settings) -> None:
    holder = CatalogHolder(settings)
    first = holder.get(seeded)
    assert holder.get(seeded) is first
    from boughtsafe.db import Recall, utcnow

    rec = seeded.get(Recall, "fda:H-0197-2027")
    assert rec is not None
    rec.updated_at = utcnow() + timedelta(seconds=5)
    seeded.commit()
    holder.invalidate()
    assert holder.get(seeded) is not first
