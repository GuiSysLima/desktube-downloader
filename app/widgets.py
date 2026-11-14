# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Componentes visuais reutilizáveis, todos usando os tokens de theme.py."""
import os
import sys
import tkinter as tk
import weakref

import customtkinter as ctk

from . import motion, thumbs
from .theme import BUTTON_STYLES, C, CONTROL_H, RADIUS, SP, THUMB, font, glyph, icon_font, tk_font, tk_icon_font


# ---------------------------------------------------------------- recursos e ícone da janela
def resource_path(rel):
    """Caminho de um recurso, no código-fonte e no .exe (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


ICON_ICO = resource_path(os.path.join("assets", "icon.ico"))
ICON_PNG = resource_path(os.path.join("assets", "icon.png"))


def apply_icon(window):
    """Ícone da janela. O CustomTkinter aplica o dele ~200 ms após criar a janela; o nosso vem depois."""
    def _set():
        try:
            if sys.platform == "win32" and os.path.isfile(ICON_ICO):
                window.iconbitmap(ICON_ICO)
            elif os.path.isfile(ICON_PNG):
                img = tk.PhotoImage(file=ICON_PNG)
                window._icon_ref = img
                window.iconphoto(False, img)
        except Exception:
            pass
    _set()
    window.after(300, _set)


def flash_window(window):
    """Pisca o botão do app na barra de tarefas (Windows) para chamar atenção."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


# ---------------------------------------------------------------- imagens
_image_cache = {}


def load_image(path, size=THUMB):
    """Carrega uma imagem PNG no tamanho pedido (CTkImage se houver Pillow; senão PhotoImage)."""
    if not path or not os.path.isfile(path):
        return None
    key = (path, os.path.getmtime(path), size)
    if key in _image_cache:
        return _image_cache[key]
    img = None
    if thumbs.HAS_PIL:
        try:
            from PIL import Image
            img = ctk.CTkImage(light_image=Image.open(path), size=size)
        except Exception:
            img = None
    if img is None:
        try:
            raw = tk.PhotoImage(file=path)
            w = raw.width() or 1
            # aproxima a escala com zoom/subsample inteiros (sem Pillow)
            for z, s in ((1, 1), (2, 5), (1, 2), (2, 3), (1, 3), (1, 4)):
                if abs(w * z / s - size[0]) <= 4:
                    img = raw.zoom(z).subsample(s) if (z, s) != (1, 1) else raw
                    break
            else:
                img = raw.subsample(max(1, round(w / size[0])))
        except Exception:
            return None
    _image_cache[key] = img
    return img


