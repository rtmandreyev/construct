"""Render the gallery's pictures, framed close to each construct: python3 scripts/gallery_images.py [slug ...]

For every example (examples/examples.json) it writes hero.jpg (1440 x 900) and thumb.jpg (1200 x 750),
and for every film (examples/films.json) poster.jpg (1200 x 750). Each construct is drawn by Construct's
own viewer, built as the gallery builds it, in its hero view with its labels, assembled and at rest
(reduced motion, so moving parts sit where their boxes are); where the construct reaches beyond the
view (a long boom), the camera pulls back until all of it is in the render. The picture is cut to the construct: its
parts' boxes are projected through the viewer's camera, given an even margin and widened to 16:10, so
no part of the construct is ever cut off (a label may be); where the box does not fit the frame, the
background is extended instead. A construct seen from inside (a nave) keeps the whole frame. Needs a
local Chromium-family browser and ffmpeg.
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
MARGIN = 0.06  # of the construct's larger side, on every side
BACKGROUND = "0x050205"
# the screen box of every part's box (and its opened box, in an open still pose), in CSS pixels
BOX = """JSON.stringify((() => { const h = HOLO.hologram, cam = h.lastCamera, c = document.querySelector('canvas');
  const w = c.clientWidth, ht = c.clientHeight, m = h.matrices(cam, w / ht).vp, open = h.openAt(0) > 0.5;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, behind = 0;
  for (const p of h.geo.parts) for (const ins of p.instances) {
    const boxes = [[ins.min, ins.max]];
    if (open && ins.open_min) boxes.push([ins.open_min, ins.open_max]);
    for (const [a, b] of boxes) for (let k = 0; k < 8; k++) {
      const v = [k & 1 ? b[0] : a[0], k & 2 ? b[1] : a[1], k & 4 ? b[2] : a[2]];
      const X = m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], Y = m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13];
      const q = m[3] * v[0] + m[7] * v[1] + m[11] * v[2] + m[15];
      if (q <= 1e-6) { behind++; continue; }
      const px = (X / q + 1) / 2 * w, py = (1 - Y / q) / 2 * ht;
      x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py);
    } }
  return {w, h: ht, x0, y0, x1, y1, behind}; })())"""


def frame(box):
    """The 16:10 window (x, y, w, h in CSS pixels, possibly beyond the render) that holds the construct."""
    if box["behind"] or box["x0"] < -box["w"] or box["x1"] > 2 * box["w"] or box["y0"] < -box["h"] or box["y1"] > 2 * box["h"]:
        return 0.0, 0.0, float(W), float(H)  # seen from inside: the whole frame
    bw, bh = box["x1"] - box["x0"], box["y1"] - box["y0"]
    pad = MARGIN * max(bw, bh)
    fw, fh = bw + 2 * pad, bh + 2 * pad
    fw, fh = max(fw, fh * 1.6), max(fh, fw / 1.6)
    cx, cy = (box["x0"] + box["x1"]) / 2, (box["y0"] + box["y1"]) / 2
    x, y = cx - fw / 2, cy - fh / 2
    # slide the window into the render where it fits; where it is larger, it stays centred and is padded
    x = min(max(x, 0.0), W - fw) if fw <= W else x
    y = min(max(y, 0.0), H - fh) if fh <= H else y
    return x, y, fw, fh


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


def outside(box):
    """How many times larger than the render the construct's box (with its margin) is; 1 when it fits."""
    if box["behind"]:
        return 1.0
    pad = MARGIN * max(box["x1"] - box["x0"], box["y1"] - box["y0"])
    cx, cy = W / 2, H / 2
    reach = max(cx - (box["x0"] - pad), (box["x1"] + pad) - cx) / cx, max(cy - (box["y0"] - pad), (box["y1"] + pad) - cy) / cy
    return max(1.0, *reach)


def shoot(page, png):
    zoom = 1.0
    for _ in range(4):  # pull back until the whole construct is in the render
        b = render.open_browser(render._url(str(page), t=60, view="hero", camera="still", motion="reduced", ui=0,
                                            capture=1, labels=1, caption=0, zoom="%.3f" % zoom), W, H, SCALE)
        try:
            box = json.loads(b.evaluate(BOX))
            k = outside(box)
            if k <= 1.0 or zoom >= 4.0:
                b.shot(png)
                return frame(box)
        finally:
            b.close()
        zoom = min(4.0, zoom * k * 1.05)
    raise SystemExit("%s: the construct does not fit the render" % page)


def main(argv):
    examples = [e["slug"] for e in site._load_examples()]
    films = [f["slug"] for f in site._load_films()]
    wanted = set(argv)
    with tempfile.TemporaryDirectory() as tmp:
        for kind, slugs, src_of in (("example", examples, lambda s: site.EXAMPLES / s),
                                    ("film", films, lambda s: site.EXAMPLES / "films" / s)):
            for slug in slugs:
                if wanted and slug not in wanted:
                    continue
                src, built = src_of(slug), Path(tmp, kind + "-" + slug)
                studio.build(str(site._public_scene(src / "scene.json", Path(tmp, "scenes"))), str(built), asset_root=str(src))
                png = Path(tmp, kind + "-" + slug + ".png")
                window = shoot(studio.page_in(built), png)
                outs = [("poster.jpg", (1200, 750))] if kind == "film" else [("hero.jpg", (1440, 900)), ("thumb.jpg", (1200, 750))]
                for name, size in outs:
                    cut(png, window, src / name, size)
                print("%-8s %-28s window %4.0f x %3.0f at (%5.0f, %5.0f)" % ((kind, slug) + tuple(window[2:]) + tuple(window[:2])),
                      flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
