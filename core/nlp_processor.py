"""
VocabRecall – German NLP vocabulary pipeline
==============================================
Tries spaCy ``de_core_news_sm`` first.  If spaCy cannot load (e.g. on
Python 3.14 where Pydantic v1 is broken), the module transparently falls
back to a **regex + heuristic** extractor that still identifies German
nouns (capitalised words with article guessing), verbs and adjectives.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common German articles mapped by grammatical gender
# ---------------------------------------------------------------------------
GENDER_ARTICLE_MAP = {
    "Masc": "der",
    "Fem": "die",
    "Neut": "das",
}

# Words to ignore
_MIN_WORD_LEN = 3

# Common German stop-words (short list for the fallback path)
_STOP_WORDS: set[str] = {
    "ich", "du", "er", "sie", "es", "wir", "ihr", "und", "oder", "aber",
    "denn", "weil", "dass", "wenn", "als", "wie", "was", "wer", "den",
    "dem", "des", "ein", "eine", "einer", "einem", "einen", "eines",
    "der", "die", "das", "ist", "sind", "war", "hat", "haben", "wird",
    "kann", "muss", "soll", "nicht", "auch", "nur", "noch", "schon",
    "sehr", "von", "mit", "auf", "für", "aus", "bei", "nach", "vor",
    "über", "unter", "durch", "ohne", "gegen", "bis", "seit", "zum",
    "zur", "vom", "beim", "ins", "ans", "ums", "am", "im", "so",
    "da", "hier", "dort", "jetzt", "dann", "nun", "mal", "doch",
    "ja", "nein", "kein", "keine", "keiner", "keinem", "keinen",
    "sich", "mir", "dir", "ihm", "uns", "euch", "ihnen", "mein",
    "dein", "sein", "unser", "euer", "mehr", "viel", "alle",
    "diese", "dieser", "dieses", "diesem", "diesen", "jede",
    "jeder", "jedes", "jedem", "jeden", "welche", "welcher",
    "solche", "manche", "einige", "andere",
}

# Common German verb endings (infinitive)
_VERB_ENDINGS = ("en", "ern", "eln")

# Common German adjective endings
_ADJ_ENDINGS = (
    "ig", "lich", "isch", "bar", "sam", "haft", "los", "voll",
    "reich", "arm", "fest", "frei", "wert",
)


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------
@dataclass
class VocabEntry:
    word: str
    lemma: str
    article: str | None = None
    word_type: str = ""          # NOUN, VERB, ADJ
    example_sentence: str = ""

    def display_front(self) -> str:
        """Human-friendly front text for a flashcard."""
        if self.article:
            return f"{self.article} {self.word}"
        return self.word


# ===================================================================
#  PRIMARY PATH – spaCy
# ===================================================================
_nlp = None
_SPACY_AVAILABLE: bool | None = None  # None = not yet checked


def _try_load_spacy():
    """Attempt to load spaCy + model. Returns nlp object or None."""
    global _nlp, _SPACY_AVAILABLE
    if _SPACY_AVAILABLE is False:
        return None
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("de_core_news_sm")
        _SPACY_AVAILABLE = True
        log.info("spaCy loaded successfully")
        return _nlp
    except Exception as exc:
        _SPACY_AVAILABLE = False
        log.warning("spaCy unavailable (%s); using regex fallback.", exc)
        return None


def _extract_with_spacy(text: str, min_freq: int) -> List[VocabEntry]:
    """Extract vocabulary using spaCy NLP."""
    nlp = _nlp  # already loaded by caller
    max_len = nlp.max_length
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]

    freq: dict[str, int] = {}
    entries: dict[str, VocabEntry] = {}

    for chunk in chunks:
        doc = nlp(chunk)
        for token in doc:
            if token.is_punct or token.is_space or token.is_digit:
                continue
            if len(token.text) < _MIN_WORD_LEN or token.is_stop:
                continue

            pos = token.pos_
            if pos not in ("NOUN", "VERB", "ADJ"):
                continue

            lemma = token.lemma_
            key = f"{pos}:{lemma.lower()}"
            freq[key] = freq.get(key, 0) + 1

            if key not in entries:
                article = None
                if pos == "NOUN":
                    morph = token.morph.get("Gender")
                    if morph:
                        article = GENDER_ARTICLE_MAP.get(morph[0])

                sent_text = token.sent.text.strip() if token.sent else ""
                sent_text = re.sub(r"\s+", " ", sent_text)

                entries[key] = VocabEntry(
                    word=token.text if pos == "NOUN" else lemma,
                    lemma=lemma,
                    article=article,
                    word_type=pos,
                    example_sentence=sent_text[:300],
                )

    return [e for k, e in entries.items() if freq[k] >= min_freq]


# ===================================================================
#  FALLBACK PATH – regex + heuristics
# ===================================================================

# Regex: sequences of word-chars including German umlauts / ß
_WORD_RE = re.compile(r"\b([A-ZÄÖÜa-zäöüß]{3,})\b")
# Sentence splitter (rough)
_SENT_RE = re.compile(r"[^.!?]*[.!?]")


def _extract_with_regex(text: str, min_freq: int) -> List[VocabEntry]:
    """Heuristic German vocabulary extraction without spaCy."""
    words = _WORD_RE.findall(text)
    sentences = _SENT_RE.findall(text)

    # Build a quick sentence lookup for example sentences
    def _find_sentence(word: str) -> str:
        for s in sentences:
            if word in s:
                return re.sub(r"\s+", " ", s.strip())[:300]
        return ""

    freq: dict[str, int] = {}
    entries: dict[str, VocabEntry] = {}

    for word in words:
        low = word.lower()
        if low in _STOP_WORDS:
            continue

        # Classify by heuristics
        if word[0].isupper() and not _is_sentence_start(text, word):
            # German nouns are capitalised
            pos = "NOUN"
        elif low.endswith(_VERB_ENDINGS) and word[0].islower():
            pos = "VERB"
        elif low.endswith(_ADJ_ENDINGS) and word[0].islower():
            pos = "ADJ"
        elif word[0].islower():
            # Treat remaining lowercase long words as potential verbs/adj
            # but only if they look "German enough"
            if len(word) >= 5:
                pos = "VERB"  # best guess
            else:
                continue
        else:
            continue

        key = f"{pos}:{low}"
        freq[key] = freq.get(key, 0) + 1

        if key not in entries:
            entries[key] = VocabEntry(
                word=word,
                lemma=low,
                article=None,  # can't determine without NLP
                word_type=pos,
                example_sentence=_find_sentence(word),
            )

    return [e for k, e in entries.items() if freq[k] >= min_freq]


def _is_sentence_start(text: str, word: str) -> bool:
    """Rough check: is *word* always at the start of a sentence?"""
    pattern = re.compile(r"(?:^|[.!?]\s+)" + re.escape(word))
    all_occurrences = len(re.findall(re.escape(word), text))
    sentence_starts = len(pattern.findall(text))
    # If >80 % of occurrences are sentence-initial, likely not a noun
    return all_occurrences > 0 and sentence_starts / all_occurrences > 0.8


# ===================================================================
#  PUBLIC API
# ===================================================================

def extract_vocabulary(text: str, *, min_freq: int = 1) -> List[VocabEntry]:
    """Analyse *text* and return a deduplicated list of German vocabulary.

    Automatically uses spaCy when available, otherwise falls back to a
    regex-based heuristic extractor.

    Parameters
    ----------
    text : str
        Raw German text (from a PDF or TXT file).
    min_freq : int
        Minimum number of occurrences for a word to be included.

    Returns
    -------
    list[VocabEntry]
        Sorted by word type (NOUN → VERB → ADJ) then alphabetically.
    """
    nlp = _try_load_spacy()

    if nlp is not None:
        results = _extract_with_spacy(text, min_freq)
        log.info("Extracted %d entries via spaCy", len(results))
    else:
        results = _extract_with_regex(text, min_freq)
        log.info("Extracted %d entries via regex fallback", len(results))

    # Sort: NOUN first, then VERB, then ADJ; alphabetically within each group
    type_order = {"NOUN": 0, "VERB": 1, "ADJ": 2}
    results.sort(key=lambda e: (type_order.get(e.word_type, 9), e.lemma.lower()))

    return results
