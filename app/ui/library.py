# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Página Biblioteca, no modelo do Spotify:
- aba "Tudo": lista estilo tracklist (#, título + canal, formato, data);
- aba "Playlists": playlists baixadas; ao abrir uma, cabeçalho com capa grande, tocar e "Alterar capa…".
"""
import os
import tkinter as tk

import customtkinter as ctk

from ..config import load_history
from ..i18n import t
from ..theme import C, CONTROL_H, SP, THUMB, THUMB_SM, font, glyph, tk_font, tk_icon_font
from ..widgets import HoverRow, IconButton, LightRow, TabBar, ThumbBox, Tooltip, button, divider
from .common import AUDIO_Q, ellipsize, reveal, short_quality

PAGE = 40                        # itens desenhados por vez ("Carregar mais")
COLS = (36, None, 90, 130, 44)   # larguras: #, título (flex), formato, data, ações
COVER = (192, 108)               # capa no cabeçalho da playlist


def _grid_cols(frame):
    for i, w in enumerate(COLS):
        if w is None:
            frame.grid_columnconfigure(i, weight=1)
        else:
            frame.grid_columnconfigure(i, minsize=w, weight=0)


# ---------------------------------------------------------------- dados
def artist_of(entry):
    """"Artista" = canal de onde veio o download (itens antigos não têm: fica vazio)."""
    return entry.get("channel") or ""


def playlist_of(entry, output_dir=""):
    """(chave, nome) da playlist do item, ou (None, None).
    Itens antigos (sem o campo) usam a subpasta da playlist dentro da pasta de destino."""
    if entry.get("playlist_id") or entry.get("playlist"):
        return entry.get("playlist_id") or entry["playlist"], entry.get("playlist") or entry["playlist_id"]
    folder = entry.get("folder") or os.path.dirname(entry.get("filepath", ""))
    if folder and output_dir and os.path.normcase(os.path.dirname(os.path.normpath(folder))) == \
            os.path.normcase(os.path.normpath(output_dir)):
        return "dir:" + os.path.normcase(os.path.normpath(folder)), os.path.basename(os.path.normpath(folder))
    return None, None


def group_playlists(items, output_dir=""):
    """Lista de playlists: [{key, name, items, channel, when, cover, folder}] (mais recentes primeiro)."""
    groups = {}
    for h in items:
        key, name = playlist_of(h, output_dir)
        if not key:
            continue
        g = groups.setdefault(key, {"key": key, "name": name, "items": [], "when": h.get("when", "")})
        g["items"].append(h)
    out = []
    for g in groups.values():
        chans = {artist_of(h) for h in g["items"] if artist_of(h)}
        g["channel"] = chans.pop() if len(chans) == 1 else ""
        g["cover"] = next((h["playlist_cover"] for h in g["items"] if h.get("playlist_cover")), "") or \
            next((h.get("thumb") for h in g["items"] if h.get("thumb")), "")
        folders = {os.path.dirname(h.get("filepath", "")) for h in g["items"] if h.get("filepath")}
        g["folder"] = folders.pop() if len(folders) == 1 else ""
        out.append(g)
    return out


def _exists(entry):
    p = entry.get("filepath", "")
    return bool(p) and os.path.isfile(p)


# ---------------------------------------------------------------- linhas
class LibraryRow(LightRow):
    """Linha da Biblioteca (Tk puro, ver LightRow: criar dezenas de linhas CTk deixava a lista lenta)."""

    def __init__(self, master, page, pos, entry, playing=False, show_playlist=True):
        super().__init__(master)
        self.page, self.entry, self.pos, self.playing = page, entry, pos, playing
        app = page.app
        _grid_cols(self)
        path = entry.get("filepath", "")
        self.exists = _exists(entry)
        # coluna #: número; no hover vira ▶
        self.num = self.label(text=str(pos + 1), kind="meta", anchor="center",
                              fg=C["accent_text"] if playing else C["text2"])
        self.num.grid(row=0, column=0, sticky="ew", padx=(SP["xs"], 0))
        # título + miniatura
        mid = self.frame()
        mid.grid(row=0, column=1, sticky="ew", pady=self.px(4))
        mid.grid_columnconfigure(1, weight=1)
        box = self.thumb(mid, size=THUMB_SM, audio=entry.get("quality") in AUDIO_Q)
        box.grid(row=0, column=0, rowspan=2, padx=(SP["sm"], SP["md"]))
        app.show_history_thumb(box, entry, path, self.exists)
        self.title = self.label(mid, text=ellipsize(entry.get("title") or entry.get("url", ""), 80), kind="row",
                                fg=C["accent_text"] if playing else (C["text"] if self.exists else C["text2"]))
        self.title.grid(row=0, column=1, sticky="sew")
        if self.exists:
            parts = [artist_of(entry)]
            if show_playlist:
                parts.append(playlist_of(entry, app.settings.output_dir)[1] or "")
            sub = "  ·  ".join(p for p in parts if p) or os.path.basename(os.path.dirname(path))
        else:
            sub = t("hist_missing_file")
        self.label(mid, text=ellipsize(sub, 90), kind="meta",
                   fg=C["text2"] if self.exists else C["warning"]).grid(row=1, column=1, sticky="new")
        self.label(text=short_quality(entry.get("quality")), kind="meta", fg=C["text2"]).grid(
            row=0, column=2, sticky="w")
        self.label(text=(entry.get("when") or "")[:10], kind="meta", fg=C["text2"]).grid(
            row=0, column=3, sticky="w")
        more = self.label(text=glyph("more"), icon_size=12, fg=C["text2"], anchor="center", cursor="hand2", width=3)
        more.grid(row=0, column=4, sticky="nsew")
        more.bind("<Button-1>", lambda e: page.menu(more, entry))
        Tooltip(more, t("tip_more"))
        self.bind_parts(double_click=self._play if self.exists else None,
                        right_click=lambda e: page.menu(None, entry, e))
        self.num.bind("<Button-1>", lambda e: self._play())
        if self.exists:
            box.on_click(self._play)

    def _enter(self, _e=None):
        super()._enter(_e)
        if self.exists:
            self.num.configure(text=glyph("play"), font=tk_icon_font(11, self.scale), cursor="hand2")

    def _leave(self, _e=None):
        super()._leave(_e)
        if not self._hot:
            self.num.configure(text=str(self.pos + 1), font=tk_font("meta", self.scale), cursor="")

    def _play(self):
        if self.exists:
            self.page.play_from(self.entry)

    def set_playing(self, on):
        """Troca só o destaque (sem recriar a linha) quando a música atual muda."""
        if on == self.playing:
            return
        self.playing = on
        self.set_fg(self.num, C["accent_text"] if on else C["text2"])
        self.set_fg(self.title, C["accent_text"] if on else (C["text"] if self.exists else C["text2"]))


class PlaylistRow(HoverRow):
    def __init__(self, master, page, group):
        super().__init__(master)
        self.page, self.group = page, group
        self.grid_columnconfigure(1, weight=1)
        box = ThumbBox(self, size=THUMB)
        box.grid(row=0, column=0, rowspan=2, padx=(SP["sm"], SP["md"]), pady=SP["xs"])
        page.show_cover(box, group)
        box.on_click(lambda: page.open_playlist(group["key"]))
        ctk.CTkLabel(self, text=ellipsize(group["name"], 80), font=font("label"), anchor="w").grid(
            row=0, column=1, sticky="sew")
        meta = t("n_items", n=len(group["items"]))
        if group["channel"]:
            meta = f"{group['channel']}  ·  {meta}"
        ctk.CTkLabel(self, text=meta, font=font("meta"), text_color=C["text2"], anchor="w").grid(
            row=1, column=1, sticky="new")
        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.grid(row=0, column=2, rowspan=2, padx=SP["sm"])
        IconButton(acts, "play", t("tip_play"), size=30, icon_size=12,
                   command=lambda: page.play_group(group)).pack(side="left")
        more = IconButton(acts, "more", t("tip_more"), size=30, icon_size=12)
        more.configure(command=lambda: page.playlist_menu(more, group))
        more.pack(side="left")
        self.bind_children(double_click=lambda: page.open_playlist(group["key"]),
                           right_click=lambda e: page.playlist_menu(None, group, e))


# ---------------------------------------------------------------- página
class LibraryPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._search_job, self._limit, self.items = None, PAGE, []
        self.view, self.playlist_key, self.rows = "all", None, []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, SP["md"]))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text=t("nav_library"), font=font("title")).grid(row=0, column=0, sticky="w")
        self.count = ctk.CTkLabel(head, text="", font=font("meta"), text_color=C["text2"])
        self.count.grid(row=0, column=1, sticky="w", padx=SP["md"], pady=(SP["sm"], 0))
        self.search = ctk.CTkEntry(head, height=CONTROL_H - 4, width=260, placeholder_text=t("hist_search"))
        self.search.grid(row=0, column=2, sticky="e")
        self.search.bind("<KeyRelease>", self._on_search)

        self.tabs = TabBar(self, (("all", t("lib_tab_all")), ("playlists", t("lib_tab_playlists"))),
                           self.set_view)
        self.tabs.grid(row=1, column=0, sticky="w", pady=(0, SP["lg"]))

        # cabeçalho variável: ações da aba "Tudo" ou capa/título da playlist aberta
        self.top = ctk.CTkFrame(self, fg_color="transparent")
        self.top.grid(row=2, column=0, sticky="ew")
        self.top.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=3, column=0, sticky="ew")
        _grid_cols(self.header)
        for col, key in ((0, "#"), (1, "col_title"), (2, "col_format"), (3, "col_date")):
            ctk.CTkLabel(self.header, text=key if key == "#" else t(key), font=font("small"),
                         text_color=C["text2"], anchor="w" if col else "center").grid(
                row=0, column=col, sticky="ew", padx=(SP["sm"] + 2 if col == 1 else 0, 0))
        divider(self.header).grid(row=1, column=0, columnspan=5, sticky="ew", pady=(SP["xs"], 0))
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=4, column=0, sticky="nsew", pady=(SP["xs"], 0))
        self.list.grid_columnconfigure(0, weight=1)
        self.set_view("all")

    # ---- navegação
    def set_view(self, view):
        self.view, self._limit = view, PAGE
        if view != "playlist":
            self.playlist_key = None
        self.tabs.select("playlists" if view == "playlist" else view)
        self.refresh()

    def open_playlist(self, key):
        self.playlist_key = key
        self.set_view("playlist")

    # ---- dados
    def _on_search(self, _e=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._apply_search)   # espera parar de digitar

    def _apply_search(self):
        self._search_job, self._limit = None, PAGE
        self.refresh()

    def _match(self, h, q):
        text = " ".join((h.get("title", ""), h.get("url", ""), h.get("channel", ""), h.get("playlist", "")))
        return not q or q in text.lower()

    def current_group(self):
        all_items = load_history()
        return next((g for g in group_playlists(all_items, self.app.settings.output_dir)
                     if g["key"] == self.playlist_key), None)

    def set_playing(self, path):
        for row in self.rows:
            if row.winfo_exists():
                row.set_playing(bool(path) and row.entry.get("filepath") == path)

    def refresh(self):
        for w in list(self.list.winfo_children()) + list(self.top.winfo_children()):
            w.destroy()
        self.rows = []
        self.app._thumb_boxes = {}
        all_items = load_history()
        q = self.search.get().strip().lower()
        self.count.configure(text=t("n_items", n=len(all_items)) if all_items else "")

        if self.view == "playlists":
            self.header.grid_remove()
            self.top.grid_remove()
            groups = [g for g in group_playlists(all_items, self.app.settings.output_dir)
                      if not q or q in g["name"].lower() or any(self._match(h, q) for h in g["items"])]
            self.items = []
            if not groups:
                self._empty(t("hist_no_results", q=q) if q else t("lib_no_playlists"))
                return
            for i, g in enumerate(groups):
                PlaylistRow(self.list, self, g).grid(row=i, column=0, sticky="ew")
            return

        self.header.grid()
        self.top.grid()
        if self.view == "playlist":
            group = self.current_group()
            if group is None:
                self.set_view("playlists")
                return
            self._playlist_header(group)
            source = group["items"]
        else:
            self._all_header()
            source = all_items
        self.items = [h for h in source if self._match(h, q)]
        if not self.items:
            self._empty(t("hist_no_results", q=q) if q else t("hist_empty"))
            return
        playing = self.app.now_playing_path()
        for i, h in enumerate(self.items[:self._limit]):
            row = LibraryRow(self.list, self, i, h, playing=bool(playing) and h.get("filepath") == playing,
                             show_playlist=self.view == "all")
            row.grid(row=i, column=0, sticky="ew")
            self.rows.append(row)
        if len(self.items) > self._limit:
            button(self.list, t("btn_load_more", n=len(self.items) - self._limit), "ghost",
                   self._more, kind="meta").grid(row=self._limit, column=0, pady=SP["md"])

    def _empty(self, msg):
        ctk.CTkLabel(self.list, text=msg, font=font("body"), text_color=C["text2"]).grid(
            row=0, column=0, pady=SP["xxl"])

    def _all_header(self):
        actions = ctk.CTkFrame(self.top, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, SP["md"]))
        IconButton(actions, "play", t("btn_play_all"), "accent", size=44, icon_size=16,
                   corner_radius=22, command=self.play_all).pack(side="left")
        IconButton(actions, "shuffle", t("tip_shuffle_play"), size=36, icon_size=15,
                   command=lambda: self.play_all(shuffle=True)).pack(side="left", padx=SP["sm"])
        button(actions, t("btn_clear_history"), "ghost", self.app.clear_history, kind="meta", height=28,
               text_color=C["text2"]).pack(side="right")

    def _playlist_header(self, g):
        top = ctk.CTkFrame(self.top, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, SP["lg"]))
        top.grid_columnconfigure(1, weight=1)
        cover = ThumbBox(top, size=COVER)
        cover.grid(row=0, column=0, rowspan=4, sticky="nw")
        self.show_cover(cover, g)
        cover.on_click(lambda: self.app.change_cover(g["items"], g["name"], g["folder"]))
        back = ctk.CTkLabel(top, text="‹  " + t("lib_tab_playlists"), font=font("meta"), text_color=C["text2"],
                            cursor="hand2", anchor="w")
        back.grid(row=0, column=1, sticky="w", padx=SP["xl"])
        back.bind("<Button-1>", lambda e: self.set_view("playlists"))
        ctk.CTkLabel(top, text=g["name"], font=font("title", size=26), anchor="w", justify="left",
                     wraplength=560).grid(row=1, column=1, sticky="w", padx=SP["xl"])
        meta = t("n_items", n=len(g["items"]))
        if g["channel"]:
            meta = f"{g['channel']}  ·  {meta}"
        ctk.CTkLabel(top, text=meta, font=font("meta"), text_color=C["text2"], anchor="w").grid(
            row=2, column=1, sticky="w", padx=SP["xl"])
        acts = ctk.CTkFrame(top, fg_color="transparent")
        acts.grid(row=3, column=1, sticky="sw", padx=SP["xl"], pady=(SP["md"], 0))
        IconButton(acts, "play", t("btn_play_all"), "accent", size=44, icon_size=16, corner_radius=22,
                   command=lambda: self.play_group(g)).pack(side="left")
        IconButton(acts, "shuffle", t("tip_shuffle_play"), size=36, icon_size=15,
                   command=lambda: self.play_group(g, shuffle=True)).pack(side="left", padx=SP["sm"])
        button(acts, t("btn_change_cover"), "secondary", lambda: self.app.change_cover(
            g["items"], g["name"], g["folder"]), kind="body", height=32).pack(side="left", padx=SP["sm"])
        more = IconButton(acts, "more", t("tip_more"), size=32, icon_size=12)
        more.configure(command=lambda: self.playlist_menu(more, g))
        more.pack(side="left")

    def show_cover(self, box, group):
        """Capa escolhida, ou a miniatura do primeiro item (gerada do arquivo se preciso)."""
        if group["cover"] and os.path.isfile(group["cover"]):
            box.set_path(group["cover"])
            return
        first = next((h for h in group["items"] if _exists(h)), None)
        if first:
            self.app.show_history_thumb(box, first, first["filepath"], True)

    def _more(self):
        self._limit += PAGE
        self.refresh()

    def playable(self):
        return [h for h in self.items if _exists(h)]

    # ---- reprodução
    def play_from(self, entry):
        """Toca a partir deste item, com o resto da lista na fila (como o Spotify)."""
        items = self.playable()
        start = next((i for i, h in enumerate(items) if h is entry), 0)
        self.app.play_entries(items, start)

    def play_all(self, shuffle=False):
        items = self.playable()
        if items:
            self.app.play_entries(items, 0, shuffle=shuffle)

    def play_group(self, group, shuffle=False):
        items = [h for h in group["items"] if _exists(h)]
        if items:
            self.app.play_entries(items, 0, shuffle=shuffle)

    # ---- menus de contexto
    def _new_menu(self):
        dark = ctk.get_appearance_mode() == "Dark"
        m = tk.Menu(self, tearoff=0, bg="#2B2D31" if dark else "#FFFFFF", fg="#F2F3F5" if dark else "#1B1B1F",
                    activebackground="#8B3DFF", activeforeground="#FFFFFF", bd=0,
                    font=(font("body").cget("family"), 10))
        return m, dark

    @staticmethod
    def _popup(m, widget, event):
        if event is not None:
            x, y = event.x_root, event.y_root
        else:
            x, y = widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def menu(self, widget, entry, event=None):
        m, dark = self._new_menu()
        state = "normal" if _exists(entry) else "disabled"
        m.add_command(label=t("menu_play"), command=lambda: self.play_from(entry), state=state)
        m.add_command(label=t("menu_play_next"), command=lambda: self.app.queue_entry(entry, next_=True), state=state)
        m.add_command(label=t("menu_add_queue"), command=lambda: self.app.queue_entry(entry), state=state)
        m.add_separator()
        key, _name = playlist_of(entry, self.app.settings.output_dir)
        if key and self.view == "all":
            m.add_command(label=t("menu_go_playlist"), command=lambda: self.open_playlist(key))
        m.add_command(label=t("menu_change_cover"), command=lambda: self.app.change_cover([entry]))
        m.add_command(label=t("btn_redownload"), command=lambda: self.app.redownload(entry))
        m.add_command(label=t("menu_open_folder"),
                      command=lambda: reveal(entry.get("filepath", ""), entry.get("folder") or self.app.settings.output_dir))
        m.add_separator()
        m.add_command(label=t("menu_delete"), command=lambda: self.app.delete_entry(entry),
                      foreground="#F23F43" if dark else "#C42B30")
        self._popup(m, widget, event)

    def playlist_menu(self, widget, group, event=None):
        m, _dark = self._new_menu()
        m.add_command(label=t("menu_play"), command=lambda: self.play_group(group))
        m.add_command(label=t("menu_add_queue"), command=lambda: self.app.queue_entries(group["items"]))
        m.add_separator()
        if self.view != "playlist":
            m.add_command(label=t("menu_open_playlist"), command=lambda: self.open_playlist(group["key"]))
        m.add_command(label=t("menu_change_cover"),
                      command=lambda: self.app.change_cover(group["items"], group["name"], group["folder"]))
        if group["folder"]:
            m.add_command(label=t("menu_open_folder"), command=lambda: reveal("", group["folder"]))
        self._popup(m, widget, event)
