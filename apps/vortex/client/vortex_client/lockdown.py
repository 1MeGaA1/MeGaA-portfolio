"""Kiosk lockdown: a low-level keyboard hook plus a foreground guard.

Blocked always (kiosk mode):   Win keys, Alt+F4, Ctrl+Shift+Esc (task manager)
Blocked while locked (no session):  Alt+Tab, Alt+Esc, Ctrl+Esc
Ctrl+Shift+Q  -> admin escape (PIN dialog), handled here so it works even if the page is broken.

Ctrl+Alt+Del cannot be intercepted by any application; see docs/INSTALL.md for the
registry policies (DisableTaskMgr, shell replacement) that close that gap.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("vortex.lockdown")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_ALTDOWN = 0x20
VK_TAB, VK_ESCAPE, VK_SHIFT, VK_CONTROL, VK_MENU = 0x09, 0x1B, 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN, VK_F4, VK_Q = 0x5B, 0x5C, 0x73, 0x51
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9

HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, w.WPARAM, w.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", w.DWORD), ("scanCode", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


user32.SetWindowsHookExW.restype = w.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD]
user32.CallNextHookEx.restype = ctypes.c_long
user32.CallNextHookEx.argtypes = [w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM]
user32.GetForegroundWindow.restype = w.HWND
user32.FindWindowW.restype = w.HWND
user32.SetForegroundWindow.argtypes = [w.HWND]
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [w.HWND]


class Lockdown:
    def __init__(self, enabled: bool, block_alt_tab_in_session: bool, on_admin_escape: Callable[[], None]):
        self.enabled = enabled
        self.block_alt_tab_in_session = block_alt_tab_in_session
        self.on_admin_escape = on_admin_escape
        self.locked = True                 # no session -> keep the kiosk in front, block switching
        self.hwnd: Optional[int] = None
        self._hook = None
        self._proc = None                  # keep the callback alive (ctypes)
        self._hook_thread_id = 0
        self._stop = False
        self._last_escape = 0.0

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if not self.enabled:
            log.info("kiosk lockdown disabled (client.json kiosk=false)")
            return
        threading.Thread(target=self._hook_thread, name="vortex-kbhook", daemon=True).start()
        threading.Thread(target=self._guard_thread, name="vortex-guard", daemon=True).start()

    def stop(self) -> None:
        self._stop = True
        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None

    def find_window(self, title: str, tries: int = 20) -> Optional[int]:
        for _ in range(tries):
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                self.hwnd = int(hwnd)
                log.info("kiosk window hwnd=%s", self.hwnd)
                return self.hwnd
            time.sleep(0.25)
        log.warning("kiosk window '%s' not found; foreground guard idle", title)
        return None

    # ------------------------------------------------------------ keyboard hook
    def _should_block(self, vk: int, flags: int, wparam: int) -> bool:
        alt = bool(flags & LLKHF_ALTDOWN)
        ctrl = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
        shift = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
        if vk in (VK_LWIN, VK_RWIN):
            return True
        if vk == VK_ESCAPE and ctrl and shift:          # task manager
            return True
        if vk == VK_F4 and alt:                         # never close the kiosk this way
            return True
        if vk == VK_Q and ctrl and shift:               # admin escape
            if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN) and time.time() - self._last_escape > 1.0:
                self._last_escape = time.time()
                threading.Thread(target=self.on_admin_escape, daemon=True).start()
            return True
        if self.locked or self.block_alt_tab_in_session:
            if vk == VK_TAB and alt:                    # Alt+Tab
                return True
            if vk == VK_ESCAPE and (alt or ctrl):       # Alt+Esc, Ctrl+Esc
                return True
        return False

    def _hook_thread(self) -> None:
        def proc(n_code: int, wparam: int, lparam: int) -> int:
            if n_code == HC_ACTION and wparam in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                try:
                    if self._should_block(kb.vkCode, kb.flags, wparam):
                        return 1
                except Exception:
                    log.exception("hook callback failed")
            return user32.CallNextHookEx(self._hook, n_code, wparam, lparam)

        self._proc = HOOKPROC(proc)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._hook:
            log.error("SetWindowsHookEx failed: %s", ctypes.GetLastError())
            return
        self._hook_thread_id = kernel32.GetCurrentThreadId()
        log.info("keyboard hook installed")
        msg = w.MSG()
        while not self._stop and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ------------------------------------------------------------ foreground guard
    def bring_to_front(self) -> None:
        if not self.hwnd:
            return
        try:
            # The ALT tap lets a background process call SetForegroundWindow successfully.
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)
            user32.BringWindowToTop(self.hwnd)
        except Exception as exc:
            log.debug("bring_to_front failed: %s", exc)

    def _guard_thread(self) -> None:
        while not self._stop:
            time.sleep(0.4)
            if not self.locked or not self.hwnd:
                continue
            try:
                if user32.GetForegroundWindow() != self.hwnd:
                    self.bring_to_front()
            except Exception:
                pass
