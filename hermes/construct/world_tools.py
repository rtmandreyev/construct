"""construct_world: whole constructs placed together in one world, from the chat.

A world is a project of its own: world.json (the placements) and constructs/<name>/ (a copy of each construct it
places, so the world travels whole and a change to the original never moves it by surprise). Every change is
checked (construct_hologram/world.py), rebuilt and shown live in the chat, like a construct.
"""

import json
import re
import shutil
import tempfile
from pathlib import Path

from . import runtime, tools
from .runtime import ConstructError

OPS = ("new", "place", "move", "remove", "list", "view")
MAX_BATCH = 64
VIEW_KEYS = ("label", "target", "yaw", "pitch", "distance")
NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


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


def check(doc, folder, surfaces_of=None, arrange=None, settle=None):
    """The world checked by Construct (construct_hologram/world.py, in a child like every engine call): its
    placements as they stand, its audit and, for `surfaces_of`, where things can stand on that placement. With
    `arrange` (moves and turns made by hand on the page), the world after them: its document comes back as `doc`."""
    spec = Path(tempfile.mkstemp(prefix=".world-check-", suffix=".json", dir=str(folder))[1])
    try:
        body = {"doc": doc, "folder": str(folder), "surfaces_of": surfaces_of}
        if arrange is not None:
            body["arrange"] = arrange
        if settle:
            body["settle"] = list(settle)
        runtime.write_json(spec, body)
        code, out, err = runtime.run_child("world", str(spec), timeout=180, cwd=folder)
    finally:
        spec.unlink(missing_ok=True)
    if code != 0:
        raise ConstructError("Construct could not check the world: %s" % (err.strip().splitlines() or ["no answer"])[-1])
    try:
        return json.loads(out)
    except ValueError:
        raise ConstructError("Construct's check of the world was not readable")


def _save_checked(path, doc, folder, surfaces_of=None):
    """Check (a placement that cannot stand where it was put is refused) and write; the check's summary."""
    res = check(doc, folder, surfaces_of)
    if res.get("errors"):
        raise ConstructError("the world would not be valid:\n" + "\n".join(res["errors"]))
    runtime.write_json(path, doc)
    return res


def _summary(res):
    return {k: res[k] for k in ("placements", "counts", "warnings", "notes") if k in res}


def _rebuild(slug, folder, path, wait=None):
    build_id = runtime.new_id()
    out = folder / "builds" / build_id
    spec = {"scene": str(path), "out": str(out), "thumb": True, "asset_root": str(folder)}
    from . import jobs
    job_id = jobs.start("build", "build", project=slug, label="build of world %s" % slug, cwd=folder, spec=spec,
                        finish={"slug": slug, "build": build_id, "out": str(out), "scene": str(path)})
    return tools._waited(job_id, "build", wait or tools.WAIT["build"], "build of world %s" % slug)


def _from_example(args, later=False):
    """A world that ships with the plugin, as the user's own project: its gallery constructs brought in by name (the
    plugin's own, or fetched from the gallery once), the constructs designed for it copied along."""
    shipped = runtime.example_worlds()
    name = args.get("example")
    if name not in shipped:
        raise ConstructError("no example world %r; examples: %s" % (name, ", ".join(sorted(shipped)) or "none"))
    src = shipped[name]["folder"]
    doc = json.loads((src / "world.json").read_text(encoding="utf-8"))
    title = args.get("title") if isinstance(args.get("title"), str) and args["title"].strip() else doc["title"]
    slug, folder = runtime.new_project(title)
    try:
        if (src / "constructs").is_dir():
            shutil.copytree(src / "constructs", folder / "constructs", dirs_exist_ok=True)
        for p in doc["placements"]:
            if not p["construct"].endswith(".json"):
                p["construct"] = _bring(folder, p["construct"])
        doc["id"], doc["title"] = slug.replace("_", "-")[:64], title.strip()
        path = folder / "world.json"
        checked = _save_checked(path, doc, folder, surfaces_of=doc["placements"][0]["id"])
        runtime.write_json(folder / "project.json", {"slug": slug, "title": title.strip(), "scene": "world.json",
                                                     "origin": "world", "from": "example:%s" % name,
                                                     "created": runtime.stamp_iso()})
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    if later:   # opened from the Worlds page: the page follows the build itself
        build, job_id = _rebuild_later(slug, folder, path)
        return {"project": slug, "title": title.strip(), "build": build, "job_id": job_id}
    res = _rebuild(slug, folder, path, args.get("wait_seconds"))
    if isinstance(res, dict):
        res["world"] = _summary(checked)
        res["surfaces"] = checked.get("surfaces", [])
        res["next"] = "it is the user's own now: place, move or remove with the other ops; put the MEDIA line in your reply"
    return res


