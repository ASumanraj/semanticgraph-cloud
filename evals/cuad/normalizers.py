"""Normalizers for CUAD evaluation value categories (T-227 Measurement design correction).

Provides deterministic normalization for:
1. Governing Law (jurisdictions): lower-cased jurisdiction name without 'State of', etc.
2. Dates (Agreement Date, Effective Date, Expiration Date): parsed to 'YYYY-MM-DD' calendar date.
3. Parties: case, punctuation, parenthetical aliases, and corporate suffixes removed.
"""

from __future__ import annotations

import re


def normalize_jurisdiction(text: str | None) -> str:
    """Normalizes governing law jurisdiction by lower-casing and removing prefixes like 'State of'.

    Examples:
    - 'State of Texas' -> 'texas'
    - 'the State of Delaware' -> 'delaware'
    - 'Commonwealth of Massachusetts' -> 'massachusetts'
    - 'laws of the State of California' -> 'california'
    - 'Nevada' -> 'nevada'
    - 'England and Wales' -> 'england and wales'
    """
    if not text:
        return ""

    t = text.lower().strip()

    # Common legal boilerplate prefixes
    prefixes = [
        "governed by and construed in accordance with the laws of the state of",
        "governed by and construed in accordance with the laws of",
        "governed by the laws of the state of",
        "governed by the laws of the commonwealth of",
        "governed by the laws of",
        "in accordance with the laws of the state of",
        "in accordance with the laws of",
        "laws of the state of",
        "laws of the commonwealth of",
        "internal laws of the state of",
        "laws of",
        "the state of",
        "the commonwealth of",
        "state of",
        "commonwealth of",
    ]
    for p in prefixes:
        if t.startswith(p):
            t = t[len(p) :].strip()
            break

    # Strip clauses after comma, such as ', usa' or ', without regard to conflict of laws'
    t = re.split(r",\s*(?:without\s+regard|excluding|usa\b|u\.s\.a\b)", t)[0].strip()

    # Remove all punctuation
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_date(text: str | None) -> str | None:
    """Parses various date representations into 'YYYY-MM-DD' calendar date format.

    Handles:
    - '11/30/17' -> '2017-11-30'
    - '5/8/14' -> '2014-05-08'
    - '2000-10-30' -> '2000-10-30'
    - 'November 30, 2017' -> '2017-11-30'
    - '30th day of November, 2017' -> '2017-11-30'
    - '8th day of May 2014' -> '2014-05-08'
    - 'May 8, 2014' -> '2014-05-08'
    """
    if not text:
        return None

    cleaned = text.strip()
    # Normalize '30th day of November, 2017' or '8th day of May 2014'
    day_of_match = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+)[,\s]+(\d{2,4})",
        cleaned,
        re.IGNORECASE,
    )
    if day_of_match:
        day, month_str, year = day_of_match.groups()
        cleaned = f"{month_str} {day} {year}"
    else:
        # Strip ordinal suffixes: 1st -> 1, 2nd -> 2, 3rd -> 3, 4th -> 4
        cleaned = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", cleaned)

    # Try dateutil parser first
    try:
        from dateutil import parser

        dt = parser.parse(cleaned)
        year = dt.year
        if year < 100:
            year = 2000 + year if year < 50 else 1900 + year
            dt = dt.replace(year=year)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Fallback to regex for M/D/YY or M/D/YYYY
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", cleaned)
    if m:
        month, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr = 2000 + yr if yr < 50 else 1900 + yr
        try:
            return f"{yr:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    # Fallback to YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if m_iso:
        yr, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            return f"{yr:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    return None


# Corporate suffixes to remove from party names (case-insensitive)
CORPORATE_SUFFIXES: set[str] = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "companies",
    "plc",
    "llp",
    "lp",
    "sa",
    "bv",
    "nv",
    "gmbh",
    "pc",
    "pty",
}


def normalize_party_name(text: str | None) -> str:
    """Normalizes a company or party name by:
    - Removing parenthetical aliases like ('Company'), (“ConvergTV”), (formerly known as ...)
    - Removing 'd/b/a ...' or 'dba ...' clauses
    - Removing corporate suffixes (inc, llc, ltd, corp, co, company, etc.)
    - Lowercasing and stripping punctuation.

    Examples:
    - 'Birch First Global Investments Inc. ("Company")' -> 'birch first global investments'
    - 'Mount Knowledge Holdings Inc. ("Marketing Affiliate", "MA")' -> 'mount knowledge holdings'
    - 'WOMEN.COM NETWORKS, INC.' -> 'women com networks'
    - 'EDIETS.COM, INC.' -> 'ediets com'
    - 'Arnold Schwarzenegger (“Endorser”)' -> 'arnold schwarzenegger'
    """
    if not text:
        return ""

    t = text.strip()

    # Remove parenthetical aliases like ("Company") or (“Party”) or (formerly known as ...)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\[.*?\]", " ", t)

    # Remove d/b/a or dba clauses
    t = re.sub(r"\b(?:d/?b/?a|doing business as)\b.*", " ", t, flags=re.IGNORECASE)

    # Collapse acronyms with periods: 'S.A.' -> 'SA', 'B.V.' -> 'BV', 'N.V.' -> 'NV'
    t = re.sub(r"\b([a-zA-Z])\.([a-zA-Z])\.?", r"\1\2", t)

    # Remove punctuation except whitespace
    t = re.sub(r"[^\w\s]", " ", t)
    t = t.lower()

    tokens = t.split()
    # Strip trailing corporate suffixes (handling combinations like 'pty ltd', 'co inc')
    while tokens:
        last = tokens[-1]
        if last in CORPORATE_SUFFIXES:
            tokens.pop()
        else:
            break

    return " ".join(tokens).strip()
