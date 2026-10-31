"""MeGaA Clipper engine: turn long videos into vertical, captioned short clips.

Pure standard-library Python. Uses the bundled ffmpeg and whisper.cpp in ./tools.

Command line:
    python clipper.py transcribe VIDEO [--lang en]
    python clipper.py search VIDEO "words to find"
    python clipper.py frame VIDEO --at 12:30
    python clipper.py cut VIDEO --start 12:30 --end 13:05 [--layout crop|fit]
                      [--crop-x 0.5] [--hook "text"] [--no-captions] [--name clip_01]
                      [--style classic|bold|box|neon|karaoke|oneword|minimal|retro] [--color #RRGGBB]
    python clipper.py render VIDEO          (renders every clip in the project's clips.json)

Each video gets a project folder in ./projects/<video name>/ holding the transcript,
clips.json, preview frames and the finished clips in out/.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"
PROJECTS = ROOT / "projects"

FFMPEG = TOOLS / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = TOOLS / "ffmpeg" / "bin" / "ffprobe.exe"
WHISPER_GPU = TOOLS / "whisper" / "whisper-cli.exe"
WHISPER_CPU = TOOLS / "whisper-cpu" / "whisper-cli.exe"
MODEL = TOOLS / "models" / "ggml-large-v3-turbo-q5_0.bin"

OUT_W, OUT_H = 1080, 1920
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Caption looks. "mode" decides how the spoken word stands out:
#   word = it takes the accent colour, box = it sits on an accent box,
#   fill = words turn accent as they are spoken (karaoke), none = no highlight.
# Sizes are in output pixels (1080x1920); margin_v is the gap below the captions.
_BASE_STYLE = {
    "font": "Arial Black", "bold": False, "size": 84, "uppercase": True,
    "max_words": 3, "max_chars": 18,
    "text": "#FFFFFF", "accent": "#FFFF00", "mode": "word",
    "outline": 7, "outline_color": "#000000", "shadow": 3, "glow": 0,
    "box_pad": 16, "pop": 1.12, "active_scale": 1.0, "margin_v": 480,
}
CAPTION_STYLES = {
    "classic": {**_BASE_STYLE, "label": "Classic"},
    "bold": {**_BASE_STYLE, "label": "Bold Pop", "font": "Segoe UI Black", "size": 92,
             "max_words": 2, "max_chars": 14, "accent": "#39FF14", "outline": 8, "shadow": 4,
             "pop": 1.0, "active_scale": 1.15},
    "box": {**_BASE_STYLE, "label": "Box", "size": 80, "accent": "#FF2BD6", "mode": "box",
            "outline": 6, "shadow": 0, "pop": 1.08},
    "neon": {**_BASE_STYLE, "label": "Neon", "font": "Segoe UI Black", "size": 82,
             "accent": "#FF2BD6", "outline": 5, "outline_color": "#00E5FF", "shadow": 0,
             "glow": 8, "pop": 1.1},
    "karaoke": {**_BASE_STYLE, "label": "Karaoke", "font": "Franklin Gothic Heavy", "size": 86,
                "max_words": 4, "max_chars": 24, "accent": "#FFD400", "mode": "fill", "pop": 1.0},
    "oneword": {**_BASE_STYLE, "label": "One Word", "font": "Impact", "size": 132, "max_words": 1,
                "max_chars": 30, "accent": "#FFE600", "outline": 9, "shadow": 4, "pop": 1.3},
    "minimal": {**_BASE_STYLE, "label": "Minimal", "font": "Segoe UI", "bold": True, "size": 60,
                "uppercase": False, "max_words": 6, "max_chars": 34, "mode": "none",
                "outline": 2, "shadow": 2, "pop": 1.0},
    "retro": {**_BASE_STYLE, "label": "Retro", "font": "Cooper Black", "size": 86,
              "uppercase": False, "text": "#FFF4D6", "accent": "#FFD23F", "outline": 7,
              "outline_color": "#E2541B", "shadow": 5, "pop": 1.1},
}
DEFAULT_CAPTION_STYLE = "classic"

# Hook (title at the top) looks. "box" draws a solid box behind the text, "outline" a text outline.
_BASE_HOOK = {"font": "Arial Black", "size": 60, "uppercase": False, "mode": "box", "text": "#000000",
              "box": "#FFFFFF", "pad": 18, "outline": 0, "outline_color": "#000000", "shadow": 0, "glow": 0}
HOOK_STYLES = {
    "white": {**_BASE_HOOK, "label": "White box"},
    "dark": {**_BASE_HOOK, "label": "Dark box", "text": "#FFFFFF", "box": "#0B0B0F"},
    "red": {**_BASE_HOOK, "label": "Red alert", "text": "#FFFFFF", "box": "#FF1744", "uppercase": True, "size": 58},
    "yellow": {**_BASE_HOOK, "label": "Yellow", "box": "#FFE600"},
    "outline": {**_BASE_HOOK, "label": "Outline", "mode": "outline", "size": 66, "text": "#FFFFFF",
                "outline": 6, "shadow": 3},
    "neon": {**_BASE_HOOK, "label": "Neon", "mode": "outline", "font": "Segoe UI Black", "size": 64,
             "text": "#FFFFFF", "outline": 4, "outline_color": "#FF2BD6", "glow": 8},
    "meme": {**_BASE_HOOK, "label": "Meme", "mode": "outline", "font": "Impact", "size": 80,
             "uppercase": True, "text": "#FFFFFF", "outline": 6},
}
DEFAULT_HOOK_STYLE = "white"
HOOK_MARGIN_TOP = 230


def resolve_hook(clip):
    """The hook look for a clip: its preset plus the clip's size and height tweaks."""
    style = dict(HOOK_STYLES.get(clip.get("hook_style") or DEFAULT_HOOK_STYLE, HOOK_STYLES[DEFAULT_HOOK_STYLE]))
    size = clip.get("hook_size")
    if isinstance(size, (int, float)) and size > 0:
        style["size"] = round(style["size"] * min(200, max(50, size)) / 100)
    pos = clip.get("hook_pos")
    style["margin_v"] = int(min(1600, max(40, pos))) if isinstance(pos, (int, float)) else HOOK_MARGIN_TOP
    duration = clip.get("hook_duration")
    style["duration"] = float(duration) if isinstance(duration, (int, float)) and duration > 0 else 0.0
    return style


