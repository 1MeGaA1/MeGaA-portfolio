"""Download the web fonts and brand icons the pages use, so cafes work with no internet.

Run once from the Vortex folder (needs internet this one time):
    python client/tools/vendor_assets.py

- Google Fonts (Rajdhani, Chakra Petch, JetBrains Mono) -> client/ui/fonts + server/admin/fonts
- simpleicons.org logos used by the kiosk cards     -> client/ui/icons
Both pages are rewritten to use the local copies.
"""
from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KIOSK = ROOT / "client" / "ui" / "index.html"
ADMIN = ROOT / "server" / "admin" / "index.html"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
FONT_CSS_URL = ("https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700"
                "&family=Chakra+Petch:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def vendor_fonts() -> None:
    css = fetch(FONT_CSS_URL).decode("utf-8")
    out_dir = ROOT / "client" / "ui" / "fonts"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0

    def local(match: re.Match) -> str:
        nonlocal n
        url = match.group(1)
        n += 1
        name = f"font-{n:02d}.woff2"
        (out_dir / name).write_bytes(fetch(url))
        return f"url({name})"

    css = re.sub(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", local, css)
    (out_dir / "fonts.css").write_text(css, "utf-8")
    print(f"fonts: {n} files -> {out_dir}")
    admin_fonts = ROOT / "server" / "admin" / "fonts"
    if admin_fonts.exists():
        shutil.rmtree(admin_fonts)
    shutil.copytree(out_dir, admin_fonts)
    print(f"fonts: copied -> {admin_fonts}")

    link_re = re.compile(r'<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">')
    for page in (KIOSK, ADMIN):
        html = page.read_text("utf-8")
        if link_re.search(html):
            html = link_re.sub('<link rel="stylesheet" href="fonts/fonts.css">', html)
            html = re.sub(r'\s*<link rel="preconnect" href="https://fonts\.g[^"]+"( crossorigin)?>', "", html)
            page.write_text(html, "utf-8")
            print(f"fonts: {page.name} now uses fonts/fonts.css")


def vendor_icons() -> None:
    html = KIOSK.read_text("utf-8")
    slugs = sorted(set(re.findall(r"https://cdn\.simpleicons\.org/([a-z0-9]+)/ffffff", html)))
    out_dir = ROOT / "client" / "ui" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for slug in slugs:
        try:
            (out_dir / f"{slug}.svg").write_bytes(fetch(f"https://cdn.simpleicons.org/{slug}/ffffff"))
            ok += 1
        except Exception as exc:  # keep the CDN url for icons we could not fetch
            print(f"icons: {slug} failed ({exc})")
            continue
        html = html.replace(f"https://cdn.simpleicons.org/{slug}/ffffff", f"icons/{slug}.svg")
    KIOSK.write_text(html, "utf-8")
    print(f"icons: {ok}/{len(slugs)} saved -> {out_dir}")


if __name__ == "__main__":
    vendor_fonts()
    vendor_icons()
