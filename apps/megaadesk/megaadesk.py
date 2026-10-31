#!/usr/bin/env python3
"""
MeGaADesk - single-file self-hosted remote desktop (AnyDesk / TeamViewer style).

No ads, no accounts, no company servers. Everything below - host, viewer, relay,
crypto, codec - lives in this one file.

  * host      : share THIS Windows PC's screen (pure stdlib, Windows only)
  * viewer    : QML / PySide6 remote-control client   (needs: pip install PySide6)
  * viewer-tk : fallback tkinter client               (pure stdlib, any OS)
  * relay     : pairing/forwarding server for a VPS   (pure stdlib, any OS)

All traffic between host and viewer is end-to-end encrypted with a password you
choose; the relay only ever forwards ciphertext.

Examples
--------
  # LAN
  python megaadesk.py host   --password SECRET --listen --port 7777
  python megaadesk.py viewer --host 192.168.1.50 --port 7777 --password SECRET

  # Internet (relay on a VPS)
  python megaadesk.py relay  --port 7000                       # on the VPS
  python megaadesk.py host   --password SECRET --relay VPS_IP:7000 --id MYPC01
  python megaadesk.py viewer --relay VPS_IP:7000 --id MYPC01 --password SECRET

  # Or just:  python megaadesk.py viewer     (opens the connect screen)
"""
import argparse
import hashlib
import hmac
import math
import os
import socket
import struct
import sys
import threading
import time
import zlib
import ctypes

_IS_WIN = sys.platform.startswith("win")

TARGET_FPS = 15
STRIP_H = 36  # frame strip height in pixels


# ===========================================================================
#  CRYPTO  - authenticated encryption from HMAC-SHA256 (no third-party deps)
# ===========================================================================
# PBKDF2 derives an encryption key + a MAC key from the password. HMAC-SHA256 in
# counter mode is the stream cipher; Encrypt-then-MAC gives integrity. A wrong
# password (or relay tampering) fails the MAC check and the peer is rejected.
# NOTE: not forward-secret (key comes only from the password) - use a strong one.

PBKDF2_ROUNDS = 200_000
KEY_LEN = 32
NONCE_LEN = 16
TAG_LEN = 32
SALT_LEN = 16


def new_salt():
    return os.urandom(SALT_LEN)


def derive_keys(password, salt):
    if isinstance(password, str):
        password = password.encode("utf-8")
    material = hashlib.pbkdf2_hmac("sha256", password, salt, PBKDF2_ROUNDS, dklen=KEY_LEN * 2)
    return material[:KEY_LEN], material[KEY_LEN:]