def resolve_style(clip):
    """The caption style for a clip: its preset plus the clip's colour, size and height tweaks."""
    style = dict(CAPTION_STYLES.get(clip.get("caption_style") or DEFAULT_CAPTION_STYLE,
                                    CAPTION_STYLES[DEFAULT_CAPTION_STYLE]))
    color = clip.get("caption_color")
    if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        style["accent"] = color.upper()
    size = clip.get("caption_size")
    if isinstance(size, (int, float)) and size > 0:
        style["size"] = round(style["size"] * min(200, max(50, size)) / 100)
    pos = clip.get("caption_pos")
    if isinstance(pos, (int, float)):
        style["margin_v"] = int(min(1700, max(80, pos)))
    kw_color = clip.get("kw_color")
    ok = isinstance(kw_color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", kw_color)
    style["kw_color"] = (kw_color.upper() if ok else "#39FF14") if clip.get("kw_highlight") else None
    style["emojis"] = bool(clip.get("emojis"))
    return style


class ClipperError(Exception):
    pass


# ---------------------------------------------------------------- time helpers

def parse_time(value):
    """Accept 750, 750.5, "12:30", "12:30.5" or "1:02:03.5" and return seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        raise ClipperError("Empty time value")
    parts = text.split(":")
    if len(parts) > 3:
        raise ClipperError(f"Bad time: {text!r}")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    except ValueError:
        raise ClipperError(f"Bad time: {text!r}") from None
    return seconds


def fmt_time(seconds):
    """750.5 -> "12:30.5", 3723.0 -> "1:02:03.0"."""
    seconds = round(max(0.0, float(seconds)), 1)  # so 59.96 shows as 1:00.0, not 0:60.0
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{int(hours)}:{int(minutes):02d}:{secs:04.1f}"
    return f"{int(minutes)}:{secs:04.1f}"


def ass_time(seconds):
    centis = int(round(max(0.0, seconds) * 100))
    hours, centis = divmod(centis, 360000)
    minutes, centis = divmod(centis, 6000)
    secs, centis = divmod(centis, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


# ---------------------------------------------------------------- processes

def check_tools(need_whisper=False):
    missing = [p for p in (FFMPEG, FFPROBE) if not p.exists()]
    if need_whisper:
        if not (WHISPER_GPU.exists() or WHISPER_CPU.exists()):
            missing.append(WHISPER_GPU)
        if not MODEL.exists():
            missing.append(MODEL)
    if missing:
        names = ", ".join(str(p.relative_to(ROOT)) for p in missing)
        raise ClipperError(f"Missing tools: {names}")


def run(cmd, cwd=None, on_line=None):
    """Run a command, streaming its stderr+stdout lines to on_line. Returns the output."""
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
    )
    lines = []
    buf = ""
    while True:
        chunk = proc.stdout.read(1)
        if not chunk:
            break
        if chunk in "\r\n":
            if buf:
                lines.append(buf)
                if on_line:
                    on_line(buf)
            buf = ""
        else:
            buf += chunk
    if buf:
        lines.append(buf)
        if on_line:
            on_line(buf)
    proc.wait()
    output = "\n".join(lines)
    if proc.returncode != 0:
        tail = "\n".join(lines[-15:])
        raise ClipperError(f"{Path(str(cmd[0])).name} failed (exit {proc.returncode}):\n{tail}")
    return output


def probe(video):
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
         "-show_entries",
         "stream=codec_name,width,height,r_frame_rate:stream_side_data=rotation:format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=NO_WINDOW,
    )
    if out.returncode != 0:
        raise ClipperError(f"Can't read video: {out.stderr.strip()}")
    info = json.loads(out.stdout)
    streams = info.get("streams") or []
    if not streams:
        raise ClipperError("No video stream found in the file")
    stream = streams[0]
    width, height = int(stream["width"]), int(stream["height"])
    for side in stream.get("side_data_list", []):
        if abs(int(side.get("rotation", 0))) in (90, 270):
            width, height = height, width
    num, _, den = stream.get("r_frame_rate", "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    duration = float(info.get("format", {}).get("duration", 0) or 0)
    audio = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    )
    return {"width": width, "height": height, "fps": fps, "duration": duration,
            "codec": stream.get("codec_name", ""), "has_audio": bool(audio.stdout.strip())}


# ---------------------------------------------------------------- projects

def safe_name(text):
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return name[:60] or "video"


def project_dir(video):
    """Folder that holds everything made from this video."""
    video = Path(video).resolve()
    base = safe_name(video.stem)
    folder = PROJECTS / base
    meta = folder / "project.json"
    if meta.exists():
        source = json.loads(meta.read_text(encoding="utf-8")).get("source")
        if source and Path(source) != video:
            digest = hashlib.sha1(str(video).encode()).hexdigest()[:6]
            folder = PROJECTS / f"{base}-{digest}"
    folder.mkdir(parents=True, exist_ok=True)
    meta = folder / "project.json"
    if not meta.exists():
        meta.write_text(json.dumps({"source": str(video)}, indent=2), encoding="utf-8")
    return folder


def load_words(project):
    path = Path(project) / "words.json"
    if not path.exists():
        raise ClipperError("This video has no transcript yet - run transcribe first")
    return json.loads(path.read_text(encoding="utf-8"))


def load_lines(project):
    path = Path(project) / "transcript.json"
    if not path.exists():
        raise ClipperError("This video has no transcript yet - run transcribe first")
    return json.loads(path.read_text(encoding="utf-8"))


def load_clips(project):
    path = Path(project) / "clips.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("clips", [])


def save_clips(project, clips):
    path = Path(project) / "clips.json"
    path.write_text(json.dumps({"clips": clips}, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- transcription

def group_lines(words, max_words=24, max_gap=1.0):
    """Group word timestamps into transcript lines that end where sentences end."""
    lines, current = [], []
    for word in words:
        if current:
            gap = word["s"] - current[-1]["e"]
            last = current[-1]["w"].rstrip()
            sentence_done = last.endswith((".", "?", "!")) and len(current) >= 3
            long_at_comma = last.endswith(",") and len(current) >= 14
            if gap > max_gap or sentence_done or long_at_comma or len(current) >= max_words:
                lines.append(current)
                current = []
        current.append(word)
    if current:
        lines.append(current)
    return [
        {"s": line[0]["s"], "e": line[-1]["e"], "text": " ".join(w["w"] for w in line)}
        for line in lines
    ]


def transcribe(video, language="en", on_progress=None, on_log=None):
    """Write words.json, transcript.json and transcript.txt into the project folder."""
    check_tools(need_whisper=True)
    project = project_dir(video)
    audio = project / "audio.wav"
    if on_log:
        on_log("Extracting audio...")
    run([FFMPEG, "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", audio])

    def progress(line):
        match = re.search(r"progress\s*=\s*(\d+)%", line)
        if match and on_progress:
            on_progress(int(match.group(1)))
        # say where it really runs: the GPU build quietly falls back to the CPU when CUDA can't load
        # (e.g. cublas64_11.dll missing next to whisper-cli.exe)
        if on_log and "whisper_backend_init_gpu: using" in line:
            on_log("Transcribing on the GPU...")
        elif on_log and "whisper_backend_init_gpu: no GPU found" in line:
            on_log("Transcribing on the CPU (no GPU found) – slower...")

    out_base = project / "whisper"
    args = ["-m", MODEL, "-f", audio, "-l", language, "-ml", "1", "-sow",
            "-oj", "-of", out_base, "-pp", "-t", str(max(1, (os.cpu_count() or 4) - 2))]
    engines = [p for p in (WHISPER_GPU, WHISPER_CPU) if p.exists()]
    last_error = None
    for engine in engines:
        if on_log:
            on_log("Loading the speech model...")
        try:
            run([engine, *args], cwd=engine.parent, on_line=progress)
            last_error = None
            break
        except ClipperError as err:
            last_error = err
            if on_log:
                on_log(f"{engine.parent.name} engine failed, trying the next one")
    if last_error:
        raise last_error

    data = json.loads((out_base.with_suffix(".json")).read_text(encoding="utf-8", errors="replace"))
    words = []
    for seg in data.get("transcription", []):
        text = seg.get("text", "").strip()
        if not text or text.startswith("[") and text.endswith("]"):
            continue
        start = seg["offsets"]["from"] / 1000
        end = seg["offsets"]["to"] / 1000
        # whisper sometimes splits one word into pieces with no leading space
        if words and not seg.get("text", " ").startswith(" ") and start - words[-1]["e"] < 0.05:
            words[-1]["w"] += text
            words[-1]["e"] = end
            continue
        words.append({"w": text, "s": round(start, 2), "e": round(end, 2)})

    save_transcript(project, words)
    audio.unlink(missing_ok=True)
    if on_progress:
        on_progress(100)
    return project


def save_transcript(project, words):
    """Write words.json plus the line-based transcript.json / transcript.txt made from it."""
    project = Path(project)
    lines = group_lines(words)
    (project / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (project / "transcript.json").write_text(json.dumps(lines, ensure_ascii=False, indent=0), encoding="utf-8")
    with open(project / "transcript.txt", "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(f"[{fmt_time(line['s'])} - {fmt_time(line['e'])}] {line['text']}\n")


def replace_line_text(project, start, end, text):
    """Fix misheard words: swap the words spoken between start and end for `text`.

    Same word count keeps each word's timing; otherwise the line's time is shared out
    by word length. Empty text removes the words (no captions there)."""
    words = load_words(project)
    picked = [i for i, w in enumerate(words) if w["s"] >= start - 0.01 and w["e"] <= end + 0.01]
    if not picked:
        raise ClipperError("Couldn't find those words in the transcript")
    first, last = picked[0], picked[-1]
    old = words[first:last + 1]
    tokens = text.split()
    if len(tokens) == len(old):
        new = [{"w": t, "s": o["s"], "e": o["e"]} for t, o in zip(tokens, old)]
    else:
        t0, t1 = old[0]["s"], old[-1]["e"]
        weights = [len(t) + 1 for t in tokens]
        total, pos, new = sum(weights) or 1, t0, []
        for token, weight in zip(tokens, weights):
            step = (t1 - t0) * weight / total
            new.append({"w": token, "s": round(pos, 2), "e": round(pos + step * 0.92, 2)})
            pos += step
    words[first:last + 1] = new
    save_transcript(project, words)


# ---------------------------------------------------------------- finding viral moments (offline)

HOOK_OPENERS = ("you ", "why ", "how ", "what ", "the truth", "nobody", "no one", "never", "stop ", "here's",
                "here is", "this is", "if you", "most people", "the secret", "the reason", "i was", "imagine",
                "the problem", "the biggest", "the best", "the worst", "the only", "let me", "listen", "so here")


def hook_strength(text):
    """0..1.5: how well a sentence works as the first thing a viewer hears."""
    t = text.lower().strip()
    score = 0.0
    if t.endswith("?"):
        score += 0.5
    if t.startswith(HOOK_OPENERS):
        score += 0.6
    if any(c.isdigit() for c in t):
        score += 0.3
    if any(keyword_emoji(w)[0] for w in t.split()):
        score += 0.3
    if len(t.split()) <= 12:
        score += 0.2
    return min(1.5, score)


def short_hook(text, limit=55):
    text = text.strip().rstrip(".")
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def find_moments(lines, peaks=None, peak_rate=20, min_len=20.0, max_len=60.0, count=10):
    """Suggest the best clips, offline: [{start, end, score, hook, text, why}].

    Every candidate runs from a sentence start to a sentence end and is scored on a strong
    opening line, keywords and numbers, loudness, pace, a punchy ending and a 30-40 s length."""
    if not lines:
        return []
    mean_peak = (sum(peaks) / len(peaks)) if peaks else 0

    def energy(a, b):
        if not peaks or not mean_peak:
            return 1.0
        window = peaks[int(a * peak_rate):int(b * peak_rate)]
        return (sum(window) / len(window) / mean_peak) if window else 1.0

    candidates = []
    for i, first in enumerate(lines):
        for j in range(i, len(lines)):
            start, end = max(0.0, first["s"] - 0.15), lines[j]["e"] + 0.3
            length = end - start
            if length > max_len:
                break
            if length < min_len:
                continue
            words = " ".join(line["text"] for line in lines[i:j + 1]).split()
            keywords = sum(1 for w in words if keyword_emoji(w)[0])
            hook = hook_strength(first["text"])
            density = keywords / max(1, len(words))
            loud = energy(start, end)
            pace = len(words) / length
            last = lines[j]["text"].rstrip()
            ending = 1.0 if last.endswith(("!", "?")) else 0.5 if last.endswith(".") else 0.0
            sweet = 1 - min(1.0, abs(length - 35) / 30)
            score = (3 * hook + 6 * density + 1.2 * min(loud, 1.6) + 0.6 * min(pace / 3, 1.2)
                     + 0.6 * ending + 0.8 * sweet)
            why = []
            if hook >= 0.6:
                why.append("strong opening line")
            if density >= 0.06:
                why.append("money / number keywords")
            if loud >= 1.15:
                why.append("high energy")
            if ending == 1.0:
                why.append("ends on a punchline")
            candidates.append({"start": round(start, 2), "end": round(end, 2), "raw": score, "i": i, "j": j,
                               "why": why or ["complete thought"]})

    candidates.sort(key=lambda c: c["raw"], reverse=True)
    picked = []
    for cand in candidates:
        overlaps = any(min(cand["end"], p["end"]) - max(cand["start"], p["start"])
                       > 0.3 * min(cand["end"] - cand["start"], p["end"] - p["start"]) for p in picked)
        if not overlaps:
            picked.append(cand)
        if len(picked) >= count:
            break
    if not picked:
        return []
    best, worst = picked[0]["raw"], picked[-1]["raw"]
    out = []
    for cand in picked:
        span = lines[cand["i"]:cand["j"] + 1]
        hook_line = max(span, key=lambda line: hook_strength(line["text"]))
        out.append({
            "start": cand["start"], "end": cand["end"],
            "score": int(round(60 + 35 * ((cand["raw"] - worst) / (best - worst) if best > worst else 1))),
            "hook": short_hook(hook_line["text"]),
            "text": " ".join(line["text"] for line in span),
            "why": cand["why"],
        })
    return out


def search(video, query):
    project = project_dir(video)
    needle = query.lower()
    return [line for line in load_lines(project) if needle in line["text"].lower()]


# ---------------------------------------------------------------- frames, proxies, waveforms

def extract_frame(video, at, out_path, width=640):
    run([FFMPEG, "-y", "-v", "error", "-ss", f"{parse_time(at):.3f}", "-i", video,
         "-frames:v", "1", "-vf", f"scale={width}:-2", out_path])
    return Path(out_path)


def make_proxy(video, out_path, duration, on_progress=None):
    """Light 720p H.264 copy used only for smooth previews (renders always use the original)."""

    def progress(line):
        match = re.search(r"out_time_us=(\d+)", line)
        if match and on_progress and duration:
            on_progress(min(99, int(int(match.group(1)) / 1e6 / duration * 100)))

    tmp = Path(out_path).with_suffix(".part.mp4")
    run([FFMPEG, "-y", "-v", "error", "-progress", "pipe:1", "-nostats", "-i", video,
         "-vf", "scale=-2:'min(720,ih)'", *video_encoder(), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tmp], on_line=progress)
    tmp.replace(out_path)
    return Path(out_path)


def audio_peaks(video, out_path, per_second=20):
    """Loudness envelope (0-255 per step) for drawing the waveform."""
    rate = per_second * 100
    proc = subprocess.run(
        [str(FFMPEG), "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(rate),
         "-f", "s16le", "-"],
        capture_output=True, creationflags=NO_WINDOW,
    )
    if proc.returncode != 0:
        raise ClipperError("Couldn't read the audio track")
    samples = array("h")
    samples.frombytes(proc.stdout[: len(proc.stdout) // 2 * 2])
    step = rate // per_second
    raw = []
    for i in range(0, len(samples), step):
        window = samples[i:i + step]
        raw.append(max(max(window), -min(window)))
    top = max(raw, default=0) or 1
    peaks = [int(255 * (p / top) ** 0.6) for p in raw]
    Path(out_path).write_text(json.dumps({"rate": per_second, "peaks": peaks}), encoding="utf-8")
    return peaks


# ---------------------------------------------------------------- captions

def clean_word(text):
    return re.sub(r"[{}\\]", "", text).strip()


def caption_chunks(words, max_words, max_chars):
    chunks, current = [], []
    for word in words:
        if current:
            joined = len(" ".join(w["w"] for w in current)) + 1 + len(word["w"])
            ends_sentence = current[-1]["w"].endswith((".", "?", "!", ","))
            if (len(current) >= max_words or joined > max_chars or ends_sentence
                    or word["s"] - current[-1]["e"] > 0.5):
                chunks.append(current)
                current = []
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def caption_words(words, start=0.0, end=None, uppercase=True):
    """Cleaned caption words between start and end, with times relative to start."""
    limit = float("inf") if end is None else end - start
    out = []
    for w in words:
        if w["e"] <= start or (end is not None and w["s"] >= end):
            continue
        text = clean_word(w["w"])
        if not text:
            continue
        if uppercase:
            text = text.upper()
        out.append({"w": text, "s": max(0.0, w["s"] - start), "e": min(limit, w["e"] - start)})
    return out


def caption_timeline(cap_words, style):
    """Group caption words into on-screen chunks; each chunk stays up until its `end`."""
    chunks = caption_chunks(cap_words, style["max_words"], style["max_chars"])
    timeline = []
    for index, chunk in enumerate(chunks):
        chunk_end = chunk[-1]["e"]
        if index + 1 < len(chunks):
            next_start = chunks[index + 1][0]["s"]
            if next_start - chunk_end < 0.35:
                chunk_end = next_start
        timeline.append({"words": chunk, "end": chunk_end})
    return timeline


# Keywords: coloured in the captions, and the emoji that pops up above the captions for them.
KEYWORD_EMOJI = {
    "money": "💰", "cash": "💵", "dollar": "💵", "salary": "💵", "paid": "💵", "rich": "🤑", "million": "🤑",
    "billion": "🤑", "wealthy": "🤑", "broke": "😩", "debt": "😩", "invest": "📈", "investing": "📈",
    "stocks": "📈", "business": "💼", "savings": "🏦", "bank": "🏦", "secret": "🤫", "truth": "👀",
    "crazy": "🤯", "insane": "🤯", "shocked": "😱", "scary": "😱", "love": "❤️", "hate": "😤", "angry": "😤",
    "fire": "🔥", "best": "🏆", "win": "🏆", "winning": "🏆", "fail": "❌", "failed": "❌", "wrong": "❌",
    "never": "🚫", "stop": "🛑", "warning": "⚠️", "danger": "⚠️", "idea": "💡", "brain": "🧠", "smart": "🧠",
    "coffee": "☕", "food": "🍔", "sleep": "😴", "gym": "💪", "strong": "💪", "phone": "📱", "car": "🚗",
    "house": "🏠", "happy": "😄", "sad": "😢", "funny": "😂", "laugh": "😂", "free": "🎁", "gift": "🎁",
    "success": "🚀", "growth": "🚀", "fast": "⚡", "power": "⚡", "dead": "💀", "death": "💀", "god": "🙏",
    "music": "🎵", "game": "🎮", "school": "🎓", "learn": "📚", "book": "📚", "future": "🔮", "goal": "🎯",
    "habit": "🔁", "doctor": "🩺", "baby": "👶", "dog": "🐶", "cat": "🐱", "wow": "😮", "time": "⏰",
}
EMOJI_DIR = ROOT / "emoji"


def bare_word(text):
    return re.sub(r"[^\w$%'-]", "", text.lower()).strip("'-")


def keyword_emoji(text):
    """(is_keyword, emoji or "") for one caption word. Numbers and money amounts count as keywords."""
    word = bare_word(text)
    if not word:
        return False, ""
    if any(c.isdigit() for c in word) or word.startswith("$") or word.endswith("%"):
        return True, "💰" if word.startswith("$") else ""
    emoji = KEYWORD_EMOJI.get(word) or (KEYWORD_EMOJI.get(word[:-1]) if word.endswith("s") else None)
    return (True, emoji) if emoji else (False, "")


def emoji_png(emoji):
    """Where the colour picture of an emoji lives (the app draws them, since ffmpeg can't)."""
    return EMOJI_DIR / ("-".join(f"{ord(c):x}" for c in emoji) + ".png")


def emoji_events(words, duration, style):
    """[(emoji, start, end)]: one emoji above each caption chunk that has a keyword with an emoji."""
    events = []
    for item in caption_timeline(caption_words(words, 0.0, duration, style["uppercase"]), style):
        for w in item["words"]:
            emoji = keyword_emoji(w["w"])[1]
            if emoji:
                events.append((emoji, item["words"][0]["s"], item["end"]))
                break
    return events


def ass_color(hex_color, alpha=0):
    """"#RRGGBB" -> ASS "&HAABBGGRR"."""
    r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def caption_event_text(chunk, active, style):
    """Text of one caption event: the whole chunk, with word `active` being spoken."""
    accent = ass_color(style["accent"])[4:]
    text = ass_color(style["text"])[4:]
    keyword = ass_color(style["kw_color"])[4:] if style.get("kw_color") else None
    scale = round(style["active_scale"] * 100)
    parts = []
    for j, w in enumerate(chunk):
        word = w["w"]
        lit = ((style["mode"] in ("word", "box") and j == active) or (style["mode"] == "fill" and j <= active))
        if keyword and not lit and keyword_emoji(word)[0]:
            word = f"{{\\c&H{keyword}&}}{word}{{\\c&H{text}&}}"
        elif style["mode"] == "word" and j == active:
            grow = f"\\fscx{scale}\\fscy{scale}" if scale != 100 else ""
            undo = "\\fscx100\\fscy100" if scale != 100 else ""
            word = f"{{\\c&H{accent}&{grow}}}{word}{{\\c&H{text}&{undo}}}"
        elif style["mode"] == "fill" and j <= active:
            word = f"{{\\c&H{accent}&}}{word}{{\\c&H{text}&}}"
        elif style["mode"] == "box" and j == active:
            outline = ass_color(style["outline_color"])[4:]
            word = (f"{{\\bord{style['box_pad']}\\3c&H{accent}&\\shad0}}{word}"
                    f"{{\\bord{style['outline']}\\3c&H{outline}&\\shad{style['shadow']}}}")
        parts.append(word)
    tags = ""
    if style["glow"]:
        tags += f"\\blur{style['glow']}"
    if active == 0 and style["pop"] != 1 and style["active_scale"] == 1:
        pop = round(style["pop"] * 100)
        tags += f"\\fscx{pop}\\fscy{pop}\\t(0,90,\\fscx100\\fscy100)"
    return (f"{{{tags}}}" if tags else "") + " ".join(parts)


WATERMARK_ALIGN = {"tl": 7, "tr": 9, "bl": 1, "br": 3}


def hook_style_line(hs):
    if hs["mode"] == "box":  # BorderStyle 3: the "outline" becomes a solid box of OutlineColour
        border, outline, outline_color, shadow = 3, hs["pad"], hs["box"], 0
    else:
        border, outline, outline_color, shadow = 1, hs["outline"], hs["outline_color"], hs["shadow"]
    return (f"Style: Hook,{hs['font']},{hs['size']},{ass_color(hs['text'])},{ass_color(hs['text'])},"
            f"{ass_color(outline_color)},&H80000000,0,0,0,0,100,100,0,0,{border},{outline},{shadow},"
            f"8,90,90,{hs['margin_v']},1")


def build_ass(words, duration, hook="", captions=True, style=None, watermark="", watermark_pos="tr",
              hook_style=None):
    """ASS subtitle file text for one clip. `words` are already on the clip's own timeline."""
    style = style or CAPTION_STYLES[DEFAULT_CAPTION_STYLE]
    hs = hook_style or resolve_hook({})
    clip_words = caption_words(words, 0.0, duration, style["uppercase"])

    bold = -1 if style["bold"] else 0
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {OUT_W}",
        f"PlayResY: {OUT_H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{style['font']},{style['size']},{ass_color(style['text'])},{ass_color(style['text'])},"
        f"{ass_color(style['outline_color'])},&H80000000,{bold},0,0,0,100,100,0,0,1,"
        f"{style['outline']},{style['shadow']},2,60,60,{style['margin_v']},1",
        hook_style_line(hs),
        f"Style: Mark,Segoe UI Semibold,38,&H33FFFFFF,&H33FFFFFF,&H66000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,2,0,{WATERMARK_ALIGN.get(watermark_pos, 9)},50,50,70,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    hook = clean_word(hook.replace("\n", " "))
    if hook:
        if hs["uppercase"]:
            hook = hook.upper()
        shown = min(duration, hs["duration"]) if hs["duration"] else duration
        tags = f"\\blur{hs['glow']}" if hs["glow"] else ""
        if hs["duration"]:
            tags += "\\fad(120,250)"
        hook = (f"{{{tags}}}" if tags else "") + hook
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(shown)},Hook,,0,0,0,,{hook}")
    watermark = clean_word(watermark.replace("\n", " "))
    if watermark:
        lines.append(f"Dialogue: 2,{ass_time(0)},{ass_time(duration)},Mark,,0,0,0,,{watermark}")

    if captions:
        for item in caption_timeline(clip_words, style):
            chunk, chunk_end = item["words"], item["end"]
            for i, word in enumerate(chunk):
                ev_start = word["s"]
                ev_end = chunk[i + 1]["s"] if i + 1 < len(chunk) else chunk_end
                if ev_end - ev_start < 0.05:
                    continue
                lines.append(f"Dialogue: 0,{ass_time(ev_start)},{ass_time(ev_end)},Caption,,0,0,0,,"
                             f"{caption_event_text(chunk, i, style)}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- rendering

_encoder_cache = {}


def video_encoder():
    """Use the NVIDIA encoder when it works on this PC, otherwise x264."""
    if "args" not in _encoder_cache:
        test = subprocess.run(
            [str(FFMPEG), "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, creationflags=NO_WINDOW,
        )
        if test.returncode == 0:
            _encoder_cache["args"] = ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                                      "-rc", "vbr", "-cq", "20", "-b:v", "0", "-maxrate", "25M",
                                      "-bufsize", "50M", "-profile:v", "high"]
        else:
            _encoder_cache["args"] = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    return _encoder_cache["args"]


FIT_ZOOM = (0.5, 2.5)   # fit: video width from half to 2.5x the frame width
CROP_ZOOM = (1.0, 2.5)  # crop: from the full-height crop to 2.5x closer


def framing(clip, layout):
    """(zoom, x, y) for a clip: how big the video is and where it sits (x, y from 0 to 1)."""
    low, high = FIT_ZOOM if layout == "fit" else CROP_ZOOM
    zoom = min(high, max(low, float(clip.get("frame_zoom") or 1.0)))
    x = min(1.0, max(0.0, float(clip.get("crop_x", 0.5))))
    y = min(1.0, max(0.0, float(clip.get("frame_y", 0.5))))
    return zoom, x, y


def layout_filter(info, layout, crop_x, zoom=1.0, frame_y=0.5):
    """Filter chain that turns one source frame into a 1080x1920 frame.

    crop: a 9:16 window (made smaller by zoom) cut from the source at (crop_x, frame_y).
    fit: the whole video, zoom x frame width, placed at (crop_x, frame_y) over a blurred copy.
    crop_x / frame_y are numbers from 0 to 1, or ffmpeg expressions of t (speaker switches)."""
    width, height = info["width"], info["height"]
    num = lambda v: f"{v:.4f}" if isinstance(v, (int, float)) else v  # noqa: E731
    if width / height <= OUT_W / OUT_H + 0.01:
        return (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2")
    if layout == "fit":
        fg_w = int(round(OUT_W * zoom / 2)) * 2
        return (f"split[la][lb];[la]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
                f"crop={OUT_W}:{OUT_H},boxblur=24:2[lbg];[lb]scale={fg_w}:-2:flags=lanczos[lfg];"
                f"[lbg][lfg]overlay=x='(W-w)*({num(crop_x)})':y='(H-h)*({num(frame_y)})'")
    crop_w = min(height * OUT_W / OUT_H, width) / zoom
    crop_h = height / zoom
    crop_w, crop_h = int(round(crop_w / 2)) * 2, int(round(crop_h / 2)) * 2
    if isinstance(crop_x, (int, float)) and isinstance(frame_y, (int, float)):
        x = int(round((width - crop_w) * crop_x))
        y = int(round((height - crop_h) * frame_y))
        return f"crop={crop_w}:{crop_h}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos"
    return (f"crop={crop_w}:{crop_h}:x='({width}-{crop_w})*({num(crop_x)})':y='({height}-{crop_h})*({num(frame_y)})',"
            f"scale={OUT_W}:{OUT_H}:flags=lanczos")


def position_track(clip, pieces):
    """Speaker switches: [(clip time, x, y)] – where the frame sits from each moment on.

    Keyframes are in source seconds; `pieces` are the parts of the source in play order."""
    def clamp01(v):
        return min(1.0, max(0.0, float(v)))

    keys = sorted((float(k["t"]), clamp01(k["x"]), clamp01(k["y"])) for k in clip.get("keyframes") or [])
    if not keys:
        return None
    base = (clamp01(clip.get("crop_x", 0.5)), clamp01(clip.get("frame_y", 0.5)))

    def at(t):
        pos = base
        for kt, kx, ky in keys:
            if kt > t:
                break
            pos = (kx, ky)
        return pos

    track, offset = [], 0.0
    for a, b, _ in pieces:
        track.append((offset, *at(a)))
        track += [(offset + kt - a, kx, ky) for kt, kx, ky in keys if a < kt < b]
        offset += b - a
    out = []
    for item in track:
        if not out or item[1:] != out[-1][1:]:
            out.append(item)
    return out


def track_expr(track, index):
    """One coordinate of a position track as nested if()s over t."""
    expr = f"{track[-1][index]:.4f}"
    for i in range(len(track) - 1, 0, -1):
        expr = f"if(lt(t,{track[i][0]:.3f}),{track[i - 1][index]:.4f},{expr})"
    return expr


# ---------------------------------------------------------------- edits (cuts, pauses, zoom, speed)

ZOOM_CENTER_Y = 0.35  # punch-ins zoom towards the upper third, where faces usually are


def edit_segments(clip, words, lines, start, end):
    """The parts of the source that stay in the clip, as [(a, b, zoom)] in source seconds."""
    # cuts = words cut in the transcript; drops = parts deleted with the razor on the timeline
    removed = [(float(a), float(b)) for a, b in [*(clip.get("cuts") or []), *(clip.get("drops") or [])]]
    inside = [w for w in words if w["e"] > start and w["s"] < end]
    if clip.get("remove_pauses") and inside:
        gap = float(clip.get("pause_min") or 0.5)
        lead, tail = 0.08, 0.12  # keep a breath around each word so cuts don't clip syllables
        if inside[0]["s"] - start > gap:
            removed.append((start, inside[0]["s"] - lead))
        for prev, nxt in zip(inside, inside[1:]):
            if nxt["s"] - prev["e"] > gap:
                removed.append((prev["e"] + tail, nxt["s"] - lead))
        if end - inside[-1]["e"] > gap:
            removed.append((inside[-1]["e"] + tail, end))

    kept = [(start, end)]
    for a, b in sorted(removed):
        pieces = []
        for s, e in kept:
            if b <= s or a >= e:
                pieces.append((s, e))
                continue
            if a > s:
                pieces.append((s, a))
            if b < e:
                pieces.append((b, e))
        kept = pieces
    kept = [(s, e) for s, e in kept if e - s >= 0.12]
    if not kept:
        raise ClipperError("Everything in this clip has been cut out")

    zoom = float(clip.get("zoom_amount") or 1.15) if clip.get("zoom") else 1.0
    if zoom == 1.0:
        return [(s, e, 1.0) for s, e in kept]
    # punch in on every other piece; long pieces are split where sentences start
    marks = [line["s"] for line in lines]
    pieces = []
    for s, e in kept:
        edges = [s, *[m for m in marks if s + 0.8 < m < e - 0.8], e]
        pieces += list(zip(edges, edges[1:]))
    return [(s, e, zoom if i % 2 else 1.0) for i, (s, e) in enumerate(pieces)]


def teaser_piece(clip, info):
    """The teaser played before the clip, as (a, b) source seconds, or None."""
    a, b = clip.get("intro_start"), clip.get("intro_end")
    if a is None or b is None:
        return None
    a, b = max(0.0, float(a)), float(b)
    if info.get("duration"):
        b = min(b, info["duration"])
    b = min(b, a + 15.0)
    return (a, b) if b - a >= 0.3 else None


# Sound effects for muted words, synthesised by ffmpeg (no downloads, no copyright). "tone" sounds
# last as long as the muted word; "hit" sounds play once where the muted word starts.
SFX_DIR = ROOT / "sfx"
MUTE_SOUNDS = {
    "silence": {"label": "Silence", "kind": "none"},
    "bleep": {"label": "Bleep", "kind": "tone", "freq": 1000},
    "boom": {"label": "Boom", "kind": "hit", "dur": 1.6, "filters": "lowpass=f=500",
             "expr": "0.95*tanh(2.5*sin(2*PI*(48*t+50*(1-exp(-7*t))/7)))*exp(-2.6*t)*(1-exp(-300*t))"},
    "pop": {"label": "Pop", "kind": "hit", "dur": 0.3,
            "expr": "0.9*sin(2*PI*(280*t+700*(1-exp(-45*t))/45))*exp(-22*t)*(1-exp(-400*t))"},
    "boing": {"label": "Boing", "kind": "hit", "dur": 0.9,
              "expr": "0.8*sin(2*PI*(170*t+160*(t-(1-exp(-6*t))/6))-25/13*cos(2*PI*13*t)*exp(-2*t))"
                      "*exp(-3.2*t)*(1-exp(-300*t))"},
    "ding": {"label": "Ding", "kind": "hit", "dur": 1.4,
             "expr": "(0.5*sin(2*PI*1318*t)*exp(-3*t)+0.25*sin(2*PI*2637*t)*exp(-4.5*t)"
                     "+0.15*sin(2*PI*3951*t)*exp(-6*t))*(1-exp(-300*t))"},
    "buzzer": {"label": "Buzzer", "kind": "hit", "dur": 0.7, "filters": "lowpass=f=3000",
               "expr": "0.35*(gt(sin(2*PI*120*t),0)*2-1)*(1-exp(-80*t))*if(lt(t,0.6),1,(0.7-t)/0.1)"},
    "whoosh": {"label": "Whoosh", "kind": "hit", "dur": 0.6, "filters": "highpass=f=300,lowpass=f=4500,volume=1.4",
               "expr": "(2*random(0)-1)*pow(sin(PI*t/0.6),2)*0.9"},
    "custom": {"label": "Custom", "kind": "hit"},
}


def sfx_file(name):
    """Path of a built-in sound effect, made with ffmpeg the first time it's needed."""
    spec = MUTE_SOUNDS.get(name)
    if not spec or "expr" not in spec:
        raise ClipperError(f"Unknown sound effect: {name}")
    SFX_DIR.mkdir(exist_ok=True)
    path = SFX_DIR / f"{name}.wav"
    if not path.exists():
        filters = ",".join(f for f in (spec.get("filters"), "aformat=channel_layouts=stereo") if f)
        run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
             f"aevalsrc='{spec['expr']}':s=48000:d={spec['dur']}", "-af", filters, "-c:a", "pcm_s16le", path])
    return path


def mute_sound_file(clip):
    """The one-shot sound file played on muted words, or None (silence / bleep)."""
    mode = clip.get("mute_mode") or "silence"
    if MUTE_SOUNDS.get(mode, {}).get("kind") != "hit":
        return None
    if mode == "custom":
        path = clip.get("mute_sfx") or ""
        if not path or not Path(path).is_file():
            raise ClipperError("The custom sound for muted words wasn't found - pick it again")
        return Path(path)
    return sfx_file(mode)


def censor(text):
    """'damn,' -> 'd***,' (keeps the first letter and any punctuation at the end)."""
    core = text.rstrip(".,!?;:\"'")
    if not core:
        return text
    return (core[0] + "*" * (len(core) - 1) if len(core) > 1 else "*") + text[len(core):]


def muted(word, mutes):
    mid = (word["s"] + word["e"]) / 2
    return any(a <= mid <= b for a, b in mutes)


def map_ranges(ranges, pieces):
    """Source-time ranges -> ranges on the finished clip's timeline (before speed), piece by piece."""
    out, offset = [], 0.0
    for a, b, _ in pieces:
        for m0, m1 in ranges:
            s, e = max(m0, a), min(m1, b)
            if e > s:
                out.append((offset + s - a, offset + e - a))
        offset += b - a
    return out


def map_words(words, pieces, speed=1.0):
    """Words placed on the finished clip's timeline, piece by piece in play order.

    Cut-out words are dropped; words in a teaser show up twice (teaser, then the clip)."""
    if not pieces:
        return []
    low, high = min(a for a, _, _ in pieces), max(b for _, b, _ in pieces)
    nearby = [w for w in words if w["e"] > low and w["s"] < high]
    out, offset = [], 0.0
    for a, b, _ in pieces:
        for w in nearby:
            if a <= (w["s"] + w["e"]) / 2 <= b:  # whisper gives short words like "I" zero length: keep them
                s = (offset + max(w["s"], a) - a) / speed
                e = (offset + min(w["e"], b) - a) / speed
                out.append({"w": w["w"], "s": s, "e": max(s, e)})
        offset += b - a
    return out


LOUDNESS = "I=-14:TP=-1.5:LRA=11"  # what TikTok / Reels / Shorts normalise to


def cut_filters(rel):
    """Video and audio filters that keep only the [(a, b, zoom)] pieces (times from clip start)."""
    if len(rel) == 1:
        a, b, _ = rel[0]
        return (f"trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS",
                f"atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS")
    keep = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b, _ in rel)
    return f"select='{keep}',setpts=N/FRAME_RATE/TB", f"aselect='{keep}',asetpts=N/SR/TB"


