"""
MeGaADesk host (agent) - the machine being controlled.

Captures the screen, streams changed strips to the viewer, and applies the
viewer's mouse/keyboard events. Two transports:

  direct : listen on a TCP port; the viewer connects straight to us (LAN).
  relay  : dial out to a relay server and register an ID (works over the
           internet through NAT). See relay.py.

Usage:
  python host.py --password SECRET --listen --port 7777
  python host.py --password SECRET --relay relay.example.com:7000 --id MYPC01
"""
import argparse
import socket
import sys
import threading
import time

import capture_win
import input_win
from common import framec, protocol

TARGET_FPS = 15


def _capture_loop(chan, cap, enc, stop):
    """Grab -> diff -> send changed strips, capped at TARGET_FPS."""
    period = 1.0 / TARGET_FPS
    enc.reset()  # first frame is a full keyframe
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            strips = enc.encode(cap.grab())
            if strips:
                chan.send(protocol.OP_FRAME, enc.pack(strips))
        except (OSError, ConnectionError):
            break
        dt = time.perf_counter() - t0
        if dt < period:
            stop.wait(period - dt)


def _input_loop(chan, inj, stop):
    """Receive and apply mouse/keyboard events; answer pings."""
    while not stop.is_set():
        try:
            op, payload = chan.recv()
        except (OSError, ConnectionError, ValueError):
            break
        if op == protocol.OP_MOUSE:
            kind, x, y, data = protocol.unpack_mouse(payload)
            if kind == protocol.M_MOVE:
                inj.move(x, y)
            elif kind == protocol.M_DOWN:
                inj.button(True, data, x, y)
            elif kind == protocol.M_UP:
                inj.button(False, data, x, y)
            elif kind == protocol.M_WHEEL:
                inj.wheel(data)
        elif op == protocol.OP_KEY:
            down, vk = protocol.unpack_key(payload)
            inj.key(down, vk)
        elif op == protocol.OP_PING:
            chan.send(protocol.OP_PONG)


def serve_session(sock, password):
    """Run one viewer session over an already-connected transport socket."""
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        chan = protocol.host_handshake(sock, password)
    except (protocol.ProtocolError, ValueError, ConnectionError) as e:
        print(f"  handshake rejected: {e}")
        sock.close()
        return

    cap = capture_win.ScreenCapturer()
    inj = input_win.InputInjector(cap.width, cap.height)
    chan.send(protocol.OP_SCREEN_INFO, protocol.pack_screen_info(cap.width, cap.height, framec.STRIP_H))
    enc = framec.FrameEncoder(cap.width, cap.height)
    print(f"  viewer connected - streaming {cap.width}x{cap.height}")

    stop = threading.Event()
    tin = threading.Thread(target=_input_loop, args=(chan, inj, stop), daemon=True)
    tin.start()
    try:
        _capture_loop(chan, cap, enc, stop)  # runs until disconnect
    finally:
        stop.set()
        cap.close()
        chan.close()
        print("  viewer disconnected")


def run_direct(password, port, bind):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(1)
    print(f"MeGaADesk host listening on {bind}:{port} (direct). Waiting for a viewer...")
    while True:
        sock, addr = srv.accept()
        print(f"connection from {addr[0]}:{addr[1]}")
        serve_session(sock, password)


def run_relay(password, relay, host_id):
    from common import relaylink
    print(f"MeGaADesk host registering as '{host_id}' on relay {relay}")
    while True:
        try:
            sock = relaylink.host_connect(relay, host_id)
        except OSError as e:
            print(f"  relay connect failed: {e}; retrying in 3s")
            time.sleep(3)
            continue
        print("  registered; waiting for a viewer...")
        serve_session(sock, password)


def main():
    ap = argparse.ArgumentParser(description="MeGaADesk host (screen sharer).")
    ap.add_argument("--password", required=True, help="session password the viewer must enter")
    ap.add_argument("--listen", action="store_true", help="direct mode: listen on a TCP port (LAN)")
    ap.add_argument("--port", type=int, default=7777, help="direct-mode listen port")
    ap.add_argument("--bind", default="0.0.0.0", help="direct-mode bind address")
    ap.add_argument("--relay", help="relay mode: host:port of the relay server")
    ap.add_argument("--id", dest="host_id", help="relay mode: this host's connect ID")
    args = ap.parse_args()

    if args.relay:
        if not args.host_id:
            ap.error("--relay requires --id")
        run_relay(args.password, args.relay, args.host_id)
    else:
        run_direct(args.password, args.port, args.bind)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
