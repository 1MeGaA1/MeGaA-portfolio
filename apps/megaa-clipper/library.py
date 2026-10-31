"""MeGaA Clipper library: Whop campaigns and their rules, the earnings tracker, export packs and
AI-picked moments. Pure standard library; everything is saved as JSON in ./data."""

import json
import re
import shutil
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

import clipper
from clipper import ClipperError

DATA = clipper.ROOT / "data"
EXPORTS = clipper.ROOT / "exports"
CAMPAIGNS = DATA / "campaigns.json"
TRACKER = DATA / "tracker.json"
SETTINGS = DATA / "settings.json"


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path, data):
    DATA.mkdir(exist_ok=True)
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _num(value, default, low, high):
    try:
        return min(high, max(low, float(value)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- campaigns

def campaigns():
    return _load(CAMPAIGNS, [])


def campaign(campaign_id):
    return next((c for c in campaigns() if c["id"] == campaign_id), None) if campaign_id else None


def save_campaign(data):
    """Create or update a campaign. Lengths of 0 mean "no limit"."""
    name = str(data.get("name") or "").strip()
    if not name:
        raise ClipperError("Give the campaign a name")
    item = {
        "id": data.get("id") or uuid.uuid4().hex[:8],
        "name": name[:60],
        "cpm": round(_num(data.get("cpm"), 1.0, 0, 1000), 2),
        "min_len": round(_num(data.get("min_len"), 0, 0, 600), 1),
        "max_len": round(_num(data.get("max_len"), 0, 0, 600), 1),
        "tags": str(data.get("tags") or "").strip()[:200],
        "watermark": str(data.get("watermark") or "").strip()[:60],
        "no_hook": bool(data.get("no_hook")),
        "need_captions": bool(data.get("need_captions")),
        "max_speed": round(_num(data.get("max_speed"), 0, 0, 2), 2),
        "notes": str(data.get("notes") or "").strip()[:1000],
    }
    items = [c for c in campaigns() if c["id"] != item["id"]]
    items.append(item)
    items.sort(key=lambda c: c["name"].lower())
    _save(CAMPAIGNS, items)
    return item


def delete_campaign(campaign_id):
    _save(CAMPAIGNS, [c for c in campaigns() if c["id"] != campaign_id])


def required_tags(camp):
    return [t for t in re.split(r"[\s,]+", camp.get("tags") or "") if t]


def check_clip(clip, camp, duration):
    """A clip against a campaign's rules: [{"level": "error"|"warn", "text": ...}]."""
    if not camp:
        return []
    problems = []
    if camp["min_len"] and duration < camp["min_len"] - 0.05:
        problems.append({"level": "error", "text": f"Too short: {duration:.1f}s – this campaign needs {camp['min_len']:g}s+"})
    if camp["max_len"] and duration > camp["max_len"] + 0.05:
        problems.append({"level": "error", "text": f"Too long: {duration:.1f}s – this campaign allows {camp['max_len']:g}s max"})
    post = (clip.get("post_caption") or "").lower()
    missing = [t for t in required_tags(camp) if t.lower() not in post]
    if missing:
        problems.append({"level": "warn", "text": f"Post caption is missing {' '.join(missing)}"})
    if camp["watermark"] and camp["watermark"].lower() not in (clip.get("watermark") or "").lower():
        problems.append({"level": "error", "text": f"Watermark must include “{camp['watermark']}”"})
    if camp["no_hook"] and (clip.get("hook") or "").strip():
        problems.append({"level": "error", "text": "This campaign doesn't allow text on top (hook)"})
    if camp["need_captions"] and clip.get("captions") is False:
        problems.append({"level": "error", "text": "This campaign needs captions"})
    if camp["max_speed"] and float(clip.get("speed") or 1) > camp["max_speed"] + 0.001:
        problems.append({"level": "error", "text": f"Speed {clip.get('speed')}× is above the allowed {camp['max_speed']:g}×"})
    return problems


# ---------------------------------------------------------------- earnings tracker

def tracker():
    return _load(TRACKER, [])


TRACK_FIELDS = ("campaign", "project", "clip", "platform", "url", "posted", "views", "style", "layout",
                "length", "hook", "teaser", "earned")


def save_entry(data):
    item = {key: data.get(key) for key in TRACK_FIELDS}
    item["id"] = data.get("id") or uuid.uuid4().hex[:10]
    item["views"] = int(_num(item.get("views"), 0, 0, 1e12))
    item["earned"] = round(_num(item.get("earned"), 0, 0, 1e9), 2) if item.get("earned") not in (None, "") else None
    item["posted"] = str(item.get("posted") or time.strftime("%Y-%m-%d"))[:10]
    item["platform"] = str(item.get("platform") or "TikTok")[:20]
    item["url"] = str(item.get("url") or "").strip()[:500]
    items = tracker()
    at = next((i for i, e in enumerate(items) if e["id"] == item["id"]), None)
    if at is None:
        items.insert(0, item)   # a new post goes on top; an update (new views) keeps its place
    else:
        items[at] = item
    _save(TRACKER, items)
    return item


def delete_entry(entry_id):
    _save(TRACKER, [e for e in tracker() if e["id"] != entry_id])


# ---------------------------------------------------------------- export pack

def _slug(text, limit=40):
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "clip"


def export_pack(project, clips, camp=None, make_zip=False):
    """Copy every rendered clip into exports/<project>_<date>/ with clear names, plus captions.txt
    holding each post caption (with the campaign's required tags added). Returns the folder or zip."""
    project = Path(project)
    ready = [c for c in clips if (project / "out" / f"{c['name']}.mp4").exists()]
    if not ready:
        raise ClipperError("No rendered clips to export – render them first")
    base = EXPORTS / f"{project.name}_{time.strftime('%Y-%m-%d_%H%M')}"
    folder, n = base, 2
    while folder.exists() or folder.with_suffix(".zip").exists():   # two exports in one minute: _2, _3…
        folder = base.with_name(f"{base.name}_{n}")
        n += 1
    folder.mkdir(parents=True)
    tags = required_tags(camp) if camp else []
    notes = []
    for n, clip in enumerate(ready, 1):
        title = _slug(clip.get("hook") or clip.get("post_caption") or clip["name"])
        target = folder / f"{n:02d}_{title}.mp4"
        shutil.copy2(project / "out" / f"{clip['name']}.mp4", target)
        caption = (clip.get("post_caption") or "").strip()
        extra = [t for t in tags if t.lower() not in caption.lower()]
        caption = " ".join(filter(None, [caption, " ".join(extra)]))
        notes.append(f"== {target.name} ==\n{caption or '(no post caption)'}\n")
    header = f"Campaign: {camp['name']}\n\n" if camp else ""
    (folder / "captions.txt").write_text(header + "\n".join(notes), encoding="utf-8")
    if not make_zip:
        return folder
    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:  # videos don't compress further
        for item in folder.iterdir():
            zf.write(item, item.name)
    shutil.rmtree(folder)
    return archive


# ---------------------------------------------------------------- settings + AI moments

def settings():
    return _load(SETTINGS, {})


def save_settings(values):
    current = settings()
    current.update({k: v for k, v in values.items() if k in ("api_key",)})
    _save(SETTINGS, current)


API_URL = "https://api.anthropic.com/v1/messages"
AI_MODEL = "claude-opus-5-5"
MOMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "clip start, seconds"},
                    "end": {"type": "number", "description": "clip end, seconds"},
                    "score": {"type": "integer", "description": "0-100 viral potential"},
                    "hook": {"type": "string", "description": "on-screen hook title, max 8 words"},
                    "post_caption": {"type": "string", "description": "TikTok caption with 3-5 hashtags"},
                    "why": {"type": "string", "description": "one short reason"},
                },
                "required": ["start", "end", "score", "hook", "post_caption", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["moments"],
    "additionalProperties": False,
}


