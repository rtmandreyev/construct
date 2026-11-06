"""Command-line workflow for Construct scenes (format construct-scene, version 2).

  new <category> [--title T] [--output scene.json]     a valid starter scene to edit
  check <scene.json>                                    validate, compile and audit
  build <scene.json> --out DIR [--asset-root DIR]       geometry.json, construct.html, audit.txt
                     [--v1]                             … plus geometry.v1.json for v1 consumers
  review <scene.json> --out DIR [--asset-root DIR]      build, then capture the review set
  video <scene.json> --out FILE.mp4|.gif [--seconds S] [--fps N] [--start S] [--view V]
  export <scene.json> --out FILE.glb|.obj [--wire edges|tubes|none] [--pose closed|open]
                      [--materials map.json] [--frame y-up|z-up] [--merge] [--colliders] [--pieces [glued]]
                                                        a 3D model (docs/EXPORT.md, docs/GODOT.md)
  print <scene.json> --out FILE.stl|.3mf [--size MM | --scale N] [--detail MM] [--wall MM] [--join MM]
                     [--lines engrave|raised] [--bed WxDxH]   one watertight body to 3D print (docs/PRINTING.md)
  freecad <scene.json> --out FILE.FCStd|.step [--step FILE.step] [--freecad PATH]
                                                        named solids and joints in FreeCAD, and STEP (docs/FREECAD.md)

Exit status: 0 success, 1 the scene or audit has errors, 2 capture unavailable.
"""

import html
import importlib
import json
import os
import re
import shutil
import subprocess
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
        with open(path, "rb"):   # a file that is not there or cannot be opened raises its own error, naming it
            pass
        if str(exc).endswith("RecursionError"):
            raise scene_mod.SceneError("%s is nested too deeply to read (thousands of brackets inside each other)" % path)
        raise scene_mod.SceneError(str(exc).replace("sheet", "file"))
    if params_mod.is_params(doc):
        return params_mod.expand(doc)
    return doc


def build(scene_path, out_dir, asset_root=None, v1=False, force=True, frame="y-up", palette=None, identity=None,
          film=False):
    scene = load(scene_path)
    geometry = scene_mod.compile_scene(scene)
    if palette or identity:  # the person's choice, never the model's
        geometry["presentation"]["style_hint"].update(
            {k: v for k, v in (("palette", palette), ("identity", identity)) if v}, note="chosen by the person (host option)")
    report = audit_mod.audit(scene, geometry)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = asset_root or str(Path(scene_path).resolve().parent)
    html, notes = render.build_html(geometry, root, film=film, solid=render.solid_payload(scene, geometry))
    _write(out / "geometry.json", json.dumps(geometry, separators=(",", ":")) + "\n", force)
    _write(out / "construct.html", html, force)
    _write(out / "audit.json", json.dumps(report, indent=2) + "\n", force)
    text = audit_mod.format_report(report) + ("\n" + "\n".join("  note: " + n for n in notes) if notes else "")
    _write(out / "audit.txt", text + "\n", force)
    if v1:
        _write(out / "geometry.v1.json", json.dumps(scene_mod.to_v1(geometry), separators=(",", ":")) + "\n", force)
    if frame == "z-up":
        _write(out / "geometry.z-up.json", json.dumps(scene_mod.reframe(geometry, "z-up"), separators=(",", ":")) + "\n", force)
    return geometry, report, text


def _critique(args, critic_mod):
    """Build the packet; record an answer; or run the critic as a second model call and record it."""
    scene_path = Path(args.scene)
    out = Path(args.out) if args.out else scene_path.resolve().parent / "critique"
    doc, diags = diagnose_mod.parse_text(scene_path.read_text(encoding="utf-8"))
    if doc is None:
        sys.stderr.write("critique: %s\n" % "; ".join(d["message"] for d in diags))
        return 1
    try:
        if args.record:
            answer, _ = diagnose_mod.parse_text(Path(args.record).read_text(encoding="utf-8"))
            model = None
        else:
            pk = critic_mod.packet(str(scene_path), str(out), args.reference, args.request)
            if not args.base_url:
                sys.stdout.write("wrote the packet: %s\nGive packet.md and its images to a fresh critic (a subagent, a "
                                 "delegated task or another model) and save its answer as critique.json, then:\n"
                                 "  construct critique %s --record critique.json\n" % (out / "packet.md", args.scene))
                return 0
            key = os.environ.get(args.key_env) if args.key_env else None
            from . import runner
            answer, _ = critic_mod.run(pk, str(out), args.base_url, args.model, key,
                                       log=lambda m: sys.stdout.write(m + "\n"))
            (out / "critique.json").write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            model = args.model
        if not isinstance(answer, dict):
            raise critic_mod.CriticError("the answer is not a JSON object")
        new, verdict = critic_mod.record(doc, answer, model)
    except (critic_mod.CriticError, OSError) as exc:
        sys.stderr.write("critique: %s\n" % exc)
        return 1
    scene_path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    (out / "defects.md").write_text(critic_mod.defects_text(answer, top=10) + "\n", encoding="utf-8")
    sys.stdout.write("verdict: %s (scores %s)\nrecorded in %s; ranked defects in %s\n" % (
        verdict, ", ".join("%s %d" % kv for kv in answer["scores"].items()), scene_path, out / "defects.md"))
    return 0


def _rounds(args):
    from . import rounds
    folder, a = Path(args.dir), list(args.args)
    try:
        if args.action == "start":
            if len(a) != 1:
                raise rounds.RoundsError("usage: construct rounds start scene.json [--tier masterpiece] [--dir run]")
            st = rounds.start(a[0], args.tier, folder if args.dir != "." else Path(a[0]).resolve().parent)
            sys.stdout.write("started: round 1, %s mode, %s; the medium's limits are seeded as known limits (L1-L3)\n" % (
                st["tier"], "stops after 2 rounds without a win, at %d rounds or %d minutes of %s" % (
                    st["max_rounds"], st["limit_seconds"] // 60, "working time, the critic's included"
                    if st["tier"] == "timeboxed" else "active time") if st.get("limit_seconds") else
                "stops only after 2 rounds without a win (or every criterion 3): no round cap, no time ceiling, so "
                "report every round and let the user stop it"))
        elif args.action == "change":
            if len(a) != 2:
                raise rounds.RoundsError("usage: construct rounds change D3 \"what changed\"")
            st = rounds.change(folder, a[0], a[1])
            sys.stdout.write("round %d: %d change(s) on %s\n" % (st["round"], len(st["changes"]), ", ".join(
                sorted({c["ledger"] for c in st["changes"]}))))
        elif args.action == "packet":
            scene = rounds.scene_of(folder)
            pk, key = rounds.packet(folder, scene, args.reference, args.request, args.out)
            sys.stdout.write("round packet: %s (part 1 this version%s, part 3 the ledger)\nGive it to ONE fresh critic "
                             "started in that folder, or `construct rounds run --base-url ...`; then:\n"
                             "  construct rounds record answer.json\n" % (pk, "" if key is None else ", part 2 the pair"))
        elif args.action in ("record", "run"):
            if args.action == "record":
                if len(a) != 1:
                    raise rounds.RoundsError("usage: construct rounds record answer.json")
                answer, _ = diagnose_mod.parse_text(Path(a[0]).read_text(encoding="utf-8"))
                if not isinstance(answer, dict):
                    raise rounds.RoundsError("the answer is not a JSON object")
                model = None
            else:
                base = args.base_url or os.environ.get("CONSTRUCT_CRITIC_BASE_URL")
                if not base:
                    raise rounds.RoundsError("run needs --base-url (or CONSTRUCT_CRITIC_BASE_URL)")
                model = args.model or os.environ.get("CONSTRUCT_CRITIC_MODEL")
                key_env = args.key_env or os.environ.get("CONSTRUCT_CRITIC_KEY_ENV")
                st = rounds.state(folder)
                if not st.get("packet") or st.get("step") != "packet":
                    raise rounds.RoundsError("no round packet waiting: `construct rounds packet` first")
                answer = rounds.run(st["packet"], base, model, os.environ.get(key_env) if key_env else None,
                                    log=lambda m: sys.stdout.write(m + "\n"))
            e = rounds.record(folder, answer, rounds.scene_of(folder), model)
            st = rounds.state(folder)
            if st["tier"] in ("masterpiece", "timeboxed", "unbounded") or e["stop"]:
                sys.stdout.write(rounds.summary(e) + "\n")
            else:
                sys.stdout.write("round %d recorded (%s); details in rounds.md\n" % (e["round"], "kept" if e["kept"] else "reverted"))
        elif args.action == "pause":
            rounds.pause(folder)
            sys.stdout.write("paused: the time until the next command is not counted; resume with `construct rounds "
                             "status`\n")
        elif args.action == "status":
            sys.stdout.write(rounds.status(folder) + "\n")
        else:
            sys.stdout.write(rounds.report(folder))
    except (rounds.RoundsError, OSError) as exc:
        sys.stderr.write("rounds: %s\n" % exc)
        return 1
    return 0


