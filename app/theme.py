# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Design system do app: cores (claro/escuro), tipografia, raios, espaçamentos e ícones.

Toda cor da interface vem daqui. Cada token é uma tupla (claro, escuro), formato aceito
pelo CustomTkinter, que troca automaticamente ao mudar o tema.

Paleta: superfícies "carvão em camadas" (estilo Windows 11 / Discord) + cores da marca
tiradas do ícone neon: rosa neon (ação principal) e violeta (destaques).
"""
import os
import sys
import tkinter.font as tkfont

import customtkinter as ctk

# ---------------------------------------------------------------- cores (claro, escuro)
C = {
    # superfícies
    "sidebar":        ("#EBEBEF", "#111214"),
    "bg":             ("#F3F3F5", "#18191C"),
    "card":           ("#FFFFFF", "#232428"),
    "card_hover":     ("#F7F7F9", "#2B2D31"),
    "card_border":    ("#E5E5EA", "#2E3035"),
    "input":          ("#FFFFFF", "#1E1F22"),
    "input_border":   ("#D9D9E0", "#313338"),
    "surface2":       ("#E9E9EE", "#2B2D31"),   # botões secundários, trilhos
    "surface2_hover": ("#DEDEE5", "#35373C"),
    "thumb_bg":       ("#E1E1E8", "#1A1B1E"),
    "divider":        ("#E6E6EB", "#2A2C31"),
    "row_hover":      ("#EEEEF2", "#26282C"),
    "player_bar":     ("#FFFFFF", "#1F2023"),
    # texto
    "text":           ("#1B1B1F", "#F2F3F5"),
    "text2":          ("#5F5F66", "#949BA4"),   # secundário/metadados (contraste >= 4.5:1)
    "text_disabled":  ("#A0A0A8", "#5C5F66"),
    # marca
    "primary":        ("#F0145A", "#F0145A"),   # rosa neon: ação principal (Baixar)
    "primary_hover":  ("#D10E4E", "#FF3D7A"),
    "primary_glow":   ("#F0145A", "#FF5C8A"),   # contorno "neon" do botão principal no tema escuro
    "on_primary":     ("#FFFFFF", "#FFFFFF"),
    "accent":         ("#8B3DFF", "#A23BFF"),   # violeta neon: progresso, seleção, foco
    "accent_hover":   ("#7A2EF0", "#B45CFF"),
    "accent_text":    ("#7A2EF0", "#C38BFF"),   # violeta para TEXTO (contraste >= 4.5:1 nos dois temas)
    "accent_soft":    ("#F0E7FF", "#2E1F4D"),   # fundo de item selecionado
    "on_accent":      ("#FFFFFF", "#FFFFFF"),
    # status (sempre acompanhados de ícone/texto, nunca só a cor)
    "success":        ("#1A7F45", "#23A55A"),
    "warning":        ("#9A6700", "#F0B232"),
    "error":          ("#C42B30", "#F23F43"),
    "error_hover":    ("#A32227", "#D9363A"),
    "warning_bg":     ("#FFF4D6", "#3A2F12"),
    "error_bg":       ("#FDE8E8", "#3A1A1C"),
    "success_bg":     ("#E3F5EA", "#16301F"),
}

# ---------------------------------------------------------------- forma e ritmo
RADIUS = {"button": 6, "input": 6, "card": 8, "thumb": 4, "pill": 999}
SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
THUMB = (96, 54)           # miniatura 16:9 na fila
THUMB_SM = (64, 36)        # miniatura nas listas (Biblioteca, fila de reprodução)
CONTROL_H = 36             # altura padrão de botões/campos
CTA_H = 40                 # altura do campo de link e do botão Baixar

# ---------------------------------------------------------------- tipografia
# Segoe UI no Windows. BAIXADOR_FONT permite outra fonte (usado nos testes fora do Windows).
FONT_FAMILY = os.environ.get("BAIXADOR_FONT", "Segoe UI")
TYPE = {                     # (tamanho, forte?) — "forte" usa Segoe UI Semibold
    "title":   (24, True),
    "section": (15, True),
    "row":     (13, False),     # título de item em listas
    "label":   (13, True),
    "body":    (13, False),
    "meta":    (12, False),
    "caption": (12, False),
    "small":   (11, False),
    # nomes antigos (compatibilidade)
    "card":    (13, True),
}
_fonts = {}
_strong_family = None


def _strong():
    """Família para texto forte: 'Segoe UI Semibold' se existir (mais natural que bold sintético)."""
    global _strong_family
    if _strong_family is None:
        try:
            fams = set(tkfont.families())
        except Exception:
            fams = set()
        semibold = FONT_FAMILY + " Semibold"
        _strong_family = (semibold, "normal") if semibold in fams else (FONT_FAMILY, "bold")
    return _strong_family


def font(kind="body", size=None, weight=None):
    s, strong = TYPE.get(kind, TYPE["body"])
    if weight == "bold":
        strong = True
    elif weight == "normal":
        strong = False
    fam, w = _strong() if strong else (FONT_FAMILY, "normal")
    key = (fam, size or s, w)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(family=fam, size=key[1], weight=w)
    return _fonts[key]


# ---------------------------------------------------------------- ícones (Segoe Fluent Icons)
# Fonte de ícones do próprio Windows: Segoe Fluent Icons (Win 11) ou Segoe MDL2 Assets (Win 10).
GLYPHS = {
    "download": "\uE896", "library": "\uE8F1", "settings": "\uE713", "play": "\uE768", "pause": "\uE769",
    "folder": "\uE8B7", "delete": "\uE74D", "more": "\uE712", "paste": "\uE77F", "retry": "\uE72C",
    "cancel": "\uE711", "link": "\uE71B", "search": "\uE721", "check": "\uE73E", "error": "\uEA39",
    "warning": "\uE7BA", "info": "\uE946", "video": "\uE714", "audio": "\uE8D6", "volume": "\uE767",
    "fullscreen": "\uE740", "back10": "\uEB9E", "fwd10": "\uEB9D", "globe": "\uE774", "theme": "\uE771",
    "puzzle": "\uEA86", "account": "\uE77B", "about": "\uE946", "update": "\uE895", "open": "\uE8A7",
    "prev": "\uE892", "next": "\uE893", "shuffle": "\uE8B1", "repeat": "\uE8EE", "repeat_one": "\uE8ED",
    "queue": "\uE8FD", "tag": "\uE8EC", "up": "\uE70E", "down": "\uE70D", "mute": "\uE74F",
    "nowplaying": "\uE768", "exit_fullscreen": "\uE73F",
}
# Sem fonte de ícones (Linux/testes): símbolos de texto simples
FALLBACK = {
    "download": "↓", "library": "≡", "settings": "⚙", "play": "▶", "pause": "❚❚", "folder": "▭",
    "delete": "✕", "more": "⋯", "paste": "⊞", "retry": "↻", "cancel": "✕", "link": "∞",
    "search": "⌕", "check": "✓", "error": "!", "warning": "!", "info": "i", "video": "▣",
    "audio": "♪", "volume": "◖", "fullscreen": "⛶", "back10": "«", "fwd10": "»", "globe": "◍",
    "theme": "◐", "puzzle": "◆", "account": "◉", "about": "i", "update": "↓", "open": "↗",
    "prev": "◀◀", "next": "▶▶", "shuffle": "⇄", "repeat": "↻", "repeat_one": "↻1", "queue": "≡", "tag": "#",
    "up": "▲", "down": "▼", "mute": "×", "nowplaying": "♫", "exit_fullscreen": "⇲",
}
_icon_family = None


def icon_family():
    """Descobre a fonte de ícones disponível (precisa de uma janela Tk já criada)."""
    global _icon_family
    if _icon_family is None:
        _icon_family = ""
        try:
            fams = set(tkfont.families())
            for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
                if f in fams:
                    _icon_family = f
                    break
        except Exception:
            pass
    return _icon_family


def glyph(name):
    return GLYPHS[name] if icon_family() else FALLBACK.get(name, "?")


def icon_font(size=16):
    key = ("icon", size)
    if key not in _fonts:
        fam = icon_family() or FONT_FAMILY
        _fonts[key] = ctk.CTkFont(family=fam, size=size)
    return _fonts[key]


# ---------------------------------------------------------------- tema do CustomTkinter
def apply_ctk_theme():
    """Aplica os tokens aos widgets padrão do CustomTkinter (antes de criar qualquer widget)."""
    ctk.set_default_color_theme("blue")
    th = ctk.ThemeManager.theme
    f = th["CTkFont"]
    if "family" in f:
        f.update(family=FONT_FAMILY, size=13)
    else:  # estrutura por plataforma
        for plat in f.values():
            plat.update(family=FONT_FAMILY, size=13)

    th["CTk"]["fg_color"] = list(C["bg"])
    th["CTkToplevel"]["fg_color"] = list(C["bg"])
    th["CTkFrame"].update(fg_color=list(C["card"]), top_fg_color=list(C["card_hover"]),
                          border_color=list(C["card_border"]), corner_radius=RADIUS["card"], border_width=0)
    th["CTkButton"].update(fg_color=list(C["accent"]), hover_color=list(C["accent_hover"]),
                           text_color=list(C["on_accent"]), text_color_disabled=list(C["text_disabled"]),
                           corner_radius=RADIUS["button"], border_color=list(C["input_border"]))
    th["CTkLabel"]["text_color"] = list(C["text"])
    th["CTkEntry"].update(fg_color=list(C["input"]), border_color=list(C["input_border"]),
                          text_color=list(C["text"]), placeholder_text_color=list(C["text2"]),
                          corner_radius=RADIUS["input"], border_width=1)
    for k in ("CTkCheckBox", "CTkRadioButton"):
        th[k].update(fg_color=list(C["accent"]), hover_color=list(C["accent_hover"]),
                     border_color=list(C["text2"]), text_color=list(C["text"]))
    th["CTkSwitch"].update(fg_color=list(C["surface2"]), progress_color=list(C["accent"]),
                           button_color=("#FFFFFF", "#F2F3F5"), button_hover_color=("#FFFFFF", "#FFFFFF"),
                           text_color=list(C["text"]))
    th["CTkProgressBar"].update(fg_color=list(C["surface2"]), progress_color=list(C["accent"]))
    th["CTkSlider"].update(fg_color=list(C["surface2"]), progress_color=list(C["accent"]),
                           button_color=list(C["accent"]), button_hover_color=list(C["accent_hover"]))
    th["CTkOptionMenu"].update(fg_color=list(C["surface2"]), button_color=list(C["surface2"]),
                               button_hover_color=list(C["surface2_hover"]), text_color=list(C["text"]),
                               corner_radius=RADIUS["button"])
    th["CTkComboBox"].update(fg_color=list(C["input"]), border_color=list(C["input_border"]),
                             button_color=list(C["surface2"]), button_hover_color=list(C["surface2_hover"]),
                             text_color=list(C["text"]))
    th["CTkScrollbar"].update(fg_color="transparent", button_color=list(C["surface2"]),
                              button_hover_color=list(C["text2"]))
    th["CTkSegmentedButton"].update(fg_color=list(C["surface2"]), selected_color=list(C["accent"]),
                                    selected_hover_color=list(C["accent_hover"]),
                                    unselected_color=list(C["surface2"]),
                                    unselected_hover_color=list(C["surface2_hover"]),
                                    text_color=list(C["text"]), corner_radius=RADIUS["button"], border_width=2)
    th["CTkTextbox"].update(fg_color=list(C["input"]), border_color=list(C["input_border"]),
                            text_color=list(C["text"]), border_width=1)
    th["CTkScrollableFrame"]["label_fg_color"] = list(C["surface2"])
    th["DropdownMenu"].update(fg_color=list(C["card"]), hover_color=list(C["surface2_hover"]),
                              text_color=list(C["text"]))


# ---------------------------------------------------------------- estilos de botão
BUTTON_STYLES = {
    "primary":   dict(fg_color=C["primary"], hover_color=C["primary_hover"], text_color=C["on_primary"],
                      border_width=1, border_color=C["primary_glow"]),
    "accent":    dict(fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["on_accent"]),
    "secondary": dict(fg_color=C["surface2"], hover_color=C["surface2_hover"], text_color=C["text"]),
    "ghost":     dict(fg_color="transparent", hover_color=C["surface2"], text_color=C["text"]),
    "danger":    dict(fg_color=C["error"], hover_color=C["error_hover"], text_color=("#FFFFFF", "#FFFFFF")),
    "danger_ghost": dict(fg_color="transparent", hover_color=C["error_bg"], text_color=C["error"]),
}


def is_windows():
    return sys.platform == "win32"
