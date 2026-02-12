"""
VocabRecall – Flashcard study screen
======================================
Full-screen-ish review experience with card flip animation, quality rating
buttons, and a real-time progress bar.
"""

from __future__ import annotations

import random
from typing import Callable, List

import customtkinter as ctk

from db.database import get_session
from db.models import Card
from core.srs_engine import get_due_cards, record_review
from ui.widgets import Theme, AccentButton, GhostButton, Separator


class FlashcardView(ctk.CTkFrame):
    """Interactive study session for a single deck."""

    QUALITY_LABELS = [
        ("Again", Theme.DANGER),
        ("Hard", Theme.WARNING),
        ("Okay", Theme.TEXT_SECONDARY),
        ("Good", Theme.ACCENT),
        ("Easy", Theme.SUCCESS),
    ]

    def __init__(
        self,
        master,
        on_finish: Callable[[], None] | None = None,
        **kw,
    ):
        kw.setdefault("fg_color", Theme.BG_DARK)
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)

        self._on_finish = on_finish
        self._cards: List[Card] = []
        self._index = 0
        self._flipped = False
        self._correct = 0
        self._incorrect = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start_session(self, deck_id: int) -> None:
        """Load due cards and begin the review loop."""
        session = get_session()
        try:
            self._cards = get_due_cards(session, deck_id)
        finally:
            session.close()

        if not self._cards:
            self._show_empty()
            return

        random.shuffle(self._cards)
        self._index = 0
        self._flipped = False
        self._correct = 0
        self._incorrect = 0
        self._build_ui()
        self._show_card()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        for w in self.winfo_children():
            w.destroy()

        # ── Top bar ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(20, 0))

        GhostButton(top, text="✕  Exit", command=self._exit_session).pack(side="left")

        self._progress_label = ctk.CTkLabel(
            top, text="",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
            text_color=Theme.TEXT_SECONDARY,
        )
        self._progress_label.pack(side="right")

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(
            self, fg_color=Theme.BG_CARD, progress_color=Theme.ACCENT,
            corner_radius=6, height=6,
        )
        self._progress_bar.pack(fill="x", padx=28, pady=(12, 0))
        self._progress_bar.set(0)

        # ── Card area ──
        self._card_frame = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=20,
            border_width=1, border_color=Theme.BORDER,
        )
        self._card_frame.pack(padx=60, pady=(30, 16), fill="both", expand=True)
        self._card_frame.bind("<Button-1>", lambda _: self._flip())

        self._word_label = ctk.CTkLabel(
            self._card_frame, text="",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=36, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
            wraplength=600,
        )
        self._word_label.pack(expand=True, pady=(40, 0))
        self._word_label.bind("<Button-1>", lambda _: self._flip())

        self._detail_label = ctk.CTkLabel(
            self._card_frame, text="",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=16),
            text_color=Theme.TEXT_SECONDARY,
            wraplength=600,
        )
        self._detail_label.pack(expand=True, pady=(0, 12))
        self._detail_label.bind("<Button-1>", lambda _: self._flip())

        self._hint_label = ctk.CTkLabel(
            self._card_frame, text="Click to reveal",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
            text_color=Theme.TEXT_MUTED,
        )
        self._hint_label.pack(pady=(0, 30))
        self._hint_label.bind("<Button-1>", lambda _: self._flip())

        # ── Rating buttons ──
        self._rating_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rating_frame.pack(fill="x", padx=60, pady=(0, 28))

        for qi, (label, color) in enumerate(self.QUALITY_LABELS, start=1):
            btn = ctk.CTkButton(
                self._rating_frame,
                text=label,
                width=100, height=44,
                fg_color=Theme.BG_CARD,
                hover_color=color,
                text_color=Theme.TEXT_PRIMARY,
                border_width=1,
                border_color=Theme.BORDER,
                corner_radius=10,
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14, weight="bold"),
                command=lambda q=qi: self._rate(q),
            )
            btn.pack(side="left", padx=6, expand=True, fill="x")

        self._hide_rating()

    # ------------------------------------------------------------------
    # Card display
    # ------------------------------------------------------------------

    def _show_card(self) -> None:
        card = self._cards[self._index]
        front = f"{card.article} {card.front}" if card.article else card.front
        self._word_label.configure(text=front)
        self._detail_label.configure(text=card.word_type or "")
        self._hint_label.configure(text="Click to reveal")
        self._flipped = False
        self._hide_rating()
        self._update_progress()

    def _flip(self) -> None:
        if self._flipped:
            return
        self._flipped = True
        card = self._cards[self._index]
        back = card.back if card.back else "—"
        self._word_label.configure(text=back)
        self._detail_label.configure(
            text=card.example_sentence or "",
        )
        self._hint_label.configure(text="Rate your recall ↓")
        self._show_rating()

    # ------------------------------------------------------------------
    # Rating
    # ------------------------------------------------------------------

    def _rate(self, quality: int) -> None:
        card = self._cards[self._index]
        session = get_session()
        try:
            merged = session.merge(card)
            record_review(session, merged, quality)
        finally:
            session.close()

        if quality >= 3:
            self._correct += 1
        else:
            self._incorrect += 1

        self._index += 1
        if self._index >= len(self._cards):
            self._show_summary()
        else:
            self._show_card()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_rating(self) -> None:
        self._rating_frame.pack(fill="x", padx=60, pady=(0, 28))

    def _hide_rating(self) -> None:
        self._rating_frame.pack_forget()

    def _update_progress(self) -> None:
        total = len(self._cards)
        done = self._index
        self._progress_bar.set(done / total if total else 0)
        self._progress_label.configure(text=f"{done} / {total}")

    def _show_summary(self) -> None:
        for w in self.winfo_children():
            w.destroy()

        total = self._correct + self._incorrect
        pct = round(self._correct / total * 100) if total else 0

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True)

        ctk.CTkLabel(
            wrap, text="🎉  Session Complete!",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=28, weight="bold"),
            text_color=Theme.SUCCESS,
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            wrap,
            text=f"✅ {self._correct}  correct    ❌ {self._incorrect}  incorrect    📊 {pct}%",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=16),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(pady=(0, 28))

        AccentButton(wrap, text="Done", command=self._exit_session, width=140).pack()

    def _show_empty(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self, text="✅  No cards due — you're all caught up!",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=18),
            text_color=Theme.SUCCESS,
        ).pack(expand=True)
        GhostButton(self, text="← Back", command=self._exit_session).pack(pady=16)

    def _exit_session(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        if self._on_finish:
            self._on_finish()
