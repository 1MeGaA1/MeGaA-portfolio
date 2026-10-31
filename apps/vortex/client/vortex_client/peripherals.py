"""Best-effort peripheral check for the account card: screen, mouse, keyboard."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import logging

log = logging.getLogger("vortex.peripherals")

RIM_TYPEMOUSE, RIM_TYPEKEYBOARD, RIM_TYPEHID = 0, 1, 2
ENUM_CURRENT_SETTINGS = -1


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", w.HANDLE), ("dwType", w.DWORD)]


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", w.WCHAR * 32), ("dmSpecVersion", w.WORD), ("dmDriverVersion", w.WORD),
        ("dmSize", w.WORD), ("dmDriverExtra", w.WORD), ("dmFields", w.DWORD),
        ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", w.DWORD), ("dmDisplayFixedOutput", w.DWORD),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short), ("dmFormName", w.WCHAR * 32),
        ("dmLogPixels", w.WORD), ("dmBitsPerPel", w.DWORD), ("dmPelsWidth", w.DWORD), ("dmPelsHeight", w.DWORD),
        ("dmDisplayFlags", w.DWORD), ("dmDisplayFrequency", w.DWORD),
        ("dmICMMethod", w.DWORD), ("dmICMIntent", w.DWORD), ("dmMediaType", w.DWORD), ("dmDitherType", w.DWORD),
        ("dmReserved1", w.DWORD), ("dmReserved2", w.DWORD), ("dmPanningWidth", w.DWORD), ("dmPanningHeight", w.DWORD),
    ]


def raw_input_counts() -> tuple[int, int, int]:
    user32 = ctypes.windll.user32
    count = w.UINT(0)
    size = ctypes.sizeof(RAWINPUTDEVICELIST)
    if user32.GetRawInputDeviceList(None, ctypes.byref(count), size) == 0xFFFFFFFF or count.value == 0:
        return 0, 0, 0
    devices = (RAWINPUTDEVICELIST * count.value)()
    got = user32.GetRawInputDeviceList(devices, ctypes.byref(count), size)
    if got == 0xFFFFFFFF:
        return 0, 0, 0
    mice = sum(1 for d in devices[:got] if d.dwType == RIM_TYPEMOUSE)
    keyboards = sum(1 for d in devices[:got] if d.dwType == RIM_TYPEKEYBOARD)
    hid = sum(1 for d in devices[:got] if d.dwType == RIM_TYPEHID)
    return mice, keyboards, hid


def display_mode() -> tuple[int, int, int]:
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)
    return 0, 0, 0


def snapshot() -> dict:
    try:
        mice, keyboards, _hid = raw_input_counts()
    except Exception as exc:  # pragma: no cover - ctypes edge cases
        log.debug("raw input failed: %s", exc)
        mice = keyboards = 0
    try:
        width, height, hz = display_mode()
    except Exception as exc:  # pragma: no cover
        log.debug("display mode failed: %s", exc)
        width = height = hz = 0
    return {
        "screen": {"status": "ok" if hz else "warn", "meta": f"{hz}Hz" if hz else "—", "detail": f"{width}x{height}"},
        "mouse": {"status": "ok" if mice else "missing", "meta": "OK" if mice else "NOT FOUND"},
        "keyboard": {"status": "ok" if keyboards else "missing", "meta": "OK" if keyboards else "NOT FOUND"},
        "headset": {"status": "unknown", "meta": "—"},
    }