def _keystream(enc_key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(enc_key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def _xor(data, keystream):
    if not data:
        return b""
    return (int.from_bytes(data, "big") ^ int.from_bytes(keystream, "big")).to_bytes(len(data), "big")


def seal(enc_key, mac_key, plaintext):
    nonce = os.urandom(NONCE_LEN)
    ct = _xor(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return nonce + ct + tag


def unseal(enc_key, mac_key, blob):
    """Verify + decrypt. Raises ValueError on a bad tag / wrong password."""
    if len(blob) < NONCE_LEN + TAG_LEN:
        raise ValueError("ciphertext too short")
    nonce, ct, tag = blob[:NONCE_LEN], blob[NONCE_LEN:-TAG_LEN], blob[-TAG_LEN:]
    expected = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("authentication failed (wrong password or tampering)")
    return _xor(ct, _keystream(enc_key, nonce, len(ct)))


# ===========================================================================
#  FRAME CODEC  - full-width horizontal strips, diffed and zlib-compressed
# ===========================================================================
def bgra_to_rgb(bgra):
    """Reorder BGRA -> RGB with three C-level strided copies (no pixel loop)."""
    n = len(bgra) // 4
    out = bytearray(n * 3)
    out[0::3] = bgra[2::4]  # R
    out[1::3] = bgra[1::4]  # G
    out[2::3] = bgra[0::4]  # B
    return bytes(out)


class FrameEncoder:
    """Host side: BGRA frame -> list of changed (strip_index, compressed_rgb)."""

    def __init__(self, width, height, strip_h=STRIP_H, level=6):
        self.w, self.h, self.sh, self.level = width, height, strip_h, level
        self.nstrips = (height + strip_h - 1) // strip_h
        self._prev = [None] * self.nstrips

    def reset(self):
        self._prev = [None] * self.nstrips

    def encode(self, bgra):
        out = []
        w4 = self.w * 4
        mv = memoryview(bgra)
        for i in range(self.nstrips):
            y0 = i * self.sh
            y1 = min(y0 + self.sh, self.h)
            src = mv[y0 * w4: y1 * w4]
            if self._prev[i] != src:
                raw = bytes(src)
                out.append((i, zlib.compress(bgra_to_rgb(raw), self.level)))
                self._prev[i] = raw
        return out

    def pack(self, strips):
        parts = []
        for i, comp in strips:
            parts.append(struct.pack(">HI", i, len(comp)))
            parts.append(comp)
        return b"".join(parts)


class FrameBuffer:
    """Viewer side: keeps a full RGB image and applies incoming strips."""

    def __init__(self, width, height, strip_h=STRIP_H):
        self.w, self.h, self.sh = width, height, strip_h
        self.nstrips = (height + strip_h - 1) // strip_h
        self.buf = bytearray(width * height * 3)

    def apply_packed(self, data):
        w3 = self.w * 3
        off = 0
        while off < len(data):
            i, clen = struct.unpack_from(">HI", data, off)
            off += 6
            comp = data[off:off + clen]
            off += clen
            rgb = zlib.decompress(comp)
            dst = (i * self.sh) * w3
            self.buf[dst:dst + len(rgb)] = rgb

    def ppm(self):
        return b"P6\n%d %d\n255\n" % (self.w, self.h) + bytes(self.buf)


# ===========================================================================
#  PROTOCOL  - length-prefixed framing, secure channel, handshake, input
# ===========================================================================
OP_HELLO = 1
OP_SCREEN_INFO = 2
OP_FRAME = 3
OP_MOUSE = 4
OP_KEY = 5
OP_PING = 6
OP_PONG = 7

MAGIC = b"MeGaADesk/1"

M_MOVE, M_DOWN, M_UP, M_WHEEL = 0, 1, 2, 3


class ProtocolError(Exception):
    pass


def send_frame(sock, data):
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed connection")
        buf += chunk
    return bytes(buf)


def recv_frame(sock, max_len=64 * 1024 * 1024):
    (n,) = struct.unpack(">I", _recv_exact(sock, 4))
    if n > max_len:
        raise ProtocolError(f"frame too large: {n}")
    return _recv_exact(sock, n)


class SecureChannel:
    def __init__(self, sock, enc_key, mac_key):
        self.sock = sock
        self._ek = enc_key
        self._mk = mac_key
        self._send_lock = threading.Lock()

    def send(self, opcode, payload=b""):
        blob = seal(self._ek, self._mk, bytes([opcode]) + payload)
        with self._send_lock:
            send_frame(self.sock, blob)

    def recv(self):
        body = unseal(self._ek, self._mk, recv_frame(self.sock))
        return body[0], body[1:]

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def host_handshake(sock, password):
    salt = new_salt()
    send_frame(sock, salt)
    ek, mk = derive_keys(password, salt)
    chan = SecureChannel(sock, ek, mk)
    opcode, payload = chan.recv()  # wrong password -> ValueError
    if opcode != OP_HELLO or payload != MAGIC:
        raise ProtocolError("bad hello")
    return chan


def viewer_handshake(sock, password):
    salt = recv_frame(sock)
    ek, mk = derive_keys(password, salt)
    chan = SecureChannel(sock, ek, mk)
    chan.send(OP_HELLO, MAGIC)
    return chan


def pack_mouse(kind, x=0, y=0, data=0):
    return struct.pack(">BHHh", kind, x, y, data)


def unpack_mouse(payload):
    return struct.unpack(">BHHh", payload)


def pack_key(down, vk):
    return struct.pack(">BH", 1 if down else 0, vk)


def unpack_key(payload):
    down, vk = struct.unpack(">BH", payload)
    return bool(down), vk


def pack_screen_info(w, h, strip_h):
    return struct.pack(">HHH", w, h, strip_h)


def unpack_screen_info(payload):
    return struct.unpack(">HHH", payload)


# ===========================================================================
#  RELAY LINK  - client-side registration/pairing helpers
# ===========================================================================
ROLE_HOST = b"H"
ROLE_VIEWER = b"J"


def split_addr(addr, default_port=7000):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def _register(sock, role, host_id):
    send_frame(sock, role + host_id.encode("utf-8"))
    status = recv_frame(sock)
    if not status or status[0] != 1:
        reason = status[1:].decode("utf-8", "replace") if len(status) > 1 else "rejected"
        raise ConnectionError(f"relay rejected connection: {reason}")


def host_connect(relay, host_id, timeout=10):
    host, port = split_addr(relay)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(None)
    _register(sock, ROLE_HOST, host_id)
    return sock


def relay_viewer_connect(relay, host_id, timeout=10):
    host, port = split_addr(relay)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(None)
    _register(sock, ROLE_VIEWER, host_id)
    return sock


# ===========================================================================
#  WINDOWS BACKEND  - screen capture (GDI) + input injection (SendInput)
#  Defined only on Windows so relay/viewer run on any OS.
# ===========================================================================
if _IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    SRCCOPY = 0x00CC0020
    CAPTUREBLT = 0x40000000
    BI_RGB = 0
    DIB_RGB_COLORS = 0
    SM_CXSCREEN, SM_CYSCREEN = 0, 1
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    CURSOR_SHOWING = 0x00000001
    DI_NORMAL = 0x0003

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hCursor", wintypes.HANDLE), ("ptScreenPos", POINT)]

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    def _set_gdi_signatures():
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
        gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                    ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
        user32.GetCursorInfo.restype = wintypes.BOOL
        user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
        user32.GetIconInfo.restype = wintypes.BOOL
        user32.CopyIcon.argtypes = [wintypes.HICON]
        user32.CopyIcon.restype = wintypes.HICON
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT]
        user32.DrawIconEx.restype = wintypes.BOOL

    def set_dpi_aware():
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

    _set_gdi_signatures()

    class ScreenCapturer:
        def __init__(self, virtual=False):
            set_dpi_aware()
            if virtual:
                self.left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                self.top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                self.width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                self.height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            else:
                self.left = self.top = 0
                self.width = user32.GetSystemMetrics(SM_CXSCREEN)
                self.height = user32.GetSystemMetrics(SM_CYSCREEN)
            self._screen_dc = user32.GetDC(0)
            self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)
            self._bitmap = gdi32.CreateCompatibleBitmap(self._screen_dc, self.width, self.height)
            gdi32.SelectObject(self._mem_dc, self._bitmap)
            self._bmi = BITMAPINFO()
            self._bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            self._bmi.bmiHeader.biWidth = self.width
            self._bmi.bmiHeader.biHeight = -self.height
            self._bmi.bmiHeader.biPlanes = 1
            self._bmi.bmiHeader.biBitCount = 32
            self._bmi.bmiHeader.biCompression = BI_RGB
            self._buf = (ctypes.c_char * (self.width * self.height * 4))()
            self.draw_cursor = True

        def _composite_cursor(self):
            ci = CURSORINFO()
            ci.cbSize = ctypes.sizeof(CURSORINFO)
            if not user32.GetCursorInfo(ctypes.byref(ci)):
                return
            if not (ci.flags & CURSOR_SHOWING) or not ci.hCursor:
                return
            hicon = user32.CopyIcon(ci.hCursor)
            if not hicon:
                return
            try:
                ii = ICONINFO()
                if user32.GetIconInfo(hicon, ctypes.byref(ii)):
                    x = ci.ptScreenPos.x - ii.xHotspot - self.left
                    y = ci.ptScreenPos.y - ii.yHotspot - self.top
                    user32.DrawIconEx(self._mem_dc, x, y, hicon, 0, 0, 0, None, DI_NORMAL)
                    if ii.hbmMask:
                        gdi32.DeleteObject(ii.hbmMask)
                    if ii.hbmColor:
                        gdi32.DeleteObject(ii.hbmColor)
            finally:
                user32.DestroyIcon(hicon)

        def grab(self):
            gdi32.BitBlt(self._mem_dc, 0, 0, self.width, self.height,
                         self._screen_dc, self.left, self.top, SRCCOPY | CAPTUREBLT)
            if self.draw_cursor:
                self._composite_cursor()
            gdi32.GetDIBits(self._mem_dc, self._bitmap, 0, self.height,
                            self._buf, ctypes.byref(self._bmi), DIB_RGB_COLORS)
            return bytes(self._buf)

        def close(self):
            try:
                gdi32.DeleteObject(self._bitmap)
                gdi32.DeleteDC(self._mem_dc)
                user32.ReleaseDC(0, self._screen_dc)
            except Exception:
                pass

        def __del__(self):
            self.close()

    # --- input injection ---------------------------------------------------
    ULONG_PTR = wintypes.WPARAM
    INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
    MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
    MOUSEEVENTF_WHEEL = 0x0800
    WHEEL_DELTA = 120
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001
    _EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0xA3, 0xA5, 0x90}

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _INPUTunion(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    def _send_input(inp):
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    class InputInjector:
        def __init__(self, screen_w, screen_h):
            self.w = max(1, screen_w)
            self.h = max(1, screen_h)

        def _abs(self, x, y):
            nx = int(x * 65535 / max(1, self.w - 1))
            ny = int(y * 65535 / max(1, self.h - 1))
            return max(0, min(65535, nx)), max(0, min(65535, ny))

        def move(self, x, y):
            nx, ny = self._abs(x, y)
            _send_input(INPUT(INPUT_MOUSE, _INPUTunion(mi=MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0))))

        def button(self, down, btn, x=None, y=None):
            if x is not None:
                self.move(x, y)
            flags = {
                (0, True): MOUSEEVENTF_LEFTDOWN, (0, False): MOUSEEVENTF_LEFTUP,
                (1, True): MOUSEEVENTF_RIGHTDOWN, (1, False): MOUSEEVENTF_RIGHTUP,
                (2, True): MOUSEEVENTF_MIDDLEDOWN, (2, False): MOUSEEVENTF_MIDDLEUP,
            }.get((btn, down))
            if flags is None:
                return
            _send_input(INPUT(INPUT_MOUSE, _INPUTunion(mi=MOUSEINPUT(0, 0, 0, flags, 0, 0))))

        def wheel(self, notches):
            _send_input(INPUT(INPUT_MOUSE, _INPUTunion(mi=MOUSEINPUT(0, 0, notches * WHEEL_DELTA & 0xFFFFFFFF, MOUSEEVENTF_WHEEL, 0, 0))))

        def key(self, down, vk):
            flags = 0 if down else KEYEVENTF_KEYUP
            if vk in _EXTENDED_VKS:
                flags |= KEYEVENTF_EXTENDEDKEY
            _send_input(INPUT(INPUT_KEYBOARD, _INPUTunion(ki=KEYBDINPUT(vk, 0, flags, 0, 0))))


