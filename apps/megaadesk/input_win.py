"""
MeGaADesk - Windows input injection (pure stdlib, ctypes SendInput).

Applies remote mouse/keyboard events on the host. Mouse coordinates arrive in
remote-screen pixels and are normalized to the 0..65535 absolute range that
SendInput expects for the primary monitor.
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

ULONG_PTR = wintypes.WPARAM  # pointer-sized, matches ULONG_PTR

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

# Virtual keys that must carry the extended-key flag to behave correctly.
_EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,  # PgUp/PgDn/End/Home/arrows
    0x2D, 0x2E,  # Insert, Delete
    0x5B, 0x5C,  # Left/Right Win
    0xA3, 0xA5,  # Right Ctrl, Right Alt
    0x90,        # NumLock
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send(inp):
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
        mi = MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0)
        _send(INPUT(INPUT_MOUSE, _INPUTunion(mi=mi)))

    def button(self, down, btn, x=None, y=None):
        """btn: 0=left, 1=right, 2=middle."""
        if x is not None:
            self.move(x, y)
        flags = {
            (0, True): MOUSEEVENTF_LEFTDOWN, (0, False): MOUSEEVENTF_LEFTUP,
            (1, True): MOUSEEVENTF_RIGHTDOWN, (1, False): MOUSEEVENTF_RIGHTUP,
            (2, True): MOUSEEVENTF_MIDDLEDOWN, (2, False): MOUSEEVENTF_MIDDLEUP,
        }.get((btn, down))
        if flags is None:
            return
        mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
        _send(INPUT(INPUT_MOUSE, _INPUTunion(mi=mi)))

    def wheel(self, notches):
        mi = MOUSEINPUT(0, 0, notches * WHEEL_DELTA & 0xFFFFFFFF, MOUSEEVENTF_WHEEL, 0, 0)
        _send(INPUT(INPUT_MOUSE, _INPUTunion(mi=mi)))

    def key(self, down, vk):
        flags = 0 if down else KEYEVENTF_KEYUP
        if vk in _EXTENDED_VKS:
            flags |= KEYEVENTF_EXTENDEDKEY
        ki = KEYBDINPUT(vk, 0, flags, 0, 0)
        _send(INPUT(INPUT_KEYBOARD, _INPUTunion(ki=ki)))


if __name__ == "__main__":
    # Safe self-test: wiggle the cursor in a small square, no clicks.
    import time
    inj = InputInjector(user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    for (x, y) in [(200, 200), (400, 200), (400, 400), (200, 400), (200, 200)]:
        inj.move(x, y)
        time.sleep(0.15)
    print("ok: cursor wiggled (no clicks sent)")
