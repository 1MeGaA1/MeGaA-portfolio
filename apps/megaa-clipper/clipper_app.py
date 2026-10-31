"""MeGaA Clipper app: serves the interface in ./ui and opens it in its own browser app window.

    pythonw clipper_app.py [VIDEO]            normal start (MeGaA Clipper.bat / desktop shortcut)
    python clipper_app.py --no-window --port 8765   server only, for testing in any browser

The server only listens on 127.0.0.1 and stops when the window is closed.
"""

import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import base64

import clipper
import library
from clipper import ClipperError

UI_DIR = clipper.ROOT / "ui"
PROFILE_DIR = clipper.ROOT / ".app-profile"
ICON = UI_DIR / "clipper.ico"
PREFERRED_PORT = 8765
PLAYABLE_CODECS = {"h264", "vp8", "vp9", "av1"}
PLAYABLE_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm"}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}
AUDIO_SUFFIXES = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}
PICK_FILE = (
    "import sys, tkinter as tk\n"
    "from tkinter import filedialog\n"
    "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)\n"
    "kinds = {'video': ('Choose a video', [('Videos', '*.mp4 *.mov *.mkv *.webm *.avi *.m4v')]),\n"
    "         'music': ('Choose background music', [('Audio', '*.mp3 *.m4a *.aac *.wav *.ogg *.flac')]),\n"
    "         'sfx': ('Choose a sound for muted words', [('Audio', '*.mp3 *.m4a *.aac *.wav *.ogg *.flac')]),\n"
    "         'popup': ('Choose a picture, GIF or short video', "
    "[('Pictures and videos', '*.png *.jpg *.jpeg *.webp *.gif *.mp4 *.mov *.webm')])}\n"
    "title, types = kinds[sys.argv[1]]\n"
    "path = filedialog.askopenfilename(title=title, filetypes=types + [('All files', '*.*')])\n"
    "print(path or '')\n"
)


def mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def number(value, default, low, high):
    try:
        return min(high, max(low, float(value)))
    except (TypeError, ValueError):
        return default


def hex_color(value, default):
    ok = isinstance(value, str) and len(value) == 7 and value.startswith("#")
    return value.upper() if ok else default


