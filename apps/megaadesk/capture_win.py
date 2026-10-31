"""
MeGaADesk - Windows screen capture (pure stdlib, ctypes + GDI).

No third-party dependencies. Grabs the primary monitor (or the full virtual
desktop) via BitBlt into a device-independent bitmap and returns raw BGRA bytes.

Returned frames are top-down, 32-bit BGRA (4 bytes/pixel), which is what the
frame codec and the tkinter viewer both expect.
"""
import ctypes
from ctypes import wintypes

# --- Win32 handles ---------------------------------------------------------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# GetDIBits / BitBlt constants
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000          # also grab layered/transparent windows
BI_RGB = 0
DIB_RGB_COLORS = 0

# GetSystemMetrics indices
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


CURSOR_SHOWING = 0x00000001
DI_NORMAL = 0x0003


def _set_signatures():
    """Give ctypes proper 64-bit-safe signatures (handles are pointers)."""
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
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]

    # cursor compositing
    user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
    user32.GetCursorInfo.restype = wintypes.BOOL
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
    user32.GetIconInfo.restype = wintypes.BOOL
    user32.CopyIcon.argtypes = [wintypes.HICON]
    user32.CopyIcon.restype = wintypes.HICON
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DrawIconEx.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON,
        ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT,
    ]
    user32.DrawIconEx.restype = wintypes.BOOL


def set_dpi_aware():
    """Report true pixels on scaled displays (avoids blurry, wrong-size grabs)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


_set_signatures()


class ScreenCapturer:
    """Reusable capturer. Allocates GDI objects once and reuses them per frame."""

    def __init__(self, virtual=False):
        set_dpi_aware()
        if virtual:
            self.left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            self.top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            self.width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            self.height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        else:
            self.left = 0
            self.top = 0
            self.width = user32.GetSystemMetrics(SM_CXSCREEN)
            self.height = user32.GetSystemMetrics(SM_CYSCREEN)

        self._screen_dc = user32.GetDC(0)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)
        self._bitmap = gdi32.CreateCompatibleBitmap(self._screen_dc, self.width, self.height)
        gdi32.SelectObject(self._mem_dc, self._bitmap)

        self._bmi = BITMAPINFO()
        self._bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self._bmi.bmiHeader.biWidth = self.width
        self._bmi.bmiHeader.biHeight = -self.height  # negative => top-down
        self._bmi.bmiHeader.biPlanes = 1
        self._bmi.bmiHeader.biBitCount = 32
        self._bmi.bmiHeader.biCompression = BI_RGB

        self._buf = (ctypes.c_char * (self.width * self.height * 4))()
        self.draw_cursor = True

    def _composite_cursor(self):
        """Draw the current mouse cursor into the memory DC (BitBlt omits it)."""
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not user32.GetCursorInfo(ctypes.byref(ci)):
            return
        if not (ci.flags & CURSOR_SHOWING) or not ci.hCursor:
            return
        hicon = user32.CopyIcon(ci.hCursor)  # snapshot so it can't change mid-draw
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
        """Capture one frame. Returns raw BGRA bytes of length width*height*4."""
        gdi32.BitBlt(
            self._mem_dc, 0, 0, self.width, self.height,
            self._screen_dc, self.left, self.top, SRCCOPY | CAPTUREBLT,
        )
        if self.draw_cursor:
            self._composite_cursor()
        gdi32.GetDIBits(
            self._mem_dc, self._bitmap, 0, self.height,
            self._buf, ctypes.byref(self._bmi), DIB_RGB_COLORS,
        )
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


if __name__ == "__main__":
    import time

    cap = ScreenCapturer()
    print(f"screen: {cap.width}x{cap.height}")

    # Warm up + time a few grabs.
    t0 = time.perf_counter()
    n = 10
    for _ in range(n):
        frame = cap.grab()
    dt = (time.perf_counter() - t0) / n
    nonzero = sum(1 for b in frame[::997] if b) / len(frame[::997])
    print(f"frame bytes: {len(frame)}  avg grab: {dt*1000:.1f} ms  ~{1/dt:.0f} fps")
    print(f"non-black sample ratio: {nonzero:.2%}")

    # Save a 24-bit BMP proof (pure stdlib) so we can eyeball it.
    import struct

    w, h = cap.width, cap.height
    row_padded = (w * 3 + 3) & ~3
    pixel_data = bytearray(row_padded * h)
    src = frame
    for y in range(h):
        srow = y * w * 4
        drow = (h - 1 - y) * row_padded  # BMP is bottom-up
        for x in range(w):
            b = src[srow + x * 4 + 0]
            g = src[srow + x * 4 + 1]
            r = src[srow + x * 4 + 2]
            di = drow + x * 3
            pixel_data[di] = b
            pixel_data[di + 1] = g
            pixel_data[di + 2] = r
    file_size = 54 + len(pixel_data)
    header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixel_data), 2835, 2835, 0, 0)
    with open("_capture_proof.bmp", "wb") as f:
        f.write(header + dib + bytes(pixel_data))
    print("wrote _capture_proof.bmp")
    cap.close()