def voice_chain(acut, speed):
    return f"{acut}," + (f"atempo={speed}," if speed != 1.0 else "")


VOICE_COMPRESSOR = "acompressor=threshold=0.089:ratio=3.5:attack=5:release=120"
TARGET_LUFS = -14.0


def measure_loudness(video, start, end, segments, speed):
    """Return the audio filter that brings the clip's speech to -14 LUFS (or None).

    Speech is compressed a little, then gained and peak-limited. The limiter eats some
    loudness, so the result is measured once more and the gain corrected."""
    _, acut = cut_filters([(a - start, b - start, z) for a, b, z in segments])

    def integrated(chain):
        proc = subprocess.run(
            [str(FFMPEG), "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
             "-i", str(video), "-vn", "-af", f"{voice_chain(acut, speed)}{chain}ebur128=framelog=quiet",
             "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        )
        found = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", proc.stderr, re.M)
        return float(found[-1]) if proc.returncode == 0 and found else None

    def chain(gain):
        return f"{VOICE_COMPRESSOR},volume={gain:.2f}dB,alimiter=limit=0.84:attack=3:release=60:level=disabled,"

    first = integrated(f"{VOICE_COMPRESSOR},")
    if first is None or first < -60:  # unreadable or silent: leave it alone
        return None
    gain = min(24.0, TARGET_LUFS - first)
    second = integrated(chain(gain))
    if second is not None:
        gain = min(24.0, gain + (TARGET_LUFS - second))
    return chain(gain).rstrip(",")


EMOJI_SIZE = 150


def edit_graph(info, clip, segments, start, speed, duration, ass_rel, music, loudness=None, teaser=None,
               inputs=None, popups=None, emojis=None):
    """The -filter_complex graph for a clip: teaser, cut, frame, zoom, speed, pop-ups, emojis,
    captions, bar, audio.

    Input 0 is the clip range, input 1 the teaser range (when there is one); `inputs` gives the
    input numbers of the music and the muted-word sound effect; each pop-up and emoji carries its own."""
    inputs = inputs or {}
    rel = [(a - start, b - start, z) for a, b, z in segments]
    graph = []
    vcut, acut = cut_filters(rel)
    has_audio = info.get("has_audio", True)
    if teaser:
        graph.append(f"[1:v]setpts=PTS-STARTPTS[tv];[0:v]{vcut}[mv]")
        if has_audio:
            graph.append(f"[1:a]asetpts=PTS-STARTPTS[ta];[0:a]{acut}[ma];[tv][ta][mv][ma]concat=n=2:v=1:a=1[cv][ca]")
        else:
            graph.append("[tv][mv]concat=n=2:v=1:a=0[cv]")
    else:
        graph.append(f"[0:v]{vcut}[cv]")
        if has_audio:
            graph.append(f"[0:a]{acut}[ca]")

    layout = clip.get("layout", "crop")
    zoom, frame_x, frame_y = framing(clip, layout)
    track = position_track(clip, ([(teaser[0], teaser[1], 1.0)] if teaser else []) + segments)
    if track:  # speaker switches: the crop jumps to each keyframe's position at its moment
        frame_x, frame_y = track_expr(track, 1), track_expr(track, 2)
    graph.append(f"[cv]{layout_filter(info, layout, frame_x, zoom, frame_y)}[vbase]")
    current = "vbase"
    pieces = ([(0.0, teaser[1] - teaser[0], 1.0)] if teaser else []) + rel
    zoomed, offset = [], 0.0
    for a, b, z in pieces:
        if z != 1.0:
            zoomed.append((offset, offset + b - a, z))
        offset += b - a
    if zoomed:
        z = zoomed[0][2]
        when = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e, _ in zoomed)
        graph.append(f"[vbase]split[vz1][vz2];[vz2]scale={round(OUT_W * z / 2) * 2}:{round(OUT_H * z / 2) * 2},"
                     f"crop={OUT_W}:{OUT_H}:(iw-{OUT_W})/2:(ih-{OUT_H})*{ZOOM_CENTER_Y}[vzoom];"
                     f"[vz1][vzoom]overlay=enable='{when}'[vzoomed]")
        current = "vzoomed"
    if speed != 1.0:
        graph.append(f"[{current}]setpts=PTS/{speed}[vspeed]")
        current = "vspeed"
    # pop-ups (pictures / GIFs / videos), then keyword emojis – both sit under the captions
    for n, pop in enumerate(popups or []):
        width = int(round(OUT_W * pop["size"] / 2)) * 2
        y = {"top": "330", "bottom": "H-h-700"}.get(pop["pos"], "(H-h)/2")
        fade_out = max(0.0, pop["dur"] - 0.15)
        # a GIF's frames at 1/100 s (its delays' unit): the overlay shows an input's last frame for one output frame
        # only, so a long last frame (a play-once GIF's end, the frame its Seconds cut) would vanish early
        frames = f"fps=100,trim=duration={pop['dur']:.3f}," if pop.get("gif") else ""
        graph.append(f"[{pop['input']}:v]{frames}scale={width}:-2,format=rgba,fade=t=in:st=0:d=0.15:alpha=1,"
                     f"fade=t=out:st={fade_out:.3f}:d=0.15:alpha=1,setpts=PTS-STARTPTS+{pop['start']:.3f}/TB[pop{n}];"
                     f"[{current}][pop{n}]overlay=x=(W-w)/2:y={y}:eof_action=pass[vpop{n}]")
        current = f"vpop{n}"
    for n, emo in enumerate(emojis or []):
        when = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in emo["times"])
        graph.append(f"[{emo['input']}:v]scale={EMOJI_SIZE}:{EMOJI_SIZE},format=rgba[emo{n}];"
                     f"[{current}][emo{n}]overlay=x=(W-w)/2:y={emo['y']}:enable='{when}'[vemo{n}]")
        current = f"vemo{n}"
    tail = f"setsar=1,ass={ass_rel}"
    if teaser and clip.get("intro_flash", True):
        cut_at = (teaser[1] - teaser[0]) / speed  # a quick white flash where the teaser ends
        tail += (f",drawbox=x=0:y=0:w=iw:h=ih:color=white@0.85:t=fill:"
                 f"enable='between(t,{max(0.0, cut_at - 0.04):.3f},{cut_at + 0.1:.3f})'")
    if clip.get("progress"):
        # a bar the width of the frame slides in from the left as the clip plays
        color = clip.get("progress_color") or "#00E5FF"
        graph.append(f"[{current}]{tail}[vcap]")
        graph.append(f"color=c=0x{color[1:]}:s={OUT_W}x16:d={duration + 1:.3f},format=yuv420p[bar]")
        graph.append(f"[vcap][bar]overlay=x='-W+W*t/{duration:.3f}':y=H-16:eof_action=pass[vout]")
    else:
        graph.append(f"[{current}]{tail}[vout]")

    fade_out = max(0.0, duration - 0.08)
    mutes = map_ranges([(float(a), float(b)) for a, b in clip.get("mutes") or []],
                       ([(teaser[0], teaser[1], 1.0)] if teaser else []) + segments)
    sound = MUTE_SOUNDS.get(clip.get("mute_mode") or "silence", MUTE_SOUNDS["silence"])
    sfx_volume = min(1.5, max(0.0, float(clip.get("mute_sfx_volume", 0.8))))
    if has_audio:
        source = "[ca]"
        if mutes:  # silence the muted words; a "tone" sound (bleep) plays over them for their whole length
            when = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in mutes)
            graph.append(f"[ca]volume=0:enable='{when}'[cmuted]")
            source = "[cmuted]"
            if sound["kind"] == "tone":  # the effect volume scales the bleep too (0.8 = the old fixed level)
                level = 0.5 * sfx_volume / 0.8
                graph.append(f"sine=frequency={sound['freq']}:sample_rate=48000,volume='if({when},{level:.3f},0)':eval=frame,"
                             f"atrim=0:{duration * speed + 1:.3f},aformat=channel_layouts=stereo[beep];"
                             "[cmuted]aformat=channel_layouts=stereo[cst];"
                             "[cst][beep]amix=inputs=2:duration=first:normalize=0[cbleep]")
                source = "[cbleep]"
        norm = loudness or f"loudnorm={LOUDNESS}"
        tempo = f"atempo={speed}," if speed != 1.0 else ""
        voice = f"{source}{tempo}{norm},aresample=48000,afade=t=in:d=0.05"
    else:
        voice = f"anullsrc=r=48000:cl=stereo,atrim=0:{duration:.3f}"
    if mutes and inputs.get("sfx") is not None:
        # "hit" sounds (boom, pop, ...) play once per muted range in each pass (the teaser, then the
        # clip), where its first kept part starts, mixed in after the loudness step so every effect
        # lands at the same level. Like the preview: a range a cut splits gets one hit, a range that
        # is cut out none, and two ranges a cut makes touch one each.
        ranges = []
        for a, b in sorted((float(a), float(b)) for a, b in clip.get("mutes") or []):
            if ranges and a <= ranges[-1][1] + 0.001:  # overlapping ones are one range (the editor merges them)
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], b))
            else:
                ranges.append((a, b))
        hits, offset = [], 0.0
        for part in ([[(teaser[0], teaser[1], 1.0)]] if teaser else []) + [segments]:
            for r in ranges:
                kept = map_ranges([r], part)
                if kept:
                    hits.append(offset + kept[0][0])
            offset += sum(b - a for a, b, _ in part)
        hits.sort()
        n = len(hits)
        graph.append(f"{voice},aformat=channel_layouts=stereo[vlev]")
        split = f",asplit={n}" + "".join(f"[sx{i}]" for i in range(n)) if n > 1 else "[sx0]"
        graph.append(f"[{inputs['sfx']}:a]aresample=48000,aformat=channel_layouts=stereo,volume={sfx_volume:.2f}{split}")
        for i, a in enumerate(hits):
            graph.append(f"[sx{i}]adelay=delays={int(a / speed * 1000)}:all=1[sd{i}]")
        voice = "[vlev]" + "".join(f"[sd{i}]" for i in range(n)) + f"amix=inputs={n + 1}:duration=first:normalize=0"
    if music:
        volume = min(1.0, max(0.0, float(clip.get("music_volume", 0.15))))
        graph.append(f"{voice},asplit[vo1][vo2]")
        graph.append(f"[{inputs['music']}:a]volume={volume:.3f},afade=t=in:d=0.8[mus]")
        graph.append("[mus][vo2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=400[duck]")
        graph.append(f"[vo1][duck]amix=inputs=2:duration=first:normalize=0,"
                     f"afade=t=out:st={max(0.0, duration - 0.6):.3f}:d=0.6[aout]")
    else:
        graph.append(f"{voice},afade=t=out:st={fade_out:.3f}:d=0.08[aout]")
    return ";".join(graph)


