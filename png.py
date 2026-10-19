"""A minimal deterministic PNG writer (standard library only).

Used to make synthetic, clearly generated artwork for examples and tests: it never
imitates a real cover. Real artwork enters a scene only as supplied, permitted bytes.
"""

import math
import struct
import zlib


def encode(width, height, pixel):
    """PNG bytes for an RGB image; `pixel(x, y)` returns (r, g, b) in 0..255."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            r, g, b = pixel(x, y)
            rows += bytes((max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def disc_cover(size=384):
    """Synthetic decorative 'album' art: concentric interference rings over a gradient."""
    c = size / 2

    def px(x, y):
        dx, dy = (x - c) / size, (y - c) / size
        r = math.hypot(dx, dy)
        a = math.atan2(dy, dx)
        ring = 0.5 + 0.5 * math.cos(r * 70 + 6 * math.sin(a * 3))
        band = 0.5 + 0.5 * math.sin((x + 2 * y) / size * 9)
        base = (18 + 30 * (y / size), 10 + 20 * band, 40 + 60 * (1 - y / size))
        glow = ring ** 6 * (1.0 - min(1.0, r * 1.9))
        return (base[0] + 230 * glow, base[1] + 120 * glow, base[2] + 210 * glow)
    return encode(size, size, px)


def book_cover(width=256, height=384):
    """Synthetic decorative 'book' art: stacked bands and a sun disc, no lettering."""
    def px(x, y):
        u, v = x / width, y / height
        stripe = int(v * 9) % 2
        sun = math.hypot(u - 0.62, v - 0.34) < 0.17
        r, g, b = (34, 52, 70) if stripe else (28, 42, 58)
        if 0.72 < v < 0.76 or 0.80 < v < 0.815:
            r, g, b = 210, 196, 160
        if sun:
            k = 1 - math.hypot(u - 0.62, v - 0.34) / 0.17
            r, g, b = 230, 140 + 60 * k, 70 + 40 * k
        return (r, g, b)
    return encode(width, height, px)