@tools.tool("construct_world")
def world(args):
    op = tools._choice(args, "op", OPS)
    if op is None:
        raise ConstructError("op is one of %s" % ", ".join(OPS))
    if op == "new" and args.get("example") is not None:
        return _from_example(args)
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
            checked = _save_checked(path, doc, folder, surfaces_of=pid)
            runtime.write_json(folder / "project.json", {"slug": slug, "title": title.strip(), "scene": "world.json",
                                                         "origin": "world", "created": runtime.stamp_iso()})
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        res = _rebuild(slug, folder, path, args.get("wait_seconds"))
        if isinstance(res, dict):
            res["world"] = _summary(checked)
            res["surfaces"] = checked.get("surfaces", [])
            res["next"] = ("place constructs with op place (on one of `surfaces` to stand on it); put the MEDIA line in "
                           "your reply")
        return res
    slug = args.get("world")
    if not isinstance(slug, str):
        raise ConstructError("world must be the world's project id (from op new)")
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    if op == "list":
        got = check(doc, folder, args.get("id"))
        if got.get("errors"):
            return {"world": slug, "title": doc["title"], "errors": got["errors"]}
        res = {"world": slug, "title": doc["title"], **_summary(got)}
        if args.get("id"):
            res["surfaces"] = got.get("surfaces", [])
        return res
    pid = args.get("id")
    if op == "place":
        many = args.get("placements")
        if many is not None:   # several at once, checked together, one rebuild
            if not isinstance(many, list) or not 0 < len(many) <= MAX_BATCH or not all(isinstance(x, dict) for x in many):
                raise ConstructError("placements is a list of 1..%d placements, each {construct, id?, on?, at?, ...}"
                                     % MAX_BATCH)
        else:
            many = [args]
        added = []
        for one in many:
            name = one.get("construct")
            rel = _bring(folder, name)
            pid = one.get("id") or runtime.slugify(_source(name)[0])[:40]
            base, n = pid, 2
            while any(p["id"] == pid for p in doc["placements"]):
                pid, n = "%s-%d" % (base, n), n + 1
            doc["placements"].append(_placement_fields(one, {"id": pid, "construct": rel}))
            added.append(pid)
        pid = ", ".join(added)
    elif op == "view":   # a named view of the world: a room, a group, one placement; shown as a button on the page
        vid = args.get("id")
        if not isinstance(vid, str) or not NAME.match(vid):
            raise ConstructError("a view needs an id (lowercase letters, digits, - _ .)")
        pr = doc.setdefault("presentation", {})
        views = [v for v in pr.get("views", []) if v.get("id") != vid]
        if not tools._bool(args, "remove"):
            v = {"id": vid}
            for k in VIEW_KEYS:
                if args.get(k) is not None:
                    v[k] = args[k]
            views.append(v)
        pr["views"] = views
        if not views:
            pr.pop("views")
        if not pr:
            doc.pop("presentation")
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
    checked = _save_checked(path, doc, folder)
    stamp = _log(folder, before, {"op": op, "by": "agent", "placement": pid,
                                  "args": {k: v for k, v in args.items() if k not in ("world", "op")}})
    res = _rebuild(slug, folder, path, args.get("wait_seconds"))
    if isinstance(res, dict):
        res["world"] = _summary(checked)
        res["undo"] = "edits/%s-before.json" % stamp
    return res


def _log(folder, before, entry):
    """Keep the world as it was (edits/<id>-before.json) and say what changed (edits/log.jsonl): every change undoes."""
    (folder / "edits").mkdir(exist_ok=True)
    stamp = runtime.new_id()
    runtime.write_json(folder / "edits" / ("%s-before.json" % stamp), before)
    with open(folder / "edits" / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict({"id": stamp}, **entry)) + "\n")
    return stamp


def _rebuild_later(slug, folder, path):
    """Rebuild without waiting. The page that asked follows the job with /construct job <id>, which publishes the
    build (to the chat card and the Constructs page) once it has ended; no thread outlives the call."""
    build_id = runtime.new_id()
    out = folder / "builds" / build_id
    spec = {"scene": str(path), "out": str(out), "thumb": True, "asset_root": str(folder)}
    from . import jobs
    job_id = jobs.start("build", "build", project=slug, label="build of %s" % slug, cwd=folder, spec=spec,
                        finish={"slug": slug, "build": build_id, "out": str(out), "scene": str(path)})
    return build_id, job_id


