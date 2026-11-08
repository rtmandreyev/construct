"""Construct's side of the plugin: run in a child process, never imported by Hermes.

    python -I -B child.py <vendor folder> <op> [args...]

The vendor folder (the one holding `construct_hologram`) goes first on the path; with -I nothing else
from the user's site or the current folder is imported. Ops:

    programs                  which outside programs Construct finds (JSON)
    cli <argv...>             Construct's own command line
    parse <argv.json>         how Construct's own parser reads a command line, without running it (JSON)
    build <spec.json>         `build`, then a small still for the gallery when a browser is there
    inspect <scene>           what the scene's own record says is known (JSON)
    edit <spec.json>          apply construct_edit's operations, validating each; the result beside, as a candidate
    world <spec.json>         check a world: its errors, or its placements, audit and surfaces (JSON)
    version                   Construct's version
    netlogo-run|netlogo-draw <spec.json>   NetLogo runs and recordings drawn (netlogo_child.py)
    film <spec.json>          a film: build, frames, encode (the frames are counted for progress)
    job <dir> <op> [args...]  run an op as a background job: exit.json records how it ended
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

LENGTH_UNITS = ("m", "mm", "cm", "km", "in", "ft")
CAP = {"facts": 40, "sources": 24, "group": 8, "articulations": 16, "next": 5, "identity": 8}


def _cli(argv):
    from construct_hologram.__main__ import main
    try:
        return main(argv) or 0
    except SystemExit as exc:   # argparse refusing an argument
        return exc.code if isinstance(exc.code, int) else 2


def programs():
    from construct_hologram import film_audio, freecad, render, runfilm
    try:
        ffmpeg = film_audio.find_ffmpeg()
    except FileNotFoundError:
        ffmpeg = None
    return {"browser": render.find_browser(), "ffmpeg": ffmpeg, "freecad": freecad.find_freecad(),
            "blender": runfilm.find_blender()}


def build(spec):
    argv = ["build", spec["scene"], "--out", spec["out"]]
    for k in ("palette", "identity"):
        if spec.get(k):
            argv += ["--" + k, spec[k]]
    if spec.get("asset_root"):
        argv += ["--asset-root", spec["asset_root"]]
    code = _cli(argv)
    page = Path(spec["out"], "construct.html")
    if spec.get("thumb") and page.is_file():
        from construct_hologram import render
        if render.find_browser():
            try:
                shot = render.stills(str(page), spec["out"], ["hero"], 480, 300)
                if shot:
                    os.replace(shot[0], Path(spec["out"], "thumb.png"))
            except Exception as exc:   # a still for the gallery is a nicety: the build stands without it
                sys.stderr.write("thumbnail: %s\n" % exc)
    return code


def thumb(spec):
    """A still for a page built without one (the Constructs page's tiles): thumb.png beside it."""
    from construct_hologram import render
    page = Path(spec["page"])
    if not page.is_file() or not render.find_browser():
        return 1
    shot = render.stills(str(page), str(page.parent), ["hero"], 480, 300)
    if not shot:
        return 1
    os.replace(shot[0], page.parent / "thumb.png")
    return 0


def _short(text, n=160):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def _capped(items, n):
    return {"items": items[:n], "more": len(items) - n} if len(items) > n else {"items": items}


ROLE_ORDER = ("identity", "mass", "structure", "artwork", "data", "detail", "ornament", "ground")
GROUPS = ("verified", "size_verified", "shape_verified", "supplied", "traced", "inferred", "designed", "decorative")
LEVELS = {2: "described", 3: "seen", 4: "seen and checked"}


AXES = (("width", "x"), ("height", "y"), ("length", "z"))


def _union(boxes):
    lo = [min(b[0][a] for b in boxes) for a in range(3)]
    hi = [max(b[1][a] for b in boxes) for a in range(3)]
    return lo, hi


def _dims(lo, hi, unit):
    k = 1000.0 if unit == "mm" else 1.0
    return {name: round((hi[a] - lo[a]) * k, 1 if unit == "mm" else 3) for a, (name, _) in enumerate(AXES)}


def envelope(doc):
    """The construct's size two ways: over everything (the overall bounds), and over its main mass alone (the body,
    without what sticks out of it: mirrors, handles, aerials, a chimney), with the parts that stand out beyond the
    body and by how much. The body is the parts the scene calls `mass`; without enough of them, the largest parts."""
    from construct_hologram import scene as scene_mod
    g = scene_mod.compile_scene(doc)
    boxes = []   # (min, max, part id, role, volume)
    for part in g["parts"]:
        if part.get("role") == "ground":
            continue
        for ins in part.get("instances", []):
            lo, hi = ins["min"], ins["max"]
            vol = max(0.0, (hi[0] - lo[0])) * max(0.0, (hi[1] - lo[1])) * max(0.0, (hi[2] - lo[2]))
            boxes.append((lo, hi, part["id"], part.get("role"), vol))
    if not boxes:
        return None
    lo, hi = _union(boxes)
    span = [hi[a] - lo[a] for a in range(3)]
    longest = max(span) or 1.0
    unit = "mm" if longest < 1.0 else "m"
    body = [b for b in boxes if b[3] == "mass"]
    how = "the parts whose role is mass"
    if body:
        blo, bhi = _union(body)
        if max(bhi[a] - blo[a] for a in range(3)) < 0.5 * longest:   # the mass parts are a small piece of it
            body = []
    if not body:   # the largest parts: each at least a twentieth of the biggest one's volume
        big = max(b[4] for b in boxes)
        body = [b for b in boxes if big and b[4] >= 0.05 * big]
        how = "the largest parts (each at least a twentieth of the biggest one's volume)"
    blo, bhi = _union(body)
    k = 1000.0 if unit == "mm" else 1.0
    beyond = {name: {} for name, _ in AXES}   # axis -> part -> (how far, which side)
    for b in boxes:
        for a, (name, axis) in enumerate(AXES):
            for side, out in (("-" + axis, blo[a] - b[0][a]), ("+" + axis, b[1][a] - bhi[a])):
                if out > max(0.01 * span[a], 0.001 * longest) and out > beyond[name].get(b[2], (0, None))[0]:
                    beyond[name][b[2]] = (out, side)
    stands_out = {}
    for name, rows in beyond.items():
        if rows:
            stands_out[name] = [{"part": pid, "side": side, "by": round(out * k, 1 if unit == "mm" else 3)}
                                for pid, (out, side) in sorted(rows.items(), key=lambda kv: -kv[1][0])[:4]]
    overall, main = _dims(lo, hi, unit), _dims(blo, bhi, unit)
    n = len({b[2] for b in body})
    out = {"unit": unit, "axes": "width x (left-right), height y (up), length z (the front faces +z)",
           "overall": overall, "body": main, "body_is": "%s: %d part%s" % (how, n, "" if n == 1 else "s"),
           "stands_out": stands_out}
    words = {"width": "wide", "height": "tall", "length": "long"}
    say = ["%s %g %s %s (%g %s overall, with %s)" % ("the body is" if not i else "", main[name], unit, words[name],
                                                    overall[name], unit, ", ".join(r["part"] for r in stands_out[name][:2]))
           for i, name in enumerate(n for n, _ in AXES if n in stands_out)]
    if say:
        out["say"] = "; ".join(x.strip() for x in say) + ". Quote the body for its size, the overall for what it needs room for."
    open_lo, open_hi = g["bounds"].get("open_min"), g["bounds"].get("open_max")
    if open_lo and open_hi and (open_lo != g["bounds"]["min"] or open_hi != g["bounds"]["max"]):
        out["overall_open"] = _dims(open_lo, open_hi, unit)
    return out


def inspect(path):
    """The construct's own record of what is known: parts by certainty, facts, sources, joints, authoring."""
    from construct_hologram import params, scene as scene_mod, studio, tiers
    doc = studio.load(path)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = doc.get("sources", [])
    facts = doc.get("facts", [])
    parts = doc.get("parts", [])
    source_kind = {s.get("id"): s.get("kind") for s in sources}
    fact_cert = {f.get("key"): f.get("certainty") for f in facts}
    authoring = doc.get("authoring", {}) or {}
    try:
        current = tiers.critic_hash(doc)
    except Exception:
        current = None
    checked = {c.get("reference") for c in authoring.get("compare", []) if c.get("pass") and c.get("scene_sha256") == current}

    groups = {}
    for p in sorted(parts, key=lambda p: ROLE_ORDER.index(p.get("role")) if p.get("role") in ROLE_ORDER else 99):
        cls = scene_mod.provenance_class(p)
        level = None
        if cls == "inferred":
            level = scene_mod.evidence_level(p, source_kind, fact_cert, checked)
            cls = "designed" if level == 1 else "inferred"
        cls = {"user_supplied": "supplied"}.get(cls, cls)
        g = groups.setdefault(cls, {"count": 0, "parts": [], "evidence": {}})
        g["count"] += 1
        g["parts"].append(p.get("label") or p.get("id"))
        if level in LEVELS:
            g["evidence"][LEVELS[level]] = g["evidence"].get(LEVELS[level], 0) + 1
        copies = 1
        if p.get("mirror"):
            copies *= 2
        if isinstance(p.get("repeat"), dict):
            copies *= int(p["repeat"].get("count", 1) or 1)
        g["copies"] = g.get("copies", 0) + copies
    by_certainty = {}
    for name in GROUPS:
        if name in groups:
            g = groups[name]
            entry = {"count": g["count"], "key_parts": g["parts"][:CAP["group"]]}
            if g["count"] > CAP["group"]:
                entry["more"] = g["count"] - CAP["group"]
            if g["copies"] != g["count"]:
                entry["with_copies"] = g["copies"]
            if g["evidence"]:
                entry["evidence"] = g["evidence"]
            by_certainty[name] = entry

    def fact_row(f):
        row = {"key": f.get("key"), "value": f.get("value") if not isinstance(f.get("value"), str) else _short(f.get("value"), 120),
               "certainty": f.get("certainty")}
        for k in ("unit", "source"):
            if f.get(k) is not None:
                row[k] = f[k]
        return row
    dims = {}
    for f in facts:
        if f.get("unit") in LENGTH_UNITS and isinstance(f.get("value"), (int, float)) and not isinstance(f.get("value"), bool):
            kind = {"user_supplied": "supplied"}.get(f.get("certainty"), f.get("certainty"))
            dims.setdefault(kind, []).append("%s %g %s" % (f.get("key"), f["value"], f["unit"]))

    joints = []
    for a in doc.get("articulations", []):
        unit = "deg" if a.get("type") in ("hinge", "turn") else "m"
        row = {"id": a.get("id"), "type": a.get("type"), "travel": "%g %s" % (a.get("amount", 0), unit),
               "parts": len(a.get("parts", []))}
        if a.get("note"):
            row["note"] = _short(a["note"], 120)
        joints.append(row)

    out = {
        "title": doc.get("title"),
        "kind": "parameter document (archetype %s)" % raw.get("archetype") if params.is_params(raw) else "scene",
        "subject": {k: (_short(v, 240) if isinstance(v, str) else v) for k, v in (doc.get("subject") or {}).items()},
        "parts": {"count": len(parts), "by_certainty": by_certainty},
        "dimensions": dims,
        "facts": _capped([fact_row(f) for f in facts], CAP["facts"]),
        "sources": _capped([dict({k: (_short(s[k], 200) if isinstance(s.get(k), str) else s.get(k))
                                  for k in ("id", "kind", "title", "rights") if k in s},
                                 **({"ref": _short(s["ref"], 200)} if s.get("ref") else {})) for s in sources], CAP["sources"]),
        "articulations": _capped(joints, CAP["articulations"]),
    }
    try:
        env = envelope(doc)
    except Exception as exc:   # a scene that does not compile yet: the record without its sizes
        env = {"error": "no sizes until it compiles: %s" % _short(exc, 200)}
    if env:
        out["size"] = env
    assets = doc.get("assets", [])
    if assets:
        out["artwork"] = [{"id": a.get("id"), "provenance": a.get("provenance"), "rights": a.get("rights")} for a in assets]
    if authoring:
        a = {k: authoring[k] for k in ("tier", "research", "outcome", "review_rounds") if k in authoring}
        if authoring.get("identity"):
            a["identity"] = [_short(i.get("feature", ""), 120) for i in authoring["identity"][:CAP["identity"]]]
        if authoring.get("next"):
            a["next"] = [_short(n, 160) for n in authoring["next"][:CAP["next"]]]
        if authoring.get("critic"):
            c = authoring["critic"]
            a["critic"] = {k: c[k] for k in ("verdict", "scores", "round", "defects") if k in c}
            a["critic"]["current"] = c.get("scene_sha256") == current
        rs = authoring.get("rounds") or []
        if rs:
            kept = [r for r in rs if r.get("result") != "reverted"]
            a["rounds"] = {"count": len(rs), "best": kept[-1].get("round") if kept else None,
                           "kept": sum(1 for r in rs if r.get("result") == "kept"),
                           "reverted": sum(1 for r in rs if r.get("result") == "reverted"),
                           "minutes": round(sum(r.get("minutes") or 0 for r in rs), 1),
                           "last": _short(rs[-1].get("summary", ""), 200)}
        if authoring.get("compare"):
            a["compare"] = [{"view": c.get("view"), "reference": c.get("reference"), "iou": c.get("iou"), "pass": c.get("pass"),
                             "current": c.get("scene_sha256") == current} for c in authoring["compare"]]
        out["authoring"] = a
    return out


def film(spec):
    """A film of the construct, as `construct video` makes it, with its frames where progress can count them."""
    from construct_hologram import film_audio, render, studio
    work = Path(spec["work"])
    work.mkdir(parents=True, exist_ok=True)
    fps = int(spec.get("fps") or 24)
    audio = None
    length = None
    if spec.get("track"):
        n = film_audio.features(spec["track"], spec.get("voice"), fps, str(work / "audio.json"), "track")
        audio, length = work / "audio.json", n / float(fps)
    elif spec.get("features"):
        audio = Path(spec["features"])
    assembly = spec.get("assembly")
    if assembly is None and length:
        assembly = max(1.0, length - 1.25)   # the ceremony's opening, then the build across the track
    seconds = spec.get("seconds") or length or (assembly + 3.0 if assembly else 12.0)
    camera = spec.get("camera") or ("steady" if spec.get("track") else "tour")
    reactivity = spec.get("reactivity")
    film_mode = bool(audio or assembly or camera == "steady" or reactivity is not None)
    page = work / "page"
    studio.build(spec["scene"], str(page), spec.get("asset_root"), palette=spec.get("palette"),
                 identity=spec.get("identity"), film=film_mode)
    extra = {}
    if audio:
        shutil.copyfile(audio, page / "audio.json")
        extra["audio"] = "audio.json"
    if assembly:
        extra["assembly"] = "%.3f" % assembly
    if camera != "tour":
        extra["camera"] = camera
    if reactivity is not None:
        extra["reactivity"] = "%g" % reactivity
    w, h = (int(x) for x in str(spec.get("size") or "1280x720").lower().split("x"))
    total = int(round(seconds * fps))
    (work / "progress.json").write_text(json.dumps({"total": total, "unit": "frames"}), encoding="utf-8")
    frames = work / "frames"
    render.frames(studio.page_in(str(page)), str(frames), seconds, fps, 0.0, w, h, view=spec.get("view"), extra=extra)
    Path(spec["out"]).parent.mkdir(parents=True, exist_ok=True)
    render.encode_video(str(frames), spec["out"], fps, sound=spec.get("track"))
    shutil.rmtree(frames, ignore_errors=True)
    shutil.rmtree(page, ignore_errors=True)
    print(json.dumps({"film": spec["out"], "seconds": round(seconds, 2), "fps": fps, "size": "%dx%d" % (w, h),
                      "camera": camera, "assembly": assembly, "reactivity": reactivity, "audio": bool(audio)}))
    return 0


def _beside(name):
    """A module that lives beside this file (the plugin's own, not Construct's), loaded by path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("construct_plugin_" + name, Path(__file__).resolve().parent / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def edit(spec):
    """Apply a list of edits to a scene, validating after each; write the result to spec["candidate"] (never to the
    scene itself: the plugin decides whether it replaces it). Prints what happened as JSON."""
    from construct_hologram import diagnose, params, scene as scene_mod
    se = _beside("scene_edit")
    text = Path(spec["scene"]).read_text(encoding="utf-8")
    doc = json.loads(text)
    is_params = params.is_params(doc)

    def problems(d):
        if is_params or not isinstance(d, dict):
            return set()
        return {"%s: %s" % (i.get("where"), i.get("message")) for i in scene_mod.validate_items(d)}

    def errors(report):
        return {"%s|%s|%s" % (d.get("path"), d.get("code"), d.get("message")) for d in report.get("diagnostics") or []
                if d.get("severity") == "error"}

    before = diagnose.diagnose_text(text)
    seen = problems(doc)
    steps = []
    for i, op in enumerate(spec["ops"], 1):
        try:
            changes = se.apply(doc, op)
        except se.EditError as exc:
            print(json.dumps({"ok": False, "failed_at": i, "error": "operation %d (%s): %s" % (i, op.get("op"), exc),
                              "applied": steps}, ensure_ascii=False))
            return 0
        now = problems(doc)
        step = {"n": i, "op": op.get("op"), "changes": changes[:40]}
        if len(changes) > 40:
            step["more_changes"] = len(changes) - 40
        if now - seen:
            step["new_problems"] = sorted(now - seen)[:10]
        if seen - now:
            step["fixed"] = sorted(seen - now)[:10]
        seen = now
        steps.append(step)
    new_text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    after = diagnose.diagnose_text(new_text)
    introduced = sorted(errors(after) - errors(before))
    Path(spec["candidate"]).write_text(new_text, encoding="utf-8")
    print(json.dumps({"ok": not introduced, "applied": steps, "introduced": introduced[:20],
                      "errors_before": before.get("errors"), "report": after}, ensure_ascii=False))
    return 0


def _wbox(g, pid):
    lo, hi = None, None
    for p in g["parts"]:
        if p.get("placement") != pid:
            continue
        for b in p["instances"]:
            lo = list(b["min"]) if lo is None else [min(lo[k], b["min"][k]) for k in range(3)]
            hi = list(b["max"]) if hi is None else [max(hi[k], b["max"][k]) for k in range(3)]
    return (lo, hi) if lo else None


def _surfaces(g, pid, n=24):
    """Where things can stand on a placement: its parts with the widest flat tops (floors, decks, tables)."""
    out = []
    for p in g["parts"]:
        if p.get("placement") != pid:
            continue
        for b in p["instances"][:1]:
            dx, dy, dz = (b["max"][k] - b["min"][k] for k in range(3))
            if dy < 0.6 * min(dx, dz) and dx * dz > 0.05:
                out.append((dx * dz, p["id"], round(b["max"][1], 3), [round(dx, 2), round(dz, 2)]))
    out.sort(reverse=True)
    return [{"on": i, "top_y": y, "size_xz_m": s} for _, i, y, s in out[:n]]


def world(spec):
    """Check a world (construct_hologram/world.py): {"errors"} when it is not valid or cannot be built, else its
    placements as they stand, the world's audit and, for `surfaces_of`, where things can stand on that placement."""
    from construct_hologram import world as w
    doc, folder = spec["doc"], spec["folder"]
    errors = w.validate(doc)
    if errors:
        return {"errors": errors[:12]}
    try:
        g = w.compile_world(doc, folder, None)
        moved = None
        if spec.get("arrange") is not None:   # moved and turned by hand on the page: the world as it is now
            doc, moved = w.arrange(doc, g, spec["arrange"])
            errors = w.validate(doc)
            if errors:
                return {"errors": errors[:12]}
            g = w.compile_world(doc, folder, None)
        landing = list(spec.get("settle") or []) + [c.get("id") for c in (spec.get("arrange") or []) if isinstance(c, dict)]
        if landing:   # set down by hand: each lands on what is under it
            doc, landed = w.settle(doc, g, set(landing))
            if landed:
                g = w.compile_world(doc, folder, None)
                moved = (moved or []) + [i for i in landed if i not in (moved or [])]
    except w.WorldError as exc:
        return {"errors": [str(exc)]}
    report = w.audit(doc, g)
    rows = []
    for r in g["world"]["placements"]:
        row = {"id": r["id"], "title": r["title"], "at": r["at"], "yaw": r["yaw"]}
        for k in ("on", "scale", "floating", "note", "angular_deg"):
            if k in r and not (k == "scale" and abs(r["scale"] - 1) < 1e-9):
                row[k] = r[k]
        box = _wbox(g, r["id"])
        if box:
            row["size_m"] = [round(box[1][k] - box[0][k], 3) for k in range(3)]
            row["bottom_y"] = round(box[0][1], 3)
        rows.append(row)
    out = {"placements": rows, "counts": dict(report["counts"]),
           "warnings": [x["message"] for x in report["warnings"]][:20], "notes": report["info"]["notes"][:10]}
    if spec.get("surfaces_of"):
        out["surfaces"] = _surfaces(g, spec["surfaces_of"])
    if moved is not None or spec.get("settle"):
        out["doc"], out["moved"] = doc, moved or []
    return out


def version():
    from construct_hologram import product
    return product.VERSION


def parse(argv):
    """What Construct's parser (whole option names only) makes of `argv`: the subcommand and every argument's value,
    or the parser's error. Nothing runs."""
    import argparse
    from construct_hologram.__main__ import build_parser
    parser = build_parser()
    err = []

    def refuse(message):
        err.append(message)
        raise SystemExit(2)
    parser.error = refuse
    for action in parser._actions:   # each subcommand's parser reports through the same door
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                sub.error = refuse
    import contextlib
    import io
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ns = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None) and not err:
            return {"help": True}
        return {"error": err[0] if err else "the command line could not be read"}

    def plain(v):
        return v if isinstance(v, (str, int, float, bool)) or v is None else \
            [plain(x) for x in v] if isinstance(v, (list, tuple)) else str(v)
    return {"values": {k: plain(v) for k, v in vars(ns).items()}}


