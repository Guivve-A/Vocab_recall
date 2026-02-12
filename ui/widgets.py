"""
VocabRecall – Reusable CustomTkinter widgets
=============================================
Shared UI primitives used across multiple views.
"""

from __future__ import annotations

import customtkinter as ctk


# ---------------------------------------------------------------------------
# Colours / design tokens
# ---------------------------------------------------------------------------
class Theme:
    """Centralised colour palette – dark-mode first."""
    BG_DARK       = "#0f1117"
    BG_SIDEBAR    = "#161822"
    BG_CARD       = "#1e2030"
    BG_CARD_HOVER = "#272a3d"
    ACCENT        = "#7c6ff5"     # purple accent
    ACCENT_HOVER  = "#6958d9"
    SUCCESS       = "#43d9a2"
    DANGER        = "#f55a6a"
    WARNING       = "#f5c842"
    TEXT_PRIMARY   = "#e2e4f0"
    TEXT_SECONDARY = "#8b8fa8"
    TEXT_MUTED     = "#5b5f78"
    BORDER         = "#2a2d40"
    FONT_FAMILY    = "Segoe UI"
    FONT_MONO      = "Consolas"


# ---------------------------------------------------------------------------
# Styled button
# ---------------------------------------------------------------------------
class AccentButton(ctk.CTkButton):
    """A consistently-styled accent button."""

    def __init__(self, master, text: str = "", command=None, **kw):
        kw.setdefault("fg_color", Theme.ACCENT)
        kw.setdefault("hover_color", Theme.ACCENT_HOVER)
        kw.setdefault("text_color", "#ffffff")
        kw.setdefault("corner_radius", 8)
        kw.setdefault("font", ctk.CTkFont(family=Theme.FONT_FAMILY, size=14, weight="bold"))
        kw.setdefault("height", 36)
        super().__init__(master, text=text, command=command, **kw)


class DangerButton(ctk.CTkButton):
    """Red-toned button for destructive actions."""

    def __init__(self, master, text: str = "", command=None, **kw):
        kw.setdefault("fg_color", Theme.DANGER)
        kw.setdefault("hover_color", "#d44454")
        kw.setdefault("text_color", "#ffffff")
        kw.setdefault("corner_radius", 8)
        kw.setdefault("font", ctk.CTkFont(family=Theme.FONT_FAMILY, size=13))
        kw.setdefault("height", 32)
        super().__init__(master, text=text, command=command, **kw)


class GhostButton(ctk.CTkButton):
    """Transparent button (sidebar items, etc.)."""

    def __init__(self, master, text: str = "", command=None, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", Theme.BG_CARD_HOVER)
        kw.setdefault("text_color", Theme.TEXT_PRIMARY)
        kw.setdefault("anchor", "w")
        kw.setdefault("corner_radius", 6)
        kw.setdefault("font", ctk.CTkFont(family=Theme.FONT_FAMILY, size=13))
        kw.setdefault("height", 32)
        super().__init__(master, text=text, command=command, **kw)


# ---------------------------------------------------------------------------
# Stat card (mini dashboard widget)
# ---------------------------------------------------------------------------
class StatCard(ctk.CTkFrame):
    """Small rounded card that shows a label + large number."""

    def __init__(self, master, label: str = "", value: str = "0", color: str = Theme.ACCENT, **kw):
        kw.setdefault("fg_color", Theme.BG_CARD)
        kw.setdefault("corner_radius", 12)
        super().__init__(master, **kw)

        self._label = ctk.CTkLabel(
            self, text=label.upper(),
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
            text_color=Theme.TEXT_MUTED,
        )
        self._label.pack(padx=16, pady=(14, 0), anchor="w")

        self._value = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=28, weight="bold"),
            text_color=color,
        )
        self._value.pack(padx=16, pady=(2, 14), anchor="w")

    def set_value(self, v: str) -> None:
        self._value.configure(text=v)


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------
class Separator(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", Theme.BORDER)
        kw.setdefault("height", 1)
        super().__init__(master, **kw)
