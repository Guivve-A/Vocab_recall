"""
VocabRecall – Text extraction from PDF and TXT files
=====================================================
Supports two document modes:

1. **Structured vocabulary** – lines with a separator (`;`, `TAB`, or `|`)
   mapping *front* → *back* (German → translation).
2. **Free text** – prose in German; words are extracted via NLP / regex.

The module auto-detects which mode to use.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import List, Tuple

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Raw text readers
# ──────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(filepath: str | Path) -> str:
    """Extract all text from a PDF using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"PDF not found: {filepath}")

    text_parts: list[str] = []
    with fitz.open(str(filepath)) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)

    full_text = "\n".join(text_parts)
    log.info("Extracted %d chars from %s (%d pages)", len(full_text), filepath.name, len(text_parts))
    return full_text


def extract_text_from_txt(filepath: str | Path) -> str:
    """Read a plain-text file with automatic encoding detection."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"TXT file not found: {filepath}")

    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = filepath.read_text(encoding=encoding)
            log.info("Read %d chars from %s (encoding=%s)", len(text), filepath.name, encoding)
            return text
        except (UnicodeDecodeError, ValueError):
            continue

    raise UnicodeDecodeError(
        "all", b"", 0, 1, f"Could not decode {filepath.name} with any supported encoding"
    )


def extract_text(filepath: str | Path) -> str:
    """Dispatch to the right reader based on file extension."""
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    if ext in (".txt", ".text", ".md", ".csv", ".tsv"):
        return extract_text_from_txt(filepath)
    raise ValueError(f"Unsupported file type: {ext}")


# ──────────────────────────────────────────────────────────────────────
# Structured vocabulary detection & parsing
# ──────────────────────────────────────────────────────────────────────

# Separators we recognise, in priority order
_SEPARATORS = ["\t", ";", "|", " - ", " – ", " — "]

# Regex for lines that look like  "der Hund ; the dog"
_STRUCTURED_LINE_RE = re.compile(
    r"^[^;|\t\n]{2,}(?:[;|\t]| [-–—] )[^;|\t\n]{2,}$"
)


def is_structured(text: str) -> bool:
    """Return True if the text looks like a structured vocabulary list.

    Heuristic: if ≥ 40 % of non-empty lines match the pattern
    ``front <sep> back``, we treat it as structured.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    matched = sum(1 for l in lines if _STRUCTURED_LINE_RE.match(l))
    ratio = matched / len(lines)
    log.debug("Structured-line ratio: %.1f%% (%d/%d)", ratio * 100, matched, len(lines))
    return ratio >= 0.4


def _detect_separator(text: str) -> str:
    """Pick the most frequently occurring separator."""
    best_sep = ";"
    best_count = 0
    for sep in _SEPARATORS:
        count = text.count(sep)
        if count > best_count:
            best_count = count
            best_sep = sep
    return best_sep


def parse_structured_vocab(text: str) -> List[Tuple[str, str]]:
    """Parse a structured vocabulary file into (front, back) pairs.

    Accepted formats (auto-detected separator):

        das Haus ; the house
        der Hund | the dog
        die Katze   the cat          ← tab-separated
        groß - big / tall

    Lines starting with ``#`` are treated as comments.
    Empty lines and lines without a separator are skipped.

    Returns
    -------
    list of (front, back) tuples.
    """
    sep = _detect_separator(text)
    pairs: List[Tuple[str, str]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if sep not in line:
            continue

        parts = line.split(sep, maxsplit=1)
        if len(parts) != 2:
            continue

        front = parts[0].strip()
        back = parts[1].strip()

        if front and back:
            pairs.append((front, back))

    log.info("Parsed %d structured pairs (sep=%r)", len(pairs), sep)
    return pairs