def ai_moments(lines, count=10, min_len=20.0, max_len=60.0, api_key=None):
    """Ask Claude for the best clips. Plain HTTPS from the standard library (no SDK, no pip)."""
    key = api_key or settings().get("api_key")
    if not key:
        raise ClipperError("Add your Anthropic API key in Settings to use AI picks")
    transcript = "\n".join(f"[{l['s']:.1f}-{l['e']:.1f}] {l['text']}" for l in lines)
    prompt = (
        f"You are a short-form video editor picking clips for TikTok / Reels / Shorts from a long video.\n"
        f"Pick the {count} best moments. Each clip must be a complete thought: start where a sentence "
        f"starts, end where a sentence ends, and last {min_len:g}-{max_len:g} seconds. Use the timestamps "
        f"in the transcript. Prefer moments with a strong first line that stops the scroll, a clear payoff, "
        f"emotion, surprise, money or numbers, and controversy. Clips must not overlap. Give each a hook "
        f"title (max 8 words, no emojis) and a post caption.\n\nTranscript:\n{transcript}"
    )
    body = {
        "model": AI_MODEL,
        "max_tokens": 16000,
        "fallbacks": "default",
        "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": MOMENT_SCHEMA}},
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2026-10-21",
        "anthropic-beta": "server-side-fallback-2026-07-01",
    })
    try:
        with urllib.request.urlopen(request, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        if err.code == 401:
            raise ClipperError("The API key was rejected – check it in Settings") from None
        if err.code == 429:
            raise ClipperError("Rate limited by the API – wait a minute and try again") from None
        raise ClipperError(f"AI request failed ({err.code}): {detail}") from None
    except (urllib.error.URLError, TimeoutError) as err:
        raise ClipperError(f"Couldn't reach the AI service: {err}") from None
    if data.get("stop_reason") == "refusal":
        raise ClipperError("The AI declined this transcript – use the offline picks instead")
    text = next((b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"), "")
    try:
        moments = json.loads(text)["moments"]
    except (ValueError, KeyError):
        raise ClipperError("The AI answer couldn't be read – try again") from None
    end_of_video = lines[-1]["e"] + 1 if lines else 0
    out = []
    for m in moments:
        start, end = max(0.0, float(m["start"])), min(end_of_video, float(m["end"]))
        if end - start >= 3:
            out.append({"start": round(start, 2), "end": round(end, 2), "score": int(m["score"]),
                        "hook": m["hook"].strip(), "post_caption": m["post_caption"].strip(),
                        "why": [m["why"].strip()], "ai": True})
    out.sort(key=lambda m: m["score"], reverse=True)
    usage = data.get("usage", {})
    cost = usage.get("input_tokens", 0) * 4 / 1e6 + usage.get("output_tokens", 0) * 20 / 1e6
    return out, round(cost, 3)