def arrange_by_hand(slug, changes):
    """The user's own moves and turns, made on the world's page (its arrange mode) and sent by the Desktop half
    through /construct arrange: checked like any change, written, logged as the user's, and rebuilt."""
    if not isinstance(slug, str) or not NAME.match(slug):
        raise ConstructError("which world? /construct arrange <world> <changes>")
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    res = check(doc, folder, arrange=changes)
    if res.get("errors"):
        raise ConstructError("the world would not be valid:\n" + "\n".join(res["errors"]))
    new, moved = res.pop("doc"), res.pop("moved")
    before = json.loads(path.read_text(encoding="utf-8"))
    runtime.write_json(path, new)
    stamp = _log(folder, before, {"op": "arrange", "by": "user", "placement": ", ".join(moved), "changes": changes})
    build, job_id = _rebuild_later(slug, folder, path)
    return dict(_summary(res), world=slug, moved=moved, build=build, job_id=job_id, undo="edits/%s-before.json" % stamp)


def open_example(name):
    """A shipped world as the user's own project, opened from the Worlds page with no model turn; rebuilt later."""
    if not isinstance(name, str) or not NAME.match(name):
        raise ConstructError("which world? /construct open-world <example>")
    return _from_example({"example": name}, later=True)


def place_by_hand(slug, name):
    """A construct put into a world by the user (the card's Add a construct): it stands on the world's first
    placement, in its middle, to be dragged where it belongs; checked, saved, logged as the user's and rebuilt."""
    if not isinstance(slug, str) or not NAME.match(slug):
        raise ConstructError("which world? /construct place <world> <construct>")
    if not isinstance(name, str) or not name or len(name) > 200:
        raise ConstructError("which construct? your project, a shipped construct or a gallery name")
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    rel = _bring(folder, name)
    base = runtime.slugify(_source(name)[0])[:40] or "construct"
    pid, n = base, 2
    while any(p["id"] == pid for p in doc["placements"]):
        pid, n = "%s-%d" % (base, n), n + 1
    one = {"id": pid, "construct": rel}
    if doc["placements"]:
        one["on"] = doc["placements"][0]["id"]
    doc["placements"].append(one)
    before = json.loads(path.read_text(encoding="utf-8"))
    checked = check(doc, folder, settle=[pid])   # it lands on what is under it: a floor, the paving
    if checked.get("errors"):
        raise ConstructError("the world would not be valid:\n" + "\n".join(checked["errors"]))
    doc = checked.pop("doc", doc)
    checked.pop("moved", None)
    runtime.write_json(path, doc)
    stamp = _log(folder, before, {"op": "place", "by": "user", "placement": pid, "args": {"construct": name}})
    build, job_id = _rebuild_later(slug, folder, path)
    return dict(_summary(checked), world=slug, placed=pid, build=build, job_id=job_id, undo="edits/%s-before.json" % stamp)


def undo(slug):
    """The world as it was before its last change (by the agent or by hand), rebuilt."""
    if not isinstance(slug, str) or not NAME.match(slug):
        raise ConstructError("which world? /construct undo <world>")
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    log = folder / "edits" / "log.jsonl"
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] if log.is_file() else []
    undone = {r.get("undoes") for r in rows if r.get("op") == "undo"}
    last = next((r for r in reversed(rows) if r.get("op") != "undo" and r["id"] not in undone
                 and (folder / "edits" / ("%s-before.json" % r["id"])).is_file()), None)
    if last is None:
        raise ConstructError("nothing to undo in %s" % slug)
    prior = json.loads((folder / "edits" / ("%s-before.json" % last["id"])).read_text(encoding="utf-8"))
    res = check(prior, folder)
    if res.get("errors"):
        raise ConstructError("the earlier world no longer checks:\n" + "\n".join(res["errors"]))
    runtime.write_json(path, prior)
    _log(folder, doc, {"op": "undo", "by": "user", "undoes": last["id"], "placement": last.get("placement", "")})
    build, job_id = _rebuild_later(slug, folder, path)
    return dict(_summary(res), world=slug, undid=last.get("op"), placement=last.get("placement", ""), build=build,
                job_id=job_id)


HANDLERS = {"construct_world": world}
