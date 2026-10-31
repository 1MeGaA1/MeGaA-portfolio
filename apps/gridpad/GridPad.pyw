"""Console-free launcher: double-click this file to open GridPad with no terminal window.

It relaunches itself through the project's own .venv (pythonw.exe), so it works no
matter which Python is associated with .pyw files.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"

in_venv = Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
if VENV_PYTHONW.exists() and not in_venv:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(VENV_PYTHONW), str(ROOT / "gridpad.py"), *sys.argv[1:]],
                     cwd=str(ROOT), creationflags=flags)
    sys.exit(0)

sys.path.insert(0, str(ROOT))
try:
    from app.main import main
except ImportError:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            "GridPad's environment is missing. In the GridPad folder run:\n\n"
            "python -m venv .venv\n.venv\\Scripts\\pip install -r requirements.txt",
            "GridPad", 0x10)
    sys.exit(1)

sys.exit(main())
