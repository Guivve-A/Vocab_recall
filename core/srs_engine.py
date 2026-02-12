"""
VocabRecall – SM-2 Spaced Repetition Engine
=============================================
Implements the SuperMemo-2 algorithm and helpers to schedule & record
flashcard reviews.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy.orm import Session

from db.models import Card, ReviewLog

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SM-2 core algorithm
# ---------------------------------------------------------------------------

def calculate_sm2(
    quality: int,
    repetitions: int,
    easiness: float,
    interval: int,
) -> Tuple[int, float, int]:
    """Apply the SM-2 algorithm and return updated scheduling values.

    Parameters
    ----------
    quality : int
        User self-assessment grade (0 = total blackout … 5 = perfect).
    repetitions : int
        Current number of consecutive successful reviews.
    easiness : float
        Current easiness factor (EF) — minimum clamped to 1.3.
    interval : int
        Current inter-repetition interval in days.

    Returns
    -------
    (new_repetitions, new_easiness, new_interval)
    """
    if quality < 0 or quality > 5:
        raise ValueError(f"quality must be 0-5, got {quality}")

    # Failed review — reset
    if quality < 3:
        new_repetitions = 0
        new_interval = 1
    else:
        # Successful review
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * easiness)
        new_repetitions = repetitions + 1

    # Update easiness factor
    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    return new_repetitions, new_easiness, new_interval


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_due_cards(session: Session, deck_id: int, *, limit: int = 50) -> List[Card]:
    """Return cards from *deck_id* whose next_review is ≤ now.

    Results are ordered oldest-first so the most overdue cards come first.
    """
    now = datetime.now(timezone.utc)
    cards = (
        session.query(Card)
        .filter(Card.deck_id == deck_id, Card.next_review <= now)
        .order_by(Card.next_review.asc())
        .limit(limit)
        .all()
    )
    log.info("Found %d due cards for deck %d", len(cards), deck_id)
    return cards


def get_all_cards(session: Session, deck_id: int) -> List[Card]:
    """Return every card in a deck regardless of schedule."""
    return (
        session.query(Card)
        .filter(Card.deck_id == deck_id)
        .order_by(Card.id)
        .all()
    )


# ---------------------------------------------------------------------------
# Review recording
# ---------------------------------------------------------------------------

def record_review(session: Session, card: Card, quality: int) -> Card:
    """Score a card with *quality* (0-5), update its SM-2 fields, and persist.

    Also inserts a ``ReviewLog`` for historical tracking.
    """
    new_reps, new_ef, new_interval = calculate_sm2(
        quality, card.repetitions, card.easiness, card.interval
    )

    card.repetitions = new_reps
    card.easiness = new_ef
    card.interval = new_interval
    card.next_review = datetime.now(timezone.utc) + timedelta(days=new_interval)

    log_entry = ReviewLog(
        card_id=card.id,
        quality=quality,
        easiness_after=new_ef,
        interval_after=new_interval,
    )
    session.add(log_entry)
    session.commit()

    log.info(
        "Reviewed card %d (q=%d) → reps=%d ef=%.2f interval=%d next=%s",
        card.id, quality, new_reps, new_ef, new_interval, card.next_review,
    )
    return card


# ---------------------------------------------------------------------------
# Deck-level statistics
# ---------------------------------------------------------------------------

def deck_stats(session: Session, deck_id: int) -> dict:
    """Return quick stats for a deck: total, due, mastered counts."""
    now = datetime.now(timezone.utc)
    total = session.query(Card).filter(Card.deck_id == deck_id).count()
    due = (
        session.query(Card)
        .filter(Card.deck_id == deck_id, Card.next_review <= now)
        .count()
    )
    mastered = (
        session.query(Card)
        .filter(Card.deck_id == deck_id, Card.repetitions >= 5)
        .count()
    )
    return {"total": total, "due": due, "mastered": mastered, "learning": total - mastered}
