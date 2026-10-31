"""
MeGaADesk - wire protocol: framing, secure channel, and handshake.

Every message on the wire is length-prefixed: 4-byte big-endian length + body.
Before the handshake, bodies are plaintext (only the salt is exchanged). After
key derivation, every body is sealed with common.crypto (encrypt-then-MAC), so
the relay - which only forwards frames - never sees plaintext.

Application message = opcode(1 byte) + payload, then sealed as one blob.
"""
import socket
import struct
import threading

from . import crypto

# --- opcodes ---------------------------------------------------------------
OP_HELLO = 1        # viewer -> host : proves password (must decrypt cleanly)
OP_SCREEN_INFO = 2  # host -> viewer : width, height, strip_h
OP_FRAME = 3        # host -> viewer : packed changed strips
OP_MOUSE = 4        # viewer -> host : mouse event
OP_KEY = 5          # viewer -> host : key event
OP_PING = 6
OP_PONG = 7
OP_CLIPBOARD = 8    # reserved for later

MAGIC = b"MeGaADesk/1"


class ProtocolError(Exception):
    pass


# --- raw length-prefixed frames -------------------------------------------
def send_frame(sock, data):
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed connection")
        buf += chunk
    return bytes(buf)


def recv_frame(sock, max_len=64 * 1024 * 1024):
    (n,) = struct.unpack(">I", _recv_exact(sock, 4))
    if n > max_len:
        raise ProtocolError(f"frame too large: {n}")
    return _recv_exact(sock, n)


# --- encrypted application channel ----------------------------------------
class SecureChannel:
    def __init__(self, sock, enc_key, mac_key):
        self.sock = sock
        self._ek = enc_key
        self._mk = mac_key
        self._send_lock = threading.Lock()

    def send(self, opcode, payload=b""):
        body = bytes([opcode]) + payload
        blob = crypto.seal(self._ek, self._mk, body)
        with self._send_lock:
            send_frame(self.sock, blob)

    def recv(self):
        blob = recv_frame(self.sock)
        body = crypto.open(self._ek, self._mk, blob)  # raises on wrong key
        return body[0], body[1:]

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# --- handshakes ------------------------------------------------------------
# The transport (direct TCP or a relay-forwarded stream) is already connected
# and paired when these run. Host speaks first with the salt.

def host_handshake(sock, password):
    """Host side. Returns a SecureChannel or raises on bad password."""
    salt = crypto.new_salt()
    send_frame(sock, salt)
    ek, mk = crypto.derive_keys(password, salt)
    chan = SecureChannel(sock, ek, mk)
    opcode, payload = chan.recv()  # OP_HELLO, decrypt failure => wrong password
    if opcode != OP_HELLO or payload != MAGIC:
        raise ProtocolError("bad hello")
    return chan


def viewer_handshake(sock, password):
    """Viewer side. Returns a SecureChannel; wrong password fails on first recv."""
    salt = recv_frame(sock)
    ek, mk = crypto.derive_keys(password, salt)
    chan = SecureChannel(sock, ek, mk)
    chan.send(OP_HELLO, MAGIC)
    return chan


# --- input event (de)serialization ----------------------------------------
# Mouse:  kind(1) x(2) y(2) data(2, signed)
M_MOVE, M_DOWN, M_UP, M_WHEEL = 0, 1, 2, 3


def pack_mouse(kind, x=0, y=0, data=0):
    return struct.pack(">BHHh", kind, x, y, data)


def unpack_mouse(payload):
    return struct.unpack(">BHHh", payload)  # kind, x, y, data


# Key:  down(1) vk(2)
def pack_key(down, vk):
    return struct.pack(">BH", 1 if down else 0, vk)


def unpack_key(payload):
    down, vk = struct.unpack(">BH", payload)
    return bool(down), vk


def pack_screen_info(w, h, strip_h):
    return struct.pack(">HHH", w, h, strip_h)


def unpack_screen_info(payload):
    return struct.unpack(">HHH", payload)  # w, h, strip_h
