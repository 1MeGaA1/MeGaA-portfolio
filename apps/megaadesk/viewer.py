"""
MeGaADesk viewer (client) - the machine you sit at.

Connects to a host (directly or via a relay), shows the remote screen in a
tkinter window, and forwards your mouse and keyboard to it.

Usage:
  python viewer.py --host 192.168.1.50 --port 7777 --password SECRET
  python viewer.py --relay relay.example.com:7000 --id MYPC01 --password SECRET
"""
import argparse
import math
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from common import framec, protocol

# tkinter Button number -> our button id (0=left, 1=right, 2=middle)
_BTN = {1: 0, 2: 2, 3: 1}


class Viewer:
    def __init__(self, chan, w, h, strip_h):
        self.chan = chan
        self.rw, self.rh = w, h
        self.fb = framec.FrameBuffer(w, h, strip_h)
        self.lock = threading.Lock()
        self.dirty = True
        self.stop = threading.Event()

        self.root = tk.Tk()
        self.root.title(f"MeGaADesk - {w}x{h}")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Downscale (integer) so the remote fits comfortably on this screen.
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.factor = max(1, math.ceil(w / (0.92 * sw)), math.ceil(h / (0.92 * sh)))

        self.label = tk.Label(self.root, borderwidth=0, highlightthickness=0, bg="black")
        self.label.pack()
        self.label.focus_set()
        self._imgref = None

        self._bind_input()
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

    # --- networking -------------------------------------------------------
    def _recv_loop(self):
        while not self.stop.is_set():
            try:
                op, payload = self.chan.recv()
            except (OSError, ConnectionError, ValueError):
                break
            if op == protocol.OP_FRAME:
                with self.lock:
                    self.fb.apply_packed(payload)
                    self.dirty = True
        self.root.after(0, self._on_disconnect)

    def _send(self, op, payload=b""):
        try:
            self.chan.send(op, payload)
        except (OSError, ConnectionError):
            self.stop.set()

    # --- rendering --------------------------------------------------------
    def _render_tick(self):
        if self.stop.is_set():
            return
        if self.dirty:
            with self.lock:
                ppm = self.fb.ppm()
                self.dirty = False
            img = tk.PhotoImage(data=ppm)
            if self.factor > 1:
                img = img.subsample(self.factor, self.factor)
            self.label.config(image=img)
            self._imgref = img  # prevent GC
        self.root.after(33, self._render_tick)

    # --- input ------------------------------------------------------------
    def _rx(self, x):
        return max(0, min(self.rw - 1, x * self.factor))

    def _ry(self, y):
        return max(0, min(self.rh - 1, y * self.factor))

    def _bind_input(self):
        self.label.bind("<Motion>", self._on_motion)
        for n in (1, 2, 3):
            self.label.bind(f"<ButtonPress-{n}>", self._on_button_down)
            self.label.bind(f"<ButtonRelease-{n}>", self._on_button_up)
        self.label.bind("<MouseWheel>", self._on_wheel)
        self.root.bind("<KeyPress>", self._on_key_down)
        self.root.bind("<KeyRelease>", self._on_key_up)

    def _on_motion(self, e):
        self._send(protocol.OP_MOUSE, protocol.pack_mouse(protocol.M_MOVE, self._rx(e.x), self._ry(e.y)))

    def _on_button_down(self, e):
        self.label.focus_set()
        self._send(protocol.OP_MOUSE, protocol.pack_mouse(protocol.M_DOWN, self._rx(e.x), self._ry(e.y), _BTN.get(e.num, 0)))

    def _on_button_up(self, e):
        self._send(protocol.OP_MOUSE, protocol.pack_mouse(protocol.M_UP, self._rx(e.x), self._ry(e.y), _BTN.get(e.num, 0)))

    def _on_wheel(self, e):
        self._send(protocol.OP_MOUSE, protocol.pack_mouse(protocol.M_WHEEL, 0, 0, int(e.delta / 120)))

    def _on_key_down(self, e):
        if e.keycode:
            self._send(protocol.OP_KEY, protocol.pack_key(True, e.keycode))

    def _on_key_up(self, e):
        if e.keycode:
            self._send(protocol.OP_KEY, protocol.pack_key(False, e.keycode))

    # --- lifecycle --------------------------------------------------------
    def _on_disconnect(self):
        if not self.stop.is_set():
            self.stop.set()
            self.root.title("MeGaADesk - disconnected")
            messagebox.showinfo("MeGaADesk", "Disconnected from host.")
            self.root.destroy()

    def close(self):
        self.stop.set()
        self.chan.close()
        self.root.destroy()

    def run(self):
        self.recv_thread.start()
        self.root.after(33, self._render_tick)
        self.root.mainloop()


def connect(args):
    if args.relay:
        from common import relaylink
        if not args.host_id:
            sys.exit("--relay requires --id")
        sock = relaylink.viewer_connect(args.relay, args.host_id)
    else:
        host, port = args.host, args.port
        sock = socket.create_connection((host, port), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def main():
    ap = argparse.ArgumentParser(description="MeGaADesk viewer (remote control client).")
    ap.add_argument("--password", required=True)
    ap.add_argument("--host", help="direct mode: host IP/name")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--relay", help="relay mode: host:port of relay server")
    ap.add_argument("--id", dest="host_id", help="relay mode: host ID to connect to")
    args = ap.parse_args()
    if not args.relay and not args.host:
        ap.error("give --host (direct) or --relay + --id")

    try:
        sock = connect(args)
        chan = protocol.viewer_handshake(sock, args.password)
        op, payload = chan.recv()  # wrong password -> ValueError here
    except ValueError:
        sys.exit("Connection failed: wrong password (authentication rejected).")
    except (OSError, ConnectionError) as e:
        sys.exit(f"Connection failed: {e}")
    if op != protocol.OP_SCREEN_INFO:
        sys.exit("Protocol error: expected screen info.")

    w, h, strip_h = protocol.unpack_screen_info(payload)
    Viewer(chan, w, h, strip_h).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
