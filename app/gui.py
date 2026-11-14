"""Interface gráfica (CustomTkinter). Todos os textos vêm de i18n.py."""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from dataclasses import asdict
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import GITHUB_REPO, __version__, browsers, deps, i18n
from .config import Settings, load_history, remove_history, save_history
from .downloader import QUALITIES, Downloader
from .fsutil import send_to_trash
from .i18n import t

URL_RE = re.compile(r"https?://[^\s\"'<>]+")
YT_RE = re.compile(r"(youtube\.com|youtu\.be)/", re.I)

GREEN = ("#1a7f37", "#3fb950")
RED = ("#c62828", "#ff6b6b")
RED_HOVER = ("#8e1c1c", "#d64545")
MUTED = ("gray40", "gray65")
GRAY_BTN = {"fg_color": "gray45", "hover_color": "gray35"}

THEMES = ("system", "light", "dark")


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


# --------------------------------------------------------------------------- diálogo de exclusão
class DeleteDialog(ctk.CTkToplevel):
    """Pergunta se remove só da lista ou também apaga o arquivo. show() -> None | "list" | "file"."""

    def __init__(self, master, title, path, exists):
        super().__init__(master)
        self.result = None
        self.title(t("del_title"))
        self.resizable(False, False)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t("del_question"), font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 4))
        ctk.CTkLabel(self, text=title[:120], anchor="w", justify="left", wraplength=480).grid(
            row=1, column=0, sticky="ew", padx=20)

        if exists:
            ctk.CTkLabel(self, text=path, anchor="w", justify="left", wraplength=480, text_color=MUTED,
                         font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 0))
            ctk.CTkLabel(self, text=t("del_warning"), anchor="w", justify="left", wraplength=480,
                         text_color=RED).grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 0))
        else:
            ctk.CTkLabel(self, text=t("del_no_file"), anchor="w", justify="left", wraplength=480,
                         text_color=MUTED).grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 0))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="e", padx=20, pady=18)
        ctk.CTkButton(btns, text=t("btn_cancel"), width=100, command=self._cancel, **GRAY_BTN).pack(side="left", padx=4)
        ctk.CTkButton(btns, text=t("btn_only_list"), width=110,
                      command=lambda: self._done("list")).pack(side="left", padx=4)
        if exists:
            ctk.CTkButton(btns, text=t("btn_delete_file"), width=130, fg_color=RED, hover_color=RED_HOVER,
                          command=lambda: self._done("file")).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())

    def _focus(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def _done(self, value):
        self.result = value
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def show(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_width()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.after(50, self._focus)
        self.master.wait_window(self)
        return self.result


# --------------------------------------------------------------------------- linha da fila
class JobRow(ctk.CTkFrame):
    def __init__(self, master, app, job):
        super().__init__(master, corner_radius=8)
        self.app = app
        self.job = job
        self.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(self, text=job["url"], anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        self.title.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))

        self.button = ctk.CTkButton(self, text=t("btn_cancel"), width=110, command=self._action)
        self.button.grid(row=0, column=1, rowspan=3, padx=12, pady=8)

        self.bar = ctk.CTkProgressBar(self, height=8)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 2))

        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=MUTED,
                                   font=ctk.CTkFont(size=12), wraplength=560, justify="left")
        self.status.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.update_job(job)

    def update_job(self, job):
        self.job = job
        title = job["title"] or job["url"]
        if len(title) > 90:
            title = title[:87] + "..."
        self.title.configure(text=title)
        self.bar.set(job["progress"])

        state = job["state"]
        extra = []
        if job["item"]:
            extra.append(t("item_n", n=job["item"]))
        quality = quality_label(job["quality"])
        if state == "downloading":
            extra += [f"{job['progress'] * 100:.0f}%", job["speed"], t("eta", eta=job["eta"]) if job["eta"] else ""]
            text, color, btn = t(job["status"]), MUTED, t("btn_cancel")
        elif state == "processing":
            text, color, btn = t(job["status"]), MUTED, t("btn_cancel")
        elif state == "done":
            text, color, btn = f"{t('st_done')}  •  {quality}", GREEN, t("btn_open_folder")
        elif state == "error":
            args = dict(job.get("error_args") or {})
            if job["error"] == "err_cookie_copy" and not args.get("browser"):
                args["browser"] = t("the_browser")
            text, color, btn = t("st_error", msg=t(job["error"], **args)), RED, t("btn_retry")
        elif state == "cancelled":
            text, color, btn = t("st_cancelled"), MUTED, t("btn_retry")
        else:
            text, color, btn = f"{t('st_queued')}  •  {quality}", MUTED, t("btn_remove")
        parts = [text] + [e for e in extra if e]
        self.status.configure(text="  •  ".join(parts), text_color=color)
        self.button.configure(text=btn)

    def _action(self):
        state = self.job["state"]
        if state in ("queued", "downloading", "processing"):
            self.app.downloader.cancel(self.job["id"])
        elif state == "done":
            reveal(self.job["filepath"], self.app.settings.output_dir)
        else:
            self.app.enqueue([self.job["url"]], self.job["quality"], self.job["playlist"], self.job["subtitles"])
            self.app.remove_row(self.job["id"])


