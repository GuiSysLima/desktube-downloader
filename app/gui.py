# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Interface gráfica (CustomTkinter): barra lateral + páginas Baixar, Biblioteca e Configurações.

Regras de arquitetura:
- Cores, fontes, raios e espaçamentos vêm de theme.py; componentes reutilizáveis de widgets.py.
- Nenhuma thread toca em widgets: o trabalho em segundo plano manda eventos para self.events,
  que a thread principal processa em _poll() a cada 100 ms.
- A lógica de download (downloader.py), componentes (deps.py), navegadores (browsers.py),
  miniaturas (thumbs.py) e player (player.py) é usada sem alterações de assinatura.
"""
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from dataclasses import asdict
from logging.handlers import RotatingFileHandler
from tkinter import filedialog

import customtkinter as ctk

from . import (AUTHOR, COPYRIGHT_YEAR, GITHUB_REPO, PROJECT_URL, __version__, browsers, deps, i18n, player,
               thumbs)
from .config import Settings, config_dir, load_history, remove_history, save_history
from .downloader import QUALITIES, Downloader
from .fsutil import send_to_trash
from .i18n import t
from .theme import BUTTON_STYLES, C, CONTROL_H, CTA_H, RADIUS, SP, apply_ctk_theme, font, glyph
from .widgets import (ICON_PNG, Card, ChoiceDialog, IconButton, TextDialog, ThumbBox, Toast, apply_icon, badge,
                      button, flash_window, icon_label, load_image, resource_path, set_badge)

log = logging.getLogger("baixador")

URL_RE = re.compile(r"https?://[^\s\"'<>]+")
YT_RE = re.compile(r"(youtube\.com|youtu\.be)/", re.I)
VIDEO_Q = ("best", "1080", "720", "480")
AUDIO_Q = ("mp3", "m4a")
THEMES = ("system", "light", "dark")
DEP_ROWS = ("ffmpeg", "deno", "node", "vlc")
OPTIONAL_DEPS = ("node", "vlc")
LIB_PAGE = 30                    # itens da Biblioteca desenhados por vez
SETTINGS_SECTIONS = ("general", "login", "components", "about")


def setup_logging():
    """Erros inesperados vão para %APPDATA%\\VidNeon\\app.log (em vez de sumirem)."""
    if log.handlers:
        return
    try:
        h = RotatingFileHandler(os.path.join(config_dir(), "app.log"), maxBytes=300_000, backupCount=1,
                                encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    except Exception:
        pass


def quality_label(key):
    return t(f"q_{key}") if key in QUALITIES else str(key)


def open_path(path):
    if not path:
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])


def reveal(path, fallback_dir=""):
    if path and os.path.exists(path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return
        path = os.path.dirname(path)
    target = path if path and os.path.isdir(path) else fallback_dir
    if target:
        os.makedirs(target, exist_ok=True)
        open_path(target)


def version_tuple(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def split_msg(key, **kw):
    """Mensagens no formato "Pergunta?\\n\\nExplicação" -> (título, texto)."""
    head, _, rest = t(key, **kw).partition("\n")
    return head.strip(), rest.strip()


# =========================================================================== barra lateral
class NavItem(ctk.CTkFrame):
    def __init__(self, master, app, key, icon, label):
        super().__init__(master, fg_color="transparent", corner_radius=RADIUS["button"], height=40, cursor="hand2")
        self.app, self.key, self.selected = app, key, False
        self.grid_propagate(False)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.bar = ctk.CTkFrame(self, width=3, height=18, corner_radius=2, fg_color="transparent")
        self.bar.grid(row=0, column=0, padx=(SP["xs"], 0))
        self.icon = icon_label(self, icon, 16)
        self.icon.grid(row=0, column=1, padx=SP["md"])
        self.text = ctk.CTkLabel(self, text=label, font=font("label"), anchor="w", text_color=C["text2"])
        self.text.grid(row=0, column=2, sticky="ew")
        self.count = badge(self, "0", "accent")
        for w in (self, self.icon, self.text, self.bar):
            w.bind("<Button-1>", lambda e: app.show_page(key))
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if not self.selected:
            self.configure(fg_color=C["surface2"] if on else "transparent")

    def set_selected(self, on):
        self.selected = on
        self.configure(fg_color=C["accent_soft"] if on else "transparent")
        self.bar.configure(fg_color=C["accent"] if on else "transparent")
        self.icon.configure(text_color=C["accent"] if on else C["text2"])
        self.text.configure(text_color=C["text"] if on else C["text2"])

    def set_count(self, n):
        if n:
            set_badge(self.count, str(n), "accent")
            self.count.grid(row=0, column=3, padx=(0, SP["sm"]))
        else:
            self.count.grid_remove()


class Sidebar(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=C["sidebar"], corner_radius=0, width=232)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SP["lg"], pady=SP["xl"])
        logo = load_image(ICON_PNG, (40, 40))
        if logo is not None:
            ctk.CTkLabel(head, image=logo, text="").pack(side="left")
        brand = ctk.CTkFrame(head, fg_color="transparent")
        brand.pack(side="left", padx=(SP["sm"], 0))
        ctk.CTkLabel(brand, text=t("app_name"), font=font("title", size=18), anchor="w").pack(anchor="w")
        ctk.CTkLabel(brand, text=t("app_tagline"), font=font("meta"), text_color=C["text2"], anchor="w",
                     justify="left", wraplength=140).pack(anchor="w")
        self.items = {}
        for i, (key, icon, label) in enumerate((("download", "download", t("nav_download")),
                                                ("library", "library", t("nav_library")),
                                                ("settings", "settings", t("nav_settings")))):
            item = NavItem(self, app, key, icon, label)
            item.grid(row=1 + i, column=0, sticky="ew", padx=SP["sm"], pady=2)
            self.items[key] = item
        ctk.CTkLabel(self, text=t("version", v=__version__), font=font("meta"), text_color=C["text2"]).grid(
            row=6, column=0, sticky="w", padx=SP["lg"], pady=SP["lg"])

    def select(self, key):
        for k, item in self.items.items():
            item.set_selected(k == key)


# =========================================================================== página Baixar
class JobCard(Card):
    def __init__(self, master, app, job):
        super().__init__(master)
        self.app, self.job, self._indeterminate = app, job, False
        self.grid_columnconfigure(1, weight=1)
        self.thumb = ThumbBox(self, audio=job["quality"] in AUDIO_Q)
        self.thumb.grid(row=0, column=0, rowspan=3, padx=SP["md"], pady=SP["md"])
        self.title = ctk.CTkLabel(self, text=job["url"], font=font("card"), anchor="w")
        self.title.grid(row=0, column=1, sticky="sew", pady=(SP["md"], 0))
        self.bar = ctk.CTkProgressBar(self, height=6, mode="determinate")
        self.bar.set(0)
        self.bar.grid(row=1, column=1, sticky="ew", pady=SP["sm"])
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=2, column=1, sticky="new", pady=(0, SP["md"]))
        info.grid_columnconfigure(1, weight=1)
        self.status_icon = icon_label(info, "info", 12)
        self.status = ctk.CTkLabel(info, text="", font=font("meta"), text_color=C["text2"], anchor="w",
                                   justify="left", wraplength=440)
        self.status.grid(row=0, column=1, sticky="w")
        self.speed = ctk.CTkLabel(info, text="", font=font("meta"), text_color=C["text2"], anchor="e")
        self.speed.grid(row=0, column=2, sticky="e", padx=(SP["sm"], 0))
        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.grid(row=0, column=2, rowspan=3, padx=SP["md"])
        self.play_btn = IconButton(acts, "play", t("tip_play"), "accent", command=self._play)
        self.folder_btn = IconButton(acts, "folder", t("tip_folder"), command=self._folder)
        self.action_btn = IconButton(acts, "cancel", t("tip_cancel"), command=self._action)
        self.action_btn.pack(side="left", padx=2)
        self.bind_children_hover()
        self.update_job(job)

    def _set_bar(self, mode, value=None, color=None):
        if mode == "indeterminate" and not self._indeterminate:
            self.bar.configure(mode="indeterminate")
            self.bar.start()
            self._indeterminate = True
        elif mode == "determinate":
            if self._indeterminate:
                self.bar.stop()
                self.bar.configure(mode="determinate")
                self._indeterminate = False
            if value is not None:
                self.bar.set(value)
        self.bar.configure(progress_color=color or C["accent"])

    def _status(self, text, icon=None, color=None):
        self.status.configure(text=text, text_color=color or C["text2"])
        if icon:
            self.status_icon.configure(text=glyph(icon), text_color=color or C["text2"])
            self.status_icon.grid(row=0, column=0, padx=(0, SP["xs"]))
        else:
            self.status_icon.grid_remove()

    def update_job(self, job):
        self.job = job
        title = job["title"] or job["url"]
        self.title.configure(text=title if len(title) <= 80 else title[:77] + "...")
        if job.get("thumb"):
            self.thumb.set_path(job["thumb"])
        state, quality = job["state"], quality_label(job["quality"])
        item = t("item_n", n=job["item"]) if job["item"] else ""
        speed = ""
        if state == "downloading" and job["status"] == "st_starting":
            self._set_bar("indeterminate")
            self._status(t("st_starting"))
        elif state == "downloading":
            self._set_bar("determinate", job["progress"])
            self._status("  •  ".join(x for x in (t(job["status"]), f"{job['progress'] * 100:.0f}%", item) if x))
            speed = "  •  ".join(x for x in (job["speed"], t("eta", eta=job["eta"]) if job["eta"] else "") if x)
        elif state == "processing":
            self._set_bar("indeterminate")
            self._status(t(job["status"]))
        elif state == "done":
            self._set_bar("determinate", 1, C["success"])
            self._status(f"{t(job['status'])}  •  {quality}", "check", C["success"])
        elif state == "error":
            self._set_bar("determinate", 0, C["error"])
            args = dict(job.get("error_args") or {})
            if job["error"] == "err_cookie_copy" and not args.get("browser"):
                args["browser"] = t("the_browser")
            self._status(t(job["error"], **args), "error", C["error"])
        elif state == "cancelled":
            self._set_bar("determinate", 0)
            self._status(t("st_cancelled"), "cancel")
        else:
            self._set_bar("determinate", 0)
            self._status(f"{t('st_queued')}  •  {quality}")
        self.speed.configure(text=speed)

        playable = state == "done" and bool(job.get("filepath")) and os.path.isfile(job["filepath"])
        for b in (self.play_btn, self.folder_btn, self.action_btn):
            b.pack_forget()
        if playable:
            self.play_btn.pack(side="left", padx=2)
            self.folder_btn.pack(side="left", padx=2)
            self.thumb.on_click(self._play)
        if state in ("queued", "downloading", "processing"):
            self.action_btn.set_icon("cancel")
            self.action_btn.tooltip.set_text(t("tip_remove") if state == "queued" else t("tip_cancel"))
            self.action_btn.pack(side="left", padx=2)
        elif state in ("error", "cancelled"):
            self.action_btn.set_icon("retry")
            self.action_btn.tooltip.set_text(t("tip_retry"))
            self.action_btn.pack(side="left", padx=2)

    def _play(self):
        self.app.play_media(self.job["filepath"], self.job["title"], self.job.get("thumb"))

    def _folder(self):
        reveal(self.job["filepath"], self.app.settings.output_dir)

    def _action(self):
        if self.job["state"] in ("queued", "downloading", "processing"):
            self.app.downloader.cancel(self.job["id"])
        else:
            j = self.job
            self.app.remove_job_card(j["id"])
            self.app.enqueue([j["url"]], j["quality"], j["playlist"], j["subtitles"])


class DownloadPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        s = app.settings
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self, text=t("nav_download"), font=font("title"), anchor="w").grid(
            row=0, column=0, sticky="ew")
        ctk.CTkLabel(self, text=t("dl_subtitle"), font=font("body"), text_color=C["text2"], anchor="w").grid(
            row=1, column=0, sticky="ew", pady=(0, SP["lg"]))

        # --- link + opções
        card = Card(self, hover=False)
        card.grid(row=2, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        icon_label(card, "link", 16).grid(row=0, column=0, padx=(SP["lg"], SP["sm"]), pady=(SP["lg"], 0))
        self.url = ctk.CTkEntry(card, height=CTA_H, font=font("body", size=14), placeholder_text=t("url_placeholder"))
        self.url.grid(row=0, column=1, sticky="ew", pady=(SP["lg"], 0))
        self.url.bind("<Return>", lambda e: app.start_download())
        self.url.bind("<FocusIn>", lambda e: self.url.configure(border_color=C["accent"]))
        self.url.bind("<FocusOut>", lambda e: self.url.configure(border_color=C["input_border"]))
        self.url.bind("<KeyRelease>", lambda e: self.show_error(""))
        IconButton(card, "paste", t("tip_paste"), "secondary", size=CTA_H, command=self.paste).grid(
            row=0, column=2, padx=(SP["sm"], 0), pady=(SP["lg"], 0))
        button(card, t("btn_download"), "primary", app.start_download, width=140, height=CTA_H,
               font=font("label", size=14)).grid(row=0, column=3, padx=(SP["sm"], SP["lg"]), pady=(SP["lg"], 0))
        self.error = ctk.CTkLabel(card, text="", font=font("caption"), text_color=C["error"], anchor="w")

        opts = ctk.CTkFrame(card, fg_color="transparent")
        opts.grid(row=2, column=0, columnspan=4, sticky="ew", padx=SP["lg"], pady=(SP["md"], SP["lg"]))
        self.kind = ctk.CTkSegmentedButton(opts, values=[t("seg_video"), t("seg_audio")], height=CONTROL_H,
                                           font=font("label"), command=self._on_kind)
        self.kind.pack(side="left")
        self.quality = ctk.CTkOptionMenu(opts, width=190, height=CONTROL_H, font=font("body"),
                                         command=self._on_quality)
        self.quality.pack(side="left", padx=(SP["sm"], 0))
        self.playlist = ctk.CTkSwitch(opts, text=t("chk_playlist"), font=font("body"), command=self._on_option)
        self.playlist.pack(side="left", padx=(SP["xl"], 0))
        self.subs = ctk.CTkSwitch(opts, text=t("chk_subtitles"), font=font("body"), command=self._on_option)
        self.subs.pack(side="left", padx=(SP["lg"], 0))
        (self.playlist.select if s.playlist else self.playlist.deselect)()
        (self.subs.select if s.subtitles else self.subs.deselect)()
        self.login = button(opts, "", "ghost", lambda: app.show_page("settings", "login"), kind="body",
                            text_color=C["text2"])
        self.login.pack(side="right")
        self._sync_quality_widgets()
        self.refresh_login()

        # --- faixa de componentes faltando
        self.banner = ctk.CTkFrame(self, fg_color=C["warning_bg"], corner_radius=RADIUS["card"])
        icon_label(self.banner, "warning", 16, C["warning"]).pack(side="left", padx=(SP["lg"], SP["sm"]),
                                                                   pady=SP["md"])
        self.banner_text = ctk.CTkLabel(self.banner, text="", font=font("body"), anchor="w", justify="left",
                                        wraplength=560)
        self.banner_text.pack(side="left", fill="x", expand=True, pady=SP["md"])
        self.banner_btn = button(self.banner, t("btn_install_now"), "accent", app.install_missing)
        self.banner_btn.pack(side="right", padx=SP["lg"])

        # --- fila
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=4, column=0, sticky="ew", pady=(SP["xl"], SP["sm"]))
        ctk.CTkLabel(head, text=t("queue_title"), font=font("section")).pack(side="left")
        self.count = badge(head, "0", "muted")
        button(head, t("btn_clear_finished"), "ghost", app.clear_finished, kind="body").pack(side="right")
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=5, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self.empty = ctk.CTkFrame(self.list, fg_color="transparent")
        icon_label(self.empty, "download", 40, C["text2"]).pack(pady=(SP["xxl"], SP["md"]))
        ctk.CTkLabel(self.empty, text=t("queue_empty_title"), font=font("section")).pack()
        ctk.CTkLabel(self.empty, text=t("queue_empty_text"), font=font("body"), text_color=C["text2"]).pack(
            pady=(SP["xs"], 0))
        ctk.CTkLabel(self.empty, text=t("queue_empty_hint"), font=font("caption"), text_color=C["text2"],
                     wraplength=460).pack(pady=(SP["md"], 0))
        self.empty.grid(row=0, column=0, pady=SP["xl"])

        # --- pasta de destino
        folder = Card(self, hover=False)
        folder.grid(row=6, column=0, sticky="ew", pady=(SP["md"], 0))
        folder.grid_columnconfigure(2, weight=1)
        icon_label(folder, "folder", 16).grid(row=0, column=0, padx=(SP["lg"], SP["sm"]), pady=SP["md"])
        ctk.CTkLabel(folder, text=t("save_to"), font=font("label")).grid(row=0, column=1, padx=(0, SP["sm"]))
        self.folder = ctk.CTkLabel(folder, text="", font=font("body"), text_color=C["text2"], anchor="w")
        self.folder.grid(row=0, column=2, sticky="ew")
        button(folder, t("btn_open"), "ghost", lambda: reveal("", app.settings.output_dir), kind="body").grid(
            row=0, column=3, padx=SP["xs"])
        button(folder, t("btn_change_folder"), "secondary", app.choose_output, kind="body").grid(
            row=0, column=4, padx=(SP["xs"], SP["lg"]), pady=SP["md"])
        self.refresh_folder()

    # ---- opções
    def _sync_quality_widgets(self):
        q = self.app.settings.quality if self.app.settings.quality in QUALITIES else "best"
        audio = q in AUDIO_Q
        self.kind.set(t("seg_audio") if audio else t("seg_video"))
        keys = AUDIO_Q if audio else VIDEO_Q
        self.quality.configure(values=[t(f"qs_{k}") for k in keys])
        self.quality.set(t(f"qs_{q}"))

    def _on_kind(self, label):
        audio = label == t("seg_audio")
        if audio != (self.app.settings.quality in AUDIO_Q):
            self.app.settings.quality = "mp3" if audio else "best"
            self.app.save()
        self._sync_quality_widgets()

    def _on_quality(self, label):
        for k in QUALITIES:
            if t(f"qs_{k}") == label:
                self.app.settings.quality = k
        self.app.save()

    def _on_option(self):
        self.app.settings.playlist = bool(self.playlist.get())
        self.app.settings.subtitles = bool(self.subs.get())
        self.app.save()

    def refresh_login(self):
        s, b = self.app.settings, browsers.BROWSERS.get(self.app.settings.browser)
        if b:
            text = t("login_browser", name=b.label)
        elif s.browser == "file" and s.cookies_file:
            text = t("login_file")
        else:
            text = t("login_none")
        self.login.configure(text=text.replace("⚙", "").strip() + "  ›")

    def refresh_folder(self):
        p = self.app.settings.output_dir
        self.folder.configure(text=p if len(p) <= 70 else "..." + p[-67:])

    # ---- link
    def paste(self):
        try:
            text = self.app.clipboard_get().strip()
        except Exception:
            return
        self.url.delete(0, "end")
        self.url.insert(0, text)
        self.url.focus_set()
        self.show_error("")

    def show_error(self, text):
        if text:
            self.error.configure(text=text)
            self.error.grid(row=1, column=1, columnspan=3, sticky="w", pady=(SP["xs"], 0))
            self.url.configure(border_color=C["error"])
        elif self.error.winfo_ismapped():
            self.error.grid_remove()
            self.url.configure(border_color=C["accent"] if self.url.focus_get() is self.url else C["input_border"])

    def set_banner(self, text, busy):
        if text:
            self.banner_text.configure(text=text)
            self.banner_btn.configure(state="disabled" if busy else "normal")
            self.banner.grid(row=3, column=0, sticky="ew", pady=(SP["md"], 0))
        else:
            self.banner.grid_remove()

    def set_count(self, n):
        if n:
            set_badge(self.count, str(n), "muted")
            self.count.pack(side="left", padx=SP["sm"])
        else:
            self.count.pack_forget()


# =========================================================================== página Biblioteca
class LibraryPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._search_job = None
        self._limit = LIB_PAGE
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(head, text=t("nav_library"), font=font("title")).pack(side="left")
        self.count = badge(head, "0", "muted")
        self.count.pack(side="left", padx=SP["sm"])
        button(head, t("btn_clear_history"), "danger_ghost", app.clear_history, kind="body").pack(side="right")
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=SP["md"])
        icon_label(bar, "search", 14).pack(side="left", padx=(0, SP["sm"]))
        self.search = ctk.CTkEntry(bar, height=CONTROL_H, width=360, placeholder_text=t("hist_search"))
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", self._on_search)
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=2, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self.refresh()

    def _on_search(self, _e=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._apply_search)  # debounce: espera parar de digitar

    def _apply_search(self):
        self._search_job = None
        self._limit = LIB_PAGE
        self.refresh()

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        self.app._thumb_boxes = {}
        all_items = load_history()
        q = self.search.get().strip().lower()
        items = [h for h in all_items if not q or q in (h.get("title", "") + h.get("url", "")).lower()]
        set_badge(self.count, str(len(all_items)), "muted")
        if not items:
            self._empty(q)
            return
        for i, h in enumerate(items[:self._limit]):
            self._row(i, h)
        if len(items) > self._limit:
            button(self.list, t("btn_load_more", n=len(items) - self._limit), "secondary", self._more,
                   kind="body").grid(row=self._limit, column=0, pady=SP["md"])

    def _more(self):
        self._limit += LIB_PAGE
        self.refresh()

    def _empty(self, query):
        f = ctk.CTkFrame(self.list, fg_color="transparent")
        f.grid(row=0, column=0, pady=SP["xxl"])
        icon_label(f, "search" if query else "library", 40, C["text2"]).pack(pady=(SP["xl"], SP["md"]))
        if query:
            ctk.CTkLabel(f, text=t("hist_no_results", q=query), font=font("section")).pack()
        else:
            ctk.CTkLabel(f, text=t("hist_empty_title"), font=font("section")).pack()
            ctk.CTkLabel(f, text=t("hist_empty_text"), font=font("body"), text_color=C["text2"]).pack(
                pady=(SP["xs"], 0))

    def _row(self, i, h):
        app = self.app
        card = Card(self.list)
        card.grid(row=i, column=0, sticky="ew", pady=(0, SP["sm"]))
        card.grid_columnconfigure(1, weight=1)
        path = h.get("filepath", "")
        exists = bool(path) and os.path.isfile(path)
        box = ThumbBox(card, audio=h.get("quality") in AUDIO_Q)
        box.grid(row=0, column=0, rowspan=2, padx=SP["md"], pady=SP["md"])
        app.show_history_thumb(box, h, path, exists)
        title = h.get("title") or h.get("url", "")
        ctk.CTkLabel(card, text=title if len(title) <= 90 else title[:87] + "...", font=font("card"),
                     anchor="w").grid(row=0, column=1, sticky="sew", pady=(SP["md"], 0))
        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.grid(row=1, column=1, sticky="new", pady=(SP["xs"], SP["md"]))
        ctk.CTkLabel(meta, text=f"{h.get('when', '')}  •  {quality_label(h.get('quality', ''))}", font=font("meta"),
                     text_color=C["text2"]).pack(side="left")
        if path and not exists:
            badge(meta, t("hist_missing_file"), "warning").pack(side="left", padx=SP["sm"])
        acts = ctk.CTkFrame(card, fg_color="transparent")
        acts.grid(row=0, column=2, rowspan=2, padx=SP["md"])
        play = (lambda p=path, e=h: app.play_media(p, e.get("title", ""), e.get("thumb"))) if exists else None
        pb = IconButton(acts, "play", t("tip_play"), "accent", command=play)
        if not exists:
            pb.configure(state="disabled", fg_color=C["surface2"])
        pb.pack(side="left", padx=2)
        IconButton(acts, "folder", t("tip_folder"),
                   command=lambda p=path, d=h.get("folder", ""): reveal(p, d or app.settings.output_dir)).pack(
            side="left", padx=2)
        more = IconButton(acts, "more", t("tip_more"))
        more.configure(command=lambda b=more, e=h: self._menu(b, e))
        more.pack(side="left", padx=2)
        if play:
            box.on_click(play)
        card.bind_children_hover()

    def _menu(self, widget, entry):
        dark = ctk.get_appearance_mode() == "Dark"
        m = tk.Menu(self, tearoff=0, bg="#2B2D31" if dark else "#FFFFFF", fg="#F2F3F5" if dark else "#1B1B1F",
                    activebackground="#7C3AED", activeforeground="#FFFFFF", bd=0,
                    font=(font("body").cget("family"), 10))
        m.add_command(label=t("btn_redownload"), command=lambda: self.app.redownload(entry))
        m.add_command(label=t("menu_open_folder"),
                      command=lambda: reveal(entry.get("filepath", ""),
                                             entry.get("folder") or self.app.settings.output_dir))
        m.add_separator()
        m.add_command(label=t("menu_delete"), command=lambda: self.app.delete_entry(entry),
                      foreground="#F23F43" if dark else "#C42B30")
        try:
            m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            m.grab_release()


# =========================================================================== página Configurações
def section_card(parent, icon, title, desc=""):
    card = Card(parent, hover=False)
    card.grid_columnconfigure(0, weight=1)
    head = ctk.CTkFrame(card, fg_color="transparent")
    head.grid(row=0, column=0, sticky="ew", padx=SP["lg"], pady=(SP["lg"], 0))
    icon_label(head, icon, 16, C["accent"]).pack(side="left", padx=(0, SP["sm"]))
    ctk.CTkLabel(head, text=title, font=font("section")).pack(side="left")
    if desc:
        ctk.CTkLabel(card, text=desc, font=font("caption"), text_color=C["text2"], anchor="w", justify="left",
                     wraplength=640).grid(row=1, column=0, sticky="ew", padx=SP["lg"], pady=(SP["xs"], 0))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.grid(row=2, column=0, sticky="ew", padx=SP["lg"], pady=(SP["md"], SP["lg"]))
    body.grid_columnconfigure(1, weight=1)
    return card, body


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text=t("nav_settings"), font=font("title"), anchor="w").grid(row=0, column=0, sticky="ew")
        self._labels = {k: t(f"set_{k}") for k in SETTINGS_SECTIONS}
        self.nav = ctk.CTkSegmentedButton(self, values=list(self._labels.values()), height=CONTROL_H,
                                          font=font("label"), command=self._on_nav)
        self.nav.grid(row=1, column=0, sticky="w", pady=(SP["md"], SP["lg"]))
        self.sections = {}
        for key in SETTINGS_SECTIONS:
            frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
            frame.grid_columnconfigure(0, weight=1)
            self.sections[key] = frame
            getattr(self, f"_build_{key}")(frame)
        self.show("general")

    def _on_nav(self, label):
        self.show(next(k for k, v in self._labels.items() if v == label))

    def show(self, key):
        for k, f in self.sections.items():
            if k == key:
                f.grid(row=2, column=0, sticky="nsew")
            else:
                f.grid_remove()
        self.nav.set(self._labels[key])

    # ---- Geral
    def _build_general(self, p):
        app, s = self.app, self.app.settings
        card, body = section_card(p, "globe", t("sec_language"))
        card.grid(row=0, column=0, sticky="ew", pady=(0, SP["md"]))
        ctk.CTkLabel(body, text=t("language_label"), font=font("body")).grid(row=0, column=0, sticky="w")
        lang = ctk.CTkOptionMenu(body, values=list(i18n.LANGUAGES.values()), width=220, height=CONTROL_H,
                                 command=app.change_language)
        lang.set(i18n.LANGUAGES[i18n.current()])
        lang.grid(row=0, column=1, sticky="w", padx=SP["md"])

        card, body = section_card(p, "theme", t("sec_theme"))
        card.grid(row=1, column=0, sticky="ew", pady=(0, SP["md"]))
        self._themes = {t(f"theme_{k}"): k for k in THEMES}
        seg = ctk.CTkSegmentedButton(body, values=list(self._themes), height=CONTROL_H, command=self._on_theme)
        seg.set(t(f"theme_{s.theme if s.theme in THEMES else 'system'}"))
        seg.grid(row=0, column=0, sticky="w")

        card, body = section_card(p, "folder", t("sec_folder"), t("sec_folder_desc"))
        card.grid(row=2, column=0, sticky="ew", pady=(0, SP["md"]))
        self.out = ctk.CTkEntry(body, height=CONTROL_H)
        self.out.insert(0, s.output_dir)
        self.out.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.out.bind("<FocusOut>", lambda e: app.set_output(self.out.get()))
        button(body, t("btn_choose"), "secondary", app.choose_output, kind="body").grid(
            row=0, column=2, padx=(SP["sm"], 0))

        card, body = section_card(p, "download", t("sec_options"))
        card.grid(row=3, column=0, sticky="ew", pady=(0, SP["md"]))
        self.switches = {}
        for r, (key, attr) in enumerate((("opt_metadata", "embed_metadata"), ("opt_thumbnail", "embed_thumbnail"),
                                         ("opt_clipboard", "watch_clipboard"))):
            sw = ctk.CTkSwitch(body, text=t(key), font=font("body"), command=self._on_options)
            (sw.select if getattr(s, attr) else sw.deselect)()
            sw.grid(row=r, column=0, columnspan=3, sticky="w", pady=SP["xs"])
            self.switches[attr] = sw
        ctk.CTkLabel(body, text=t("sub_langs_label"), font=font("body")).grid(row=3, column=0, sticky="w",
                                                                            pady=(SP["sm"], 0))
        self.langs = ctk.CTkEntry(body, width=200, height=CONTROL_H)
        self.langs.insert(0, s.sub_langs)
        self.langs.grid(row=3, column=1, sticky="w", padx=SP["md"], pady=(SP["sm"], 0))
        self.langs.bind("<FocusOut>", lambda e: self._on_options())

    def _on_theme(self, label):
        self.app.settings.theme = self._themes.get(label, "system")
        ctk.set_appearance_mode(self.app.settings.theme)
        self.app.save()

    def _on_options(self):
        s = self.app.settings
        for attr, sw in self.switches.items():
            setattr(s, attr, bool(sw.get()))
        s.sub_langs = self.langs.get().strip() or "pt.*,en.*"
        self.app.save()

    def set_output_text(self, path):
        if self.out.get().strip() != path:
            self.out.delete(0, "end")
            self.out.insert(0, path)

    # ---- Login
    def _build_login(self, p):
        app, s = self.app, self.app.settings
        card, body = section_card(p, "account", t("sec_login"), t("sec_login_desc"))
        card.grid(row=0, column=0, sticky="ew")
        installed = browsers.installed_keys()
        self._browsers = {t("browser_none"): "none"}
        for k, b in browsers.BROWSERS.items():
            self._browsers[f"{b.label}  {t('detected')}" if k in installed else b.label] = k
        self._browsers[t("browser_file")] = "file"
        ctk.CTkLabel(body, text=t("browser_label"), font=font("body")).grid(row=0, column=0, sticky="w")
        self.browser = ctk.CTkOptionMenu(body, values=list(self._browsers), width=260, height=CONTROL_H,
                                         command=self._on_browser)
        self.browser.set(next((lbl for lbl, k in self._browsers.items() if k == s.browser), t("browser_none")))
        self.browser.grid(row=0, column=1, sticky="w", padx=SP["md"])
        button(body, t("btn_test_login"), "accent", app.test_login, kind="body").grid(row=0, column=2, sticky="e")
        self.cookie_label = ctk.CTkLabel(body, text=t("file_label"), font=font("body"))
        self.cookie = ctk.CTkEntry(body, height=CONTROL_H, placeholder_text=t("cookie_placeholder"))
        self.cookie.insert(0, s.cookies_file)
        self.cookie.bind("<FocusOut>", lambda e: self._set_cookie(self.cookie.get()))
        self.cookie_btn = button(body, t("btn_choose"), "secondary", self._choose_cookie, kind="body")
        self.result = ctk.CTkFrame(body, fg_color="transparent")
        self.result_icon = icon_label(self.result, "info", 14)
        self.result_text = ctk.CTkLabel(self.result, text="", font=font("body"), anchor="w", justify="left",
                                        wraplength=600)
        self.result_text.pack(side="left")
        tip = ctk.CTkFrame(body, fg_color=C["surface2"], corner_radius=RADIUS["button"])
        tip.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(SP["md"], 0))
        icon_label(tip, "info", 14, C["accent"]).pack(side="left", anchor="n", padx=(SP["md"], SP["sm"]),
                                                      pady=SP["md"])
        self.tip = ctk.CTkLabel(tip, text="", font=font("caption"), anchor="w", justify="left", wraplength=600)
        self.tip.pack(side="left", fill="x", expand=True, pady=SP["md"], padx=(0, SP["md"]))
        self._update_cookie_widgets()

    def _on_browser(self, label):
        self.app.settings.browser = self._browsers.get(label, "none")
        self.set_login_result(None)
        self._update_cookie_widgets()
        self.app.pages["download"].refresh_login()
        self.app.save()

    def _update_cookie_widgets(self):
        """O campo do cookies.txt só aparece quando essa opção é escolhida."""
        if self.app.settings.browser == "file":
            self.cookie_label.grid(row=1, column=0, sticky="w", pady=(SP["md"], 0))
            self.cookie.grid(row=1, column=1, sticky="ew", padx=SP["md"], pady=(SP["md"], 0))
            self.cookie_btn.grid(row=1, column=2, sticky="e", pady=(SP["md"], 0))
        else:
            for w in (self.cookie_label, self.cookie, self.cookie_btn):
                w.grid_remove()
        self.tip.configure(text=self.app.login_tip_text())

    def _set_cookie(self, path):
        self.app.settings.cookies_file = path.strip()
        self.app.pages["download"].refresh_login()
        self.app.save()

    def _choose_cookie(self):
        path = filedialog.askopenfilename(filetypes=[("Cookies", "*.txt"), (t("all_files"), "*.*")])
        if path:
            path = os.path.normpath(path)
            self.cookie.delete(0, "end")
            self.cookie.insert(0, path)
            self._set_cookie(path)

    def set_login_result(self, ok, text=""):
        if text:
            self.result.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(SP["md"], 0))
        else:
            self.result.grid_remove()
        if ok is None:
            self.result_icon.pack_forget()
            self.result_text.configure(text=text, text_color=C["text2"])
            return
        color = C["success"] if ok else C["error"]
        self.result_icon.configure(text=glyph("check" if ok else "error"), text_color=color)
        self.result_icon.pack(side="left", padx=(0, SP["sm"]), before=self.result_text)
        self.result_text.configure(text=text, text_color=color)

    # ---- Componentes
    def _build_components(self, p):
        app = self.app
        self.dep = {}
        for i, name in enumerate(DEP_ROWS):
            card = Card(p, hover=False)
            card.grid(row=1 + i, column=0, sticky="ew", pady=(0, SP["sm"]))
            card.grid_columnconfigure(1, weight=1)
            icon_label(card, "puzzle", 18, C["accent"]).grid(row=0, column=0, rowspan=3, padx=SP["lg"],
                                                             pady=SP["md"])
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.grid(row=0, column=1, sticky="ew", pady=(SP["md"], 0))
            ctk.CTkLabel(top, text=deps.COMPONENTS[name].label, font=font("card")).pack(side="left")
            b = badge(top, "", "muted")
            b.pack(side="left", padx=SP["sm"])
            ctk.CTkLabel(card, text=t(f"dep_desc_{name}"), font=font("caption"), text_color=C["text2"], anchor="w",
                         justify="left", wraplength=520).grid(row=1, column=1, sticky="ew", pady=(SP["xs"], SP["md"]))
            path = ctk.CTkLabel(card, text="", font=font("meta"), text_color=C["text2"], anchor="w")
            btn = button(card, t("btn_install"), "accent", lambda n=name: app.dep_action(n), kind="body", width=120)
            btn.grid(row=0, column=2, rowspan=3, padx=SP["lg"])
            self.dep[name] = (b, path, btn)
        foot = ctk.CTkFrame(p, fg_color="transparent")
        foot.grid(row=10, column=0, sticky="ew", pady=(SP["sm"], 0))
        ctk.CTkLabel(foot, text=f"yt-dlp {deps.ytdlp_version()}", font=font("meta"), text_color=C["text2"]).pack(
            side="left")
        button(foot, t("btn_recheck"), "ghost", app.refresh_deps, kind="body").pack(side="right")
        self.log_card, body = section_card(p, "info", t("log_title"))
        self.log = ctk.CTkTextbox(body, height=130, font=ctk.CTkFont(family="Consolas", size=11))
        self.log.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.log.configure(state="disabled")

    def update_deps(self, status, busy):
        for name, (b, path_lbl, btn) in self.dep.items():
            path = status.get(name)
            if path:
                set_badge(b, t("badge_installed"), "success")
                path_lbl.configure(text=path)
                path_lbl.grid(row=2, column=1, sticky="ew", pady=(0, SP["md"]))
                btn.configure(text=t("btn_uninstall"), **BUTTON_STYLES["danger_ghost"])
            else:
                optional = name in OPTIONAL_DEPS
                set_badge(b, t("badge_optional") if optional else t("badge_missing"), "muted" if optional else "error")
                path_lbl.grid_remove()
                btn.configure(text=t("btn_install"), **BUTTON_STYLES["accent"])
            btn.configure(state="disabled" if busy else "normal")

    def log_line(self, line):
        if not self.log_card.winfo_ismapped():
            self.log_card.grid(row=11, column=0, sticky="ew", pady=(SP["md"], 0))
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---- Sobre
    def _build_about(self, p):
        app = self.app
        project = f"https://github.com/{GITHUB_REPO}" if GITHUB_REPO else PROJECT_URL
        # --- marca
        card = Card(p, hover=False)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        logo = load_image(ICON_PNG, (72, 72))
        if logo is not None:
            ctk.CTkLabel(card, image=logo, text="").grid(row=0, column=0, rowspan=3, padx=SP["xl"], pady=SP["xl"])
        ctk.CTkLabel(card, text=t("app_name"), font=font("title"), anchor="w").grid(
            row=0, column=1, sticky="sw", pady=(SP["xl"], 0))
        ctk.CTkLabel(card, text=t("version", v=__version__) + f"  •  yt-dlp {deps.ytdlp_version()}",
                     font=font("body"), text_color=C["text2"], anchor="w").grid(row=1, column=1, sticky="w")
        ctk.CTkLabel(card, text=t("app_tagline") + ". " + t("about_text"), font=font("caption"),
                     text_color=C["text2"], anchor="w", justify="left", wraplength=520).grid(
            row=2, column=1, sticky="nw", pady=(SP["xs"], SP["xl"]))
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w", pady=SP["md"])
        b = button(row, t("btn_check_updates"), "accent", app.check_updates, kind="body")
        b.pack(side="left")
        if not GITHUB_REPO:   # build local sem repositório: sem como checar atualizações
            b.configure(state="disabled", fg_color=C["surface2"], text_color_disabled=C["text_disabled"])
        button(row, t("btn_project_page"), "secondary", lambda: webbrowser.open(project), kind="body").pack(
            side="left", padx=SP["sm"])
        button(row, t("btn_open_log"), "ghost", lambda: open_path(os.path.join(config_dir(), "app.log")),
               kind="body").pack(side="left", padx=SP["sm"])

        # --- licença e créditos (avisos legais exigidos pela GPL-3.0; o crédito ao autor é
        #     obrigatório pelos termos adicionais da seção 7(b) — ver NOTICE)
        lic, body = section_card(p, "info", t("sec_license"))
        lic.grid(row=2, column=0, sticky="ew", pady=(SP["sm"], 0))
        ctk.CTkLabel(body, text=f"© {COPYRIGHT_YEAR} {AUTHOR}", font=font("label"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w")
        link = ctk.CTkLabel(body, text=f"VidNeon by {AUTHOR}  —  {PROJECT_URL}", font=font("caption"),
                            text_color=C["accent"], anchor="w", cursor="hand2")
        link.grid(row=1, column=0, columnspan=3, sticky="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(PROJECT_URL))
        ctk.CTkLabel(body, text=t("legal_notice"), font=font("caption"), text_color=C["text2"], anchor="w",
                     justify="left", wraplength=640).grid(row=2, column=0, columnspan=3, sticky="w", pady=(SP["sm"], 0))
        ctk.CTkLabel(body, text=t("third_party"), font=font("caption"), text_color=C["text2"], anchor="w",
                     justify="left", wraplength=640).grid(row=3, column=0, columnspan=3, sticky="w", pady=(SP["sm"], 0))
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=3, sticky="w", pady=(SP["md"], 0))
        button(btns, t("btn_view_license"), "secondary", lambda: self._show_text("LICENSE", t("btn_view_license")),
               kind="body").pack(side="left")
        button(btns, t("btn_view_notice"), "secondary", lambda: self._show_text("NOTICE", t("btn_view_notice")),
               kind="body").pack(side="left", padx=SP["sm"])

    def _show_text(self, filename, title):
        """Mostra LICENSE/NOTICE numa janela de leitura (o arquivo vai junto no .exe)."""
        path = resource_path(filename)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            webbrowser.open("https://www.gnu.org/licenses/gpl-3.0.html" if filename == "LICENSE" else PROJECT_URL)
            return
        TextDialog(self.app, f"{t('app_name')} — {title}", text)


# =========================================================================== janela principal
class App(ctk.CTk):
    def __init__(self):
        setup_logging()
        deps.refresh_path()
        self.settings = Settings.load()
        i18n.set_language(self.settings.language or i18n.detect_default())
        apply_ctk_theme()
        ctk.set_appearance_mode(self.settings.theme)
        super().__init__()
        self.geometry("1120x740")
        self.minsize(920, 620)
        apply_icon(self)
        self.report_callback_exception = self._on_tk_error

        self.events = queue.Queue()
        self.downloader = Downloader(lambda: self.settings, self.events)
        self.cards, self.hidden_jobs = {}, set()
        self._last_clip, self._installing, self._page = "", False, "download"
        self._player_win = None
        self._thumb_boxes, self._thumb_pending, self._thumb_queue = {}, set(), queue.Queue()
        threading.Thread(target=self._thumb_worker, daemon=True).start()
        self.sidebar = self.content = None

        self._build_ui()
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<Control-v>", self._shortcut_paste)
        self.bind("<Control-V>", self._shortcut_paste)
        self.bind("<Control-l>", lambda e: self._focus_url())
        for i, key in enumerate(("download", "library", "settings"), start=1):
            self.bind(f"<Control-Key-{i}>", lambda e, k=key: self.show_page(k))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self.after(400, self.refresh_deps)

    # ------------------------------------------------------------------ estrutura
    def _build_ui(self):
        self.title(f"{t('app_name')}  {__version__}")
        for w in (self.sidebar, self.content):
            if w is not None:
                w.destroy()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages = {"download": DownloadPage(self.content, self)}
        self.pages["library"] = LibraryPage(self.content, self)
        self.pages["settings"] = SettingsPage(self.content, self)
        self.toast = Toast(self.content)
        self.cards = {}
        for jid in sorted(self.downloader.jobs):
            if jid not in self.hidden_jobs:
                self._ensure_card(asdict(self.downloader.jobs[jid]))
        self._update_counts()
        self.show_page(self._page)

    def show_page(self, key, section=None):
        self._page = key
        for k, p in self.pages.items():
            if k == key:
                p.grid(row=0, column=0, sticky="nsew", padx=SP["xxl"], pady=SP["xl"])
            else:
                p.grid_remove()
        self.sidebar.select(key)
        if key == "settings" and section:
            self.pages["settings"].show(section)

    def change_language(self, label):
        code = next((c for c, name in i18n.LANGUAGES.items() if name == label), i18n.DEFAULT)
        if code == i18n.current():
            return
        self.settings.language = code
        self.save()
        i18n.set_language(code)
        self._build_ui()
        self.show_page("settings", "general")
        self.refresh_deps()

    def save(self):
        try:
            self.settings.save()
        except Exception as e:
            log.exception("save settings")
            self.toast.show(t("save_error", err=e), "error")

    def _bg(self, func, callback):
        """Roda func() em segundo plano e chama callback(resultado) na thread principal."""
        def work():
            try:
                result = func()
            except Exception:
                log.exception("background task")
                result = None
            self.events.put(("call", (callback, result)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ baixar
    def _focus_url(self):
        self.show_page("download")
        self.pages["download"].url.focus_set()

    def _shortcut_paste(self, event=None):
        """Ctrl+V fora de um campo de texto: cola o link e já começa a baixar."""
        focus = self.focus_get()
        if focus is not None and focus.winfo_class() in ("Entry", "Text", "TEntry"):
            return None
        self.show_page("download")
        self.pages["download"].paste()
        self.start_download()
        return "break"

    def _on_focus(self, _event=None):
        page = self.pages.get("download")
        if not page or not self.settings.watch_clipboard or page.url.get().strip():
            return
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return
        if clip and clip != self._last_clip and URL_RE.match(clip) and YT_RE.search(clip):
            self._last_clip = clip
            page.url.insert(0, clip)

    def start_download(self):
        page = self.pages["download"]
        urls = URL_RE.findall(page.url.get().strip())
        if not urls:
            page.show_error(t("invalid_url"))
            page.url.focus_set()
            return
        s = self.settings
        quality, playlist, subs = s.quality, s.playlist, s.subtitles

        page.show_error("")

        def go():
            page.url.delete(0, "end")
            self.enqueue(urls, quality, playlist, subs)
        self.with_browser_check(go)

    def with_browser_check(self, proceed, test=False):
        """Se o navegador do login bloqueia os cookies e está aberto, pergunta antes (sem travar a janela)."""
        key = self.settings.browser
        b = browsers.BROWSERS.get(key)
        if not b or not b.locks_cookies:
            proceed()
            return

        def after_check(running):
            if not running:
                proceed()
                return
            buttons = [(t("btn_cancel"), None, "secondary")]
            if not test:
                buttons.append((t("btn_download_anyway"), "anyway", "secondary"))
            buttons.append((t("btn_close_and_test" if test else "btn_close_and_download"), "close", "primary"))
            choice = ChoiceDialog(self, t("app_name"), t("browser_open_heading", name=b.label),
                                  t("browser_open_msg"), buttons, icon="warning", icon_color=C["warning"]).show()
            if choice == "anyway":
                proceed()
            elif choice == "close":
                self.toast.show(t("closing_browser", name=b.label), "info", 3000)
                self._bg(lambda: self._close_and_wait(key), lambda _r: proceed())
        self._bg(lambda: browsers.is_running(key), after_check)

    @staticmethod
    def _close_and_wait(key):
        browsers.close_browser(key)
        for _ in range(20):          # espera o processo sumir (até ~6 s) sem travar a interface
            if not browsers.is_running(key):
                break
            time.sleep(0.3)
        time.sleep(0.5)

    def enqueue(self, urls, quality, playlist, subtitles, overwrite=False):
        for url in urls:
            job = self.downloader.add(url, quality, playlist, subtitles, overwrite=overwrite)
            self._ensure_card(asdict(job))
        self._update_counts()

    def _ensure_card(self, job):
        if job["id"] in self.hidden_jobs:
            return
        card = self.cards.get(job["id"])
        page = self.pages["download"]
        if card is None:
            page.empty.grid_remove()
            card = JobCard(page.list, self, job)
            self.cards[job["id"]] = card
            self._regrid()
        else:
            card.update_job(job)

    def _regrid(self):
        page = self.pages["download"]
        for i, jid in enumerate(sorted(self.cards, reverse=True)):
            self.cards[jid].grid(row=i + 1, column=0, sticky="ew", pady=(0, SP["sm"]))
        if not self.cards:
            page.empty.grid(row=0, column=0, pady=SP["xl"])

    def remove_job_card(self, job_id):
        self.hidden_jobs.add(job_id)
        card = self.cards.pop(job_id, None)
        if card:
            card.destroy()
        self._regrid()
        self._update_counts()

    def clear_finished(self):
        for jid, card in list(self.cards.items()):
            if card.job["state"] in ("done", "error", "cancelled"):
                self.remove_job_card(jid)

    def _update_counts(self):
        active = sum(1 for j in self.downloader.jobs.values() if j.state in ("queued", "downloading", "processing"))
        self.sidebar.items["download"].set_count(active)
        self.pages["download"].set_count(len(self.cards))

    # ------------------------------------------------------------------ pasta
    def set_output(self, path):
        path = (path or "").strip()
        if path:
            self.settings.output_dir = path
            self.save()
            self.pages["download"].refresh_folder()
            self.pages["settings"].set_output_text(path)

    def choose_output(self):
        s = self.settings
        initial = s.output_dir if os.path.isdir(s.output_dir) else os.path.expanduser("~")
        path = filedialog.askdirectory(title=t("choose_folder_title"), initialdir=initial)
        if path:
            self.set_output(os.path.normpath(path))
            self.toast.show(t("folder_changed"), "success", 2500)

    # ------------------------------------------------------------------ biblioteca
    def show_history_thumb(self, box, entry, path, exists):
        thumb = entry.get("thumb")
        if thumb and os.path.isfile(thumb):
            box.set_path(thumb)
            return
        key = thumbs.key_for("file:" + path) if path else ""
        cached = thumbs.cached(key)
        if cached:
            box.set_path(cached)
        elif exists and deps.find("ffmpeg"):
            self._thumb_boxes.setdefault(key, []).append(box)
            if key not in self._thumb_pending:
                self._thumb_pending.add(key)
                self._thumb_queue.put((key, path))

    def _thumb_worker(self):
        while True:
            key, path = self._thumb_queue.get()
            try:
                result = thumbs.from_file(path, key)
            except Exception:
                log.exception("thumb")
                result = None
            self.events.put(("thumb_ready", (key, result)))

    def play_media(self, path, title="", thumb=None):
        if not path or not os.path.isfile(path):
            self.toast.show(t("player_file_missing"), "warning")
            return
        if not player.available():
            choice = ChoiceDialog(self, t("app_name"), t("vlc_heading"), t("vlc_msg"),
                                  [(t("btn_cancel"), None, "secondary"),
                                   (t("btn_open_external"), "external", "secondary"),
                                   (t("btn_install_vlc"), "install", "primary")], icon="play").show()
            if choice == "external":
                open_path(path)
            elif choice == "install":
                if deps.has_winget():
                    self.run_dep_task("install", ["vlc"])
                    self.toast.show(t("player_vlc_installing"), "info", 6000)
                else:
                    webbrowser.open(deps.COMPONENTS["vlc"].site)
            return
        if self._player_win is not None and self._player_win.winfo_exists():
            self._player_win.close()
        try:
            cover = load_image(thumb, (320, 180)) if thumb else None
            self._player_win = player.PlayerWindow(self, path, title, cover, on_open_external=open_path)
            apply_icon(self._player_win)
        except Exception as e:
            log.exception("player")
            self.toast.show(t("player_error", err=e).split("\n")[0], "error")
            open_path(path)

    def redownload(self, entry):
        url, quality = entry.get("url"), entry.get("quality", "best")
        if not url:
            return
        path = entry.get("filepath", "")
        overwrite = False
        if path and os.path.isfile(path):
            choice = ChoiceDialog(self, t("redl_title"), t("redl_heading"), t("redl_message"),
                                  [(t("btn_cancel"), None, "secondary"), (t("btn_play"), "play", "secondary"),
                                   (t("btn_replace"), "replace", "primary")], detail=path, icon="retry").show()
            if choice is None:
                return
            if choice == "play":
                self.play_media(path, entry.get("title", ""), entry.get("thumb"))
                return
            overwrite = True

        def go():
            self.enqueue([url], quality, False, self.settings.subtitles, overwrite=overwrite)
            self.show_page("download")
        self.with_browser_check(go)

    def delete_entry(self, entry):
        path = entry.get("filepath", "")
        exists = bool(path) and os.path.isfile(path)
        buttons = [(t("btn_cancel"), None, "secondary"), (t("btn_only_list"), "list", "secondary")]
        if exists:
            buttons.append((t("btn_delete_file"), "file", "danger"))
        choice = ChoiceDialog(self, t("del_title"), t("del_question"), entry.get("title") or entry.get("url", ""),
                              buttons, detail=path if exists else t("del_no_file"),
                              warning=t("del_warning") if exists else "", icon="delete",
                              icon_color=C["error"]).show()
        if choice is None:
            return
        if choice == "file":
            try:
                send_to_trash(path)
            except Exception as e:
                log.exception("delete")
                ChoiceDialog(self, t("app_name"), t("delete_error_heading"), str(e), [(t("btn_ok"), None, "accent")],
                             detail=path, icon="error", icon_color=C["error"]).show()
                return
            self.toast.show(t("deleted_to_trash", name=os.path.basename(path)), "success")
        else:
            self.toast.show(t("removed_from_list"), "info")
        remove_history(entry)
        self.pages["library"].refresh()

    def clear_history(self):
        head, msg = split_msg("clear_history_confirm")
        if ChoiceDialog(self, t("app_name"), head, msg, [(t("btn_cancel"), None, "secondary"),
                                                       (t("btn_clear_history"), "ok", "danger")],
                        icon="delete", icon_color=C["error"]).show():
            save_history([])
            self.pages["library"].refresh()

    # ------------------------------------------------------------------ login
    def login_tip_text(self):
        key = self.settings.browser
        b = browsers.BROWSERS.get(key)
        if key == "file":
            tip = t("tip_file")
        elif b is None:
            tip = t("tip_none")
        elif b.locks_cookies:
            tip = t("tip_locking", name=b.label) + "\n" + t("tip_fallback")
        else:
            tip = t("tip_open_ok", name=b.label)
        return tip + "\n" + t("tip_when_needed")

    def test_login(self):
        key, page = self.settings.browser, self.pages["settings"]
        if key == "none":
            page.set_login_result(None, t("choose_browser_first"))
            return
        if key == "file" and not self.settings.cookies_file:
            page.set_login_result(None, t("choose_cookie_file"))
            return

        def run():
            page.set_login_result(None, t("testing"))
            cookie_file = self.settings.cookies_file if key == "file" else ""
            self._bg(lambda: browsers.test_cookies("" if key == "file" else key, cookie_file),
                     lambda r: r and page.set_login_result(r[0], t(r[1], **r[2])))
        self.with_browser_check(run, test=True)

    # ------------------------------------------------------------------ componentes
    def missing(self):
        st = deps.status()
        out = []
        if not st["ffmpeg"]:
            out.append("ffmpeg")
        if not st["deno"] and not st["node"]:
            out.append("deno")
        return out

    def refresh_deps(self):
        deps.refresh_path()
        st = deps.status()
        self.pages["settings"].update_deps(st, self._installing)
        miss = self.missing()
        names = ", ".join(deps.COMPONENTS[m].label for m in miss)
        self.pages["download"].set_banner(t("missing_banner", names=names) if miss else "", self._installing)

    def install_missing(self):
        self.run_dep_task("install", self.missing())

    def dep_action(self, name):
        if self._installing:
            return
        if deps.find(name):
            head, msg = split_msg(f"uninstall_confirm_{name}")
            if ChoiceDialog(self, t("app_name"), head, msg, [(t("btn_cancel"), None, "secondary"),
                                                           (t("btn_uninstall"), "ok", "danger")],
                            icon="delete", icon_color=C["error"]).show():
                self.run_dep_task("uninstall", [name])
        elif not deps.has_winget():
            webbrowser.open(deps.COMPONENTS[name].site)
        elif name == "node":
            head, msg = split_msg("install_node_confirm")
            if ChoiceDialog(self, t("app_name"), head, msg, [(t("btn_cancel"), None, "secondary"),
                                                           (t("btn_install"), "ok", "accent")], icon="puzzle").show():
                self.run_dep_task("install", [name])
        else:
            self.run_dep_task("install", [name])

    def run_dep_task(self, action, names):
        if not names or self._installing:
            return
        if not deps.has_winget():
            head, msg = split_msg("no_winget")
            ChoiceDialog(self, t("app_name"), head, msg, [(t("btn_ok"), None, "accent")], icon="warning",
                         icon_color=C["warning"]).show()
            return
        self._installing = True
        self.refresh_deps()
        labels = ", ".join(deps.COMPONENTS[n].label for n in names)
        msg = t("installing" if action == "install" else "uninstalling", names=labels)
        self.pages["settings"].log_line(msg)
        self.toast.show(msg, "info", 5000)

        def work():
            for n in names:
                label = deps.COMPONENTS[n].label
                out = lambda line: self.events.put(("install_log", line))  # noqa: E731
                try:
                    if action == "install":
                        ok = deps.install(n, out)
                        text = t("installed_ok" if ok else "installed_fail", name=label)
                    else:
                        ok = deps.uninstall(n, out)
                        text = t("uninstalled_ok", name=label) if ok else \
                            t("uninstalled_fail", name=label, path=deps.find(n) or "?")
                except Exception as e:
                    log.exception("dep task")
                    ok, text = False, f"{label}: {e}"
                self.events.put(("install_log", text))
                self.events.put(("install_result", (ok, text)))
            self.events.put(("install_done", action))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ atualizações
    def check_updates(self):
        def fetch():
            req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                         headers={"Accept": "application/vnd.github+json",
                                                  "User-Agent": "VidNeon"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.load(r)
                return data.get("tag_name", ""), data.get("html_url", "")
            except Exception as e:
                return "", str(e)
        self.toast.show(t("checking_updates"), "info", 2500)
        self._bg(fetch, lambda r: self._on_update(*(r or ("", "?"))))

    def _on_update(self, tag, info):
        self.toast.hide()
        if not tag:
            ChoiceDialog(self, t("app_name"), t("update_heading_err"), info, [(t("btn_ok"), None, "accent")],
                         icon="warning", icon_color=C["warning"]).show()
        elif version_tuple(tag) > version_tuple(__version__):
            if ChoiceDialog(self, t("app_name"), t("update_heading_new", tag=tag), t("update_msg_new", v=__version__),
                            [(t("btn_cancel"), None, "secondary"), (t("btn_download_update"), "ok", "primary")],
                            icon="update").show():
                webbrowser.open(info)
        else:
            self.toast.show(t("up_to_date", v=__version__), "success")

    # ------------------------------------------------------------------ eventos
    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                try:
                    self._handle(kind, data)
                except Exception:
                    log.exception("event %s", kind)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, kind, data):
        if kind == "job":
            self._ensure_card(data)
            if data["state"] in ("done", "error", "cancelled") or data["status"] == "st_starting":
                self._update_counts()
            if data["state"] == "done":
                self.toast.show(t("done_status", title=(data["title"] or data["url"])[:70]), "success")
                if self.focus_displayof() is None:
                    flash_window(self)
            elif data["state"] == "error":
                self.toast.show(t("failed_status"), "error")
                if self.focus_displayof() is None:
                    flash_window(self)
        elif kind == "log":
            log.info("yt-dlp: %s", data)
        elif kind == "history":
            self.pages["library"].refresh()
        elif kind == "call":
            callback, result = data
            callback(result)
        elif kind == "install_log":
            self.pages["settings"].log_line(data)
        elif kind == "install_result":
            ok, text = data
            self.toast.show(text, "success" if ok else "warning", 5000)
        elif kind == "install_done":
            self._installing = False
            player.reset()
            self.refresh_deps()
            if data == "install" and not self.missing():
                self.pages["settings"].log_line(t("all_ready"))
        elif kind == "thumb_ready":
            key, path = data
            self._thumb_pending.discard(key)
            for box in self._thumb_boxes.pop(key, []):
                if path and box.winfo_exists():
                    box.set_path(path)

    def _on_tk_error(self, exc, val, tb):
        log.error("Tk callback error", exc_info=(exc, val, tb))

    def _on_close(self):
        if self.downloader.busy():
            if not ChoiceDialog(self, t("app_name"), t("close_busy"), "", [(t("btn_cancel"), None, "secondary"),
                                                                           (t("btn_close_anyway"), "ok", "danger")],
                                icon="warning", icon_color=C["warning"]).show():
                return
        self.save()
        self.destroy()
