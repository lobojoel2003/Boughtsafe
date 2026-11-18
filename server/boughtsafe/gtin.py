"""GTIN (UPC/EAN) normalization.

Every barcode Boughtsafe sees is reduced to a canonical 14-digit GTIN so that a
UPC-A printed on a recall notice ("UPC 0 70552 00649 2"), an EAN-13 from a
European import ("4 056489 722458"), a UPC-E from a phone scan ("04252614") and
a GS1-128 case label all compare equal when they name the same product.

Two entry points:

* :func:`gtin_candidates` normalizes one code. Strict mode only accepts codes
  with a valid check digit. Lenient mode also repairs the damage that recall
  notices and receipts commonly do to barcodes (dropped check digits, dropped
  leading zeros) and may return several plausible readings.
* :func:`extract_gtins` pulls every barcode out of free text such as an openFDA
  ``product_description``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

GTIN_LENGTHS = (8, 12, 13, 14)
BUCKET_SALT = "boughtsafe/v1:"


def check_digit(body: str) -> int:
    """GS1 mod-10 check digit for ``body`` (all digits except the check digit)."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += (ord(ch) - 48) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def is_valid(digits: str) -> bool:
    """True when ``digits`` is a GTIN-8/12/13/14 with a correct check digit."""
    return (
        len(digits) in GTIN_LENGTHS
        and digits.isdigit()
        and check_digit(digits[:-1]) == ord(digits[-1]) - 48
    )


def to_gtin14(digits: str) -> str:
    return digits.zfill(14)


def upce_to_upca(code: str) -> str | None:
    """Expand an 8-digit UPC-E (number system + 6 digits + check) to UPC-A.

    Returns the 12-digit UPC-A, or ``None`` when ``code`` cannot be a UPC-E.
    """
    if len(code) != 8 or not code.isdigit() or code[0] not in "01":
        return None
    ns, d, check = code[0], code[1:7], code[7]
    last = d[5]
    if last in "012":
        body = d[0:2] + last + "0000" + d[2:5]
    elif last == "3":
        body = d[0:3] + "00000" + d[3:5]
    elif last == "4":
        body = d[0:4] + "00000" + d[4]
    else:
        body = d[0:5] + "0000" + last
    upca = ns + body + check
    return upca if is_valid(upca) else None


def digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def gtin_candidates(raw: str, *, hint: str | None = None, lenient: bool = False) -> list[str]:
    """Normalize ``raw`` to zero or more canonical GTIN-14 strings.

    ``hint`` is the symbology reported by a scanner (``upc_e``, ``ean_8`` ...),
    which resolves the UPC-E / EAN-8 ambiguity of 8-digit codes.
    ``lenient`` enables repairs for codes copied by hand into notices/receipts.
    """
    d = digits_only(raw)
    out: list[str] = []

    def add(code: str) -> None:
        g = to_gtin14(code)
        if g not in out and int(g) != 0:
            out.append(g)

    if not d or len(d) > 14:
        return out

    if len(d) == 8:
        upca = upce_to_upca(d)
        if hint in (None, "upc_e") and upca:
            add(upca)
        if hint in (None, "ean_8") and is_valid(d):
            add(d)
        return out

    if len(d) in (12, 13, 14) and is_valid(d):
        add(d)
        return out

    if not lenient:
        return out

    if len(d) == 11:
        # Either the leading number-system zero or the trailing check digit was dropped.
        if is_valid("0" + d):
            add("0" + d)
        add(d + str(check_digit(d)))
    elif len(d) == 10:
        # Number system and check digit both missing (common in CPSC notices).
        body = "0" + d
        add(body + str(check_digit(body)))
    elif len(d) == 12 and d.startswith("0"):
        # Receipts (e.g. Walmart) print a zero-padded UPC without its check digit.
        body = d[1:]
        add(body + str(check_digit(body)))
    elif len(d) == 13 and d.startswith("0"):
        body = d[1:]
        if is_valid(body):
            add(body)
    return out


def normalize(raw: str, *, hint: str | None = None) -> str | None:
    """Strictly normalize a single scanned/typed code, or ``None``."""
    c = gtin_candidates(raw, hint=hint)
    return c[0] if c else None


