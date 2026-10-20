"""Render the README's pictures into docs/media: python3 scripts/docs_media.py

Needs a local Chromium-family browser and ffmpeg. Everything shown is a synthetic example
from the repository, rendered by Construct's own viewer.
"""

import importlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = next(p for p in ROOT.iterdir() if (p / "product.py").is_file())
sys.path.insert(0, str(ROOT))
render = importlib.import_module(PKG.name + ".render")
params = importlib.import_module(PKG.name + ".params")
scene = importlib.import_module(PKG.name + ".scene")
EX = PKG / "examples" / "v2"
OUT = ROOT / "docs" / "media"
GALLERY = ["lighthouse.json", "turntable.json", "lantern-jellyfish.json", "cd.json", "book.json",
           "object-electric-guitar.params.json", "object-synth.params.json", "object-acoustic-guitar.params.json",
           "case-digipak.params.json", "vessel-bottle.params.json", "vessel-can.params.json", "vessel-glass-tulip.params.json"]


def page(name, tmp):
    import json
    doc = json.loads((EX / name).read_text())
    if params.is_params(doc):
        doc = params.expand(doc)
    html, _ = render.build_html(scene.compile_scene(doc), str(EX))
    path = Path(tmp) / (name.split(".")[0] + ".html")
    path.write_text(html, encoding="utf-8")
    return path


def gif(src_page, out, start, seconds, speed, w, h, tmp, view=None, zoom=None):
    frames = Path(tmp) / ("f-" + out.stem)
    frames.mkdir()
    b = render.open_browser(render._url(src_page, ui=0, capture=1, caption=0, t=start, view=view, zoom=zoom), w, h, 1.0)
    try:
        n = int(seconds * 15)
        for i in range(n):
            b.evaluate("HOLO.renderAt(%.4f)" % (start + i / 15.0 * speed))
            b.shot(frames / ("frame-%05d.png" % i))
    finally:
        b.close()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "15", "-i", str(frames / "frame-%05d.png"), "-vf",
                    "scale=%d:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=3" % w, str(out)], check=True)


def still(src_page, out, t, w, h, **q):
    b = render.open_browser(render._url(src_page, ui=0, capture=1, caption=0, t=t, **q), w, h, 1.0)
    try:
        b.shot(out)
    finally:
        b.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        lighthouse = page("lighthouse.json", tmp)
        gif(lighthouse, OUT / "hero.gif", 0.0, 9.0, 1.3, 760, 430, tmp, zoom=0.78)
        gif(page("cd.json", tmp), OUT / "opening.gif", 5.5, 7.0, 1.2, 640, 360, tmp)
        still(lighthouse, OUT / "provenance.png", 30.0, 960, 540, mode="provenance", motion="reduced")
        cells = []
        for i, name in enumerate(GALLERY):
            out = Path(tmp) / ("g%02d.png" % i)
            still(page(name, tmp), out, 30.0, 640, 480, motion="reduced")
            cells.append(str(out))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + sum([["-i", c] for c in cells], []) + [
            "-filter_complex", "".join("[%d]" % i for i in range(len(cells))) + "xstack=inputs=%d:layout=%s[v]" % (
                len(cells), "|".join("%d_%d" % ((i % 4) * 640, (i // 4) * 480) for i in range(len(cells)))),
            "-map", "[v]", "-q:v", "3", str(OUT / "gallery.jpg")], check=True)
    for p in sorted(OUT.iterdir()):
        print("%-16s %7.0f KB" % (p.name, p.stat().st_size / 1024))


if __name__ == "__main__":
    main()
