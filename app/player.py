# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Reprodução com fila (estilo Spotify), baseada no VLC (libvlc).

Este módulo não tem interface: a classe Playback guarda a fila e controla o VLC.
A interface (barra "tocando agora" e página Reproduzindo) fica em app/ui/playing.py.
O VLC precisa estar instalado (Configurações › Componentes); sem ele, o app oferece abrir o
arquivo no player padrão do Windows.
"""
import ctypes
import os
import random
import sys

from . import deps

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


AUDIO_EXT = (".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".flac")
REPEAT_MODES = ("off", "all", "one")


def fmt_time(ms):
    return _fmt(ms)


def make_item(path, title="", thumb=None, quality="", artist=""):
    """Item da fila. kind = 'audio' ou 'video' (pela extensão); artist = canal de origem."""
    kind = "audio" if path.lower().endswith(AUDIO_EXT) or quality in ("mp3", "m4a") else "video"
    return {"path": path, "title": title or os.path.splitext(os.path.basename(path))[0],
            "thumb": thumb or "", "kind": kind, "artist": artist or ""}


class Playback:
    """Fila de reprodução + VLC. Chamado só pela thread principal (a interface chama tick())."""

    def __init__(self, on_change=None, volume=80):
        vlc = load_vlc()
        if vlc is None:
            raise RuntimeError(_load_error or "VLC not available")
        self.vlc = vlc
        self.instance = vlc.Instance("--no-video-title-show", "--quiet")
        self.mp = self.instance.media_player_new()
        try:  # cliques/teclas vão para a janela do app, não para o VLC
            self.mp.video_set_mouse_input(False)
            self.mp.video_set_key_input(False)
        except Exception:
            pass
        self.queue, self.index = [], -1
        self.shuffle, self.repeat = False, "off"
        self.volume = int(volume)
        self.mp.audio_set_volume(self.volume)
        self._handle = None
        self.on_change = on_change or (lambda: None)

    # ---------------------------------------------------------------- estado
    @property
    def current(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else None

    @property
    def upcoming(self):
        return self.queue[self.index + 1:] if self.current else list(self.queue)

    def is_playing(self):
        return bool(self.mp.is_playing())

    def position(self):
        """(tempo_ms, duração_ms)."""
        return max(0, self.mp.get_time() or 0), max(0, self.mp.get_length() or 0)

    # ---------------------------------------------------------------- saída de vídeo
    def set_video_handle(self, handle):
        """Janela (winfo_id) onde o vídeo é desenhado. Ao trocar, recarrega o vídeo atual no mesmo ponto."""
        changed = handle != self._handle
        self._handle = handle
        if changed and self.current and self.current["kind"] == "video" and self.is_playing():
            ms = self.position()[0]
            self._load(start_ms=ms)

    def _attach(self):
        if self._handle is None:
            return
        if sys.platform == "win32":
            self.mp.set_hwnd(self._handle)
        else:
            self.mp.set_xwindow(self._handle)

    # ---------------------------------------------------------------- fila
    def play_list(self, items, start=0):
        """Toca uma lista (ex.: a Biblioteca) a partir de um item — substitui a fila."""
        self.queue = [dict(i) for i in items]
        self.index = max(0, min(start, len(self.queue) - 1)) if self.queue else -1
        if self.shuffle and self.queue:
            self._shuffle_upcoming()
        self._load()

    def play_now(self, item):
        """Toca um item agora, mantendo o resto da fila depois dele."""
        self.queue.insert(self.index + 1, dict(item))
        self.index += 1
        self._load()

    def play_next(self, item):
        """Coloca o item logo depois do atual ("Tocar a seguir")."""
        self.queue.insert(self.index + 1 if self.current else len(self.queue), dict(item))
        if self.current is None:
            self.index = len(self.queue) - 1
            self._load()
        else:
            self.on_change()

    def add(self, items):
        """Adiciona ao fim da fila. Se nada estiver tocando, começa a tocar."""
        start_now = self.current is None
        first = len(self.queue)
        self.queue.extend(dict(i) for i in items)
        if start_now and self.queue:
            self.index = first
            self._load()
        else:
            self.on_change()

    def remove(self, i):
        if not 0 <= i < len(self.queue):
            return
        playing = i == self.index
        del self.queue[i]
        if i < self.index:
            self.index -= 1
        if playing:
            if self.index >= len(self.queue):
                self.index = len(self.queue) - 1
            if self.current:
                self._load()
            else:
                self.stop(clear=False)
        self.on_change()

    def move(self, i, j):
        """Move o item i para a posição j (reordenar a fila)."""
        if not (0 <= i < len(self.queue) and 0 <= j < len(self.queue)) or i == j:
            return
        item = self.queue.pop(i)
        self.queue.insert(j, item)
        if self.index == i:
            self.index = j
        elif i < self.index <= j:
            self.index -= 1
        elif j <= self.index < i:
            self.index += 1
        self.on_change()

    def jump(self, i):
        if 0 <= i < len(self.queue):
            self.index = i
            self._load()

    def clear_upcoming(self):
        if self.current:
            self.queue = self.queue[:self.index + 1]
        else:
            self.queue = []
        self.on_change()

    # ---------------------------------------------------------------- transporte
    def toggle(self):
        if self.current is None:
            if self.queue:
                self.index = 0
                self._load()
            return
        if self.is_playing():
            self.mp.pause()
        else:
            if self.mp.get_state() in (self.vlc.State.Ended, self.vlc.State.Stopped):
                self._load()
            else:
                self.mp.play()
        self.on_change()

    def next(self, auto=False):
        if not self.queue:
            return
        if auto and self.repeat == "one":
            self._load()
            return
        if self.index + 1 < len(self.queue):
            self.index += 1
        elif self.repeat == "all":
            self.index = 0
        else:
            if auto:          # fim da fila
                self.mp.stop()
                self.on_change()
            return
        self._load()

    def prev(self):
        if self.position()[0] > 3000 or self.index <= 0:
            self.mp.set_time(0)
            return
        self.index -= 1
        self._load()

    def seek(self, fraction):
        self.mp.set_position(max(0.0, min(1.0, float(fraction))))

    def skip(self, delta_ms):
        now, length = self.position()
        if length > 0:
            self.mp.set_time(int(max(0, min(length - 500, now + delta_ms))))

    def set_volume(self, value):
        self.volume = int(value)
        self.mp.audio_set_volume(self.volume)

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        if self.shuffle:
            self._shuffle_upcoming()
        self.on_change()

    def cycle_repeat(self):
        self.repeat = REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1) % len(REPEAT_MODES)]
        self.on_change()

    def stop(self, clear=True):
        self.mp.stop()
        if clear:
            self.queue, self.index = [], -1
        self.on_change()

    def tick(self):
        """Chamado pela interface a cada ~250 ms: passa para o próximo item quando o atual termina."""
        if self.current and self.mp.get_state() == self.vlc.State.Ended:
            self.next(auto=True)

    def release(self):
        try:
            self.mp.stop()
            self.mp.release()
            self.instance.release()
        except Exception:
            pass

    # ---------------------------------------------------------------- internos
    def _shuffle_upcoming(self):
        rest = self.queue[self.index + 1:]
        random.shuffle(rest)
        self.queue = self.queue[:self.index + 1] + rest

    def _load(self, start_ms=0):
        item = self.current
        if item is None:
            return
        self.mp.stop()
        self.mp.set_media(self.instance.media_new(item["path"]))
        if item["kind"] == "video":
            self._attach()
        self.mp.audio_set_volume(self.volume)
        self.mp.play()
        if start_ms:
            self.mp.set_time(int(start_ms))
        self.on_change()