def page_in(folder):
    """The built page in a folder: construct.html (or hologram.html from before 0.2)."""
    new = Path(folder, "construct.html")
    return str(new if new.exists() or not Path(folder, "hologram.html").exists() else Path(folder, "hologram.html"))


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
    p.add_argument("--seed", type=int, help="a seeded variant: sizes drawn near the standard, the same seed the same "
                                            "object (marked synthetic)")
    p.add_argument("--output")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("author", help="draft a construct with any OpenAI-compatible model: check and repair until clean")
    p.add_argument("request", help="what to make, in plain words")
    p.add_argument("--base-url", required=True, help="e.g. https://api.deepseek.com/v1 or http://localhost:11434/v1")
    p.add_argument("--model", required=True)
    p.add_argument("--key-env", help="the environment variable that holds the API key (never stored)")
    p.add_argument("--out", required=True)
    p.add_argument("--params", action="store_true", help="ask for a parameter document (best for small models)")
    p.add_argument("--reference", action="append",
                   help="a reference image (a local photo or an https URL), optionally view=image (side=photo.jpg) so "
                        "the critic compares it with the render from that view; repeatable")
    p.add_argument("--tier", "--mode", dest="tier", choices=("fast", "masterpiece", "timeboxed", "unbounded", "quick",
                                                            "standard", "showcase"),
                   help="the mode and its limits: fast (the default: one pass, 10 min; quick, standard and showcase "
                        "are its tiers), masterpiece (the critic every round: 12 rounds, 2 hours), timeboxed (masterpiece in 2 "
                        "hours in all, the critic's time included), unbounded (only on "
                        "explicit request: no round cap, no time ceiling); also 'mode: ...' in the request")
    p.add_argument("--research", choices=("auto", "on", "off"),
                   help="auto follows the research policy; on/off overrides it (also 'research: ...' in the request)")
    p.add_argument("--vision", action="store_true",
                   help="the model can see images: review its own captures and improve (needs a browser)")
    p.add_argument("--rounds", type=int, help="override the tier's check rounds")
    p.add_argument("--review-rounds", type=int, help="override the tier's review/improve rounds")
    p.add_argument("--max-seconds", type=float, help="override the tier's wall clock")
    p.add_argument("--max-images", type=int, help="override the tier's limit on web reference images")
    p.add_argument("--critic", action="store_true",
                   help="an independent critic (a fresh call, same endpoint) judges each review against the references")
    p.add_argument("--critic-model", help="the critic's model (implies --critic)")
    p.add_argument("--critic-base-url", help="the critic's endpoint (default: the author's)")
    p.add_argument("--critic-key-env", help="the critic's API key variable (default: the author's)")
    p.add_argument("--max-total-tokens", type=int, help="stop when prompt + completion tokens reach this")
    p.add_argument("--max-cost", type=float, help="stop when the estimated cost (USD) reaches this")
    p.add_argument("--price-in", type=float, help="USD per million prompt tokens (for --max-cost)")
    p.add_argument("--price-out", type=float, help="USD per million completion tokens (for --max-cost)")
    p = sub.add_parser("trace", help="fit a traced outline (construct-trace) to a documented dimension: an extrude profile")
    p.add_argument("trace")
    p.add_argument("--fit", required=True, help="a:b=metres between two traced features, or height=metres / width=metres")
    p.add_argument("--origin", default="bottom-center", help="bottom-center, center or feature:<name>")
    p.add_argument("--points", type=int, default=96)
    p.add_argument("--out")
    p = sub.add_parser("trace-image", help="have a vision model trace a reference image, then fit it (OpenAI-compatible)")
    p.add_argument("image", nargs="+", help="local image files (the user's photos) or https URLs viewed, never kept")
    p.add_argument("--what", required=True, help='what to trace, e.g. "the guitar body outline, front view"')
    p.add_argument("--features", help="comma-separated feature names to mark, e.g. nut,bridge,neck-joint")
    p.add_argument("--fit", required=True)
    p.add_argument("--origin", default="bottom-center")
    p.add_argument("--points", type=int, default=96)
    p.add_argument("--title", help="how to cite the reference")
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--key-env")
    p.add_argument("--out", required=True)
    p = sub.add_parser("terrain", help="a measured-terrain construct from elevation data you supply (.asc or .xyz)")
    p.add_argument("--dem", required=True, nargs="+",
                   help="ESRI ASCII grids (.asc) or XYZ exports, or a folder of tiles; never downloaded")
    p.add_argument("--center", help="lat,lon (WGS84) of the area's centre")
    p.add_argument("--extent", type=float, help="the area's side in metres, with --center")
    p.add_argument("--bbox", help="xmin,ymin,xmax,ymax in the grid's coordinates")
    p.add_argument("--crs", help="EPSG:2056 (Swiss LV95), EPSG:326xx/327xx (UTM) or EPSG:4326; guessed when omitted")
    p.add_argument("--resolution", type=int, default=72, help="grid cells along the longer side (8..100)")
    p.add_argument("--class", dest="cls", choices=("spot", "site", "valley", "massif", "range"), help="scale class (from the extent when omitted)")
    p.add_argument("--exaggeration", type=float, default=1.0, help="vertical exaggeration, stated on the construct (1 = true)")
    p.add_argument("--title", default="Terrain")
    p.add_argument("--source-title", required=True, help='the dataset and its attribution, e.g. "swissALTI3D, ©swisstopo"')
    p.add_argument("--source-ref")
    p.add_argument("--rights", default="permitted", choices=("permitted", "public_domain", "user_private"))
    p.add_argument("--gpx", help="a route to drape on the terrain")
    p.add_argument("--mark", action="append", default=[], help="Name=lat,lon; repeatable")
    p.add_argument("--from", dest="view_from", default="S", help="the side to view from: S, SE, E, NE, N, NW, W, SW")
    p.add_argument("--plain", action="store_true", help="no traced ridgelines or summit marker")
    p.add_argument("--into", help="put the terrain under an existing scene as its plinth, at real scale, the ground "
                                  "at --center level with the scene's y = 0")
    p.add_argument("--output", help="the terrain scene to write (or use --into)")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("critique", help="an independent critic's packet (renders beside references), its answer, "
                                         "or a second model call that runs it")
    p.add_argument("scene")
    p.add_argument("--out", help="the packet folder (default: <scene folder>/critique)")
    p.add_argument("--reference", action="append", default=[],
                   help="view=image: a reference photo and the view it shows (front, side, back, top, three-quarter, hero); repeatable")
    p.add_argument("--request", help="the request in plain words (default: the scene's summary)")
    p.add_argument("--record", help="a construct-critique answer to check and record in the scene's authoring block")
    p.add_argument("--base-url", help="run the critic as a second model call on this OpenAI-compatible endpoint")
    p.add_argument("--model")
    p.add_argument("--key-env")
    p = sub.add_parser("rounds", help="improvement rounds: a defect ledger, a pairwise gate, stop rules and a log")
    p.add_argument("action", choices=("start", "change", "packet", "record", "run", "pause", "status", "report"))
    p.add_argument("args", nargs="*", help="start: scene.json; change: ID \"what changed\"; record: answer.json")
    p.add_argument("--dir", default=".", help="the run's folder (state.json, ledger.json, rounds.md, checkpoints/)")
    p.add_argument("--tier", "--mode", dest="tier", default="masterpiece", choices=("masterpiece", "timeboxed", "unbounded"),
                   help="masterpiece (12 rounds, 2 hours active), timeboxed (the same, 2 hours in all: the critic's "
                        "time counted too) or unbounded (only the stop rules; explicit request)")
    p.add_argument("--reference", action="append", default=[], help="view=image, as for critique; repeatable")
    p.add_argument("--request", help="the request in plain words")
    p.add_argument("--out", help="the packet folder (default: a neutral folder in the temp directory)")
    p.add_argument("--base-url", help="run the round's critic as direct model calls (default: $CONSTRUCT_CRITIC_BASE_URL)")
    p.add_argument("--model")
    p.add_argument("--key-env")
    p = sub.add_parser("compare", help="measure the construct's silhouette from a view against a traced reference")
    p.add_argument("scene")
    p.add_argument("--trace", required=True, help="the reference's construct-trace (its outline in pixels)")
    p.add_argument("--view", default="side", help="front, side, back, top, three-quarter or one of the scene's views")
    p.add_argument("--fit", default="width", choices=("width", "height"), help="the dimension both are scaled to")
    p.add_argument("--overlay", help="write the two outlines over each other as a PNG")
    p.add_argument("--record", action="store_true", help="record the result in the scene's authoring block")
    p = sub.add_parser("loft-from-traces", help="loft stations for a body from traced side, top and front views")
    p.add_argument("--side", required=True, help="construct-trace of the side view")
    p.add_argument("--top", required=True, help="construct-trace of the top (plan) view")
    p.add_argument("--front", help="construct-trace of the front view (how the body narrows towards its top)")
    p.add_argument("--length", required=True, type=float, help="the documented overall length, metres")
    p.add_argument("--height", type=float, help="the documented height, to check the traces against")
    p.add_argument("--width", type=float, help="the documented width, to check the traces against")
    p.add_argument("--stations", type=int, default=24)
    p.add_argument("--nose-side", default="left", choices=("left", "right"), help="where the nose is in the side image")
    p.add_argument("--nose-top", default="up", choices=("up", "down", "left", "right"),
                   help="where the nose is in the top image")
    p.add_argument("--sill", type=float, help="the body's lowest height between the wheels (default 10%% of the height)")
    p.add_argument("--out", help="write the result (loft shape, sources, part stub, checks) as JSON")
    p.add_argument("--into", help="a scene whose part gets this loft as its shape (with the references as sources)")
    p.add_argument("--part", default="body", help="the part to replace with --into")
    p.add_argument("--drop", action="append", default=[],
                   help="parts the traced body replaces, removed with --into (a traced side includes the cabin: "
                        "--drop glasshouse); repeatable")
    p = sub.add_parser("globe", help="a measured globe from coastline data you supply (GeoJSON)")
    p.add_argument("--coastlines", required=True, help="GeoJSON lines or polygons in longitude/latitude; never downloaded")
    p.add_argument("--title", default="Earth")
    p.add_argument("--source-title", required=True, help='the dataset and its attribution, e.g. "Natural Earth (public domain)"')
    p.add_argument("--source-ref")
    p.add_argument("--rights", default="public_domain", choices=("permitted", "public_domain", "user_private"))
    p.add_argument("--graticule", type=int, default=30, choices=(0, 10, 15, 20, 30, 45), help="degrees; 0 for none")
    p.add_argument("--no-tilt", action="store_true", help="draw the axis upright instead of at the axial tilt")
    p.add_argument("--rpm", type=float, default=1.0, help="spin speed (0: still)")
    p.add_argument("--output", required=True)
    p.add_argument("--force", action="store_true")
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
    p.add_argument("--fit", action="store_true",
                   help="also how its solids fit: parts that poke through others where it shows, and parts buried in "
                        "others (what a solid, a print or a kit shows and the light forgives)")
    p.add_argument("--cells", type=int, default=160,
                   help="--fit: voxels along the longest side (default 160; more finds thinner parts, slower)")
    p = sub.add_parser("build", help="geometry, the HTML preview and the audit")
    p.add_argument("scene")
    p.add_argument("--out", required=True)
    p.add_argument("--asset-root")
    p.add_argument("--v1", action="store_true")
    p.add_argument("--frame", choices=("y-up", "z-up"), default="y-up",
                   help="also write geometry.z-up.json for consumers with a Z-up object frame")
    p.add_argument("--palette", choices=scene_mod.PALETTES, help="a colour the person chose (the default is the house palette)")
    p.add_argument("--identity", choices=scene_mod.IDENTITIES, help="an identity tint the person chose")
    p.add_argument("--film", action="store_true", help="also embed film mode, for ?assembly=, ?audio=, ?reactivity= "
                                                        "and ?camera=steady (docs/FILM.md)")
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
    p.add_argument("--seconds", type=float, help="length of the video (default 12, or the assembly plus 3 s with --assembly)")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--view")
    p.add_argument("--size", default="1280x720")
    p.add_argument("--palette", choices=scene_mod.PALETTES, help="a colour the person chose (the default is the house palette)")
    p.add_argument("--identity", choices=scene_mod.IDENTITIES, help="an identity tint the person chose")
    p.add_argument("--assembly", type=float, help="film mode: the assembly lasts this many seconds (e.g. a whole track), "
                                                   "overriding the scene's")
    p.add_argument("--audio", help="film mode: audio features from `audio` (energy, high, voice); the build and the "
                                   "light follow them")
    p.add_argument("--sound", help="film mode: an audio file to put in the MP4, from --start, cut to the video's length")
    p.add_argument("--camera", choices=("tour", "steady", "still"), default="tour",
                   help="tour: the scene's own camera choreography (the default); steady: one long shot from the "
                        "view, drifting and breathing; still: the view held, no motion")
    p.add_argument("--reactivity", type=float, help="film mode, with --audio: how strongly the music shows, 0..2 "
                                                    "(default 1; 0 is an even build with no light or accents)")
    p = sub.add_parser("export", help="a 3D model: glTF (.glb) for Blender, game engines and the web, or OBJ "
                                      "(docs/EXPORT.md)")
    p.add_argument("scene")
    p.add_argument("--out", required=True, help="FILE.glb or FILE.obj (an .mtl is written beside it)")
    p.add_argument("--format", choices=("glb", "obj"), help="default: from the file's extension")
    p.add_argument("--wire", choices=("edges", "tubes", "seams", "none"), default="edges",
                   help="the line art: edges (default), thin tubes (for engines that drop lines), tubes for the "
                        "design lines only (seams, creases, outlines: for finished game models) or none")
    p.add_argument("--wire-radius", type=float, help="the tubes' radius in metres (default: from the object's size)")
    p.add_argument("--pose", choices=("closed", "open"), default="closed",
                   help="the pose the model rests in; glTF also carries the open animation either way")
    p.add_argument("--materials", help="a material map: part ids or patterns to colour, metalness and roughness")
    p.add_argument("--frame", choices=("y-up", "z-up"), default="y-up", help="OBJ only (glTF is always Y up)")
    p.add_argument("--merge", action="store_true",
                   help="glTF: merge every part that does not move into one mesh per material (for game engines)")
    p.add_argument("--colliders", action="store_true",
                   help="glTF: a box collider per part, <part>-convcolonly (a collision shape in Godot), moving with its joint")
    p.add_argument("--pieces", nargs="?", const="loose", choices=("loose", "glued"),
                   help="glTF: the pieces it would break into, each a rigid body with convex shapes (OMI_physics_body; "
                        "a RigidBody3D in Godot), interlocked parts together, made to settle rather than burst; "
                        "glued: what stays put is one body and each hinged or sliding part one more, its joint in its "
                        "extras (docs/GODOT.md connects them)")
    p.add_argument("--quality", action="store_true",
                   help="glTF: each triangle coloured by its smallest angle (green good, amber under 20 degrees, red "
                        "under 10: slivers that subdivide and shade badly)")
    p = sub.add_parser("print", help="one watertight body to 3D print: STL or 3MF, checked (docs/PRINTING.md)")
    p.add_argument("scene")
    p.add_argument("--out", help="FILE.stl or FILE.3mf")
    p.add_argument("--format", choices=("stl", "3mf"), help="default: from the file's extension")
    size = p.add_mutually_exclusive_group()
    size.add_argument("--size", type=float, help="the longest side in mm (default %g)" % 100.0)
    size.add_argument("--scale", type=float, help="print at 1:N of the object's real size, e.g. 43")
    size.add_argument("--fit", action="store_true", help="the largest print that stands on the printer's bed")
    p.add_argument("--printer", choices=("small", "desktop", "cube", "large", "resin"),
                   help="a printer class: its bed, its finest voxel and its thinnest wall (--printers compares them)")
    p.add_argument("--exact", action="store_true",
                   help="3MF: the construct's own solids as they are, parts of one object the slicer joins (only open "
                        "and too-thin surfaces become voxels): every detail the construct has, at the printer's resolution")
    p.add_argument("--printers", action="store_true",
                   help="for each printer class, the largest print and how much detail survives; writes nothing")
    p.add_argument("--detail", type=float, help="the voxel size in mm (default 0.4, a nozzle's width, or the printer's)")
    p.add_argument("--wall", type=float, help="open surfaces are thickened to this wall in mm (default 0.8, or the printer's)")
    p.add_argument("--join", type=float, default=1.6,
                   help="close gaps between parts up to this wide, in mm, so the print is one piece (default 1.6; 0: off)")
    p.add_argument("--lines", nargs="?", const="raised", default="none", choices=("none", "engrave", "raised"),
                   help="the parts drawn only in lines: none (left out, the default), engrave (cut into the surface, "
                        "like a model kit's panel lines) or raised (--lines alone)")
    p.add_argument("--bed", help="the printer's build volume in mm (default 250x210x220, or the printer's)")
    p = sub.add_parser("kit", help="a model kit to print, glue and paint: pieces on plates, numbered, with a booklet "
                                   "(docs/PRINTING.md)")
    p.add_argument("scene")
    p.add_argument("--out", required=True, help="the folder for the plates (3MF), booklet.html and kit.json")
    size = p.add_mutually_exclusive_group()
    size.add_argument("--scale", type=float, default=24, help="1:N (default 24, a common car-kit scale)")
    size.add_argument("--size", type=float, help="the built model's longest side in mm, instead of a scale")
    p.add_argument("--detail", type=float, default=0.35, help="the voxel size in mm (default 0.35)")
    p.add_argument("--printer", choices=("small", "desktop", "cube", "large", "resin"),
                   help="a printer class: its bed for the plates (a large kit wants a large bed)")
    p.add_argument("--plan", help="a kit plan (kit-plan.json): parts to merge, small parts to keep, clear parts, a title")
    p.add_argument("--materials", help="a material map: each piece's paint (default: <scene>.materials.json beside it)")
    p.add_argument("--bed", help="the printer's build volume in mm (default 250x210x220, or the printer's)")
    p.add_argument("--critic", action="store_true", help="print the kit critic's brief and stop")
    p.add_argument("--only", help="also only.3mf: just these pieces on a plate, to print again (numbers as on the "
                                  "plates, ranges, or part names: '12,14', '3-5', 'door-glass*')")
    p = sub.add_parser("freecad", help="named solids and joints in FreeCAD (.FCStd), and STEP; runs FreeCAD "
                                       "(docs/FREECAD.md)")
    p.add_argument("scene")
    p.add_argument("--out", required=True, help="FILE.FCStd, or FILE.step for STEP alone")
    p.add_argument("--step", help="also write STEP here")
    p.add_argument("--freecad", help="the FreeCAD command line to run (default: $CONSTRUCT_FREECAD, `freecadcmd`, "
                                     "or the usual installs)")
    p.add_argument("--facets", action="store_true",
                   help="every part faceted as the construct draws it, instead of true shapes (exact solids, splines, "
                        "NURBS lofts) where the part's shape allows")
    p = sub.add_parser("netlogo-compare", help="NetLogo runs side by side (2 to 8), drawn the same way on one time "
                                               "scale (a slider moved step by step, other seeds)")
    p.add_argument("runs", nargs="+", help="the recordings (.jsonl), left to right")
    p.add_argument("--view", default="auto", help="space-time, network-time, phase, field or auto (default)")
    p.add_argument("--labels", help="the runs' names, left to right, as 'vision 3,vision 6' (default A,B,C...)")
    p.add_argument("--state", help="network-time: the variable that turns")
    p.add_argument("--title")
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("netlogo-film", help="a NetLogo run as a film in Blender: every turtle as moving light "
                                            "(needs Blender; docs/NETLOGO.md)")
    p.add_argument("run", help="the recording (.jsonl)")
    p.add_argument("--out", help="render the film to this .mp4")
    p.add_argument("--blend", help="save the film's scene as this .blend, to play or render in Blender")
    p.add_argument("--size", default="1920x1080")
    p.add_argument("--from", dest="start", type=float, default=0.0, help="seconds into the run to start at")
    p.add_argument("--seconds", type=float, help="how long (default: the whole run)")
    p.add_argument("--samples", type=int, default=16, help="EEVEE samples per frame")
    p.add_argument("--trail", type=float, default=0.35, help="seconds of light trail behind each turtle")
    p.add_argument("--blender", help="the Blender to run (default: $CONSTRUCT_BLENDER, `blender`, or the usual installs)")
    p = sub.add_parser("netlogo-plates", help="a NetLogo run as printed plates, one per moment, that stack in order "
                                              "on pins: a simulation you can hold (docs/PRINTING.md)")
    p.add_argument("run", help="the recording (.jsonl)")
    p.add_argument("--out", required=True, help="the folder for the plates, pins, sleeves and KEY.md")
    when = p.add_mutually_exclusive_group()
    when.add_argument("--plates", type=int, default=6, help="how many plates, evenly over the run (default 6)")
    when.add_argument("--at", help="the ticks to print, e.g. 0,20,68,300")
    p.add_argument("--size", type=float, default=100.0, help="the world's longer side in mm (default 100)")
    p.add_argument("--format", choices=("3mf", "stl"), default="3mf")
    p.add_argument("--title", help="the title on the key card (default: the model's)")
    p.add_argument("--state", help="the true/false turtle variable shown by a dot's height (default: the first)")
    p.add_argument("--tall", choices=("true", "false"), default="true",
                   help="which value stands tall (Fireflies: --state hidden? --tall false, the flashing ones)")
    p = sub.add_parser("netlogo-instrument", help="a copy of a NetLogo model that records its run for Construct, "
                                                  "and a headless experiment (docs/NETLOGO.md)")
    p.add_argument("model", help="the model (.nlogox)")
    p.add_argument("--title", required=True, help="the model's name, as the construct will cite it")
    p.add_argument("--out", required=True, help="a folder for the copy, construct.nls and the experiment")
    p.add_argument("--run-file", default="run.jsonl", help="the recording's name, beside the model (default run.jsonl)")
    p.add_argument("--turtles", default="", help="turtle variables or reporters to record, comma-separated")
    p.add_argument("--reporters", default="", help="observer reporters to record each tick, separated by ';'")
    p.add_argument("--patches", help="a patch reporter and how often, as REPORTER:EVERY (for example pcolor:5)")
    p.add_argument("--every", type=int, default=1, help="record every N ticks (default 1)")
    p.add_argument("--seed", type=int, help="the random seed the experiment sets (recorded with the run)")
    p.add_argument("--ticks", type=int, default=500, help="the experiment's time limit (default 500)")
    p.add_argument("--no-turtles", action="store_true", help="record no turtles (reporters or patches only)")
    p.add_argument("--setup", help="the model's setup command (default: its `setup`, else its setup button; with "
                   "inputs, if it takes any: \"setup 3\")")
    p.add_argument("--go", help="the model's go command (default: its `go`, else its forever button)")
    p = sub.add_parser("netlogo", help="a construct of a recorded NetLogo run (docs/NETLOGO.md)")
    p.add_argument("run", help="the recording (.jsonl, written by construct.nls)")
    p.add_argument("--view", required=True, choices=("auto", "space-time", "network-time", "phase", "field", "pulse"),
                   help="auto: the view the data suits (a network that turned, changing patches, turtles switching "
                        "on and off (pulse), two moving counts, else the agents' paths)")
    p.add_argument("--out", required=True, help="the scene to write (.json); then `build` it")
    p.add_argument("--title", help="the construct's title (default: the model's)")
    p.add_argument("--state", help="network-time: the turtle variable whose turning true lifts a node; pulse: the "
                                   "true/false variable that switches on and off (hidden? too)")
    p.add_argument("--landmarks", choices=("on", "off"), default="on", help="mark the moments worth marking, computed "
                   "from the run's first count (half way and most of the way, a peak, or half and all at once): on (default) or off")
    p.add_argument("--colors", choices=("run", "house"), default="run",
                   help="run (default): the run's own NetLogo colours, made to read as light; house: Construct's tones")
    p.add_argument("--window", help="space-time and pulse: auto (default: the window where the order formed, when "
                                    "it forms early), whole (the whole run), or the tick to end at")
    p.add_argument("--x", help="phase: the reporter across the floor (default: the first recorded)")
    p.add_argument("--z", help="phase: the reporter front to back (default: the second)")
    p.add_argument("--change", choices=("first", "last"), default="first", help="field: lift each patch to its "
                                                                               "first or its last change")
    p.add_argument("--max-agents", type=int, help="space-time: draw at most this many turtles (default 150)")
    p.add_argument("--smooth", type=int, help="phase: a centred moving average over N records (recorded as a fact)")
    p.add_argument("--levels", type=int, help="field: how many fronts to draw (default 32)")
    p.add_argument("--resolution", type=int, help="field: blocks across the world (default 64)")
    p.add_argument("--time", choices=("linear", "sqrt"),
                   help="height from ticks: linear (default) or sqrt, to stretch a run whose changes come early")
    p.add_argument("--solid", action="store_true", help="add solids for a 3D model: each turtle as a sphere "
                   "(network-time), the cycle as a tube (phase), the change as a surface (field)")
    p.add_argument("--materials-out", help="also write a material map in the run's own NetLogo colours (for export)")
    p.add_argument("--csv", help="also write the run's counts at every record as CSV (the clock, each reporter, each "
                                 "breed's turtles), for a spreadsheet")
    p.add_argument("--glb", help="also export the 3D model (.glb: tubes, solids, the run's colours, the build)")
    p.add_argument("--art", help="an art-direction layer (art.json) on top of the data: views, emphasis, labels, "
                                 "milestones; never the data itself (docs/NETLOGO.md)")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("audio", help="film mode: per-frame audio features (energy, high, voice) for `video --audio`")
    p.add_argument("music", help="the track (any format ffmpeg reads)")
    p.add_argument("--out", required=True, help="the features JSON")
    p.add_argument("--voice", help="an optional voice stem; its level drives the voice shimmer")
    p.add_argument("--fps", type=int, default=24, help="frames per second of the features (match the video's)")
    p.add_argument("--scale", choices=("track", "fixed"), default="track",
                   help="track (default): each track mapped to its own loudness range; fixed: the older -40..-10 dB window")


