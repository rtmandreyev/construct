"""Command-line workflow for hologram scenes (format version 2).

  new <category> [--title T] [--output scene.json]     a valid starter scene to edit
  check <scene.json>                                    validate, compile and audit
  build <scene.json> --out DIR [--asset-root DIR]       geometry.json, hologram.html, audit.txt
                     [--v1]                             … plus geometry.v1.json for v1 consumers
  review <scene.json> --out DIR [--asset-root DIR]      build, then capture the review set
  video <scene.json> --out FILE.mp4|.gif [--seconds S] [--fps N] [--start S] [--view V]

Exit status: 0 success, 1 the scene or audit has errors, 2 capture unavailable.
"""

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from . import audit as audit_mod
from . import diagnose as diagnose_mod
from . import params as params_mod
from . import product as product_mod
from . import hologram, render, scene as scene_mod

STARTER = {
    "object": ("A starter object", "object", [
        {"id": "body", "label": "Body", "role": "mass", "shape": {"type": "cylinder", "radius": 0.08, "height": 0.22},
         "certainty": "inferred", "stage": 0, "basis": ["height"]},
        {"id": "handle", "label": "Handle", "role": "identity",
         "shape": {"type": "tube", "path": [[0.08, 0.17, 0], [0.13, 0.15, 0], [0.13, 0.07, 0], [0.08, 0.05, 0]], "radius": 0.012},
         "certainty": "inferred", "stage": 1},
    ]),
    "architecture": ("A starter building", "architecture", [
        {"id": "hall", "label": "Hall", "role": "mass", "shape": {"type": "extrude", "profile": [[-6, -0.0], [6, 0], [6, 9], [0, 13], [-6, 9]], "height": 20, "axis": "z"},
         "at": [0, 0, -10], "certainty": "inferred", "stage": 0, "basis": ["height"]},
        {"id": "tower", "label": "Tower", "role": "identity", "shape": {"type": "box", "size": [4, 22, 4], "anchor": "base"},
         "at": [8, 0, 6], "certainty": "inferred", "stage": 1},
    ]),
    "machine": ("A starter machine", "machine", [
        {"id": "housing", "role": "mass", "shape": {"type": "box", "size": [1.2, 0.6, 0.8], "anchor": "base"}, "certainty": "inferred", "stage": 0, "basis": ["height"]},
        {"id": "rotor", "role": "identity", "shape": {"type": "torus", "major": 0.25, "minor": 0.04}, "at": [0, 0.85, 0], "rotate": [90, 0, 0],
         "certainty": "inferred", "stage": 1, "motion": {"type": "spin", "axis": [0, 0, 1], "rpm": 20}},
        {"id": "mast", "role": "structure", "shape": {"type": "cylinder", "radius": 0.03, "height": 0.25}, "at": [0, 0.6, 0], "certainty": "inferred", "stage": 1},
    ]),
    "organism": ("A starter creature", "organism", [
        {"id": "body", "role": "mass", "shape": {"type": "sphere", "radii": [0.3, 0.2, 0.5], "anchor": "base"}, "at": [0, 0.25, 0], "certainty": "inferred", "stage": 1, "basis": ["height"]},
        {"id": "leg", "role": "structure", "shape": {"type": "tube", "path": [[0.18, 0.35, 0.25], [0.3, 0.2, 0.3], [0.32, 0.0, 0.32]], "radius": [0.04, 0.03, 0.02]},
         "certainty": "inferred", "stage": 0, "mirror": "x", "repeat": {"count": 2, "step": {"at": [0, 0, -0.5]}}},
        {"id": "eye", "role": "identity", "shape": {"type": "sphere", "radius": 0.04}, "at": [0.12, 0.57, 0.38], "certainty": "inferred", "stage": 2, "mirror": "x"},
    ]),
    "cd": ("A generic CD in a jewel case", "cd", [
        {"id": "case", "role": "mass", "shape": {"type": "box", "size": [0.142, 0.125, 0.0104]}, "at": [0, 0.0625, 0], "certainty": "inferred", "stage": 0, "basis": ["height"]},
        {"id": "front", "role": "artwork", "shape": {"type": "plane", "size": [0.12, 0.12]}, "at": [0.008, 0.0625, 0.0053], "certainty": "decorative", "stage": 1,
         "artwork": {"slot": "cover-front"},
         "note": "an empty artwork slot until real, permitted cover bytes are supplied"},
    ]),
    "book": ("A generic hardcover book", "book", [
        {"id": "block", "role": "structure", "shape": {"type": "box", "size": [0.150, 0.228, 0.030], "ribs": 6}, "at": [0.002, 0.114, 0], "certainty": "inferred", "stage": 0, "basis": ["height"]},
        {"id": "cover", "role": "mass", "shape": {"type": "box", "size": [0.156, 0.234, 0.036]}, "at": [0, 0.117, 0], "certainty": "inferred", "stage": 1},
    ]),
}