# ---------------------------------------------------------------- dica (tooltip)
class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self._job = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text):
        self.text = text

    def _schedule(self, _e=None):
        self._cancel()
        self._job = self.widget.after(450, self._show)

    def _cancel(self):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if not text or self.tip:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        dark = ctk.get_appearance_mode() == "Dark"
        bg, fg = ("#111214", "#F2F3F5") if dark else ("#1B1B1F", "#FFFFFF")
        lbl = tk.Label(self.tip, text=text, bg=bg, fg=fg, padx=8, pady=4,
                       font=(font("caption").cget("family"), 9))
        lbl.pack()
        self.tip.update_idletasks()
        self.tip.wm_geometry(f"+{x - self.tip.winfo_width() // 2}+{y}")

    def _hide(self, _e=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ---------------------------------------------------------------- botões
def button(master, text, style="secondary", command=None, width=None, height=CONTROL_H, kind="label", **kw):
    opts = dict(BUTTON_STYLES[style])
    opts.update(kw)
    opts.setdefault("font", font(kind))
    opts.setdefault("corner_radius", RADIUS["button"])
    return ctk.CTkButton(master, text=text, command=command, height=height, width=width or 0, **opts)


class IconButton(ctk.CTkButton):
    """Botão só com ícone (Segoe Fluent Icons) + tooltip com o nome da ação."""

    def __init__(self, master, icon, tooltip="", style="ghost", size=CONTROL_H, icon_size=16, command=None, **kw):
        opts = dict(BUTTON_STYLES[style])
        opts.update(kw)
        opts.setdefault("corner_radius", RADIUS["button"])
        super().__init__(master, text=glyph(icon), width=size, height=size, font=icon_font(icon_size),
                         command=command, **opts)
        self.tooltip = Tooltip(self, tooltip) if tooltip else None

    def set_icon(self, icon):
        self.configure(text=glyph(icon))


def icon_label(master, icon, size=16, color=None, **kw):
    return ctk.CTkLabel(master, text=glyph(icon), font=icon_font(size), text_color=color or C["text2"], **kw)


# ---------------------------------------------------------------- selo (badge)
BADGE = {
    "success": (C["success_bg"], C["success"]),
    "warning": (C["warning_bg"], C["warning"]),
    "error": (C["error_bg"], C["error"]),
    "muted": (C["surface2"], C["text2"]),
    "accent": (C["accent_soft"], C["accent_text"]),
}


def badge(master, text, kind="muted"):
    bg, fg = BADGE[kind]
    return ctk.CTkLabel(master, text=f"  {text}  ", fg_color=bg, text_color=fg, corner_radius=RADIUS["pill"],
                        font=font("meta", weight="bold"), height=22)


def set_badge(lbl, text, kind):
    bg, fg = BADGE[kind]
    lbl.configure(text=f"  {text}  ", fg_color=bg, text_color=fg)


# ---------------------------------------------------------------- card com hover
class Card(ctk.CTkFrame):
    def __init__(self, master, hover=True, **kw):
        kw.setdefault("fg_color", C["card"])
        kw.setdefault("corner_radius", RADIUS["card"])
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C["card_border"])
        super().__init__(master, **kw)
        self._hover = hover
        if hover:
            self.bind("<Enter>", self._enter, add="+")
            self.bind("<Leave>", self._leave, add="+")

    def bind_children_hover(self):
        """Mantém o hover ao passar o mouse sobre os filhos."""
        if not self._hover:
            return
        for w in self._all_children(self):
            try:
                w.bind("<Enter>", self._enter, add="+")
                w.bind("<Leave>", self._leave, add="+")
            except Exception:
                pass

    @staticmethod
    def _all_children(w):
        for c in w.winfo_children():
            yield c
            yield from Card._all_children(c)

    def _enter(self, _e=None):
        self.configure(fg_color=C["card_hover"])

    def _leave(self, _e=None):
        try:
            x, y = self.winfo_pointerxy()
            inside = self.winfo_containing(x, y)
            while inside is not None:
                if inside is self:
                    return
                inside = inside.master
        except Exception:
            pass
        self.configure(fg_color=C["card"])


# ---------------------------------------------------------------- miniatura
class ThumbBox(ctk.CTkFrame):
    """Quadro 16:9 de tamanho fixo com a miniatura, ou um ícone enquanto não há imagem."""

    def __init__(self, master, audio=False, size=THUMB):
        super().__init__(master, width=size[0], height=size[1], fg_color=C["thumb_bg"],
                         corner_radius=RADIUS["thumb"])
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.label = ctk.CTkLabel(self, text=glyph("audio" if audio else "video"), text_color=C["text2"],
                                  font=icon_font(26), fg_color="transparent")
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        self._path, self._size, self._cb = None, size, None

    def on_click(self, callback):
        self._cb = callback
        for w in (self, self.label):
            w.configure(cursor="hand2" if callback else "")
            w.bind("<Button-1>", lambda e: self._cb and self._cb())

    def set_path(self, path):
        if path == self._path:
            return
        img = load_image(path, self._size)
        if img is not None:
            self._path = path
            self.label.configure(image=img, text="")

    def reset(self, audio=False):
        """Volta ao ícone (sem imagem)."""
        self._path = None
        self.label.configure(image="", text=glyph("audio" if audio else "video"))