def load_transcript(project):
    """(words, lines) of a project, or empty lists before transcribing."""
    words_path, lines_path = Path(project) / "words.json", Path(project) / "transcript.json"
    words = json.loads(words_path.read_text(encoding="utf-8")) if words_path.exists() else []
    lines = json.loads(lines_path.read_text(encoding="utf-8")) if lines_path.exists() else []
    return words, lines


def plan_clip(clip, info, words, lines):
    """What a clip is made of: start, end, kept segments, teaser, pieces in play order, speed and
    final duration. Used for rendering and for the campaign checks."""
    start, end = parse_time(clip["start"]), parse_time(clip["end"])
    if end <= start:
        raise ClipperError(f"Clip {clip.get('name')}: end must be after start")
    if info["duration"] and start >= info["duration"]:
        raise ClipperError(f"Clip {clip.get('name')}: starts after the video ends")
    end = min(end, info["duration"] or end)
    segments = edit_segments(clip, words, lines, start, end)
    teaser = teaser_piece(clip, info)
    pieces = ([(teaser[0], teaser[1], 1.0)] if teaser else []) + segments
    speed = min(2.0, max(0.5, float(clip.get("speed") or 1.0)))
    duration = sum(b - a for a, b, _ in pieces) / speed
    return {"start": start, "end": end, "segments": segments, "teaser": teaser, "pieces": pieces,
            "speed": speed, "duration": duration}


VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
POPUP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"} | VIDEO_SUFFIXES


def popup_occurrences(clip, pieces, speed):
    """Each pop-up placed on the finished clip: [(popup, start)] (a teaser can show one twice)."""
    out = []
    for pop in clip.get("popups") or []:
        at, offset = float(pop["at"]), 0.0
        for a, b, _ in pieces:
            if a <= at < b:
                out.append((pop, (offset + at - a) / speed))
            offset += b - a
    return out


def is_animated_webp(path):
    """An animated WebP (a VP8X header with the animation flag): ffmpeg has no decoder for those."""
    try:
        with open(path, "rb") as f:
            head = f.read(21)
    except OSError:
        return False
    return len(head) == 21 and head[:4] == b"RIFF" and head[8:16] == b"WEBPVP8X" and bool(head[20] & 0x02)


def check_popup_picture(path):
    """Raise ClipperError unless ffmpeg can decode a pop-up picture or GIF. They are looped (-loop 1 /
    -ignore_loop 0), and a file ffmpeg can't decode would keep the render spinning forever."""
    path = Path(path)
    if is_animated_webp(path):
        raise ClipperError(f"Animated WebP pop-ups aren't supported - use a GIF or a video instead: {path.name}")
    try:
        out = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "null", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL, timeout=30, creationflags=NO_WINDOW)
        ok = out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    if not ok:
        raise ClipperError(f"Can't read the pop-up picture (ffmpeg can't decode it): {path.name}")


