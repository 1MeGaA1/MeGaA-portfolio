"""Start the Vortex kiosk client (same as `python -m vortex_client`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vortex_client.app import main  # noqa: E402

main()