# ---------------------------------------------------------------- aviso flutuante (snackbar)
class Toast:
    """Aviso temporário na parte de baixo da área de conteúdo (sem bloquear a interface)."""

    KINDS = {"info": ("info", C["accent"]), "success": ("check", C["success"]),
             "error": ("error", C["error"]), "warning": ("warning", C["warning"])}

    def __init__(self, parent):
        self.parent, self.frame, self._job, self._kind, self._label = parent, None, None, None, None

    def show(self, text, kind="info", ms=4000):
        # aviso do mesmo tipo já visível (ex.: progresso): só troca o texto, sem animar de novo
        if self.frame is not None and self._kind == kind and self.frame.winfo_exists():
            self._label.configure(text=text)
            if self._job:
                self.parent.after_cancel(self._job)
            self._job = self.parent.after(ms, self.hide)
            return
        self.hide()
        self._kind = kind
        icon, color = self.KINDS.get(kind, self.KINDS["info"])
        f = ctk.CTkFrame(self.parent, fg_color=C["card"], corner_radius=RADIUS["card"], border_width=1,
                         border_color=color)
        icon_label(f, icon, 16, color).pack(side="left", padx=(SP["md"], SP["sm"]), pady=SP["sm"])
        self._label = ctk.CTkLabel(f, text=text, font=font("body"), wraplength=520, justify="left")
        self._label.pack(side="left", padx=(0, SP["sm"]), pady=SP["sm"])
        IconButton(f, "cancel", size=28, icon_size=10, command=self.hide).pack(side="left", padx=(0, SP["sm"]))
        f.lift()
        self.frame = f
        rest, start = -SP["lg"], SP["lg"]       # entra deslizando de baixo (desacelerando)
        f.place(relx=0.5, rely=1.0, y=start if motion.enabled() else rest, anchor="s")
        motion.animate(f, "toast", motion.DUR["medium"],
                       lambda p: f.place_configure(y=round(start + (rest - start) * p)),
                       easing=motion.ease_out_back)
        self._job = self.parent.after(ms, self.hide)

    def hide(self):
        if self._job:
            try:
                self.parent.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.frame is not None:
            f, self.frame = self.frame, None
            try:
                y0 = int(f.place_info().get("y", -SP["lg"]))
            except Exception:
                y0 = -SP["lg"]

            def gone():
                try:
                    f.destroy()
                except Exception:
                    pass
            # sai mais rápido do que entrou, acelerando para baixo
            motion.animate(f, "toast", round(motion.DUR["short"] * motion.EXIT),
                           lambda p: f.place_configure(y=round(y0 + (SP["xxl"] + SP["lg"]) * p)),
                           gone, motion.ease_in)