# --------------------------------------------------------------------------- janela
class App(ctk.CTk):
    def __init__(self):
        deps.refresh_path()
        self.settings = Settings.load()
        i18n.set_language(self.settings.language or i18n.detect_default())
        ctk.set_appearance_mode(self.settings.theme)
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.geometry("980x700")
        self.minsize(800, 560)

        self.events = queue.Queue()
        self.downloader = Downloader(lambda: self.settings, self.events)
        self.rows = {}
        self.hidden_jobs = set()
        self._last_clip = ""
        self._installing = False
        self.tabs = None

        self._build_ui()

        self.bind("<FocusIn>", self._on_focus)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self.after(400, self._refresh_deps)

    def _build_ui(self):
        self.title(f"{t('app_name')}  {__version__}")
        self.tabs = ctk.CTkTabview(self, anchor="nw")
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.tab_dl = self.tabs.add(t("tab_download"))
        self.tab_hist = self.tabs.add(t("tab_history"))
        self.tab_cfg = self.tabs.add(t("tab_settings"))
        self.rows = {}
        self._build_download_tab()
        self._build_history_tab()
        self._build_settings_tab()
        # recria a fila (útil ao trocar de idioma)
        for jid in sorted(self.downloader.jobs):
            if jid not in self.hidden_jobs:
                self._ensure_row(asdict(self.downloader.jobs[jid]))

    def _change_language(self, label):
        code = next((c for c, name in i18n.LANGUAGES.items() if name == label), i18n.DEFAULT)
        if code == i18n.current():
            return
        self.settings.language = code
        self._save()
        i18n.set_language(code)
        self.tabs.destroy()
        self._build_ui()
        self.tabs.set(t("tab_settings"))
        self._refresh_deps()

    # ------------------------------------------------------------------ aba Baixar
    def _build_download_tab(self):
        tab = self.tab_dl
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 6))
        top.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(top, height=42, font=ctk.CTkFont(size=14), placeholder_text=t("url_placeholder"))
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self._on_download())
        ctk.CTkButton(top, text=t("btn_paste"), width=80, height=42, command=self._paste, **GRAY_BTN).grid(
            row=0, column=1, padx=(8, 0))
        ctk.CTkButton(top, text=t("btn_download"), width=120, height=42, font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._on_download).grid(row=0, column=2, padx=(8, 0))

        opts = ctk.CTkFrame(tab, fg_color="transparent")
        opts.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.quality_menu = ctk.CTkOptionMenu(opts, values=[quality_label(q) for q in QUALITIES], width=250,
                                              command=self._on_quality)
        self.quality_menu.set(quality_label(self.settings.quality if self.settings.quality in QUALITIES else "best"))
        self.quality_menu.pack(side="left")
        self.playlist_var = ctk.BooleanVar(value=self.settings.playlist)
        ctk.CTkCheckBox(opts, text=t("chk_playlist"), variable=self.playlist_var,
                        command=self._on_option).pack(side="left", padx=(16, 0))
        self.subs_var = ctk.BooleanVar(value=self.settings.subtitles)
        ctk.CTkCheckBox(opts, text=t("chk_subtitles"), variable=self.subs_var,
                        command=self._on_option).pack(side="left", padx=(16, 0))
        self.login_label = ctk.CTkButton(opts, text="", fg_color="transparent", text_color=MUTED,
                                         hover_color=("gray85", "gray25"), anchor="e",
                                         command=lambda: self.tabs.set(t("tab_settings")))
        self.login_label.pack(side="right")

        self.banner = ctk.CTkFrame(tab, fg_color=("#fff4ce", "#4a3b00"), corner_radius=8)
        self.banner_text = ctk.CTkLabel(self.banner, text="", anchor="w", justify="left",
                                        text_color=("#5c4400", "#ffe08a"))
        self.banner_text.pack(side="left", padx=12, pady=8, fill="x", expand=True)
        self.banner_btn = ctk.CTkButton(self.banner, text=t("btn_install_now"), width=130,
                                        command=self._install_missing)
        self.banner_btn.pack(side="right", padx=12, pady=8)

        self.queue_frame = ctk.CTkScrollableFrame(tab, label_text=t("queue_title"))
        self.queue_frame.grid(row=3, column=0, sticky="nsew")
        self.queue_frame.grid_columnconfigure(0, weight=1)
        self.empty_label = ctk.CTkLabel(self.queue_frame, text_color=MUTED, text=t("queue_empty"))
        self.empty_label.grid(row=0, column=0, pady=40)

        folder = ctk.CTkFrame(tab, corner_radius=8)
        folder.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        folder.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(folder, text=t("save_to"), font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(12, 6), pady=8)
        self.folder_label = ctk.CTkLabel(folder, text="", anchor="w", text_color=MUTED)
        self.folder_label.grid(row=0, column=1, sticky="ew", pady=8)
        ctk.CTkButton(folder, text=t("btn_open"), width=80,
                      command=lambda: reveal("", self.settings.output_dir)).grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(folder, text=t("btn_change_folder"), width=130, command=self._choose_output,
                      **GRAY_BTN).grid(row=0, column=3, padx=(4, 12), pady=8)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkButton(bottom, text=t("btn_clear_finished"), width=150, command=self._clear_finished,
                      **GRAY_BTN).pack(side="left")
        self.status_bar = ctk.CTkLabel(bottom, text="", text_color=MUTED, anchor="e")
        self.status_bar.pack(side="right", fill="x", expand=True)
        self._refresh_login_label()
        self._refresh_folder_label()

    def _refresh_folder_label(self):
        path = self.settings.output_dir
        self.folder_label.configure(text=path if len(path) <= 80 else "..." + path[-77:])

    def _refresh_login_label(self):
        b = self.settings.browser
        if b in browsers.BROWSERS:
            text = t("login_browser", name=browsers.BROWSERS[b].label)
        elif b == "file" and self.settings.cookies_file:
            text = t("login_file")
        else:
            text = t("login_none")
        self.login_label.configure(text=text)

    def _paste(self):
        try:
            text = self.clipboard_get()
        except Exception:
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, text.strip())

    def _on_focus(self, _event=None):
        if not self.settings.watch_clipboard or self.url_entry.get().strip():
            return
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return
        if clip and clip != self._last_clip and URL_RE.match(clip) and YT_RE.search(clip):
            self._last_clip = clip
            self.url_entry.insert(0, clip)

    def _on_quality(self, label):
        for q in QUALITIES:
            if quality_label(q) == label:
                self.settings.quality = q
        self._save()

    def _on_option(self):
        self.settings.playlist = self.playlist_var.get()
        self.settings.subtitles = self.subs_var.get()
        self._save()

    def _on_download(self):
        urls = URL_RE.findall(self.url_entry.get().strip())
        if not urls:
            messagebox.showwarning(t("app_name"), t("invalid_url"))
            return
        if not self._check_browser_lock():
            return
        self.enqueue(urls, self.settings.quality, self.playlist_var.get(), self.subs_var.get())
        self.url_entry.delete(0, "end")

    def _check_browser_lock(self) -> bool:
        key = self.settings.browser
        b = browsers.BROWSERS.get(key)
        if not b or not b.locks_cookies or not browsers.is_running(key):
            return True
        answer = messagebox.askyesnocancel(t("app_name"), t("browser_open_download", name=b.label), icon="warning")
        if answer is None:
            return False
        if answer:
            browsers.close_browser(key)
            self.after(1500)
        return True

    def enqueue(self, urls, quality, playlist, subtitles):
        for url in urls:
            job = self.downloader.add(url, quality, playlist, subtitles)
            self._ensure_row(asdict(job))

    def _ensure_row(self, job):
        if job["id"] in self.hidden_jobs:
            return None
        row = self.rows.get(job["id"])
        if row is None:
            self.empty_label.grid_remove()
            row = JobRow(self.queue_frame, self, job)
            self.rows[job["id"]] = row
            self._regrid_rows()
        else:
            row.update_job(job)
        return row

    def _regrid_rows(self):
        for i, jid in enumerate(sorted(self.rows, reverse=True)):
            self.rows[jid].grid(row=i + 1, column=0, sticky="ew", padx=4, pady=4)
        if not self.rows:
            self.empty_label.grid()

    def remove_row(self, job_id):
        self.hidden_jobs.add(job_id)
        row = self.rows.pop(job_id, None)
        if row:
            row.destroy()
        self._regrid_rows()

    def _clear_finished(self):
        for jid, row in list(self.rows.items()):
            if row.job["state"] in ("done", "error", "cancelled"):
                self.remove_row(jid)

    # ------------------------------------------------------------------ aba Vídeos baixados
    def _build_history_tab(self):
        tab = self.tab_hist
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(4, 6))
        self.hist_search = ctk.CTkEntry(bar, placeholder_text=t("hist_search"), width=320)
        self.hist_search.pack(side="left")
        self.hist_search.bind("<KeyRelease>", lambda e: self._refresh_history())
        ctk.CTkButton(bar, text=t("btn_clear_history"), width=140, command=self._clear_history,
                      **GRAY_BTN).pack(side="right")
        self.hist_frame = ctk.CTkScrollableFrame(tab)
        self.hist_frame.grid(row=1, column=0, sticky="nsew")
        self.hist_frame.grid_columnconfigure(0, weight=1)
        self._refresh_history()

    def _refresh_history(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()
        query = self.hist_search.get().strip().lower()
        items = [h for h in load_history() if not query or query in (h.get("title", "") + h.get("url", "")).lower()]
        if not items:
            ctk.CTkLabel(self.hist_frame, text=t("hist_empty"), text_color=MUTED).grid(row=0, column=0, pady=40)
            return
        for i, h in enumerate(items[:150]):
            f = ctk.CTkFrame(self.hist_frame, corner_radius=8)
            f.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            f.grid_columnconfigure(0, weight=1)
            title = h.get("title") or h.get("url", "")
            ctk.CTkLabel(f, text=title[:100], anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="ew", padx=12, pady=(6, 0))
            path = h.get("filepath", "")
            exists = bool(path) and os.path.exists(path)
            sub = f"{h.get('when', '')}  •  {quality_label(h.get('quality', ''))}"
            if path and exists:
                sub += f"  •  {path}"
            elif path:
                sub += f"  •  {t('hist_missing_file')}"
            ctk.CTkLabel(f, text=sub[:160], anchor="w", text_color=MUTED).grid(
                row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
            btns = ctk.CTkFrame(f, fg_color="transparent")
            btns.grid(row=0, column=1, rowspan=2, padx=8)
            ctk.CTkButton(btns, text=t("btn_open"), width=64, state="normal" if exists else "disabled",
                          command=lambda p=path: open_path(p)).pack(side="left", padx=2)
            ctk.CTkButton(btns, text=t("btn_folder"), width=64,
                          command=lambda p=path, d=h.get("folder", ""): reveal(p, d or self.settings.output_dir)
                          ).pack(side="left", padx=2)
            ctk.CTkButton(btns, text=t("btn_redownload"), width=120, **GRAY_BTN,
                          command=lambda u=h.get("url"), q=h.get("quality", "best"): self._redownload(u, q)
                          ).pack(side="left", padx=2)
            ctk.CTkButton(btns, text=t("btn_delete"), width=72, fg_color=RED, hover_color=RED_HOVER,
                          command=lambda e=h: self._delete_entry(e)).pack(side="left", padx=2)

    def _delete_entry(self, entry):
        path = entry.get("filepath", "")
        exists = bool(path) and os.path.isfile(path)
        choice = DeleteDialog(self, entry.get("title") or entry.get("url", ""), path, exists).show()
        if choice is None:
            return
        if choice == "file":
            try:
                send_to_trash(path)
            except Exception as e:
                messagebox.showerror(t("app_name"), t("delete_error", path=path, err=e))
                return
            self.status_bar.configure(text=t("deleted_to_trash", name=os.path.basename(path)))
        else:
            self.status_bar.configure(text=t("removed_from_list"))
        remove_history(entry)
        self._refresh_history()

    def _redownload(self, url, quality):
        if url and self._check_browser_lock():
            self.enqueue([url], quality, False, self.subs_var.get())
            self.tabs.set(t("tab_download"))

    def _clear_history(self):
        if messagebox.askyesno(t("app_name"), t("clear_history_confirm")):
            save_history([])
            self._refresh_history()

    # ------------------------------------------------------------------ aba Configurações
    def _section(self, parent, row, title, desc=""):
        f = ctk.CTkFrame(parent, corner_radius=8)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=6)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=(10, 0))
        if desc:
            ctk.CTkLabel(f, text=desc, anchor="w", justify="left", text_color=MUTED, wraplength=760).grid(
                row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 4))
        return f

    def _build_settings_tab(self):
        sf = ctk.CTkScrollableFrame(self.tab_cfg, fg_color="transparent")
        sf.pack(fill="both", expand=True)
        sf.grid_columnconfigure(0, weight=1)

        # --- idioma
        f = self._section(sf, 0, t("sec_language"))
        ctk.CTkLabel(f, text=t("language_label")).grid(row=2, column=0, sticky="w", padx=14, pady=(6, 12))
        self.lang_menu = ctk.CTkOptionMenu(f, values=list(i18n.LANGUAGES.values()), width=220,
                                           command=self._change_language)
        self.lang_menu.set(i18n.LANGUAGES[i18n.current()])
        self.lang_menu.grid(row=2, column=1, sticky="w", pady=(6, 12))

        # --- pasta
        f = self._section(sf, 1, t("sec_folder"), t("sec_folder_desc"))
        self.out_entry = ctk.CTkEntry(f)
        self.out_entry.insert(0, self.settings.output_dir)
        self.out_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(14, 6), pady=(6, 12))
        self.out_entry.bind("<FocusOut>", lambda e: self._set_output(self.out_entry.get()))
        ctk.CTkButton(f, text=t("btn_choose"), width=110, command=self._choose_output).grid(
            row=2, column=2, padx=(0, 14), pady=(6, 12))

        # --- login
        f = self._section(sf, 2, t("sec_login"), t("sec_login_desc"))
        installed = browsers.installed_keys()
        self._browser_labels = {t("browser_none"): "none"}
        for k, b in browsers.BROWSERS.items():
            self._browser_labels[f"{b.label}  {t('detected')}" if k in installed else b.label] = k
        self._browser_labels[t("browser_file")] = "file"
        ctk.CTkLabel(f, text=t("browser_label")).grid(row=2, column=0, sticky="w", padx=14, pady=6)
        self.browser_menu = ctk.CTkOptionMenu(f, values=list(self._browser_labels), width=260,
                                              command=self._on_browser)
        self.browser_menu.set(next((lbl for lbl, k in self._browser_labels.items() if k == self.settings.browser),
                                   t("browser_none")))
        self.browser_menu.grid(row=2, column=1, sticky="w", pady=6)
        ctk.CTkButton(f, text=t("btn_test_login"), width=110, command=self._test_login).grid(
            row=2, column=2, padx=(0, 14), pady=6)

        ctk.CTkLabel(f, text=t("file_label")).grid(row=3, column=0, sticky="w", padx=14, pady=6)
        self.cookie_entry = ctk.CTkEntry(f, placeholder_text=t("cookie_placeholder"))
        self.cookie_entry.insert(0, self.settings.cookies_file)
        self.cookie_entry.grid(row=3, column=1, sticky="ew", pady=6)
        self.cookie_entry.bind("<FocusOut>", lambda e: self._set_cookie_file(self.cookie_entry.get()))
        self.cookie_btn = ctk.CTkButton(f, text=t("btn_choose"), width=110, command=self._choose_cookie_file)
        self.cookie_btn.grid(row=3, column=2, padx=(0, 14), pady=6)
        self.login_result = ctk.CTkLabel(f, text="", anchor="w", justify="left", wraplength=760)
        self.login_result.grid(row=4, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 4))
        ctk.CTkLabel(f, anchor="w", justify="left", text_color=MUTED, wraplength=760, text=t("login_tip")).grid(
            row=5, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 12))
        self._update_cookie_widgets()

        # --- opções
        f = self._section(sf, 3, t("sec_options"))
        self.meta_var = ctk.BooleanVar(value=self.settings.embed_metadata)
        self.thumb_var = ctk.BooleanVar(value=self.settings.embed_thumbnail)
        self.clip_var = ctk.BooleanVar(value=self.settings.watch_clipboard)
        for r, (key, var) in enumerate((("opt_metadata", self.meta_var), ("opt_thumbnail", self.thumb_var),
                                        ("opt_clipboard", self.clip_var))):
            ctk.CTkCheckBox(f, text=t(key), variable=var, command=self._on_cfg_option).grid(
                row=2 + r, column=0, columnspan=3, sticky="w", padx=14, pady=4)
        ctk.CTkLabel(f, text=t("sub_langs_label")).grid(row=5, column=0, sticky="w", padx=14, pady=(4, 12))
        self.langs_entry = ctk.CTkEntry(f, width=200)
        self.langs_entry.insert(0, self.settings.sub_langs)
        self.langs_entry.grid(row=5, column=1, sticky="w", pady=(4, 12))
        self.langs_entry.bind("<FocusOut>", lambda e: self._on_cfg_option())

        # --- componentes
        f = self._section(sf, 4, t("sec_components"), t("sec_components_desc"))
        self.dep_labels = {}
        self.dep_buttons = {}
        for i, (name, label) in enumerate((("ffmpeg", "ffmpeg"), ("deno", "Deno"), ("node", "Node.js"))):
            ctk.CTkLabel(f, text=label, width=80, anchor="w").grid(row=2 + i, column=0, sticky="w", padx=14, pady=3)
            lbl = ctk.CTkLabel(f, text="", anchor="w")
            lbl.grid(row=2 + i, column=1, sticky="ew", pady=3)
            self.dep_labels[name] = lbl
            if name in deps.WINGET_IDS:
                b = ctk.CTkButton(f, text=t("btn_install"), width=110, command=lambda n=name: self._install([n]))
                b.grid(row=2 + i, column=2, padx=(0, 14), pady=3)
                self.dep_buttons[name] = b
        ctk.CTkLabel(f, text=f"yt-dlp {deps.ytdlp_version()}", text_color=MUTED, anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=14, pady=3)
        ctk.CTkButton(f, text=t("btn_recheck"), width=110, command=self._refresh_deps, **GRAY_BTN).grid(
            row=5, column=2, padx=(0, 14), pady=3)
        self.install_log = ctk.CTkTextbox(f, height=90, font=ctk.CTkFont(family="Consolas", size=11))
        self.install_log.grid(row=6, column=0, columnspan=3, sticky="ew", padx=14, pady=(4, 12))
        self.install_log.configure(state="disabled")

        # --- aparência / atualizações
        f = self._section(sf, 5, t("sec_appearance"))
        self._theme_labels = {t(f"theme_{k}"): k for k in THEMES}
        self.theme_seg = ctk.CTkSegmentedButton(f, values=list(self._theme_labels), command=self._on_theme)
        self.theme_seg.set(t(f"theme_{self.settings.theme if self.settings.theme in THEMES else 'system'}"))
        self.theme_seg.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=6)
        ctk.CTkLabel(f, text=t("version", v=__version__), text_color=MUTED).grid(row=3, column=0, sticky="w", padx=14)
        ctk.CTkButton(f, text=t("btn_check_updates"), width=180, command=self._check_updates,
                      state="normal" if GITHUB_REPO else "disabled").grid(row=3, column=1, sticky="w", pady=(6, 12))
        if GITHUB_REPO:
            ctk.CTkButton(f, text=t("btn_project_page"), width=150, **GRAY_BTN,
                          command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}")).grid(
                row=3, column=2, padx=(0, 14), pady=(6, 12))

    def _save(self):
        try:
            self.settings.save()
        except Exception as e:
            if getattr(self, "status_bar", None):
                self.status_bar.configure(text=t("save_error", err=e))

    def _set_output(self, path):
        path = path.strip()
        if path:
            self.settings.output_dir = path
            self._save()
            self._refresh_folder_label()
            if self.out_entry.get().strip() != path:
                self.out_entry.delete(0, "end")
                self.out_entry.insert(0, path)

    def _choose_output(self):
        initial = self.settings.output_dir if os.path.isdir(self.settings.output_dir) else os.path.expanduser("~")
        path = filedialog.askdirectory(title=t("choose_folder_title"), initialdir=initial)
        if path:
            self._set_output(os.path.normpath(path))

    def _on_browser(self, label):
        self.settings.browser = self._browser_labels.get(label, "none")
        self.login_result.configure(text="")
        self._update_cookie_widgets()
        self._refresh_login_label()
        self._save()

    def _update_cookie_widgets(self):
        state = "normal" if self.settings.browser == "file" else "disabled"
        self.cookie_entry.configure(state=state)
        self.cookie_btn.configure(state=state)

    def _set_cookie_file(self, path):
        self.settings.cookies_file = path.strip()
        self._refresh_login_label()
        self._save()

    def _choose_cookie_file(self):
        path = filedialog.askopenfilename(filetypes=[("Cookies", "*.txt"), (t("all_files"), "*.*")])
        if path:
            path = os.path.normpath(path)
            self.cookie_entry.delete(0, "end")
            self.cookie_entry.insert(0, path)
            self._set_cookie_file(path)

    def _test_login(self):
        key = self.settings.browser
        if key == "none":
            self.login_result.configure(text=t("choose_browser_first"), text_color=MUTED)
            return
        if key == "file" and not self.settings.cookies_file:
            self.login_result.configure(text=t("choose_cookie_file"), text_color=MUTED)
            return
        if key in browsers.BROWSERS and browsers.BROWSERS[key].locks_cookies and browsers.is_running(key):
            if messagebox.askyesno(t("app_name"), t("browser_open_test", name=browsers.BROWSERS[key].label)):
                browsers.close_browser(key)
            else:
                return
        self.login_result.configure(text=t("testing"), text_color=MUTED)

        def work():
            result = browsers.test_cookies("" if key == "file" else key,
                                           self.settings.cookies_file if key == "file" else "")
            self.events.put(("login_test", result))

        threading.Thread(target=work, daemon=True).start()

    def _on_cfg_option(self):
        self.settings.embed_metadata = self.meta_var.get()
        self.settings.embed_thumbnail = self.thumb_var.get()
        self.settings.watch_clipboard = self.clip_var.get()
        self.settings.sub_langs = self.langs_entry.get().strip() or "pt.*,en.*"
        self._save()

    def _on_theme(self, label):
        self.settings.theme = self._theme_labels.get(label, "system")
        ctk.set_appearance_mode(self.settings.theme)
        self._save()

    # ------------------------------------------------------------------ componentes
    def _missing(self):
        st = deps.status()
        missing = []
        if not st["ffmpeg"]:
            missing.append("ffmpeg")
        if not st["deno"] and not st["node"]:
            missing.append("deno")
        return missing

    def _refresh_deps(self):
        deps.refresh_path()
        st = deps.status()
        for name, lbl in self.dep_labels.items():
            path = st.get(name)
            if path:
                lbl.configure(text=f"✓  {path}", text_color=GREEN)
            elif name == "node":
                lbl.configure(text=t("dep_node_optional"), text_color=MUTED)
            else:
                lbl.configure(text=t("dep_missing"), text_color=RED)
            if name in self.dep_buttons:
                self.dep_buttons[name].configure(state="disabled" if path or self._installing else "normal")
        missing = self._missing()
        if missing:
            names = ", ".join("Deno" if m == "deno" else m for m in missing)
            self.banner_text.configure(text=t("missing_banner", names=names))
            self.banner_btn.configure(state="disabled" if self._installing else "normal")
            self.banner.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        else:
            self.banner.grid_remove()

    def _install_missing(self):
        self._install(self._missing())

    def _install(self, names):
        if not names or self._installing:
            return
        if not deps.has_winget():
            messagebox.showerror(t("app_name"), t("no_winget"))
            return
        self._installing = True
        self._refresh_deps()
        self._log_install(t("installing", names=", ".join(names)))

        def work():
            for n in names:
                ok = deps.install(n, lambda line: self.events.put(("install_log", line)))
                self.events.put(("install_log", t("installed_ok" if ok else "installed_fail", name=n)))
            self.events.put(("install_done", None))

        threading.Thread(target=work, daemon=True).start()

    def _log_install(self, line):
        self.install_log.configure(state="normal")
        self.install_log.insert("end", line + "\n")
        self.install_log.see("end")
        self.install_log.configure(state="disabled")
        self.status_bar.configure(text=line[:120])

    # ------------------------------------------------------------------ atualizações
    def _check_updates(self):
        def work():
            try:
                req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                             headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "BaixadorYouTube"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.load(r)
                self.events.put(("update", (data.get("tag_name", ""), data.get("html_url", ""))))
            except Exception as e:
                self.events.put(("update", ("", str(e))))

        self.status_bar.configure(text=t("checking_updates"))
        threading.Thread(target=work, daemon=True).start()

    def _on_update_result(self, tag, info):
        if not tag:
            messagebox.showinfo(t("app_name"), t("update_error", err=info))
        elif version_tuple(tag) > version_tuple(__version__):
            if messagebox.askyesno(t("app_name"), t("update_available", tag=tag, v=__version__)):
                webbrowser.open(info)
        else:
            messagebox.showinfo(t("app_name"), t("up_to_date", v=__version__))
        self.status_bar.configure(text="")

    # ------------------------------------------------------------------ eventos
    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "job":
                    self._ensure_row(data)
                    if data["state"] == "done":
                        self.status_bar.configure(text=t("done_status", title=(data["title"] or data["url"])[:80]))
                        self.bell()
                    elif data["state"] == "error":
                        self.status_bar.configure(text=t("failed_status"))
                elif kind == "log":
                    self.status_bar.configure(text=str(data)[:140])
                elif kind == "history":
                    self._refresh_history()
                elif kind == "login_test":
                    ok, key, args = data
                    self.login_result.configure(text=("✓  " if ok else "✗  ") + t(key, **args),
                                                text_color=GREEN if ok else RED)
                elif kind == "install_log":
                    self._log_install(data)
                elif kind == "install_done":
                    self._installing = False
                    self._refresh_deps()
                    if not self._missing():
                        self._log_install(t("all_ready"))
                elif kind == "update":
                    self._on_update_result(*data)
        except queue.Empty:
            pass
        except Exception:  # nunca deixa o loop de eventos morrer
            pass
        self.after(100, self._poll)

    def _on_close(self):
        if self.downloader.busy() and not messagebox.askyesno(t("app_name"), t("close_busy")):
            return
        self._save()
        self.destroy()
