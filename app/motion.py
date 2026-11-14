# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Animações da interface (Tkinter não tem transições nativas: interpolamos com after()).

Regras (ui-ux-pro-max › Animation):
- tokens únicos de duração/easing para tudo (motion-consistency);
- desaceleração ao entrar, aceleração ao sair, e a saída ~65% da entrada (exit-faster-than-enter);
- toda animação é interrompível: uma nova na mesma chave cancela a anterior e o estado final é
  sempre aplicado explicitamente (cancellable-state-transitions);
- nada bloqueia a interface (no-blocking-animation);
- só animações com significado (hover, aba ativa, aviso entrando, progresso, diálogo abrindo);
- respeita "reduzir movimento": a opção do app (Configurações › Geral) e a configuração do Windows
  "Mostrar animações no Windows" (SPI_GETCLIENTAREAANIMATION).
"""
import sys

import customtkinter as ctk

FRAME_MS = 16                      # ~60 quadros/s
DUR = {"micro": 110, "short": 180, "medium": 240}
EXIT = 0.65                        # saída = 65% da entrada

_enabled = True
_jobs = {}                          # (id(widget), chave) -> after id


def ease_out(t):                    # desacelera ao chegar (cubic)
    return 1 - (1 - t) ** 3


def ease_in(t):                     # acelera ao sair
    return t ** 3


def system_allows() -> bool:
    """False quando o usuário desligou as animações do Windows."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        value = ctypes.c_bool(True)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
        return bool(value.value)
    except Exception:
        return True


def set_enabled(on: bool):
    global _enabled
    _enabled = bool(on) and system_allows()


def enabled() -> bool:
    return _enabled


def cancel(widget, key):
    job = _jobs.pop((id(widget), key), None)
    if job is not None:
        try:
            widget.after_cancel(job)
        except Exception:
            pass


def animate(widget, key, duration, step, done=None, easing=ease_out):
    """Chama step(p) com p de 0 a 1 (já com easing) ao longo de duration ms; depois done()."""
    cancel(widget, key)
    if not _enabled or duration <= 0:
        step(1.0)
        if done:
            done()
        return
    frames = max(1, int(duration / FRAME_MS))

    def tick(i=1):
        try:
            if not widget.winfo_exists():
                _jobs.pop((id(widget), key), None)
                return
            step(easing(i / frames))
        except Exception:
            _jobs.pop((id(widget), key), None)
            return
        if i < frames:
            _jobs[(id(widget), key)] = widget.after(FRAME_MS, lambda: tick(i + 1))
        else:
            _jobs.pop((id(widget), key), None)
            if done:
                done()
    _jobs[(id(widget), key)] = widget.after(FRAME_MS, tick)


# ---------------------------------------------------------------- cores
def _mode_index():
    return 1 if ctk.get_appearance_mode() == "Dark" else 0


def resolve(color):
    """Token (claro, escuro) -> '#rrggbb' do tema atual."""
    if isinstance(color, (tuple, list)):
        return color[_mode_index()]
    return color


def mix(a, b, p):
    a, b = resolve(a).lstrip("#"), resolve(b).lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * p):02x}" for x, y in zip(ca, cb))


def fade_color(widget, attr, start, end, duration, final=None, easing=ease_out):
    """Transição de cor (fg_color, text_color...). final = valor aplicado no fim (ex.: o token
    original ou "transparent"), para o widget continuar seguindo a troca de tema."""
    def step(p):
        widget.configure(**{attr: mix(start, end, p)})

    def done():
        widget.configure(**{attr: final if final is not None else end})
    animate(widget, "color:" + attr, duration, step, done, easing)


def fade_in_window(window, duration=DUR["short"]):
    """Diálogos entram com fade (alpha da janela). Sem suporte: aparece direto."""
    if not _enabled:
        return
    try:
        window.attributes("-alpha", 0.0)
    except Exception:
        return

    def step(p):
        window.attributes("-alpha", max(0.2, p))   # não fica "fantasma" abaixo de 0.2

    animate(window, "alpha", duration, step, lambda: window.attributes("-alpha", 1.0))
