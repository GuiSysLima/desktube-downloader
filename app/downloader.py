"""Fila de downloads em segundo plano usando o yt-dlp."""
import itertools
import os
import queue
import threading
import time
from dataclasses import asdict, dataclass, field

import yt_dlp

from . import browsers, deps
from .config import add_history

# Rótulos traduzidos em i18n.py com as chaves "q_<qualidade>"
QUALITIES = ("best", "1080", "720", "480", "mp3", "m4a")
AUDIO = ("mp3", "m4a")


def format_for(quality: str, has_ffmpeg: bool) -> str:
    if quality == "m4a":
        return "ba[ext=m4a]/ba/b"
    if quality == "mp3":
        return "ba/b"
    lim = "" if quality == "best" else f"[height<={quality}]"
    if has_ffmpeg:
        # Prefere MP4+M4A; cai para qualquer combinação e, por fim, para o que houver
        return f"bv*{lim}[ext=mp4]+ba[ext=m4a]/bv*{lim}+ba/b{lim}/bv*+ba/b"
    # Sem ffmpeg não dá para juntar vídeo e áudio: só formatos que já vêm completos
    return f"b{lim}[ext=mp4]/b{lim}/b"


def friendly_error(msg: str, settings):
    """Converte o erro do yt-dlp em (chave de tradução, argumentos)."""
    m = msg.lower()
    browser = browsers.BROWSERS.get(settings.browser)
    if "sign in to confirm" in m or "not a bot" in m or "login required" in m:
        return "err_login", {}
    if "could not copy" in m and "cookie" in m:
        return "err_cookie_copy", {"browser": browser.label if browser else ""}
    if "decrypt" in m or "dpapi" in m:
        return "err_decrypt", {}
    if "requested format is not available" in m or "only images are available" in m:
        return "err_no_format", {}
    if "private video" in m:
        return "err_private", {}
    if "confirm your age" in m or "age-restricted" in m or "inappropriate for some users" in m:
        return "err_age", {}
    if "video unavailable" in m:
        return "err_unavailable", {}
    if "unsupported url" in m:
        return "err_unsupported", {}
    if "unable to download webpage" in m or "getaddrinfo" in m or "timed out" in m:
        return "err_network", {}
    first = msg.replace("ERROR: ", "").strip().splitlines()[0] if msg.strip() else "?"
    return "err_generic", {"msg": first[:300]}


def _fmt_speed(v):
    if not v:
        return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if v < 1024:
            return f"{v:.1f} {unit}"
        v /= 1024
    return f"{v:.1f} TB/s"


