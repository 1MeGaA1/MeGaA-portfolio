"""Client unit tests (no window, no server).

Run from the client/ folder:  python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vortex_client import config
from vortex_client.launcher import Launcher
from vortex_client.link import OFFLINE_REPLY, ServerLink


class ConfigTests(unittest.TestCase):
    def test_config_roundtrip_and_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "client.json"
            with mock.patch.object(config, "CONFIG_PATH", path):
                cfg = config.load_config()          # creates the file with defaults
                self.assertTrue(path.exists())
                self.assertTrue(cfg.station_name)   # hostname fallback
                cfg.server = "ws://192.168.1.10:8787"
                cfg.station_key = "abc"
                config.save_config(cfg)
                again = config.load_config()
                self.assertEqual(again.server, "ws://192.168.1.10:8787")
                self.assertEqual(again.station_key, "abc")

    def test_catalog_created_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            with mock.patch.object(config, "CATALOG_PATH", path):
                cat = config.load_catalog()
                self.assertIn("Counter-Strike 2", cat["games"])
                self.assertIn("Chrome", cat["apps"])
                self.assertEqual(json.loads(path.read_text("utf-8"))["games"], cat["games"])


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.launcher = Launcher(
            {"games": {"Valorant": {"launch": "riot:valorant", "process": "VALORANT.exe"}},
             "apps": {"Chrome": {"exe": "Z:/definitely/missing/chrome.exe"}}},
            lambda name, state, extra: self.events.append((name, state)),
        )

    def test_find_is_case_insensitive(self) -> None:
        self.assertIsNotNone(self.launcher.find("game", "valorant"))
        self.assertIsNotNone(self.launcher.find("app", "CHROME"))
        self.assertIsNone(self.launcher.find("game", "Chrome"))

    def test_unknown_and_missing_targets_fail_cleanly(self) -> None:
        res = self.launcher.launch("game", "Fortnite")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "not_installed")
        res = self.launcher.launch("app", "Chrome")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "missing_exe")
        self.assertEqual(self.events, [])

    def test_uri_launch_is_tracked(self) -> None:
        with mock.patch("vortex_client.launcher.os.startfile", create=True) as startfile:
            res = self.launcher.launch("game", "Valorant")
        self.assertTrue(res["ok"])
        startfile.assert_called_once_with("riot:valorant")
        self.assertEqual(self.events, [("Valorant", "starting")])
        self.assertEqual(self.launcher.running(), [])   # not confirmed running until the process shows up


class LinkTests(unittest.TestCase):
    def test_request_while_offline_returns_offline_reply(self) -> None:
        link = ServerLink(config.ClientConfig(), lambda kind, msg: None)
        self.assertEqual(link.request({"type": "login"}), OFFLINE_REPLY)
        self.assertFalse(link.online)


class CloseBehaviourTests(unittest.TestCase):
    """The launcher must close when the user closes it in windowed mode, and must NOT be
    closable by a customer in kiosk mode. This is the regression guard for that bug."""

    def _make_app(self, **cfg_over):
        from vortex_client.app import VortexApp, EXIT_RESTART
        app = VortexApp.__new__(VortexApp)     # skip __init__ (no logging/window side effects)
        app.cfg = config.ClientConfig(**cfg_over)
        app._exiting = False
        app.exit_code = EXIT_RESTART
        # stop() calls in _on_closing must be safe on un-started components
        app.lockdown = type("L", (), {"stop": lambda self: None})()
        app.link = type("K", (), {"stop": lambda self: None})()
        app.launcher = type("J", (), {"stop": lambda self: None})()
        return app

    def test_windowed_close_is_allowed_and_does_not_relaunch(self) -> None:
        app = self._make_app(kiosk=False)
        self.assertTrue(app._on_closing())          # allow the close
        self.assertEqual(app.exit_code, 0)          # code 0 -> watchdog stops, no relaunch
        self.assertTrue(app._exiting)

    def test_kiosk_close_is_blocked(self) -> None:
        app = self._make_app(kiosk=True, debug=False)
        self.assertFalse(app._on_closing())         # customer cannot close the kiosk
        self.assertFalse(app._exiting)

    def test_kiosk_debug_close_is_allowed(self) -> None:
        app = self._make_app(kiosk=True, debug=True)
        self.assertTrue(app._on_closing())

    def test_close_after_admin_exit_is_allowed(self) -> None:
        app = self._make_app(kiosk=True, debug=False)
        app._exiting = True                          # exit() already ran (admin PIN / restart)
        self.assertTrue(app._on_closing())


if __name__ == "__main__":
    unittest.main()
