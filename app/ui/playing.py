# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Reprodução estilo Spotify:
- PlayingPage: vídeo (ou capa, para áudio) à esquerda e a fila à direita.
- PlayerBar: barra fixa embaixo da janela com o que está tocando e os controles.
O motor (fila + VLC) é app/player.py (classe Playback)."""
import tkinter as tk

import customtkinter as ctk

from ..i18n import t
from ..player import fmt_time
from ..theme import C, RADIUS, SP, THUMB_SM, font
from ..widgets import HoverRow, IconButton, ThumbBox, button, load_image
from .common import ellipsize


# =========================================================================== fila (painel direito)
class QueueRow(HoverRow):
    def __init__(self, master, page, index, item, current=False):
        super().__init__(master)
        self.page, self.index = page, index
        self.grid_columnconfigure(1, weight=1)
        box = ThumbBox(self, audio=item["kind"] == "audio", size=THUMB_SM)
        box.grid(row=0, column=0, rowspan=2, padx=(SP["sm"], SP["sm"]), pady=SP["xs"])
        if item.get("thumb"):
            box.set_path(item["thumb"])
        ctk.CTkLabel(self, text=ellipsize(item["title"], 30), font=font("row"), anchor="w",
                     text_color=C["accent_text"] if current else C["text"]).grid(row=0, column=1, sticky="sew")
        ctk.CTkLabel(self, text=ellipsize(item.get("artist") or t("kind_" + item["kind"]), 40), font=font("meta"),
                     text_color=C["text2"], anchor="w").grid(row=1, column=1, sticky="new")
        if not current:
            acts = ctk.CTkFrame(self, fg_color="transparent")
            acts.grid(row=0, column=2, rowspan=2, padx=(0, SP["xs"]))
            IconButton(acts, "up", t("tip_move_up"), size=26, icon_size=10,
                       command=lambda: page.app.playback.move(index, index - 1)).pack(side="left")
            IconButton(acts, "down", t("tip_move_down"), size=26, icon_size=10,
                       command=lambda: page.app.playback.move(index, index + 1)).pack(side="left")
            IconButton(acts, "cancel", t("tip_remove_queue"), size=26, icon_size=9,
                       command=lambda: page.app.playback.remove(index)).pack(side="left")
        self.bind_children(double_click=lambda: page.app.playback.jump(index))


class PlayingPage(ctk.CTkFrame):
    QUEUE_W = 340

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.title = ctk.CTkLabel(self, text=t("nav_playing"), font=font("title"), anchor="w")
        self.title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SP["lg"]))

        # --- palco: vídeo (tk.Frame, necessário para o VLC desenhar) ou capa do áudio
        self.stage = ctk.CTkFrame(self, fg_color="#000000", corner_radius=RADIUS["card"])
        self.stage.grid(row=1, column=0, sticky="nsew")
        self.video = tk.Frame(self.stage, bg="#000000", highlightthickness=0)
        self.video.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.video.bind("<Button-1>", lambda e: app.playback and app.playback.toggle())
        self.video.bind("<Double-Button-1>", lambda e: app.toggle_fullscreen())
        self.cover = ctk.CTkFrame(self.stage, fg_color=C["sidebar"], corner_radius=RADIUS["card"])
        self.cover_img = ctk.CTkLabel(self.cover, text="")
        self.cover_img.place(relx=0.5, rely=0.42, anchor="center")
        self.cover_title = ctk.CTkLabel(self.cover, text="", font=font("section", size=18), wraplength=460)
        self.cover_title.place(relx=0.5, rely=0.78, anchor="center")
        self.empty = ctk.CTkFrame(self.stage, fg_color=C["card"], corner_radius=RADIUS["card"])
        inner = ctk.CTkFrame(self.empty, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(inner, text=t("playing_empty"), font=font("body"), text_color=C["text2"]).pack()
        button(inner, t("btn_go_library"), "secondary", lambda: app.show_page("library"), kind="body").pack(
            pady=SP["md"])

        # --- fila
        self.side = ctk.CTkFrame(self, fg_color="transparent", width=self.QUEUE_W)
        self.side.grid(row=1, column=1, sticky="ns", padx=(SP["xl"], 0))
        self.side.grid_propagate(False)
        self.side.grid_columnconfigure(0, weight=1)
        self.side.grid_rowconfigure(4, weight=1)
        head = ctk.CTkFrame(self.side, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(head, text=t("queue_play_title"), font=font("section")).pack(side="left")
        button(head, t("btn_clear_queue"), "ghost", lambda: app.playback and app.playback.clear_upcoming(),
               kind="meta", height=26, text_color=C["text2"]).pack(side="right")
        ctk.CTkLabel(self.side, text=t("now_playing").upper(), font=font("small"), text_color=C["text2"],
                     anchor="w").grid(row=1, column=0, sticky="ew", pady=(SP["md"], SP["xs"]))
        self.now = ctk.CTkFrame(self.side, fg_color="transparent")
        self.now.grid(row=2, column=0, sticky="ew")
        self.now.grid_columnconfigure(0, weight=1)
        self.next_label = ctk.CTkLabel(self.side, text=t("up_next").upper(), font=font("small"),
                                       text_color=C["text2"], anchor="w")
        self.next_label.grid(row=3, column=0, sticky="ew", pady=(SP["lg"], SP["xs"]))
        self.list = ctk.CTkScrollableFrame(self.side, fg_color="transparent")
        self.list.grid(row=4, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self._immersive = False
        self.refresh()

    def video_handle(self):
        self.video.update_idletasks()
        return self.video.winfo_id()

    def refresh(self):
        pb = self.app.playback
        cur = pb.current if pb else None
        # palco
        if cur is None:
            self.cover.place_forget()
            self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)
        elif cur["kind"] == "audio":
            self.empty.place_forget()
            img = load_image(cur.get("thumb"), (480, 270)) if cur.get("thumb") else None
            self.cover_img.configure(image=img, text="" if img else "♪",
                                     font=font("title", size=72) if not img else font("body"))
            self.cover_title.configure(text=cur["title"])
            self.cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self.empty.place_forget()
            self.cover.place_forget()
        # fila
        for w in list(self.now.winfo_children()) + list(self.list.winfo_children()):
            w.destroy()
        if cur is not None:
            QueueRow(self.now, self, pb.index, cur, current=True).grid(row=0, column=0, sticky="ew")
        upcoming = pb.upcoming if pb else []
        start = pb.index + 1 if cur is not None else 0
        for k, item in enumerate(upcoming):
            QueueRow(self.list, self, start + k, item).grid(row=k, column=0, sticky="ew")
        if not upcoming:
            ctk.CTkLabel(self.list, text=t("queue_play_empty"), font=font("meta"), text_color=C["text2"]).grid(
                row=0, column=0, pady=SP["lg"])

    def set_immersive(self, on):
        """Tela cheia: só o vídeo."""
        self._immersive = on
        if on:
            self.title.grid_remove()
            self.side.grid_remove()
            self.stage.configure(corner_radius=0)
        else:
            self.title.grid()
            self.side.grid()
            self.stage.configure(corner_radius=RADIUS["card"])


# =========================================================================== barra "tocando agora"
class PlayerBar(ctk.CTkFrame):
    def __init__(self, master, app):
        # barra "flutuante": cartão arredondado com margem, fixo no rodapé de todas as telas
        super().__init__(master, fg_color=C["player_bar"], corner_radius=RADIUS["card"] + 2, height=80,
                         border_width=1, border_color=C["divider"])
        self.app = app
        self._dragging = False
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=3, uniform="bar")
        self.grid_columnconfigure(1, weight=4, uniform="bar")
        self.grid_columnconfigure(2, weight=3, uniform="bar")
        self.grid_rowconfigure(1, weight=1)

        # esquerda: o que está tocando
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="w", padx=SP["lg"])
        self.thumb = ThumbBox(left, size=THUMB_SM)
        self.thumb.pack(side="left")
        self.thumb.on_click(lambda: app.show_page("playing"))
        txt = ctk.CTkFrame(left, fg_color="transparent")
        txt.pack(side="left", padx=SP["md"])
        self.title = ctk.CTkLabel(txt, text="", font=font("label"), anchor="w", cursor="hand2")
        self.title.pack(anchor="w")
        self.title.bind("<Button-1>", lambda e: app.show_page("playing"))
        self.sub = ctk.CTkLabel(txt, text="", font=font("meta"), text_color=C["text2"], anchor="w")
        self.sub.pack(anchor="w")

        # centro: controles + tempo
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=1, column=1)
        ctrls = ctk.CTkFrame(mid, fg_color="transparent")
        ctrls.pack()
        self.shuffle = IconButton(ctrls, "shuffle", t("tip_shuffle"), size=30, icon_size=13,
                                  command=lambda: app.playback.toggle_shuffle())
        self.shuffle.pack(side="left", padx=SP["xs"])
        IconButton(ctrls, "prev", t("tip_prev"), size=30, icon_size=13,
                   command=lambda: app.playback.prev()).pack(side="left", padx=SP["xs"])
        self.play = IconButton(ctrls, "pause", t("tip_play"), "accent", size=36, icon_size=14, corner_radius=18,
                               command=lambda: app.playback.toggle())
        self.play.pack(side="left", padx=SP["sm"])
        IconButton(ctrls, "next", t("tip_next"), size=30, icon_size=13,
                   command=lambda: app.playback.next()).pack(side="left", padx=SP["xs"])
        self.repeat = IconButton(ctrls, "repeat", t("tip_repeat"), size=30, icon_size=13,
                                 command=lambda: app.playback.cycle_repeat())
        self.repeat.pack(side="left", padx=SP["xs"])
        line = ctk.CTkFrame(mid, fg_color="transparent")
        line.pack(fill="x", pady=(2, 0))
        self.t_now = ctk.CTkLabel(line, text="0:00", font=font("small"), text_color=C["text2"], width=40)
        self.t_now.pack(side="left")
        self.seek = ctk.CTkSlider(line, from_=0, to=1000, number_of_steps=1000, width=250, height=14,
                                  command=self._drag)
        self.seek.set(0)
        self.seek.pack(side="left", padx=SP["xs"])
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        self.seek.bind("<ButtonRelease-1>", self._release)
        self.t_len = ctk.CTkLabel(line, text="0:00", font=font("small"), text_color=C["text2"], width=40)
        self.t_len.pack(side="left")

        # direita: fila, volume, tela cheia
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=2, sticky="e", padx=SP["lg"])
        IconButton(right, "queue", t("tip_queue"), size=30, icon_size=13,
                   command=lambda: app.show_page("playing")).pack(side="left", padx=SP["xs"])
        self.mute = IconButton(right, "volume", t("tip_mute"), size=30, icon_size=13, command=self._mute)
        self.mute.pack(side="left")
        self.volume = ctk.CTkSlider(right, from_=0, to=100, width=96, height=14, command=self._volume)
        self.volume.set(app.settings.volume)
        self.volume.pack(side="left", padx=SP["xs"])
        self.full = IconButton(right, "fullscreen", t("tip_fullscreen"), size=30, icon_size=13,
                               command=app.toggle_fullscreen)
        self.full.pack(side="left", padx=SP["xs"])
        self._before_mute = app.settings.volume

    # ---- interação
    def _drag(self, value):
        self._dragging = True
        pb = self.app.playback
        if pb:
            length = pb.position()[1]
            self.t_now.configure(text=fmt_time(length * value / 1000))

    def _release(self, _e=None):
        if self.app.playback:
            self.app.playback.seek(self.seek.get() / 1000)
        self._dragging = False

    def _volume(self, value):
        if self.app.playback:
            self.app.playback.set_volume(value)
        self.app.settings.volume = int(value)
        self.mute.set_icon("mute" if int(value) == 0 else "volume")

    def _mute(self):
        cur = int(self.volume.get())
        new = self._before_mute or 80 if cur == 0 else 0
        if cur:
            self._before_mute = cur
        self.volume.set(new)
        self._volume(new)
        self.app.save()

    # ---- atualização
    def refresh(self):
        pb = self.app.playback
        cur = pb.current if pb else None
        if cur is None:
            return
        self.title.configure(text=ellipsize(cur["title"], 23))
        self.sub.configure(text=ellipsize(cur.get("artist") or t("kind_" + cur["kind"]), 34))
        if self.thumb._path != (cur.get("thumb") or None):
            self.thumb.reset(cur["kind"] == "audio")
            if cur.get("thumb"):
                self.thumb.set_path(cur["thumb"])
        self.shuffle.configure(text_color=C["accent_text"] if pb.shuffle else C["text2"])
        self.repeat.set_icon("repeat_one" if pb.repeat == "one" else "repeat")
        self.repeat.configure(text_color=C["accent_text"] if pb.repeat != "off" else C["text2"])
        self.full.configure(state="normal" if cur["kind"] == "video" else "disabled")

    def tick(self):
        pb = self.app.playback
        if not pb or pb.current is None:
            return
        now, length = pb.position()
        if not self._dragging and length > 0:
            self.seek.set(1000 * now / length)
            self.t_now.configure(text=fmt_time(now))
        self.t_len.configure(text=fmt_time(length))
        self.play.set_icon("pause" if pb.is_playing() else "play")
