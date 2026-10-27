"""Render the gallery's pictures, framed close to each construct: python3 scripts/gallery_images.py [slug ...]

For every example (examples/examples.json), and every "beyond" item drawn from its construct
(`"pictures": "construct"` in examples/beyond.json), it writes hero.jpg (1440 x 900) and thumb.jpg
(1200 x 750), and for every film (examples/films.json) poster.jpg (1200 x 750). Each construct is drawn by Construct's
own viewer, built as the gallery builds it, in its hero view, assembled and at rest (reduced motion).

The picture is framed on what the construct draws, not on its labels: a render without labels finds
the box of its lines and points (pixels clearly brighter than the haze; faint fog and ground may fall
outside), the camera pulls back while that box touches the edge of the render (a long boom), and the
picture, with its labels, is cut to the box with an even margin and widened to 16:10, the background
extended where needed rather than the construct cut. Labels may be clipped at the edges. A construct
seen from inside (a nave) keeps the whole frame. Needs a local Chromium-family browser and ffmpeg.
"""

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
render = importlib.import_module("construct_hologram.render")
studio = importlib.import_module("construct_hologram.studio")
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)

W, H, SCALE = 1440, 900, 2.0  # the render, in CSS pixels, at twice the density
MARGIN = 0.07  # of the construct's larger side, on every side
BRIGHT = 56  # a construct's lines and points are brighter than this (0..255); haze, fog and faint ground stay below
EDGE = 4  # device pixels: a box this close to the render's edge may be cut by it
BACKGROUND = "0x050205"
# whether any part lies behind the camera: a construct seen from inside, which fills the whole frame
INSIDE = """(() => { const h = HOLO.hologram, cam = h.lastCamera, c = document.querySelector('canvas');
  const m = h.matrices(cam, c.clientWidth / c.clientHeight).vp;
  for (const p of h.geo.parts) for (const ins of p.instances) for (let k = 0; k < 8; k++) {
    const v = [k & 1 ? ins.max[0] : ins.min[0], k & 2 ? ins.max[1] : ins.min[1], k & 4 ? ins.max[2] : ins.min[2]];
    if (m[3] * v[0] + m[7] * v[1] + m[11] * v[2] + m[15] <= 1e-6) return true; }
  return false; })()"""


def bright_box(png):
    """The box (device pixels) of the render's pixels brighter than BRIGHT, or None."""
    rw, rh = round(W * SCALE), round(H * SCALE)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    mark = bytes(1 if v > BRIGHT else 0 for v in range(256))
    x0, y0, x1, y1 = rw, rh, -1, -1
    for y in range(rh):
        row = raw[y * rw:(y + 1) * rw].translate(mark)
        a = row.find(1)
        if a < 0:
            continue
        x0, x1, y0, y1 = min(x0, a), max(x1, row.rfind(1)), min(y0, y), y
    return (x0, y0, x1, y1) if x1 >= 0 else None


def frame(box):
    """The 16:10 window (x, y, w, h in CSS pixels, possibly beyond the render) that holds the box."""
    if box is None:
        return 0.0, 0.0, float(W), float(H)
    x0, y0, x1, y1 = (v / SCALE for v in box)
    bw, bh = x1 - x0, y1 - y0
    pad = max(MARGIN * max(bw, bh), 16.0)
    fw, fh = bw + 2 * pad, bh + 2 * pad
    fw, fh = max(fw, fh * 1.6), max(fh, fw / 1.6)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx - fw / 2, cy - fh / 2, fw, fh  # centred on the construct; beyond the render, background


def cut(png, window, out, size):
    """Cut the window out of the render (padding with the background where it lies beyond it) to size."""
    x, y, fw, fh = (round(v * SCALE) for v in window)
    rw, rh = round(W * SCALE), round(H * SCALE)
    px, py = max(0, -x), max(0, -y)  # how far the window reaches beyond the render
    cx, cy = max(0, x), max(0, y)
    cw, ch = min(rw, x + fw) - cx, min(rh, y + fh) - cy
    vf = "crop=%d:%d:%d:%d,pad=%d:%d:%d:%d:color=%s,scale=%d:%d:flags=lanczos" % (
        cw, ch, cx, cy, fw, fh, px, py, BACKGROUND, size[0], size[1])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-vf", vf, "-q:v", "3", str(out)], check=True)


def capture(page, png, zoom, labels):
    b = render.open_browser(render._url(str(page), t=60, view="hero", camera="still", motion="reduced", ui=0, capture=1,
                                        labels=labels, caption=0, zoom="%.3f" % zoom), W, H, SCALE)
    try:
        inside = b.evaluate(INSIDE) is True
        b.shot(png)
    finally:
        b.close()
    return inside


def shoot(page, png):
    """The labelled render in png, and the window to cut from it."""
    rw, rh = round(W * SCALE), round(H * SCALE)
    zoom, box = 1.0, None
    while True:  # pull back only as far as needed: further away, fog dims thin lines
        inside = capture(page, png, zoom, 0)
        box = None if inside else bright_box(png)
        if box is None or (box[0] > EDGE and box[1] > EDGE and box[2] < rw - 1 - EDGE and box[3] < rh - 1 - EDGE):
            break
        if zoom >= 4.0:
            raise SystemExit("%s: the construct does not fit the render even pulled back" % page)
        zoom = min(4.0, zoom * 1.3)
    capture(page, png, zoom, 1)
    return frame(box), zoom


def main(argv):
    examples = [e["slug"] for e in site._load_examples()]
    films = [f["slug"] for f in site._load_films()]
    wanted = set(argv)
    with tempfile.TemporaryDirectory() as tmp:
        beyond = [b["slug"] for b in site._load_beyond() if b.get("pictures") == "construct"]
        for kind, slugs, src_of in (("example", examples, lambda s: site.EXAMPLES / s),
                                    ("film", films, lambda s: site.EXAMPLES / "films" / s),
                                    ("beyond", beyond, lambda s: site.EXAMPLES / s)):
            for slug in slugs:
                if wanted and slug not in wanted:
                    continue
                src, built = src_of(slug), Path(tmp, kind + "-" + slug)
                studio.build(str(site._public_scene(src / "scene.json", Path(tmp, "scenes"))), str(built), asset_root=str(src))
                png = Path(tmp, kind + "-" + slug + ".png")
                window, zoom = shoot(studio.page_in(built), png)
                outs = [("poster.jpg", (1200, 750))] if kind == "film" else [("hero.jpg", (1440, 900)), ("thumb.jpg", (1200, 750))]
                for name, size in outs:
                    cut(png, window, src / name, size)
                print("%-8s %-28s zoom %.2f, window %4.0f x %3.0f at (%5.0f, %5.0f)"
                      % ((kind, slug, zoom) + tuple(window[2:]) + tuple(window[:2])), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
