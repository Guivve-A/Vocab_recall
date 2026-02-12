"""
VocabRecall – Study Session View  (v7)
=======================================
• Dual mode: ON = due cards only (SM-2), OFF = ALL cards (cramming)
• Visual-history undo works in both modes, DB rollback only in tracked mode
• Counters in a single container for clean hide/show
• Cross-fade animation via window alpha (zero glitches)
"""

from __future__ import annotations

import logging
import math
import os
import random
import subprocess
import tempfile
import threading
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List

import customtkinter as ctk

from db.database import get_session
from db.models import Card, ReviewLog
from core.srs_engine import get_due_cards, get_all_cards, record_review
from ui.widgets import Theme

log = logging.getLogger(__name__)


# ── History entry ────────────────────────────────────────────────────
@dataclass
class _HistoryEntry:
    """One answered card in the visual history stack."""
    card_id: int
    card_idx: int           # position in self._cards at the time
    was_tracked: bool       # was tracking ON when answered?
    quality: int
    # SM-2 snapshot (only meaningful when was_tracked)
    prev_reps: int = 0
    prev_ease: float = 2.5
    prev_interval: int = 0
    prev_next: datetime | None = None
    log_id: int | None = None   # ReviewLog.id (None if sandbox)


# ── DB helpers ───────────────────────────────────────────────────────
def _count_known(deck_id: int) -> int:
    now = datetime.now(timezone.utc)
    s = get_session()
    try:
        return s.query(Card).filter(
            Card.deck_id == deck_id,
            Card.repetitions >= 1,
            Card.next_review > now,
        ).count()
    finally:
        s.close()


