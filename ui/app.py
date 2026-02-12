"""
VocabRecall – Main application window
=======================================
Ties together the sidebar, deck viewer, study session, and import
dialog into a single CustomTkinter application.
"""

from __future__ import annotations

import customtkinter as ctk

from db.database import init_db
from ui.widgets import Theme
from ui.sidebar import Sidebar
from ui.deck_view import DeckView
from ui.study_session import StudySessionView
from ui.import_dialog import ImportDialog


class VocabRecallApp(ctk.CTk):
    """Root application window."""

    APP_TITLE = "VocabRecall — German Vocabulary Trainer"
    WIDTH = 1100
    HEIGHT = 720

    def __init__(self) -> None:
        super().__init__()

        # ── Window setup ──
        self.title(self.APP_TITLE)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(900, 560)
        self.configure(fg_color=Theme.BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Ensure database tables exist
        init_db()

        # ── Layout: sidebar | content ──
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self._sidebar = Sidebar(
            self,
            on_deck_select=self._on_deck_select,
            on_import=self._on_import,
        )
        self._sidebar.grid(row=0, column=0, sticky="ns")

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color=Theme.BG_DARK, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Deck view (default visible)
        self._deck_view = DeckView(self._content, on_study=self._on_study)
        self._deck_view.grid(row=0, column=0, sticky="nsew")

        self._current_deck_id: int | None = None
        self._study_window: StudySessionView | None = None

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_deck_select(self, deck_id: int) -> None:
        """User clicked a deck in the sidebar."""
        self._current_deck_id = deck_id
        self._deck_view.show_deck(deck_id)

    def _on_study(self, deck_id: int) -> None:
        """Open the study session as a separate Toplevel window."""
        # Prevent multiple study windows
        if self._study_window is not None and self._study_window.winfo_exists():
            self._study_window.focus()
            return

        self._current_deck_id = deck_id
        self._study_window = StudySessionView(
            self,
            deck_id=deck_id,
            on_close=self._on_study_finish,
        )

    def _on_study_finish(self) -> None:
        """Refresh the deck view after the study session closes."""
        self._study_window = None
        if self._current_deck_id:
            self._deck_view.show_deck(self._current_deck_id)
        self._sidebar.refresh()

    def _on_import(self, folder_id: int | None) -> None:
        """Open the import dialog."""
        ImportDialog(
            self,
            folder_id=folder_id,
            on_complete=self._after_import,
        )

    def _after_import(self) -> None:
        """Refresh sidebar & deck view after a successful import."""
        self._sidebar.refresh()
        if self._current_deck_id:
            self._deck_view.show_deck(self._current_deck_id)