def export_errors():
    from . import export
    return export.ExportError


def printing_list(ids):
    from . import printing
    return printing._list(ids)


COMMANDS = ("new", "params", "expand", "prompts", "author", "trace", "trace-image", "terrain", "globe", "critique", "rounds", "compare", "loft-from-traces", "check", "build", "review",
            "video", "audio", "export", "print", "kit", "freecad", "netlogo-plates", "netlogo", "netlogo-instrument", "netlogo-film", "netlogo-compare")


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
            doc = params_mod.template(args.archetype, args.variant)
            if args.seed is not None:
                doc = params_mod.vary(doc, args.seed)
            text = json.dumps(doc, indent=2) + "\n"
            if args.output:
                _write(args.output, text, args.force)
            else:
                sys.stdout.write(text)
            return 0
        if args.command == "terrain":
            from . import terrain as terrain_mod
            try:
                sc = terrain_mod.build(
                    args.dem, center=tuple(float(x) for x in args.center.split(",")) if args.center else None,
                    extent=args.extent, bbox=tuple(float(x) for x in args.bbox.split(",")) if args.bbox else None,
                    crs=args.crs, resolution=args.resolution, cls=args.cls, exaggeration=args.exaggeration,
                    title=args.title, source_title=args.source_title, source_ref=args.source_ref, rights=args.rights,
                    gpx=args.gpx, marks=args.mark, view_from=args.view_from,
                    emphasis=not args.plain and not args.into, real_scale=bool(args.into))
            except (terrain_mod.TerrainError, OSError, ValueError) as exc:
                sys.stderr.write("terrain: %s\n" % exc)
                return 1
            if args.into:
                if not (args.center and args.extent):
                    sys.stderr.write("terrain: --into needs --center and --extent (the building stands at the centre)\n")
                    return 1
                host, _ = diagnose_mod.parse_text(Path(args.into).read_text(encoding="utf-8"))
                if not isinstance(host, dict) or "parts" not in host:
                    sys.stderr.write("terrain: %s is not a scene\n" % args.into)
                    return 1
                merged = terrain_mod.plinth(host, sc)
                Path(args.into).write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
                sys.stdout.write("put the measured terrain under %s as its plinth (real scale)\n" % args.into)
                return 0
            if not args.output:
                sys.stderr.write("terrain: give --output (or --into)\n")
                return 1
            _write(args.output, json.dumps(sc, indent=1, ensure_ascii=False) + "\n", args.force)
            sys.stdout.write("wrote %s: %s\n" % (args.output, sc["subject"]["summary"]))
            return 0
        if args.command == "rounds":
            return _rounds(args)
        if args.command == "compare":
            from . import compare as compare_mod
            from . import trace as trace_mod
            doc, diags = diagnose_mod.parse_text(Path(args.scene).read_text(encoding="utf-8"))
            tdoc, tdiags = diagnose_mod.parse_text(Path(args.trace).read_text(encoding="utf-8"))
            if doc is None or tdoc is None:
                sys.stderr.write("compare: cannot read %s\n" % (args.scene if doc is None else args.trace))
                return 1
            try:
                result, picture = compare_mod.compare(doc, tdoc, args.view, args.fit)
            except (compare_mod.CompareError, trace_mod.TraceError, scene_mod.SceneError) as exc:
                sys.stderr.write("compare: %s\n" % exc)
                return 1
            if args.overlay:
                Path(args.overlay).write_bytes(picture)
            sys.stdout.write("%s view against %s: IoU %.3f (needs %.2f), outlines %.2f%% apart (of the view's %s; "
                             "needs <= %.1f%%)%s: %s\n" % (
                                 args.view, result["reference"], result["iou"], result["threshold"]["iou"],
                                 100 * result["edge"], args.fit, 100 * result["threshold"]["edge"],
                                 ", reference %s" % result["orientation"] if result["mirrored"] else "",
                                 "PASS" if result["pass"] else "not yet"))
            for w in result["warnings"]:
                sys.stdout.write("warning: %s\n" % w)
            if args.record:
                new = compare_mod.record(doc, result, tdoc)
                Path(args.scene).write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                sys.stdout.write("recorded in %s\n" % args.scene)
            return 0 if result["pass"] else 2
        if args.command == "loft-from-traces":
            from . import trace as trace_mod
            docs = {}
            for k in ("side", "top", "front"):
                path = getattr(args, k)
                if path:
                    docs[k], _ = diagnose_mod.parse_text(Path(path).read_text(encoding="utf-8"))
                    if docs[k] is None:
                        sys.stderr.write("loft-from-traces: cannot read %s\n" % path)
                        return 1
            try:
                res = trace_mod.stations(docs["side"], docs["top"], args.length, docs.get("front"), args.height,
                                         args.width, args.stations, args.nose_side, args.nose_top, args.sill)
            except trace_mod.TraceError as exc:
                sys.stderr.write("loft-from-traces: %s\n" % exc)
                return 1
            if args.out:
                _write(args.out, json.dumps(res, indent=1) + "\n", True)
            if args.into:
                sc, _ = diagnose_mod.parse_text(Path(args.into).read_text(encoding="utf-8"))
                part = next((p for p in (sc or {}).get("parts", []) if p.get("id") == args.part), None)
                if part is None:
                    sys.stderr.write("loft-from-traces: %s has no part %r\n" % (args.into, args.part))
                    return 1
                sc["parts"] = [p for p in sc["parts"] if p.get("id") not in set(args.drop)]
                for idf in (sc.get("authoring") or {}).get("identity", []):
                    idf["parts"] = [x for x in idf.get("parts", []) if x not in set(args.drop)]
                part["shape"] = res["loft"]
                part["at"] = [0, 0, 0]
                part.pop("rotate", None)
                part.update({k: v for k, v in res["part"].items()})
                have = {s_.get("id") for s_ in sc.get("sources", [])}
                sc.setdefault("sources", []).extend(src for src in res["sources"] if src["id"] not in have)
                Path(args.into).write_text(json.dumps(sc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            c = res["checks"]
            sys.stdout.write("%d stations; traced %.3f x %.3f x %.3f m (w x h x l)%s%s\n" % (
                len(res["loft"]["sections"]), res["size_m"][0], res["size_m"][1], res["size_m"][2],
                "; height %.0f%% of the documented" % (100 * c["height_ratio"]) if "height_ratio" in c else "",
                "; width %.0f%% of the documented" % (100 * c["width_ratio"]) if "width_ratio" in c else ""))
            return 0
        if args.command == "critique":
            from . import critic as critic_mod
            return _critique(args, critic_mod)
        if args.command == "globe":
            from . import globe as globe_mod
            try:
                sc = globe_mod.build(args.coastlines, title=args.title, source_title=args.source_title,
                                     source_ref=args.source_ref, rights=args.rights, graticule=args.graticule,
                                     tilt=not args.no_tilt, rpm=args.rpm)
            except globe_mod.GlobeError as exc:
                sys.stderr.write("globe: %s\n" % exc)
                return 1
            _write(args.output, json.dumps(sc, indent=1, ensure_ascii=False) + "\n", args.force)
            sys.stdout.write("wrote %s: %s\n" % (args.output, sc["subject"]["summary"]))
            return 0
        if args.command == "trace":
            from . import trace as trace_mod
            doc, diags = diagnose_mod.parse_text(Path(args.trace).read_text(encoding="utf-8"))
            if doc is None:
                sys.stderr.write("trace: %s\n" % "; ".join(d["message"] for d in diags))
                return 1
            try:
                result = trace_mod.fit(doc, args.fit, args.origin, args.points)
            except trace_mod.TraceError as exc:
                sys.stderr.write("trace: %s\n" % exc)
                return 1
            text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
            if args.out:
                _write(args.out, text, True)
                sys.stdout.write("wrote %s: %d points, %.3f x %.3f m\n" % (args.out, len(result["profile"]), *result["size_m"]))
            else:
                sys.stdout.write(text)
            return 0
        if args.command == "trace-image":
            try:
                from . import runner
            except ImportError:
                sys.stderr.write("trace-image: not part of this package; use the full checkout (%s)\n" % product_mod.REPO)
                return 2
            try:
                return runner.run_trace_image(args, sys.stdout)
            except (runner.RunnerError, OSError) as exc:
                sys.stderr.write("trace-image: %s\n" % exc)
                return 2
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
            peek, _ = diagnose_mod.parse_text(text)
            other = {"construct-trace": "a trace: use it with construct trace, compare or loft-from-traces",
                     "construct-critique": "a critique: record it with construct critique",
                     "construct-rounds": "a rounds state: see it with construct rounds status"}.get(
                         (peek or {}).get("format") if isinstance(peek, dict) else None)
            if other:
                sys.stderr.write("check: %s is not a scene, it is %s\n" % (args.scene, other))
                return 1
            report = diagnose_mod.diagnose_text(text)
            if getattr(args, "fit", False) and report.get("stats") is not None:
                from . import fit as fit_mod
                fitted = fit_mod.check(diagnose_mod.parse_text(text)[0] if not params_mod.is_params(
                    diagnose_mod.parse_text(text)[0]) else params_mod.expand(diagnose_mod.parse_text(text)[0]),
                    cells=max(40, min(600, args.cells)))
                for issue in fitted["issues"]:   # as every diagnostic: a code, a message and a hint
                    issue["hint"] = diagnose_mod.FIT_HINTS.get(issue["code"])
                report["fit"] = fitted
            if args.json:
                sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            elif report["stats"] is not None:  # it compiled: the audit report, then anything left to fix
                scene, _ = diagnose_mod.parse_text(text)
                if params_mod.is_params(scene):
                    scene = params_mod.expand(scene)
                sys.stdout.write(audit_mod.format_report(audit_mod.audit(scene, scene_mod.compile_scene(scene))) + "\n")
                if not report["ok"]:
                    sys.stdout.write("\nhow to fix:\n" + report["repair_text"] + "\n")
                if report.get("fit") is not None:
                    sys.stdout.write("\n" + fit_mod.report(report["fit"]) + "\n")
            else:
                n = report["errors"]
                sys.stdout.write("invalid scene (%d problem%s)\n%s\n" % (n, "" if n == 1 else "s", report["repair_text"]))
            return 0 if report["ok"] else 1
        if args.command == "build":
            _, report, text = build(args.scene, args.out, args.asset_root, args.v1, frame=args.frame,
                                    palette=args.palette, identity=args.identity, film=args.film)
            sys.stdout.write(text + "\nwrote %s\n" % Path(args.out, "construct.html"))
            return 0 if report["ok"] else 1
        if args.command == "review":
            _, report, text = build(args.scene, args.out, args.asset_root, palette=args.palette, identity=args.identity)
            sys.stdout.write(text + "\n")
            w, h = (int(x) for x in args.size.lower().split("x"))
            sheets = [s for s in args.sheets.split(",") if s]
            paths = render.review(page_in(args.out), str(Path(args.out, "review")), w, h, sheets=sheets)
            sys.stdout.write("captured:\n  %s\n" % "\n  ".join(paths))
            return 0 if report["ok"] else 1
        if args.command == "netlogo-compare":
            from . import netlogo as nl
            labels = [x.strip() for x in args.labels.split(",")] if args.labels else None
            try:
                sc = nl.compare([nl.read_run(r) for r in args.runs], args.view, labels, args.title, state=args.state)
            except nl.NetLogoError as exc:
                sys.stderr.write("netlogo-compare: %s\n" % exc)
                return 1
            _write(args.out, json.dumps(sc, separators=(",", ":"), ensure_ascii=False) + "\n", args.force)
            sys.stdout.write("wrote %s: %d runs side by side; build it as any scene\n" % (args.out, len(args.runs)))
            return 0
        if args.command == "netlogo-plates":
            from . import netlogo as netlogo_mod, plates
            try:
                at = [int(x) for x in args.at.split(",")] if args.at else None
            except ValueError:
                sys.stderr.write("netlogo-plates: --at takes ticks, e.g. 0,20,68,300\n")
                return 1
            try:
                run = netlogo_mod.read_run(args.run)
                r = plates.write(run, args.out, args.format, recording=args.run, count=args.plates, at=at,
                                 size=args.size, title=args.title, state=args.state, tall=args.tall == "true")
            except (plates.PlatesError, netlogo_mod.NetLogoError, OSError) as exc:
                sys.stderr.write("netlogo-plates: %s\n" % exc)
                return 1
            sys.stdout.write("wrote %d plates (ticks %s), 2 pins, sleeves and KEY.md to %s: %s x %s mm plates, a "
                             "stack %s mm tall%s\n" % (len(r["plates"]), ", ".join(str(p["tick"]) for p in r["plates"]),
                                                       args.out, r["size_mm"][0], r["size_mm"][1], r["stack_mm"],
                                                       "; tall dots: %s %s" % (r["state"], args.tall) if r["state"] else ""))
            return 0 if r["watertight"] else 1
        if args.command == "netlogo-film":
            from . import runfilm
            if not (args.out or args.blend):
                sys.stderr.write("netlogo-film: --out film.mp4, --blend film.blend, or both\n")
                return 1
            try:   # read it here first: a bad recording is refused without starting Blender
                runfilm.parse(args.run)
            except (ValueError, KeyError, TypeError) as exc:
                sys.stderr.write("netlogo-film: %s\n" % exc)
                return 1
            blender = runfilm.find_blender(args.blender)
            if not blender:
                sys.stderr.write("netlogo-film: Blender was not found; install it (blender.org) or pass --blender PATH "
                                 "(or set CONSTRUCT_BLENDER)\n")
                return 1
            job = {"root": str(Path(__file__).resolve().parent.parent), "run": str(Path(args.run).resolve()),
                   "out": args.out and str(Path(args.out).resolve()), "blend": args.blend and str(Path(args.blend).resolve()),
                   "size": args.size, "start": args.start, "seconds": args.seconds, "samples": args.samples,
                   "trail": args.trail}
            code = ("import sys, json; a = json.loads(sys.argv[sys.argv.index('--') + 1]); sys.path.insert(0, a.pop('root'))\n"
                    "from construct_hologram import runfilm\n"
                    "f = runfilm.render(**a); print('CONSTRUCT-FILM %d %d' % f)\n")
            r = subprocess.run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python-expr", code, "--",
                                json.dumps(job)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            done = next((ln for ln in r.stdout.splitlines() if ln.startswith("CONSTRUCT-FILM ")), None)
            if r.returncode or not done:
                tail = (r.stderr or r.stdout).strip().splitlines()[-6:]
                sys.stderr.write("netlogo-film: Blender failed:\n%s\n" % "\n".join(tail))
                return 1
            first, last = (int(x) for x in done.split()[1:])
            for path, what in ((args.blend, "the film's scene: open it in Blender with the Construct add-on and press play"),
                               (args.out, "the film")):
                if path:
                    sys.stdout.write("wrote %s: %s (frames %d to %d)\n" % (path, what, first, last))
            return 0
        if args.command in ("netlogo", "netlogo-instrument"):
            from . import netlogo as nl
            try:
                if args.command == "netlogo-instrument":
                    src = Path(args.model)
                    patches = None
                    if args.patches:
                        rep_, _, every = args.patches.rpartition(":")
                        patches = (rep_, int(every)) if rep_ and every.isdigit() else (args.patches, 1)
                    model, xml = nl.instrument(src.read_text(encoding="utf-8"), args.title, args.run_file,
                                               [t.strip() for t in args.turtles.split(",") if t.strip()],
                                               [r.strip() for r in args.reporters.split(";") if r.strip()],
                                               patches, args.every, args.seed, args.ticks, args.no_turtles,
                                               args.setup, args.go)
                    out = Path(args.out)
                    out.mkdir(parents=True, exist_ok=True)
                    target = out / (src.stem + "-construct.nlogox")
                    target.write_text(model, encoding="utf-8")
                    shutil.copyfile(nl.NLS, out / "construct.nls")
                    (out / "construct-experiment.xml").write_text(xml, encoding="utf-8")
                    run_with = [html.unescape(re.search(r"<%s>(.*?)</%s>" % (k, k), xml, re.S).group(1)) for k in ("setup", "go")]
                    run_with = ["; ".join(ln.strip() for ln in c.splitlines()
                                          if ln.strip() and not ln.strip().startswith(("construct-", "random-seed")))
                                for c in run_with]
                    sys.stdout.write("wrote %s, construct.nls and construct-experiment.xml in %s\n"
                                     "Run it in NetLogo (setup: %s; go: %s), or headless:\n"
                                     "  NetLogo_Console --headless --model \"%s\" --setup-file \"%s\" "
                                     "--experiment construct --threads 1\n"
                                     "then: construct netlogo %s --view VIEW --out scene.json\n"
                                     "  (VIEW: space-time for moving agents, network-time --state VAR for spreading "
                                     "on a network,\n   phase for two reporters in a cycle, field for patches; "
                                     "docs/NETLOGO.md)\n"
                                     % (target.name, out, run_with[0], run_with[1], target, out / "construct-experiment.xml",
                                        out / args.run_file))
                    return 0
                if args.view == "auto":
                    run_auto = nl.read_run(args.run)
                    picked, _, why = nl.choose_view(run_auto)
                    if picked == "field":
                        try:
                            nl.scene_from_run(run_auto, "field")
                        except nl.NetLogoError:
                            picked, _, why = nl.choose_view(run_auto, exclude=("field",))
                            why += "; the patches changed all at once"
                    sys.stdout.write("view: %s (%s)\n" % (picked, why))
                scene = nl.scene_from_run(nl.read_run(args.run), args.view, args.title, state=args.state, x=args.x,
                                          z=args.z, change=args.change, max_agents=args.max_agents,
                                          time=args.time, smooth=args.smooth, levels=args.levels,
                                          resolution=args.resolution, solid=args.solid, window=args.window,
                                          landmarks=args.landmarks, colors=args.colors)
                win = next((f for f in scene["facts"] if f["key"] == "window"), None)
                if win:
                    sys.stdout.write("window: %s (%s)\n" % (win["value"], win["note"].split(":")[0].lower()))
                run_data = nl.read_run(args.run)
                if args.art:
                    scene = nl.apply_art(scene, json.loads(Path(args.art).read_text(encoding="utf-8")))
            except (nl.NetLogoError, json.JSONDecodeError) as exc:
                sys.stderr.write("netlogo: %s\n" % exc)
                return 1
            text = json.dumps(scene, separators=(",", ":"), ensure_ascii=False) + "\n"   # data: compact
            _write(args.out, text, args.force)
            if args.csv:
                _write(args.csv, nl.counts_csv(run_data), args.force)
            if args.materials_out or args.glb:
                mats = nl.materials_from_run(run_data, scene)
                if args.materials_out:
                    _write(args.materials_out, json.dumps(mats, indent=1) + "\n", args.force)
                if args.glb:
                    from . import export as export_mod
                    export_mod.export(scene, args.glb, wire="tubes", materials=mats)
                    sys.stdout.write("wrote %s: the 3D model (tubes, solids, the run's colours)\n" % args.glb)
            g = scene_mod.compile_scene(scene)
            sys.stdout.write("wrote %s: %s, %d parts, %d lines, %d triangles\n"
                             % (args.out, args.view, len(scene["parts"]), g["counts"]["lines"], g["counts"]["triangles"]))
            return 0
        if args.command == "export":
            from . import export as export_mod
            try:
                s = export_mod.export(load(args.scene), args.out, args.format, args.wire, args.pose, args.materials,
                                      args.frame, args.wire_radius, args.merge, args.colliders,
                                      {None: False, "loose": True}.get(args.pieces, args.pieces), args.quality)
            except export_mod.ExportError as exc:
                sys.stderr.write("export: %s\n" % exc)
                return 1
            anims = ", ".join(s.get("animations", [])) or "none"
            sys.stdout.write("wrote %s: %d parts, %d triangles, %d edges%s\n"
                             % (", ".join(s["files"]), s["parts"], s["triangles"], s["edges"],
                                "; animations: " + anims if s["format"] == "glb" else ""))
            q = s["quality"]
            if q["triangles"]:
                sys.stdout.write("  triangles: %.0f%% thin (an angle under 10 degrees), %.0f%% fair (under 20)%s\n" % (
                    100 * q["thin_share"], 100 * q["fair_share"], "" if args.quality else "; --quality shows where"))
            if s.get("quads"):
                sys.stdout.write("  %d quads, positions shared: ready to subdivide\n" % s["quads"])
            return 0
        if args.command == "print":
            from . import printing
            pr = printing.PRINTERS.get(args.printer or "desktop")
            try:
                bed = tuple(float(x) for x in args.bed.lower().split("x")) if args.bed else pr["bed"]
                if len(bed) != 3:
                    raise ValueError
            except ValueError:
                sys.stderr.write("print: --bed WxDxH in mm, e.g. 250x210x220\n")
                return 1
            if args.printers:
                try:
                    rows = printing.printers(load(args.scene), lines=args.lines, wall=args.wall)
                except printing.PrintError as exc:
                    sys.stderr.write("print: %s\n" % exc)
                    return 1
                sys.stdout.write("the largest print on each printer class (parts: kept / thickened / lost, an estimate "
                                 "from each part's size)\n")
                for r in rows:
                    sys.stdout.write("  %-8s %-7s %s mm, voxel %g mm%s; real features under ~%g mm lost; parts %d / %d / %d"
                                     "  (%s)\n" % (r["printer"], r["scale"], " x ".join("%g" % x for x in r["size_mm"]),
                                                   r["detail_mm"], " (the grid's limit)" if r["limited_by_grid"] else "",
                                                   r["smallest_real_mm"], r["kept"], r["thickened"], r["lost"], r["label"]))
                return 0
            if not args.out:
                sys.stderr.write("print: --out FILE.stl or FILE.3mf (or --printers to compare printers)\n")
                return 1
            try:
                r = printing.write(load(args.scene), args.out, args.format,
                                   size=printing.SIZE_MM if args.size is None else args.size, scale=args.scale, fit=args.fit,
                                   detail=args.detail if args.detail is not None else
                                   (pr["detail"] if args.printer else printing.DETAIL_MM),
                                   wall=args.wall if args.wall is not None else
                                   (pr["wall"] if args.printer else printing.WALL_MM), join=args.join,
                                   lines=args.lines, bed=bed, coarsen=bool(args.printer or args.fit), exact=args.exact)
            except printing.PrintError as exc:
                sys.stderr.write("print: %s\n" % exc)
                return 1
            sys.stdout.write("wrote %s: %s mm at %s, %d triangles\n" % (
                r["files"][0], " x ".join("%g" % x for x in r["size_mm"]), r["scale"], r["triangles"]))
            for line in printing.notes(r):
                sys.stdout.write("  %s\n" % line)
            return 0 if r["watertight"] else 1
        if args.command == "kit":
            from . import kit as kit_mod
            if args.critic:
                sys.stdout.write(kit_mod.CRITIC + "\n")
                return 0
            try:
                bed = tuple(float(x) for x in args.bed.lower().split("x")) if args.bed else \
                    __import__("construct_hologram.printing", fromlist=["PRINTERS"]).PRINTERS[args.printer or "desktop"]["bed"]
                mats = args.materials or (str(Path(args.scene).with_suffix(".materials.json"))
                                          if Path(args.scene).with_suffix(".materials.json").is_file() else None)
                progress = lambda m: sys.stderr.write(m + "\n")   # a building's kit takes many minutes: say where it is
                k = kit_mod.make(load(args.scene), scale=args.scale, size=args.size, detail=args.detail, plan=args.plan,
                                 materials=mats, bed=bed, log=progress)
                kit_mod.write(k, args.out, only=args.only, log=progress)
            except (kit_mod.KitError, export_errors(), ValueError) as exc:
                sys.stderr.write("kit: %s\n" % exc)
                return 1
            c = k["report"]["counts"]
            sys.stdout.write("wrote %s: %s on %s, %s, at %s (%s mm)\n" % (
                args.out, kit_mod.counted(c["pieces"], "piece"), kit_mod.counted(c["plates"], "plate"),
                kit_mod.counted(c["steps"], "step"), k["scale"], " x ".join("%g" % x for x in k["size_mm"])))
            for prob in k["report"]["problems"]:
                sys.stdout.write("  %s\n" % prob["message"])
            return 0 if k["report"]["ok"] else 1
        if args.command == "freecad":
            from . import freecad
            out = Path(args.out)
            is_step = out.suffix.lower() in (".step", ".stp")
            if not is_step and out.suffix.lower() != ".fcstd":
                sys.stderr.write("freecad: --out FILE.FCStd or FILE.step\n")
                return 1
            try:
                r = freecad.make(load(args.scene), fcstd=None if is_step else out, step=out if is_step else args.step,
                                 freecad=args.freecad, exact=not args.facets)
            except freecad.FreeCADError as exc:
                sys.stderr.write("freecad: %s\n" % exc)
                return 1
            sys.stdout.write("wrote %s: %d named parts, %d joint%s\n" % (", ".join(r["files"]), r["parts"], r["joints"],
                                                                         "" if r["joints"] == 1 else "s"))
            if r.get("exact"):
                sys.stdout.write("  true shapes (exact solids, splines, NURBS): %d of %d parts\n" % (len(r["exact"]), r["parts"]))
            if r.get("faceted"):
                sys.stdout.write("  faceted, the true shape did not match the construct: %s\n" % printing_list(r["faceted"]))
            if r["surfaces"]:
                sys.stdout.write("  surfaces, not solids (open in the construct): %s\n" % printing_list(r["surfaces"]))
            if r["left_out"]:
                sys.stdout.write("  drawn only in lines, left out: %s\n" % printing_list(r["left_out"]))
            if r["invalid"]:
                sys.stdout.write("  FreeCAD found these shapes invalid: %s\n" % printing_list(r["invalid"]))
            return 0 if not r["invalid"] else 1
        if args.command == "audio":
            from . import film_audio
            try:
                n = film_audio.features(args.music, args.voice, args.fps, args.out, args.scale)
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                sys.stderr.write("audio: %s\n" % (exc if isinstance(exc, FileNotFoundError) else
                                                   "ffmpeg could not read %s" % args.music))
                return 1
            sys.stdout.write("wrote %s (%d frames at %d fps)\n" % (args.out, n, args.fps))
            return 0
        if args.command == "video":
            out = Path(args.out)
            seconds = args.seconds if args.seconds is not None else (args.assembly + 3.0 if args.assembly else 12.0)
            # film mode is embedded only when a film option asks for it; otherwise the stock page
            film = bool(args.audio or args.assembly or args.camera == "steady" or args.reactivity is not None)
            with tempfile.TemporaryDirectory(prefix="hologram-video-") as tmp:
                build(args.scene, tmp, args.asset_root, palette=args.palette, identity=args.identity, film=film)
                w, h = (int(x) for x in args.size.lower().split("x"))
                extra = {}
                if args.audio:  # the features travel beside the page, which fetches them
                    shutil.copyfile(args.audio, Path(tmp, "audio.json"))
                    extra["audio"] = "audio.json"
                if args.assembly:
                    extra["assembly"] = "%.3f" % args.assembly
                if args.camera != "tour":
                    extra["camera"] = args.camera
                if args.reactivity is not None:
                    extra["reactivity"] = "%g" % args.reactivity
                render.frames(page_in(tmp), str(Path(tmp, "frames")), seconds, args.fps,
                              args.start, w, h, view=args.view, extra=extra)
                out.parent.mkdir(parents=True, exist_ok=True)
                render.encode_video(str(Path(tmp, "frames")), str(out), args.fps, sound=args.sound,
                                    sound_start=args.start)
            sys.stdout.write("wrote %s\n" % out)
            return 0
    except scene_mod.SceneError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except render.CaptureError as exc:
        sys.stderr.write("capture unavailable: %s\n" % exc)
        return 2
    return 1
