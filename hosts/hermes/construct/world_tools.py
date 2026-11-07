"""construct_world: whole constructs placed together in one world, from the chat.

A world is a project of its own: world.json (the placements) and constructs/<name>/ (a copy of each construct it
places, so the world travels whole and a change to the original never moves it by surprise). Every change is
checked (construct_hologram/world.py), rebuilt and shown live in the chat, like a construct.
"""

import json
import re
import shutil
from pathlib import Path

from . import runtime, tools
from .runtime import ConstructError

OPS = ("new", "place", "move", "remove", "list")
NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


def _world_mod():
    from construct_hologram import world
    return world


def _load(folder):
    path = folder / "world.json"
    if not path.is_file():
        raise ConstructError("project %s is not a world (no world.json); start one with op new" % folder.name)
    return path, json.loads(path.read_text(encoding="utf-8"))


def _source(name):
    """A construct to place: the user's own project, a construct the plugin ships, or a scene by absolute path.
    Returns (key, scene path, material map or None, title)."""
    if not isinstance(name, str) or not name.strip():
        raise ConstructError("construct must be a project id, a shipped construct's name or a scene's path")
    root = runtime.projects_root()
    if runtime.SLUG.match(name) and (root / name).is_dir():   # the user's own construct (or world) first
        folder = root / name
        info = runtime.read_project(folder)
        scene = Path(info.get("scene") or "scene.json")
        scene = scene if scene.is_absolute() else folder / scene
        if (folder / "world.json").is_file():
            scene = folder / "world.json"
        if not scene.is_file():
            raise ConstructError("project %s has no scene yet" % name)
        maps = scene.with_name(re.sub(r"(\.params)?\.json$", "", scene.name) + ".materials.json")
        return name, scene, maps if maps.is_file() else None, info.get("title") or name
    stock = runtime.examples()
    if name in stock:
        f = stock[name]
        return name, f["scene"], f.get("materials"), name
    if name in runtime.gallery():   # any construct in the gallery, fetched once
        f = runtime.gallery_files(name)
        return name, f["scene"], f.get("materials"), runtime.gallery()[name].get("title", name)
    p = Path(name).expanduser()
    if p.is_absolute() and p.is_file():
        maps = p.with_name(re.sub(r"(\.params)?\.json$", "", p.name) + ".materials.json")
        return runtime.slugify(p.parent.name if p.stem in ("scene", "world") else p.stem), p, \
            maps if maps.is_file() else None, p.stem
    raise ConstructError("no construct %r: name one of your projects, a shipped construct (%s) or a scene's absolute "
                         "path" % (name, ", ".join(sorted(stock))))


def _bring(folder, name):
    """Copy a construct into the world (constructs/<key>/), once; the placement's `construct` path."""
    key, scene, maps, _ = _source(name)
    dest = folder / "constructs" / key
    rel = "constructs/%s/%s" % (key, "world.json" if scene.name == "world.json" else "scene.json")
    if (folder / rel).is_file():
        return rel
    dest.mkdir(parents=True, exist_ok=True)
    if scene.name == "world.json":   # a world placed in a world (a building in a district): it comes whole
        shutil.copytree(scene.parent, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("builds", "exports", "review", "work", "edits", "films"))
        return rel
    tools._copy_scene(scene, dest / "scene.json")
    if maps is not None:
        shutil.copyfile(maps, dest / "scene.materials.json")
    return rel


def _vec(args, key):
    v = args.get(key)
    if v is None:
        return None
    if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        raise ConstructError("%s must be [x, y, z] in metres" % key)
    return [float(x) for x in v]


def _placement_fields(args, p):
    for key in ("at", "rotate"):
        v = _vec(args, key)
        if v is not None:
            p[key] = v
    for key in ("yaw", "scale"):
        v = args.get(key)
        if v is not None:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ConstructError("%s must be a number" % key)
            p[key] = float(v)
    for key in ("on", "note", "label"):
        v = args.get(key)
        if v is not None:
            if not isinstance(v, str):
                raise ConstructError("%s must be text" % key)
            if v == "" and key == "on":
                p.pop("on", None)
            else:
                p[key] = v
    if args.get("floating") is not None:
        p["floating"] = tools._bool(args, "floating")
    if args.get("sky") is not None:
        if not isinstance(args["sky"], dict):
            raise ConstructError("sky must be {diameter_m, distance_m, azimuth?, elevation?}")
        p["sky"] = args["sky"]
        p.pop("at", None)
        p.pop("scale", None)
        p.pop("on", None)
    return p


def _save_checked(path, doc, folder):
    """Validate, compile (to catch a placement that cannot stand where it was put) and write."""
    w = _world_mod()
    errs = w.validate(doc)
    if errs:
        raise ConstructError("the world would not be valid:\n" + "\n".join(errs[:12]))
    try:
        w.compile_world(doc, folder, None)
    except w.WorldError as exc:
        raise ConstructError(str(exc))
    runtime.write_json(path, doc)