def gif_timing(path):
    """How the render plays a GIF pop-up, read the way ffmpeg's gif demuxer does with -ignore_loop 0:
    {"delays": seconds per frame, "plays": passes (0 = forever)}, or None for a file it can't walk.
    A delay of 0 counts as 0.1 s, a frame without its own delay keeps the one before; the NETSCAPE loop
    count is the number of passes (none = once, 0 = forever). A single picture is held (popup_input)."""
    try:
        data = Path(path).read_bytes()
        if data[:6] not in (b"GIF87a", b"GIF89a"):
            return None
        pos = 13 + (3 << ((data[10] & 7) + 1) if data[10] & 0x80 else 0)
        delays, plays, delay = [], 1, 10
        while pos < len(data) and data[pos] != 0x3B:
            if data[pos] == 0x21:
                label, pos, first, netscape = data[pos + 1], pos + 2, True, False
                while data[pos]:
                    block = data[pos + 1:pos + 1 + data[pos]]
                    if label == 0xF9 and first and len(block) >= 3:
                        delay = int.from_bytes(block[1:3], "little") or 10
                    elif label == 0xFF and first:
                        netscape = block == b"NETSCAPE2.0"
                    elif netscape and len(block) >= 3 and block[0] == 1:
                        plays = int.from_bytes(block[1:3], "little")
                    pos += 1 + data[pos]
                    first = False
                pos += 1
            elif data[pos] == 0x2C:
                flags = data[pos + 9]
                pos += 10 + (3 << ((flags & 7) + 1) if flags & 0x80 else 0) + 1
                while data[pos]:
                    pos += 1 + data[pos]
                pos += 1
                delays.append(delay / 100)
            else:
                return None
        return {"delays": delays, "plays": plays if len(delays) > 1 else 0} if delays else None
    except (OSError, IndexError):
        return None


