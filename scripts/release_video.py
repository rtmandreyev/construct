"""Render the release video from a storyboard: python3 scripts/release_video.py [storyboard.json]
    [--showcase DIR] [--out DIR] [--aspects 16x9,1x1,9x16] [--fps 30] [--draft]

Every shot is a real hologram rendered by the toolkit's own viewer in a headless local
browser, at each aspect natively (the viewer frames the object for the aspect; nothing is
cropped). On-screen type is set in the same page, in fonts given in the storyboard (OFL fonts
installed on this machine; the font files are read, never copied into the output).
ffmpeg joins the shots. The product's name comes from product.py, so a rename carries over.

Outputs, per aspect: release-<aspect>.mp4 (silent: the music slot is marked in
markers.json and MUSIC_SLOT.txt), grabs/<aspect>-<shot>.png (a clean still of each shot), and
the shot list with its timing. Shots whose source is "showcase:<name>" are read from the
showcase folder; missing ones are skipped (and listed), so a draft can be cut before it exists.
"""

import argparse
import base64
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = next(p for p in ROOT.iterdir() if (p / "product.py").is_file())
sys.path.insert(0, str(ROOT))
product = importlib.import_module(PKG.name + ".product")
render = importlib.import_module(PKG.name + ".render")
params = importlib.import_module(PKG.name + ".params")
scene = importlib.import_module(PKG.name + ".scene")

ASPECTS = {"16x9": (1920, 1080), "1x1": (1080, 1080), "9x16": (1080, 1920)}


def _font_face(family, path):
    p = Path(path).expanduser()
    if not p.is_file():
        return ""
    mime = "font/otf" if p.suffix.lower() == ".otf" else "font/ttf"
    return "@font-face { font-family: '%s'; src: url(data:%s;base64,%s); }" % (
        family, mime, base64.b64encode(p.read_bytes()).decode("ascii"))


def overlay_script(board, aspect):
    """JS that adds the type layer to a page and a setType(text, sub, opacity, place) function."""
    fonts = board.get("fonts", {})
    css = _font_face("Headline", fonts.get("headline", "")) + _font_face("Mono", fonts.get("mono", ""))
    w, h = ASPECTS[aspect]
    unit = min(w, h) / 1080.0
    css += """
#rv { position: fixed; inset: 0; pointer-events: none; z-index: 99; display: flex; flex-direction: column;
      padding: %(pad)dpx; box-sizing: border-box; }
#rv.center { justify-content: center; align-items: center; text-align: center; }
#rv.low { justify-content: flex-end; align-items: flex-start; text-align: left; }
#rv.high { justify-content: flex-start; align-items: center; text-align: center; padding-top: %(top)dpx; }
#rv.left { justify-content: center; align-items: flex-start; text-align: left; }
#rv.left .t, #rv.left .s { width: 40vw; }
#rv.bottom { justify-content: flex-end; align-items: center; text-align: center; padding-bottom: 17vh; }
#rv.bottom .t, #rv.bottom .s { width: 84vw; }
#rv .t { font: 600 %(t)dpx/1.04 'Headline', 'Source Sans Pro', sans-serif; color: #fff; letter-spacing: -0.01em;
         text-shadow: 0 0 %(g)dpx rgba(209,107,208,.55), 0 2px 12px rgba(0,0,0,.6); white-space: pre-line; }
#rv .s { margin-top: %(sg)dpx; font: 400 %(s)dpx/1.3 'Mono', ui-monospace, monospace; color: rgba(240,228,250,.86);
         letter-spacing: .04em; white-space: pre-line; }
#rv .tag { position: fixed; left: %(pad)dpx; bottom: %(tagb)dpx; font: 400 %(tag)dpx/1 'Mono', ui-monospace, monospace;
           color: rgba(236,226,246,.7); letter-spacing: .08em; text-transform: uppercase; }
.caption, .legend, .help, .labels, svg.leaders { display: none !important; }
""" % {"pad": int(96 * unit), "top": int(150 * unit), "bot": int(260 * unit), "t": int(84 * unit), "g": int(18 * unit), "s": int(30 * unit),
       "sg": int(18 * unit), "tag": int(22 * unit), "tagb": int(48 * unit)}
    return """(function(){
  if (!document.getElementById('rvstyle')) {
    const st = document.createElement('style'); st.id = 'rvstyle'; st.textContent = %s; document.head.appendChild(st);
    const d = document.createElement('div'); d.id = 'rv'; d.innerHTML = '<div class="t"></div><div class="s"></div><div class="tag"></div>';
    document.body.appendChild(d);
  }
  window.setType = function(t, s, tag, o, place) {
    const d = document.getElementById('rv'); d.className = place || 'center';
    d.querySelector('.t').textContent = t || ''; d.querySelector('.s').textContent = s || '';
    d.querySelector('.tag').textContent = tag || ''; d.style.opacity = o;
  };
  return document.fonts.ready.then(() => 1);
})()""" % json.dumps(css)


