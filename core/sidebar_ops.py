"""
VocabRecall – Sidebar DB Operations
=====================================
Pure database helpers for folder / deck management.
No UI code — called by the Sidebar widget.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy.orm import Session

from db.database import get_session
from db.models import Folder, Deck, Card, ReviewLog

log = logging.getLogger(__name__)


# ── Rename ────────────────────────────────────────────────────────────

def rename_folder(folder_id: int, new_name: str) -> bool:
    """Rename a folder. Returns True on success."""
    s = get_session()
    try:
        f = s.get(Folder, folder_id)
        if not f:
            return False
        f.name = new_name.strip()
        s.commit()
        log.info("Renamed folder %d → %r", folder_id, f.name)
        return True
    finally:
        s.close()


def rename_deck(deck_id: int, new_name: str) -> bool:
    """Rename a deck. Returns True on success."""
    s = get_session()
    try:
        d = s.get(Deck, deck_id)
        if not d:
            return False
        d.name = new_name.strip()
        s.commit()
        log.info("Renamed deck %d → %r", deck_id, d.name)
        return True
    finally:
        s.close()


# ── Move ──────────────────────────────────────────────────────────────

def move_deck(deck_id: int, target_folder_id: int) -> bool:
    """Move a deck to a different folder. Returns True on success."""
    s = get_session()
    try:
        d = s.get(Deck, deck_id)
        tf = s.get(Folder, target_folder_id)
        if not d or not tf:
            return False
        d.folder_id = target_folder_id
        s.commit()
        log.info("Moved deck %d → folder %d", deck_id, target_folder_id)
        return True
    finally:
        s.close()


# ── Delete ────────────────────────────────────────────────────────────

def delete_folder(folder_id: int) -> bool:
    """Delete a folder and everything inside (cascade)."""
    s = get_session()
    try:
        f = s.get(Folder, folder_id)
        if not f:
            return False
        s.delete(f)
        s.commit()
        log.info("Deleted folder %d", folder_id)
        return True
    finally:
        s.close()


def delete_deck(deck_id: int) -> bool:
    """Delete a deck and all its cards + logs (cascade)."""
    s = get_session()
    try:
        d = s.get(Deck, deck_id)
        if not d:
            return False
        s.delete(d)
        s.commit()
        log.info("Deleted deck %d", deck_id)
        return True
    finally:
        s.close()


# ── Reset progress ───────────────────────────────────────────────────

def reset_deck_progress(deck_id: int) -> int:
    """Reset all SM-2 fields for every card in a deck.
    Deletes all ReviewLogs. Returns number of cards reset."""
    now = datetime.now(timezone.utc)
    s = get_session()
    try:
        cards = s.query(Card).filter(Card.deck_id == deck_id).all()
        for c in cards:
            c.repetitions = 0
            c.easiness = 2.5
            c.interval = 0
            c.next_review = now
        # Delete all review logs for these cards
        card_ids = [c.id for c in cards]
        if card_ids:
            s.query(ReviewLog).filter(ReviewLog.card_id.in_(card_ids)).delete(
                synchronize_session="fetch"
            )
        s.commit()
        log.info("Reset progress for deck %d (%d cards)", deck_id, len(cards))
        return len(cards)
    finally:
        s.close()


# ── Export ────────────────────────────────────────────────────────────

def export_deck_csv(deck_id: int, filepath: str) -> int:
    """Export a deck's cards to CSV. Returns number of cards exported."""
    s = get_session()
    try:
        cards = (
            s.query(Card)
            .filter(Card.deck_id == deck_id)
            .order_by(Card.id)
            .all()
        )
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["front", "back", "article", "word_type", "example_sentence"])
            for c in cards:
                w.writerow([c.front, c.back or "", c.article or "",
                            c.word_type or "", c.example_sentence or ""])
        log.info("Exported %d cards from deck %d → %s", len(cards), deck_id, filepath)
        return len(cards)
    finally:
        s.close()


# ── Query helpers ─────────────────────────────────────────────────────

def get_all_folders(exclude_id: int | None = None) -> List[Tuple[int, str]]:
    """Return [(id, name), ...] for all folders, optionally excluding one."""
    s = get_session()
    try:
        q = s.query(Folder.id, Folder.name).order_by(Folder.name)
        if exclude_id is not None:
            q = q.filter(Folder.id != exclude_id)
        return q.all()
    finally:
        s.close()