# ===========================================================================
#  HOST  - capture loop + input application over a transport socket
# ===========================================================================
def _capture_loop(chan, cap, enc, stop):
    period = 1.0 / TARGET_FPS
    enc.reset()
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            strips = enc.encode(cap.grab())
            if strips:
                chan.send(OP_FRAME, enc.pack(strips))
        except (OSError, ConnectionError):
            break
        dt = time.perf_counter() - t0
        if dt < period:
            stop.wait(period - dt)


def _input_loop(chan, inj, stop):
    while not stop.is_set():
        try:
            op, payload = chan.recv()
        except (OSError, ConnectionError, ValueError):
            break
        if op == OP_MOUSE:
            kind, x, y, data = unpack_mouse(payload)
            if kind == M_MOVE:
                inj.move(x, y)
            elif kind == M_DOWN:
                inj.button(True, data, x, y)
            elif kind == M_UP:
                inj.button(False, data, x, y)
            elif kind == M_WHEEL:
                inj.wheel(data)
        elif op == OP_KEY:
            down, vk = unpack_key(payload)
            inj.key(down, vk)
        elif op == OP_PING:
            chan.send(OP_PONG)


def serve_session(sock, password):
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        chan = host_handshake(sock, password)
    except (ProtocolError, ValueError, ConnectionError) as e:
        print(f"  handshake rejected: {e}")
        sock.close()
        return
    cap = ScreenCapturer()
    inj = InputInjector(cap.width, cap.height)
    chan.send(OP_SCREEN_INFO, pack_screen_info(cap.width, cap.height, STRIP_H))
    enc = FrameEncoder(cap.width, cap.height)
    print(f"  viewer connected - streaming {cap.width}x{cap.height}")
    stop = threading.Event()
    tin = threading.Thread(target=_input_loop, args=(chan, inj, stop), daemon=True)
    tin.start()
    try:
        _capture_loop(chan, cap, enc, stop)
    finally:
        stop.set()
        cap.close()
        chan.close()
        print("  viewer disconnected")


