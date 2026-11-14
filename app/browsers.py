# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Navegadores suportados para leitura de cookies (login do YouTube)."""
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Browser:
    label: str
    ytdlp_name: str       # nome que o yt-dlp entende
    profile_dir: str      # pasta de perfil (com variáveis de ambiente)
    process: str          # executável no Windows
    locks_cookies: bool   # True se o banco de cookies fica bloqueado com o navegador aberto
    custom_profile: bool = False  # True se precisa passar o caminho do perfil ao yt-dlp

    @property
    def path(self) -> str:
        return os.path.expandvars(self.profile_dir)

    def is_installed(self) -> bool:
        return os.path.isdir(self.path)


BROWSERS = {
    "operagx": Browser("Opera GX", "opera", r"%APPDATA%\Opera Software\Opera GX Stable",
                       "opera.exe", True, custom_profile=True),
    "opera": Browser("Opera", "opera", r"%APPDATA%\Opera Software\Opera Stable", "opera.exe", True),
    "chrome": Browser("Google Chrome", "chrome", r"%LOCALAPPDATA%\Google\Chrome\User Data", "chrome.exe", True),
    "edge": Browser("Microsoft Edge", "edge", r"%LOCALAPPDATA%\Microsoft\Edge\User Data", "msedge.exe", True),
    "brave": Browser("Brave", "brave", r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data", "brave.exe", True),
    "vivaldi": Browser("Vivaldi", "vivaldi", r"%LOCALAPPDATA%\Vivaldi\User Data", "vivaldi.exe", True),
    "firefox": Browser("Firefox", "firefox", r"%APPDATA%\Mozilla\Firefox\Profiles", "firefox.exe", False),
}

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def installed_keys() -> list:
    return [k for k, b in BROWSERS.items() if b.is_installed()]


def cookies_spec(key: str):
    """Tupla para a opção `cookiesfrombrowser` do yt-dlp."""
    b = BROWSERS[key]
    if b.custom_profile:
        return (b.ytdlp_name, b.path)
    return (b.ytdlp_name,)


def is_running(key: str) -> bool:
    if sys.platform != "win32":
        return False
    exe = BROWSERS[key].process
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
            capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10,
        ).stdout
        return exe.lower() in out.lower()
    except Exception:
        return False


def close_browser(key: str) -> bool:
    if sys.platform != "win32":
        return False
    exe = BROWSERS[key].process
    try:
        r = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True,
                           creationflags=NO_WINDOW, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def test_cookies(key: str = "", cookies_file: str = "") -> tuple:
    """Verifica se há login do YouTube. Retorna (ok, chave_de_tradução, argumentos)."""
    from yt_dlp.cookies import YoutubeDLCookieJar, extract_cookies_from_browser

    try:
        if cookies_file:
            jar = YoutubeDLCookieJar(cookies_file)
            jar.load(ignore_discard=True, ignore_expires=True)
        else:
            spec = cookies_spec(key)
            jar = extract_cookies_from_browser(spec[0], spec[1] if len(spec) > 1 else None)
    except Exception as e:
        msg = str(e)
        if "copy" in msg.lower() and "database" in msg.lower():
            return False, "ck_locked", {}
        if "decrypt" in msg.lower() or "dpapi" in msg.lower():
            return False, "ck_decrypt", {}
        return False, "ck_error", {"msg": msg}

    yt = [c for c in jar if c.domain.endswith("youtube.com")]
    logged = any(c.name in ("LOGIN_INFO", "SAPISID", "__Secure-3PSID") for c in yt)
    if logged:
        return True, "ck_ok", {"n": len(yt)}
    if yt:
        return False, "ck_not_logged", {}
    return False, "ck_none", {}