# ---------------------------------------------------------------- diálogo de escolha
class ChoiceDialog(ctk.CTkToplevel):
    """Diálogo modal com botões que dizem a ação ("Fechar e baixar", "Apagar arquivo"...).
    buttons = [(texto, valor, estilo)] da esquerda para a direita; o último é a ação principal.
    show() -> valor clicado, ou None se fechado/Esc."""

    def __init__(self, master, title, heading, message="", buttons=(), detail="", warning="",
                 icon="info", icon_color=None):
        super().__init__(master)
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=C["card"])
        self.grid_columnconfigure(1, weight=1)
        icon_label(self, icon, 22, icon_color or C["accent"]).grid(
            row=0, column=0, sticky="n", padx=(SP["xl"], SP["md"]), pady=(SP["xl"], 0))
        ctk.CTkLabel(self, text=heading, font=font("section"), anchor="w", justify="left", wraplength=440).grid(
            row=0, column=1, sticky="ew", padx=(0, SP["xl"]), pady=(SP["xl"], SP["xs"]))
        r = 1
        for text, color, kind in ((message, C["text"], "body"), (detail, C["text2"], "meta"),
                                  (warning, C["error"], "body")):
            if text:
                ctk.CTkLabel(self, text=text, anchor="w", justify="left", wraplength=440, text_color=color,
                             font=font(kind)).grid(row=r, column=1, sticky="ew", padx=(0, SP["xl"]),
                                                   pady=(SP["xs"], 0))
                r += 1
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=r, column=0, columnspan=2, sticky="e", padx=SP["xl"], pady=SP["xl"])
        for text, value, style in buttons:
            button(row, text, style, command=lambda v=value: self._done(v)).pack(side="left", padx=(SP["sm"], 0))
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(None))
        self.bind("<Escape>", lambda e: self._done(None))
        # Enter confirma a ação principal — exceto se ela for destrutiva (ex.: apagar arquivo)
        if buttons and buttons[-1][2] not in ("danger", "danger_ghost"):
            last = buttons[-1][1]
            self.bind("<Return>", lambda e: self._done(last))
        apply_icon(self)

    def _done(self, value):
        self.result = value
        self.destroy()

    def _focus(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def show(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_width()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        motion.fade_in_window(self)
        self.after(50, self._focus)
        self.master.wait_window(self)
        return self.result


# ---------------------------------------------------------------- leitor de texto (licença)
class TextDialog(ctk.CTkToplevel):
    """Janela somente leitura para textos longos (LICENSE, NOTICE)."""

    def __init__(self, master, title, text):
        super().__init__(master)
        self.title(title)
        self.geometry("760x620")
        self.transient(master)
        self.configure(fg_color=C["bg"])
        box = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(family="Consolas", size=12), corner_radius=0,
                             border_width=0)
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.configure(state="disabled")
        self.bind("<Escape>", lambda e: self.destroy())
        apply_icon(self)
        motion.fade_in_window(self)
        self.after(50, self.lift)


# ---------------------------------------------------------------- linha de lista com hover
class HoverRow(ctk.CTkFrame):
    """Linha de lista (sem borda) que destaca ao passar o mouse — como as listas do Spotify/Windows."""

    def __init__(self, master, base=None, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("corner_radius", RADIUS["card"])
        super().__init__(master, **kw)
        self._normal = kw["fg_color"]
        self._base = base or C["bg"]          # cor de fundo atrás da linha (para a transição)
        self._hot = False
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def bind_children(self, double_click=None, right_click=None):
        """Propaga hover (e opcionalmente duplo clique / botão direito) para os filhos."""
        for w in Card._all_children(self):
            try:
                w.bind("<Enter>", self._enter, add="+")
                w.bind("<Leave>", self._leave, add="+")
                if double_click and not isinstance(w, ctk.CTkButton):
                    w.bind("<Double-Button-1>", lambda e=None: double_click(), add="+")
                if right_click:
                    w.bind("<Button-3>", right_click, add="+")
            except Exception:
                pass
        if double_click:
            self.bind("<Double-Button-1>", lambda e=None: double_click(), add="+")
        if right_click:
            self.bind("<Button-3>", right_click, add="+")

    def _enter(self, _e=None):
        if self._hot:
            return
        self._hot = True
        motion.fade_color(self, "fg_color", self._base, C["row_hover"], motion.DUR["micro"])

    def _leave(self, _e=None):
        try:
            x, y = self.winfo_pointerxy()
            inside = self.winfo_containing(x, y)
            while inside is not None:
                if inside is self:
                    return
                inside = inside.master
        except Exception:
            pass
        if not self._hot:
            return
        self._hot = False
        motion.fade_color(self, "fg_color", C["row_hover"], self._base,
                          round(motion.DUR["micro"] * motion.EXIT), final=self._normal, easing=motion.ease_in)


def divider(master):
    return ctk.CTkFrame(master, height=1, fg_color=C["divider"], corner_radius=0)


# ---------------------------------------------------------------- abas sublinhadas
class TabBar(ctk.CTkFrame):
    """Abas em texto com sublinhado na aba ativa (no lugar de botões segmentados)."""

    def __init__(self, master, tabs, command):
        super().__init__(master, fg_color="transparent")
        self._items, self.command, self._current, self._pos = {}, command, None, None
        for i, (key, label) in enumerate(tabs):
            lbl = ctk.CTkLabel(self, text=label, font=font("label"), text_color=C["text2"], cursor="hand2",
                               width=0, height=26)
            lbl.grid(row=0, column=i, sticky="w", padx=(0, SP["xl"]))
            lbl.bind("<Button-1>", lambda e, k=key: self.command(k))
            self._items[key] = lbl
        self.grid_rowconfigure(1, minsize=4)
        # um único sublinhado que desliza até a aba escolhida (continuidade visual)
        # (tk.Frame: o CTkFrame não aceita largura no place)
        self.indicator = tk.Frame(self, height=2, bd=0, highlightthickness=0, bg=motion.resolve(C["accent"]))

    def select(self, key):
        self._current = key
        self.indicator.configure(bg=motion.resolve(C["accent"]))   # acompanha o tema atual
        for k, lbl in self._items.items():
            lbl.configure(text_color=C["text"] if k == key else C["text2"])
        self._move()

    def _move(self, tries=0):
        lbl = self._items.get(self._current)
        if lbl is None:
            return
        x, w = lbl.winfo_x(), lbl.winfo_width()
        if w <= 1:                        # ainda não foi desenhado: tenta de novo em seguida
            if tries < 20:
                self.after(30, lambda: self._move(tries + 1))
            return
        y = lbl.winfo_y() + lbl.winfo_height() + 1
        if self._pos is None or not self.indicator.winfo_ismapped():
            self._pos = (x, w)
            self.indicator.place(x=x, y=y, width=w, height=2)
            return
        x0, w0 = self._pos
        self._pos = (x, w)

        def step(p):
            self.indicator.place_configure(x=round(x0 + (x - x0) * p), width=max(1, round(w0 + (w - w0) * p)),
                                           y=y)
        motion.animate(self.indicator, "slide", motion.DUR["medium"], step, easing=motion.ease_out_expo)


# ---------------------------------------------------------------- grupo de configurações (estilo Windows 11)
class SettingsGroup(ctk.CTkFrame):
    """Bloco com linhas "título + descrição | controle", separadas por divisórias finas."""

    def __init__(self, master, title=""):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        r = 0
        if title:
            ctk.CTkLabel(self, text=title, font=font("label"), anchor="w").grid(
                row=0, column=0, sticky="w", pady=(0, SP["sm"]))
            r = 1
        self.box = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=RADIUS["card"])
        self.box.grid(row=r, column=0, sticky="ew")
        self.box.grid_columnconfigure(0, weight=1)
        self._rows = 0

    def add_row(self, title, desc="", wrap=440):
        """Cria uma linha e devolve (frame_da_direita, label_da_descrição)."""
        if self._rows:
            divider(self.box).grid(row=self._rows * 2 - 1, column=0, sticky="ew", padx=SP["lg"])
        row = ctk.CTkFrame(self.box, fg_color="transparent")
        row.grid(row=self._rows * 2, column=0, sticky="ew", padx=SP["lg"], pady=SP["md"])
        row.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, text=title, font=font("body"), anchor="w").pack(anchor="w")
        d = ctk.CTkLabel(left, text=desc, font=font("meta"), text_color=C["text2"], anchor="w", justify="left",
                         wraplength=wrap)
        if desc:
            d.pack(anchor="w")
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(SP["lg"], 0))
        self._rows += 1
        return right, d


