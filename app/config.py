# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Configurações e histórico, salvos em %APPDATA%\\VidNeon (migrados de %APPDATA%\\BaixadorYouTube)."""
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field, fields

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
HISTORY_LIMIT = 2000


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
    component_paths: dict = field(default_factory=dict)  # caminhos escolhidos em "Localizar…"
    volume: int = 80               # volume do player
    animations: bool = True        # animações da interface (desligadas também se o Windows pedir)
    auto_update_check: bool = True # procurar atualização ao abrir (1x por dia)
    last_update_check: float = 0.0

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
    return add_history_many([entry])


def add_history_many(entries: list) -> list:
    """Adiciona itens no topo, na ordem dada (o 1º da lista fica em cima). O mesmo arquivo
    baixado de novo substitui o registro antigo, sem duplicar; a capa escolhida é mantida."""
    items = load_history()
    when = time.strftime("%Y-%m-%d %H:%M")
    new = []
    for entry in entries:
        old = next((h for h in items if entry.get("filepath") and h.get("filepath") == entry["filepath"]), None)
        if old is not None:
            items.remove(old)
            if old.get("custom_thumb"):
                entry = {**entry, "thumb": old["thumb"], "custom_thumb": True}
        new.append({"id": uuid.uuid4().hex, "when": when, **entry})
    items = new + items
    save_history(items)
    return items


def update_history(predicate, **changes) -> int:
    """Altera os itens em que predicate(item) é verdadeiro. Devolve quantos mudaram."""
    items = load_history()
    n = 0
    for h in items:
        if predicate(h):
            h.update(changes)
            n += 1
    if n:
        save_history(items)
    return n


def remove_history(entry: dict) -> None:
    """Remove uma entrada (pelo id, ou pelo conteúdo nas entradas antigas sem id)."""
    items = load_history()
    for i, h in enumerate(items):
        if (entry.get("id") and h.get("id") == entry["id"]) or (not entry.get("id") and h == entry):
            del items[i]
            break
    save_history(items)
