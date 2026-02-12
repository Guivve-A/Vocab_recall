"""
VocabRecall – Import dialog
=============================
Modal-style workflow:
  pick a file → detect format → extract/parse → preview → confirm → create cards.

Supports TWO document modes:
  • **Structured** – lines like ``das Haus ; the house`` → front/back directly.
  • **Free text** – raw German prose → NLP/regex extraction.
"""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog
from typing import Callable, List

import customtkinter as ctk

from db.database import get_session
from db.models import Folder, Deck, Card
from core.extractor import extract_text, is_structured, parse_structured_vocab
from core.nlp_processor import extract_vocabulary, VocabEntry
from ui.widgets import Theme, AccentButton, DangerButton, GhostButton, Separator


class ImportDialog(ctk.CTkToplevel):
    """Top-level modal window for importing files and previewing vocabulary."""

    WIDTH = 860
    HEIGHT = 660

    def __init__(
        self,
        master,
        folder_id: int | None = None,
        on_complete: Callable[[], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)

        self.title("Import File — VocabRecall")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_DARK)
        self.grab_set()

        self._folder_id = folder_id
        self._on_complete = on_complete

        # Results — one of these will be populated
        self._vocab: List[VocabEntry] = []
        self._pairs: List[tuple[str, str]] = []
        self._is_structured = False

        self._filepath: str | None = None

        self._build_step_pick()

    # ==================================================================
    # Step 1 – Pick file
    # ==================================================================

    def _build_step_pick(self) -> None:
        self._clear()

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True)

        ctk.CTkLabel(
            wrap, text="📥  Import a file",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            wrap,
            text="Select a PDF or TXT file.\n"
                 "Structured files (front ; back) are imported directly.\n"
                 "Free-text files are analysed to extract vocabulary.",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14),
            text_color=Theme.TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(0, 12))

        # Format hint
        hint_frame = ctk.CTkFrame(wrap, fg_color=Theme.BG_CARD, corner_radius=12)
        hint_frame.pack(padx=24, pady=(0, 20), fill="x")

        ctk.CTkLabel(
            hint_frame,
            text="📋  Supported structured formats:",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13, weight="bold"),
            text_color=Theme.ACCENT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        examples = (
            "das Haus ; the house\n"
            "der Hund | the dog\n"
            "die Katze \\t the cat   (tab-separated)\n"
            "groß - big / tall"
        )
        ctk.CTkLabel(
            hint_frame,
            text=examples,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=Theme.TEXT_SECONDARY,
            justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        AccentButton(wrap, text="Choose File…", command=self._pick_file, width=180).pack()

    def _pick_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select a document",
            filetypes=[
                ("Supported files", "*.pdf *.txt *.text *.md *.csv *.tsv"),
                ("PDF", "*.pdf"),
                ("Text / CSV", "*.txt *.text *.md *.csv *.tsv"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._filepath = path
        self._build_step_processing()

    # ==================================================================
    # Step 2 – Processing
    # ==================================================================

    def _build_step_processing(self) -> None:
        self._clear()

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True)

        ctk.CTkLabel(
            wrap, text="⏳  Processing…",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=20, weight="bold"),
            text_color=Theme.ACCENT,
        ).pack(pady=(0, 12))

        self._status_label = ctk.CTkLabel(
            wrap, text=f"Reading {Path(self._filepath).name}",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
            text_color=Theme.TEXT_SECONDARY,
        )
        self._status_label.pack()

        self._pbar = ctk.CTkProgressBar(
            wrap, fg_color=Theme.BG_CARD, progress_color=Theme.ACCENT,
            width=400, height=8, corner_radius=4,
            mode="indeterminate",
        )
        self._pbar.pack(pady=(16, 0))
        self._pbar.start()

        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self) -> None:
        try:
            text = extract_text(self._filepath)

            if is_structured(text):
                self.after(0, lambda: self._status_label.configure(
                    text="Structured format detected — parsing pairs…"
                ))
                self._pairs = parse_structured_vocab(text)
                self._is_structured = True
            else:
                self.after(0, lambda: self._status_label.configure(
                    text="Free text detected — running NLP analysis…"
                ))
                self._vocab = extract_vocabulary(text)
                self._is_structured = False

            self.after(0, self._build_step_preview)
        except Exception as exc:
            self.after(0, lambda: self._show_error(str(exc)))

    # ==================================================================
    # Step 3 – Preview
    # ==================================================================

    def _build_step_preview(self) -> None:
        self._clear()

        count = len(self._pairs) if self._is_structured else len(self._vocab)
        mode_label = "structured pairs" if self._is_structured else "vocabulary items"

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 0))

        ctk.CTkLabel(
            hdr,
            text=f"Found {count} {mode_label}",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        AccentButton(
            hdr, text="✔  Import All",
            command=self._confirm_import, width=140,
        ).pack(side="right", padx=(8, 0))
        DangerButton(
            hdr, text="Cancel",
            command=self.destroy, width=90,
        ).pack(side="right")

        # Mode badge
        badge = ctk.CTkLabel(
            hdr,
            text=f"  {'📋 Structured' if self._is_structured else '🧠 NLP'}  ",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
            fg_color=Theme.ACCENT if self._is_structured else Theme.WARNING,
            corner_radius=6,
            text_color="#ffffff",
        )
        badge.pack(side="left", padx=(12, 0))

        Separator(self).pack(fill="x", padx=24, pady=(12, 0))

        # Table
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=8)

        if self._is_structured:
            self._preview_structured(scroll)
        else:
            self._preview_nlp(scroll)

    def _preview_structured(self, parent) -> None:
        """Table: Front | Back"""
        hdr = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=8)
        hdr.pack(fill="x", pady=(0, 6))
        for col, w in [("Front (Deutsch)", 350), ("Back (Translation)", 350)]:
            ctk.CTkLabel(
                hdr, text=col, width=w,
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
                text_color=Theme.TEXT_MUTED,
            ).pack(side="left", padx=8, pady=6)

        for front, back in self._pairs:
            row = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=8)
            row.pack(fill="x", pady=1)
            for text, w in [(front, 350), (back, 350)]:
                ctk.CTkLabel(
                    row, text=text, width=w,
                    font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                    text_color=Theme.TEXT_PRIMARY, anchor="w",
                ).pack(side="left", padx=8, pady=5)

    def _preview_nlp(self, parent) -> None:
        """Table: Word | Type | Article | Example"""
        hdr = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=8)
        hdr.pack(fill="x", pady=(0, 6))
        for col, w in [("Word", 220), ("Type", 70), ("Article", 60), ("Example", 360)]:
            ctk.CTkLabel(
                hdr, text=col, width=w,
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
                text_color=Theme.TEXT_MUTED,
            ).pack(side="left", padx=6, pady=6)

        for entry in self._vocab:
            row = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=8)
            row.pack(fill="x", pady=1)
            example = entry.example_sentence
            if len(example) > 80:
                example = example[:80] + "…"
            for text, w in [
                (entry.display_front(), 220),
                (entry.word_type, 70),
                (entry.article or "—", 60),
                (example or "—", 360),
            ]:
                ctk.CTkLabel(
                    row, text=text, width=w,
                    font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
                    text_color=Theme.TEXT_PRIMARY, anchor="w",
                ).pack(side="left", padx=6, pady=5)

    # ==================================================================
    # Step 4 – Confirm & create cards
    # ==================================================================

    def _confirm_import(self) -> None:
        session = get_session()
        try:
            folder_id = self._folder_id
            if folder_id is None:
                folder = Folder(name="Imported")
                session.add(folder)
                session.flush()
                folder_id = folder.id

            filename = Path(self._filepath).stem
            deck = Deck(
                name=filename,
                folder_id=folder_id,
                source_filename=Path(self._filepath).name,
            )
            session.add(deck)
            session.flush()

            if self._is_structured:
                for front, back in self._pairs:
                    # Try to extract article from front (e.g. "das Haus" → article="das", front="Haus")
                    article, clean_front = _split_article(front)
                    card = Card(
                        deck_id=deck.id,
                        front=clean_front,
                        back=back,
                        article=article,
                        word_type="NOUN" if article else "",
                    )
                    session.add(card)
            else:
                for entry in self._vocab:
                    card = Card(
                        deck_id=deck.id,
                        front=entry.word,
                        back=entry.lemma if entry.lemma != entry.word else "",
                        article=entry.article,
                        word_type=entry.word_type,
                        example_sentence=entry.example_sentence,
                    )
                    session.add(card)

            session.commit()
        finally:
            session.close()

        if self._on_complete:
            self._on_complete()
        self.destroy()

    # ==================================================================
    # Helpers
    # ==================================================================

    def _show_error(self, msg: str) -> None:
        self._clear()
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True)
        ctk.CTkLabel(
            wrap, text="❌  Error",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=20, weight="bold"),
            text_color=Theme.DANGER,
        ).pack(pady=(0, 8))
        ctk.CTkLabel(
            wrap, text=msg, wraplength=600,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
            text_color=Theme.TEXT_SECONDARY,
        ).pack(pady=(0, 20))
        GhostButton(wrap, text="← Try again", command=self._build_step_pick).pack()

    def _clear(self) -> None:
        for w in self.winfo_children():
            w.destroy()


# ──────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────

_ARTICLES = {"der", "die", "das", "ein", "eine"}


def _split_article(text: str) -> tuple[str | None, str]:
    """Split ``'das Haus'`` → ``('das', 'Haus')``."""
    parts = text.split(None, 1)
    if len(parts) == 2 and parts[0].lower() in _ARTICLES:
        return parts[0].lower(), parts[1]
    return None, text