# ── Audio ────────────────────────────────────────────────────────────
_AUDIO_DIR = os.path.join(tempfile.gettempdir(), "vocabrecall_audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)


def _play_audio(word: str) -> None:
    try:
        from gtts import gTTS
    except ImportError:
        log.warning("gTTS not installed – pip install gtts"); return
    try:
        safe = "".join(c if c.isalnum() else "_" for c in word)
        fp = os.path.join(_AUDIO_DIR, f"{safe}.mp3")
        if not os.path.exists(fp):
            gTTS(text=word, lang="de").save(fp)
        cmd = (
            f'powershell -WindowStyle Hidden -Command "'
            f"Add-Type -AssemblyName presentationCore;"
            f"$p=New-Object System.Windows.Media.MediaPlayer;"
            f"$p.Open('{fp}');$p.Play();Start-Sleep -Seconds 3\""
        )
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log.warning("TTS failed: %s", e)


# ── Fade constants ───────────────────────────────────────────────────
_FADE_STEPS = 6
_FADE_MS    = 16
_ALPHA_MIN  = 0.82


# =====================================================================
#  StudySessionView
# =====================================================================
class StudySessionView(ctk.CTkToplevel):

    W, H = 780, 600

    BG       = "#0d0f14"
    HDR      = "#13151c"
    CARD     = "#181b25"
    CARD_BD  = "#262a3a"
    FTR      = "#13151c"
    CPROG    = "#f0a050"
    CKNOWN   = "#3ddba9"
    CWRONG   = "#3a2030"
    CWRONGH  = "#5a2535"
    CRIGHT   = "#1a3530"
    CRIGH_H  = "#1a5040"
    COFF     = "#1a1c28"
    CMUT     = "#5b5f78"
    CTXT     = "#e2e4f0"
    CACC     = "#7c6ff5"

    def __init__(self, master, deck_id: int,
                 on_close: Callable[[], None] | None = None, **kw):
        super().__init__(master, **kw)
        self.title("Study Session — VocabRecall")
        self.geometry(f"{self.W}x{self.H}")
        self.minsize(640, 480)
        self.configure(fg_color=self.BG)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._deck_id  = deck_id
        self._on_close = on_close
        self._cards: List[Card] = []
        self._idx = 0
        self._track = True          # ON = SM-2 mode, OFF = cram all
        self._showing_back = False
        self._anim = False
        self._history: List[_HistoryEntry] = []   # visual history (always works)
        self._done = False
        self._shuffled = False

        self._known  = _count_known(deck_id)
        self._s_known = 0

        self._load_due()
        self._prog = len(self._cards)

        self.bind("<space>", lambda _: self._flip())
        self.bind("<Right>", lambda _: self.mark_known())
        self.bind("<Left>",  lambda _: self.mark_unknown())

        self._face_front: ctk.CTkFrame | None = None
        self._face_back:  ctk.CTkFrame | None = None

        if not self._cards:
            self._build_empty()
        else:
            self._build_ui()
            self._load_card()

    # ── data loading ─────────────────────────────────────────────────
    def _load_due(self):
        """Load only due cards (SM-2 mode)."""
        s = get_session()
        try:
            self._cards = get_due_cards(s, self._deck_id, limit=200)
        finally:
            s.close()
        random.shuffle(self._cards)
        self._idx = 0

    def _load_all(self):
        """Load ALL cards in the deck (cram/review mode)."""
        s = get_session()
        try:
            self._cards = get_all_cards(s, self._deck_id)
        finally:
            s.close()
        random.shuffle(self._cards)
        self._idx = 0

    # ── empty state ──────────────────────────────────────────────────
    def _build_empty(self):
        f = ctk.CTkFrame(self, fg_color="transparent"); f.pack(expand=True)
        ctk.CTkLabel(f, text="✅  No hay tarjetas pendientes",
                     font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=22,
                                      weight="bold"),
                     text_color=self.CKNOWN).pack(pady=(0, 12))
        ctk.CTkLabel(f,
                     text=f"Ya conoces {self._known} tarjetas.\n¡Buen trabajo!",
                     font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14),
                     text_color=self.CMUT, justify="center").pack(pady=(0, 24))
        ctk.CTkButton(f, text="Cerrar", command=self._close,
                      fg_color=self.CACC, hover_color="#6958d9",
                      width=120, height=38, corner_radius=8,
                      font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14,
                                       weight="bold")).pack()

    # ══════════════════════════════════════════════════════════════════
    #  UI LAYOUT
    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Header (grid layout — immune to reorder bugs) ─────────
        hdr = ctk.CTkFrame(self, fg_color=self.HDR, corner_radius=0, height=56)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)   # center col expands

        # Col 0 — counter container (hide/show as ONE unit)
        self._counters_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        self._counters_frame.grid(row=0, column=0, sticky="w", padx=0, pady=0)

        lf = ctk.CTkFrame(self._counters_frame, fg_color="transparent")
        lf.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(lf, text="🔄",
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(lf, text="En progreso:",
                     font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                     text_color=self.CMUT).pack(side="left", padx=(0, 6))
        self._lp = ctk.CTkLabel(
            lf, text=str(self._prog),
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=self.CPROG)
        self._lp.pack(side="left")

        rf = ctk.CTkFrame(self._counters_frame, fg_color="transparent")
        rf.pack(side="left", padx=(32, 24), pady=12)
        ctk.CTkLabel(rf, text="✅",
                     font=ctk.CTkFont(size=16)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(rf, text="Conocida:",
                     font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                     text_color=self.CMUT).pack(side="left", padx=(0, 6))
        self._lk = ctk.CTkLabel(
            rf, text=str(self._known),
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=self.CKNOWN)
        self._lk.pack(side="left")

        # Col 0 — sandbox label (same cell, initially hidden)
        self._sandbox_lbl = ctk.CTkLabel(
            hdr, text="📖  Modo Repaso — sin seguimiento",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13, weight="bold"),
            text_color=self.CMUT)
        self._sandbox_lbl.grid(row=0, column=0, sticky="w", padx=24, pady=12)
        self._sandbox_lbl.grid_remove()  # hidden until switch OFF

        # Col 1 — center card counter label
        self._lc = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
            text_color=self.CMUT)
        self._lc.grid(row=0, column=1, sticky="")

        # ── Card host ─────────────────────────────────────────────────
        self._card_host = ctk.CTkFrame(self, fg_color="transparent")
        self._card_host.pack(fill="both", expand=True, padx=40, pady=(20, 12))
        self._card_host.grid_rowconfigure(0, weight=1)
        self._card_host.grid_columnconfigure(0, weight=1)

        # ── Footer ────────────────────────────────────────────────────
        ftr = ctk.CTkFrame(self, fg_color=self.FTR, corner_radius=0, height=84)
        ftr.pack(fill="x", side="bottom"); ftr.pack_propagate(False)

        sf = ctk.CTkFrame(ftr, fg_color="transparent")
        sf.pack(side="left", padx=20, pady=16)
        self._sw = ctk.CTkSwitch(
            sf, text="Seguir progreso",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
            text_color=self.CMUT,
            progress_color=self.CACC, button_color=self.CACC,
            fg_color="#2a2d40", command=self._toggle_mode)
        self._sw.select(); self._sw.pack()

        uf = ctk.CTkFrame(ftr, fg_color="transparent")
        uf.pack(side="right", padx=20, pady=16)
        self._bsh = ctk.CTkButton(
            uf, text="🔀", width=44, height=44,
            fg_color="#1e2030", hover_color="#2a2d40",
            corner_radius=22, font=ctk.CTkFont(size=18),
            command=self._shuffle)
        self._bsh.pack(side="right", padx=(8, 0))
        self._bun = ctk.CTkButton(
            uf, text="↩", width=44, height=44,
            fg_color="#1e2030", hover_color="#2a2d40",
            corner_radius=22, font=ctk.CTkFont(size=18),
            command=self._go_back, state="disabled")
        self._bun.pack(side="right")

        cb = ctk.CTkFrame(ftr, fg_color="transparent")
        cb.pack(expand=True, pady=10)
        self._bx = ctk.CTkButton(
            cb, text="✗", width=64, height=64, corner_radius=32,
            fg_color=self.CWRONG, hover_color=self.CWRONGH,
            text_color="#f06070",
            font=ctk.CTkFont(size=28, weight="bold"),
            command=self.mark_unknown)
        self._bx.pack(side="left", padx=20)
        self._bo = ctk.CTkButton(
            cb, text="✓", width=64, height=64, corner_radius=32,
            fg_color=self.CRIGHT, hover_color=self.CRIGH_H,
            text_color=self.CKNOWN,
            font=ctk.CTkFont(size=28, weight="bold"),
            command=self.mark_known)
        self._bo.pack(side="left", padx=20)

    # ══════════════════════════════════════════════════════════════════
    #  FACE BUILDERS
    # ══════════════════════════════════════════════════════════════════
    def _build_faces(self):
        if self._face_front:
            self._face_front.destroy()
        if self._face_back:
            self._face_back.destroy()

        card = self._cards[self._idx]
        word = f"{card.article} {card.front}" if card.article else card.front
        trans = card.back or "—"

        # ── FRONT ─────────────────────────────────────────────────────
        ff = ctk.CTkFrame(self._card_host, fg_color=self.CARD,
                          corner_radius=20, border_width=1,
                          border_color=self.CARD_BD)
        ff.grid(row=0, column=0, sticky="nsew")
        ff.pack_propagate(False)
        ff.bind("<Button-1>", lambda _: self._flip())

        if card.word_type:
            b = ctk.CTkLabel(ff, text=f"  {card.word_type}  ",
                             font=ctk.CTkFont(family=Theme.FONT_FAMILY,
                                              size=11, weight="bold"),
                             text_color="#fff", fg_color=self.CACC,
                             corner_radius=10, width=70, height=22)
            b.pack(pady=(28, 0))
            b.bind("<Button-1>", lambda _: self._flip())

        wl = ctk.CTkLabel(ff, text=word,
                          font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=40,
                                           weight="bold"),
                          text_color=self.CTXT, wraplength=500)
        wl.pack(expand=True)
        wl.bind("<Button-1>", lambda _: self._flip())

        ctk.CTkButton(ff, text="🔊  Escuchar", width=130, height=36,
                      fg_color="#1e2030", hover_color="#262a3a",
                      text_color=self.CMUT, corner_radius=8,
                      font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                      command=self._tts).pack(pady=(0, 8))

        fh = ctk.CTkLabel(ff, text="Clic o [Espacio] para voltear",
                          font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
                          text_color="#3a3d50")
        fh.pack(pady=(0, 20))
        fh.bind("<Button-1>", lambda _: self._flip())
        self._face_front = ff

        # ── BACK ──────────────────────────────────────────────────────
        bf = ctk.CTkFrame(self._card_host, fg_color=self.CARD,
                          corner_radius=20, border_width=1,
                          border_color=self.CARD_BD)
        bf.grid(row=0, column=0, sticky="nsew")
        bf.pack_propagate(False)
        bf.bind("<Button-1>", lambda _: self._flip())

        sm = ctk.CTkLabel(bf, text=word,
                          font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=16),
                          text_color=self.CMUT)
        sm.pack(pady=(24, 4))
        sm.bind("<Button-1>", lambda _: self._flip())

        tr = ctk.CTkLabel(bf, text=trans,
                          font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=34,
                                           weight="bold"),
                          text_color=self.CKNOWN, wraplength=500)
        tr.pack(expand=True)
        tr.bind("<Button-1>", lambda _: self._flip())

        ex = card.example_sentence or ""
        if ex:
            el = ctk.CTkLabel(bf, text=f"« {ex} »",
                              font=ctk.CTkFont(family=Theme.FONT_FAMILY,
                                               size=13),
                              text_color=self.CMUT, wraplength=480,
                              justify="center")
            el.pack(pady=(0, 8))
            el.bind("<Button-1>", lambda _: self._flip())

        bh = ctk.CTkLabel(bf, text="Clic para volver al anverso",
                          font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
                          text_color="#3a3d50")
        bh.pack(pady=(0, 20))
        bh.bind("<Button-1>", lambda _: self._flip())
        self._face_back = bf

    # ══════════════════════════════════════════════════════════════════
    #  CARD DISPLAY
    # ══════════════════════════════════════════════════════════════════
    def _load_card(self):
        if self._idx >= len(self._cards):
            self._finish(); return

        self._showing_back = False
        self._done = False
        self._build_faces()
        self._face_front.tkraise()
        self._lc.configure(
            text=f"Tarjeta {self._idx + 1} de {len(self._cards)}")

    # ══════════════════════════════════════════════════════════════════
    #  FLIP ANIMATION  (cross-fade via window alpha)
    # ══════════════════════════════════════════════════════════════════
    def _flip(self):
        if self._anim or self._done:
            return
        self._anim = True
        self._fade_dim(0)

    def _fade_dim(self, step: int):
        if step > _FADE_STEPS:
            self._do_swap()
            self._fade_bright(0)
            return
        t = step / _FADE_STEPS
        e = math.sin(t * math.pi / 2)
        alpha = 1.0 - (1.0 - _ALPHA_MIN) * e
        try: self.attributes("-alpha", alpha)
        except tk.TclError: pass
        self.after(_FADE_MS, self._fade_dim, step + 1)

    def _do_swap(self):
        if self._showing_back:
            self._showing_back = False
            self._face_front.tkraise()
        else:
            self._showing_back = True
            self._face_back.tkraise()

    def _fade_bright(self, step: int):
        if step > _FADE_STEPS:
            try: self.attributes("-alpha", 1.0)
            except tk.TclError: pass
            self._anim = False
            return
        t = step / _FADE_STEPS
        e = math.sin(t * math.pi / 2)
        alpha = _ALPHA_MIN + (1.0 - _ALPHA_MIN) * e
        try: self.attributes("-alpha", alpha)
        except tk.TclError: pass
        self.after(_FADE_MS, self._fade_bright, step + 1)

    # ══════════════════════════════════════════════════════════════════
    #  ACTIONS
    # ══════════════════════════════════════════════════════════════════
    def mark_known(self):
        if self._done or self._anim or self._idx >= len(self._cards):
            return
        self._answer(quality=4)

    def mark_unknown(self):
        if self._done or self._anim or self._idx >= len(self._cards):
            return
        self._answer(quality=1)

    def _answer(self, quality: int):
        """Record answer to visual history; persist to DB only if tracking."""
        card = self._cards[self._idx]
        entry = _HistoryEntry(
            card_id=card.id,
            card_idx=self._idx,
            was_tracked=self._track,
            quality=quality,
            prev_reps=card.repetitions,
            prev_ease=card.easiness,
            prev_interval=card.interval,
            prev_next=card.next_review,
        )

        if self._track:
            # Persist to DB
            s = get_session()
            try:
                m = s.merge(card)
                record_review(s, m, quality)
                last = (s.query(ReviewLog).filter(ReviewLog.card_id == card.id)
                         .order_by(ReviewLog.id.desc()).first())
                entry.log_id = last.id if last else None
                card.repetitions = m.repetitions
                card.easiness    = m.easiness
                card.interval    = m.interval
                card.next_review = m.next_review
            finally:
                s.close()

            if quality >= 3:
                self._known += 1
                self._s_known += 1
                self._prog = max(0, self._prog - 1)
            self._upd()

        self._history.append(entry)
        self._bun.configure(state="normal")
        self._idx += 1
        self._load_card()

    # ── Go Back (always works) ────────────────────────────────────────
    def _go_back(self):
        """Navigate to previous card. DB rollback only if it was tracked."""
        if not self._history:
            return

        entry = self._history.pop()

        # If this card was answered in tracked mode → rollback DB
        if entry.was_tracked and entry.log_id is not None:
            s = get_session()
            try:
                cd = s.get(Card, entry.card_id)
                if cd:
                    cd.repetitions = entry.prev_reps
                    cd.easiness    = entry.prev_ease
                    cd.interval    = entry.prev_interval
                    cd.next_review = entry.prev_next
                rl = s.get(ReviewLog, entry.log_id)
                if rl:
                    s.delete(rl)
                s.commit()
            finally:
                s.close()

            # Revert local card object too
            for c in self._cards:
                if c.id == entry.card_id:
                    c.repetitions = entry.prev_reps
                    c.easiness    = entry.prev_ease
                    c.interval    = entry.prev_interval
                    c.next_review = entry.prev_next
                    break

            # Revert counters
            if entry.quality >= 3:
                self._known  = max(0, self._known - 1)
                self._s_known = max(0, self._s_known - 1)
                self._prog += 1
            self._upd()

        # Navigate back visually
        self._idx = entry.card_idx
        self._done = False
        if hasattr(self, "_summ_frame"):
            self._summ_frame.destroy()
        self._load_card()

        if not self._history:
            self._bun.configure(state="disabled")

    # ── Shuffle toggle ────────────────────────────────────────────────
    def _shuffle(self):
        if self._done:
            return
        self._shuffled = not self._shuffled
        if self._shuffled:
            random.shuffle(self._cards)
            self._idx = 0
            self._bsh.configure(fg_color=self.CACC, hover_color="#6958d9")
            self._load_card()
        else:
            self._bsh.configure(fg_color="#1e2030", hover_color="#2a2d40")

    # ── Mode toggle (the big switch) ──────────────────────────────────
    def _toggle_mode(self):
        """Switch ON = SM-2 due cards, OFF = ALL cards (cram)."""
        self._track = bool(self._sw.get())

        if self._track:
            # Show counters, hide sandbox label
            self._sandbox_lbl.grid_remove()
            self._counters_frame.grid()          # restores saved row/col/sticky
            self._upd()
            # Reload due cards only
            self._load_due()
        else:
            # Hide counters, show sandbox label
            self._counters_frame.grid_remove()
            self._sandbox_lbl.grid()             # restores saved row/col/sticky
            # Reload ALL cards
            self._load_all()

        self._prog = len(self._cards)
        self._history.clear()
        self._bun.configure(state="disabled")
        self._shuffled = False
        self._bsh.configure(fg_color="#1e2030", hover_color="#2a2d40")

        if not self._cards:
            # Clear card area
            if self._face_front: self._face_front.destroy()
            if self._face_back:  self._face_back.destroy()
            self._face_front = None
            self._face_back = None
            self._done = True
            self._lc.configure(text="Sin tarjetas")
        else:
            self._done = False
            self._load_card()

    # ── helpers ───────────────────────────────────────────────────────
    def _upd(self):
        self._lp.configure(text=str(self._prog))
        self._lk.configure(text=str(self._known))

    def _tts(self):
        if self._idx >= len(self._cards): return
        c = self._cards[self._idx]
        w = f"{c.article} {c.front}" if c.article else c.front
        threading.Thread(target=_play_audio, args=(w,), daemon=True).start()

    # ══════════════════════════════════════════════════════════════════
    #  SESSION END
    # ══════════════════════════════════════════════════════════════════
    def _finish(self):
        self._done = True
        if self._face_front:
            self._face_front.destroy(); self._face_front = None
        if self._face_back:
            self._face_back.destroy(); self._face_back = None

        self._summ_frame = ctk.CTkFrame(self._card_host, fg_color="transparent")
        self._summ_frame.grid(row=0, column=0, sticky="nsew")
        inn = ctk.CTkFrame(self._summ_frame, fg_color="transparent")
        inn.pack(expand=True)

        tot = len(self._cards)
        pct = round(self._s_known / tot * 100) if tot else 0

        ctk.CTkLabel(inn, text="🎉",
                     font=ctk.CTkFont(size=48)).pack(pady=(0, 8))
        ctk.CTkLabel(inn, text="¡Sesión completada!",
                     font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=26,
                                      weight="bold"),
                     text_color=self.CKNOWN).pack(pady=(0, 20))

        st = ctk.CTkFrame(inn, fg_color=self.CARD, corner_radius=16)
        st.pack(padx=40, pady=(0, 24))
        for lb, v, cl in [
            ("Conocidas",       str(self._s_known),        self.CKNOWN),
            ("En progreso",     str(tot - self._s_known),  self.CPROG),
            ("Precisión",       f"{pct}%",                 self.CACC),
            ("Total histórico", str(self._known),          self.CTXT),
        ]:
            col = ctk.CTkFrame(st, fg_color="transparent")
            col.pack(side="left", padx=24, pady=20)
            ctk.CTkLabel(col, text=lb.upper(),
                         font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11,
                                          weight="bold"),
                         text_color=self.CMUT).pack()
            ctk.CTkLabel(col, text=v,
                         font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=32,
                                          weight="bold"),
                         text_color=cl).pack(pady=(4, 0))

        ctk.CTkButton(inn, text="Cerrar sesión", command=self._close,
                      fg_color=self.CACC, hover_color="#6958d9",
                      width=160, height=44, corner_radius=10,
                      font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15,
                                       weight="bold")).pack()

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()