def starter(category, title=None):
    if category not in STARTER:
        raise scene_mod.SceneError("no starter for %r; choose one of %s" % (category, ", ".join(sorted(STARTER))))
    default_title, cat, parts = STARTER[category]
    height = {"object": 0.22, "architecture": 13.0, "machine": 1.1, "organism": 0.7, "cd": 0.125, "book": 0.234}[category]
    return {
        "format": scene_mod.FORMAT, "version": scene_mod.VERSION,
        "id": "starter-%s" % category, "title": title or default_title,
        "subject": {"category": cat, "summary": "Replace with what the user asked for.", "accuracy": "generic", "synthetic": False},
        "units": "m", "seed": 7,
        "sources": [{"id": "request", "kind": "user_request", "title": "The user's request", "rights": "user_private"}],
        "facts": [{"key": "height", "value": height, "unit": "m", "certainty": "inferred", "source": "request",
                   "note": "typical size; replace with a measurement or a cited figure when one exists"}],
        "parts": json.loads(json.dumps(parts)),
        "presentation": {"framing": {"yaw": 35, "pitch": 18}, "atmosphere": {"haze": 0.7, "grid": True, "projector": category != "architecture"}},
        "animation": {"assembly": {"style": "ceremony", "seconds": 6.0, "interference": True},
                      "idle": {"life": "alive", "events": ["scan", "sweep", "shimmer"], "cadence": [5, 11], "strength": 0.6},
                      "camera": {"drift": 6, "breathe": 0.03}},
    }