def finite(value):
    """A number (or a number as text) as a float, or None for anything else - NaN and infinity too."""
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def clean_edits(clip):
    """The editing settings of a clip (cuts, pauses, zoom, speed, bar, music, watermark)."""
    def items(value):
        """A list from the clip, or nothing (clips.json can be edited by hand)."""
        return value if isinstance(value, list) else []

    def ranges(value):
        """Sorted, merged [a, b] source seconds, like the editors' normaliseCuts: a range of 0.01 s or less is
        dropped (it would only split a kept piece, which moves the zoom punch-ins)."""
        found = []
        for item in items(value):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            a, b = finite(item[0]), finite(item[1])
            if a is not None and b is not None and round(b, 3) - round(a, 3) > 0.01:
                found.append([round(a, 3), round(b, 3)])
        out = []
        for a, b in sorted(found):
            if out and a <= out[-1][1] + 0.001:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return out

    cuts = ranges(clip.get("cuts"))
    # razor lines on the timeline (source seconds): only where the editor shows the parts; the render ignores them
    splits = sorted({t for t in (round(v, 2) for v in map(finite, items(clip.get("splits"))) if v is not None)
                     if 0 < t < 1e7})[:200]
    music = str(clip.get("music") or "")
    if music and Path(music).suffix.lower() not in AUDIO_SUFFIXES:
        music = ""
    mute_sfx = str(clip.get("mute_sfx") or "")
    if mute_sfx and Path(mute_sfx).suffix.lower() not in AUDIO_SUFFIXES:
        mute_sfx = ""
    intro_a, intro_b = number(clip.get("intro_start"), None, 0, 1e7), number(clip.get("intro_end"), None, 0, 1e7)
    if intro_a is None or intro_b is None or intro_b - intro_a < 0.3:
        intro_a = intro_b = None
    else:
        intro_b = min(intro_b, intro_a + 15)
    return {
        "mutes": ranges(clip.get("mutes")),
        "mute_mode": clip.get("mute_mode") if clip.get("mute_mode") in clipper.MUTE_SOUNDS else "silence",
        "mute_sfx": mute_sfx,
        "mute_sfx_volume": round(number(clip.get("mute_sfx_volume"), 0.8, 0.0, 1.5), 2),
        "mute_captions": bool(clip.get("mute_captions", True)),
        "intro_start": round(intro_a, 3) if intro_a is not None else None,
        "intro_end": round(intro_b, 3) if intro_b is not None else None,
        "intro_flash": bool(clip.get("intro_flash", True)),
        "cuts": cuts,
        "drops": ranges(clip.get("drops")),
        "splits": splits,
        "remove_pauses": bool(clip.get("remove_pauses")),
        "pause_min": round(number(clip.get("pause_min"), 0.5, 0.2, 2.0), 2),
        "zoom": bool(clip.get("zoom")),
        "zoom_amount": round(number(clip.get("zoom_amount"), 1.15, 1.05, 1.4), 2),
        "speed": round(number(clip.get("speed"), 1.0, 0.5, 2.0), 2),
        "progress": bool(clip.get("progress")),
        "progress_color": hex_color(clip.get("progress_color"), "#00E5FF"),
        "music": music,
        "music_volume": round(number(clip.get("music_volume"), 0.15, 0.0, 1.0), 2),
        "watermark": str(clip.get("watermark") or "").strip()[:40],
        "watermark_pos": clip.get("watermark_pos") if clip.get("watermark_pos") in ("tl", "tr", "bl", "br") else "tr",
        "hook_style": clip.get("hook_style") if clip.get("hook_style") in clipper.HOOK_STYLES else clipper.DEFAULT_HOOK_STYLE,
        "hook_size": round(number(clip.get("hook_size"), 100, 50, 200)),
        "hook_pos": round(number(clip.get("hook_pos"), 0, 40, 1600)) if clip.get("hook_pos") is not None else None,
        "hook_duration": round(number(clip.get("hook_duration"), 0, 0, 30), 1),
        "frame_zoom": round(number(clip.get("frame_zoom"), 1.0, 0.5, 2.5), 3),
        "frame_y": round(number(clip.get("frame_y"), 0.5, 0.0, 1.0), 3),
        "kw_highlight": bool(clip.get("kw_highlight")),
        "kw_color": hex_color(clip.get("kw_color"), "#39FF14"),
        "emojis": bool(clip.get("emojis")),
        "keyframes": sorted(({"t": round(number(k.get("t"), 0, 0, 1e7), 2),
                              "x": round(number(k.get("x"), 0.5, 0, 1), 3),
                              "y": round(number(k.get("y"), 0.5, 0, 1), 3)}
                             for k in items(clip.get("keyframes")) if isinstance(k, dict)), key=lambda k: k["t"]),
        "popups": [{"id": str(p.get("id") or "")[:12], "at": round(number(p.get("at"), 0, 0, 1e7), 2),
                    "dur": round(number(p.get("dur"), 1.5, 0.3, 10), 2), "path": str(p.get("path")),
                    "pos": p.get("pos") if p.get("pos") in ("top", "center", "bottom") else "center",
                    "size": round(number(p.get("size"), 0.8, 0.2, 1.0), 2)}
                   for p in items(clip.get("popups"))
                   if isinstance(p, dict) and Path(str(p.get("path") or "")).suffix.lower() in clipper.POPUP_SUFFIXES],
    }


