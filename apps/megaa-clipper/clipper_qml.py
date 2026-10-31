"""MeGaA Clipper – QML edition (PySide6).

    pythonw clipper_qml.py [VIDEO]

Same engine as the web edition (clipper.py, library.py and the Session in clipper_app.py);
only the interface is different: Qt Quick / QML in ./qml, rendered on the GPU.
"""

import hashlib
import json
import math
import os
import subprocess
import sys
import threading
import wave
from array import array
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

import clipper
import clipper_app
import library
from clipper import ClipperError

QML_DIR = clipper.ROOT / "qml"


def file_url(path):
    return QUrl.fromLocalFile(str(path)).toString() if path else ""


def error(err):
    return {"error": str(err)}


def tone_wav(freq):
    """sfx/tone_<freq>.wav: 1 s of a full-scale sine (48 kHz stereo 16-bit) for the preview's bleep.
    1 s holds a whole number of cycles, so it loops without a click."""
    freq = max(20, min(20000, int(round(freq or 1000))))
    path = clipper.SFX_DIR / f"tone_{freq}.wav"
    if not path.exists():
        clipper.SFX_DIR.mkdir(exist_ok=True)
        rate = 48000
        samples = array("h")
        for i in range(rate):
            v = int(round(32767 * math.sin(2 * math.pi * freq * i / rate)))
            samples.extend((v, v))
        if sys.byteorder == "big":
            samples.byteswap()
        tmp = path.with_name(f"{path.stem}.part.wav")
        with wave.open(str(tmp), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(samples.tobytes())
        tmp.replace(path)
    return path


def custom_sound_wav(path):
    """A custom muted-word sound as a WAV the preview can play (SoundEffect only reads PCM WAV): converted
    once by ffmpeg with the render's own resampling and kept in sfx/custom/<hash of path, size and time>.wav."""
    src = Path(path or "")
    if not path or not src.is_file() or src.suffix.lower() not in clipper_app.AUDIO_SUFFIXES:
        raise ClipperError("The custom sound for muted words wasn't found - pick it again")
    st = src.stat()
    key = hashlib.sha1(f"{src.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8")).hexdigest()[:16]
    out = clipper.SFX_DIR / "custom" / f"{key}.wav"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{key}.part.wav")
        clipper.run([clipper.FFMPEG, "-y", "-v", "error", "-i", src, "-vn",
                     "-af", "aresample=48000,aformat=channel_layouts=stereo", "-c:a", "pcm_s16le", tmp])
        tmp.replace(out)
    return out


def exif_orientation(path):
    """The EXIF orientation (1-8, 1 = as stored) of a PNG (eXIf chunk) or WebP (EXIF chunk) picture. ffmpeg turns
    those upright like a JPEG; Qt's Image.autoTransform only reads a JPEG's, so the preview turns them itself."""
    try:
        data = Path(path).read_bytes()
        tiff = None
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            pos = 8
            while pos + 8 <= len(data) and tiff is None:
                size, kind = int.from_bytes(data[pos:pos + 4], "big"), data[pos + 4:pos + 8]
                if kind == b"eXIf":
                    tiff = data[pos + 8:pos + 8 + size]
                pos += 12 + size
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            pos = 12
            while pos + 8 <= len(data) and tiff is None:
                kind, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "little")
                if kind == b"EXIF":
                    tiff = data[pos + 8:pos + 8 + size]
                pos += 8 + size + (size & 1)
        if not tiff:
            return 1
        # the chunk must start with the TIFF header: ffmpeg ignores one with a JPEG-style "Exif\0\0" prefix
        # (a WebP is then rendered as stored; a PNG can't be decoded at all and is refused by popupInfo)
        order = {b"II": "little", b"MM": "big"}[tiff[:2]]
        ifd = int.from_bytes(tiff[4:8], order)
        for n in range(int.from_bytes(tiff[ifd:ifd + 2], order)):
            entry = tiff[ifd + 2 + 12 * n:ifd + 14 + 12 * n]
            if int.from_bytes(entry[:2], order) == 0x0112:
                value = int.from_bytes(entry[8:10], order)
                return value if 1 <= value <= 8 else 1
    except (OSError, KeyError, ValueError):
        pass
    return 1