def run_host_direct(password, port, bind):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(1)
    print(f"MeGaADesk host listening on {bind}:{port} (direct). Waiting for a viewer...")
    while True:
        sock, addr = srv.accept()
        print(f"connection from {addr[0]}:{addr[1]}")
        serve_session(sock, password)


def run_host_relay(password, relay, host_id):
    print(f"MeGaADesk host registering as '{host_id}' on relay {relay}")
    while True:
        try:
            sock = host_connect(relay, host_id)
        except OSError as e:
            print(f"  relay connect failed: {e}; retrying in 3s")
            time.sleep(3)
            continue
        print("  registered; waiting for a viewer...")
        serve_session(sock, password)


# ===========================================================================
#  RELAY SERVER
# ===========================================================================
_waiting = {}
_waiting_lock = threading.Lock()


def _pump(a, b):
    def one_way(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    t = threading.Thread(target=one_way, args=(a, b), daemon=True)
    t.start()
    one_way(b, a)
    for s in (a, b):
        try:
            s.close()
        except OSError:
            pass


def _relay_handle(sock, addr):
    try:
        reg = recv_frame(sock, max_len=1024)
    except (OSError, ProtocolError):
        sock.close()
        return
    role, host_id = reg[:1], reg[1:].decode("utf-8", "replace")
    if not host_id:
        send_frame(sock, b"\x00missing id")
        sock.close()
        return
    if role == ROLE_HOST:
        with _waiting_lock:
            old = _waiting.pop(host_id, None)
            _waiting[host_id] = sock
        if old is not None:
            try:
                old.close()
            except OSError:
                pass
        try:
            send_frame(sock, b"\x01")
        except OSError:
            with _waiting_lock:
                if _waiting.get(host_id) is sock:
                    _waiting.pop(host_id, None)
            sock.close()
            return
        print(f"[+] host '{host_id}' registered from {addr[0]}")
        return
    if role == ROLE_VIEWER:
        with _waiting_lock:
            hsock = _waiting.pop(host_id, None)
        if hsock is None:
            send_frame(sock, b"\x00no host with that ID is online")
            sock.close()
            print(f"[-] viewer wanted '{host_id}' but no host waiting ({addr[0]})")
            return
        try:
            send_frame(sock, b"\x01")
        except OSError:
            try:
                hsock.close()
            except OSError:
                pass
            sock.close()
            return
        print(f"[*] paired '{host_id}': host <-> viewer {addr[0]}")
        _pump(hsock, sock)
        print(f"[x] session '{host_id}' ended")
        return
    send_frame(sock, b"\x00unknown role")
    sock.close()


def run_relay(port, bind):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(64)
    print(f"MeGaADesk relay listening on {bind}:{port}")
    while True:
        sock, addr = srv.accept()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=_relay_handle, args=(sock, addr), daemon=True).start()


