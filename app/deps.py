"""Dependências externas: ffmpeg (juntar vídeo/áudio, MP3) e Deno/Node (desafios JS do YouTube)."""
import os
import shutil
import subprocess
import sys

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

WINGET_IDS = {
    "ffmpeg": "Gyan.FFmpeg",
    "deno": "DenoLand.Deno",
}


def refresh_path() -> None:
    """Relê o PATH do registro (para enxergar programas instalados com o app aberto)."""
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
    current = os.environ.get("PATH", "").split(";")
    merged = []
    for p in current + parts + extra:
        if p and p not in merged:
            merged.append(p)
    os.environ["PATH"] = ";".join(merged)


def find(name: str):
    return shutil.which(name)


def status() -> dict:
    return {"ffmpeg": find("ffmpeg"), "deno": find("deno"), "node": find("node")}


def has_winget() -> bool:
    return find("winget") is not None


def install(name: str, on_line=None) -> bool:
    """Instala via winget. `on_line` recebe cada linha de saída."""
    pkg = WINGET_IDS[name]
    cmd = ["winget", "install", "--id", pkg, "-e",
           "--accept-source-agreements", "--accept-package-agreements"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW)
    except FileNotFoundError:
        if on_line:
            on_line("winget não encontrado. Instale o 'App Installer' pela Microsoft Store.")
        return False
    for line in proc.stdout:
        line = line.strip()
        if line and on_line and not set(line) <= set("-\\|/ █▒"):
            on_line(line)
    proc.wait()
    refresh_path()
    return find(name) is not None


def ytdlp_version() -> str:
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "?"