def run(op, args):
    if op == "programs":
        print(json.dumps(programs()))
        return 0
    if op == "cli":
        return _cli(args)
    if op == "parse":
        print(json.dumps(parse(json.loads(Path(args[0]).read_text(encoding="utf-8"))), ensure_ascii=False))
        return 0
    if op == "inspect":
        print(json.dumps(inspect(args[0]), ensure_ascii=False))
        return 0
    if op == "world":
        print(json.dumps(world(json.loads(Path(args[0]).read_text(encoding="utf-8"))), ensure_ascii=False))
        return 0
    if op == "version":
        print(version())
        return 0
    if op == "thumb":
        return thumb({"page": args[0]})
    if op == "edit":
        return edit(json.loads(Path(args[0]).read_text(encoding="utf-8")))
    if op.startswith("netlogo-"):   # the NetLogo ops live beside this file (netlogo_child.py)
        return _beside("netlogo_child").run(op, args)
    if op in ("build", "film"):
        spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        return build(spec) if op == "build" else film(spec)
    sys.stderr.write("unknown op %r\n" % op)
    return 2


def job(folder, op, args):
    """Run an op as a background job and record how it ended, whatever happens."""
    folder = Path(folder)
    code, error = 1, None
    try:
        code = run(op, args)
    except BaseException as exc:   # the job's record must be written however the op ends
        error = "%s: %s" % (type(exc).__name__, exc)
        sys.stderr.write(error + "\n")
    sys.stdout.flush()
    sys.stderr.flush()
    tmp = folder / ".exit.json.tmp"
    tmp.write_text(json.dumps({"code": code, "error": error, "ended": time.time()}), encoding="utf-8")
    os.replace(tmp, folder / "exit.json")
    return code


def main(argv):
    sys.path.insert(0, argv[0])
    op, rest = argv[1], argv[2:]
    if op == "job":
        return job(rest[0], rest[1], rest[2:])
    try:
        return run(op, rest)
    except Exception as exc:
        sys.stderr.write("%s: %s\n" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
