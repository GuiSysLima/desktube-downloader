# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Página Configurações: abas Geral / Login / Componentes / Sobre, com grupos no estilo do
Windows 11 (título + descrição à esquerda, controle à direita, divisórias finas)."""
import os
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from .. import AUTHOR, COPYRIGHT_YEAR, PROJECT_URL, __version__, browsers, deps, i18n, motion, updater
from ..config import config_dir
from ..i18n import t
from ..theme import BUTTON_STYLES, C, RADIUS, SP, font
from ..widgets import ICON_PNG, SettingsGroup, TabBar, TextDialog, button, load_image, resource_path
from .common import open_path

THEMES = ("system", "light", "dark")
DEP_ROWS = ("ffmpeg", "deno", "node", "vlc")
OPTIONAL_DEPS = ("node", "vlc")
SECTIONS = ("general", "login", "components", "about")
WRAP = 600


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text=t("nav_settings"), font=font("title"), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, SP["md"]))
        self.tabs = TabBar(self, [(k, t(f"set_{k}")) for k in SECTIONS], self.show)
        self.tabs.grid(row=1, column=0, sticky="w", pady=(0, SP["lg"]))
        self.sections = {}
        for key in SECTIONS:
            frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
            frame.grid_columnconfigure(0, weight=1)
            self.sections[key] = frame
            getattr(self, f"_build_{key}")(frame)
        self.current = None
        self.show("general")

    def show(self, key):
        self.current = key
        for k, f in self.sections.items():
            if k == key:
                f.grid(row=2, column=0, sticky="nsew")
            else:
                f.grid_remove()
        self.tabs.select(key)

    @staticmethod
    def _group(parent, row, title=""):
        g = SettingsGroup(parent, title)
        g.grid(row=row, column=0, sticky="ew", pady=(0, SP["xl"]), padx=(0, SP["sm"]))
        return g

    # ================================================================ Geral
    def _build_general(self, p):
        app, s = self.app, self.app.settings
        g = self._group(p, 0, t("grp_appearance"))
        right, _ = g.add_row(t("sec_language"), t("language_desc"))
        lang = ctk.CTkOptionMenu(right, values=list(i18n.LANGUAGES.values()), width=200, height=32,
                                 command=app.change_language)
        lang.set(i18n.LANGUAGES[i18n.current()])
        lang.pack()
        right, _ = g.add_row(t("sec_theme"), t("theme_desc"))
        self._themes = {t(f"theme_{k}"): k for k in THEMES}
        seg = ctk.CTkSegmentedButton(right, values=list(self._themes), height=32, command=self._on_theme)
        seg.set(t(f"theme_{s.theme if s.theme in THEMES else 'system'}"))
        seg.pack()

        right, _ = g.add_row(t("opt_animations"), t("opt_animations_desc"))
        self.anim = ctk.CTkSwitch(right, text="", width=44, command=self._on_animations)
        (self.anim.select if s.animations else self.anim.deselect)()
        self.anim.pack()

        g = self._group(p, 1, t("grp_downloads"))
        right, self.out_desc = g.add_row(t("sec_folder"), s.output_dir)
        button(right, t("btn_choose"), "secondary", app.choose_output, kind="body", height=32).pack()
        self.switches = {}
        for key, attr in (("opt_metadata", "embed_metadata"), ("opt_thumbnail", "embed_thumbnail"),
                          ("opt_clipboard", "watch_clipboard")):
            right, _ = g.add_row(t(key), t(key + "_desc"))
            sw = ctk.CTkSwitch(right, text="", width=44, command=self._on_options)
            (sw.select if getattr(s, attr) else sw.deselect)()
            sw.pack()
            self.switches[attr] = sw
        right, _ = g.add_row(t("sub_langs_label").rstrip(":"), t("sub_langs_desc"))
        self.langs = ctk.CTkEntry(right, width=160, height=32)
        self.langs.insert(0, s.sub_langs)
        self.langs.pack()
        self.langs.bind("<FocusOut>", lambda e: self._on_options())

    def _on_theme(self, label):
        self.app.settings.theme = self._themes.get(label, "system")
        ctk.set_appearance_mode(self.app.settings.theme)
        self.app.save()

    def _on_animations(self):
        self.app.settings.animations = bool(self.anim.get())
        motion.set_enabled(self.app.settings.animations)
        self.app.save()

    def _on_options(self):
        s = self.app.settings
        for attr, sw in self.switches.items():
            setattr(s, attr, bool(sw.get()))
        s.sub_langs = self.langs.get().strip() or "pt.*,en.*"
        self.app.save()

    def set_output_text(self, path):
        self.out_desc.configure(text=path)

    # ================================================================ Login
    def _build_login(self, p):
        app, s = self.app, self.app.settings
        ctk.CTkLabel(p, text=t("sec_login_desc"), font=font("body"), text_color=C["text2"], anchor="w",
                     justify="left", wraplength=WRAP + 100).grid(row=0, column=0, sticky="w", pady=(0, SP["lg"]))
        g = self._group(p, 1, t("sec_login"))
        installed = browsers.installed_keys()
        self._browsers = {t("browser_none"): "none"}
        for k, b in browsers.BROWSERS.items():
            self._browsers[f"{b.label}  {t('detected')}" if k in installed else b.label] = k
        self._browsers[t("browser_file")] = "file"
        right, _ = g.add_row(t("browser_label").rstrip(":"), t("browser_desc"))
        self.browser = ctk.CTkOptionMenu(right, values=list(self._browsers), width=240, height=32,
                                         command=self._on_browser)
        self.browser.set(next((lbl for lbl, k in self._browsers.items() if k == s.browser), t("browser_none")))
        self.browser.pack()
        right, self.cookie_desc = g.add_row(t("browser_file"), s.cookies_file or t("cookie_placeholder"))
        self.cookie_row = right.master
        button(right, t("btn_choose"), "secondary", self._choose_cookie, kind="body", height=32).pack()
        right, self.result = g.add_row(t("btn_test_login"), t("test_login_desc"))
        button(right, t("btn_test_login"), "accent", app.test_login, kind="body", height=32).pack()
        self.result_default = t("test_login_desc")

        self.tip = ctk.CTkLabel(p, text="", font=font("meta"), text_color=C["text2"], anchor="w", justify="left",
                                wraplength=WRAP + 100)
        self.tip.grid(row=2, column=0, sticky="w")
        self._update_cookie_widgets()

    def _on_browser(self, label):
        self.app.settings.browser = self._browsers.get(label, "none")
        self.set_login_result(None)
        self._update_cookie_widgets()
        self.app.pages["download"].refresh_login()
        self.app.save()

    def _update_cookie_widgets(self):
        """A linha do cookies.txt só aparece quando essa opção é escolhida."""
        if self.app.settings.browser == "file":
            self.cookie_row.grid()
        else:
            self.cookie_row.grid_remove()
        self.tip.configure(text=self.app.login_tip_text())

    def _choose_cookie(self):
        path = filedialog.askopenfilename(filetypes=[("Cookies", "*.txt"), (t("all_files"), "*.*")])
        if path:
            path = os.path.normpath(path)
            self.app.settings.cookies_file = path
            self.cookie_desc.configure(text=path)
            self.app.pages["download"].refresh_login()
            self.app.save()

    def set_login_result(self, ok, text=""):
        if not text:
            self.result.configure(text=self.result_default, text_color=C["text2"])
            return
        color = C["text2"] if ok is None else (C["success"] if ok else C["error"])
        self.result.configure(text=text, text_color=color)

    # ================================================================ Componentes
    def _build_components(self, p):
        app = self.app
        ctk.CTkLabel(p, text=t("components_intro"), font=font("body"), text_color=C["text2"], anchor="w",
                     justify="left", wraplength=WRAP + 100).grid(row=0, column=0, sticky="w", pady=(0, SP["lg"]))
        g = self._group(p, 1)
        self.dep = {}
        for name in DEP_ROWS:
            right, desc = g.add_row(deps.COMPONENTS[name].label, t(f"dep_desc_{name}"), wrap=330)
            status = ctk.CTkLabel(right, text="", font=font("meta"), width=110, anchor="e")
            status.pack(side="left", padx=(0, SP["md"]))
            locate = button(right, t("btn_locate"), "ghost", lambda n=name: app.locate_dep(n), kind="body",
                            height=32)
            locate.pack(side="left", padx=(0, SP["xs"]))
            btn = button(right, t("btn_install"), "accent", lambda n=name: app.dep_action(n), kind="body",
                         width=112, height=32)
            btn.pack(side="left")
            self.dep[name] = (status, desc, locate, btn)
        foot = ctk.CTkFrame(p, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", pady=(0, SP["md"]), padx=(0, SP["sm"]))
        ctk.CTkLabel(foot, text=f"yt-dlp {deps.ytdlp_version()}", font=font("meta"), text_color=C["text2"]).pack(
            side="left")
        button(foot, t("btn_recheck"), "secondary", app.refresh_deps, kind="body", height=32).pack(side="right")
        self.log_box = ctk.CTkFrame(p, fg_color="transparent")
        ctk.CTkLabel(self.log_box, text=t("log_title"), font=font("label"), anchor="w").pack(anchor="w",
                                                                                         pady=(0, SP["sm"]))
        self.log = ctk.CTkTextbox(self.log_box, height=150, font=ctk.CTkFont(family="Consolas", size=11),
                                  corner_radius=RADIUS["card"], fg_color=C["card"])
        self.log.pack(fill="x")
        self.log.configure(state="disabled")

    def update_deps(self, status, busy):
        for name, (st, desc, locate, btn) in self.dep.items():
            path = status.get(name)
            base = t(f"dep_desc_{name}")
            if path:
                st.configure(text="✓  " + t("badge_installed"), text_color=C["success"])
                desc.configure(text=f"{base}\n{path}")
                btn.configure(text=t("btn_uninstall"), **BUTTON_STYLES["danger_ghost"])
                locate.pack_forget()
            else:
                optional = name in OPTIONAL_DEPS
                st.configure(text=t("badge_optional") if optional else t("badge_missing"),
                             text_color=C["text2"] if optional else C["error"])
                desc.configure(text=base)
                btn.configure(text=t("btn_install"), **BUTTON_STYLES["accent"])
                if not locate.winfo_ismapped():
                    locate.pack(side="left", padx=(0, SP["xs"]), before=btn)
            btn.configure(state="disabled" if busy else "normal")
            locate.configure(state="disabled" if busy else "normal")

    def log_line(self, line):
        if not self.log_box.winfo_ismapped():
            self.log_box.grid(row=3, column=0, sticky="ew", padx=(0, SP["sm"]))
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ================================================================ Sobre
    def _build_about(self, p):
        app = self.app
        brand = ctk.CTkFrame(p, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", pady=(0, SP["xl"]))
        logo = load_image(ICON_PNG, (56, 56))
        if logo is not None:
            ctk.CTkLabel(brand, image=logo, text="").pack(side="left", padx=(0, SP["lg"]))
        txt = ctk.CTkFrame(brand, fg_color="transparent")
        txt.pack(side="left")
        ctk.CTkLabel(txt, text=t("app_name"), font=font("title"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt, text=t("app_tagline"), font=font("body"), text_color=C["text2"], anchor="w").pack(
            anchor="w")

        g = self._group(p, 1, t("grp_version"))
        version = t("version", v=__version__)
        if updater.is_dev():
            version += "  ·  " + t("dev_build")
        right, self.update_desc = g.add_row(version, f"yt-dlp {deps.ytdlp_version()}")
        self.update_btn = button(right, t("btn_check_updates"), "accent", app.check_updates, kind="body",
                                 height=32)
        self.update_btn.pack()
        right, _ = g.add_row(t("auto_update"), t("auto_update_desc"))
        self.auto = ctk.CTkSwitch(right, text="", width=44, command=self._on_auto)
        (self.auto.select if app.settings.auto_update_check else self.auto.deselect)()
        self.auto.pack()
        right, _ = g.add_row(t("btn_project_page"), PROJECT_URL)
        button(right, t("btn_open"), "secondary", lambda: webbrowser.open(PROJECT_URL), kind="body",
               height=32).pack()
        right, _ = g.add_row(t("btn_open_log"), t("open_log_desc"))
        button(right, t("btn_open"), "secondary", lambda: open_path(os.path.join(config_dir(), "app.log")),
               kind="body", height=32).pack()

        # licença e créditos: avisos exigidos pela GPL-3.0; o crédito ao autor é obrigatório pelos
        # termos adicionais da seção 7(b) — ver NOTICE
        g = self._group(p, 2, t("sec_license"))
        right, _ = g.add_row(f"© {COPYRIGHT_YEAR} {AUTHOR}", f"VidNeon by {AUTHOR}  —  {PROJECT_URL}")
        right, _ = g.add_row("GNU GPL-3.0", t("legal_notice"))
        button(right, t("btn_view"), "secondary", lambda: self._show_text("LICENSE", t("btn_view_license")),
               kind="body", height=32).pack()
        right, _ = g.add_row(t("btn_view_notice"), t("third_party"))
        button(right, t("btn_view"), "secondary", lambda: self._show_text("NOTICE", t("btn_view_notice")),
               kind="body", height=32).pack()

    def _on_auto(self):
        self.app.settings.auto_update_check = bool(self.auto.get())
        self.app.save()

    def set_update_busy(self, busy, text=""):
        self.update_btn.configure(state="disabled" if busy else "normal")
        if text:
            self.update_desc.configure(text=text)

    def _show_text(self, filename, title):
        """Mostra LICENSE/NOTICE numa janela de leitura (o arquivo vai junto no .exe)."""
        try:
            with open(resource_path(filename), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            webbrowser.open("https://www.gnu.org/licenses/gpl-3.0.html" if filename == "LICENSE" else PROJECT_URL)
            return
        TextDialog(self.app, f"{t('app_name')} — {title}", text)
