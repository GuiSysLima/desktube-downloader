# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Utilitários compartilhados pelas páginas."""
import os
import re
import subprocess
import sys

from ..downloader import QUALITIES
from ..i18n import t

URL_RE = re.compile(r"https?://[^\s\"'<>]+")
YT_RE = re.compile(r"(youtube\.com|youtu\.be)/", re.I)
VIDEO_Q = ("best", "1080", "720", "480")
AUDIO_Q = ("mp3", "m4a")


def quality_label(key):
    return t(f"q_{key}") if key in QUALITIES else str(key or "")


def short_quality(key):
    """Rótulo curto para colunas de lista (ex.: 'MP3', '1080p', 'Vídeo')."""
    return {"best": t("qcol_best"), "1080": "1080p", "720": "720p", "480": "480p",
            "mp3": "MP3", "m4a": "M4A"}.get(key, str(key or ""))


def open_path(path):
    if not path:
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])


def reveal(path, fallback_dir=""):
    """Mostra o arquivo selecionado no Explorer (ou abre a pasta)."""
    if path and os.path.exists(path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return
        path = os.path.dirname(path)
    target = path if path and os.path.isdir(path) else fallback_dir
    if target:
        os.makedirs(target, exist_ok=True)
        open_path(target)


def split_msg(key, **kw):
    """Mensagens no formato "Pergunta?\\n\\nExplicação" -> (título, texto)."""
    head, _, rest = t(key, **kw).partition("\n")
    return head.strip(), rest.strip()


def ellipsize(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n - 1] + "…"


def context_menu(master, entries, widget=None, event=None):
    """Menu de contexto no tema do app. entries = [(texto, comando, habilitado?) | None (separador)]."""
    import tkinter as tk

    import customtkinter as ctk

    from ..theme import font
    dark = ctk.get_appearance_mode() == "Dark"
    m = tk.Menu(master, tearoff=0, bg="#2B2D31" if dark else "#FFFFFF", fg="#F2F3F5" if dark else "#1B1B1F",
                activebackground="#8B3DFF", activeforeground="#FFFFFF", bd=0,
                font=(font("body").cget("family"), 10))
    for e in entries:
        if e is None:
            m.add_separator()
        else:
            text, cmd, *rest = e
            m.add_command(label=text, command=cmd, state="normal" if (not rest or rest[0]) else "disabled")
    if event is not None:
        x, y = event.x_root, event.y_root
    else:
        x, y = widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height()
    try:
        m.tk_popup(x, y)
    finally:
        m.grab_release()
