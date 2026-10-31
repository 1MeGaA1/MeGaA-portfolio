"""
MeGaADesk relay server - run this on a public VPS.

It pairs a host and a viewer that use the same ID and then blindly forwards
bytes between them. All application traffic is end-to-end encrypted by the host
and viewer, so the relay only ever sees the public salt, the ID, and ciphertext.
It cannot see your screen or your keystrokes.

Flow:
  * A host connects and registers ID X -> parked as "waiting".
  * A viewer connects and joins ID X -> the two sockets are pumped together
    until either side disconnects.

Usage (on the VPS):
  python relay.py --port 7000

Then open that TCP port in the firewall. Pure stdlib - copy this one file over.
"""
import argparse
import socket
import sys
import threading

from common import protocol
from common import relaylink

waiting = {}          # host_id -> socket (a host waiting for a viewer)
waiting_lock = threading.Lock()


def _pump(a, b):
    """Forward bytes a<->b until one side closes; then close both."""
    def one_way(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    t = threading.Thread(target=one_way, args=(a, b), daemon=True)
    t.start()
    one_way(b, a)
    for s in (a, b):
        try:
            s.close()
        except OSError:
            pass


def handle(sock, addr):
    try:
        reg = protocol.recv_frame(sock, max_len=1024)
    except (OSError, protocol.ProtocolError):
        sock.close()
        return
    role, host_id = reg[:1], reg[1:].decode("utf-8", "replace")
    if not host_id:
        protocol.send_frame(sock, b"\x00missing id")
        sock.close()
        return

    if role == relaylink.ROLE_HOST:
        with waiting_lock:
            old = waiting.pop(host_id, None)
            waiting[host_id] = sock
        if old is not None:
            try:
                old.close()  # a newer host replaces a stale registration
            except OSError:
                pass
        try:
            protocol.send_frame(sock, b"\x01")
        except OSError:
            with waiting_lock:
                if waiting.get(host_id) is sock:
                    waiting.pop(host_id, None)
            sock.close()
            return
        print(f"[+] host '{host_id}' registered from {addr[0]}")
        # Parked. The viewer's handler will pop and pump this socket.
        return

    if role == relaylink.ROLE_VIEWER:
        with waiting_lock:
            hsock = waiting.pop(host_id, None)
        if hsock is None:
            protocol.send_frame(sock, b"\x00no host with that ID is online")
            sock.close()
            print(f"[-] viewer wanted '{host_id}' but no host waiting ({addr[0]})")
            return
        try:
            protocol.send_frame(sock, b"\x01")
        except OSError:
            try:
                hsock.close()
            except OSError:
                pass
            sock.close()
            return
        print(f"[*] paired '{host_id}': host <-> viewer {addr[0]}")
        _pump(hsock, sock)
        print(f"[x] session '{host_id}' ended")
        return

    protocol.send_frame(sock, b"\x00unknown role")
    sock.close()


def main():
    ap = argparse.ArgumentParser(description="MeGaADesk relay server (run on a VPS).")
    ap.add_argument("--port", type=int, default=7000)
    ap.add_argument("--bind", default="0.0.0.0")
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.bind, args.port))
    srv.listen(64)
    print(f"MeGaADesk relay listening on {args.bind}:{args.port}")
    while True:
        sock, addr = srv.accept()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=handle, args=(sock, addr), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
