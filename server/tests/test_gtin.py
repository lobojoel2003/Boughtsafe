import pytest

from boughtsafe import gtin


@pytest.mark.parametrize(
    "code",
    ["036000291452", "4006381333931", "96385074", "00012345600012", "860007132216"],
)
def test_valid_check_digits(code: str) -> None:
    assert gtin.is_valid(code)


@pytest.mark.parametrize("code", ["036000291453", "4006381333932", "123", "abcdefabcdef"])
def test_invalid_codes(code: str) -> None:
    assert not gtin.is_valid(code)


@pytest.mark.parametrize(
    ("upce", "upca"),
    [
        ("04252614", "042100005264"),  # last digit 4
        ("01234558", "012345000058"),  # last digit 5-9
        ("01234133", "012300000413"),  # last digit 3
        ("01234505", "012000003455"),  # last digit 0-2
        ("01234500", None),  # wrong check digit
        ("21234505", None),  # number system must be 0 or 1
    ],
)
def test_upce_expansion(upce: str, upca: str | None) -> None:
    assert gtin.upce_to_upca(upce) == upca


def test_normalize_pads_to_gtin14() -> None:
    assert gtin.normalize("0 36000 29145 2") == "00036000291452"
    assert gtin.normalize("4006381333931") == "04006381333931"
    assert gtin.normalize("04252614", hint="upc_e") == "00042100005264"
    assert gtin.normalize("96385074", hint="ean_8") == "00000096385074"
    assert gtin.normalize("036000291453") is None


def test_all_representations_compare_equal() -> None:
    a = gtin.normalize("042100005264")
    b = gtin.normalize("04252614")
    c = gtin.normalize("0042100005264")
    d = gtin.normalize("00042100005264")
    assert a == b == c == d


def test_lenient_repairs() -> None:
    # 11 digits: check digit dropped (Gearharts 8oz in a real FDA notice)
    assert "00898111002064" in gtin.gtin_candidates("8 98111 00206", lenient=True)
    # 10 digits: number system and check digit dropped
    assert gtin.gtin_candidates("9787014483", lenient=True) == ["00097870144835"]
    # 12 digits printed by receipt printers: zero-padded body without check digit
    printed = "007874235188"
    assert not gtin.is_valid(printed)
    body = printed[1:]
    assert gtin.gtin_candidates(printed, lenient=True) == [
        gtin.to_gtin14(body + str(gtin.check_digit(body)))
    ]
    # strict mode never guesses
    assert gtin.gtin_candidates("8 98111 00206") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Raw milk cheddar ... UPC: 860007132216; Family Farmstead", ["00860007132216"]),
        ("GELATO 16FL OZ UPC 4 056489 722458 DISTRIBUTED BY LIDL", ["04056489722458"]),
        ("Hoagie Rolls, 6 rolls/bag. UPC 0 70552 00649 2. Distributed", ["00070552006492"]),
        (
            "4oz UPC 8 98111 00205 7; Net Wt. 8oz UPC 8 98111 00206; Gearharts",
            ["00898111002057", "00898111002064"],
        ),
        (
            "16 OZ: UPC 675643050967 32 OZ: UPC 675643050974",
            ["00675643050967", "00675643050974"],
        ),
        ("U.P.C. 0 12345 67890 5 and 0 12345 67891 2", ["00012345678905", "00012345678912"]),
        ("UPC codes: 0 70552 00649 2 12 ct per case", ["00070552006492"]),
        ("Horchata Drink Mix; packaged in 1lb, 5lb, 50lb units. No UPC", []),
        ("Lot: 202526227 Exp. Date: 10-13-28", []),
    ],
)
def test_extract_from_real_notice_text(text: str, expected: list[str]) -> None:
    assert gtin.extract_gtins(text) == expected


def test_display_formats() -> None:
    assert gtin.display("00070552006492") == "0 70552 00649 2"
    assert gtin.display("04056489722458") == "4 056489 722458"
    assert gtin.display("10012345678902") == "10012345678902"


def test_bucket_is_stable_and_short() -> None:
    b = gtin.bucket("00860007132216")
    assert b == gtin.bucket("00860007132216")
    assert len(b) == 4
    assert int(b, 16) >= 0
    # Must stay in sync with web/src/lib/buckets.ts (tested there with the same vector).
    assert b == "2675"