def card_page(folder):
    path = Path(folder) / "card.html"
    path.write_text("<!doctype html><meta charset=utf-8><style>html,body{margin:0;height:100%;background:#070207}</style>"
                    "<body data-ready=1></body>", encoding="utf-8")
    return path


def source_path(src, showcase):
    if src.startswith("showcase:"):
        if not showcase:
            return None
        name = src.split(":", 1)[1]
        for cand in (Path(showcase) / name, Path(showcase) / (name + ".json"), Path(showcase) / name / "scene.json",
                     Path(showcase) / name / "params.json"):
            if cand.is_file():
                return cand
        hits = sorted(Path(showcase).glob(name + "*/*.json")) if Path(showcase).is_dir() else []
        return hits[0] if hits else None
    p = (ROOT / src) if not Path(src).is_absolute() else Path(src)
    return p if p.is_file() else None


def build_page(src, folder):
    doc = json.loads(Path(src).read_text(encoding="utf-8"))
    if params.is_params(doc):
        doc = params.expand(doc)
    geometry = scene.compile_scene(doc)
    html, _ = render.build_html(geometry, str(Path(src).parent))
    out = Path(folder) / (Path(src).stem.replace(".params", "") + ".html")
    out.write_text(html, encoding="utf-8")
    return out, doc.get("title", "")


def text_at(shot, t):
    """The type to show at time t (seconds into the shot): (text, sub, opacity, place)."""
    ty = shot.get("type")
    if not ty:
        return ("", "", 0.0, "center")
    a, b = ty.get("in", 0.15), ty.get("out", shot["seconds"] - 0.1)
    fade = 0.22
    o = 0.0 if t < a or t > b else min(1.0, (t - a) / fade, (b - t) / fade)
    return (fill(ty.get("text", "")), fill(ty.get("sub", "")), max(0.0, o), ty.get("place", "center"))


def fill(text):
    return text.replace("{TITLE}", product.TITLE).replace("{NAME}", product.NAME)


def render_shot(b, shot, page, aspect, fps, frames_dir, start_index, is_card):
    """Capture one shot's frames; returns the next frame index."""
    lay = dict(BOARD.get("layout", {}).get(aspect, {}))
    lay.update(shot.get("layout", {}).get(aspect, {}))
    q = {"ui": 0, "capture": 1, "caption": 0, "labels": 0, "view": shot.get("view"), "mode": shot.get("mode"),
         "open": shot.get("open"), "motion": shot.get("motion"),
         "shift": ",".join("%g" % v for v in lay["shift"]) if lay.get("shift") and shot.get("type") else None,
         "zoom": lay.get("zoom") if shot.get("type") else lay.get("bare_zoom")}
    b.open(page.resolve().as_uri() if is_card else render._url(page, **{k: v for k, v in q.items() if v is not None}))
    b.evaluate(overlay_script(BOARD, aspect))
    n = int(round(shot["seconds"] * fps))
    tag = fill(shot.get("tag", ""))
    i = start_index
    for k in range(n):
        t = k / fps
        if not is_card:
            b.evaluate("HOLO.renderAt(%.4f)" % (shot.get("start", 0.0) + t * shot.get("speed", 1.0)))
        text, sub, o, place = text_at(shot, t)
        if place in ("low", "center") and lay.get("place") and shot.get("kind") != "card":
            place = lay["place"]
        b.evaluate("setType(%s, %s, %s, %.3f, %s)" % (json.dumps(text), json.dumps(sub), json.dumps(tag), o, json.dumps(place)))
        b.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")
        data = b.call("Page.captureScreenshot", format="jpeg", quality=92, captureBeyondViewport=False)["data"]
        (Path(frames_dir) / ("f%06d.jpg" % i)).write_bytes(base64.b64decode(data))
        i += 1
    return i


