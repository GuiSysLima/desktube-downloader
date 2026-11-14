"""Miniaturas (preview) dos vídeos/áudios, independentes da opção de inserir capa no arquivo.

As miniaturas ficam em cache em %APPDATA%\\VidNeon\\thumbs\\<chave>.png (320x180, 16:9).
Fontes, em ordem:
  1. imagem do vídeo informada pelo site (baixada durante o download);
  2. um quadro do próprio arquivo de vídeo, ou a capa embutida no áudio (via ffmpeg).
Usa o Pillow quando disponível; senão, o ffmpeg faz a conversão.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request

from . import deps
from .config import config_dir

W, H = 320, 180
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
THUMB_DIR = os.path.join(config_dir(), "thumbs")

try:
    from PIL import Image  # type: ignore
    HAS_PIL = True
except Exception:  # pragma: no cover
    HAS_PIL = False


def key_for(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]


def path_for(key: str) -> str:
    return os.path.join(THUMB_DIR, f"{key}.png")


def cached(key: str):
    p = path_for(key)
    return p if key and os.path.isfile(p) and os.path.getsize(p) > 0 else None


def _ffmpeg(args) -> bool:
    exe = deps.find("ffmpeg")
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args],
                           capture_output=True, timeout=30, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


_FIT = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")


def _convert(src: str, dest: str) -> bool:
    """Converte qualquer imagem (jpg/webp/png) para PNG 320x180 com tarjas pretas se preciso."""
    os.makedirs(THUMB_DIR, exist_ok=True)
    if HAS_PIL:
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((W, H))
                canvas = Image.new("RGB", (W, H), (0, 0, 0))
                canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
                canvas.save(dest, "PNG")
            return True
        except Exception:
            pass
    return _ffmpeg(["-i", src, "-vf", _FIT, "-frames:v", "1", dest])


def best_thumbnail_url(info: dict) -> str:
    """Escolhe uma miniatura de tamanho médio (evita baixar imagens enormes)."""
    if info.get("extractor_key", "").lower().startswith("youtube") and info.get("id"):
        return f"https://i.ytimg.com/vi/{info['id']}/mqdefault.jpg"
    thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url")]
    sized = sorted((t for t in thumbs if t.get("width")), key=lambda t: t["width"])
    for t in sized:
        if t["width"] >= 300:
            return t["url"]
    if sized:
        return sized[-1]["url"]
    return info.get("thumbnail") or (thumbs[-1]["url"] if thumbs else "")


def from_url(url: str, key: str):
    """Baixa a imagem e grava a miniatura. Retorna o caminho ou None."""
    if not url or not key:
        return None
    if cached(key):
        return path_for(key)
    tmp = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(5_000_000)
        fd, tmp = tempfile.mkstemp(suffix=".img")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path_for(key) if _convert(tmp, path_for(key)) else None
    except Exception:
        return None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def from_file(media_path: str, key: str):
    """Gera a miniatura a partir do arquivo: capa embutida (áudio) ou um quadro do vídeo."""
    if not media_path or not os.path.isfile(media_path) or not key:
        return None
    if cached(key):
        return path_for(key)
    os.makedirs(THUMB_DIR, exist_ok=True)
    dest = path_for(key)
    # quadro aos 3s (vídeos curtos: cai para o primeiro quadro); em áudios pega a capa embutida
    for args in (["-ss", "3", "-i", media_path], ["-i", media_path]):
        if _ffmpeg([*args, "-map", "0:v:0", "-vf", _FIT, "-frames:v", "1", dest]) and os.path.isfile(dest):
            return dest
    return None
