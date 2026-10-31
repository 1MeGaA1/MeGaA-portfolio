# MeGaA Clipper

Turns a long video (podcast, stream, interview) into short **vertical 9:16 clips** with
big word-by-word captions, ready for TikTok, Reels and Shorts. Everything runs locally:
speech-to-text on the GPU with whisper.cpp, rendering with ffmpeg (NVENC).

## What it does

- **Transcribe** a video with word-level timestamps (whisper.cpp, GPU with CPU fallback).
- **Pick moments** from the transcript (click / shift-click), trim on a waveform that snaps
  to word edges, or let it suggest viral moments (offline heuristics, or Claude via the API).
- **Style captions**: 8 caption presets, 7 hook styles, keyword colours and emojis, pop-ups.
- **Edit**: remove pauses, zoom punch-ins, speed, razor cuts, keyframed framing, teaser intro,
  progress bar, music ducking, watermark, mute/bleep ranges with synthesized sound effects.
- **Render** to -14 LUFS (two-pass loudness) with a live preview that mirrors the engine.
- **Track** campaigns, posted clips and earnings, and export ready-to-post packs.

## Two front-ends, one engine

| File | What it is |
|---|---|
| `clipper.py` | The engine and CLI. Pure Python standard library: drives ffmpeg and whisper.cpp. |
| `clipper_app.py` + `ui/` | Web UI: a stdlib HTTP server plus HTML/CSS/JS, opened as a Chrome app window. |
| `clipper_qml.py` + `qml/` | Native Qt Quick (PySide6) edition drawn on the GPU, with undo/redo and the razor tool. |
| `library.py` | Campaigns, tracker, export packs and the optional Claude "AI moments" call (raw `urllib`). |

## Setup

The engine needs these binaries in `tools/` (not committed, they are ~2 GB):

```
tools/ffmpeg/bin/ffmpeg.exe, ffprobe.exe      # BtbN ffmpeg build
tools/whisper/whisper-cli.exe                  # whisper.cpp CUDA build (+ cuBLAS DLLs)
tools/whisper-cpu/whisper-cli.exe              # whisper.cpp CPU build (fallback)
tools/models/ggml-large-v3-turbo-q5_0.bin      # whisper model
```

Then:

```bash
python clipper_app.py        # web UI
pip install PySide6 && python clipper_qml.py   # QML edition
```

The AI moment picker is optional: paste an Anthropic API key in Settings.

See [HOW-TO.md](HOW-TO.md) for the full user guide.
