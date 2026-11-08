"""The tool handlers. Each takes the model's arguments and returns a JSON string; none raises."""

import base64
import functools
import html
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

from . import jobs, readback, runtime, schemas
from .runtime import ConstructError

log = logging.getLogger(__name__)

WAIT = {"build": 240, "review": 300, "export": 330, "check": 300, "film": 4}
REVIEW_SHOW = ["hero", "sheet-views", "sheet-assembly", "view-open"]
LIST_CAP = 40
_surface = {"fn": None}


def set_surface(fn):
    """`fn()` names the calling session's client (desktop, cli, tui...) or messaging platform."""
    _surface["fn"] = fn


def _desktop_or_local():
    fn = _surface["fn"]
    try:
        surface = fn() if fn else ""
    except Exception:
        surface = ""
    return surface in ("", "desktop", "cli", "tui", "acp", "local")


def tool(name):
    """Wrap a handler: known arguments only, a JSON string always, an error as {"error": ...}."""
    allowed = set(schemas.by_name(name)["parameters"]["properties"])

    def wrap(fn):
        @functools.wraps(fn)
        def handler(args=None, **kwargs):
            try:
                args = args or {}
                if not isinstance(args, dict):
                    raise ConstructError("arguments must be an object")
                unknown = sorted(set(args) - allowed)
                if unknown:
                    raise ConstructError("unknown argument(s) %s; this tool takes %s" % (
                        ", ".join(unknown), ", ".join(sorted(allowed))))
                out = fn(args)
            except ConstructError as exc:
                out = {"error": str(exc)}
            except Exception as exc:   # never let a handler raise into the agent loop
                log.exception("construct: %s failed", name)
                out = {"error": "%s failed: %s: %s" % (name, type(exc).__name__, exc)}
            return json.dumps(out, ensure_ascii=False)
        return handler
    return wrap


def _bool(args, key, default=False):
    v = args.get(key, default)
    if not isinstance(v, bool):
        raise ConstructError("%s must be true or false" % key)
    return v


def _choice(args, key, options, default=None):
    v = args.get(key, default)
    if v is not None and v not in options:
        raise ConstructError("%s must be one of %s" % (key, ", ".join(options)))
    return v


def _number(args, key, lo, hi, integer=False):
    v = args.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and not isinstance(v, int)) or not lo <= v <= hi:
        raise ConstructError("%s must be %s from %g to %g" % (key, "an integer" if integer else "a number", lo, hi))
    return v


def _size(args, key, default):
    v = args.get(key, default)
    if not isinstance(v, str) or not re.match(r"^[0-9]{3,4}x[0-9]{3,4}$", v):
        raise ConstructError("%s must be WIDTHxHEIGHT, e.g. 1280x720" % key)
    return v


def _file(args, key):
    v = args.get(key)
    if v is None:
        return None
    p = Path(str(v)).expanduser()
    if not p.is_absolute() or not p.is_file():
        raise ConstructError("%s must be an existing file, by absolute path" % key)
    return str(p.resolve())


def media(*paths):
    return ["MEDIA:%s" % p for p in paths if p]


def _waited(job_id, kind, seconds, label):
    """A job's result if it ends within `seconds`; else its handle and a watcher that reports it."""
    if jobs.wait(job_id, seconds) is not None:
        return jobs.status(job_id)
    jobs.watch(job_id, label)
    return {"job_id": job_id, "state": "running", "kind": kind,
            "next": "it outlasted this call; call construct_job with this job_id for its result"}


# ---------------------------------------------------------------------------- start