def display(gtin14: str) -> str:
    """Human formatting: UPC-A ``0 12345 67890 5``, EAN-13 ``4 006381 333931``."""
    if gtin14.startswith("00"):
        u = gtin14[2:]
        return f"{u[0]} {u[1:6]} {u[6:11]} {u[11]}"
    if gtin14.startswith("0"):
        e = gtin14[1:]
        return f"{e[0]} {e[1:7]} {e[7:13]}"
    return gtin14


def bucket(gtin14: str) -> str:
    """16-bit watch bucket used for privacy-preserving push alerts.

    A device registers buckets, never barcodes. Each bucket is shared by roughly
    1/65,536 of all GTINs, so the server cannot tell which product you own.
    The web client implements the identical function.
    """
    return hashlib.sha256((BUCKET_SALT + gtin14).encode()).hexdigest()[:4]


# --- extraction from free text ----------------------------------------------------

_KEYWORD = re.compile(
    r"(?<![A-Za-z])(?:U\.\s?P\.\s?C\.?|UPCs?|GTINs?|EANs?|bar\s*codes?)(?![A-Za-z])",
    re.IGNORECASE,
)
_LABEL = re.compile(
    r"(?:[\s:#\-\u2013'\u2019]|\(s\))*(?:codes?|numbers?|nos?\.?)?(?:[\s:#\-\u2013]|\(s\))*",
    re.IGNORECASE,
)
# A run of digits that may contain single spaces or dashes ("0 70552 00649 2").
_RUN = re.compile(r"\d(?:[ \u00a0\-\u2010-\u2013]?\d)*")
_GROUP_SEP = re.compile(r"[ \u00a0\-\u2010-\u2013]")
_LIST_SEP = re.compile(
    r"\s*(?:,|;|/|&|\band\b|\bor\b)?\s*"
    r"(?:\d+(?:\.\d+)?\s*(?:fl\.?\s*oz|oz|lbs?|g|kg|ml|l|ct|count|pk|pack)\b\.?\s*[:\-]?\s*)?"
    r"(?:(?:UPC|EAN|GTIN)s?\s*[:#]?\s*)?",
    re.IGNORECASE,
)
_STANDALONE = re.compile(r"(?<![\w.\-])(\d{12,14})(?![\w\-])")
_NO_UPC = re.compile(r"\bno\s+UPC\b", re.IGNORECASE)


def _codes_in_run(run: str) -> list[str]:
    """Split one digit run into barcode-sized codes.

    Notices often list several codes separated only by spaces, or follow a code
    with a pack count ("0 70552 00649 2 12 ct"), so a run is consumed group by
    group: first the longest prefix that is a valid GTIN, otherwise the longest
    prefix of a length lenient repair understands.
    """
    groups = [g for g in _GROUP_SEP.split(run) if g]
    codes: list[str] = []
    i = 0
    while i < len(groups):
        strict: tuple[int, str] | None = None
        loose: tuple[int, str] | None = None
        acc = ""
        for j in range(i, len(groups)):
            acc += groups[j]
            if len(acc) > 14:
                break
            if len(acc) in (12, 13, 14) and is_valid(acc):
                strict = (j, acc)
            elif len(acc) in (8, 10, 11, 12, 13):
                loose = (j, acc)
        pick = strict or loose
        if pick:
            codes.append(pick[1])
            i = pick[0] + 1
        else:
            i += 1
    return codes


def extract_gtins(text: str) -> list[str]:
    """Return canonical GTIN-14s found in free text, most explicit first."""
    if not text:
        return []
    found: list[str] = []

    def add_all(codes: Iterable[str]) -> None:
        for g in codes:
            if g not in found:
                found.append(g)

    for kw in _KEYWORD.finditer(text):
        label = _LABEL.match(text, kw.end())
        pos = label.end() if label else kw.end()
        while True:
            m = _RUN.match(text, pos)
            if not m:
                break
            for code in _codes_in_run(m.group(0)):
                add_all(gtin_candidates(code, lenient=True))
            pos = m.end()
            sep = _LIST_SEP.match(text, pos)
            if not sep or sep.end() == pos:
                break
            pos = sep.end()

    for m in _STANDALONE.finditer(text):
        add_all(gtin_candidates(m.group(1)))
    return found


def mentions_no_upc(text: str) -> bool:
    return bool(_NO_UPC.search(text or ""))