# ===========================================================================
#  QML VIEWER  (PySide6)
# ===========================================================================
MAIN_QML = r"""
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import MeGaADesk 1.0

ApplicationWindow {
    id: win
    visible: true
    width: 1040
    height: 660
    title: "MeGaADesk"
    color: "#0e1116"

    Material.theme: Material.Dark
    Material.accent: "#4c8dff"
    Material.primary: "#4c8dff"
    Material.foreground: "#e8ebf0"

    property bool connected: false
    property string status: ""
    property bool hostActive: false
    property string hostStatus: ""

    Connections {
        target: backend
        function onConnected(w, h) {
            win.connected = true
            win.status = ""
            win.title = "MeGaADesk — " + w + "×" + h
            remoteScreen.forceActiveFocus()
        }
        function onFailed(msg) { win.connected = false; win.status = msg }
        function onDisconnected() {
            win.connected = false
            win.status = "Disconnected."
            win.title = "MeGaADesk"
        }
        function onHostStatus(s) { win.hostStatus = s }
        function onHostActive(a) { win.hostActive = a }
    }

    RemoteScreen {
        id: remoteScreen
        objectName: "remoteScreen"
        anchors.fill: parent
        visible: win.connected
        focus: win.connected
    }

    // Floating disconnect button while connected
    Button {
        visible: win.connected
        text: "Disconnect"
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 12
        Material.background: "#e05260"
        onClicked: backend.disconnect()
    }

    // Connect / Share card
    Rectangle {
        visible: !win.connected
        anchors.centerIn: parent
        width: 470
        height: form.implicitHeight + 52
        radius: 16
        color: "#171b22"
        border.color: "#262c38"
        border.width: 1

        ColumnLayout {
            id: form
            anchors.centerIn: parent
            width: parent.width - 56
            spacing: 16

            Label {
                text: "MeGaADesk"
                color: "#f2f4f8"
                font.pixelSize: 34
                font.bold: true
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 6
            }
            Label {
                text: "Remote Desktop — no ads, your server"
                color: "#7d858f"
                font.pixelSize: 13
                Layout.alignment: Qt.AlignHCenter
            }

            TabBar {
                id: topMode
                Layout.fillWidth: true
                TabButton { text: "Connect to a PC" }
                TabButton { text: "Share this PC" }
            }

            StackLayout {
                Layout.fillWidth: true
                currentIndex: topMode.currentIndex

                // ---- Connect: control someone else's PC ----
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    TabBar {
                        id: modeTab
                        Layout.fillWidth: true
                        TabButton { text: "Relay (Internet)" }
                        TabButton { text: "Direct (LAN)" }
                    }
                    ColumnLayout {
                        visible: modeTab.currentIndex === 0
                        Layout.fillWidth: true
                        spacing: 18
                        TextField { id: relayAddr; placeholderText: "Relay host:port  (e.g. 203.0.113.9:7000)"; Layout.fillWidth: true }
                        TextField { id: relayId; placeholderText: "Host ID  (their ID)"; Layout.fillWidth: true }
                    }
                    ColumnLayout {
                        visible: modeTab.currentIndex === 1
                        Layout.fillWidth: true
                        spacing: 18
                        TextField { id: directHost; placeholderText: "Host IP  (e.g. 192.168.1.50)"; Layout.fillWidth: true }
                        TextField { id: directPort; placeholderText: "Port"; text: "7777"; Layout.fillWidth: true }
                    }
                    TextField {
                        id: pw
                        placeholderText: "Password"
                        echoMode: TextInput.Password
                        Layout.fillWidth: true
                        onAccepted: connectBtn.clicked()
                    }
                    Button {
                        id: connectBtn
                        text: "Connect"
                        highlighted: true
                        Layout.fillWidth: true
                        onClicked: {
                            if (modeTab.currentIndex === 0)
                                backend.connectRelay(relayAddr.text.trim(), relayId.text.trim(), pw.text)
                            else
                                backend.connectDirect(directHost.text.trim(), parseInt(directPort.text || "7777"), pw.text)
                        }
                    }
                    Label {
                        text: win.status
                        visible: win.status.length > 0
                        color: "#ff6b6b"
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                // ---- Share: let someone control THIS PC ----
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    Label {
                        text: "Let someone control THIS PC — give them the details below."
                        color: "#9aa1ab"
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    TabBar {
                        id: shareMode
                        Layout.fillWidth: true
                        enabled: !win.hostActive
                        TabButton { text: "Relay (Internet)" }
                        TabButton { text: "Direct (LAN)" }
                    }
                    ColumnLayout {
                        visible: shareMode.currentIndex === 0
                        Layout.fillWidth: true
                        spacing: 16
                        TextField { id: hostRelay; placeholderText: "Relay host:port  (your VPS, e.g. 203.0.113.9:7000)"; enabled: !win.hostActive; Layout.fillWidth: true }
                        TextField { id: hostId; text: defaultHostId; placeholderText: "Your ID  (they type this)"; enabled: !win.hostActive; Layout.fillWidth: true }
                    }
                    ColumnLayout {
                        visible: shareMode.currentIndex === 1
                        Layout.fillWidth: true
                        spacing: 8
                        Label { text: "Your LAN IP:   " + lanIp; color: "#cfd4dc"; font.pixelSize: 13; Layout.fillWidth: true }
                        TextField { id: hostPort; text: "7777"; placeholderText: "Port"; enabled: !win.hostActive; Layout.fillWidth: true }
                    }
                    TextField {
                        id: hostPw
                        text: defaultHostPassword
                        placeholderText: "Password  (they type this)"
                        enabled: !win.hostActive
                        Layout.fillWidth: true
                    }
                    Button {
                        id: shareBtn
                        text: win.hostActive ? "Stop Sharing" : "Start Sharing"
                        highlighted: true
                        enabled: isWindows
                        Material.background: win.hostActive ? "#e05260" : "#3fb96b"
                        Layout.fillWidth: true
                        onClicked: {
                            if (win.hostActive)
                                backend.stopHost()
                            else if (shareMode.currentIndex === 0)
                                backend.startHostRelay(hostRelay.text.trim(), hostId.text.trim(), hostPw.text)
                            else
                                backend.startHostDirect(parseInt(hostPort.text || "7777"), hostPw.text)
                        }
                    }
                    Label {
                        text: isWindows ? win.hostStatus : "Hosting is available on Windows only."
                        visible: text.length > 0
                        color: win.hostActive ? "#7fd6a0" : "#9aa1ab"
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
}
"""


def _default_host_id():
    try:
        name = socket.gethostname()
    except Exception:
        name = "MYPC"
    name = "".join(c for c in name.upper() if c.isalnum() or c in "-_")[:20]
    return name or "MYPC"


