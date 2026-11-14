# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Configurações e histórico, salvos em %APPDATA%\\VidNeon (migrados de %APPDATA%\\BaixadorYouTube)."""
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, fields

from . import APP_ID, OLD_APP_IDS


def _base_dir() -> str:
    return os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")


def _migrate_old_data(new_path: str) -> None:
    """Primeira execução com o nome novo: copia config, histórico e miniaturas da pasta antiga.
    A pasta antiga é mantida como backup."""
    for old_id in OLD_APP_IDS:
        old_path = os.path.join(_base_dir(), old_id)
        if not os.path.isdir(old_path):
            continue
        try:
            shutil.copytree(old_path, new_path)
        except Exception:
            return
        # o histórico guarda caminhos absolutos das miniaturas: aponta para a pasta nova
        hist = os.path.join(new_path, "historico.json")
        try:
            with open(hist, encoding="utf-8") as f:
                items = json.load(f)
            for h in items:
                thumb = h.get("thumb") or ""
                if thumb.startswith(old_path):
                    h["thumb"] = new_path + thumb[len(old_path):]
            with open(hist, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return


def config_dir() -> str:
    path = os.path.join(_base_dir(), APP_ID)
    if not os.path.isdir(path):
        _migrate_old_data(path)
    os.makedirs(path, exist_ok=True)
    return path


CONFIG_PATH = os.path.join(config_dir(), "config.json")
HISTORY_PATH = os.path.join(config_dir(), "historico.json")
DEFAULT_OUTPUT = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")
HISTORY_LIMIT = 300


@dataclass
class Settings:
    output_dir: str = DEFAULT_OUTPUT
    browser: str = "none"          # chave de browsers.BROWSERS, "none" ou "file"
    cookies_file: str = ""
    quality: str = "best"          # chave de downloader.QUALITIES
    playlist: bool = False
    subtitles: bool = False
    sub_langs: str = "pt.*,en.*"
    embed_metadata: bool = True
    embed_thumbnail: bool = False
    watch_clipboard: bool = True
    theme: str = "system"          # system | light | dark
    language: str = ""             # "pt" | "en" | "" (automático: instalador ou Windows)

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})
        except Exception:
            return cls()

    def save(self) -> None:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)


def load_history() -> list:
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(items: list) -> None:
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items[:HISTORY_LIMIT], f, indent=2, ensure_ascii=False)
    os.replace(tmp, HISTORY_PATH)


def add_history(entry: dict) -> list:
    items = load_history()
    # o mesmo arquivo baixado de novo substitui o registro antigo (sem duplicar a lista)
    if entry.get("filepath"):
        items = [h for h in items if h.get("filepath") != entry["filepath"]]
    entry = {"id": uuid.uuid4().hex, "when": time.strftime("%Y-%m-%d %H:%M"), **entry}
    items.insert(0, entry)
    save_history(items)
    return items


def remove_history(entry: dict) -> None:
    """Remove uma entrada (pelo id, ou pelo conteúdo nas entradas antigas sem id)."""
    items = load_history()
    for i, h in enumerate(items):
        if (entry.get("id") and h.get("id") == entry["id"]) or (not entry.get("id") and h == entry):
            del items[i]
            break
    save_history(items)
