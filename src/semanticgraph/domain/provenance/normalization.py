"""
Normalization utilities for text and provenance spans.

Normalizations that shift character offsets (such as unicode normalization,
ligature decomposition, and line ending standardization) MUST be applied
to chunk text BEFORE character offsets are computed, ensuring that:
chunk.text[start_offset:end_offset] == quote
is an exact character-for-character equality after storage.
"""

from __future__ import annotations

import unicodedata


def normalize_for_provenance(text: str) -> str:
    """Normalize text deterministically before computing character offsets.

    Applies:
    1. Unicode NFKC normalization (decomposes ligatures like 'ﬁ' -> 'fi', 'ﬂ' -> 'fl').
    2. Line ending standardization (CRLF / CR -> LF).
    3. Non-breaking space standardization ('\\u00a0' -> ' ').
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization decomposes ligatures and compatibility forms
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Standardize line endings to LF
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Standardize non-breaking spaces
    normalized = normalized.replace("\u00a0", " ")

    return normalized
