"""Start the native Vortex kiosk (PySide6 + QML)."""
import sys
from pathlib import Path

# reuse the backend package from the sibling web client
sys.path.insert(0, str(Path(__file__).resolve().parent))          # client-native (vortex_native)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "client"))  # client (vortex_client)

from vortex_native.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