# ---------------------------------------------------------------- linhas "leves" (Tk puro)
# Widgets do CustomTkinter desenham tudo num Canvas e custam ~10 ms cada; uma lista com centenas de
# linhas travava a interface. As listas grandes (fila de reprodução, Biblioteca) usam Tk puro, com as
# mesmas cores/fontes do tema, a escala de DPI aplicada à mão e recoloração ao trocar claro/escuro.
_light_rows = weakref.WeakSet()
_photo_cache = {}
_tracker_on = False


def _recolor_all(_mode=None):
    for row in list(_light_rows):
        try:
            if row.winfo_exists():
                row.recolor()
        except Exception:
            pass


def load_photo(path, size):
    """PhotoImage (para tk.Label) no tamanho pedido, com cache."""
    if not path or not os.path.isfile(path):
        return None
    key = (path, os.path.getmtime(path), size)
    if key in _photo_cache:
        return _photo_cache[key]
    img = None
    if thumbs.HAS_PIL:
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as im:
                img = ImageTk.PhotoImage(im.convert("RGB").resize(size, Image.LANCZOS))
        except Exception:
            img = None
    if img is None:
        img = load_image(path, size) if not thumbs.HAS_PIL else None   # sem Pillow, load_image já é PhotoImage
    if img is not None:
        if len(_photo_cache) > 600:
            _photo_cache.clear()
        _photo_cache[key] = img
    return img


class LightThumb(tk.Frame):
    """Miniatura de tamanho fixo em Tk puro (mesma interface do ThumbBox: set_path, reset, on_click)."""

    def __init__(self, master, size, scale, audio=False):
        self.size = (round(size[0] * scale), round(size[1] * scale))
        super().__init__(master, width=self.size[0], height=self.size[1], bd=0, highlightthickness=0,
                         bg=motion.resolve(C["thumb_bg"]))
        self.pack_propagate(False)
        self.scale, self._path, self._cb = scale, None, None
        self.label = tk.Label(self, bd=0, bg=motion.resolve(C["thumb_bg"]), fg=motion.resolve(C["text2"]),
                              font=tk_icon_font(18, scale))
        self.label.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        self.reset(audio)

    def reset(self, audio=False):
        self._path = None
        self.label.configure(image="", text=glyph("audio" if audio else "video"))

    def set_path(self, path):
        if path == self._path:
            return
        img = load_photo(path, self.size)
        if img is not None:
            self._path = path
            self.label.configure(image=img, text="")
            self.label.image = img

    def on_click(self, callback):
        self._cb = callback
        for w in (self, self.label):
            w.configure(cursor="hand2" if callback else "")
            w.bind("<Button-1>", lambda e: self._cb and self._cb())

    def recolor(self):
        self.configure(bg=motion.resolve(C["thumb_bg"]))
        self.label.configure(bg=motion.resolve(C["thumb_bg"]), fg=motion.resolve(C["text2"]))