def _fmt_eta(v):
    if v is None:
        return ""
    v = int(v)
    h, rem = divmod(v, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class Cancelled(Exception):
    pass


@dataclass
class Job:
    id: int
    url: str
    quality: str
    playlist: bool
    subtitles: bool
    state: str = "queued"     # queued | downloading | processing | done | error | cancelled
    status: str = "st_queued"  # chave de tradução (i18n)
    title: str = ""
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    item: str = ""
    filepath: str = ""
    error: str = ""            # chave de tradução do erro
    error_args: dict = field(default_factory=dict)


class _Logger:
    def __init__(self, emit):
        self.emit = emit

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.emit(("log", f"⚠ {msg}"))

    def error(self, msg):
        self.emit(("log", msg))


class Downloader:
    def __init__(self, get_settings, events: queue.Queue):
        self.get_settings = get_settings
        self.events = events
        self.jobs = {}
        self._ids = itertools.count(1)
        self._queue = queue.Queue()
        self._cancel = set()
        self._current = None
        threading.Thread(target=self._worker, daemon=True).start()

    # --- API usada pela interface ---
    def add(self, url, quality, playlist, subtitles) -> Job:
        job = Job(next(self._ids), url.strip(), quality, playlist, subtitles)
        self.jobs[job.id] = job
        self._queue.put(job.id)
        self._emit(job)
        return job

    def cancel(self, job_id):
        self._cancel.add(job_id)
        job = self.jobs.get(job_id)
        if job and job.state == "queued":
            job.state, job.status = "cancelled", "st_cancelled"
            self._emit(job)

    def busy(self) -> bool:
        return any(j.state in ("queued", "downloading", "processing") for j in self.jobs.values())

    # --- internos ---
    def _emit(self, job):
        self.events.put(("job", asdict(job)))

    def _worker(self):
        while True:
            job_id = self._queue.get()
            job = self.jobs.get(job_id)
            if not job or job.state != "queued":
                continue
            self._current = job_id
            try:
                self._run(job)
            finally:
                self._current = None
                self._cancel.discard(job_id)

    def _build_opts(self, job, s):
        st = deps.status()
        ffmpeg = st["ffmpeg"]
        audio = job.quality in AUDIO
        out = s.output_dir or os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")
        os.makedirs(out, exist_ok=True)
        name = "%(title)s.%(ext)s"
        tmpl = os.path.join(out, "%(playlist_title|Playlist)s", name) if job.playlist else os.path.join(out, name)

        opts = {
            "outtmpl": tmpl,
            "format": format_for(job.quality, bool(ffmpeg)),
            "noplaylist": not job.playlist,
            "windowsfilenames": True,
            "quiet": True,
            "no_warnings": False,
            "noprogress": True,
            "logger": _Logger(self.events.put),
            "progress_hooks": [lambda d: self._on_progress(job, d)],
            "postprocessor_hooks": [lambda d: self._on_postprocess(job, d)],
            "retries": 5,
            "fragment_retries": 5,
            "concurrent_fragment_downloads": 4,
        }
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg
        # Desafios JavaScript do YouTube: o yt-dlp usa o Deno por padrão; sem ele, tenta o Node
        if not st["deno"] and st["node"]:
            opts["js_runtimes"] = {"node": {"path": st["node"]}}

        # Login (cookies)
        if s.browser == "file" and s.cookies_file:
            opts["cookiefile"] = s.cookies_file
        elif s.browser in browsers.BROWSERS:
            opts["cookiesfrombrowser"] = browsers.cookies_spec(s.browser)

        pps = []
        if audio:
            if job.quality == "mp3" and ffmpeg:
                pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"})
        elif ffmpeg:
            opts["merge_output_format"] = "mp4"

        if job.subtitles and not audio:
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = [x.strip() for x in s.sub_langs.split(",") if x.strip()] or ["pt.*"]
            if ffmpeg:
                pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

        if ffmpeg and s.embed_metadata:
            pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
        if ffmpeg and s.embed_thumbnail and job.quality != "m4a":
            opts["writethumbnail"] = True
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        if pps:
            opts["postprocessors"] = pps
        return opts

    def _run(self, job):
        s = self.get_settings()
        job.state, job.status, job.error = "downloading", "st_starting", ""
        job.error_args = {}
        job.progress = 0.0
        self._emit(job)
        try:
            opts = self._build_opts(job, s)
            with yt_dlp.YoutubeDL(opts) as ydl:
                code = ydl.download([job.url])
            if job.id in self._cancel:
                raise Cancelled()
            if code:
                raise RuntimeError("__partial__")
        except Exception as e:  # noqa: BLE001
            if job.id in self._cancel or isinstance(e, Cancelled) or "Cancelled" in repr(e):
                job.state, job.status = "cancelled", "st_cancelled"
            else:
                job.state, job.status = "error", "st_error"
                if "__partial__" in str(e):
                    job.error, job.error_args = "err_partial", {}
                else:
                    job.error, job.error_args = friendly_error(str(e), s)
            self._emit(job)
            return

        job.state, job.status, job.progress = "done", "st_done", 1.0
        job.speed = job.eta = ""
        self._emit(job)
        try:
            add_history({
                "title": job.title or job.url,
                "url": job.url,
                "quality": job.quality,
                "filepath": job.filepath,
                "folder": os.path.dirname(job.filepath) if job.filepath else s.output_dir,
            })
            self.events.put(("history", None))
        except Exception:
            pass

    def _on_progress(self, job, d):
        if job.id in self._cancel:
            raise Cancelled()
        info = d.get("info_dict") or {}
        job.title = info.get("title") or job.title
        idx, total_items = info.get("playlist_index"), info.get("n_entries") or info.get("playlist_count")
        job.item = f"{idx}/{total_items}" if idx and total_items else ""

        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            if total:
                job.progress = max(0.0, min(1.0, done / total))
            audio_part = job.quality not in AUDIO and info.get("vcodec") == "none"
            job.state = "downloading"
            job.status = "st_downloading_audio" if audio_part else "st_downloading"
            job.speed, job.eta = _fmt_speed(d.get("speed")), _fmt_eta(d.get("eta"))
            now = time.monotonic()
            if now - getattr(job, "_last", 0) < 0.15:
                return
            job._last = now
        elif d["status"] == "finished":
            job.progress = 1.0
            job.state, job.status = "processing", "st_processing"
            job.filepath = info.get("filepath") or d.get("filename") or job.filepath
        self._emit(job)

    def _on_postprocess(self, job, d):
        if job.id in self._cancel:
            raise Cancelled()
        names = {
            "Merger": "st_merging",
            "FFmpegExtractAudio": "st_converting",
            "EmbedThumbnail": "st_thumbnail",
            "FFmpegMetadata": "st_metadata",
            "FFmpegEmbedSubtitle": "st_subtitles",
        }
        if d["status"] == "started" and d.get("postprocessor") in names:
            job.state, job.status = "processing", names[d["postprocessor"]]
            self._emit(job)
        elif d["status"] == "finished":
            path = (d.get("info_dict") or {}).get("filepath")
            if path:
                job.filepath = path
