"""Start the Vortex server.

    python run_server.py                 # data/server.json decides host/port
    python run_server.py --port 9000
    set VORTEX_DATA_DIR=D:\\vortex-data   # move the database somewhere else
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from vortex_server.config import DATA_DIR, load_settings  # noqa: E402
from vortex_server.main import create_app  # noqa: E402


def lan_addresses() -> list[str]:
    addrs: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addrs.add(ip)
    except socket.gaierror:
        pass
    return sorted(addrs)


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("" if host in ("0.0.0.0", "") else host, port))
            return True
        except OSError:
            return False


def setup_logging(debug: bool) -> None:
    """Console + data/server.log. The file matters when the server is started at boot by
    Task Scheduler (no console to look at); it rotates at 5 MB, keeping 3 old files."""
    from logging.handlers import RotatingFileHandler
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(DATA_DIR / "server.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as exc:
        root.warning("cannot write server.log: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vortex cafe server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.debug:
        settings.debug = True

    setup_logging(settings.debug)
    if not port_free(settings.host, settings.port):
        # uvicorn would log the bind error and exit 1; exit 2 tells serve_forever.bat to stop
        # instead of restarting into the same collision every 5 seconds.
        print(f"\n  Port {settings.port} is already in use: the Vortex server is probably running already.")
        sys.exit(2)
    app = create_app(settings)

    print("=" * 60)
    print(f"  VORTEX SERVER  -  {settings.cafe_name}")
    print(f"  Admin panel : http://localhost:{settings.port}/admin/")
    for ip in lan_addresses():
        print(f"                http://{ip}:{settings.port}/admin/   (LAN)")
    print(f"  Stations    : ws://<this-pc-ip>:{settings.port}/ws/station")
    print(f"  Database    : {settings.db_path}")
    print(f"  Log file    : {DATA_DIR / 'server.log'}")
    print("=" * 60)
    uvicorn.run(app, host=settings.host, port=settings.port,
                log_level="debug" if settings.debug else "info", log_config=None)


if __name__ == "__main__":
    main()
