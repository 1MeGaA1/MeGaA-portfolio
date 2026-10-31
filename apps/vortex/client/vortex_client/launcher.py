"""Launch games/apps from the catalog, watch them, and kill them when the session ends."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Callable, Optional

import psutil

log = logging.getLogger("vortex.launcher")

STARTUP_GRACE = 90.0   # seconds a launcher (Steam, Riot) may take before the real game process appears


class Launcher:
    def __init__(self, catalog: dict, on_event: Callable[[str, str, dict], None]):
        self.catalog = catalog
        self.on_event = on_event
        self._tracked: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._stop = False

    def start(self) -> None:
        threading.Thread(target=self._monitor, name="vortex-launcher", daemon=True).start()

    def stop(self) -> None:
        self._stop = True

    # ------------------------------------------------------------ catalog
    def find(self, kind: str, name: str) -> Optional[dict]:
        bucket = self.catalog.get("games" if kind == "game" else "apps", {})
        wanted = name.strip().lower()
        for key, entry in bucket.items():
            if key.lower() == wanted:
                return entry
        return None

    def running(self) -> list[str]:
        with self._lock:
            return [n for n, t in self._tracked.items() if t["state"] == "running"]

    # ------------------------------------------------------------ launch
    def launch(self, kind: str, name: str) -> dict:
        entry = self.find(kind, name)
        if not entry:
            return {"ok": False, "error": "not_installed", "message": f"{name} is not set up on this PC."}
        pid: Optional[int] = None
        try:
            if entry.get("exe"):
                exe = os.path.expandvars(entry["exe"])
                if not os.path.exists(exe):
                    return {"ok": False, "error": "missing_exe", "message": f"{name} is not installed here."}
                proc = subprocess.Popen([exe, *entry.get("args", [])], cwd=entry.get("cwd") or os.path.dirname(exe))
                pid = proc.pid
            elif entry.get("launch"):
                os.startfile(entry["launch"])   # steam://, riot, epic, discord://, spotify:
            else:
                return {"ok": False, "error": "bad_entry", "message": f"{name} has no launch target in catalog.json."}
        except OSError as exc:
            log.error("launch %s failed: %s", name, exc)
            return {"ok": False, "error": "launch_failed", "message": f"Could not start {name}: {exc}"}
        with self._lock:
            self._tracked[name] = {"pid": pid, "process": entry.get("process"), "kind": kind,
                                   "started": time.time(), "state": "starting"}
        log.info("launched %s (%s) pid=%s", name, kind, pid)
        self.on_event(name, "starting", {"kind": kind})
        return {"ok": True}

    # ------------------------------------------------------------ watch
    @staticmethod
    def _pids_by_name(proc_name: str) -> list[int]:
        wanted = proc_name.lower()
        pids = []
        for p in psutil.process_iter(["name"]):
            try:
                if (p.info["name"] or "").lower() == wanted:
                    pids.append(p.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return pids

    def _is_alive(self, t: dict) -> bool:
        pid = t.get("pid")
        if pid and psutil.pid_exists(pid):
            try:
                if psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if t.get("process") and self._pids_by_name(t["process"]):
            return True
        return False

    def _monitor(self) -> None:
        while not self._stop:
            time.sleep(2)
            with self._lock:
                items = list(self._tracked.items())
            for name, t in items:
                alive = self._is_alive(t)
                if alive and t["state"] == "starting":
                    t["state"] = "running"
                    self.on_event(name, "running", {"kind": t["kind"]})
                elif not alive:
                    if t["state"] == "starting" and time.time() - t["started"] < STARTUP_GRACE:
                        continue   # launcher still spinning up (or a URI we cannot track)
                    with self._lock:
                        self._tracked.pop(name, None)
                    self.on_event(name, "exited", {"kind": t["kind"], "tracked": bool(t.get("pid") or t.get("process"))})

    # ------------------------------------------------------------ kill
    @staticmethod
    def _kill_tree(pid: int) -> None:
        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.Error:
                pass
        try:
            parent.kill()
        except psutil.Error:
            pass

    def kill_all(self) -> None:
        """Session over: close everything we launched (and their named processes)."""
        with self._lock:
            items = list(self._tracked.items())
            self._tracked.clear()
        for name, t in items:
            if t.get("pid"):
                self._kill_tree(t["pid"])
            if t.get("process"):
                for pid in self._pids_by_name(t["process"]):
                    self._kill_tree(pid)
            log.info("closed %s", name)