class LightRow(tk.Frame):
    """Linha de lista em Tk puro com destaque animado ao passar o mouse."""

    def __init__(self, master, base=None):
        global _tracker_on
        self.scale = ctk.ScalingTracker.get_widget_scaling(master)
        self._base = base or C["bg"]
        super().__init__(master, bd=0, highlightthickness=0, bg=motion.resolve(self._base))
        self._parts, self._thumbs, self._hot, self._tint = [], [], False, None
        _light_rows.add(self)
        if not _tracker_on:
            ctk.AppearanceModeTracker.add(_recolor_all)
            _tracker_on = True

    def px(self, v):
        return round(v * self.scale)

    # ---- construção
    def label(self, master=None, text="", kind="body", fg=None, icon_size=None, **kw):
        lbl = tk.Label(master or self, text=text, bd=0, anchor=kw.pop("anchor", "w"), justify="left",
                       bg=motion.resolve(self._base), fg=motion.resolve(fg or C["text"]),
                       font=tk_icon_font(icon_size, self.scale) if icon_size else tk_font(kind, self.scale), **kw)
        self._parts.append([lbl, fg or C["text"]])
        return lbl

    def frame(self, master=None):
        f = tk.Frame(master or self, bd=0, highlightthickness=0, bg=motion.resolve(self._base))
        self._parts.append([f, None])
        return f

    def thumb(self, master=None, size=THUMB, audio=False):
        box = LightThumb(master or self, size, self.scale, audio)
        self._thumbs.append(box)
        return box

    def set_fg(self, widget, token):
        for part in self._parts:
            if part[0] is widget:
                part[1] = token
        widget.configure(fg=motion.resolve(token))

    def bind_parts(self, double_click=None, right_click=None):
        widgets = [self] + [p[0] for p in self._parts] + [w for b in self._thumbs for w in (b, b.label)]
        for w in widgets:
            w.bind("<Enter>", self._enter, add="+")
            w.bind("<Leave>", self._leave, add="+")
            if double_click:
                w.bind("<Double-Button-1>", lambda e: double_click(), add="+")
            if right_click:
                w.bind("<Button-3>", right_click, add="+")

    # ---- cores
    def set_bg(self, color):
        self.configure(bg=color)
        for w, _fg in self._parts:
            w.configure(bg=color)

    def tint(self, token):
        """Fundo fixo (ex.: item sendo arrastado). None volta ao normal."""
        self._tint = token
        motion.cancel(self, "hover")
        self.set_bg(motion.resolve(token or (C["row_hover"] if self._hot else self._base)))

    def flash(self, token, duration=motion.DUR["medium"]):
        """Acende e apaga (ex.: mostra onde o item arrastado foi parar)."""
        start, end = token, self._base
        motion.animate(self, "hover", duration, lambda p: self.set_bg(motion.mix(start, end, p)),
                       easing=motion.ease_in_out)

    def recolor(self):
        self.set_bg(motion.resolve(self._tint or (C["row_hover"] if self._hot else self._base)))
        for w, fg in self._parts:
            if fg is not None:
                w.configure(fg=motion.resolve(fg))
        for b in self._thumbs:
            b.recolor()

    def _enter(self, _e=None):
        if self._hot:
            return
        self._hot = True
        if self._tint is None:
            motion.animate(self, "hover", motion.DUR["micro"],
                           lambda p: self.set_bg(motion.mix(self._base, C["row_hover"], p)))

    def _leave(self, _e=None):
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            while w is not None:
                if w is self:
                    return
                w = w.master
        except Exception:
            pass
        if not self._hot:
            return
        self._hot = False
        if self._tint is None:
            motion.animate(self, "hover", round(motion.DUR["micro"] * motion.EXIT),
                           lambda p: self.set_bg(motion.mix(C["row_hover"], self._base, p)), easing=motion.ease_in)