def _summary(doc, folder):
    w = _world_mod()
    try:
        g = w.compile_world(doc, folder, None)
    except w.WorldError as exc:
        return {"error": str(exc)}
    report = w.audit(doc, g)
    rows = []
    for r in g["world"]["placements"]:
        row = {"id": r["id"], "title": r["title"], "at": r["at"], "yaw": r["yaw"]}
        for k in ("on", "scale", "floating", "note", "angular_deg"):
            if k in r and not (k == "scale" and abs(r["scale"] - 1) < 1e-9):
                row[k] = r[k]
        box = _box(g, r["id"])
        if box:
            row["size_m"] = [round(box[1][k] - box[0][k], 3) for k in range(3)]
            row["bottom_y"] = round(box[0][1], 3)
        rows.append(row)
    return {"placements": rows, "counts": dict(report["counts"]),
            "warnings": [x["message"] for x in report["warnings"]][:20], "notes": report["info"]["notes"][:10]}


def _box(g, pid):
    lo, hi = None, None
    for p in g["parts"]:
        if p.get("placement") != pid:
            continue
        for b in p["instances"]:
            lo = list(b["min"]) if lo is None else [min(lo[k], b["min"][k]) for k in range(3)]
            hi = list(b["max"]) if hi is None else [max(hi[k], b["max"][k]) for k in range(3)]
    return (lo, hi) if lo else None


def surfaces(doc, folder, pid, n=24):
    """Where things can stand on a placement: its parts with the widest flat tops (floors, decks, tables)."""
    w = _world_mod()
    g = w.compile_world(doc, folder, None)
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


def _rebuild(slug, folder, path, wait=None):
    build_id = runtime.new_id()
    out = folder / "builds" / build_id
    spec = {"scene": str(path), "out": str(out), "thumb": True, "asset_root": str(folder)}
    from . import jobs
    job_id = jobs.start("build", "build", project=slug, label="build of world %s" % slug, cwd=folder, spec=spec,
                        finish={"slug": slug, "build": build_id, "out": str(out), "scene": str(path)})
    return tools._waited(job_id, "build", wait or tools.WAIT["build"], "build of world %s" % slug)


@tools.tool("construct_world")
def world(args):
    op = tools._choice(args, "op", OPS)
    if op is None:
        raise ConstructError("op is one of %s" % ", ".join(OPS))
    if op == "new":
        title = args.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ConstructError("a new world needs a title (at most 120 characters)")
        slug, folder = runtime.new_project(title)
        try:
            doc = {"format": "construct-world", "version": 1, "id": slug.replace("_", "-"), "title": title.strip(),
                   "placements": []}
            if args.get("summary"):
                doc["summary"] = str(args["summary"])[:400]
            host = args.get("construct")
            if host is None:
                raise ConstructError("a new world starts from a construct to hold the rest (construct: your project, a "
                                     "shipped construct, or a path): a house, a street, a plinth")
            pid = args.get("id") or runtime.slugify(_source(host)[0])[:40]
            p = _placement_fields(args, {"id": pid, "construct": _bring(folder, host)})
            doc["placements"].append(p)
            path = folder / "world.json"
            _save_checked(path, doc, folder)
            runtime.write_json(folder / "project.json", {"slug": slug, "title": title.strip(), "scene": "world.json",
                                                         "origin": "world", "created": runtime.stamp_iso()})
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        res = _rebuild(slug, folder, path, args.get("wait_seconds"))
        if isinstance(res, dict):
            res["world"] = _summary(doc, folder)
            res["surfaces"] = surfaces(doc, folder, pid)
            res["next"] = ("place constructs with op place (on one of `surfaces` to stand on it); put the MEDIA line in "
                           "your reply")
        return res
    slug = args.get("world")
    if not isinstance(slug, str):
        raise ConstructError("world must be the world's project id (from op new)")
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    if op == "list":
        res = {"world": slug, "title": doc["title"], **_summary(doc, folder)}
        if args.get("id"):
            res["surfaces"] = surfaces(doc, folder, args["id"])
        return res
    pid = args.get("id")
    if op == "place":
        name = args.get("construct")
        rel = _bring(folder, name)
        pid = pid or runtime.slugify(_source(name)[0])[:40]
        base, n = pid, 2
        while any(p["id"] == pid for p in doc["placements"]):
            pid, n = "%s-%d" % (base, n), n + 1
        doc["placements"].append(_placement_fields(args, {"id": pid, "construct": rel}))
    elif op in ("move", "remove"):
        idx = next((i for i, p in enumerate(doc["placements"]) if p["id"] == pid), None)
        if idx is None:
            raise ConstructError("no placement %r in %s (placements: %s)" % (
                pid, slug, ", ".join(p["id"] for p in doc["placements"])))
        if op == "remove":
            if idx == 0 and len(doc["placements"]) > 1:
                raise ConstructError("%s holds the others; remove them first or start a new world" % pid)
            if any(p.get("on", "").split("/")[0] == pid for p in doc["placements"]):
                raise ConstructError("other placements stand on %s; move them first" % pid)
            doc["placements"].pop(idx)
        else:
            _placement_fields(args, doc["placements"][idx])
    before = json.loads(path.read_text(encoding="utf-8"))
    _save_checked(path, doc, folder)
    (folder / "edits").mkdir(exist_ok=True)
    stamp = runtime.new_id()
    runtime.write_json(folder / "edits" / ("%s-before.json" % stamp), before)
    with open(folder / "edits" / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": stamp, "op": op, "placement": pid, "args": {k: v for k, v in args.items()
                                                                             if k not in ("world", "op")}}) + "\n")
    res = _rebuild(slug, folder, path, args.get("wait_seconds"))
    if isinstance(res, dict):
        res["world"] = _summary(doc, folder)
        res["undo"] = "edits/%s-before.json" % stamp
    return res


HANDLERS = {"construct_world": world}