class Backend(QObject):
    """Everything the QML interface asks the engine for. Long jobs run in the Session's threads;
    QML polls state() a few times a second, like the web edition does."""

    toast = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.session = clipper_app.session
        self.popup_cache = {}   # (path, size, mtime) -> popup_details

    # ------------------------------------------------------------ state

    @Slot(result="QVariant")
    def state(self):
        return self.session.snapshot()

    @Slot(result=str)
    def mediaUrl(self):
        return file_url(self.session.media_path()) if self.session.video else ""

    @Slot(result="QVariant")
    def transcript(self):
        try:
            return self.session.transcript()
        except ClipperError as err:
            return error(err)

    @Slot(result=str)
    def peaks(self):
        path = self.session.project / "peaks.json" if self.session.project else None
        return path.read_text() if path and path.exists() else ""

    @Slot(result="QVariant")
    def styles(self):
        return {
            "styles": clipper.CAPTION_STYLES, "default": clipper.DEFAULT_CAPTION_STYLE,
            "hooks": clipper.HOOK_STYLES, "default_hook": clipper.DEFAULT_HOOK_STYLE,
            "hook_top": clipper.HOOK_MARGIN_TOP, "keywords": clipper.KEYWORD_EMOJI,
            "emoji_size": clipper.EMOJI_SIZE,
            # Qt hands dicts to QML with sorted keys, so the preset order travels separately
            "style_order": list(clipper.CAPTION_STYLES), "hook_order": list(clipper.HOOK_STYLES),
            "mute_order": list(clipper.MUTE_SOUNDS),
            "mute_sounds": {k: {"label": v["label"], "kind": v["kind"], "freq": v.get("freq")}
                            for k, v in clipper.MUTE_SOUNDS.items()},
        }

    @Slot(str, result=str)
    def emojiUrl(self, emoji):
        png = clipper.emoji_png(emoji)
        return file_url(png) if png.exists() else ""

    @Slot(str, result=str)
    def clipUrl(self, name):
        if not self.session.project:
            return ""
        path = self.session.project / "out" / f"{clipper.safe_name(name)}.mp4"
        return file_url(path) if path.exists() else ""

    @Slot(str, result="QVariant")
    def planClip(self, clip_json):
        """The engine's own plan for a clip (kept pieces, teaser, speed, final length and the caption words
        on the clip's timeline) – the numbers the render uses. Testing aid: the preview must match it."""
        try:
            clip = json.loads(clip_json)
            clip.update(clipper_app.clean_edits(clip))
            words, lines = clipper.load_transcript(self.session.project)
            plan = clipper.plan_clip(clip, self.session.info, words, lines)
            source = words
            mutes = clip.get("mutes") or []
            if mutes and clip.get("mute_captions", True):
                source = [{**w, "w": clipper.censor(w["w"])} if clipper.muted(w, mutes) else w for w in words]
            mapped = clipper.map_words(source, plan["pieces"], plan["speed"])
            pops = clip.get("popups") or []
            shown = clipper.popup_occurrences(clip, plan["pieces"], plan["speed"])
            return {"segments": [list(p) for p in plan["segments"]],
                    "teaser": list(plan["teaser"]) if plan["teaser"] else None,
                    "speed": plan["speed"], "duration": plan["duration"],
                    "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in mapped],
                    # [index in the cleaned clip's popups, start on the finished clip] per occurrence
                    "popups": [[next(i for i, q in enumerate(pops) if q is p), start] for p, start in shown]}
        except (ClipperError, ValueError, KeyError, TypeError) as err:
            return error(err)

    # ------------------------------------------------------------ preview sounds (Edit tab)

    @Slot(str, result=str)
    def sfxUrl(self, name):
        """A built-in muted-word sound (sfx/<name>.wav, made by ffmpeg the first time), or ""."""
        try:
            return file_url(clipper.sfx_file(name))
        except (ClipperError, OSError):
            return ""

    @Slot(float, result=str)
    def toneUrl(self, freq):
        """The looping bleep tone at `freq` Hz, or ""."""
        try:
            return file_url(tone_wav(freq))
        except OSError:
            return ""

    @Slot(str, result=str)
    def customSoundUrl(self, path):
        """The user's muted-word sound converted for the preview, or "" (missing / unreadable)."""
        try:
            return file_url(custom_sound_wav(path))
        except (ClipperError, OSError):
            return ""

    @Slot(str, result=str)
    def musicUrl(self, path):
        """The background music, or "" unless it is an existing audio file."""
        p = Path(path or "")
        ok = bool(path) and p.is_file() and p.suffix.lower() in clipper_app.AUDIO_SUFFIXES
        return file_url(p) if ok else ""

    @Slot(str, result="QVariant")
    def checkAudio(self, url):
        """A file picked in the audio dialog: {path, name} if it is an audio file the engine takes
        (like /api/pick-music and /api/pick-sfx), else {path: ""}."""
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        p = Path(path) if path else None
        if p and p.is_file() and p.suffix.lower() in clipper_app.AUDIO_SUFFIXES:
            self.session.picked_music.add(str(p))
            return {"path": str(p), "name": p.name}
        return {"path": ""}

    # ------------------------------------------------------------ pop-ups (Edit tab)

    @Slot(result="QVariant")
    def popupTypes(self):
        """The file types a pop-up can be – the engine's own lists, pictures first (plain lists: dicts
        reach QML with sorted keys)."""
        videos = sorted(clipper.VIDEO_SUFFIXES)
        return {"popup": sorted(clipper.POPUP_SUFFIXES - clipper.VIDEO_SUFFIXES) + videos, "video": videos}

    @Slot(str, result="QVariant")
    def popupInfo(self, path):
        """A pop-up file (a file: URL or a path), like /api/pick-popup + /media/file: {path: ""} unless it is
        a picture, GIF or video the engine takes, else the path as the web edition saves it, the file name,
        its URL, kind (picture / gif / video) and whether it exists – plus what the render makes of it
        (popup_details); a file the render can't use has an error and no URL."""
        if path.startswith("file:"):
            path = QUrl(path).toLocalFile()
        if not path or Path(path).suffix.lower() not in clipper.POPUP_SUFFIXES:
            return {"path": ""}
        target = Path(path)
        suffix = target.suffix.lower()
        kind = "video" if suffix in clipper.VIDEO_SUFFIXES else "gif" if suffix == ".gif" else "picture"
        info = {"path": str(target), "name": target.name, "url": file_url(target), "kind": kind,
                "exists": target.is_file()}
        if info["exists"]:
            info.update(self.popup_details(target, kind))
            if info.get("error"):
                info["url"] = ""
        return info

    def popup_details(self, target, kind):
        """What the render makes of a pop-up file, worked out once per version of the file: {error} for a
        picture or GIF ffmpeg can't decode (the render refuses it), a GIF's frame times {gif}, the EXIF
        orientation of a PNG / WebP {orient} and a video's size turned upright by its rotation {w, h} (ffmpeg
        turns pictures and videos upright before scaling them)."""
        try:
            st = target.stat()
            key = (str(target), st.st_size, st.st_mtime_ns)
        except OSError:
            return {}
        if key not in self.popup_cache:
            details = {}
            try:
                if kind == "video":
                    info = clipper.probe(target)
                    details = {"w": info["width"], "h": info["height"]}
                else:
                    clipper.check_popup_picture(target)
                    if kind == "gif":
                        details = {"gif": clipper.gif_timing(target)}
                    elif target.suffix.lower() in (".png", ".webp"):
                        details = {"orient": exif_orientation(target)}
            except ClipperError as err:
                details = {} if kind == "video" else {"error": str(err)}
            self.popup_cache[key] = details
        return self.popup_cache[key]

    # ------------------------------------------------------------ actions

    @Slot(str, result="QVariant")
    def openVideo(self, path):
        try:
            if path.startswith("file:"):
                path = QUrl(path).toLocalFile()
            self.session.open(path)
            return {}
        except ClipperError as err:
            return error(err)

    @Slot(result="QVariant")
    def closeVideo(self):
        with self.session.lock:
            if self.session.job["running"]:
                return error("Wait for the current task to finish first")
            self.session.video = self.session.project = self.session.info = None
        return {}

    @Slot(str, result="QVariant")
    def transcribe(self, lang):
        try:
            self.session.transcribe(lang or "en")
            return {}
        except ClipperError as err:
            return error(err)

    @Slot(str, result="QVariant")
    def saveClips(self, clips_json):
        """Clips arrive as JSON text (plain data, no QJSValue conversion surprises)."""
        try:
            self.session.save_clips(json.loads(clips_json))
            return {"clips": self.session.clips_with_status()}
        except (ClipperError, ValueError, KeyError, TypeError) as err:
            return error(err)

    @Slot(str, result="QVariant")
    def render(self, names_json):
        try:
            self.session.render(json.loads(names_json))
            return {}
        except (ClipperError, ValueError) as err:
            return error(err)

    @Slot(float, float, str, result="QVariant")
    def editLine(self, start, end, text):
        try:
            clipper.replace_line_text(self.session.project, start, end, text)
            return {}
        except ClipperError as err:
            return error(err)

    @Slot()
    def openOutput(self):
        if self.session.project:
            folder = self.session.project / "out"
            folder.mkdir(exist_ok=True)
            os.startfile(folder)

    @Slot(str)
    def reveal(self, name):
        if self.session.project:
            target = self.session.project / "out" / f"{clipper.safe_name(name)}.mp4"
            subprocess.Popen(["explorer", "/select,", str(target)])

    # ------------------------------------------------------------ settings, moments, campaigns, tracker, export

    aiMomentsDone = Signal("QVariant")   # the AI picks, {moments, cost} or {error}: they take about a minute

    @Slot(result="QVariant")
    def settings(self):
        key = library.settings().get("api_key") or ""
        return {"has_key": bool(key), "key_hint": f"…{key[-4:]}" if key else ""}

    @Slot(str, result="QVariant")
    def saveApiKey(self, key):
        try:
            library.save_settings({"api_key": str(key or "").strip()})
            return {}
        except OSError as err:
            return error(err)

    @Slot(int, float, float, result="QVariant")
    def moments(self, count, min_len, max_len):
        """The free picks (clipper.find_moments): every sentence-to-sentence stretch, scored."""
        try:
            lines = clipper.load_lines(self.session.project)
            peaks_file = self.session.project / "peaks.json"
            peaks = json.loads(peaks_file.read_text())["peaks"] if peaks_file.exists() else None
            return {"moments": clipper.find_moments(lines, peaks, min_len=min_len, max_len=max_len, count=count)}
        except (ClipperError, OSError, ValueError, KeyError, TypeError) as err:
            return error(err)

    @Slot(int, float, float, result="QVariant")
    def aiMoments(self, count, min_len, max_len):
        """Starts the AI picks in a thread; the answer arrives through aiMomentsDone."""
        try:
            lines = clipper.load_lines(self.session.project)
        except (ClipperError, OSError, ValueError, TypeError) as err:
            return error(err)

        def work():
            try:
                moments, cost = library.ai_moments(lines, count, min_len, max_len)
                self.aiMomentsDone.emit({"moments": moments, "cost": cost})
            except Exception as err:  # noqa: BLE001 – any failure must reach the window, or it waits forever
                self.aiMomentsDone.emit(error(err))
        threading.Thread(target=work, daemon=True).start()
        return {}

    @Slot(result="QVariant")
    def campaigns(self):
        return library.campaigns()

    @Slot(str, result="QVariant")
    def saveCampaign(self, data_json):
        try:
            return {"campaign": library.save_campaign(json.loads(data_json))}
        except (ClipperError, OSError, ValueError, TypeError) as err:
            return error(err)

    @Slot(str, result="QVariant")
    def deleteCampaign(self, campaign_id):
        try:
            library.delete_campaign(campaign_id)
            if self.session.project and self.session.project_meta().get("campaign") == campaign_id:
                self.session.set_campaign(None)
            return {}
        except OSError as err:
            return error(err)

    @Slot(str, result="QVariant")
    def setProjectCampaign(self, campaign_id):
        """The campaign whose rules this video's clips are checked against ("" = none)."""
        if not self.session.project:
            return error("Open a video first")
        try:
            self.session.set_campaign(campaign_id or None)
            return {}
        except OSError as err:
            return error(err)

    @Slot(result="QVariant")
    def tracker(self):
        return {"entries": library.tracker(), "campaigns": library.campaigns()}

    @Slot(str, result="QVariant")
    def saveEntry(self, data_json):
        try:
            return {"entry": library.save_entry(json.loads(data_json))}
        except (OSError, ValueError, TypeError) as err:
            return error(err)

    @Slot(str, result="QVariant")
    def deleteEntry(self, entry_id):
        try:
            library.delete_entry(entry_id)
            return {}
        except OSError as err:
            return error(err)

    @Slot(bool, result="QVariant")
    def exportPack(self, make_zip):
        """Every rendered clip + captions.txt into clipper/exports/ (a folder, or one ZIP), then shows it."""
        try:
            camp = library.campaign(self.session.project_meta().get("campaign"))
            result = library.export_pack(self.session.project, clipper.load_clips(self.session.project), camp,
                                         make_zip=make_zip)
            if result.is_dir():
                os.startfile(result)
            else:
                subprocess.Popen(["explorer", "/select,", str(result)])
            return {"path": str(result)}
        except (ClipperError, OSError, TypeError) as err:
            return error(err)