@tool("construct_start")
def start(args):
    sources = [k for k in ("archetype", "category", "example", "from_path") if args.get(k) is not None]
    if len(sources) > 1:
        raise ConstructError("give one source: %s" % " or ".join(sources))
    if not sources:
        code, out, err = runtime.run_child("cli", "params", "--list", timeout=60)
        rows = [{k: e.get(k) for k in ("name", "title", "parts", "line", "use")} for e in runtime.catalog()]
        worlds = [{k: w[k] for k in ("name", "title", "summary")} for w in runtime.example_worlds().values()]
        return {"examples": rows, "worlds": worlds, "archetypes": out.strip() if code == 0 else err.strip(),
                "categories": schemas.CATEGORIES, "programs": runtime.programs(),
                "next": "call construct_start with one of example (a finished construct to start from or show), archetype "
                        "(+ variant), category or from_path"}
    title = args.get("title")
    if title is not None and (not isinstance(title, str) or len(title) > 120):
        raise ConstructError("title must be a string of at most 120 characters")
    source = sources[0]
    if source == "archetype":
        _choice(args, "archetype", schemas.ARCHETYPES)
        if args.get("variant") is not None and not isinstance(args["variant"], str):
            raise ConstructError("variant must be a string")
        seed = _number(args, "seed", 0, 2 ** 31, integer=True)
    elif source == "category":
        _choice(args, "category", schemas.CATEGORIES)
    elif source == "example":
        known = runtime.examples()
        if args["example"] not in known:
            raise ConstructError("no bundled example %r; examples: %s" % (args["example"], ", ".join(sorted(known))))
    else:
        origin = _file(args, "from_path")
    slug, folder = runtime.new_project(title or args.get("example") or args.get("variant") or args.get("archetype")
                                       or args.get("category") or Path(args.get("from_path", "construct")).stem)
    try:
        name = "scene.json"
        if source == "archetype":
            name = "scene.params.json"
            argv = ["params", args["archetype"], "--output", str(folder / name)]
            if args.get("variant"):
                argv += ["--variant", args["variant"]]
            if seed is not None:
                argv += ["--seed", str(seed)]
            code, out, err = runtime.run_child("cli", *argv, timeout=60, cwd=folder)
            if code:
                raise ConstructError("params: %s" % (err.strip() or out.strip()))
            if title:
                _retitle(folder / name, title)
        elif source == "category":
            argv = ["new", args["category"], "--output", str(folder / name)] + (["--title", title] if title else [])
            code, out, err = runtime.run_child("cli", *argv, timeout=60, cwd=folder)
            if code:
                raise ConstructError("new: %s" % (err.strip() or out.strip()))
        else:
            if source == "example":
                files = runtime.examples()[args["example"]]
                src, maps = files["scene"], files["materials"]
                if files.get("kit_plan"):   # its model kit plan, for construct_command kit --plan kit-plan.json
                    shutil.copyfile(files["kit_plan"], folder / "kit-plan.json")
            else:
                src = Path(origin)
                maps = src.with_name(re.sub(r"(\.params)?\.json$", "", src.name) + ".materials.json")
            if src.name.endswith(".params.json"):
                name = "scene.params.json"
            _copy_scene(src, folder / name)
            if maps and maps.is_file():   # the paints travel with it, beside the scene where export finds them
                shutil.copyfile(maps, folder / (re.sub(r"(\.params)?\.json$", "", name) + ".materials.json"))
            if title:
                _retitle(folder / name, title)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)   # no half-made project left behind
        raise
    doc = json.loads((folder / name).read_text(encoding="utf-8"))
    info = {"slug": slug, "title": doc.get("title") or title or slug, "scene": name, "origin": source,
            "from": args.get(source), "created": runtime.stamp_iso()}
    if isinstance(args.get("for_world"), str) and args["for_world"].strip():
        info["for_world"] = args["for_world"].strip()[:120]
    runtime.write_json(folder / "project.json", info)
    return {"project": slug, "project_dir": str(folder), "scene": str(folder / name), "title": doc.get("title"),
            "kind": "parameter document" if name.endswith(".params.json") else "scene", "programs": runtime.programs(),
            "next": "edit the scene file with your file tools (facts with certainty and sources first), then "
                    "construct_check until needs_repair is false, then construct_build"}


def _retitle(path, title):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict):
        doc["title"] = title
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_scene(src, dst):
    """Copy a scene and the artwork files it names by relative path (never a path that leaves its folder)."""
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConstructError("%s is not a JSON scene: %s" % (src, exc))
    if not isinstance(doc, dict) or not (doc.get("parts") or doc.get("archetype") or doc.get("format")):
        raise ConstructError("%s is not a Construct scene or parameter document" % src)
    shutil.copyfile(src, dst)
    base = src.parent.resolve()
    paths = [a.get("path") for a in doc.get("assets", []) if isinstance(a, dict)]
    paths += [a.get("path") for a in (doc.get("artwork") or {}).values() if isinstance(a, dict)] \
        if isinstance(doc.get("artwork"), dict) else []
    for rel in paths:
        if not isinstance(rel, str) or Path(rel).is_absolute():
            continue
        f = (base / rel).resolve()
        if runtime.inside(f, [base]) and f.is_file() and f.stat().st_size <= 32 * 1024 * 1024:
            (dst.parent / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst.parent / rel)


# ---------------------------------------------------------------------------- check and inspect

def _compact_check(report, scene):
    out = {k: report.get(k) for k in ("ok", "needs_repair", "errors", "warnings", "stats") if k in report}
    diags = report.get("diagnostics") or []
    out["diagnostics"] = [{k: d.get(k) for k in ("severity", "code", "path", "message", "hint") if d.get(k) is not None}
                          for d in diags[:LIST_CAP]]
    if len(diags) > LIST_CAP:
        out["diagnostics_left_out"] = len(diags) - LIST_CAP
    if report.get("needs_repair") and report.get("repair_text"):
        out["repair_text"] = report["repair_text"][:8000]
    if "fit" in report and report["fit"] is not None:
        fit = report["fit"]
        issues = fit.get("issues") or []
        rows = []
        for i in issues[:30]:
            small, big = (list(i.get("parts") or []) + [None, None])[:2]   # an open shell names one part
            row = {"code": i.get("code"), "parts": i.get("parts"), "at_m": i.get("at"), "share": i.get("share"),
                   "message": i.get("message")}
            if i.get("code") == "pokes":
                row["fix"] = ("Trim or move %s so it ends at %s's face near %s (or shorten it there); leave it only if it "
                              "is meant to pass through." % (small, big, i.get("at")))
            elif i.get("code") == "crosses-glass":
                row["fix"] = ("%s runs through the pane %s: move or trim it to stop at the glass, or fit the pane to its "
                              "frame if it is the glass that is out of place." % (small, big))
            elif i.get("code") == "open":
                row["fix"] = ("%s is an open shell (a hole shows in the solid): close it (cap the ends, give the skin a "
                              "back) or, if it is meant to be open and hidden, leave it." % small)
            elif i.get("code") == "buried":
                row["fix"] = ("%s is hidden inside %s: if it should show, move it out to sit on %s's surface (or make %s "
                              "thinner); if it is a hidden part by design, leave it or remove it." % (small, big, big, big))
            rows.append(row)
        out["fit"] = {"parts": fit.get("parts"), "issues": rows,
                      "summary": "nothing pokes through or hides" if not issues else
                      "%d finding(s), what shows most first" % len(issues)}
        if len(issues) > 30:
            out["fit"]["left_out"] = len(issues) - 30
    out["scene"] = str(scene)
    return out