class Session:
    """The video the window is working on, plus the background job running for it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.video = None
        self.project = None
        self.info = None
        self.job = {"kind": None, "running": False, "progress": 0, "message": "Ready", "error": None, "seq": 0}
        self.prep = {"state": "idle", "progress": 0, "message": ""}
        self.clip_status = {}
        self.picked_music = set()
        self.last_seen = time.time()
        self.bye_at = None

    def media_allowed(self, path):
        """Only serve files the user picked, or that a clip of this project uses (music, sounds, pop-ups)."""
        if not path or not Path(path).is_file():
            return False
        if Path(path).suffix.lower() not in AUDIO_SUFFIXES | clipper.POPUP_SUFFIXES:
            return False
        path = str(Path(path))
        if path in self.picked_music:
            return True
        if not self.project:
            return False
        for c in clipper.load_clips(self.project):
            used = [c.get("music"), c.get("mute_sfx")] + [p.get("path") for p in c.get("popups") or []]
            if any(str(Path(u)) == path for u in used if u):
                return True
        return False

    # ------------------------------------------------------------ campaign of the open project

    def project_meta(self):
        try:
            return json.loads((self.project / "project.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def set_campaign(self, campaign_id):
        meta = self.project_meta()
        meta["campaign"] = campaign_id or None
        (self.project / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._checks_key = None

    def clip_checks(self, clips):
        """Campaign rule problems for each clip, by name (cached until something changes)."""
        meta = self.project_meta()
        camp = library.campaign(meta.get("campaign"))
        key = (meta.get("campaign"), mtime(self.project / "clips.json"), mtime(self.project / "words.json"),
               mtime(library.CAMPAIGNS))
        if getattr(self, "_checks_key", None) == key:
            return self._checks
        checks = {}
        if camp:
            words, lines = clipper.load_transcript(self.project)
            for clip in clips:
                try:
                    duration = clipper.plan_clip(clip, self.info, words, lines)["duration"]
                except ClipperError as err:
                    checks[clip["name"]] = [{"level": "error", "text": str(err)}]
                    continue
                checks[clip["name"]] = library.check_clip(clip, camp, duration)
        self._checks_key, self._checks = key, checks
        return checks

    def clip_lengths(self, clips):
        """The finished length (s) of each clip, by name, as the render makes it: teaser, cuts, deleted parts,
        removed pauses and speed included (cached until something changes). A clip that can't be made has none."""
        key = (str(self.project), mtime(self.project / "clips.json"), mtime(self.project / "words.json"))
        if getattr(self, "_lengths_key", None) == key:
            return self._lengths
        words, lines = clipper.load_transcript(self.project)
        lengths = {}
        for clip in clips:
            try:
                lengths[clip["name"]] = round(clipper.plan_clip(clip, self.info, words, lines)["duration"], 2)
            except (ClipperError, KeyError, TypeError, ValueError):
                continue
        self._lengths_key, self._lengths = key, lengths
        return lengths

    # ------------------------------------------------------------ opening

    def needs_proxy(self):
        return (self.info["codec"] not in PLAYABLE_CODECS
                or self.video.suffix.lower() not in PLAYABLE_SUFFIXES
                or self.info["height"] > 1440)

    def open(self, path):
        video = Path(path)
        if not video.is_file():
            raise ClipperError(f"File not found: {video}")
        clipper.check_tools()
        info = clipper.probe(video)
        with self.lock:
            if self.job["running"]:
                raise ClipperError("Wait for the current task to finish first")
            self.video, self.info = video, info
            self.project = clipper.project_dir(video)
            self.clip_status = {}
            self.prep = {"state": "idle", "progress": 0, "message": ""}
        threading.Thread(target=self._prepare, args=(video, self.project, info), daemon=True).start()

    def _prepare(self, video, project, info):
        """Build the waveform and, when the browser can't play the file, a preview copy."""

        def update(**values):
            with self.lock:
                if self.video == video:
                    self.prep.update(values)

        try:
            peaks = project / "peaks.json"
            if not peaks.exists() or mtime(peaks) < mtime(video):
                update(state="working", message="Reading audio")
                clipper.audio_peaks(video, peaks)
            proxy = project / "proxy.mp4"
            if self.needs_proxy() and (not proxy.exists() or mtime(proxy) < mtime(video)):
                update(state="working", message="Preparing preview", progress=0)
                clipper.make_proxy(video, proxy, info["duration"],
                                   on_progress=lambda pct: update(progress=pct))
            update(state="ready", progress=100, message="")
        except ClipperError as err:
            update(state="error", message=str(err))

    def media_path(self):
        if not self.video:
            return None
        proxy = self.project / "proxy.mp4"
        if self.needs_proxy():
            return proxy if proxy.exists() else None
        return self.video

    # ------------------------------------------------------------ state for the window

    def recent(self):
        items = []
        for meta in clipper.PROJECTS.glob("*/project.json"):
            try:
                source = Path(json.loads(meta.read_text(encoding="utf-8"))["source"])
            except (OSError, ValueError, KeyError):
                continue
            if not source.exists():
                continue
            folder = meta.parent
            items.append({
                "path": str(source),
                "name": source.name,
                "transcript": (folder / "transcript.json").exists(),
                "clips": len(clipper.load_clips(folder)),
                "touched": max(filter(None, (mtime(folder / n) for n in
                                             ("clips.json", "transcript.json", "project.json")))),
            })
        items.sort(key=lambda item: item["touched"], reverse=True)
        return items[:8]

    def clips_with_status(self):
        clips = clipper.load_clips(self.project)
        checks = self.clip_checks(clips)
        lengths = self.clip_lengths(clips)
        out_dir = self.project / "out"
        result = []
        for clip in clips:
            name = clip.get("name", "")
            rendered = mtime(out_dir / f"{name}.mp4")
            # length: the finished clip's seconds (the status is never saved back, so it can't end up in clips.json)
            status = {"state": "ready" if rendered else "new", "progress": 0, "mtime": rendered, "length": lengths.get(name)}
            status.update(self.clip_status.get(name, {}))
            if status["state"] == "done":
                status["state"] = "ready" if rendered else "new"
            result.append({**clip, "status": status, "checks": checks.get(name, [])})
        return result

    def snapshot(self):
        with self.lock:
            job, prep = dict(self.job), dict(self.prep)
            video, project, info = self.video, self.project, self.info
        state = {"job": job, "prep": prep, "video": None, "clips": [], "recent": []}
        if not video:
            state["recent"] = self.recent()
            return state
        media = self.media_path()
        state["video"] = {
            "path": str(video),
            "name": video.name,
            "key": str(project.name),
            "info": info,
            "media": f"{project.name}-{mtime(media)}" if media else None,
            "transcript": mtime(project / "transcript.json"),
            "peaks": mtime(project / "peaks.json"),
            "campaign": self.project_meta().get("campaign"),
        }
        state["clips"] = self.clips_with_status()
        return state

    def transcript(self):
        lines = clipper.load_lines(self.project)
        words = clipper.load_words(self.project)
        return {"lines": lines, "words": clipper.caption_words(words, uppercase=False)}

    # ------------------------------------------------------------ jobs

    def start_job(self, kind, work):
        with self.lock:
            if not self.video:
                raise ClipperError("Open a video first")
            if self.job["running"]:
                raise ClipperError("Busy - wait for the current task to finish")
            self.job = {"kind": kind, "running": True, "progress": 0, "message": "Starting",
                        "error": None, "seq": self.job["seq"] + 1}

        def target():
            try:
                message = work()
                self.set_job(running=False, progress=100, message=message)
            except ClipperError as err:
                self.set_job(running=False, error=str(err), message="Failed")
            except Exception as err:  # report anything unexpected to the window instead of dying
                self.set_job(running=False, error=f"{type(err).__name__}: {err}", message="Failed")

        threading.Thread(target=target, daemon=True).start()

    def set_job(self, **values):
        with self.lock:
            self.job.update(values)

    def transcribe(self, lang):
        video = self.video

        def work():
            clipper.transcribe(video, lang or "en",
                               on_progress=lambda pct: self.set_job(progress=pct),
                               on_log=lambda text: self.set_job(message=text.rstrip(".")))
            return "Transcript ready"

        self.start_job("transcribe", work)

    def render(self, names):
        video, project = self.video, self.project
        clips = {c["name"]: c for c in clipper.load_clips(project)}
        todo = [clips[n] for n in names if n in clips]
        if not todo:
            raise ClipperError("No clips to render")
        with self.lock:
            for clip in todo:
                self.clip_status[clip["name"]] = {"state": "queued", "progress": 0}

        def work():
            failed = []
            for index, clip in enumerate(todo):
                name = clip["name"]

                def progress(pct, name=name, index=index):
                    with self.lock:
                        self.clip_status[name] = {"state": "rendering", "progress": pct}
                        self.job["progress"] = int((index + pct / 100) / len(todo) * 100)

                self.set_job(message=f"Rendering {name} ({index + 1}/{len(todo)})")
                progress(0)
                try:
                    clipper.render_clip(video, clip, on_progress=progress)
                    with self.lock:
                        self.clip_status[name] = {"state": "done", "progress": 100}
                except ClipperError as err:
                    failed.append(name)
                    with self.lock:
                        self.clip_status[name] = {"state": "error", "progress": 0, "error": str(err)}
            if failed:
                raise ClipperError(f"Failed: {', '.join(failed)}")
            return f"{len(todo)} clip{'s' if len(todo) != 1 else ''} rendered"

        self.start_job("render", work)

    def save_clips(self, clips):
        cleaned, seen = [], set()
        for clip in clips:
            name = clipper.safe_name(str(clip.get("name") or ""))
            if not name or name in seen:
                raise ClipperError(f"Clip names must be unique and not empty ({name or 'empty'})")
            seen.add(name)
            start, end = clipper.parse_time(clip["start"]), clipper.parse_time(clip["end"])
            if end <= start:
                raise ClipperError(f"{name}: end must be after start")
            style = clip.get("caption_style")
            color = clip.get("caption_color")
            size = clip.get("caption_size")
            pos = clip.get("caption_pos")
            cleaned.append({
                "name": name,
                "start": round(start, 2),
                "end": round(end, 2),
                "layout": "fit" if clip.get("layout") == "fit" else "crop",
                "crop_x": round(min(1.0, max(0.0, float(clip.get("crop_x", 0.5)))), 3),
                "hook": str(clip.get("hook", "")).strip(),
                "captions": bool(clip.get("captions", True)),
                "caption_style": style if style in clipper.CAPTION_STYLES else clipper.DEFAULT_CAPTION_STYLE,
                "caption_color": color if isinstance(color, str) and color.startswith("#") and len(color) == 7 else None,
                "caption_size": int(size) if isinstance(size, (int, float)) else 100,
                "caption_pos": int(pos) if isinstance(pos, (int, float)) else None,
                "post_caption": str(clip.get("post_caption", "")).strip(),
                **clean_edits(clip),
            })
        clipper.save_clips(self.project, cleaned)
        with self.lock:
            for name in list(self.clip_status):
                if name not in seen:
                    del self.clip_status[name]


