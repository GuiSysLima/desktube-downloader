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
from ..motion import resolve
from ..player import fmt_time
from ..theme import C, RADIUS, SP, THUMB_SM, font, glyph, icon_font
from ..widgets import IconButton, LightRow, ThumbBox, Tooltip, button, load_image
from .common import context_menu, ellipsize


# =========================================================================== fila (painel direito)
VISIBLE = 40          # itens da fila desenhados por vez ("Mostrar mais" desenha o próximo bloco)
DRAG_START = 6        # px que o mouse precisa andar para começar a arrastar (evita arrastar sem querer)
EDGE = 28             # px perto da borda da lista que fazem ela rolar durante o arraste


class QueueRow(LightRow):
    """Linha da fila (Tk puro, ver LightRow). As linhas são REAPROVEITADAS: set_item só troca o
    conteúdo, então mudar a fila não recria widgets."""

    def __init__(self, master, page, current=False):
        super().__init__(master)
        self.page, self.index, self.item, self.current, self._thumb = page, None, None, current, None
        self.grid_columnconfigure(2, weight=1)
        self.grip = self.label(text="", icon_size=11, fg=C["text2"], width=2, anchor="center")
        self.grip.grid(row=0, column=0, rowspan=2, padx=(self.px(2), 0))
        self.box = self.thumb(size=THUMB_SM)
        self.box.grid(row=0, column=1, rowspan=2, padx=(self.px(4), self.px(8)), pady=self.px(4))
        self.title = self.label(text="", kind="row")
        self.title.grid(row=0, column=2, sticky="sew")
        self.sub = self.label(text="", kind="meta", fg=C["text2"])
        self.sub.grid(row=1, column=2, sticky="new")
        self.remove = None
        if not current:
            self.remove = self.label(text="", icon_size=9, fg=C["text2"], width=3, anchor="center", cursor="hand2")
            self.remove.grid(row=0, column=3, rowspan=2, padx=(0, self.px(4)), sticky="ns")
            self.remove.bind("<Button-1>", lambda e: self.index is not None and page.app.playback.remove(self.index))
            Tooltip(self.remove, t("tip_remove_queue"))
        self.bind_parts(double_click=lambda: self.index is not None and page.app.playback.jump(self.index),
                        right_click=lambda e: page.row_menu(self, e))
        if not current:
            page.enable_drag(self)

    def set_item(self, index, item):
        self.index = index
        if item is self.item and item.get("thumb") == self._thumb:
            return
        self.item, self._thumb = item, item.get("thumb")
        self.title.configure(text=ellipsize(item["title"], 29))
        self.set_fg(self.title, C["accent_text"] if self.current else C["text"])
        self.sub.configure(text=ellipsize(item.get("artist") or t("kind_" + item["kind"]), 42))
        self.box.reset(item["kind"] == "audio")
        if item.get("thumb"):
            self.box.set_path(item["thumb"])

    def _enter(self, _e=None):
        super()._enter(_e)
        if not self.current:
            self.grip.configure(text=glyph("drag"), cursor="fleur")
            self.remove.configure(text=glyph("cancel"))

    def _leave(self, _e=None):
        super()._leave(_e)
        if not self.current and not self._hot:
            self.grip.configure(text="", cursor="")
            self.remove.configure(text="")

    def drag_widgets(self):
        return (self, self.grip, self.box, self.box.label, self.title, self.sub)


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
        self.count = ctk.CTkLabel(head, text="", font=font("meta"), text_color=C["text2"])
        self.count.pack(side="left", padx=SP["sm"])
        button(head, t("btn_clear_queue"), "ghost", lambda: app.playback and app.playback.clear_upcoming(),
               kind="meta", height=26, text_color=C["text2"]).pack(side="right")
        ctk.CTkLabel(self.side, text=t("now_playing").upper(), font=font("small"), text_color=C["text2"],
                     anchor="w").grid(row=1, column=0, sticky="ew", pady=(SP["md"], SP["xs"]))
        self.now = QueueRow(self.side, self, current=True)
        self.next_label = ctk.CTkLabel(self.side, text=t("up_next").upper() + "  ·  " + t("drag_hint"),
                                       font=font("small"), text_color=C["text2"], anchor="w")
        self.next_label.grid(row=3, column=0, sticky="ew", pady=(SP["lg"], SP["xs"]))
        self.list = ctk.CTkScrollableFrame(self.side, fg_color="transparent")
        self.list.grid(row=4, column=0, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self.rows = []
        self.empty_q = ctk.CTkLabel(self.list, text=t("queue_play_empty"), font=font("meta"), text_color=C["text2"])
        self.more = button(self.list, "", "ghost", self._show_more, kind="meta", height=28, text_color=C["text2"])
        self.indicator = tk.Frame(self.list, height=2, bd=0, highlightthickness=0, bg=resolve(C["accent"]))
        self._limit, self._stage_sig, self._q_sig = VISIBLE, None, None
        self._drag, self._scroll_job = None, None
        self._immersive = False
        self.refresh()

    def video_handle(self):
        self.video.update_idletasks()
        return self.video.winfo_id()

    # ---------------------------------------------------------------- atualização (só o que mudou)
    def refresh(self, force=False):
        pb = self.app.playback
        cur = pb.current if pb else None
        stage = (cur["path"], cur.get("thumb"), cur["kind"], cur["title"]) if cur else None
        if force or stage != self._stage_sig:
            self._stage_sig = stage
            self._refresh_stage(cur)
        queue = pb.queue if pb else []
        start = pb.index + 1 if cur is not None else 0
        visible = queue[start:start + self._limit]
        sig = (pb.index if pb else -1, len(queue), self._limit,
               tuple((id(i), i.get("thumb")) for i in visible))
        if self._drag and self._drag["active"]:
            return                                   # não mexe nas linhas enquanto o usuário arrasta
        if not force and sig == self._q_sig:
            return
        self._q_sig = sig
        if cur is not None:
            self.now.set_item(pb.index, cur)
            self.now.grid(row=2, column=0, sticky="ew")
        else:
            self.now.grid_remove()
        while len(self.rows) < len(visible):              # cria só as linhas que faltam
            row = QueueRow(self.list, self)
            row.grid(row=len(self.rows), column=0, sticky="ew")
            self.rows.append(row)
        for k, row in enumerate(self.rows):
            if k < len(visible):
                row.set_item(start + k, visible[k])
                if not row.winfo_manager():
                    row.grid()
            elif row.winfo_manager():
                row.grid_remove()
        rest = len(queue) - start - len(visible)
        if rest > 0:
            self.more.configure(text=t("btn_load_more", n=rest))
            self.more.grid(row=len(self.rows) + 1, column=0, pady=SP["sm"])
        else:
            self.more.grid_remove()
        if visible:
            self.empty_q.grid_remove()
        else:
            self.empty_q.grid(row=0, column=0, pady=SP["lg"])
        upcoming = len(queue) - start
        self.count.configure(text=t("n_items", n=upcoming) if upcoming > 0 else "")

    def _refresh_stage(self, cur):
        if cur is None:
            self.cover.place_forget()
            self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)
        elif cur["kind"] == "audio":
            self.empty.place_forget()
            img = load_image(cur.get("thumb"), (480, 270)) if cur.get("thumb") else None
            self.cover_img.configure(image=img or "", text="" if img else "♪",
                                     font=font("title", size=72) if not img else font("body"))
            self.cover_title.configure(text=cur["title"])
            self.cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self.empty.place_forget()
            self.cover.place_forget()

    def _show_more(self):
        self._limit += VISIBLE
        self.refresh()

    # ---------------------------------------------------------------- menu de contexto
    def row_menu(self, row, event):
        pb = self.app.playback
        if not pb or row.index is None:
            return
        i = row.index
        entries = [(t("menu_play"), lambda: pb.jump(i))]
        if not row.current:
            entries += [(t("menu_move_top"), lambda: pb.move(i, pb.index + 1), i > pb.index + 1),
                        None, (t("tip_remove_queue"), lambda: pb.remove(i))]
        context_menu(self, entries, event=event)

    # ---------------------------------------------------------------- arrastar para reordenar
    def enable_drag(self, row):
        for w in row.drag_widgets():
            w.bind("<ButtonPress-1>", lambda e, r=row: self._drag_start(r, e), add="+")
            w.bind("<B1-Motion>", self._drag_motion, add="+")
            w.bind("<ButtonRelease-1>", self._drag_end, add="+")

    def _drag_start(self, row, e):
        if row.index is None:
            return
        self._drag = {"row": row, "from": row.index, "y0": e.y_root, "y": e.y_root, "active": False, "to": None}

    def _visible_rows(self):
        return [r for r in self.rows if r.winfo_manager() and r.index is not None]

    def _drag_motion(self, e):
        d = self._drag
        if not d:
            return
        d["y"] = e.y_root
        if not d["active"]:
            if abs(e.y_root - d["y0"]) < DRAG_START:
                return
            d["active"] = True
            d["row"].tint(C["accent_soft"])
            self.indicator.configure(bg=resolve(C["accent"]))
            self._autoscroll()
        rows = self._visible_rows()
        if not rows:
            return
        slot = next((k for k, r in enumerate(rows) if e.y_root < r.winfo_rooty() + r.winfo_height() / 2),
                    len(rows))
        if slot < len(rows):
            y, ins = rows[slot].winfo_y(), rows[slot].index
        else:
            last = rows[-1]
            y, ins = last.winfo_y() + last.winfo_height(), last.index + 1
        i = d["from"]
        d["to"] = ins if ins <= i else ins - 1          # posição final do item depois de tirado do lugar
        self.indicator.place(x=SP["sm"], y=max(0, y - 1), relwidth=1, width=-2 * SP["sm"], height=2)
        self.indicator.lift()

    def _autoscroll(self):
        """Enquanto arrasta perto da borda de cima/baixo, a lista rola sozinha."""
        d = self._drag
        if not d or not d["active"]:
            self._scroll_job = None
            return
        canvas = self.list._parent_canvas
        top = canvas.winfo_rooty()
        bottom = top + canvas.winfo_height()
        if d["y"] < top + EDGE:
            canvas.yview_scroll(-1, "units")
        elif d["y"] > bottom - EDGE:
            canvas.yview_scroll(1, "units")
        self._scroll_job = self.after(40, self._autoscroll)

    def _drag_end(self, _e=None):
        d, self._drag = self._drag, None
        if self._scroll_job:
            self.after_cancel(self._scroll_job)
            self._scroll_job = None
        self.indicator.place_forget()
        if not d or not d["active"]:
            return
        d["row"].tint(None)
        pb, i, j = self.app.playback, d["from"], d["to"]
        if pb and j is not None and j != i:
            pb.move(i, j)
            self.after(60, lambda: self._flash(j))      # mostra onde o item foi parar

    def _flash(self, index):
        self.refresh()
        row = next((r for r in self._visible_rows() if r.index == index), None)
        if row is not None:
            row.flash(C["accent_soft"])

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
        self.queue_btn = IconButton(right, "queue", t("tip_queue"), size=30, icon_size=13,
                                    command=app.toggle_queue_page)
        self.queue_btn.pack(side="left", padx=SP["xs"])
        self.mute = IconButton(right, "volume", t("tip_mute"), size=30, icon_size=13, command=self._mute)
        self.mute.pack(side="left")
        self.volume = ctk.CTkSlider(right, from_=0, to=100, width=96, height=14, command=self._volume)
        self.volume.set(app.settings.volume)
        self.volume.pack(side="left", padx=SP["xs"])
        self.full = IconButton(right, "fullscreen", t("tip_fullscreen"), size=30, icon_size=13,
                               command=app.toggle_fullscreen)
        self.full.pack(side="left", padx=SP["xs"])
        self._before_mute = app.settings.volume
        self._last = {}

    def _set(self, key, value, apply):
        """Só reconfigura o widget se o valor mudou (cada configure redesenha um widget do CTk)."""
        if self._last.get(key) != value:
            self._last[key] = value
            apply(value)

    def set_queue_active(self, on):
        self._set("queue", on, lambda v: self.queue_btn.configure(text_color=C["accent_text"] if v else C["text"]))

    def set_fullscreen(self, on):
        self.full.set_icon("exit_fullscreen" if on else "fullscreen")
        if self.full.tooltip:
            self.full.tooltip.set_text(t("tip_exit_fullscreen") if on else t("tip_fullscreen"))

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
        self._set("shuffle", pb.shuffle,
                  lambda v: self.shuffle.configure(text_color=C["accent_text"] if v else C["text2"]))
        self._set("repeat", pb.repeat, lambda v: (
            self.repeat.set_icon("repeat_one" if v == "one" else "repeat"),
            self.repeat.configure(text_color=C["accent_text"] if v != "off" else C["text2"])))
        self._set("full", cur["kind"] == "video",
                  lambda v: self.full.configure(state="normal" if v else "disabled"))

    def tick(self):
        pb = self.app.playback
        if not pb or pb.current is None:
            return
        now, length = pb.position()
        if not self._dragging and length > 0:
            self._set("seek", round(1000 * now / length), self.seek.set)
            self._set("now", fmt_time(now), lambda v: self.t_now.configure(text=v))
        self._set("len", fmt_time(length), lambda v: self.t_len.configure(text=v))
        self._set("play", "pause" if pb.is_playing() else "play", self.play.set_icon)
