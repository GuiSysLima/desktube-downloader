# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Página Baixar: campo de link, opções e fila de downloads (lista com divisórias)."""
import os

import customtkinter as ctk

from .. import browsers, motion
from ..downloader import QUALITIES
from ..i18n import t
from ..theme import C, CONTROL_H, CTA_H, RADIUS, SP, THUMB, font, glyph
from ..widgets import HoverRow, IconButton, ThumbBox, button, divider, icon_label
from .common import AUDIO_Q, VIDEO_Q, ellipsize, quality_label, reveal


class JobRow(HoverRow):
    """Um item da fila de downloads."""

    def __init__(self, master, app, job):
        super().__init__(master, corner_radius=RADIUS["card"])
        self.app, self.job, self._indeterminate = app, job, False
        self.grid_columnconfigure(1, weight=1)
        self.thumb = ThumbBox(self, audio=job["quality"] in AUDIO_Q, size=THUMB)
        self.thumb.grid(row=0, column=0, rowspan=3, padx=(SP["sm"], SP["md"]), pady=SP["sm"])
        self.title = ctk.CTkLabel(self, text=job["url"], font=font("label"), anchor="w")
        self.title.grid(row=0, column=1, sticky="sew", pady=(SP["sm"], 0))
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=1, column=1, sticky="ew")
        info.grid_columnconfigure(1, weight=1)
        self.status_icon = ctk.CTkLabel(info, text="", width=14)
        self.status = ctk.CTkLabel(info, text="", font=font("meta"), text_color=C["text2"], anchor="w",
                                   justify="left", wraplength=520)
        self.status.grid(row=0, column=1, sticky="w")
        self.speed = ctk.CTkLabel(info, text="", font=font("meta"), text_color=C["text2"], anchor="e")
        self.speed.grid(row=0, column=2, sticky="e", padx=(SP["sm"], 0))
        self.bar = ctk.CTkProgressBar(self, height=3, corner_radius=2, mode="determinate")
        self.bar.set(0)
        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.grid(row=0, column=2, rowspan=3, padx=SP["sm"])
        self.play_btn = IconButton(acts, "play", t("tip_play"), size=32, icon_size=14, command=self._play)
        self.folder_btn = IconButton(acts, "folder", t("tip_folder"), size=32, icon_size=14, command=self._folder)
        self.action_btn = IconButton(acts, "cancel", t("tip_cancel"), size=32, icon_size=12, command=self._action)
        self.bind_children()
        self.update_job(job)

    def _set_bar(self, mode, value=0.0, color=None):
        """Barra fina visível só enquanto o download está ativo."""
        if mode is None:
            if self._indeterminate:
                self.bar.stop()
                self._indeterminate = False
            self.bar.grid_remove()
            return
        self.bar.grid(row=2, column=1, sticky="ew", pady=(SP["xs"], SP["sm"]))
        if mode == "indeterminate" and not self._indeterminate:
            self.bar.configure(mode="indeterminate")
            self.bar.start()
            self._indeterminate = True
        elif mode == "determinate":
            if self._indeterminate:
                self.bar.stop()
                self.bar.configure(mode="determinate")
                self._indeterminate = False
            start = self.bar.get()
            if value > start:     # avança suavemente até o novo valor (sem "pulos")
                motion.animate(self.bar, "progress", motion.DUR["short"],
                               lambda p: self.bar.set(start + (value - start) * p), easing=motion.ease_out)
            else:
                motion.cancel(self.bar, "progress")
                self.bar.set(value)
        self.bar.configure(progress_color=color or C["accent"])

    def _status(self, text, icon=None, color=None):
        self.status.configure(text=text, text_color=color or C["text2"])
        if icon:
            from ..theme import icon_font
            self.status_icon.configure(text=glyph(icon), font=icon_font(11), text_color=color or C["text2"])
            self.status_icon.grid(row=0, column=0, padx=(0, SP["xs"]))
        else:
            self.status_icon.grid_remove()

    def update_job(self, job):
        self.job = job
        self.title.configure(text=ellipsize(job["title"] or job["url"], 90))
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
            self._status("  ·  ".join(x for x in (f"{job['progress'] * 100:.0f}%", t(job["status"]), item) if x))
            speed = "  ·  ".join(x for x in (job["speed"], t("eta", eta=job["eta"]) if job["eta"] else "") if x)
        elif state == "processing":
            self._set_bar("indeterminate")
            self._status(t(job["status"]))
        elif state == "done":
            self._set_bar(None)
            self._status(f"{t(job['status'])}  ·  {quality}", "check", C["success"])
        elif state == "error":
            self._set_bar(None)
            args = dict(job.get("error_args") or {})
            if job["error"] == "err_cookie_copy" and not args.get("browser"):
                args["browser"] = t("the_browser")
            self._status(t(job["error"], **args), "error", C["error"])
        elif state == "cancelled":
            self._set_bar(None)
            self._status(t("st_cancelled"))
        else:
            self._set_bar(None)
            self._status(f"{t('st_queued')}  ·  {quality}")
        self.speed.configure(text=speed)

        playable = state == "done" and bool(job.get("filepath")) and os.path.isfile(job["filepath"])
        for b in (self.play_btn, self.folder_btn, self.action_btn):
            b.pack_forget()
        if playable:
            self.play_btn.pack(side="left", padx=1)
            self.folder_btn.pack(side="left", padx=1)
            self.thumb.on_click(self._play)
        if state in ("queued", "downloading", "processing"):
            self.action_btn.set_icon("cancel")
            self.action_btn.tooltip.set_text(t("tip_remove") if state == "queued" else t("tip_cancel"))
            self.action_btn.pack(side="left", padx=1)
        elif state in ("error", "cancelled"):
            self.action_btn.set_icon("retry")
            self.action_btn.tooltip.set_text(t("tip_retry"))
            self.action_btn.pack(side="left", padx=1)

    def _play(self):
        self.app.play_file(self.job["filepath"], self.job["title"], self.job.get("thumb"), self.job["quality"])

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
            row=0, column=0, sticky="ew", pady=(0, SP["lg"]))

        # --- link
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        self.url = ctk.CTkEntry(bar, height=CTA_H, font=font("body", size=14), placeholder_text=t("url_placeholder"))
        self.url.grid(row=0, column=0, sticky="ew")
        self.url.bind("<Return>", lambda e: app.start_download())
        self.url.bind("<FocusIn>", lambda e: self.url.configure(border_color=C["accent"]))
        self.url.bind("<FocusOut>", lambda e: self.url.configure(border_color=C["input_border"]))
        self.url.bind("<KeyRelease>", lambda e: self.show_error(""))
        IconButton(bar, "paste", t("tip_paste"), "secondary", size=CTA_H, command=self.paste).grid(
            row=0, column=1, padx=(SP["sm"], 0))
        button(bar, t("btn_download"), "primary", app.start_download, width=120, height=CTA_H).grid(
            row=0, column=2, padx=(SP["sm"], 0))
        self.error = ctk.CTkLabel(bar, text="", font=font("meta"), text_color=C["error"], anchor="w")

        # --- opções (sem card)
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.grid(row=2, column=0, sticky="ew", pady=(SP["md"], 0))
        self.kind = ctk.CTkSegmentedButton(opts, values=[t("seg_video"), t("seg_audio")], height=32,
                                           font=font("body"), command=self._on_kind)
        self.kind.pack(side="left")
        self.quality = ctk.CTkOptionMenu(opts, width=180, height=32, font=font("body"), command=self._on_quality)
        self.quality.pack(side="left", padx=(SP["sm"], 0))
        self.playlist = ctk.CTkSwitch(opts, text=t("chk_playlist"), font=font("body"), command=self._on_option)
        self.playlist.pack(side="left", padx=(SP["xl"], 0))
        self.subs = ctk.CTkSwitch(opts, text=t("chk_subtitles"), font=font("body"), command=self._on_option)
        self.subs.pack(side="left", padx=(SP["lg"], 0))
        (self.playlist.select if s.playlist else self.playlist.deselect)()
        (self.subs.select if s.subtitles else self.subs.deselect)()
        self.login = button(opts, "", "ghost", lambda: app.show_page("settings", "login"), kind="meta",
                            text_color=C["text2"], height=28)
        self.login.pack(side="right")
        self._sync_quality_widgets()
        self.refresh_login()

        # --- aviso de componentes faltando (compacto)
        self.banner = ctk.CTkFrame(self, fg_color=C["warning_bg"], corner_radius=RADIUS["card"])
        icon_label(self.banner, "warning", 14, C["warning"]).pack(side="left", padx=(SP["md"], SP["sm"]),
                                                                   pady=SP["sm"])
        self.banner_text = ctk.CTkLabel(self.banner, text="", font=font("body"), anchor="w", justify="left")
        self.banner_text.pack(side="left", fill="x", expand=True, pady=SP["sm"])
        button(self.banner, t("btn_details"), "ghost", lambda: app.show_page("settings", "components"),
               kind="body", height=30).pack(side="right", padx=(0, SP["sm"]))
        self.banner_btn = button(self.banner, t("btn_install_now"), "accent", app.install_missing, kind="body",
                                 height=30)
        self.banner_btn.pack(side="right", padx=SP["xs"])

        # --- fila
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=4, column=0, sticky="ew", pady=(SP["xl"], SP["xs"]))
        ctk.CTkLabel(head, text=t("queue_title"), font=font("section")).pack(side="left")
        self.count = ctk.CTkLabel(head, text="", font=font("meta"), text_color=C["text2"])
        self.count.pack(side="left", padx=SP["sm"])
        button(head, t("btn_clear_finished"), "ghost", app.clear_finished, kind="meta", height=28,
               text_color=C["text2"]).pack(side="right")
        divider(self).grid(row=4, column=0, sticky="sew")
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=5, column=0, sticky="nsew", pady=(SP["xs"], 0))
        self.list.grid_columnconfigure(0, weight=1)
        self.empty = ctk.CTkFrame(self.list, fg_color="transparent")
        ctk.CTkLabel(self.empty, text=t("queue_empty"), font=font("body"), text_color=C["text2"]).pack()
        ctk.CTkLabel(self.empty, text=t("queue_empty_hint"), font=font("meta"), text_color=C["text_disabled"]).pack(
            pady=(SP["xs"], 0))
        self.empty.grid(row=0, column=0, pady=SP["xxl"])

        # --- pasta de destino (linha simples)
        divider(self).grid(row=6, column=0, sticky="ew", pady=(SP["sm"], 0))
        folder = ctk.CTkFrame(self, fg_color="transparent")
        folder.grid(row=7, column=0, sticky="ew", pady=(SP["sm"], 0))
        folder.grid_columnconfigure(1, weight=1)
        icon_label(folder, "folder", 14).grid(row=0, column=0, padx=(0, SP["sm"]))
        self.folder = ctk.CTkLabel(folder, text="", font=font("meta"), text_color=C["text2"], anchor="w")
        self.folder.grid(row=0, column=1, sticky="ew")
        button(folder, t("btn_open"), "ghost", lambda: reveal("", app.settings.output_dir), kind="meta",
               height=28).grid(row=0, column=2)
        button(folder, t("btn_change_folder"), "ghost", app.choose_output, kind="meta", height=28).grid(
            row=0, column=3)
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
        self.folder.configure(text=t("save_to") + "  " + (p if len(p) <= 80 else "…" + p[-79:]))

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
            self.error.grid(row=1, column=0, columnspan=3, sticky="w", pady=(SP["xs"], 0))
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
        self.count.configure(text=t("n_items", n=n) if n else "")
