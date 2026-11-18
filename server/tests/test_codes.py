from datetime import date

import pytest

from boughtsafe import codes


@pytest.mark.parametrize(
    ("raw", "norm"),
    [
        ("Lot # 3B1-274", "3B1274"),
        ("LOT CODE: 26-254", "26254"),
        ("best by JUL 22 27", "JUL2227"),
        ("  batch 0042 ", "0042"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_code(raw: str | None, norm: str) -> None:
    assert codes.normalize_code(raw) == norm


def test_code_keys_join_split_tokens() -> None:
    keys = codes.code_keys("Sell By Oct / 12 3B1 274; Exp. date: 10-12-26")
    assert "3B1274" in keys
    assert "OCT" not in keys  # no digit
    assert "SELL" not in keys


@pytest.mark.parametrize(
    ("text", "all_codes", "specific"),
    [
        ("All lots", True, False),
        ("All product codes within expiry", True, False),
        ("all best by dates", True, False),
        ("none", False, False),
        ("", False, False),
        ("Lot: 14250", False, True),
        ("No lot code, Best By JUL 22 27", False, True),
    ],
)
def test_covers_all_and_specific(text: str, all_codes: bool, specific: bool) -> None:
    assert codes.covers_all_codes(text) is all_codes
    assert codes.has_specific_codes(text) is specific


def test_find_dates_many_formats() -> None:
    found = [d for _, _, d in codes.find_dates("7/27/2027, 2027-08-01, JUL 22 27, 3 Aug 2027")]
    assert found == [date(2027, 7, 27), date(2027, 8, 1), date(2027, 7, 22), date(2027, 8, 3)]


def test_date_range_in_notice() -> None:
    notice = codes.parse_notice_codes("BEST BY OCT 1 2026 to BEST BY OCT 21 2026")
    assert notice.ranges == [(date(2026, 10, 1), date(2026, 10, 21))]
    assert codes.compare_code(notice, "2026-10-10") == "matched"
    assert codes.compare_code(notice, "OCT 25 2026") == "not_listed"
    # a lot number can't be compared with best-by dates
    assert codes.compare_code(notice, "Lot 12345") == "unknown"


def test_lot_codes_in_notice() -> None:
    notice = codes.parse_notice_codes(
        "Lot 260327, Best by date 7-27-27 and 9-27-27 Lot 260803, Best by date 2-03-28"
    )
    assert codes.compare_code(notice, "260327") == "matched"
    assert codes.compare_code(notice, "lot 260803") == "matched"
    assert codes.compare_code(notice, "Best by 7/27/2027") == "matched"
    assert codes.compare_code(notice, "261111") == "not_listed"


def test_best_by_only_notice_and_lot_entry_is_unknown() -> None:
    notice = codes.parse_notice_codes("No lot code, Best By JUL 22 27")
    assert codes.compare_code(notice, "Jul 22 2027") == "matched"
    assert codes.compare_code(notice, "L1234") == "unknown"


def test_short_entries_are_unknown() -> None:
    notice = codes.parse_notice_codes("Lot 12")
    assert codes.compare_code(notice, "12") == "unknown"


def test_mentions_codes() -> None:
    assert codes.mentions_codes("with lot code 26300 and a use-by date of 12/15/2026")
    assert not codes.mentions_codes("2-lb. packages of chicken nuggets")
    assert not codes.mentions_codes("All best-by dates.")


@pytest.mark.parametrize(
    ("reason", "kind", "allergens"),
    [
        ("Potential contamination with E. coli (pathogenic non-O157 STEC).", "pathogen", []),
        ("Listeria monocytogenes", "pathogen", []),
        (
            "undeclared allergen ingredient (Sesame, Peanuts, Wheat)",
            "allergen",
            ["peanut", "wheat", "sesame"],
        ),
        ("Undeclared soy.", "allergen", ["soy"]),
        ("Foreign Object - Broken glass was found", "foreign", []),
        ("Elevated levels of lead", "chemical", []),
        ("Risk of serious injury from fire and burn hazards", "injury", []),
        ("Misbranding, Unreported Allergens", "allergen", []),
        ("Something unusual", "other", []),
    ],
)
def test_classify_hazard(reason: str, kind: str, allergens: list[str]) -> None:
    h = codes.classify_hazard(reason)
    assert h.kind == kind
    assert h.allergens == allergens