session = Session()


def pick_file(kind="video"):
    result = subprocess.run([sys.executable, "-c", PICK_FILE, kind], capture_output=True, text=True,
                            encoding="utf-8", creationflags=clipper.NO_WINDOW)
    path = result.stdout.strip()
    return path or None


class Handler(BaseHTTPRequestHandler):
    server_version = "MeGaAClipper"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def host_ok(self):
        host = self.headers.get("Host", "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type=None):
        path = Path(path)
        if not path or not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        header = self.headers.get("Range", "")
        if header.startswith("bytes="):
            first, _, last = header[6:].split(",")[0].strip().partition("-")
            try:
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    start = max(0, size - int(last))
            except ValueError:
                start, end = 0, size - 1
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", content_type or CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        remaining = end - start + 1
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                while remaining > 0:
                    chunk = fh.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.host_ok():
            self.send_error(403)
            return
        session.last_seen = time.time()
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/", "/index.html"):
                self.send_file(UI_DIR / "index.html")
            elif path.startswith("/ui/"):
                target = (UI_DIR / path[4:]).resolve()
                if UI_DIR.resolve() not in target.parents:
                    self.send_error(404)
                else:
                    self.send_file(target)
            elif path == "/api/state":
                self.send_json(session.snapshot())
            elif path == "/api/transcript":
                self.send_json(session.transcript())
            elif path == "/api/styles":
                self.send_json({"styles": clipper.CAPTION_STYLES, "default": clipper.DEFAULT_CAPTION_STYLE,
                                "hooks": clipper.HOOK_STYLES, "default_hook": clipper.DEFAULT_HOOK_STYLE,
                                "hook_top": clipper.HOOK_MARGIN_TOP, "keywords": clipper.KEYWORD_EMOJI,
                                "emoji_size": clipper.EMOJI_SIZE,
                                "mute_sounds": {k: {"label": v["label"], "kind": v["kind"], "freq": v.get("freq")}
                                                for k, v in clipper.MUTE_SOUNDS.items()}})
            elif path == "/api/peaks":
                self.send_file(session.project / "peaks.json", "application/json")
            elif path == "/api/ping":
                self.send_json({"app": "clipper"})
            elif path == "/media/source":
                media = session.media_path()
                if media:
                    self.send_file(media, "video/mp4")
                else:
                    self.send_error(404)
            elif path.startswith("/media/clip/"):
                name = clipper.safe_name(path[len("/media/clip/"):].removesuffix(".mp4"))
                self.send_file(session.project / "out" / f"{name}.mp4")
            elif path.startswith("/media/sfx/"):
                name = path[len("/media/sfx/"):].removesuffix(".wav")
                self.send_file(clipper.sfx_file(name), "audio/wav")
            elif path in ("/media/music", "/media/file"):
                wanted = parse_qs(urlparse(self.path).query).get("path", [""])[0]
                if session.media_allowed(wanted):
                    self.send_file(wanted)
                else:
                    self.send_error(404)
            elif path == "/api/campaigns":
                self.send_json({"campaigns": library.campaigns()})
            elif path == "/api/tracker":
                self.send_json({"entries": library.tracker(), "campaigns": library.campaigns()})
            elif path == "/api/settings":
                key = library.settings().get("api_key") or ""
                self.send_json({"has_key": bool(key), "key_hint": f"…{key[-4:]}" if key else ""})
            elif path == "/api/emoji-needed":
                wanted = sorted(set(clipper.KEYWORD_EMOJI.values()) | {"💰"})
                self.send_json({"emojis": [e for e in wanted if not clipper.emoji_png(e).exists()]})
            elif path == "/api/moments":
                query = parse_qs(urlparse(self.path).query)
                lines = clipper.load_lines(session.project)
                peaks_file = session.project / "peaks.json"
                peaks = json.loads(peaks_file.read_text())["peaks"] if peaks_file.exists() else None
                self.send_json({"moments": clipper.find_moments(
                    lines, peaks, min_len=float(query.get("min", ["20"])[0]),
                    max_len=float(query.get("max", ["60"])[0]), count=int(query.get("count", ["10"])[0]))})
            else:
                self.send_error(404)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except ClipperError as err:
            self.send_json({"error": str(err)}, 400)
        except (AttributeError, TypeError):  # no video open yet
            self.send_json({"error": "Open a video first"}, 400)

    def do_POST(self):
        if not self.host_ok():
            self.send_error(403)
            return
        session.last_seen = time.time()
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        path = urlparse(self.path).path
        if path == "/api/bye":
            session.bye_at = time.time()
            self.send_json({})
            return
        try:
            body = json.loads(raw or b"{}")
            if path == "/api/open":
                target = body.get("path") or pick_file()
                if not target:
                    self.send_json({"opened": False})
                    return
                session.open(target)
                self.send_json({"opened": True})
            elif path in ("/api/pick-music", "/api/pick-sfx"):
                target = pick_file("music" if path == "/api/pick-music" else "sfx")
                if target and Path(target).suffix.lower() in AUDIO_SUFFIXES:
                    session.picked_music.add(str(Path(target)))
                    self.send_json({"path": str(Path(target)), "name": Path(target).name})
                else:
                    self.send_json({"path": None})
            elif path == "/api/edit-line":
                clipper.replace_line_text(session.project, float(body["s"]), float(body["e"]),
                                          str(body.get("text", "")))
                self.send_json({})
            elif path == "/api/pick-popup":
                target = pick_file("popup")
                if target and Path(target).suffix.lower() in clipper.POPUP_SUFFIXES:
                    if Path(target).suffix.lower() not in clipper.VIDEO_SUFFIXES:
                        clipper.check_popup_picture(target)   # an animated WebP etc. would stall the render
                    session.picked_music.add(str(Path(target)))
                    self.send_json({"path": str(Path(target)), "name": Path(target).name})
                else:
                    self.send_json({"path": None})
            elif path == "/api/campaigns":
                self.send_json({"campaign": library.save_campaign(body)})
            elif path == "/api/campaigns/delete":
                library.delete_campaign(body.get("id"))
                self.send_json({})
            elif path == "/api/project-campaign":
                session.set_campaign(body.get("id"))
                self.send_json({})
            elif path == "/api/tracker":
                self.send_json({"entry": library.save_entry(body)})
            elif path == "/api/tracker/delete":
                library.delete_entry(body.get("id"))
                self.send_json({})
            elif path == "/api/settings":
                library.save_settings({"api_key": str(body.get("api_key") or "").strip()})
                self.send_json({})
            elif path == "/api/emoji":
                emoji = str(body.get("emoji") or "")
                if emoji not in set(clipper.KEYWORD_EMOJI.values()) | {"💰"}:
                    raise ClipperError("Unknown emoji")
                png = base64.b64decode(str(body.get("png") or "").split(",")[-1])
                if not png.startswith(b"\x89PNG"):
                    raise ClipperError("Not a PNG picture")
                clipper.EMOJI_DIR.mkdir(exist_ok=True)
                clipper.emoji_png(emoji).write_bytes(png)
                self.send_json({})
            elif path == "/api/moments-ai":
                moments, cost = library.ai_moments(clipper.load_lines(session.project), int(body.get("count", 10)),
                                                   float(body.get("min", 20)), float(body.get("max", 60)))
                self.send_json({"moments": moments, "cost": cost})
            elif path == "/api/export":
                camp = library.campaign(session.project_meta().get("campaign"))
                result = library.export_pack(session.project, clipper.load_clips(session.project), camp,
                                             make_zip=bool(body.get("zip")))
                if result.is_dir():
                    os.startfile(result)
                else:
                    subprocess.Popen(["explorer", "/select,", str(result)])
                self.send_json({"path": str(result)})
            elif path == "/api/close":
                with session.lock:
                    if session.job["running"]:
                        raise ClipperError("Wait for the current task to finish first")
                    session.video = session.project = session.info = None
                self.send_json({})
            elif path == "/api/transcribe":
                session.transcribe(body.get("lang", "en"))
                self.send_json({})
            elif path == "/api/clips":
                session.save_clips(body.get("clips", []))
                self.send_json({"clips": session.clips_with_status()})
            elif path == "/api/render":
                session.render(body.get("names", []))
                self.send_json({})
            elif path == "/api/open-output":
                folder = session.project / "out"
                folder.mkdir(exist_ok=True)
                os.startfile(folder)
                self.send_json({})
            elif path == "/api/reveal":
                name = clipper.safe_name(body.get("name", ""))
                target = session.project / "out" / f"{name}.mp4"
                subprocess.Popen(["explorer", "/select,", str(target)])
                self.send_json({})
            else:
                self.send_error(404)
        except (ClipperError, ValueError, KeyError, TypeError) as err:
            self.send_json({"error": str(err)}, 400)
        except AttributeError:
            self.send_json({"error": "Open a video first"}, 400)


# ---------------------------------------------------------------- window + icon

def find_browser():
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = shutil.which("msedge") or shutil.which("chrome")
    return Path(found) if found else None


def open_window(url):
    """Open the interface as a borderless app window. Returns the browser process, if any."""
    browser = find_browser()
    if not browser:
        webbrowser.open(url)
        return None
    PROFILE_DIR.mkdir(exist_ok=True)
    return subprocess.Popen([
        str(browser), f"--app={url}", f"--user-data-dir={PROFILE_DIR}",
        "--window-size=1600,1000", "--no-first-run", "--no-default-browser-check",
        "--disable-features=Translate,msEdgeSidebarV2", "--autoplay-policy=no-user-gesture-required",
    ])


def make_icon():
    """Write ui/clipper.ico: the neon play mark on a dark rounded tile (PNG inside an ICO)."""
    size, ss = 256, 3
    cyan, magenta, bg = (0, 229, 255), (255, 43, 214), (8, 11, 20)

    def inside(px, py, ox):
        # triangle (60,52) (204,128) (60,204), shifted right by ox
        x1, y1, x2, y2, x3, y3 = 60 + ox, 52, 204 + ox, 128, 60 + ox, 204
        d1 = (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
        d2 = (px - x3) * (y2 - y3) - (x2 - x3) * (py - y3)
        d3 = (px - x1) * (y3 - y1) - (x3 - x1) * (py - y1)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    def in_tile(px, py, radius=56):
        cx = min(max(px, radius), size - radius)
        cy = min(max(py, radius), size - radius)
        return (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2

    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    px, py = x + (sx + 0.5) / ss, y + (sy + 0.5) / ss
                    if not in_tile(px, py):
                        continue
                    if inside(px, py, 0):
                        color = cyan
                    elif inside(px, py, 14):
                        color = magenta
                    else:
                        color = bg
                    acc[0] += color[0]
                    acc[1] += color[1]
                    acc[2] += color[2]
                    acc[3] += 255
            n = ss * ss
            alpha = acc[3] // n
            if alpha:
                scale = 255 / acc[3]
                rows += bytes((int(acc[0] * scale), int(acc[1] * scale), int(acc[2] * scale), alpha))
            else:
                rows += b"\0\0\0\0"

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
    header = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    ICON.write_bytes(header + png)
    return png


# ---------------------------------------------------------------- main

def existing_server(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == "clipper"
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description="MeGaA Clipper app window")
    parser.add_argument("video", nargs="?")
    parser.add_argument("--port", type=int, default=PREFERRED_PORT)
    parser.add_argument("--no-window", action="store_true", help="only run the server")
    args = parser.parse_args()

    if not ICON.exists():
        make_icon()

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        if existing_server(args.port):  # the app is already open: just show another window
            open_window(f"http://127.0.0.1:{args.port}/")
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    if args.video:
        try:
            session.open(args.video)
        except ClipperError:
            pass

    url = f"http://127.0.0.1:{port}/"
    if args.no_window:
        print(f"MeGaA Clipper running at {url}", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        server.shutdown()
        return

    window = open_window(url)
    session.last_seen = time.time()
    while True:
        time.sleep(1)
        if session.job["running"]:
            continue
        window_gone = window is not None and window.poll() is not None
        said_bye = session.bye_at and time.time() - session.bye_at > 4 and session.last_seen <= session.bye_at + 1
        idle = window is None and time.time() - session.last_seen > 1800
        if window_gone or said_bye or idle:
            break
    server.shutdown()


if __name__ == "__main__":
    main()
