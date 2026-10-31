"""Pretend to be a kiosk PC, for demos and for testing the admin panel.

    python tools/demo_station.py                      # connects as "DEMO-01"
    python tools/demo_station.py --name PC-07 --server ws://192.168.1.10:8787
    python tools/demo_station.py --login nova@vortex.gg --password secret   # logs in after connecting

Prints every message the server sends. Ctrl+C to disconnect.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket

import websockets


async def run(server: str, name: str, key: str, login: str | None, password: str | None) -> None:
    url = server.rstrip("/") + "/ws/station"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "hello", "station_name": name, "station_key": key,
                                  "hostname": socket.gethostname(), "version": "demo"}))
        welcome = json.loads(await ws.recv())
        print("<-", json.dumps(welcome, indent=1)[:600], flush=True)
        if welcome.get("type") != "welcome":
            return
        if welcome.get("station_key"):
            print(f"   station key issued: {welcome['station_key']}  (pass --key next time)", flush=True)

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(welcome["config"]["heartbeat_seconds"])
                await ws.send(json.dumps({"type": "heartbeat"}))

        hb = asyncio.create_task(heartbeat())
        if login:
            await ws.send(json.dumps({"type": "login", "req_id": 1, "login": login, "password": password or ""}))
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "pong":
                    continue
                print("<-", json.dumps(msg)[:400], flush=True)
        finally:
            hb.cancel()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="ws://127.0.0.1:8787")
    parser.add_argument("--name", default="DEMO-01")
    parser.add_argument("--key", default="")
    parser.add_argument("--login")
    parser.add_argument("--password")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.server, args.name, args.key, args.login, args.password))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
