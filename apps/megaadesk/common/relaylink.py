"""
MeGaADesk - relay client helpers.

Both host and viewer dial OUT to the relay (works through NAT), send a one-frame
registration, and read a one-frame status. After that the relay forwards raw
bytes between the paired peers and steps out of the way - so the end-to-end
MeGaADesk handshake and all encrypted traffic pass through untouched. The relay
never has the password and cannot decrypt anything.

Control frames (length-prefixed, see protocol.send_frame/recv_frame):
    registration : role(1) + id           role = b'H' (host) or b'J' (viewer)
    status       : b'\\x01'               = OK / paired-ready
                   b'\\x00' + reason       = rejected
"""
import socket

from . import protocol

ROLE_HOST = b"H"
ROLE_VIEWER = b"J"


def split_addr(addr, default_port=7000):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def _register(sock, role, host_id):
    protocol.send_frame(sock, role + host_id.encode("utf-8"))
    status = protocol.recv_frame(sock)
    if not status or status[0] != 1:
        reason = status[1:].decode("utf-8", "replace") if len(status) > 1 else "rejected"
        raise ConnectionError(f"relay rejected connection: {reason}")


def host_connect(relay, host_id, timeout=10):
    """Register as a host and wait to be paired. Returns the transport socket."""
    host, port = split_addr(relay)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(None)
    _register(sock, ROLE_HOST, host_id)
    return sock


def viewer_connect(relay, host_id, timeout=10):
    """Ask the relay to pair us with a waiting host ID. Returns the socket."""
    host, port = split_addr(relay)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(None)
    _register(sock, ROLE_VIEWER, host_id)
    return sock
