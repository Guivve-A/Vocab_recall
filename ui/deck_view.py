"""
VocabRecall – Deck viewer (card table)
=======================================
Displays all cards in a selected deck in a scrollable list and provides
a "Study" button to launch the flashcard game.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from db.database import get_session
from db.models import Deck, Card
from core.srs_engine import deck_stats, get_all_cards
from ui.widgets import Theme, AccentButton, StatCard, Separator


class DeckView(ctk.CTkFrame):
    """Content panel that shows deck metadata, stats, and card list."""

    def __init__(
        self,
        master,
        on_study: Callable[[int], None] | None = None,
        **kw,
    ):
        kw.setdefault("fg_color", Theme.BG_DARK)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)

        self._on_study = on_study
        self._deck_id: int | None = None

        # ── Placeholder ──
        self._placeholder = ctk.CTkLabel(
            self,
            text="← Select a deck from the sidebar to view its cards",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15),
            text_color=Theme.TEXT_MUTED,
        )
        self._placeholder.pack(expand=True)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_deck(self, deck_id: int) -> None:
        """Populate the view with a specific deck's data."""
        self._deck_id = deck_id
        self._placeholder.pack_forget()
        for w in self.winfo_children():
            w.destroy()

        session = get_session()
        try:
            deck = session.get(Deck, deck_id)
            if not deck:
                return
            stats = deck_stats(session, deck_id)
            cards = get_all_cards(session, deck_id)
        finally:
            session.close()

        self._build_header(deck, stats)
        self._build_card_list(cards)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_header(self, deck: Deck, stats: dict) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 0))

        # Title row
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x")

        ctk.CTkLabel(
            title_row,
            text=f"🃏  {deck.name}",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        if stats["due"] > 0:
            AccentButton(
                title_row,
                text=f"▶  Study  ({stats['due']} due)",
                command=lambda: self._on_study(deck.id) if self._on_study else None,
                width=180,
            ).pack(side="right")
        else:
            ctk.CTkLabel(
                title_row,
                text="✅  All caught up!",
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14),
                text_color=Theme.SUCCESS,
            ).pack(side="right", padx=8)

        # Source file info
        if deck.source_filename:
            ctk.CTkLabel(
                header,
                text=f"Source: {deck.source_filename}",
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
                text_color=Theme.TEXT_MUTED,
            ).pack(anchor="w", pady=(4, 0))

        # Stat cards row
        stat_row = ctk.CTkFrame(header, fg_color="transparent")
        stat_row.pack(fill="x", pady=(16, 0))

        for label, value, color in [
            ("Total", str(stats["total"]), Theme.TEXT_PRIMARY),
            ("Due", str(stats["due"]), Theme.WARNING),
            ("Learning", str(stats["learning"]), Theme.ACCENT),
            ("Mastered", str(stats["mastered"]), Theme.SUCCESS),
        ]:
            sc = StatCard(stat_row, label=label, value=value, color=color)
            sc.pack(side="left", padx=(0, 12), fill="x", expand=True)

        Separator(self).pack(fill="x", padx=28, pady=(20, 0))

    def _build_card_list(self, cards: list[Card]) -> None:
        if not cards:
            ctk.CTkLabel(
                self,
                text="No cards yet. Import a file to generate vocabulary.",
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14),
                text_color=Theme.TEXT_MUTED,
            ).pack(pady=40)
            return

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=12)

        # Column headers
        hdr = ctk.CTkFrame(scroll, fg_color=Theme.BG_CARD, corner_radius=8, height=36)
        hdr.pack(fill="x", pady=(0, 6))
        for col, w in [("Front", 200), ("Back", 200), ("Type", 80), ("Reps", 60), ("EF", 60)]:
            ctk.CTkLabel(
                hdr, text=col, width=w,
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
                text_color=Theme.TEXT_MUTED,
            ).pack(side="left", padx=8, pady=6)

        for card in cards:
            row = ctk.CTkFrame(scroll, fg_color=Theme.BG_CARD, corner_radius=8, height=36)
            row.pack(fill="x", pady=2)

            front_text = f"{card.article} {card.front}" if card.article else card.front
            for text, w in [
                (front_text, 200),
                (card.back or "—", 200),
                (card.word_type or "", 80),
                (str(card.repetitions), 60),
                (f"{card.easiness:.2f}", 60),
            ]:
                ctk.CTkLabel(
                    row, text=text, width=w,
                    font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                    text_color=Theme.TEXT_PRIMARY,
                    anchor="w",
                ).pack(side="left", padx=8, pady=6)

    def clear(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self._placeholder = ctk.CTkLabel(
            self,
            text="← Select a deck from the sidebar to view its cards",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15),
            text_color=Theme.TEXT_MUTED,
        )
        self._placeholder.pack(expand=True)
