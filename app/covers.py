# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""Capas personalizadas (de uma playlist ou de um item).

Uma capa nova é aplicada em até três lugares:
  1. no app: vira a miniatura dos itens na Biblioteca e no player;
  2. na pasta: folder.jpg (o Explorer e os players de música usam esse arquivo como capa);
  3. opcionalmente dentro dos arquivos (.mp3, .m4a, .mp4), via ffmpeg, sem reconverter o áudio/vídeo.
"""
import os
import subprocess
import sys
import tempfile
import time

from . import deps, thumbs

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
IMAGE_TYPES = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
EMBED_EXT = (".mp3", ".m4a", ".mp4", ".m4v")
FOLDER_JPG = "folder.jpg"
MAX_SIDE = 1000


def make_thumb(src: str) -> str:
    """Miniatura (320x180) para o app. A chave muda a cada troca, para não reaproveitar o cache."""
    key = thumbs.key_for(f"cover:{src}:{time.time()}")
    dest = thumbs.path_for(key)
    if not thumbs._convert(src, dest):
        raise RuntimeError("image")
    return dest


def make_jpg(src: str, dest: str) -> bool:
    """Converte a imagem para JPEG (até 1000 px no maior lado)."""
    if thumbs.HAS_PIL:
        try:
            from PIL import Image  # type: ignore
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                im.save(dest, "JPEG", quality=90)
            return True
        except Exception:
            pass
    return _ffmpeg(["-i", src, "-vf", f"scale='min({MAX_SIDE},iw)':-2", "-frames:v", "1", "-q:v", "3", dest])


def _set_hidden(path, hidden):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2 if hidden else 0x80)
    except Exception:
        pass


def write_folder_jpg(jpg: str, folder: str) -> bool:
    """Grava folder.jpg (oculto, como faz o Windows Media Player) na pasta da playlist."""
    if not folder or not os.path.isdir(folder):
        return False
    dest = os.path.join(folder, FOLDER_JPG)
    try:
        tmp = dest + ".tmp"
        with open(jpg, "rb") as fi, open(tmp, "wb") as fo:
            fo.write(fi.read())
        if os.path.exists(dest):
            _set_hidden(dest, False)       # arquivo oculto não pode ser sobrescrito direto no Windows
        os.replace(tmp, dest)
        _set_hidden(dest, True)
        return True
    except OSError:
        return False


def can_embed(path: str) -> bool:
    return bool(path) and path.lower().endswith(EMBED_EXT) and os.path.isfile(path)


def embed(media: str, jpg: str) -> bool:
    """Troca a capa embutida no arquivo (sem reconverter). Só mexe no original se tudo der certo."""
    if not can_embed(media) or not deps.find("ffmpeg"):
        return False
    ext = os.path.splitext(media)[1].lower()
    if ext == ".mp3":
        maps = ["-map", "0:a", "-map", "1:0", "-id3v2_version", "3", "-disposition:v:0", "attached_pic"]
    elif ext == ".m4a":
        maps = ["-map", "0:a", "-map", "1:0", "-disposition:v:0", "attached_pic"]
    else:   # mp4/m4v: 1 trilha de vídeo (sem a capa antiga) + áudio/legendas + a capa nova
        maps = ["-map", "0:V:0", "-map", "0:a?", "-map", "0:s?", "-map", "1:0", "-disposition:v:1", "attached_pic"]
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(media))
    os.close(fd)
    try:
        ok = _ffmpeg(["-i", media, "-i", jpg, *maps, "-map_metadata", "0", "-c", "copy", tmp], timeout=300)
        if ok and os.path.getsize(tmp) > 0:
            os.replace(tmp, media)
            return True
        return False
    except OSError:
        return False
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _ffmpeg(args, timeout=60) -> bool:
    exe = deps.find("ffmpeg")
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args],
                           capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


def apply(src: str, entries: list, folder: str = "", embed_files: bool = False, on_progress=None) -> dict:
    """Aplica a capa. Roda em segundo plano. Devolve {"thumb", "folder_jpg", "embedded", "failed"}."""
    result = {"thumb": make_thumb(src), "folder_jpg": False, "embedded": 0, "failed": 0}
    fd, jpg = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        if not make_jpg(src, jpg):
            return result
        if folder:
            result["folder_jpg"] = write_folder_jpg(jpg, folder)
        if embed_files:
            files = [e.get("filepath") for e in entries if can_embed(e.get("filepath", ""))]
            for i, path in enumerate(files, start=1):
                if embed(path, jpg):
                    result["embedded"] += 1
                else:
                    result["failed"] += 1
                if on_progress:
                    on_progress(i, len(files))
        return result
    finally:
        try:
            os.remove(jpg)
        except OSError:
            pass
