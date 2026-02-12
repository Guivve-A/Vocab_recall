"""
VocabRecall – Sidebar  (v2 – context menus, drag & drop, smart import)
=======================================================================
Features:
  • Right-click context menus on folders and decks
  • Drag & drop decks between folders
  • Smart import (auto-targets selected folder or shows picker dialog)
  • Visual selection highlight
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

from db.database import get_session
from db.models import Folder, Deck
from core.sidebar_ops import (
    rename_folder, rename_deck, move_deck,
    delete_folder, delete_deck,
    reset_deck_progress, export_deck_csv, get_all_folders,
)
from ui.widgets import Theme, GhostButton, AccentButton, Separator


class Sidebar(ctk.CTkFrame):
    """Left-hand sidebar with folder/deck navigation."""

    def __init__(
        self,
        master,
        on_deck_select: Callable[[int], None] | None = None,
        on_import: Callable[[int | None], None] | None = None,
        **kw,
    ):
        kw.setdefault("fg_color", Theme.BG_SIDEBAR)
        kw.setdefault("corner_radius", 0)
        kw.setdefault("width", 280)
        super().__init__(master, **kw)

        self._on_deck_select = on_deck_select
        self._on_import = on_import
        self._selected_folder_id: int | None = None

        # Drag & drop state
        self._drag_deck_id: int | None = None
        self._drag_ghost: ctk.CTkLabel | None = None
        self._folder_rows: dict[int, ctk.CTkFrame] = {}   # folder_id → row widget

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(20, 6))
        ctk.CTkLabel(
            header, text="📂  VocabRecall",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=18, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        Separator(self).pack(fill="x", padx=16, pady=(6, 8))

        # ── Action buttons ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 4))

        AccentButton(btn_row, text="＋ Folder", command=self._create_folder,
                     width=110).pack(side="left", padx=4)
        AccentButton(btn_row, text="📥 Import", command=self._trigger_import,
                     width=110).pack(side="left", padx=4)

        Separator(self).pack(fill="x", padx=16, pady=(8, 4))

        # ── Scrollable tree ──
        self._tree_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        self._tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh()

    # ==================================================================
    #  PUBLIC
    # ==================================================================

    def refresh(self) -> None:
        """Rebuild the tree from the database."""
        for w in self._tree_frame.winfo_children():
            w.destroy()
        self._folder_rows.clear()

        session = get_session()
        try:
            roots = (
                session.query(Folder)
                .filter(Folder.parent_id.is_(None))
                .order_by(Folder.name)
                .all()
            )
            if not roots:
                ctk.CTkLabel(
                    self._tree_frame,
                    text="No folders yet.\nClick '＋ Folder' to start.",
                    text_color=Theme.TEXT_MUTED,
                    font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                    justify="center",
                ).pack(pady=40)
                return

            for folder in roots:
                self._render_folder(folder, indent=0)
        finally:
            session.close()

    # ==================================================================
    #  RENDER
    # ==================================================================

    def _render_folder(self, folder: Folder, indent: int) -> None:
        row = ctk.CTkFrame(self._tree_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)
        self._folder_rows[folder.id] = row

        prefix = "  " * indent + "📁 "
        is_sel = (self._selected_folder_id == folder.id)

        btn = GhostButton(
            row,
            text=f"{prefix}{folder.name}",
            command=lambda fid=folder.id: self._select_folder(fid),
            fg_color=Theme.BG_CARD if is_sel else "transparent",
        )
        btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Right-click on folder button
        btn.bind("<Button-3>",
                 lambda e, fid=folder.id, fn=folder.name:
                     self._folder_context_menu(e, fid, fn))

        # Decks inside this folder
        session = get_session()
        try:
            decks = (
                session.query(Deck)
                .filter(Deck.folder_id == folder.id)
                .order_by(Deck.name)
                .all()
            )
            for deck in decks:
                self._render_deck(deck, indent + 1)

            children = (
                session.query(Folder)
                .filter(Folder.parent_id == folder.id)
                .order_by(Folder.name)
                .all()
            )
            for child in children:
                self._render_folder(child, indent + 1)
        finally:
            session.close()

    def _render_deck(self, deck: Deck, indent: int) -> None:
        prefix = "  " * indent + "🃏 "
        row = ctk.CTkFrame(self._tree_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)

        btn = GhostButton(
            row,
            text=f"{prefix}{deck.name}",
            command=lambda did=deck.id: self._select_deck(did),
        )
        btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Right-click on deck button
        btn.bind("<Button-3>",
                 lambda e, did=deck.id, dn=deck.name, fid=deck.folder_id:
                     self._deck_context_menu(e, did, dn, fid))

        # ── Drag & Drop bindings ──
        btn.bind("<ButtonPress-1>",
                 lambda e, did=deck.id: self._drag_start(e, did), add="+")
        btn.bind("<B1-Motion>", self._drag_motion)
        btn.bind("<ButtonRelease-1>", self._drag_drop, add="+")

    # ==================================================================
    #  CONTEXT MENU — FOLDER
    # ==================================================================

    def _folder_context_menu(self, event, folder_id: int, folder_name: str):
        menu = tk.Menu(self, tearoff=0,
                       bg="#1e2030", fg="#e2e4f0",
                       activebackground=Theme.ACCENT, activeforeground="#fff",
                       font=("Segoe UI", 10),
                       relief="flat", bd=0)

        menu.add_command(label="✏️  Cambiar nombre",
                         command=lambda: self._rename_folder_dialog(folder_id, folder_name))
        menu.add_separator()
        menu.add_command(label="🗑️  Eliminar carpeta",
                         command=lambda: self._confirm_delete_folder(folder_id, folder_name))

        menu.tk_popup(event.x_root, event.y_root)

    def _rename_folder_dialog(self, folder_id: int, current_name: str):
        dialog = ctk.CTkInputDialog(
            text=f"Nuevo nombre para '{current_name}':",
            title="Cambiar nombre — Carpeta",
        )
        name = dialog.get_input()
        if name and name.strip():
            rename_folder(folder_id, name.strip())
            self.refresh()

    def _confirm_delete_folder(self, folder_id: int, name: str):
        ok = messagebox.askyesno(
            "Eliminar carpeta",
            f"¿Eliminar la carpeta '{name}' y todo su contenido?\n\n"
            "Se borrarán todos los mazos, tarjetas y registros de repaso.",
            icon="warning",
        )
        if ok:
            delete_folder(folder_id)
            if self._selected_folder_id == folder_id:
                self._selected_folder_id = None
            self.refresh()

    # ==================================================================
    #  CONTEXT MENU — DECK
    # ==================================================================

    def _deck_context_menu(self, event, deck_id: int, deck_name: str,
                           current_folder_id: int):
        menu = tk.Menu(self, tearoff=0,
                       bg="#1e2030", fg="#e2e4f0",
                       activebackground=Theme.ACCENT, activeforeground="#fff",
                       font=("Segoe UI", 10),
                       relief="flat", bd=0)

        menu.add_command(label="✏️  Cambiar nombre",
                         command=lambda: self._rename_deck_dialog(deck_id, deck_name))

        # ── Move to… submenu ──
        folders = get_all_folders()
        if len(folders) > 1:
            move_menu = tk.Menu(menu, tearoff=0,
                                bg="#1e2030", fg="#e2e4f0",
                                activebackground=Theme.ACCENT,
                                activeforeground="#fff",
                                font=("Segoe UI", 10))
            for fid, fname in folders:
                if fid == current_folder_id:
                    continue
                move_menu.add_command(
                    label=f"📁  {fname}",
                    command=lambda d=deck_id, f=fid: self._do_move_deck(d, f),
                )
            menu.add_cascade(label="📂  Mover a…", menu=move_menu)

        menu.add_separator()
        menu.add_command(label="🔄  Reiniciar progreso",
                         command=lambda: self._confirm_reset_progress(deck_id, deck_name))
        menu.add_command(label="📤  Exportar CSV",
                         command=lambda: self._export_deck(deck_id, deck_name))
        menu.add_separator()
        menu.add_command(label="🗑️  Eliminar mazo",
                         command=lambda: self._confirm_delete_deck(deck_id, deck_name))

        menu.tk_popup(event.x_root, event.y_root)

    def _rename_deck_dialog(self, deck_id: int, current_name: str):
        dialog = ctk.CTkInputDialog(
            text=f"Nuevo nombre para '{current_name}':",
            title="Cambiar nombre — Mazo",
        )
        name = dialog.get_input()
        if name and name.strip():
            rename_deck(deck_id, name.strip())
            self.refresh()

    def _do_move_deck(self, deck_id: int, target_folder_id: int):
        move_deck(deck_id, target_folder_id)
        self.refresh()

    def _confirm_reset_progress(self, deck_id: int, name: str):
        ok = messagebox.askyesno(
            "Reiniciar progreso",
            f"¿Reiniciar todo el progreso del mazo '{name}'?\n\n"
            "Todas las tarjetas volverán a estado nuevo (repeticiones=0).\n"
            "Se eliminarán todos los registros de repaso.",
            icon="warning",
        )
        if ok:
            n = reset_deck_progress(deck_id)
            messagebox.showinfo("Progreso reiniciado",
                                f"Se reiniciaron {n} tarjetas.")
            self.refresh()

    def _export_deck(self, deck_id: int, deck_name: str):
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in deck_name)
        fp = filedialog.asksaveasfilename(
            title="Exportar mazo como CSV",
            defaultextension=".csv",
            initialfile=f"{safe}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if fp:
            n = export_deck_csv(deck_id, fp)
            messagebox.showinfo("Exportación completa",
                                f"Se exportaron {n} tarjetas a:\n{fp}")

    def _confirm_delete_deck(self, deck_id: int, name: str):
        ok = messagebox.askyesno(
            "Eliminar mazo",
            f"¿Eliminar el mazo '{name}' y todas sus tarjetas?",
            icon="warning",
        )
        if ok:
            delete_deck(deck_id)
            self.refresh()

    # ==================================================================
    #  DRAG & DROP
    # ==================================================================

    def _drag_start(self, event, deck_id: int):
        self._drag_deck_id = deck_id

    def _drag_motion(self, event):
        if self._drag_deck_id is None:
            return

        # Create ghost label on first motion
        if self._drag_ghost is None:
            self._drag_ghost = ctk.CTkLabel(
                self.winfo_toplevel(),
                text="🃏 mover…",
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11),
                fg_color=Theme.ACCENT, text_color="#fff",
                corner_radius=8, width=100, height=26,
            )

        # Position ghost near cursor
        rx, ry = self.winfo_toplevel().winfo_pointerxy()
        tx = rx - self.winfo_toplevel().winfo_rootx() + 12
        ty = ry - self.winfo_toplevel().winfo_rooty() + 12
        self._drag_ghost.place(x=tx, y=ty)

        # Highlight folder under cursor
        self._highlight_drop_target(rx, ry)

    def _highlight_drop_target(self, abs_x: int, abs_y: int):
        """Highlight the folder row under the cursor."""
        for fid, row in self._folder_rows.items():
            try:
                rx = row.winfo_rootx()
                ry = row.winfo_rooty()
                rw = row.winfo_width()
                rh = row.winfo_height()
                if rx <= abs_x <= rx + rw and ry <= abs_y <= ry + rh:
                    row.configure(fg_color=Theme.BG_CARD_HOVER)
                else:
                    row.configure(fg_color="transparent")
            except tk.TclError:
                pass

    def _drag_drop(self, event):
        deck_id = self._drag_deck_id
        self._drag_deck_id = None

        # Remove ghost
        if self._drag_ghost is not None:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if deck_id is None:
            return

        # Find which folder was dropped onto
        abs_x, abs_y = self.winfo_toplevel().winfo_pointerxy()
        target_fid = None
        for fid, row in self._folder_rows.items():
            try:
                rx = row.winfo_rootx()
                ry = row.winfo_rooty()
                rw = row.winfo_width()
                rh = row.winfo_height()
                if rx <= abs_x <= rx + rw and ry <= abs_y <= ry + rh:
                    target_fid = fid
                    break
            except tk.TclError:
                pass

        # Reset folder highlights
        for row in self._folder_rows.values():
            try:
                row.configure(fg_color="transparent")
            except tk.TclError:
                pass

        if target_fid is not None:
            move_deck(deck_id, target_fid)
            self.refresh()

    # ==================================================================
    #  SMART IMPORT
    # ==================================================================

    def _trigger_import(self) -> None:
        """If a folder is selected → import there. Otherwise show picker."""
        if self._selected_folder_id is not None:
            if self._on_import:
                self._on_import(self._selected_folder_id)
            return

        # No folder selected — show picker dialog
        self._show_import_picker()

    def _show_import_picker(self):
        """Modal dialog: create new folder or select existing one."""
        folders = get_all_folders()

        dlg = ctk.CTkToplevel(self)
        dlg.title("¿Dónde importar?")
        dlg.geometry("380x280")
        dlg.resizable(False, False)
        dlg.configure(fg_color=Theme.BG_DARK)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        ctk.CTkLabel(
            dlg, text="Selecciona un destino",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=16, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(pady=(24, 16))

        if folders:
            ctk.CTkLabel(
                dlg, text="Carpeta existente:",
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                text_color=Theme.TEXT_SECONDARY,
            ).pack(anchor="w", padx=28)

            folder_map = {name: fid for fid, name in folders}
            combo = ctk.CTkComboBox(
                dlg, values=list(folder_map.keys()),
                width=320,
                font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                dropdown_font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13),
                fg_color=Theme.BG_CARD, border_color=Theme.BORDER,
                button_color=Theme.ACCENT,
            )
            combo.pack(padx=28, pady=(4, 12))

            def _use_existing():
                sel = combo.get()
                fid = folder_map.get(sel)
                if fid and self._on_import:
                    dlg.destroy()
                    self._on_import(fid)

            AccentButton(dlg, text="Importar aquí", command=_use_existing,
                         width=320).pack(padx=28, pady=(0, 8))

        sep_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        sep_frame.pack(fill="x", padx=28, pady=4)
        Separator(sep_frame).pack(fill="x")
        ctk.CTkLabel(sep_frame, text=" o ", fg_color=Theme.BG_DARK,
                     text_color=Theme.TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).place(relx=0.5, rely=0.5,
                                                       anchor="center")

        def _create_new():
            dlg.destroy()
            inner = ctk.CTkInputDialog(
                text="Nombre de la nueva carpeta:",
                title="Nueva carpeta",
            )
            name = inner.get_input()
            if not name or not name.strip():
                return
            s = get_session()
            try:
                f = Folder(name=name.strip())
                s.add(f); s.commit()
                fid = f.id
            finally:
                s.close()
            self.refresh()
            if self._on_import:
                self._on_import(fid)

        AccentButton(dlg, text="＋ Crear nueva carpeta", command=_create_new,
                     width=320, fg_color=Theme.BG_CARD,
                     hover_color=Theme.BG_CARD_HOVER,
                     text_color=Theme.TEXT_PRIMARY).pack(padx=28, pady=(8, 0))

    # ==================================================================
    #  BASIC ACTIONS
    # ==================================================================

    def _select_folder(self, folder_id: int) -> None:
        self._selected_folder_id = folder_id
        self.refresh()   # re-render to highlight selected

    def _select_deck(self, deck_id: int) -> None:
        if self._on_deck_select:
            self._on_deck_select(deck_id)

    def _create_folder(self) -> None:
        dialog = ctk.CTkInputDialog(
            text="Folder name:", title="New Folder",
        )
        name = dialog.get_input()
        if not name or not name.strip():
            return
        session = get_session()
        try:
            folder = Folder(name=name.strip(), parent_id=self._selected_folder_id)
            session.add(folder)
            session.commit()
        finally:
            session.close()
        self.refresh()
