"""Player interno de vídeo/áudio, baseado no VLC (libvlc) embutido numa janela do app.

O VLC precisa estar instalado (Configurações › Componentes). Sem ele, o app abre o arquivo
no player padrão do Windows.
"""
import ctypes
import os
import sys
import tkinter as tk

import customtkinter as ctk

from . import deps
from .i18n import t
from .theme import C, SP, font, glyph, icon_font

_vlc = None          # módulo vlc carregado
_load_error = None   # motivo da falha, se houver
_tried = False


def reset():
    """Permite tentar carregar o VLC de novo (ex.: depois de instalá-lo)."""
    global _tried, _vlc, _load_error
    if _vlc is None:
        _tried, _load_error = False, None


def load_vlc():
    """Carrega o python-vlc com segurança. Retorna o módulo ou None (nunca encerra o app)."""
    global _vlc, _load_error, _tried
    if _tried:
        return _vlc
    _tried = True
    try:
        if sys.platform == "win32":
            vlc_dir = deps.find_vlc_dir()
            if not vlc_dir:
                _load_error = "VLC not installed"
                return None
            lib = os.path.join(vlc_dir, "libvlc.dll")
            try:
                os.add_dll_directory(vlc_dir)
            except Exception:
                pass
            ctypes.CDLL(lib)  # testa antes: se falhar (ex.: VLC 32 bits), não deixa o python-vlc fechar o app
            os.environ["PYTHON_VLC_LIB_PATH"] = lib
            plugins = os.path.join(vlc_dir, "plugins")
            if os.path.isdir(plugins):
                os.environ["PYTHON_VLC_MODULE_PATH"] = plugins
        import vlc  # type: ignore
        vlc.Instance  # noqa: B018 — garante que o módulo carregou de fato
        _vlc = vlc
    except BaseException as e:  # o python-vlc pode chamar sys.exit() se não achar a libvlc
        _load_error = f"{type(e).__name__}: {e}"
        _vlc = None
    return _vlc


def available() -> bool:
    return load_vlc() is not None


