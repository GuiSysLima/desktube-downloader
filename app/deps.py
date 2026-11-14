# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Componentes externos: ffmpeg, Deno, Node.js e VLC.

- ffmpeg: junta vídeo/áudio, converte para MP3, gera miniaturas.
- Deno / Node.js: resolvem os desafios JavaScript do YouTube.
- VLC: usado pelo player interno.
Instalação e desinstalação pelo winget.
"""
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    winget_id: str
    exe: str            # executável procurado no PATH ("" = detecção especial)
    site: str           # site oficial (alternativa ao winget)


COMPONENTS = {
    "ffmpeg": Component("ffmpeg", "ffmpeg", "Gyan.FFmpeg", "ffmpeg", "https://ffmpeg.org/download.html"),
    "deno": Component("deno", "Deno", "DenoLand.Deno", "deno", "https://deno.com/"),
    "node": Component("node", "Node.js", "OpenJS.NodeJS.LTS", "node", "https://nodejs.org/"),
    "vlc": Component("vlc", "VLC", "VideoLAN.VLC", "", "https://www.videolan.org/vlc/"),
}

# compatibilidade com código antigo
WINGET_IDS = {k: c.winget_id for k, c in COMPONENTS.items()}


def refresh_path() -> None:
    """Relê o PATH do registro (para enxergar programas instalados/removidos com o app aberto)."""
    if sys.platform != "win32":
        return
    import winreg

    parts = []
    for root, sub in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ):
        try:
            with winreg.OpenKey(root, sub) as k:
                value, _ = winreg.QueryValueEx(k, "Path")
                parts += os.path.expandvars(value).split(";")
        except OSError:
            pass
    extra = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
        os.path.expandvars(r"%USERPROFILE%\.deno\bin"),
    ]
    merged = []
    for p in os.environ.get("PATH", "").split(";") + parts + extra:
        if p and p not in merged:
            merged.append(p)
    os.environ["PATH"] = ";".join(merged)


def find_vlc_dir():
    """Pasta de instalação do VLC (com libvlc.dll), ou None."""
    candidates = []
    if sys.platform == "win32":
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r"Software\VideoLAN\VLC") as k:
                    candidates.append(winreg.QueryValueEx(k, "InstallDir")[0])
            except OSError:
                pass
        candidates += [os.path.expandvars(r"%ProgramFiles%\VideoLAN\VLC"),
                       os.path.expandvars(r"%ProgramFiles(x86)%\VideoLAN\VLC")]
        for d in candidates:
            if d and os.path.isfile(os.path.join(d, "libvlc.dll")):
                return d
        return None
    lib = shutil.which("vlc")
    return os.path.dirname(lib) if lib else None


def find(name: str):
    if name == "vlc":
        return find_vlc_dir()
    comp = COMPONENTS.get(name)
    return shutil.which(comp.exe if comp else name)


def status() -> dict:
    return {k: find(k) for k in COMPONENTS}


def has_winget() -> bool:
    return shutil.which("winget") is not None


def _run_winget(args, on_line=None) -> int:
    cmd = ["winget", *args, "--accept-source-agreements", "--disable-interactivity"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW)
    except FileNotFoundError:
        if on_line:
            on_line("winget não encontrado / winget not found")
        return -1
    for line in proc.stdout:
        line = line.strip()
        # ignora as barras de progresso animadas
        if line and on_line and not set(line) <= set("-\\|/ █▒░"):
            on_line(line)
    proc.wait()
    return proc.returncode


def install(name: str, on_line=None) -> bool:
    """Instala via winget. Retorna True se o componente passou a ser encontrado."""
    comp = COMPONENTS[name]
    _run_winget(["install", "--id", comp.winget_id, "-e", "--accept-package-agreements"], on_line)
    refresh_path()
    return find(name) is not None


def uninstall(name: str, on_line=None) -> bool:
    """Desinstala via winget. Retorna True se o componente deixou de ser encontrado."""
    comp = COMPONENTS[name]
    _run_winget(["uninstall", "--id", comp.winget_id, "-e", "--silent"], on_line)
    refresh_path()
    return find(name) is None


def ytdlp_version() -> str:
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "?"