def dark_title_bar(window):
    """Same dark title bar + cyan border as the web edition (Windows 10/11)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        colors = {"BG": 0x0D0705, "BORDER": 0xA79700, "TEXT": 0xFFF1E6}  # 0x00BBGGRR
        for attr, value in ((20, 1), (35, colors["BG"]), (34, colors["BORDER"]), (36, colors["TEXT"])):
            data = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(data), ctypes.sizeof(data))
    except (AttributeError, OSError):
        pass


def main():
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv)
    app.setApplicationName("MeGaA Clipper")
    app.setWindowIcon(QIcon(str(clipper.ROOT / "ui" / "clipper.ico")))

    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("testMode", bool(os.environ.get("MEGAA_SHOT")))
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    window = engine.rootObjects()[0]
    dark_title_bar(window)

    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        backend.openVideo(sys.argv[1])

    # testing aid: MEGAA_TEST=script.js runs JavaScript in the window (Store, stage, win) after MEGAA_TEST_MS
    test = os.environ.get("MEGAA_TEST")
    if test:
        code = Path(test).read_text(encoding="utf-8")
        QTimer.singleShot(int(os.environ.get("MEGAA_TEST_MS", "2500")),
                          lambda: QMetaObject.invokeMethod(window, "runTest", Q_ARG("QVariant", code)))

    # testing aid: MEGAA_SHOT=out.png [MEGAA_SHOT_MS=4000] saves a picture of the window, then quits
    shot = os.environ.get("MEGAA_SHOT")
    if shot:
        def grab():
            window.grabWindow().save(shot)
            app.quit()
        QTimer.singleShot(int(os.environ.get("MEGAA_SHOT_MS", "4000")), grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
