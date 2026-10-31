"""Runs the JS bridge test (tests/bridge_kiosk_test.js) through Node.

Verifies vortex-bridge.js picks kiosk vs browser mode correctly and routes calls
to window.pywebview.api in kiosk mode. Skipped if Node is not installed.
"""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS_TEST = HERE / "bridge_kiosk_test.js"


class BridgeTest(unittest.TestCase):
    def test_bridge_mode_detection_and_routing(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        proc = subprocess.run([node, str(JS_TEST)], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, f"bridge test failed:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("checks passed", proc.stdout)


if __name__ == "__main__":
    unittest.main()
