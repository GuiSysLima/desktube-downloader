# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Janela principal: barra lateral, páginas (app/ui/*) e a barra do player no rodapé.

Regras de arquitetura (ver CLAUDE.md):
- Cores, fontes, raios e espaçamentos vêm de theme.py; componentes reutilizáveis de widgets.py.
- Nenhuma thread toca em widgets: o trabalho em segundo plano manda eventos para self.events,
  que a thread principal processa em _poll() a cada 100 ms (ou usa self._bg(func, callback)).
- As páginas só chamam métodos públicos do App (play_entries, start_download, dep_action...).
"""
import logging
import os
import queue
import random
import threading
import time
import webbrowser
from dataclasses import asdict
from logging.handlers import RotatingFileHandler
from tkinter import filedialog

import customtkinter as ctk

from . import __version__, browsers, covers, deps, i18n, motion, player, thumbs, updater
from .config import Settings, config_dir, load_history, remove_history, save_history, update_history
from .downloader import Downloader
from .fsutil import send_to_trash
from .i18n import t
from .theme import C, RADIUS, SP, apply_ctk_theme, font, icon_font, glyph
from .ui.common import URL_RE, YT_RE, open_path, split_msg
from .ui.download import DownloadPage, JobRow
from .ui.library import LibraryPage, artist_of
from .ui.playing import PlayerBar, PlayingPage
from .ui.settings import SettingsPage
from .widgets import ICON_PNG, ChoiceDialog, Toast, apply_icon, badge, flash_window, icon_label, load_image, \
    set_badge

log = logging.getLogger("baixador")

PAGES = ("download", "library", "playing", "settings")
TICK_MS = 250
UPDATE_EVERY = 24 * 3600


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


# =========================================================================== barra lateral
class NavItem(ctk.CTkFrame):
    def __init__(self, master, app, key, icon, label):
        super().__init__(master, fg_color="transparent", corner_radius=RADIUS["button"], height=38, cursor="hand2")
        self.app, self.key, self.selected = app, key, False
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.icon = icon_label(self, icon, 15)
        self.icon.grid(row=0, column=0, padx=(SP["md"], SP["md"]))
        self.text = ctk.CTkLabel(self, text=label, font=font("body"), anchor="w", text_color=C["text2"])
        self.text.grid(row=0, column=1, sticky="ew")
        self.count = badge(self, "0", "accent")
        for w in (self, self.icon, self.text):
            w.bind("<Button-1>", lambda e: app.show_page(key))
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if not self.selected:
            if on:
                motion.fade_color(self, "fg_color", C["sidebar"], C["row_hover"], motion.DUR["micro"])
            else:
                motion.fade_color(self, "fg_color", C["row_hover"], C["sidebar"],
                                  round(motion.DUR["micro"] * motion.EXIT), final="transparent",
                                  easing=motion.ease_in)
            self.text.configure(text_color=C["text"] if on else C["text2"])

    def set_selected(self, on):
        was, self.selected = self.selected, on
        if on and not was:          # item escolhido "acende" (transição curta)
            motion.fade_color(self, "fg_color", C["sidebar"], C["surface2"], motion.DUR["short"])
        elif not on:
            motion.cancel(self, "color:fg_color")
            self.configure(fg_color="transparent")
        self.icon.configure(text_color=C["accent_text"] if on else C["text2"])
        self.text.configure(text_color=C["text"] if on else C["text2"], font=font("label" if on else "body"))

    def set_count(self, n):
        if n:
            set_badge(self.count, str(n), "accent")
            self.count.grid(row=0, column=2, padx=(0, SP["sm"]))
        else:
            self.count.grid_remove()


class Sidebar(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=C["sidebar"], corner_radius=0, width=216)
        self.app = app
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SP["lg"], pady=(SP["xl"], SP["lg"]))
        logo = load_image(ICON_PNG, (28, 28))
        if logo is not None:
            ctk.CTkLabel(head, image=logo, text="").pack(side="left")
        ctk.CTkLabel(head, text=t("app_name"), font=font("title", size=18), anchor="w").pack(
            side="left", padx=(SP["sm"], 0))
        self.items = {}
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=SP["sm"])
        nav.grid_columnconfigure(0, weight=1)
        for i, (key, icon) in enumerate((("download", "download"), ("library", "library"),
                                         ("playing", "nowplaying"))):
            item = NavItem(nav, app, key, icon, t(f"nav_{key}"))
            item.grid(row=i, column=0, sticky="ew", pady=1)
            self.items[key] = item
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=SP["sm"])
        bottom.grid_columnconfigure(0, weight=1)
        item = NavItem(bottom, app, "settings", "settings", t("nav_settings"))
        item.grid(row=0, column=0, sticky="ew")
        self.items["settings"] = item

        # rodapé: ícone + versão, centralizados; clicar abre Configurações › Sobre
        self.update_note = ctk.CTkLabel(self, text="", font=font("small"), text_color=C["accent_text"], cursor="hand2")
        foot = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        foot.grid(row=7, column=0, pady=(SP["md"], SP["lg"]))
        self.ver_icon = ctk.CTkLabel(foot, text=glyph("tag"), font=icon_font(12), text_color=C["text2"])
        self.ver_icon.pack(side="left", padx=(0, SP["xs"] + 2))
        self.ver = ctk.CTkLabel(foot, text=t("version", v=__version__), font=font("meta"), text_color=C["text2"])
        self.ver.pack(side="left")
        for w in (foot, self.ver_icon, self.ver):
            w.bind("<Button-1>", lambda e: app.show_page("settings", "about"))
        self.update_note.bind("<Button-1>", lambda e: app.show_update_dialog())

    def select(self, key):
        for k, item in self.items.items():
            item.set_selected(k == key)

    def set_update(self, tag):
        """Mostra "vX disponível" acima da versão quando há atualização (checagem automática)."""
        if tag:
            self.update_note.configure(text=t("update_badge", tag=tag))
            self.update_note.grid(row=6, column=0, pady=(SP["md"], 0))
        else:
            self.update_note.grid_remove()


# =========================================================================== janela principal
class App(ctk.CTk):
    def __init__(self):
        setup_logging()
        deps.refresh_path()
        self.settings = Settings.load()
        deps.CUSTOM_PATHS.update(self.settings.component_paths or {})
        motion.set_enabled(self.settings.animations)
        i18n.set_language(self.settings.language or i18n.detect_default())
        apply_ctk_theme()
        ctk.set_appearance_mode(self.settings.theme)
        super().__init__()
        self.geometry("1180x760")
        self.minsize(980, 640)
        apply_icon(self)
        self.report_callback_exception = self._on_tk_error

        self.events = queue.Queue()
        self.downloader = Downloader(lambda: self.settings, self.events)
        self.rows, self.hidden_jobs = {}, set()
        self._last_clip, self._installing, self._page = "", False, "download"
        self._thumb_boxes, self._thumb_pending, self._thumb_queue = {}, set(), queue.Queue()
        self._diag_logged, self._update_info, self._updating = set(), None, False
        self.playback, self._fullscreen, self._pb_after = None, False, None
        self._last_path, self._lib_dirty = None, False
        threading.Thread(target=self._thumb_worker, daemon=True).start()
        self.sidebar = self.content = self.bar = None

        self._build_ui()
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<Control-v>", self._shortcut_paste)
        self.bind("<Control-V>", self._shortcut_paste)
        self.bind("<Control-l>", lambda e: self._focus_url())
        self.bind("<space>", self._shortcut_space)
        self.bind("<Escape>", lambda e: self._fullscreen and self.toggle_fullscreen(False))
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        for i, key in enumerate(PAGES, start=1):
            self.bind(f"<Control-Key-{i}>", lambda e, k=key: self.show_page(k))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self.after(TICK_MS, self._tick)
        self.after(400, self.refresh_deps)
        self.after(3000, self._auto_update_check)

    # ------------------------------------------------------------------ estrutura
    def _build_ui(self):
        self.title(t("app_name"))
        for w in (self.sidebar, self.content, self.bar):
            if w is not None:
                w.destroy()
        self.configure(fg_color=C["bg"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self.content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages = {"download": DownloadPage(self.content, self),
                      "library": LibraryPage(self.content, self),
                      "playing": PlayingPage(self.content, self),
                      "settings": SettingsPage(self.content, self)}
        self.bar = PlayerBar(self, self)
        self.toast = Toast(self.content)
        self.rows = {}
        for jid in sorted(self.downloader.jobs):
            if jid not in self.hidden_jobs:
                self._ensure_row(asdict(self.downloader.jobs[jid]))
        self._update_counts()
        if self.playback:
            self.playback.set_video_handle(self.pages["playing"].video_handle())
        if self._update_info:
            self.sidebar.set_update(self._update_info["tag"])
        self._apply_playback_change()
        self.show_page(self._page)

    def show_page(self, key, section=None):
        self._page = key
        pad = (0, 0) if self._fullscreen else (SP["xxl"], SP["xl"])
        for k, p in self.pages.items():
            if k == key:
                p.grid(row=0, column=0, sticky="nsew", padx=pad[0], pady=pad[1])
            else:
                p.grid_remove()
        self.sidebar.select(key)
        if key == "settings" and section:
            self.pages["settings"].show(section)
        if key == "library" and self._lib_dirty:
            self._lib_dirty = False
            self.pages["library"].refresh()

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

    def _typing(self):
        focus = self.focus_get()
        return focus is not None and focus.winfo_class() in ("Entry", "Text", "TEntry")

    # ------------------------------------------------------------------ baixar
    def _focus_url(self):
        self.show_page("download")
        self.pages["download"].url.focus_set()

    def _shortcut_paste(self, event=None):
        """Ctrl+V fora de um campo de texto: cola o link e já começa a baixar."""
        if self._typing():
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
            self._ensure_row(asdict(job))
        self._update_counts()

    def _ensure_row(self, job):
        if job["id"] in self.hidden_jobs:
            return
        row = self.rows.get(job["id"])
        page = self.pages["download"]
        if row is None:
            page.empty.grid_remove()
            self.rows[job["id"]] = JobRow(page.list, self, job)
            self._regrid()
        else:
            row.update_job(job)

    def _regrid(self):
        page = self.pages["download"]
        for i, jid in enumerate(sorted(self.rows, reverse=True)):
            self.rows[jid].grid(row=i + 1, column=0, sticky="ew", pady=(0, 2))
        if not self.rows:
            page.empty.grid(row=0, column=0, pady=SP["xxl"])

    def remove_job_card(self, job_id):
        self.hidden_jobs.add(job_id)
        row = self.rows.pop(job_id, None)
        if row:
            row.destroy()
        self._regrid()
        self._update_counts()

    def clear_finished(self):
        for jid, row in list(self.rows.items()):
            if row.job["state"] in ("done", "error", "cancelled"):
                self.remove_job_card(jid)

    def _update_counts(self):
        active = sum(1 for j in self.downloader.jobs.values() if j.state in ("queued", "downloading", "processing"))
        self.sidebar.items["download"].set_count(active)
        self.pages["download"].set_count(len(self.rows))

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
                self.play_entries([entry], 0)
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
            self._drop_from_queue(path)      # o VLC trava o arquivo enquanto toca
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

    # ---- capas
    def change_cover(self, entries, playlist_name=None, folder=""):
        """Troca a capa de uma playlist (playlist_name) ou de um item."""
        path = filedialog.askopenfilename(title=t("cover_choose_title"),
                                          filetypes=[(t("images"), " ".join(covers.IMAGE_TYPES)),
                                                     (t("all_files"), "*.*")])
        if not path:
            return
        embeddable = [e for e in entries if covers.can_embed(e.get("filepath", ""))]
        if playlist_name:
            buttons = [(t("btn_cancel"), None, "secondary"), (t("btn_cover_playlist"), "playlist", "secondary"),
                       (t("btn_cover_all"), "all", "primary")]
            choice = ChoiceDialog(self, t("app_name"), t("cover_heading_playlist", name=playlist_name),
                                  t("cover_msg_playlist"), buttons, detail=path, icon="library").show()
        else:
            buttons = [(t("btn_cancel"), None, "secondary"), (t("btn_cover_app"), "app", "secondary")]
            if embeddable:
                buttons.append((t("btn_cover_file"), "file", "primary"))
            choice = ChoiceDialog(self, t("app_name"), t("cover_heading_item"), t("cover_msg_item"),
                                  buttons, detail=path, icon="library").show()
        if not choice:
            return
        embed = choice in ("all", "file")
        playing = self.now_playing_path()
        targets = [e for e in embeddable if e.get("filepath") != playing] if embed else []
        out = os.path.normcase(os.path.normpath(self.settings.output_dir))
        use_folder = folder if playlist_name and folder and os.path.normcase(os.path.normpath(folder)) != out else ""
        ids = {e.get("id") for e in entries if e.get("id")}
        paths = {e.get("filepath") for e in entries if e.get("filepath")}
        self.toast.show(t("cover_applying"), "info", 60000)

        def progress(i, n):
            self.events.put(("toast", (t("cover_embedding", i=i, n=n), "info")))

        def work():
            return covers.apply(path, targets, use_folder, embed_files=embed, on_progress=progress)

        def done(result):
            if not result:
                self.toast.show(t("cover_failed"), "error")
                return
            thumb = result["thumb"]
            match = lambda h: h.get("id") in ids or h.get("filepath") in paths  # noqa: E731
            if choice == "playlist":
                update_history(match, playlist_cover=thumb)
            elif choice == "all":
                update_history(match, playlist_cover=thumb, thumb=thumb, custom_thumb=True)
            else:
                update_history(match, thumb=thumb, custom_thumb=True)
            if choice != "playlist" and self.playback:
                for item in self.playback.queue:
                    if item["path"] in paths:
                        item["thumb"] = thumb
                self._on_playback_change()
            msg = t("cover_done")
            if embed:
                msg += " " + t("cover_embedded", n=result["embedded"])
                if result["failed"] or len(targets) < len(embeddable):
                    msg += " " + t("cover_skipped", n=result["failed"] + len(embeddable) - len(targets))
            self.toast.show(msg, "success", 6000)
            self.pages["library"].refresh()
        self._bg(work, done)

    # ------------------------------------------------------------------ player
    def _vlc_missing(self, path=""):
        choice = ChoiceDialog(self, t("app_name"), t("vlc_heading"), t("vlc_msg"),
                              [(t("btn_cancel"), None, "secondary"),
                               (t("btn_open_external"), "external", "secondary"),
                               (t("btn_install_vlc"), "install", "primary")], icon="play").show()
        if choice == "external" and path:
            open_path(path)
        elif choice == "install":
            if deps.has_winget():
                self.run_dep_task("install", ["vlc"])
                self.toast.show(t("player_vlc_installing"), "info", 6000)
            else:
                webbrowser.open(deps.COMPONENTS["vlc"].site)

    def _ensure_playback(self, path=""):
        if self.playback is not None:
            return self.playback
        if not player.available():
            self._vlc_missing(path)
            return None
        try:
            pb = player.Playback(on_change=self._on_playback_change, volume=self.settings.volume)
        except Exception as e:
            log.exception("player")
            self.toast.show(t("player_error", err=e).split("\n")[0], "error")
            if path:
                open_path(path)
            return None
        pb.set_video_handle(self.pages["playing"].video_handle())
        self.playback = pb
        return pb

    @staticmethod
    def entry_thumb(entry):
        """Miniatura do item: a gravada no histórico ou a gerada do arquivo (cache)."""
        thumb = entry.get("thumb")
        if thumb and os.path.isfile(thumb):
            return thumb
        path = entry.get("filepath")
        return thumbs.cached(thumbs.key_for("file:" + path)) if path else None

    def _item(self, entry):
        return player.make_item(entry["filepath"], entry.get("title", ""), self.entry_thumb(entry),
                                entry.get("quality", ""), artist_of(entry))

    def _after_start(self, pb):
        cur = pb.current
        if cur and cur["kind"] == "video":
            self.show_page("playing")

    def play_entries(self, entries, start=0, shuffle=False):
        """Toca itens da Biblioteca (a fila vira essa lista, como no Spotify)."""
        entries = [e for e in entries if e.get("filepath") and os.path.isfile(e["filepath"])]
        if not entries:
            self.toast.show(t("player_file_missing"), "warning")
            return
        pb = self._ensure_playback(entries[min(start, len(entries) - 1)]["filepath"])
        if pb is None:
            return
        items = [self._item(e) for e in entries]
        if shuffle:
            pb.shuffle = True
            start = random.randrange(len(items))
        pb.play_list(items, start)
        self._after_start(pb)

    def play_file(self, path, title="", thumb=None, quality=""):
        """Toca um arquivo recém-baixado (fila de downloads), mantendo o resto da fila depois dele."""
        if not path or not os.path.isfile(path):
            self.toast.show(t("player_file_missing"), "warning")
            return
        pb = self._ensure_playback(path)
        if pb is None:
            return
        entry = next((h for h in load_history() if h.get("filepath") == path), None) or \
            {"filepath": path, "title": title, "thumb": thumb, "quality": quality}
        pb.play_now(self._item(entry))
        self._after_start(pb)

    def queue_entry(self, entry, next_=False):
        pb = self._ensure_playback(entry.get("filepath", ""))
        if pb is None:
            return
        if next_:
            pb.play_next(self._item(entry))
            self.toast.show(t("queued_next"), "success", 2000)
        else:
            pb.add([self._item(entry)])
            self.toast.show(t("queued_end"), "success", 2000)

    def queue_entries(self, entries):
        entries = [e for e in entries if e.get("filepath") and os.path.isfile(e["filepath"])]
        if not entries:
            return
        pb = self._ensure_playback(entries[0]["filepath"])
        if pb is not None:
            pb.add([self._item(e) for e in entries])
            self.toast.show(t("queued_n", n=len(entries)), "success", 2000)

    def now_playing_path(self):
        cur = self.playback.current if self.playback else None
        return cur["path"] if cur else None

    def _drop_from_queue(self, path):
        pb = self.playback
        if not pb or not path:
            return
        for i in reversed(range(len(pb.queue))):
            if pb.queue[i]["path"] == path:
                pb.remove(i)

    def _on_playback_change(self):
        """Chamado pelo motor a cada mudança; junta várias mudanças seguidas num redesenho só."""
        if self._pb_after is None:
            self._pb_after = self.after(30, self._apply_playback_change)

    def _apply_playback_change(self):
        self._pb_after = None
        pb = self.playback
        has_queue = bool(pb and pb.queue)
        if has_queue and not self._fullscreen:
            self.bar.grid(row=1, column=1, sticky="ew", padx=SP["md"], pady=(0, SP["md"]))
            self.bar.refresh()
        else:
            self.bar.grid_remove()
        self.pages["playing"].refresh()
        path = self.now_playing_path()
        if path != self._last_path:
            self._last_path = path
            if self._page == "library":
                self.pages["library"].refresh()
            else:
                self._lib_dirty = True
        cur = pb.current if pb else None
        if self._fullscreen and (cur is None or cur["kind"] != "video"):
            self.toggle_fullscreen(False)

    def toggle_fullscreen(self, on=None):
        cur = self.playback.current if self.playback else None
        on = (not self._fullscreen) if on is None else on
        if on and (cur is None or cur["kind"] != "video"):
            return
        self._fullscreen = on
        self.attributes("-fullscreen", on)
        if on:
            self.sidebar.grid_remove()
            self.bar.grid_remove()
        else:
            self.sidebar.grid()
        self.pages["playing"].set_immersive(on)
        self.show_page("playing")
        if not on:
            self._apply_playback_change()

    def _shortcut_space(self, _e=None):
        if self._typing() or not self.playback or not self.playback.queue:
            return None
        self.playback.toggle()
        return "break"

    def _tick(self):
        try:
            if self.playback:
                self.playback.tick()
                self.bar.tick()
        except Exception:
            log.exception("tick")
        self.after(TICK_MS, self._tick)

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
    @staticmethod
    def missing(st=None):
        st = st or deps.status()
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
        miss = self.missing(st)
        for name in miss:            # diagnóstico no app.log (uma vez por sessão)
            if name not in self._diag_logged:
                self._diag_logged.add(name)
                log.info("\n".join(deps.diagnose(name)))
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

    def locate_dep(self, name):
        """"Localizar…": o usuário aponta o executável (ou a pasta do VLC) manualmente."""
        comp = deps.COMPONENTS[name]
        exe = "vlc.exe" if name == "vlc" else comp.exe + (".exe" if os.name == "nt" else "")
        path = filedialog.askopenfilename(title=t("locate_title", name=comp.label),
                                          filetypes=[(comp.label, exe), (t("all_files"), "*.*")])
        if not path:
            return
        path = os.path.normpath(path)
        deps.CUSTOM_PATHS[name] = path
        if name == "vlc":
            player.reset()
        if deps.find(name):
            self.settings.component_paths[name] = path
            self.save()
            self.toast.show(t("located_ok", name=comp.label), "success")
        else:
            deps.CUSTOM_PATHS.pop(name, None)
            ChoiceDialog(self, t("app_name"), t("locate_invalid", name=comp.label), "", [(t("btn_ok"), None, "accent")],
                         detail=path, icon="warning", icon_color=C["warning"]).show()
        self.refresh_deps()

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
                        if not ok:      # mostra onde procurou, para dar para resolver com "Localizar…"
                            for line in deps.diagnose(n):
                                out(line)
                                log.info(line)
                            text += "\n" + t("locate_hint", name=label)
                    else:
                        ok = deps.uninstall(n, out)
                        text = t("uninstalled_ok", name=label) if ok else \
                            t("uninstalled_fail", name=label, path=deps.find(n) or "?")
                except Exception as e:
                    log.exception("dep task")
                    ok, text = False, f"{label}: {e}"
                self.events.put(("install_log", text))
                self.events.put(("install_result", (ok, text.split("\n")[0])))
            self.events.put(("install_done", action))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ atualizações
    def _auto_update_check(self):
        s = self.settings
        if s.auto_update_check and not updater.is_dev() and time.time() - s.last_update_check > UPDATE_EVERY:
            self.check_updates(manual=False)

    def check_updates(self, manual=True):
        if self._updating:
            return

        def fetch():
            try:
                return "ok", updater.fetch_latest()
            except updater.NoReleases:
                return "none", None
            except Exception as e:
                return "error", str(e)
        if manual:
            self.toast.show(t("checking_updates"), "info", 10000)
            self.pages["settings"].set_update_busy(True)
        self._bg(fetch, lambda r: self._on_update(r or ("error", "?"), manual))

    def _on_update(self, result, manual):
        kind, info = result
        self.pages["settings"].set_update_busy(False)
        if manual:
            self.toast.hide()
        if kind == "error":
            log.warning("update check: %s", info)
            if manual:
                ChoiceDialog(self, t("app_name"), t("update_heading_err"), info, [(t("btn_ok"), None, "accent")],
                             icon="warning", icon_color=C["warning"]).show()
            return
        self.settings.last_update_check = time.time()
        self.save()
        if kind == "none":
            if manual:
                self.toast.show(t("no_releases"), "info")
            return
        state = updater.compare(info["tag"])
        self.pages["settings"].set_update_busy(False, t("latest_published", tag=info["tag"]))
        if state == "newer":
            self._update_info = info
            self.sidebar.set_update(info["tag"])
            if manual:
                self.show_update_dialog()
            else:
                self.toast.show(t("update_heading_new", tag=info["tag"]), "info", 6000)
        elif state == "dev":
            if manual:
                choice = ChoiceDialog(self, t("app_name"), t("update_dev_heading"),
                                      t("update_dev_msg", v=__version__, tag=info["tag"]),
                                      [(t("btn_ok"), None, "secondary"), (t("btn_see_release"), "page", "accent")],
                                      icon="update").show()
                if choice == "page":
                    webbrowser.open(info["url"])
        elif manual:
            self.toast.show(t("up_to_date", v=__version__), "success")

    def show_update_dialog(self):
        info = self._update_info
        if not info:
            return
        notes = updater.notes_excerpt(info.get("notes", ""))
        message = t("update_msg_new", v=__version__) + (f"\n\n{notes}" if notes else "")
        buttons = [(t("btn_not_now"), None, "secondary"), (t("btn_see_release"), "page", "secondary")]
        if updater.can_self_install() and info.get("asset_url"):
            buttons.append((t("btn_update_install"), "install", "primary"))
        else:
            buttons[-1] = (t("btn_download_update"), "page", "primary")
        choice = ChoiceDialog(self, t("app_name"), t("update_heading_new", tag=info["tag"]), message, buttons,
                              icon="update").show()
        if choice == "page":
            webbrowser.open(info["url"])
        elif choice == "install":
            self._download_update(info)

    def _download_update(self, info):
        if self._updating:
            return
        self._updating = True
        self.toast.show(t("update_downloading", p=0), "info", 600000)

        def work():
            try:
                path = updater.download(info["asset_url"], info.get("asset_size", 0),
                                        lambda f: self.events.put(("update_progress", f)))
                self.events.put(("update_ready", path))
            except Exception as e:
                log.exception("update download")
                self.events.put(("update_failed", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _install_update(self, path):
        self._updating = False
        self.toast.hide()
        busy = self.downloader.busy()
        if not ChoiceDialog(self, t("app_name"), t("update_ready_heading"),
                            t("update_ready_busy") if busy else t("update_ready_msg"),
                            [(t("btn_later"), None, "secondary"), (t("btn_install_restart"), "ok", "primary")],
                            icon="update").show():
            return
        try:
            updater.run_installer(path)
        except Exception as e:
            log.exception("run installer")
            self.toast.show(t("update_failed", err=e), "error")
            return
        self._shutdown()

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
            self._ensure_row(data)
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
        elif kind == "toast":
            text, toast_kind = data
            self.toast.show(text, toast_kind, 60000)
        elif kind == "install_log":
            self.pages["settings"].log_line(data)
        elif kind == "install_result":
            ok, text = data
            self.toast.show(text, "success" if ok else "warning", 6000)
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
        elif kind == "update_progress":
            self.toast.show(t("update_downloading", p=int(data * 100)), "info", 600000)
        elif kind == "update_ready":
            self._install_update(data)
        elif kind == "update_failed":
            self._updating = False
            self.toast.show(t("update_failed", err=data), "error", 8000)

    def _on_tk_error(self, exc, val, tb):
        log.error("Tk callback error", exc_info=(exc, val, tb))

    def _shutdown(self):
        self.save()
        if self.playback:
            self.playback.release()
        self.destroy()

    def _on_close(self):
        if self.downloader.busy():
            if not ChoiceDialog(self, t("app_name"), t("close_busy"), "", [(t("btn_cancel"), None, "secondary"),
                                                                           (t("btn_close_anyway"), "ok", "danger")],
                                icon="warning", icon_color=C["warning"]).show():
                return
        self._shutdown()