def popup_input(pop):
    """ffmpeg input arguments for a pop-up file (a picture is held, a GIF plays its own loop count – a
    one-frame GIF is held like a picture – a video plays)."""
    path = Path(pop["path"])
    if not path.is_file():
        raise ClipperError(f"Pop-up file not found: {path}")
    dur = f"{float(pop.get('dur') or 1.5):.3f}"
    suffix = path.suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        check_popup_picture(path)
    if suffix == ".gif":
        timing = gif_timing(path)
        if timing and len(timing["delays"]) == 1:
            # the gif demuxer gives one frame per delay (a long delay would show for one frame only): read it as a picture
            return ["-f", "image2", "-c:v", "gif", "-loop", "1", "-t", dur, "-i", str(path)]
        return ["-ignore_loop", "0", "-t", dur, "-i", str(path)]
    if suffix in VIDEO_SUFFIXES:
        return ["-t", dur, "-i", str(path)]
    return ["-loop", "1", "-t", dur, "-i", str(path)]


def render_clip(video, clip, on_progress=None, on_log=None):
    """Render one clip dict to projects/<name>/out/<clip name>.mp4 and return the path."""
    check_tools()
    project = project_dir(video)
    info = probe(video)
    words, lines = load_transcript(project)
    plan = plan_clip(clip, info, words, lines)
    start, end, segments, teaser, pieces, speed, duration = (
        plan[k] for k in ("start", "end", "segments", "teaser", "pieces", "speed", "duration"))

    name = safe_name(clip.get("name") or f"clip_{fmt_time(start)}")
    out_dir = project / "out"
    out_dir.mkdir(exist_ok=True)
    music = clip.get("music") or ""
    if music and not Path(music).is_file():
        raise ClipperError(f"Music file not found: {music}")

    caption_source = words
    mutes = [(float(a), float(b)) for a, b in clip.get("mutes") or []]
    if mutes and clip.get("mute_captions", True):
        caption_source = [{**w, "w": censor(w["w"])} if muted(w, mutes) else w for w in words]

    style = resolve_style(clip)
    show_captions = bool(clip.get("captions", True)) and bool(words)
    clip_words = map_words(caption_source, pieces, speed)
    ass_path = out_dir / f"{name}.ass"
    ass_path.write_text(
        build_ass(clip_words, duration, hook=clip.get("hook", ""),
                  captions=show_captions, style=style,
                  watermark=clip.get("watermark", ""), watermark_pos=clip.get("watermark_pos", "tr"),
                  hook_style=resolve_hook(clip)),
        encoding="utf-8",
    )
    # ffmpeg's filter syntax chokes on Windows drive letters, so the subtitle file is
    # passed as a path relative to ROOT and ffmpeg runs from there.
    ass_rel = ass_path.relative_to(ROOT).as_posix()
    if on_log:
        on_log(f"Measuring loudness for {name}...")
    loudness = measure_loudness(video, start, end, segments, speed) if info.get("has_audio", True) else None
    sfx = mute_sound_file(clip) if clip.get("mutes") else None
    # inputs: 0 = clip range, then the teaser range, the music and the muted-word sound when used
    extra = [name_ for name_, used in (("teaser", teaser), ("music", music), ("sfx", sfx)) if used]
    inputs = {key: 1 + extra.index(key) for key in extra}
    extra_args = []
    next_input = 1 + len(extra)
    popups = []
    for pop, at in popup_occurrences(clip, pieces, speed):
        extra_args += popup_input(pop)
        popups.append({"input": next_input, "start": at, "dur": float(pop.get("dur") or 1.5),
                       "pos": pop.get("pos", "center"), "size": min(1.0, max(0.2, float(pop.get("size") or 0.8))),
                       "gif": Path(pop["path"]).suffix.lower() == ".gif"})
        next_input += 1
    emojis = []
    if style["emojis"] and show_captions:
        y = int(OUT_H - style["margin_v"] - style["size"] * 1.25 - EMOJI_SIZE - 10)
        grouped = {}
        for emoji, a, b in emoji_events(clip_words, duration, style):
            grouped.setdefault(emoji, []).append((a, b))
        for emoji, times in grouped.items():
            png = emoji_png(emoji)
            if not png.exists():  # pictures are made by the app window; skip ones it hasn't drawn yet
                continue
            extra_args += ["-loop", "1", "-i", str(png)]
            emojis.append({"input": next_input, "times": times, "y": y})
            next_input += 1
    graph = edit_graph(info, clip, segments, start, speed, duration, ass_rel, music, loudness, teaser, inputs,
                       popups, emojis)
    out_path = out_dir / f"{name}.mp4"
    fps_args = ["-r", "60"] if info["fps"] > 60.5 else []
    teaser_args = ["-ss", f"{teaser[0]:.3f}", "-t", f"{teaser[1] - teaser[0]:.3f}", "-i", video] if teaser else []
    music_args = ["-stream_loop", "-1", "-i", music] if music else []
    music_args += ["-i", sfx] if sfx else []
    music_args += extra_args

    def progress(line):
        match = re.search(r"out_time_us=(\d+)", line)
        if match and on_progress:
            on_progress(min(100, int(int(match.group(1)) / 1e6 / duration * 100)))

    if on_log:
        on_log(f"Rendering {name} ({fmt_time(start)} - {fmt_time(end)})...")
    run([FFMPEG, "-y", "-v", "error", "-progress", "pipe:1", "-nostats",
         "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", video, *teaser_args, *music_args,
         "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
         *fps_args, *video_encoder(), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{duration:.3f}",
         "-movflags", "+faststart", out_path],
        cwd=ROOT, on_line=progress)
    ass_path.unlink(missing_ok=True)

    post = clip.get("post_caption", "").strip()
    if post:
        notes = out_dir / "post_captions.txt"
        existing = notes.read_text(encoding="utf-8") if notes.exists() else ""
        entry = f"== {name}.mp4 ==\n{post}\n\n"
        if entry not in existing:
            notes.write_text(existing + entry, encoding="utf-8")
    if on_progress:
        on_progress(100)
    return out_path