def _write(path, text, force):
    path = Path(path)
    if path.exists() and not force:
        raise scene_mod.SceneError("%s exists; use --force to overwrite" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".hologram-", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def load(path):
    """A scene, or the scene a parameter document builds."""
    try:
        doc = hologram.read_sheet(path)
    except hologram.SheetError as exc:
        raise scene_mod.SceneError(str(exc))
    if params_mod.is_params(doc):
        return params_mod.expand(doc)
    return doc


def build(scene_path, out_dir, asset_root=None, v1=False, force=True, frame="y-up", palette=None, identity=None):
    scene = load(scene_path)
    geometry = scene_mod.compile_scene(scene)
    if palette or identity:  # the person's choice, never the model's
        geometry["presentation"]["style_hint"].update(
            {k: v for k, v in (("palette", palette), ("identity", identity)) if v}, note="chosen by the person (host option)")
    report = audit_mod.audit(scene, geometry)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = asset_root or str(Path(scene_path).resolve().parent)
    html, notes = render.build_html(geometry, root)
    _write(out / "geometry.json", json.dumps(geometry, separators=(",", ":")) + "\n", force)
    _write(out / "hologram.html", html, force)
    _write(out / "audit.json", json.dumps(report, indent=2) + "\n", force)
    text = audit_mod.format_report(report) + ("\n" + "\n".join("  note: " + n for n in notes) if notes else "")
    _write(out / "audit.txt", text + "\n", force)
    if v1:
        _write(out / "geometry.v1.json", json.dumps(scene_mod.to_v1(geometry), separators=(",", ":")) + "\n", force)
    if frame == "z-up":
        _write(out / "geometry.z-up.json", json.dumps(scene_mod.reframe(geometry, "z-up"), separators=(",", ":")) + "\n", force)
    return geometry, report, text


def add_commands(sub):
    p = sub.add_parser("new", help="write a valid starter scene for a category")
    p.add_argument("category", choices=sorted(STARTER))
    p.add_argument("--title")
    p.add_argument("--output")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("params", help="a parameter document for an archetype (the simple path); --list to see them all")
    p.add_argument("archetype", nargs="?", choices=sorted(params_mod.VARIANTS))
    p.add_argument("--variant")
    p.add_argument("--list", action="store_true")
    p.add_argument("--output")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("author", help="draft a hologram with any OpenAI-compatible model: check and repair until clean")
    p.add_argument("request", help="what to make, in plain words")
    p.add_argument("--base-url", required=True, help="e.g. https://api.deepseek.com/v1 or http://localhost:11434/v1")
    p.add_argument("--model", required=True)
    p.add_argument("--key-env", help="the environment variable that holds the API key (never stored)")
    p.add_argument("--out", required=True)
    p.add_argument("--params", action="store_true", help="ask for a parameter document (best for small models)")
    p.add_argument("--rounds", type=int, default=4)
    p = sub.add_parser("prompts", help="write the any-model authoring package (prompts and params schema)")
    p.add_argument("--out", required=True)
    p = sub.add_parser("expand", help="the full scene a parameter document builds")
    p.add_argument("params")
    p.add_argument("--output")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("check", help="validate, compile and audit a scene ('-' reads stdin); --json for "
                                     "machine-readable diagnostics with JSON paths and fix hints")
    p.add_argument("scene")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("build", help="geometry, the HTML preview and the audit")
    p.add_argument("scene")
    p.add_argument("--out", required=True)
    p.add_argument("--asset-root")
    p.add_argument("--v1", action="store_true")
    p.add_argument("--frame", choices=("y-up", "z-up"), default="y-up",
                   help="also write geometry.z-up.json for consumers with a Z-up object frame")
    p.add_argument("--palette", choices=scene_mod.PALETTES, help="a colour the person chose (the default is the house palette)")
    p.add_argument("--identity", choices=scene_mod.IDENTITIES, help="an identity tint the person chose")
    p = sub.add_parser("review", help="build, then capture contact sheets and stills")
    p.add_argument("scene")
    p.add_argument("--out", required=True)
    p.add_argument("--asset-root")
    p.add_argument("--size", default="1440x900")
    p.add_argument("--sheets", default=",".join(render.SHEETS))
    p.add_argument("--palette", choices=scene_mod.PALETTES, help="a colour the person chose (the default is the house palette)")
    p.add_argument("--identity", choices=scene_mod.IDENTITIES, help="an identity tint the person chose")
    p = sub.add_parser("video", help="render the animation to MP4 or GIF (needs ffmpeg)")
    p.add_argument("scene")
    p.add_argument("--out", required=True)
    p.add_argument("--asset-root")
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--view")
    p.add_argument("--size", default="1280x720")
    p.add_argument("--palette", choices=scene_mod.PALETTES, help="a colour the person chose (the default is the house palette)")
    p.add_argument("--identity", choices=scene_mod.IDENTITIES, help="an identity tint the person chose")


COMMANDS = ("new", "params", "expand", "prompts", "author", "check", "build", "review", "video")


def run(args):
    try:
        if args.command == "new":
            text = json.dumps(starter(args.category, args.title), indent=2) + "\n"
            if args.output:
                _write(args.output, text, args.force)
            else:
                sys.stdout.write(text)
            return 0
        if args.command == "params":
            if args.list or not args.archetype:
                sys.stdout.write(params_mod.describe() + "\n")
                return 0
            text = json.dumps(params_mod.template(args.archetype, args.variant), indent=2) + "\n"
            if args.output:
                _write(args.output, text, args.force)
            else:
                sys.stdout.write(text)
            return 0
        if args.command in ("author", "prompts"):
            try:
                importlib.import_module("." + ("runner" if args.command == "author" else "prompts"), __package__)
            except ImportError:
                sys.stderr.write("%s: not part of this package; use the full checkout (%s)\n" % (args.command, product_mod.REPO))
                return 2
        if args.command == "author":
            from . import runner
            try:
                return runner.run(args, sys.stdout)
            except runner.RunnerError as exc:
                sys.stderr.write("author: %s\n" % exc)
                return 2
        if args.command == "prompts":
            from . import prompts as prompts_mod
            for name in prompts_mod.write(args.out):
                sys.stdout.write("wrote %s\n" % Path(args.out, name))
            return 0
        if args.command == "expand":
            text = json.dumps(load(args.params), indent=2, ensure_ascii=False) + "\n"
            if args.output:
                _write(args.output, text, args.force)
            else:
                sys.stdout.write(text)
            return 0
        if args.command == "check":
            text = sys.stdin.read() if args.scene == "-" else Path(args.scene).read_text(encoding="utf-8")
            report = diagnose_mod.diagnose_text(text)
            if args.json:
                sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            elif report["stats"] is not None:  # it compiled: the audit report, then anything left to fix
                scene, _ = diagnose_mod.parse_text(text)
                if params_mod.is_params(scene):
                    scene = params_mod.expand(scene)
                sys.stdout.write(audit_mod.format_report(audit_mod.audit(scene, scene_mod.compile_scene(scene))) + "\n")
                if not report["ok"]:
                    sys.stdout.write("\nhow to fix:\n" + report["repair_text"] + "\n")
            else:
                sys.stdout.write("invalid scene (%d problems)\n%s\n" % (report["errors"], report["repair_text"]))
            return 0 if report["ok"] else 1
        if args.command == "build":
            _, report, text = build(args.scene, args.out, args.asset_root, args.v1, frame=args.frame,
                                    palette=args.palette, identity=args.identity)
            sys.stdout.write(text + "\nwrote %s\n" % Path(args.out, "hologram.html"))
            return 0 if report["ok"] else 1
        if args.command == "review":
            _, report, text = build(args.scene, args.out, args.asset_root, palette=args.palette, identity=args.identity)
            sys.stdout.write(text + "\n")
            w, h = (int(x) for x in args.size.lower().split("x"))
            sheets = [s for s in args.sheets.split(",") if s]
            paths = render.review(str(Path(args.out, "hologram.html")), str(Path(args.out, "review")), w, h, sheets=sheets)
            sys.stdout.write("captured:\n  %s\n" % "\n  ".join(paths))
            return 0 if report["ok"] else 1
        if args.command == "video":
            out = Path(args.out)
            with tempfile.TemporaryDirectory(prefix="hologram-video-") as tmp:
                build(args.scene, tmp, args.asset_root, palette=args.palette, identity=args.identity)
                w, h = (int(x) for x in args.size.lower().split("x"))
                render.frames(str(Path(tmp, "hologram.html")), str(Path(tmp, "frames")), args.seconds, args.fps,
                              args.start, w, h, view=args.view)
                out.parent.mkdir(parents=True, exist_ok=True)
                render.encode_video(str(Path(tmp, "frames")), str(out), args.fps)
            sys.stdout.write("wrote %s\n" % out)
            return 0
    except scene_mod.SceneError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except render.CaptureError as exc:
        sys.stderr.write("capture unavailable: %s\n" % exc)
        return 2
    return 1
