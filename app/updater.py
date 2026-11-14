# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Verificação de atualizações pelas Releases do GitHub.

- Versões publicadas seguem "vMAJOR.MINOR.PATCH" (ex.: v2.0.0).
- Builds feitos fora de uma tag (código de commit, "-dev") são "desenvolvimento": nunca são
  tratados como mais novos que uma versão publicada (antes, "b01330d" virava "versão 1330").
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from . import GITHUB_REPO, PROJECT_URL, __version__

API = "https://api.github.com/repos/{repo}/releases/latest"
INSTALLER_ASSET = "VidNeon-Setup.exe"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class NoReleases(Exception):
    """O repositório ainda não tem nenhuma Release publicada."""


def repo() -> str:
    if GITHUB_REPO:
        return GITHUB_REPO
    m = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", PROJECT_URL)
    return m.group(1) if m else ""


def parse(version):
    """'v2.0.0' -> (2, 0, 0). Qualquer outra coisa (commit, 'v2.0.0-3-gabc', 'dev') -> None."""
    m = SEMVER.match((version or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_dev(version=__version__) -> bool:
    return parse(version) is None


def can_self_install() -> bool:
    """Só o .exe (PyInstaller) no Windows consegue se atualizar rodando o instalador."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def fetch_latest(timeout=10) -> dict:
    """Consulta a Release mais recente. Levanta NoReleases ou outra exceção de rede."""
    req = urllib.request.Request(API.format(repo=repo()), headers={
        "Accept": "application/vnd.github+json", "User-Agent": "VidNeon"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NoReleases() from e
        raise
    asset = next((a for a in data.get("assets", []) if a.get("name") == INSTALLER_ASSET), None)
    return {
        "tag": data.get("tag_name", ""),
        "name": data.get("name") or data.get("tag_name", ""),
        "url": data.get("html_url") or f"{PROJECT_URL}/releases",
        "notes": data.get("body") or "",
        "asset_url": asset.get("browser_download_url") if asset else "",
        "asset_size": asset.get("size", 0) if asset else 0,
    }


def compare(latest_tag, current=__version__) -> str:
    """'newer' (há versão nova), 'same' (atualizado) ou 'dev' (build de desenvolvimento)."""
    cur, new = parse(current), parse(latest_tag)
    if cur is None:
        return "dev"
    if new is not None and new > cur:
        return "newer"
    return "same"


def notes_excerpt(notes: str, max_lines=10) -> str:
    """Primeiras linhas úteis das notas da versão (sem markdown pesado)."""
    out = []
    for line in notes.splitlines():
        line = re.sub(r"[#*`>|]", "", line).strip()
        if not line or set(line) <= set("-=:"):
            continue
        out.append(line)
        if len(out) >= max_lines:
            break
    return "\n".join(out)


def download(url, size=0, on_progress=None) -> str:
    """Baixa o instalador para a pasta temporária. on_progress(fração 0..1)."""
    dest = os.path.join(tempfile.gettempdir(), INSTALLER_ASSET)
    req = urllib.request.Request(url, headers={"User-Agent": "VidNeon"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if on_progress and total:
                on_progress(min(1.0, done / total))
    os.replace(dest + ".part", dest)
    return dest


def run_installer(path):
    """Abre o instalador (ele fecha o app aberto e atualiza; ver CloseApplications no installer.iss)."""
    subprocess.Popen([path], close_fds=True)
