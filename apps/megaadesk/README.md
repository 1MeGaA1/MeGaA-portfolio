# MeGaADesk

A self-hosted remote-desktop tool (like AnyDesk / TeamViewer) — **no ads, no
company servers, no account**. You run the relay on your own VPS, so nothing
touches anyone else's infrastructure.

- **Host** (the PC being controlled): **pure Python standard library** — zero
  dependencies. Drop it on any Windows machine that has Python.
- **Viewer** (the PC you sit at): a **Qt Quick / QML** app (PySide6), GPU-composited.
- **Relay** (a cheap VPS): pure stdlib, one file. Only ever sees encrypted bytes.

Everything between host and viewer is **end-to-end encrypted** with a password
you choose. The relay pairs the two by an ID and forwards ciphertext — it can't
see your screen or your keystrokes.

---

## How it works

```
   ┌──────────┐      encrypted       ┌─────────┐      encrypted      ┌──────────┐
   │  HOST    │  ───────────────►    │  RELAY  │   ───────────────►  │  VIEWER  │
   │ (Windows)│  screen frames       │  (VPS)  │   screen frames     │  (QML)   │
   │  capture │  ◄───────────────    │ forwards│   ◄───────────────  │  display │
   │  + input │      input events    │  bytes  │      input events   │  + input │
   └──────────┘                      └─────────┘                     └──────────┘
        └─ both dial OUT to the relay, so NAT/firewalls aren't a problem ─┘
```

**Pipeline:** capture the screen with GDI `BitBlt` (ctypes) → composite the
mouse cursor → split into horizontal strips and send only the ones that changed,
`zlib`-compressed → encrypt (HMAC-SHA256 stream cipher, encrypt-then-MAC) → relay
→ decrypt → rebuild the framebuffer → paint in QML. Input events travel back the
same encrypted channel and are replayed with `SendInput`.

**Bandwidth (measured, 1920×1080):** full keyframe ≈ **375 KB**; idle/typing
deltas **a few KB**; heavy motion up to ~450 KB/frame. Great for desktop, admin,
and coding work over normal broadband. Full-screen video/gaming will be choppy
(no hardware H.264 — that's the one optional upgrade, see *Roadmap*).

---

## Security

- Session key = **PBKDF2-HMAC-SHA256(password, salt)**, 200k rounds.
- Traffic = **HMAC-SHA256 counter-mode stream cipher + Encrypt-then-MAC**. A
  wrong password or any tampering by the relay makes the MAC check fail and the
  connection is dropped.
- The relay sees only: the public salt, the connection ID, and ciphertext.
- **Not yet forward-secret** (the key comes only from the password). An ephemeral
  Diffie–Hellman upgrade is planned (see *Roadmap*). **Use a strong password.**

---

## Install

**Host machine:** just Python 3.8+ (Windows). Nothing to `pip install`.

**Viewer machine:** Python 3.8+ and PySide6:

```bash
pip install PySide6
```

(Or use the pure-stdlib fallback viewer `viewer.py` — see below — which needs
nothing but Python.)

**Relay VPS:** Python 3.8+ only. Copy `relay.py` and the `common/` folder over.

---

## Quick start — LAN (no VPS needed)

On the **host** PC (find its LAN IP with `ipconfig`):

```bash
python host.py --password YOURSECRET --listen --port 7777
```

On the **viewer** PC:

```bash
python viewer_qml.py --host 192.168.1.50 --port 7777 --password YOURSECRET
```

…or run `python viewer_qml.py` with no arguments and fill in the connect screen.

---

## Internet setup (via your VPS relay)

**1. On the VPS**, run the relay and open the port in the firewall:

```bash
python3 relay.py --port 7000
# then allow it, e.g.:  sudo ufw allow 7000/tcp
```

**2. On the host** PC you want to control:

```bash
python host.py --password YOURSECRET --relay YOUR.VPS.IP:7000 --id MYPC01
```

**3. On the viewer**, run `python viewer_qml.py`, choose **Relay (Internet)**,
and enter `YOUR.VPS.IP:7000`, the ID `MYPC01`, and the password.

The ID is like an AnyDesk address; the password is what protects the session.

---

## Launchers (Windows)

Double-click these instead of typing commands:

| File | What it does |
|---|---|
| `run_host.bat`   | Prompts for LAN vs internet + password, starts the host |
| `run_viewer.bat` | Opens the QML viewer connect screen |
| `run_relay.bat`  | Starts the relay (for a Windows VPS) |

---

## Files

```
MeGaADesk/
  host.py            host / agent (capture + input), pure stdlib
  viewer_qml.py      QML viewer (PySide6)          ← main viewer
  viewer.py          tkinter viewer (pure stdlib)  ← zero-install fallback
  relay.py           relay server for the VPS, pure stdlib
  capture_win.py     GDI screen capture + cursor compositing (ctypes)
  input_win.py       SendInput mouse/keyboard injection (ctypes)
  qml/main.qml       viewer UI
  common/
    protocol.py      framing, secure channel, handshake, input (de)serialization
    crypto.py        PBKDF2 + HMAC-CTR authenticated encryption
    framec.py        strip-diff frame codec (BGRA→RGB, zlib)
    relaylink.py     relay client (registration/pairing)
```

---

## Tuning

In `common/framec.py`: `STRIP_H` (strip height — smaller = finer diffs, a bit
more overhead) and the zlib `level`. In `host.py`: `TARGET_FPS` (default 15).

---

## Limitations (v1)

- **Windows host only** (capture/input use Win32). The viewer is cross-platform.
- **Primary monitor only** (multi-monitor capture exists in the capturer but
  isn't wired to input mapping yet).
- **No file transfer / clipboard / audio** yet.
- To control **elevated apps or the UAC prompt**, run the host **as
  Administrator**. The Windows secure desktop (lock screen / Ctrl-Alt-Del) can't
  be driven by a normal process.

## Roadmap

1. **Forward secrecy** — authenticated ephemeral Diffie–Hellman (pure stdlib
   `pow()` with an RFC 3526 group) on top of the password.
2. **Optional H.264** (PyAV) for smooth video/gaming — one dependency, viewer-side.
3. Clipboard sync, file transfer, multi-monitor, audio.
4. Adaptive quality (drop zlib level / downscale) when the uplink is tight.
