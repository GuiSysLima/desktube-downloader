# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Componentes externos: ffmpeg, Deno, Node.js e VLC.

- ffmpeg: junta vídeo/áudio, converte para MP3, gera miniaturas.
- Deno / Node.js: resolvem os desafios JavaScript do YouTube.
- VLC: usado pelo player interno.
Instalação e desinstalação pelo winget.
"""
import glob
import logging
import os
import re
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
    custom = CUSTOM_PATHS.get("vlc")
    if custom:
        d = custom if os.path.isdir(custom) else os.path.dirname(custom)
        if os.path.isfile(os.path.join(d, "libvlc.dll" if sys.platform == "win32" else "vlc")) or \
                sys.platform != "win32" and os.path.isfile(custom):
            return d
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


# --------------------------------------------------------------------------- detecção
# Caminhos escolhidos manualmente pelo usuário (Configurações › Componentes › Localizar).
# O app preenche a partir de Settings.component_paths.
CUSTOM_PATHS = {}

WINGET_LINKS = r"%LOCALAPPDATA%\Microsoft\WinGet\Links"
# Onde procurar o executável REAL quando ele não aparece no PATH. Motivos comuns:
# - o winget instala ffmpeg/Deno como pacote "portátil" e cria só um link simbólico em
#   WinGet\Links; alguns Pythons (ex.: o da Microsoft Store) não enxergam esses links;
# - o PATH do processo é antigo (programa instalado com o app aberto).
SEARCH = {
    "ffmpeg": [
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe",
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe",
        r"%ProgramFiles%\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe",
        r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe",
        r"%SystemDrive%\ffmpeg\bin\ffmpeg.exe",
        r"%USERPROFILE%\scoop\shims\ffmpeg.exe",
        r"%ProgramData%\chocolatey\bin\ffmpeg.exe",
    ],
    "deno": [
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno*\deno.exe",
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno*\*\deno.exe",
        r"%ProgramFiles%\WinGet\Packages\DenoLand.Deno*\deno.exe",
        r"%USERPROFILE%\.deno\bin\deno.exe",
        r"%USERPROFILE%\scoop\shims\deno.exe",
        r"%ProgramData%\chocolatey\bin\deno.exe",
    ],
    "node": [
        r"%ProgramFiles%\nodejs\node.exe",
        r"%LOCALAPPDATA%\Programs\nodejs\node.exe",
        r"%NVM_SYMLINK%\node.exe",
        r"%SystemDrive%\nvm4w\nodejs\node.exe",
        r"%USERPROFILE%\scoop\shims\node.exe",
    ],
}
log = logging.getLogger("baixador")


def _expand(pattern: str) -> str:
    """Expande %VAR% (também fora do Windows, para os testes) e ajusta o separador."""
    out = re.sub(r"%(\w+)%", lambda m: os.environ.get(m.group(1), m.group(0)), pattern)
    return out if os.sep == "\\" else out.replace("\\", os.sep)


def _real_file(path):
    """Caminho do arquivo real (segue links simbólicos), ou None."""
    try:
        if os.path.isfile(path):
            return path
        if os.path.islink(path):
            target = os.path.realpath(path)
            if os.path.isfile(target):
                return target
    except OSError:
        pass
    return None


def _exe(name):
    return name + (".exe" if sys.platform == "win32" else "")


def _ensure_on_path(exe_path):
    """Coloca a pasta do executável no PATH do processo (para o yt-dlp e subprocessos)."""
    folder = os.path.dirname(exe_path)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if folder and folder not in parts:
        os.environ["PATH"] = os.pathsep.join([folder] + parts)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def locate(name: str):
    """Procura o componente e devolve (caminho, onde_foi_encontrado) ou (None, tentativas)."""
    tried = []
    custom = CUSTOM_PATHS.get(name)
    if custom:
        found = _real_file(custom)
        tried.append(("custom", custom, bool(found)))
        if found:
            return found, "custom"
    comp = COMPONENTS.get(name)
    exe = comp.exe if comp else name
    found = shutil.which(exe)
    tried.append(("PATH", exe, bool(found)))
    if found:
        return found, "PATH"
    link = os.path.join(_expand(WINGET_LINKS), _exe(exe))
    found = _real_file(link)
    tried.append(("WinGet Links", link, bool(found)))
    if found:
        return found, "WinGet Links"
    for pattern in SEARCH.get(name, []):
        pat = _expand(pattern)
        if "%" in pat:      # variável inexistente
            continue
        hits = sorted((h for h in glob.glob(pat) if os.path.isfile(h)), key=_mtime, reverse=True)
        tried.append(("busca", pat, bool(hits)))
        for h in hits:
            if os.path.isfile(h):
                return h, "busca"
    return None, tried


def find(name: str):
    if name == "vlc":
        return find_vlc_dir()
    path, _how = locate(name)
    if path:
        _ensure_on_path(path)
    return path


def diagnose(name: str) -> list:
    """Linhas de diagnóstico (vão para o registro e para o app.log quando algo não é encontrado)."""
    path, info = locate(name)
    if path:
        return [f"{name}: encontrado em {path} ({info})"]
    lines = [f"{name}: não encontrado. Python: {sys.executable}"]
    for how, where, ok in info:
        lines.append(f"  [{'ok' if ok else '--'}] {how}: {where}")
    return lines


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