def main(argv=None):
    global BOARD
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("storyboard", nargs="?", default=str(ROOT / "scripts" / "release_video.json"))
    ap.add_argument("--showcase")
    ap.add_argument("--out", default=str(ROOT / ".local" / "release"))
    ap.add_argument("--aspects", default="16x9,1x1,9x16")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--draft", action="store_true", help="half resolution, 15 fps: a quick check of the cut")
    args = ap.parse_args(argv)
    BOARD = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fps = 15 if args.draft else args.fps
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg is needed to join the shots")
    with tempfile.TemporaryDirectory(prefix="release-") as tmp:
        tmp = Path(tmp)
        card = card_page(tmp)
        shots, skipped = [], []
        have_showcase = bool(args.showcase) and Path(args.showcase).is_dir()
        for sh in BOARD["shots"]:
            if sh.get("draft") and have_showcase:
                continue  # draft stand-ins give way to the showcase
            if sh.get("kind") == "card":
                shots.append((sh, card, True, ""))
                continue
            src = source_path(sh["src"], args.showcase)
            if src is None:
                skipped.append(sh["src"])
                continue
            page, title = build_page(src, tmp)
            shots.append((sh, page, False, title))
        report = {"product": product.NAME, "fps": fps, "skipped": skipped, "aspects": {}}
        for aspect in args.aspects.split(","):
            w, h = ASPECTS[aspect]
            if args.draft:
                w, h = w // 2, h // 2
            frames = tmp / ("frames-" + aspect)
            frames.mkdir()
            grabs = out / "grabs"
            grabs.mkdir(exist_ok=True)
            b = render.open_browser(render._url(shots[0][1] if not shots[0][2] else next(s[1] for s in shots if not s[2]),
                                                ui=0, capture=1, t=0), w, h, 1.0)
            timeline, i = [], 0
            try:
                for sh, page, is_card, title in shots:
                    first = i
                    i = render_shot(b, sh, page, aspect, fps, frames, i, is_card)
                    timeline.append({"id": sh["id"], "start": round(first / fps, 3), "end": round(i / fps, 3),
                                     "subject": title or sh.get("kind", ""), "music": sh.get("music", "")})
                    grab = sh.get("grab", 0.85)
                    shutil.copyfile(frames / ("f%06d.jpg" % (first + int((i - first - 1) * grab))),
                                    grabs / ("%s-%s.jpg" % (aspect, sh["id"])))
            finally:
                b.close()
            video = out / ("release-%s.mp4" % aspect)
            fade_out = max(0.0, i / fps - 0.6)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "f%06d.jpg"),
                            "-vf", "fade=t=in:st=0:d=0.4,fade=t=out:st=%.2f:d=0.6" % fade_out,
                            "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(video)], check=True)
            report["aspects"][aspect] = {"video": str(video), "seconds": round(i / fps, 2), "timeline": timeline}
        (out / "markers.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        tl = report["aspects"][args.aspects.split(",")[0]]["timeline"]
        (out / "MUSIC_SLOT.txt").write_text(
            "MUSIC SLOT (not chosen): the videos are silent. Cut music to these shot boundaries\n"
            "(seconds, identical in every aspect):\n\n" +
            "\n".join("%6.2f-%6.2f  %-12s %s" % (s["start"], s["end"], s["id"], s["music"]) for s in tl) + "\n",
            encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "aspects"}, indent=1))
    for a, r in report["aspects"].items():
        print("%s: %s (%.1f s)" % (a, r["video"], r["seconds"]))


BOARD = {}

if __name__ == "__main__":
    main()
