"""Construct's side of the plugin: run in a child process, never imported by Hermes.

    python -I -B child.py <vendor folder> <op> [args...]

The vendor folder (the one holding `construct_hologram`) goes first on the path; with -I nothing else
from the user's site or the current folder is imported. Ops:

    programs                  which outside programs Construct finds (JSON)
    cli <argv...>             Construct's own command line
    build <spec.json>         `build`, then a small still for the gallery when a browser is there
    inspect <scene>           what the scene's own record says is known (JSON)
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


def _short(text, n=160):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def _capped(items, n):
    return {"items": items[:n], "more": len(items) - n} if len(items) > n else {"items": items}


ROLE_ORDER = ("identity", "mass", "structure", "artwork", "data", "detail", "ornament", "ground")
GROUPS = ("verified", "size_verified", "shape_verified", "supplied", "traced", "inferred", "designed", "decorative")
LEVELS = {2: "described", 3: "seen", 4: "seen and checked"}


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


def run(op, args):
    if op == "programs":
        print(json.dumps(programs()))
        return 0
    if op == "cli":
        return _cli(args)
    if op == "inspect":
        print(json.dumps(inspect(args[0]), ensure_ascii=False))
        return 0
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