def _fmt(ms):
    if not ms or ms < 0:
        return "0:00"
    s = int(ms // 1000)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class PlayerWindow(ctk.CTkToplevel):
    """Janela do player: área de vídeo (ou capa, para áudio) + controles."""

    AUDIO_EXT = (".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".flac")

    def __init__(self, master, path, title="", cover_image=None, on_open_external=None):
        super().__init__(master)
        vlc = load_vlc()
        self.path = path
        self.on_open_external = on_open_external
        self.is_audio = path.lower().endswith(self.AUDIO_EXT)
        self._dragging = False
        self._closing = False
        self.title(title or os.path.basename(path))
        self.geometry("700x440" if self.is_audio else "960x600")
        self.minsize(420, 300)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- área de exibição
        from .widgets import IconButton, button, icon_label  # import local: evita ciclo widgets<->player
        self.configure(fg_color=C["bg"])
        if self.is_audio:
            area = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0)
            area.grid(row=0, column=0, sticky="nsew")
            inner = ctk.CTkFrame(area, fg_color="transparent")
            inner.place(relx=0.5, rely=0.5, anchor="center")
            if cover_image is not None:
                ctk.CTkLabel(inner, image=cover_image, text="").pack(pady=(0, SP["md"]))
            else:
                icon_label(inner, "audio", 64, C["accent"]).pack(pady=(0, SP["md"]))
            ctk.CTkLabel(inner, text=self.title(), font=font("section"), wraplength=520).pack()
            self.video = None
        else:
            self.video = tk.Frame(self, bg="black", highlightthickness=0)
            self.video.grid(row=0, column=0, sticky="nsew")
            self.video.bind("<Double-Button-1>", lambda e: self._toggle_fullscreen())
            self.video.bind("<Button-1>", lambda e: self.toggle())

        # --- controles
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=C["card"], border_width=0)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_columnconfigure(4, weight=1)
        self.play_btn = IconButton(bar, "pause", t("tip_play"), "accent", size=40, icon_size=16, command=self.toggle)
        self.play_btn.grid(row=0, column=0, padx=(SP["md"], SP["xs"]), pady=SP["sm"])
        IconButton(bar, "back10", "−10 s", command=lambda: self.skip(-10000)).grid(row=0, column=1, padx=2)
        IconButton(bar, "fwd10", "+10 s", command=lambda: self.skip(10000)).grid(row=0, column=2, padx=2)
        self.time_label = ctk.CTkLabel(bar, text="0:00 / 0:00", width=110, font=font("meta"), text_color=C["text2"])
        self.time_label.grid(row=0, column=3, padx=SP["sm"])
        self.seek = ctk.CTkSlider(bar, from_=0, to=1000, number_of_steps=1000, command=self._on_seek_drag)
        self.seek.set(0)
        self.seek.grid(row=0, column=4, sticky="ew", padx=SP["sm"])
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        self.seek.bind("<ButtonRelease-1>", self._on_seek_release)
        icon_label(bar, "volume", 14).grid(row=0, column=5, padx=(SP["sm"], 0))
        self.volume = ctk.CTkSlider(bar, from_=0, to=100, width=100, command=self._on_volume)
        self.volume.set(80)
        self.volume.grid(row=0, column=6, padx=(SP["xs"], SP["sm"]))
        if not self.is_audio:
            IconButton(bar, "fullscreen", "F", command=self._toggle_fullscreen).grid(row=0, column=7, padx=2)
        button(bar, t("btn_open_external"), "secondary", self._open_external, kind="body").grid(
            row=0, column=8, padx=(SP["xs"], SP["md"]))

        # --- atalhos
        self.bind("<space>", lambda e: self.toggle())
        self.bind("<Left>", lambda e: self.skip(-5000))
        self.bind("<Right>", lambda e: self.skip(5000))
        self.bind("<Escape>", lambda e: self._exit_fullscreen_or_close())
        self.bind("<f>", lambda e: self._toggle_fullscreen())
        self.protocol("WM_DELETE_WINDOW", self.close)

        # --- VLC
        self.instance = vlc.Instance("--no-video-title-show", "--quiet")
        self.player = self.instance.media_player_new()
        self.player.set_media(self.instance.media_new(path))
        self.after(150, self._start)

    # -------------------------------------------------------------- controle
    def _start(self):
        if self.video is not None:
            self.update_idletasks()
            handle = self.video.winfo_id()
            if sys.platform == "win32":
                self.player.set_hwnd(handle)
            else:
                self.player.set_xwindow(handle)
        try:  # deixa cliques e teclas chegarem à janela do app, não ao VLC
            self.player.video_set_mouse_input(False)
            self.player.video_set_key_input(False)
        except Exception:
            pass
        self.player.audio_set_volume(int(self.volume.get()))
        self.player.play()
        self.focus_force()
        self._tick()

    def toggle(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            if self._ended():
                self.player.stop()
            self.player.play()

    def skip(self, delta_ms):
        length = self.player.get_length()
        if length > 0:
            self.player.set_time(int(max(0, min(length - 500, self.player.get_time() + delta_ms))))

    def _ended(self):
        vlc = load_vlc()
        return self.player.get_state() == vlc.State.Ended

    def _on_seek_drag(self, value):
        self._dragging = True
        length = self.player.get_length()
        if length > 0:
            self.time_label.configure(text=f"{_fmt(length * value / 1000)} / {_fmt(length)}")

    def _on_seek_release(self, _event=None):
        self.player.set_position(float(self.seek.get()) / 1000)
        self._dragging = False

    def _on_volume(self, value):
        self.player.audio_set_volume(int(value))

    def _tick(self):
        if self._closing:
            return
        try:
            length, now = self.player.get_length(), self.player.get_time()
            if not self._dragging and length > 0:
                self.seek.set(1000 * now / length)
                self.time_label.configure(text=f"{_fmt(now)} / {_fmt(length)}")
            self.play_btn.set_icon("pause" if self.player.is_playing() else "play")
        except Exception:
            pass
        self.after(250, self._tick)

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def _exit_fullscreen_or_close(self):
        if self.attributes("-fullscreen"):
            self.attributes("-fullscreen", False)
        else:
            self.close()

    def _open_external(self):
        if self.on_open_external:
            self.player.pause()
            self.on_open_external(self.path)

    def close(self):
        self._closing = True
        try:
            self.player.stop()
            self.player.release()
            self.instance.release()
        except Exception:
            pass
        self.destroy()
