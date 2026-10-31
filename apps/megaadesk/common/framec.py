"""
MeGaADesk - frame codec (pure stdlib).

The screen is sliced into full-width horizontal strips. Each frame we compare
every strip's raw bytes against the previous frame and only send the strips that
changed, zlib-compressed. Full-width strips are contiguous in the capture buffer,
so slicing and comparing them is a C-level operation - no per-pixel Python loops.

Wire format for one frame (before encryption):
    seq:      unused here, handled by protocol
    for each changed strip:  index(2) | comp_len(4) | comp_bytes

Colors are converted BGRA (capture) -> RGB (what the tkinter PPM viewer wants),
using strided slice assignment so the whole conversion stays at C speed.
"""
import struct
import zlib

STRIP_H = 36  # strip height in pixels; smaller = finer diffs, more overhead


def bgra_to_rgb(bgra):
    """Reorder BGRA -> RGB with three C-level strided copies (no pixel loop)."""
    n = len(bgra) // 4
    out = bytearray(n * 3)
    out[0::3] = bgra[2::4]  # R
    out[1::3] = bgra[1::4]  # G
    out[2::3] = bgra[0::4]  # B
    return bytes(out)


class FrameEncoder:
    """Host side: BGRA frame -> list of changed (strip_index, compressed_rgb)."""

    def __init__(self, width, height, strip_h=STRIP_H, level=6):
        self.w = width
        self.h = height
        self.sh = strip_h
        self.level = level
        self.nstrips = (height + strip_h - 1) // strip_h
        self._prev = [None] * self.nstrips  # previous BGRA bytes per strip

    def reset(self):
        """Force the next encode() to be a full keyframe (e.g. new viewer)."""
        self._prev = [None] * self.nstrips

    def encode(self, bgra):
        """Return list of (index, comp_bytes) for strips that changed."""
        out = []
        w4 = self.w * 4
        mv = memoryview(bgra)
        for i in range(self.nstrips):
            y0 = i * self.sh
            y1 = min(y0 + self.sh, self.h)
            src = mv[y0 * w4: y1 * w4]  # zero-copy view of this strip (BGRA)
            if self._prev[i] != src:
                raw = bytes(src)
                comp = zlib.compress(bgra_to_rgb(raw), self.level)
                out.append((i, comp))
                self._prev[i] = raw
        return out

    def pack(self, strips):
        """Serialize encode() output to bytes."""
        parts = []
        for i, comp in strips:
            parts.append(struct.pack(">HI", i, len(comp)))
            parts.append(comp)
        return b"".join(parts)


class FrameBuffer:
    """Viewer side: keeps a full RGB image and applies incoming strips to it."""

    def __init__(self, width, height, strip_h=STRIP_H):
        self.w = width
        self.h = height
        self.sh = strip_h
        self.nstrips = (height + strip_h - 1) // strip_h
        self.buf = bytearray(width * height * 3)  # RGB

    def apply_packed(self, data):
        """Apply a packed strip payload. Returns number of strips applied."""
        w3 = self.w * 3
        off = 0
        count = 0
        while off < len(data):
            (i, clen) = struct.unpack_from(">HI", data, off)
            off += 6
            comp = data[off:off + clen]
            off += clen
            rgb = zlib.decompress(comp)
            dst = (i * self.sh) * w3
            self.buf[dst:dst + len(rgb)] = rgb
            count += 1
        return count

    def ppm(self):
        """Return the current image as PPM (P6) bytes for tkinter PhotoImage."""
        return b"P6\n%d %d\n255\n" % (self.w, self.h) + bytes(self.buf)


if __name__ == "__main__":
    import os
    import time

    w, h = 1920, 1080
    enc = FrameEncoder(w, h)
    fb = FrameBuffer(w, h)

    frame1 = os.urandom(w * h * 4)
    t0 = time.perf_counter()
    strips = enc.encode(frame1)
    packed = enc.pack(strips)
    dt = (time.perf_counter() - t0) * 1000
    print(f"keyframe: {len(strips)} strips, {len(packed)/1024:.0f} KB, {dt:.0f} ms (random data = worst case)")

    fb.apply_packed(packed)
    assert bytes(fb.buf) == bgra_to_rgb(frame1), "roundtrip mismatch"

    # second frame: change only two strips -> tiny delta
    frame2 = bytearray(frame1)
    for k in range(2 * w * 4):
        frame2[k] = (frame2[k] + 7) & 0xFF
    t0 = time.perf_counter()
    strips = enc.encode(bytes(frame2))
    packed = enc.pack(strips)
    dt = (time.perf_counter() - t0) * 1000
    print(f"delta (2 strips changed): {len(strips)} strips, {len(packed)/1024:.1f} KB, {dt:.1f} ms")
    print("ok: codec roundtrip")