@tool("construct_check")
def check(args):
    slug, folder, scene = runtime.resolve(args)
    fit = _bool(args, "fit")
    argv = ["check", str(scene), "--json"]
    if fit:
        argv.append("--fit")
        cells = _number(args, "cells", 40, 600, integer=True)
        if cells:
            argv += ["--cells", str(cells)]
    job_id = jobs.start("check", "cli", argv, project=slug, label="check of %s" % slug, cwd=folder,
                        finish={"scene": str(scene)})
    return _waited(job_id, "check", WAIT["check"], "check of %s" % slug)


def _finish_check(rec, done, tail):
    # the report is the log's JSON (stdout and stderr share the log; the report is one JSON object)
    full = (runtime.jobs_root() / rec["id"] / "log.txt").read_text(encoding="utf-8", errors="replace")
    start, end = full.find("{"), full.rfind("}")
    try:
        report = json.loads(full[start:end + 1]) if start >= 0 else None
    except ValueError:
        report = None
    if not isinstance(report, dict):
        raise ConstructError("check could not read the scene: %s" % full.strip()[-2000:])
    out = _compact_check(report, rec["finish"].get("scene", ""))
    out["state"] = "done"
    return out


@tool("construct_inspect")
def inspect(args):
    name = args.get("project")
    shipped = runtime.examples() if isinstance(name, str) and not args.get("scene") else {}
    if name in shipped and not (runtime.SLUG.match(name) and (runtime.projects_root() / name).is_dir()):
        # a construct the plugin ships, read where it is (nothing is written): what a world will place, measured
        slug, scene = name, Path(shipped[name]["scene"])
        folder = scene.parent
    else:
        slug, folder, scene = runtime.resolve(args)
    code, out, err = runtime.run_child("inspect", str(scene), timeout=120, cwd=folder)
    if code:
        raise ConstructError("could not read the scene: %s" % (err.strip()[-2000:] or "unknown error"))
    rec = json.loads(out)
    rec["project"] = slug
    rec["how_to_read"] = ("verified: cites a source; size_verified/shape_verified: one axis verified; supplied: the "
                          "user's; traced: fitted to a drawing; inferred: estimated from a description or a picture "
                          "(evidence says which); designed: invented for the presentation; decorative: ornament")
    return rec


# ---------------------------------------------------------------------------- edit

@tool("construct_edit")
def edit(args):
    from . import scene_edit
    slug, folder, scene = runtime.resolve(args)
    if not runtime.inside(scene, runtime.allowed_roots()):
        raise ConstructError("the scene %s is outside the projects: construct_edit changes only scenes inside a project. "
                             "Copy it in first (construct_start from_path), then edit the copy" % scene)
    try:
        ops = scene_edit.check_ops(args.get("operations"))
    except scene_edit.EditError as exc:
        raise ConstructError(str(exc))
    dry = _bool(args, "dry_run")
    work = folder / "edits"
    work.mkdir(parents=True, exist_ok=True)
    edit_id = runtime.new_id()
    spec_path, candidate = work / (".%s.spec.json" % edit_id), work / (".%s.candidate.json" % edit_id)
    runtime.write_json(spec_path, {"scene": str(scene), "ops": ops, "candidate": str(candidate)})
    try:
        code, out, err = runtime.run_child("edit", str(spec_path), timeout=360, cwd=folder)
        try:
            res = json.loads(out.strip().splitlines()[-1]) if out.strip() else None
        except ValueError:
            res = None
        if code or not isinstance(res, dict):
            raise ConstructError("the edit could not run: %s" % (err.strip()[-2000:] or out.strip()[-2000:] or "no answer"))
        result = {"project": slug, "scene": str(scene), "applied": res.get("applied", []), "dry_run": dry}
        if res.get("error"):
            result.update(written=False, error=res["error"],
                          next="nothing was written; fix that operation (the ones before it are shown) and send the list again")
            return result
        report = _compact_check(res.get("report") or {}, scene)
        report.pop("scene", None)
        result["check"] = report
        if res.get("introduced"):
            result.update(written=False, introduced=res["introduced"],
                          next="nothing was written: these edits add the errors listed under introduced (the step that "
                               "added each is under applied[].new_problems); change the operations and send them again")
            return result
        if dry:
            result.update(written=False, next="a dry run: send the same operations without dry_run to write them")
            return result
        before = work / ("%s-before.json" % edit_id)
        shutil.copyfile(scene, before)   # the scene as it was, to go back to
        os.replace(candidate, scene)
        with open(work / "log.jsonl", "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({"id": edit_id, "at": runtime.stamp_iso(), "ops": ops,
                                       "before": before.name}, ensure_ascii=False) + "\n")
        _keep_newest(work, "*-before.json", 20)
        result.update(written=True, undo=str(before),
                      next="written; construct_check if the summary shows problems, then construct_build to see it")
        return result
    finally:
        for p in (spec_path, candidate):
            try:
                p.unlink()
            except OSError:
                pass