# ---------------------------------------------------------------- command line

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Turn long videos into vertical captioned clips.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("transcribe", help="make a transcript with word timings")
    p.add_argument("video")
    p.add_argument("--lang", default="en", help="spoken language code, or 'auto' (default en)")

    p = sub.add_parser("search", help="find words in the transcript")
    p.add_argument("video")
    p.add_argument("query")

    p = sub.add_parser("frame", help="save a still image from the video")
    p.add_argument("video")
    p.add_argument("--at", required=True)
    p.add_argument("--out")

    p = sub.add_parser("cut", help="render one clip")
    p.add_argument("video")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--name")
    p.add_argument("--layout", choices=["crop", "fit"], default="crop")
    p.add_argument("--crop-x", type=float, default=0.5, help="0 = left edge, 0.5 = centre, 1 = right edge")
    p.add_argument("--hook", default="")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--style", choices=sorted(CAPTION_STYLES), default=DEFAULT_CAPTION_STYLE,
                   help="caption look")
    p.add_argument("--color", help="highlight colour, e.g. #39FF14")

    p = sub.add_parser("render", help="render every clip listed in the project's clips.json")
    p.add_argument("video")

    args = parser.parse_args(argv)
    video = Path(args.video)
    if not video.exists():
        parser.error(f"file not found: {video}")

    def show_progress(pct):
        print(f"\r  {pct:3d}%", end="", flush=True)

    try:
        if args.command == "transcribe":
            project = transcribe(video, args.lang, on_progress=show_progress, on_log=print)
            print(f"\nTranscript saved: {project / 'transcript.txt'}")
        elif args.command == "search":
            for line in search(video, args.query):
                print(f"[{fmt_time(line['s'])} - {fmt_time(line['e'])}] {line['text']}")
        elif args.command == "frame":
            out = Path(args.out) if args.out else project_dir(video) / f"frame_{safe_name(args.at)}.png"
            print(extract_frame(video, args.at, out))
        elif args.command == "cut":
            clip = {"name": args.name, "start": args.start, "end": args.end, "layout": args.layout,
                    "crop_x": args.crop_x, "hook": args.hook, "captions": not args.no_captions,
                    "caption_style": args.style, "caption_color": args.color}
            out = render_clip(video, clip, on_progress=show_progress, on_log=print)
            print(f"\nSaved: {out}")
        elif args.command == "render":
            clips = load_clips(project_dir(video))
            if not clips:
                raise ClipperError("clips.json has no clips")
            for clip in clips:
                out = render_clip(video, clip, on_progress=show_progress, on_log=print)
                print(f"\n  saved {out.name}")
    except ClipperError as err:
        print(f"\nError: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