def _gen_password():
    return os.urandom(3).hex()  # 6 hex chars, e.g. 'a3f9c1'


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no data sent; just picks the outbound iface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def cmd_viewer(args):
    from PySide6.QtCore import Qt, QObject, Signal, Slot, QRectF, QTimer
    from PySide6.QtGui import QGuiApplication, QImage, QColor
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
    from PySide6.QtQuick import QQuickPaintedItem, QQuickItem
    from PySide6.QtQuickControls2 import QQuickStyle

    qt_btn = {Qt.LeftButton: 0, Qt.RightButton: 1, Qt.MiddleButton: 2}

    class RemoteScreen(QQuickPaintedItem):
        inputMouse = Signal(int, int, int, int)
        inputKey = Signal(bool, int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAcceptedMouseButtons(Qt.AllButtons)
            self.setAcceptHoverEvents(True)
            self.setFlag(QQuickItem.ItemAcceptsInputMethod, True)
            self._img = QImage(1, 1, QImage.Format_RGB888)
            self._img.fill(QColor("black"))
            self._rw, self._rh = 1, 1
            self._scale, self._ox, self._oy = 1.0, 0.0, 0.0

        def set_remote_size(self, w, h):
            self._rw, self._rh = w, h

        @Slot(QImage)
        def show_frame(self, img):
            self._img = img
            self.update()

        def paint(self, painter):
            iw, ih = self.width(), self.height()
            painter.fillRect(QRectF(0, 0, iw, ih), QColor("black"))
            if self._rw <= 0 or self._rh <= 0:
                return
            self._scale = min(iw / self._rw, ih / self._rh)
            dw, dh = self._rw * self._scale, self._rh * self._scale
            self._ox, self._oy = (iw - dw) / 2, (ih - dh) / 2
            painter.drawImage(QRectF(self._ox, self._oy, dw, dh), self._img)

        def _map(self, px, py):
            if self._scale <= 0:
                return 0, 0
            rx = int((px - self._ox) / self._scale)
            ry = int((py - self._oy) / self._scale)
            return max(0, min(self._rw - 1, rx)), max(0, min(self._rh - 1, ry))

        def hoverMoveEvent(self, e):
            x, y = self._map(e.position().x(), e.position().y())
            self.inputMouse.emit(M_MOVE, x, y, 0)

        def mouseMoveEvent(self, e):
            x, y = self._map(e.position().x(), e.position().y())
            self.inputMouse.emit(M_MOVE, x, y, 0)

        def mousePressEvent(self, e):
            self.forceActiveFocus()
            x, y = self._map(e.position().x(), e.position().y())
            self.inputMouse.emit(M_DOWN, x, y, qt_btn.get(e.button(), 0))

        def mouseReleaseEvent(self, e):
            x, y = self._map(e.position().x(), e.position().y())
            self.inputMouse.emit(M_UP, x, y, qt_btn.get(e.button(), 0))

        def wheelEvent(self, e):
            self.inputMouse.emit(M_WHEEL, 0, 0, int(e.angleDelta().y() / 120))

        def keyPressEvent(self, e):
            vk = e.nativeVirtualKey()
            if vk:
                self.inputKey.emit(True, vk)

        def keyReleaseEvent(self, e):
            vk = e.nativeVirtualKey()
            if vk:
                self.inputKey.emit(False, vk)

    class Backend(QObject):
        connected = Signal(int, int)
        failed = Signal(str)
        disconnected = Signal()
        frameReady = Signal(QImage)
        hostStatus = Signal(str)
        hostActive = Signal(bool)

        def __init__(self):
            super().__init__()
            self.chan = None
            self.screen = None
            self._stop = threading.Event()
            self._host_stop = None
            self._host_srv = None
            self._host_chan = None

        def attach_screen(self, screen):
            self.screen = screen
            self.frameReady.connect(screen.show_frame)
            screen.inputMouse.connect(self._on_mouse)
            screen.inputKey.connect(self._on_key)

        @Slot(str, int, str)
        def connectDirect(self, host, port, password):
            self._start(lambda: socket.create_connection((host, int(port)), timeout=10), password)

        @Slot(str, str, str)
        def connectRelay(self, relay, host_id, password):
            self._start(lambda: relay_viewer_connect(relay, host_id), password)

        @Slot()
        def disconnect(self):
            self._stop.set()
            if self.chan:
                self.chan.close()

        def _on_mouse(self, kind, x, y, data):
            if self.chan:
                try:
                    self.chan.send(OP_MOUSE, pack_mouse(kind, x, y, data))
                except OSError:
                    pass

        def _on_key(self, down, vk):
            if self.chan:
                try:
                    self.chan.send(OP_KEY, pack_key(down, vk))
                except OSError:
                    pass

        def _start(self, connect_fn, password):
            self._stop.clear()
            threading.Thread(target=self._worker, args=(connect_fn, password), daemon=True).start()

        def _worker(self, connect_fn, password):
            try:
                sock = connect_fn()
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                chan = viewer_handshake(sock, password)
                op, payload = chan.recv()
            except ValueError:
                self.failed.emit("Wrong password (authentication rejected).")
                return
            except (OSError, ConnectionError) as e:
                self.failed.emit(f"Connection failed: {e}")
                return
            if op != OP_SCREEN_INFO:
                self.failed.emit("Protocol error: expected screen info.")
                return
            w, h, sh = unpack_screen_info(payload)
            self.chan = chan
            self.screen.set_remote_size(w, h)
            self.connected.emit(w, h)
            fb = FrameBuffer(w, h, sh)
            stride = w * 3
            while not self._stop.is_set():
                try:
                    op, payload = chan.recv()
                except (OSError, ConnectionError, ValueError):
                    break
                if op == OP_FRAME:
                    fb.apply_packed(payload)
                    img = QImage(bytes(fb.buf), w, h, stride, QImage.Format_RGB888)
                    try:
                        self.frameReady.emit(img.copy())
                    except RuntimeError:
                        return  # window/backend torn down during shutdown
            try:
                self.disconnected.emit()
            except RuntimeError:
                pass

        # --- hosting: let someone control THIS PC --------------------
        @Slot(str, str, str)
        def startHostRelay(self, relay, host_id, password):
            if not _IS_WIN:
                self.hostStatus.emit("Hosting requires Windows.")
                return
            if not (relay and host_id and password):
                self.hostStatus.emit("Enter the relay address, an ID, and a password.")
                return
            self._host_stop = threading.Event()
            self.hostActive.emit(True)
            threading.Thread(target=self._host_relay_loop, args=(relay, host_id, password), daemon=True).start()

        @Slot(int, str)
        def startHostDirect(self, port, password):
            if not _IS_WIN:
                self.hostStatus.emit("Hosting requires Windows.")
                return
            if not password:
                self.hostStatus.emit("Set a password first.")
                return
            self._host_stop = threading.Event()
            self.hostActive.emit(True)
            threading.Thread(target=self._host_direct_loop, args=(int(port), password), daemon=True).start()

        @Slot()
        def stopHost(self):
            if self._host_stop:
                self._host_stop.set()
            if self._host_srv:
                try:
                    self._host_srv.close()
                except OSError:
                    pass
            if self._host_chan:
                try:
                    self._host_chan.close()
                except OSError:
                    pass

        def _host_relay_loop(self, relay, host_id, password):
            while not self._host_stop.is_set():
                self.hostStatus.emit("Registering on relay...")
                try:
                    sock = host_connect(relay, host_id)
                except OSError as e:
                    self.hostStatus.emit(f"Relay error: {e} - retrying in 3s")
                    if self._host_stop.wait(3):
                        break
                    continue
                self.hostStatus.emit(f"Waiting for someone to connect...   (ID: {host_id})")
                self._serve_gui(sock, password)
            self.hostActive.emit(False)
            self.hostStatus.emit("Sharing stopped.")

        def _host_direct_loop(self, port, password):
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv.bind(("0.0.0.0", port))
                srv.listen(1)
            except OSError as e:
                self.hostStatus.emit(f"Cannot listen on port {port}: {e}")
                self.hostActive.emit(False)
                return
            self._host_srv = srv
            self.hostStatus.emit(f"Waiting on port {port}...   (give out your LAN IP + password)")
            while not self._host_stop.is_set():
                try:
                    sock, addr = srv.accept()
                except OSError:
                    break
                self._serve_gui(sock, password)
                if not self._host_stop.is_set():
                    self.hostStatus.emit(f"Waiting on port {port}...")
            try:
                srv.close()
            except OSError:
                pass
            self._host_srv = None
            self.hostActive.emit(False)
            self.hostStatus.emit("Sharing stopped.")

        def _serve_gui(self, sock, password):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                chan = host_handshake(sock, password)
            except (ProtocolError, ValueError, ConnectionError):
                self.hostStatus.emit("A connection attempt was rejected (wrong password).")
                try:
                    sock.close()
                except OSError:
                    pass
                return
            cap = ScreenCapturer()
            inj = InputInjector(cap.width, cap.height)
            chan.send(OP_SCREEN_INFO, pack_screen_info(cap.width, cap.height, STRIP_H))
            enc = FrameEncoder(cap.width, cap.height)
            self._host_chan = chan
            self.hostStatus.emit("\U0001f7e2 Connected - your screen is being shared.")
            sess_stop = threading.Event()
            tin = threading.Thread(target=_input_loop, args=(chan, inj, sess_stop), daemon=True)
            tin.start()
            try:
                _capture_loop(chan, cap, enc, sess_stop)
            except Exception:
                pass
            finally:
                sess_stop.set()
                cap.close()
                chan.close()
                self._host_chan = None

    app = QGuiApplication(sys.argv[:1])
    QQuickStyle.setStyle("Material")  # modern dark-themed controls
    qmlRegisterType(RemoteScreen, "MeGaADesk", 1, 0, "RemoteScreen")
    backend = Backend()
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("defaultHostId", _default_host_id())
    ctx.setContextProperty("defaultHostPassword", _gen_password())
    ctx.setContextProperty("lanIp", _lan_ip())
    ctx.setContextProperty("isWindows", bool(_IS_WIN))
    engine.loadData(MAIN_QML.encode("utf-8"))
    if not engine.rootObjects():
        sys.exit("Failed to load QML.")
    win = engine.rootObjects()[0]
    screen = win.findChild(RemoteScreen, "remoteScreen")
    backend.attach_screen(screen)

    if args.password and (args.host or args.relay):
        if args.relay:
            QTimer.singleShot(200, lambda: backend.connectRelay(args.relay, args.host_id or "", args.password))
        else:
            QTimer.singleShot(200, lambda: backend.connectDirect(args.host, args.port, args.password))

    if getattr(args, "selfhost", 0):
        QTimer.singleShot(300, lambda: backend.startHostDirect(args.selfhost, args.password or "hostpw"))

    if args.selftest:
        got = {"frames": 0}
        backend.frameReady.connect(lambda *_: got.__setitem__("frames", got["frames"] + 1))

        def done():
            print(f"selftest: received {got['frames']} frames")
            app.quit()
        QTimer.singleShot(int(args.selftest * 1000), done)

    sys.exit(app.exec())


# ===========================================================================
#  TKINTER VIEWER  (pure stdlib fallback)
# ===========================================================================
def cmd_viewer_tk(args):
    import tkinter as tk
    from tkinter import messagebox

    _btn = {1: 0, 2: 2, 3: 1}

    if args.relay:
        if not args.host_id:
            sys.exit("--relay requires --id")
        sock = relay_viewer_connect(args.relay, args.host_id)
    else:
        if not args.host:
            sys.exit("give --host (direct) or --relay + --id")
        sock = socket.create_connection((args.host, args.port), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        chan = viewer_handshake(sock, args.password)
        op, payload = chan.recv()
    except ValueError:
        sys.exit("Connection failed: wrong password.")
    except (OSError, ConnectionError) as e:
        sys.exit(f"Connection failed: {e}")
    if op != OP_SCREEN_INFO:
        sys.exit("Protocol error: expected screen info.")
    rw, rh, strip_h = unpack_screen_info(payload)

    lock = threading.Lock()
    fb = FrameBuffer(rw, rh, strip_h)
    stop = threading.Event()
    state = {"dirty": True, "imgref": None}

    root = tk.Tk()
    root.title(f"MeGaADesk - {rw}x{rh}")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    factor = max(1, math.ceil(rw / (0.92 * sw)), math.ceil(rh / (0.92 * sh)))
    label = tk.Label(root, borderwidth=0, highlightthickness=0, bg="black")
    label.pack()
    label.focus_set()

    def send(op_, payload_=b""):
        try:
            chan.send(op_, payload_)
        except (OSError, ConnectionError):
            stop.set()

    def rx(x):
        return max(0, min(rw - 1, x * factor))

    def ry(y):
        return max(0, min(rh - 1, y * factor))

    label.bind("<Motion>", lambda e: send(OP_MOUSE, pack_mouse(M_MOVE, rx(e.x), ry(e.y))))
    for n in (1, 2, 3):
        label.bind(f"<ButtonPress-{n}>", lambda e: (label.focus_set(), send(OP_MOUSE, pack_mouse(M_DOWN, rx(e.x), ry(e.y), _btn.get(e.num, 0)))))
        label.bind(f"<ButtonRelease-{n}>", lambda e: send(OP_MOUSE, pack_mouse(M_UP, rx(e.x), ry(e.y), _btn.get(e.num, 0))))
    label.bind("<MouseWheel>", lambda e: send(OP_MOUSE, pack_mouse(M_WHEEL, 0, 0, int(e.delta / 120))))
    root.bind("<KeyPress>", lambda e: e.keycode and send(OP_KEY, pack_key(True, e.keycode)))
    root.bind("<KeyRelease>", lambda e: e.keycode and send(OP_KEY, pack_key(False, e.keycode)))

    def recv_loop():
        while not stop.is_set():
            try:
                op_, payload_ = chan.recv()
            except (OSError, ConnectionError, ValueError):
                break
            if op_ == OP_FRAME:
                with lock:
                    fb.apply_packed(payload_)
                    state["dirty"] = True
        root.after(0, on_disconnect)

    def render_tick():
        if stop.is_set():
            return
        if state["dirty"]:
            with lock:
                ppm = fb.ppm()
                state["dirty"] = False
            img = tk.PhotoImage(data=ppm)
            if factor > 1:
                img = img.subsample(factor, factor)
            label.config(image=img)
            state["imgref"] = img
        root.after(33, render_tick)

    def on_disconnect():
        if not stop.is_set():
            stop.set()
            messagebox.showinfo("MeGaADesk", "Disconnected from host.")
            root.destroy()

    def on_close():
        stop.set()
        chan.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    threading.Thread(target=recv_loop, daemon=True).start()
    root.after(33, render_tick)
    root.mainloop()


# ===========================================================================
#  COMMANDS
# ===========================================================================
def cmd_host(args):
    if not _IS_WIN:
        sys.exit("The host runs on Windows only (screen capture uses Win32).")
    if args.relay:
        if not args.host_id:
            sys.exit("--relay requires --id")
        run_host_relay(args.password, args.relay, args.host_id)
    else:
        run_host_direct(args.password, args.port, args.bind)


def cmd_relay(args):
    run_relay(args.port, args.bind)


def build_parser():
    p = argparse.ArgumentParser(prog="megaadesk", description="MeGaADesk - single-file remote desktop.")
    sub = p.add_subparsers(dest="command", required=True)

    h = sub.add_parser("host", help="share this Windows PC's screen")
    h.add_argument("--password", required=True)
    h.add_argument("--listen", action="store_true", help="direct/LAN mode (default)")
    h.add_argument("--port", type=int, default=7777)
    h.add_argument("--bind", default="0.0.0.0")
    h.add_argument("--relay", help="relay mode: host:port of the relay server")
    h.add_argument("--id", dest="host_id", help="relay mode: this host's ID")
    h.set_defaults(func=cmd_host)

    v = sub.add_parser("viewer", help="QML remote-control client (needs PySide6)")
    v.add_argument("--password")
    v.add_argument("--host")
    v.add_argument("--port", type=int, default=7777)
    v.add_argument("--relay")
    v.add_argument("--id", dest="host_id")
    v.add_argument("--selftest", type=float, default=0, help=argparse.SUPPRESS)
    v.add_argument("--selfhost", type=int, default=0, help=argparse.SUPPRESS)  # dev: auto-start LAN hosting
    v.set_defaults(func=cmd_viewer)

    t = sub.add_parser("viewer-tk", help="tkinter remote-control client (pure stdlib)")
    t.add_argument("--password", required=True)
    t.add_argument("--host")
    t.add_argument("--port", type=int, default=7777)
    t.add_argument("--relay")
    t.add_argument("--id", dest="host_id")
    t.set_defaults(func=cmd_viewer_tk)

    r = sub.add_parser("relay", help="pairing/forwarding server for a VPS")
    r.add_argument("--port", type=int, default=7000)
    r.add_argument("--bind", default="0.0.0.0")
    r.set_defaults(func=cmd_relay)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