def _keep_newest(folder, pattern, keep):
    for old in sorted(folder.glob(pattern))[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------- build

@tool("construct_build")
def build(args):
    slug, folder, scene = runtime.resolve(args)
    palette = _choice(args, "palette", schemas.PALETTES)
    identity = _choice(args, "identity", schemas.IDENTITIES)
    build_id = runtime.new_id()
    out = folder / "builds" / build_id
    spec = {"scene": str(scene), "out": str(out), "thumb": _bool(args, "thumbnail", True), "palette": palette,
            "identity": identity, "asset_root": str(scene.parent)}
    job_id = jobs.start("build", "build", project=slug, label="build of %s" % slug, cwd=folder, spec=spec,
                        finish={"slug": slug, "build": build_id, "out": str(out), "scene": str(scene)})
    return _waited(job_id, "build", WAIT["build"], "build of %s" % slug)


def _title_of(page):
    with open(page, "r", encoding="utf-8", errors="replace") as fh:
        head = fh.read(4096)
    m = re.search(r"<title>(.*?)</title>", head, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def _finish_build(rec, done, tail):
    f = rec["finish"]
    if Path(f["scene"]).name == "world.json":   # a world: the Worlds page lists it, and its card can be arranged
        try:
            n = len(json.loads(Path(f["scene"]).read_text(encoding="utf-8")).get("placements", []))
        except (OSError, ValueError):
            n = None
        return publish(f["slug"], f["build"], Path(f["out"]), f["scene"], tail, kind="world", extra_card={"placements": n})
    return publish(f["slug"], f["build"], Path(f["out"]), f["scene"], tail)


def publish(slug, build_id, out, scene, tail="", kind="construct", extra_card=None):
    """A finished build (`out` holds construct.html and audit.json) put where chat and the Constructs page show it;
    the tool result with its MEDIA line. Other tools that make a construct page (a NetLogo run) end here too."""
    page = Path(out) / "construct.html"
    if not page.is_file():
        raise ConstructError("the build failed:\n%s" % tail)
    try:
        audit = json.loads((Path(out) / "audit.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        audit = {}
    info = audit.get("info", {})
    title = _title_of(page) or slug
    card = {"project": slug, "build": build_id, "title": title, "parts": info.get("parts"), "kind": kind,
            "counts": info.get("counts", {}), "size_m": info.get("dimensions_m"), "audit_ok": audit.get("ok"),
            "warnings": [str(x.get("message", x) if isinstance(x, dict) else x)[:200] for x in (audit.get("warnings") or [])][:12],
            "created": runtime.stamp_iso(), "page": str(page), "scene": str(scene)}
    card.update(runtime.scene_stamp(scene))
    card.update(extra_card or {})
    shown = runtime.show(slug, build_id, page, card, thumb=Path(out) / "thumb.png")
    runtime.prune(Path(out).parent)
    loader = shown / "loader.html"
    full = shown / "construct.html"
    first = loader if _desktop_or_local() else full
    audit_text = ""
    try:
        audit_text = (Path(out) / "audit.txt").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    result = {"success": True, "project": slug, "build": build_id,
              "title": title, "parts": info.get("parts"), "counts": info.get("counts"), "size_m": info.get("dimensions_m"),
              "audit": {"ok": audit.get("ok"), "errors": [e.get("message", e) if isinstance(e, dict) else e
                                                           for e in audit.get("errors", [])][:20],
                        "warnings": [w.get("message", w) if isinstance(w, dict) else w
                                     for w in audit.get("warnings", [])][:20], "report": audit_text[:3000]},
              "page": str(page), "file_path": str(first), "media_tag": "MEDIA:%s" % first, "media": media(first),
              "next": "put the MEDIA line in your reply; review it with construct_review"}
    if first == loader:
        result["page_in_browser"] = str(full)
    return result


# ---------------------------------------------------------------------------- review

@tool("construct_review")
def review(args):
    slug, folder, scene = runtime.resolve(args)
    sheets = args.get("sheets") or list(schemas.SHEETS)
    if not isinstance(sheets, list) or any(s not in schemas.SHEETS for s in sheets) or not sheets:
        raise ConstructError("sheets must be a list from %s" % ", ".join(schemas.SHEETS))
    show = args.get("show") or REVIEW_SHOW
    if not isinstance(show, list) or any(s not in schemas.REVIEW_IMAGES for s in show):
        raise ConstructError("show must be a list from %s" % ", ".join(schemas.REVIEW_IMAGES))
    size = _size(args, "size", "1280x800")
    out = folder / "review" / runtime.new_id()
    argv = ["review", str(scene), "--out", str(out), "--size", size, "--sheets", ",".join(sheets),
            "--asset-root", str(scene.parent)]
    for k, opts in (("palette", schemas.PALETTES), ("identity", schemas.IDENTITIES)):
        if _choice(args, k, opts):
            argv += ["--" + k, args[k]]
    job_id = jobs.start("review", "cli", argv, project=slug, label="review of %s" % slug, cwd=folder,
                        finish={"slug": slug, "out": str(out), "show": show})
    return _waited(job_id, "review", WAIT["review"], "review of %s" % slug)


def _finish_review(rec, done, tail):
    f = rec["finish"]
    folder = Path(f["out"]) / "review"
    if done.get("code") == 2 or "capture unavailable" in tail:
        raise ConstructError("no review images: %s. Deliver the page without captures and say so; do not install a "
                             "browser." % (tail.strip().splitlines()[-1] if tail.strip() else "no browser"))
    images = {p.stem: str(p) for p in sorted(folder.glob("*.png"))} if folder.is_dir() else {}
    if not images:
        raise ConstructError("the review made no images:\n%s" % tail)
    runtime.prune(Path(f["out"]).parent, keep=4)
    shown = [images[n] for n in f["show"] if n in images]
    return {"success": True, "project": f["slug"], "images": images, "media": media(*shown),
            "audit_ok": done.get("code") == 0, "report": tail[-3000:],
            "next": "look at the images (vision) and score them with the art-direction rubric; put the MEDIA lines "
                    "you want the user to see in your reply"}


# ---------------------------------------------------------------------------- export

EXT = {"glb": ".glb", "obj": ".obj", "stl": ".stl", "3mf": ".3mf", "fcstd": ".FCStd", "step": ".step"}


@tool("construct_export")
def export(args):
    return _export(args, WAIT["export"])


def _export(args, wait):
    """An export started (and waited for `wait` seconds): the tool's, and the Desktop card's (which does not wait)."""
    slug, folder, scene = runtime.resolve(args)
    fmt = _choice(args, "format", list(EXT))
    if fmt is None:
        raise ConstructError("format is required: %s" % ", ".join(EXT))
    stem = re.sub(r"(\.params)?\.json$", "", scene.name)
    stem = slug if stem in ("scene", "construct") else stem
    exports = folder / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    target = exports / ("%s-%s%s" % (stem, runtime.new_id(), EXT[fmt]))
    extra_files = []
    if fmt in ("glb", "obj"):
        argv = ["export", str(scene), "--out", str(target)]
        for k, opts in (("wire", ["edges", "tubes", "seams", "none"]), ("pose", ["closed", "open"]),
                        ("frame", ["y-up", "z-up"])):
            if _choice(args, k, opts):
                argv += ["--" + k, args[k]]
        pieces = _choice(args, "pieces", ["none", "glued", "loose"])
        if pieces and pieces != "none":
            argv += ["--pieces", pieces]
        if _bool(args, "merge"):
            argv.append("--merge")
        if _bool(args, "colliders"):
            argv.append("--colliders")
        mats = _materials(args, scene, exports)
        if mats:
            argv += ["--materials", mats]
    elif fmt in ("stl", "3mf"):
        argv = ["print", str(scene), "--out", str(target)]
        size, scale, fit = _number(args, "size_mm", 5, 2000), _number(args, "scale", 1, 10000), _bool(args, "fit")
        if sum(1 for x in (size, scale, fit or None) if x) > 1:
            raise ConstructError("give one of size_mm, scale or fit")
        if size:
            argv += ["--size", "%g" % size]
        if scale:
            argv += ["--scale", "%g" % scale]
        if fit:
            argv.append("--fit")
        if _choice(args, "printer", ["small", "desktop", "cube", "large", "resin"]):
            argv += ["--printer", args["printer"]]
        if _bool(args, "exact"):
            if fmt != "3mf":
                raise ConstructError("exact is for 3mf (its solids are parts of one object)")
            argv.append("--exact")
        if _choice(args, "lines", ["none", "engrave", "raised"]):
            argv += ["--lines", args["lines"]]
    else:
        found = runtime.programs().get("freecad")
        if not found:
            raise ConstructError("FreeCAD is not installed (Construct looks for freecadcmd on the PATH and in the usual "
                                 "places, or CONSTRUCT_FREECAD). Say so, and offer glb or step another way.")
        argv = ["freecad", str(scene), "--out", str(target)]
        if fmt == "fcstd" and _bool(args, "step"):
            step = target.with_suffix(".step")
            argv += ["--step", str(step)]
            extra_files.append(str(step))
    label = "%s export of %s" % (fmt, slug)
    job_id = jobs.start("export", "cli", argv, project=slug, label=label, cwd=folder,
                        finish={"slug": slug, "file": str(target), "format": fmt, "extra": extra_files})
    return _waited(job_id, "export", wait, label)


def _materials(args, scene, exports):
    if args.get("materials") is not None and args.get("materials_path") is not None:
        raise ConstructError("give materials or materials_path, not both")
    if isinstance(args.get("materials"), dict):
        path = exports / ("materials-%s.json" % runtime.new_id())
        runtime.write_json(path, args["materials"])
        return str(path)
    if args.get("materials") is not None:
        raise ConstructError("materials must be an object (a material map)")
    if args.get("materials_path") is not None:
        p = Path(str(args["materials_path"])).expanduser()
        p = p if p.is_absolute() else scene.parent / p
        if not p.is_file():
            raise ConstructError("no material map at %s" % p)
        return str(p)
    beside = scene.with_name(re.sub(r"(\.params)?\.json$", "", scene.name) + ".materials.json")
    return str(beside) if beside.is_file() else None


def _finish_export(rec, done, tail):
    f = rec["finish"]
    target = Path(f["file"])
    if not target.is_file():
        raise ConstructError("the export failed:\n%s" % tail)
    files = [str(target)] + [x for x in f.get("extra", []) if Path(x).is_file()]
    if f["format"] == "obj" and target.with_suffix(".mtl").is_file():
        files.append(str(target.with_suffix(".mtl")))
    verified = verify_export(target, f["format"], tail)
    out = {"success": True, "project": f["slug"], "format": f["format"], "file_path": str(target), "files": files,
           "bytes": target.stat().st_size, "verified": verified, "summary": verified.get("summary", ""),
           "report": tail.strip()[-3000:], "media": media(str(target)), "media_tag": "MEDIA:%s" % target,
           "next": "the verified block is Construct's own read-back of the written file: report it as it is (size, "
                   "parts, animations, bounds); there is no need to open the file in another program to check it. "
                   "Put the MEDIA line in your reply"}
    for extra in files[1:]:
        if Path(extra).suffix.lower() in (".step", ".stp"):
            out["verified_step"] = verify_export(Path(extra), "step", tail)
    if f["format"] in ("stl", "3mf") and done.get("code") == 1:
        out["printable"] = False
        out["warning"] = "not watertight: do not hand it over as printable; read the report"
    elif f["format"] in ("stl", "3mf"):
        out["printable"] = True
    item = runtime.record_item(f["slug"], "export", target, title="%s export" % f["format"].upper(), summary=verified)
    if item:
        out["item"] = item["id"]   # the Desktop half reads a model too large for the chat's own reader by this id
    for extra in files[1:]:
        if Path(extra).suffix.lower() in (".step", ".stp"):
            runtime.record_item(f["slug"], "export", extra, title="STEP export", summary=out.get("verified_step"))
    return out


def verify_export(target, fmt, tail=""):
    """What the written file holds, read back from it (readback.py), with Construct's own counts and one line to say."""
    got = readback.read(target)
    made = readback.construct_report(tail)
    got["construct"] = made
    b = got.get("bounds")
    dims = ""
    if b:
        dims = "%s m (%s mm)" % (" x ".join("%g" % v for v in b["m"]), " x ".join("%g" % v for v in b["mm"]))
    bits = ["%s %s" % (got["size"], fmt.upper())]
    if fmt == "glb" and "nodes" in got:
        bits.append("%d named parts in %d nodes and %d meshes, %d triangles" % (
            got["named_parts"], got["nodes"], got["meshes"], got["triangles"]))
        if got.get("animations"):
            bits.append("animations: " + ", ".join("%s (%gs, %d channels)" % (a["name"] or "unnamed", a["seconds"], a["channels"])
                                                   for a in got["animations"]))
        else:
            bits.append("no animations")
    elif fmt == "obj" and "objects" in got:
        bits.append("%d named objects, %d faces" % (got["objects"], got["faces"]))
    elif fmt in ("stl", "3mf") and "triangles" in got:
        bits.append("%d triangles%s" % (got["triangles"], ", %d objects" % got["objects"] if fmt == "3mf" else ""))
    elif fmt == "step" and "solids" in got:
        bits.append("%d products, %d solids, %d faces (%d curved: %s)" % (
            got["products"], got["solids"], got["faces"], got["curved_faces"],
            ", ".join("%s %d" % kv for kv in sorted(got["surfaces"].items())) or "none"))
    elif fmt == "fcstd" and "solids" in got:
        bits.append("%d named solids in %d objects" % (got["solids"], got["objects"]))
    if fmt in ("step", "fcstd") and "exact" in made:
        bits.append("%d exact CAD shapes, %d faceted" % (made["exact"], made["faceted"]))
    if made.get("joints") is not None:
        bits.append("%d joints" % made["joints"])
    if dims:
        bits.append(dims)
    if got.get("error"):
        bits.append("READ-BACK FAILED: " + got["error"])
    got["summary"] = "; ".join(bits)
    got["verified_by"] = "the plugin read the written file back (not the scene)"
    return got


# ---------------------------------------------------------------------------- film

@tool("construct_film")
def film(args):
    slug, folder, scene = runtime.resolve(args)
    found = runtime.programs()
    missing = [n for n, k in (("a Chromium-family browser", "browser"), ("ffmpeg", "ffmpeg")) if not found.get(k)]
    if missing:
        raise ConstructError("a film needs %s, which this machine does not have; do not install anything, say so" %
                             " and ".join(missing))
    track, voice, features = _file(args, "track"), _file(args, "voice"), _file(args, "audio_features")
    if track and features:
        raise ConstructError("give track or audio_features, not both")
    if voice and not track:
        raise ConstructError("voice goes with a track")
    spec = {"scene": str(scene), "asset_root": str(scene.parent), "track": track, "voice": voice, "features": features,
            "seconds": _number(args, "seconds", 1, 1800), "assembly": _number(args, "assembly", 1, 1200),
            "camera": _choice(args, "camera", ["tour", "steady", "still"]),
            "reactivity": _number(args, "reactivity", 0, 2), "size": _size(args, "size", "1280x720"),
            "fps": _number(args, "fps", 12, 60, integer=True) or 24, "view": args.get("view"),
            "palette": _choice(args, "palette", schemas.PALETTES), "identity": _choice(args, "identity", schemas.IDENTITIES)}
    if spec["view"] is not None and (not isinstance(spec["view"], str) or not re.match(r"^[a-z0-9-]{1,64}$", spec["view"])):
        raise ConstructError("view must be a view id such as front, side or hero")
    films = folder / "films"
    spec["out"] = str(films / ("film-%s.mp4" % runtime.new_id()))
    label = "film of %s" % slug
    job_id = jobs.start("film", "film", project=slug, label=label, cwd=folder, spec=spec,
                        finish={"slug": slug, "file": spec["out"]})
    done = jobs.wait(job_id, WAIT["film"])
    if done is not None:   # it ended at once: something was missing
        return jobs.status(job_id)
    jobs.watch(job_id, label)
    return {"job_id": job_id, "state": "running", "kind": "film", "project": slug,
            "next": "the film renders in the background (about 1-2 frames a second); tell the user, then check it with "
                    "construct_job"}


def _finish_film(rec, done, tail):
    f = rec["finish"]
    target = Path(f["file"])
    if done.get("code") != 0 or not target.is_file():
        raise ConstructError("the film failed:\n%s" % tail)
    about = {}
    for line in reversed(tail.splitlines()):
        if line.startswith("{"):
            try:
                about = json.loads(line)
            except ValueError:
                pass
            break
    runtime.record_item(f["slug"], "film", target, title="film", summary=about)
    return {"success": True, "project": f["slug"], "file_path": str(target), "film": about,
            "bytes": target.stat().st_size, "media": media(str(target)), "media_tag": "MEDIA:%s" % target,
            "next": "sample frames to check it moves with the music and ends whole, then put the MEDIA line in your reply"}


# ---------------------------------------------------------------------------- jobs

@tool("construct_job")
def job(args):
    job_id = args.get("job_id")
    if job_id is None:
        return {"jobs": jobs.recent()}
    if _bool(args, "cancel"):
        stopped = jobs.cancel(job_id)
        time.sleep(0.3)
        out = jobs.status(job_id)
        out["cancelled"] = stopped
        return out
    wait = _number(args, "wait_seconds", 1, schemas.WAIT_MAX, integer=True)
    if wait:
        jobs.folder(job_id)   # a bad id is refused before waiting
        started = time.time()
        jobs.wait(job_id, wait)
        out = jobs.status(job_id)
        out["waited_s"] = round(time.time() - started, 1)
        if out.get("state") == "running":
            out["next"] = "still running after %d s; call construct_job again with wait_seconds" % wait
        return out
    return jobs.status(job_id)


# ---------------------------------------------------------------------------- command

COMMANDS = {"new", "params", "expand", "check", "build", "review", "export", "print", "kit", "freecad", "trace",
            "terrain", "globe", "critique", "rounds", "compare", "loft-from-traces", "audio", "video", "netlogo",
            "netlogo-instrument", "netlogo-compare", "netlogo-plates", "netlogo-film", "prompts"}
NETWORK = {"author": "it drafts with a model over the network", "trace-image": "it sends images to a model over the network"}
# what Construct's parser makes of a command line (whole option names only), by the argument it sets
WRITES = {"out": "--out", "output": "--output", "overlay": "--overlay", "into": "--into", "glb": "--glb", "csv": "--csv",
          "materials_out": "--materials-out", "blend": "--blend", "dir": "--dir", "step": "--step"}
NETWORK_ARGS = {"base_url": "--base-url", "critic_base_url": "--critic-base-url", "key_env": "--key-env",
                "critic_key_env": "--critic-key-env", "critic_model": "--critic-model"}
PROGRAM_ARGS = {"freecad": "--freecad", "blender": "--blender"}


def parsed(argv):
    """argv as Construct's own parser reads it, in a child (nothing runs): {name: value}, or a refusal."""
    spec = runtime.data_dir() / "work" / (".argv-%s.json" % runtime.new_id())
    spec.parent.mkdir(parents=True, exist_ok=True)
    try:
        runtime.write_json(spec, argv)
        code, out, err = runtime.run_child("parse", str(spec), timeout=60)
    finally:
        spec.unlink(missing_ok=True)
    try:
        got = json.loads(out) if code == 0 else None
    except ValueError:
        got = None
    if not isinstance(got, dict):
        raise ConstructError("Construct could not read that command line: %s" % (err.strip()[-400:] or "no answer"))
    if got.get("error"):
        hint = " (options are written in full: --out, not --ou)" if "unrecognized" in got["error"] else ""
        raise ConstructError("construct %s: %s%s" % (argv[0], got["error"], hint))
    return got.get("values")   # None: a help request, which runs nothing else


@tool("construct_command")
def command(args):
    argv = args.get("argv")
    if not isinstance(argv, list) or not argv or len(argv) > 64 or \
            any(not isinstance(a, str) or len(a) > 4000 or "\0" in a for a in argv):
        raise ConstructError("argv must be a list of 1 to 64 strings")
    sub = argv[0]
    if sub in NETWORK:
        raise ConstructError("%s is not run by the plugin: %s. Do that step yourself (a delegated subagent for a critic)." %
                             (sub, NETWORK[sub]))
    if sub not in COMMANDS:
        raise ConstructError("unknown or unavailable subcommand %r; available: %s" % (sub, ", ".join(sorted(COMMANDS))))
    # every check below reads what Construct's parser will act on, never the spelling of a flag
    values = parsed(argv) or {}
    for name, flag in NETWORK_ARGS.items():
        if values.get(name) not in (None, False):
            raise ConstructError("%s calls a model over the network; the plugin does not. Delegate the critic to a fresh "
                                 "subagent and record its answer instead." % flag)
    for name, flag in PROGRAM_ARGS.items():
        if values.get(name) not in (None, ""):
            raise ConstructError("%s names a program to run; the plugin runs only the %s it finds itself (the plugin's "
                                 "settings, CONSTRUCT_%s, or PATH). Drop %s." % (flag, name.title(), name.upper(), flag))
    if sub == "rounds" and values.get("action") == "run":
        raise ConstructError("rounds run calls a model over the network; use rounds packet, a delegated critic and "
                             "rounds record")
    project = args.get("project")
    folder = runtime.project_dir(project) if project else runtime.data_dir() / "work"
    folder.mkdir(parents=True, exist_ok=True)
    roots = runtime.allowed_roots()

    def where(value):
        p = Path(value).expanduser()
        return (p if p.is_absolute() else folder / p).resolve()
    for name, flag in WRITES.items():
        value = values.get(name)
        for v in (value if isinstance(value, list) else [value]):
            if isinstance(v, str) and v and not runtime.inside(where(v), roots):
                raise ConstructError("%s %s is outside the project and the plugin's data folder; write inside the project "
                                     "(a relative path)" % (flag, v))
    # commands that write beside (or into) the scene they are given: that scene must be inside a project
    scene_arg = None
    if sub == "critique" or (sub == "compare" and values.get("record")):
        scene_arg = values.get("scene")
    elif sub == "rounds" and values.get("action") == "start" and values.get("args"):
        scene_arg = values["args"][0]
    if isinstance(scene_arg, str) and not runtime.inside(where(scene_arg), roots):
        raise ConstructError("%s writes beside the scene; copy %s into a project first (construct_start from_path)" %
                             (sub, scene_arg))
    wait = _number(args, "wait_seconds", 1, 380, integer=True) or 300
    started = time.time()
    label = "construct %s" % sub
    job_id = jobs.start("command", "cli", argv, project=project, label=label, cwd=folder,
                        finish={"folder": str(folder), "since": started, "argv": argv})
    return _waited(job_id, "command", wait, label)


def _finish_command(rec, done, tail):
    f = rec["finish"]
    folder, since = Path(f["folder"]), f["since"] - 1
    written = []
    for p in sorted(folder.rglob("*")):
        if len(written) >= 60:
            break
        try:
            if p.is_file() and p.stat().st_mtime >= since and not p.name.startswith("."):
                written.append(str(p))
        except OSError:
            continue
    shown = [p for p in written if Path(p).suffix.lower() in (".png", ".jpg", ".mp4", ".gif", ".glb", ".3mf", ".stl")][:8]
    out = {"state": jobs.outcome(done, tail), "exit": done.get("code"), "argv": f["argv"],
           "output": tail.strip()[-6000:], "files": written[:LIST_CAP],
           "note": "exit 1 is Construct's own 'has problems' (read the output); 2 means a capture was not possible"}
    slug, sub = rec.get("project"), f["argv"][0]
    if slug and done.get("code") in (0, 1):
        kit_dir = _out_arg(f["argv"], folder) if sub == "kit" else None
        if kit_dir is not None and (kit_dir / "booklet.html").is_file():
            kit = publish_kit(slug, kit_dir)
            out["kit"] = kit
            shown = [kit["file_path"]] + [p for p in shown if not p.startswith(str(kit_dir))][:4]
            out["next"] = ("put the kit's MEDIA line in your reply: Hermes Desktop shows its steps in 3D and its booklet; "
                           "the plates are the .3mf files")
        for p in written:
            suffix = Path(p).suffix.lower()
            if kit_dir is not None and p.startswith(str(kit_dir)):
                continue
            if suffix == ".mp4":
                runtime.record_item(slug, "film", p, title="film (%s)" % sub)
            elif suffix in (".glb", ".obj", ".stl", ".3mf", ".step", ".fcstd"):
                kind = "plates" if sub == "netlogo-plates" else "export"
                runtime.record_item(slug, kind, p, title="%s (%s)" % (suffix[1:].upper(), sub),
                                    summary=verify_export(Path(p), suffix[1:], tail) if kind == "export" else None)
    out["media"] = media(*shown)
    return out


def _out_arg(argv, folder):
    """The folder an argv's --out names (relative to the working folder)."""
    for i, a in enumerate(argv):
        flag, eq, val = a.partition("=")
        if flag == "--out":
            value = val if eq else (argv[i + 1] if i + 1 < len(argv) else None)
            if value:
                p = Path(value).expanduser()
                return (p if p.is_absolute() else folder / p).resolve()
    return None


IMG = re.compile(r"""(src=)(["'])(img/[A-Za-z0-9._-]{1,80}\.(svg|png))\2""")


def publish_kit(slug, kit_dir):
    """A model kit's pages put where chat and the Constructs page show them: shown/<slug>/kits/<id>/ holds its steps
    in 3D (assembly.html, a construct page), its booklet with the pictures inlined (one file a frame can show), a
    loader and a card. Returns the kit's card with its MEDIA line."""
    kit_id = runtime.new_id()
    folder = runtime.shown_root() / slug / "kits" / kit_id
    folder.mkdir(parents=True, exist_ok=True)
    budget = [24 * 1024 * 1024]

    def inline(m):
        f = (kit_dir / m.group(3)).resolve()
        if not runtime.inside(f, [kit_dir.resolve()]) or not f.is_file() or f.stat().st_size > budget[0]:
            return m.group(0)
        budget[0] -= f.stat().st_size
        mime = "image/svg+xml" if m.group(4) == "svg" else "image/png"
        return '%s%s%s%s' % (m.group(1), m.group(2), "data:%s;base64,%s" % (mime, base64.b64encode(f.read_bytes()).decode("ascii")),
                             m.group(2))
    booklet = (kit_dir / "booklet.html").read_text(encoding="utf-8")
    (folder / "booklet.html").write_text(IMG.sub(inline, booklet), encoding="utf-8")
    has3d = (kit_dir / "assembly.html").is_file()
    if has3d:
        runtime.link_or_copy(kit_dir / "assembly.html", folder / "assembly.html")
    try:
        info = json.loads((kit_dir / "kit.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    title = str(info.get("title") or slug)
    card = {"kind": "kit", "project": slug, "kit": kit_id, "title": title, "pieces": len(info.get("pieces") or []),
            "plates": len(sorted(kit_dir.glob("plate-*.3mf"))), "steps": len(info.get("steps") or []), "has_3d": has3d,
            "size_mm": info.get("size_mm"), "scale": info.get("scale"), "created": runtime.stamp_iso(),
            "folder": str(kit_dir), "booklet": str(kit_dir / "booklet.html")}
    runtime.write_loader(folder / "loader.html", title + ", a kit", "assembly.html" if has3d else "booklet.html")
    runtime.write_json(folder / "card.json", card)
    runtime.prune(folder.parent)
    runtime.record_item(slug, "kit", kit_dir / "kit.json", title="model kit: %d pieces, %d plates" % (card["pieces"], card["plates"]),
                        summary={"kit": kit_id, "pieces": card["pieces"], "plates": card["plates"], "steps": card["steps"]})
    loader = folder / "loader.html"
    return dict(card, file_path=str(loader), media_tag="MEDIA:%s" % loader, media=media(str(loader)))


jobs.register_finisher("check", _finish_check)
jobs.register_finisher("build", _finish_build)
jobs.register_finisher("review", _finish_review)
jobs.register_finisher("export", _finish_export)
jobs.register_finisher("film", _finish_film)
jobs.register_finisher("command", _finish_command)

HANDLERS = {"construct_start": start, "construct_edit": edit, "construct_check": check, "construct_inspect": inspect, "construct_build": build,
            "construct_review": review, "construct_export": export, "construct_film": film, "construct_job": job,
            "construct_command": command}
