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

OPS = ("new", "place", "move", "remove", "list", "view", "tidy", "refresh")
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
        key, title = _path_key(p)
        return key, p, maps if maps.is_file() else None, title or p.stem
    raise ConstructError("no construct %r: name one of your projects, a shipped construct (%s) or a scene's absolute "
                         "path" % (name, ", ".join(sorted(stock))))


def _path_key(path):
    """The name a scene given by path is kept under in a world, and its title: the project it belongs to (a scene in
    a checkpoint or round folder of one of the user's projects), else the scene's own id, else its folder's name."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    doc = doc if isinstance(doc, dict) else {}
    root = runtime.projects_root()
    try:
        rel = path.resolve().relative_to(root).parts
    except ValueError:
        rel = ()
    if len(rel) > 1 and runtime.SLUG.match(rel[0]) and (root / rel[0]).is_dir() and rel[1] != "constructs":
        return rel[0], doc.get("title")
    if isinstance(doc.get("id"), str) and runtime.slugify(doc["id"]) != "construct":
        return runtime.slugify(doc["id"]), doc.get("title")
    stem = path.stem[:-7] if path.stem.endswith(".params") else path.stem
    return runtime.slugify(path.parent.name if stem in ("scene", "world") else stem), doc.get("title")


SOURCE = ".source.json"   # beside each copy: what it was copied from, for refresh


def _origin(name):
    p = Path(name).expanduser()
    return str(p.resolve()) if p.is_absolute() else name.strip()


def _copy_in(dest, scene, maps):
    """A construct (or a world, whole) copied into `dest`, with its artwork and material map."""
    dest.mkdir(parents=True, exist_ok=True)
    if scene.name == "world.json":   # a world placed in a world (a building in a district): it comes whole
        shutil.copytree(scene.parent, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("builds", "exports", "review", "work", "edits", "films", "stills"))
        return
    tools._copy_scene(scene, dest / "scene.json")
    if maps is not None:
        shutil.copyfile(maps, dest / "scene.materials.json")


def _bring(folder, name):
    """Copy a construct into the world (constructs/<key>/), once per source; the placement's `construct` path. The
    key is the source's project id or the scene's own id; a different construct under a taken key gets key-2."""
    key, scene, maps, _ = _source(name)
    origin, base, n = _origin(name), key, 2
    kind = "world.json" if scene.name == "world.json" else "scene.json"
    while True:
        dest = folder / "constructs" / key
        rel = "constructs/%s/%s" % (key, kind)
        if not dest.exists():
            break
        rec = _read_source(dest)
        if (folder / rel).is_file() and (rec.get("origin") == origin if rec else key == base):
            return rel   # this construct is here already (a copy from before records were kept: by its name)
        key, n = "%s-%d" % (base, n), n + 1
    _copy_in(dest, scene, maps)
    runtime.write_json(dest / SOURCE, {"construct": name.strip(), "origin": origin, "copied": runtime.stamp_iso()})
    return rel


def _read_source(dest):
    try:
        rec = json.loads((dest / SOURCE).read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) and isinstance(rec.get("construct"), str) else None
    except (OSError, ValueError):
        return None


def _refresh(slug, folder, doc, pid=None):
    """Re-copy the placed constructs (one placement's, or all) from their sources as they are now, then check the
    world; on a failed check the copies go back as they were. Returns (refreshed, skipped, the world's check)."""
    placements = doc["placements"]
    if pid is not None:
        placements = [p for p in placements if p["id"] == pid]
        if not placements:
            raise ConstructError("no placement %r in %s (placements: %s)" % (
                pid, slug, ", ".join(p["id"] for p in doc["placements"])))
    keys = {}
    for p in placements:
        parts = p["construct"].split("/")
        if len(parts) == 3 and parts[0] == "constructs":
            keys.setdefault(parts[1], []).append(p["id"])
    refreshed, skipped, backups, res = [], [], {}, None
    stash = Path(tempfile.mkdtemp(prefix=".refresh-", dir=str(folder)))
    try:
        for key, ids in sorted(keys.items()):
            dest = folder / "constructs" / key
            rec = _read_source(dest)
            name = rec["construct"] if rec else key
            if rec is None and not (runtime.SLUG.match(key) and (runtime.projects_root() / key).is_dir()):
                skipped.append({"construct": key, "placements": ids, "why": "no source recorded (it came with the world)"})
                continue
            try:
                _, scene, maps, _ = _source(name)
            except ConstructError as exc:
                skipped.append({"construct": key, "placements": ids, "why": str(exc)})
                continue
            kind = "world.json" if scene.name == "world.json" else "scene.json"
            before = (dest / kind).read_bytes() if (dest / kind).is_file() else None
            shutil.move(str(dest), str(stash / key))
            backups[key] = dest
            _copy_in(dest, scene, maps)
            runtime.write_json(dest / SOURCE, {"construct": name, "origin": _origin(name), "copied": runtime.stamp_iso()})
            refreshed.append({"construct": key, "placements": ids, "from": name,
                              "changed": before != (dest / kind).read_bytes()})
        if backups:
            res = check(doc, folder)
            if res.get("errors"):
                raise ConstructError("refreshed, the world would not be valid (the copies are back as they were):\n" +
                                     "\n".join(res["errors"]))
    except Exception:
        for key, dest in backups.items():
            shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(stash / key), str(dest))
        raise
    finally:
        shutil.rmtree(stash, ignore_errors=True)
    return refreshed, skipped, res


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
    slug = runtime.project_id(slug)
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    if op == "refresh":   # the constructs improved since they were placed, copied in again
        pid = args.get("id")
        if pid is not None and not isinstance(pid, str):
            raise ConstructError("id is one placement's id (leave it out to refresh every placed construct)")
        refreshed, skipped, checked = _refresh(slug, folder, doc, pid)
        if not any(r["changed"] for r in refreshed):
            return {"world": slug, "refreshed": refreshed, "skipped": skipped,
                    "next": "nothing changed since they were placed: the world is as it was (not rebuilt)"}
        with open(_edits(folder), "a", encoding="utf-8") as fh:  # no before-file: undo leaves a refresh alone
            fh.write(json.dumps({"id": runtime.new_id(), "op": "refresh", "by": "agent", "placement": pid or "",
                                 "constructs": [r["construct"] for r in refreshed if r["changed"]]}) + "\n")
        res = _rebuild(slug, folder, path, args.get("wait_seconds"))
        if isinstance(res, dict):
            res.update(world=_summary(checked), refreshed=refreshed, skipped=skipped)
        return res
    if op == "list":
        got = check(doc, folder, args.get("id"))
        if got.get("errors"):
            return {"world": slug, "title": doc["title"], "errors": got["errors"]}
        res = {"world": slug, "title": doc["title"], **_summary(got)}
        if args.get("id"):
            res["surfaces"] = got.get("surfaces", [])
        return res
    pid = args.get("id")
    if op == "tidy":   # the scratch work of a world archived: kept, off the Constructs page
        names = args.get("projects")
        if not isinstance(names, list) or not names or len(names) > 200 or not all(isinstance(n, str) and NAME.match(n) for n in names):
            raise ConstructError("projects is a list of project ids to archive")
        done = []
        for n in names:
            pf = runtime.projects_root() / n
            if n == slug or not (pf / "project.json").is_file():
                continue
            info = json.loads((pf / "project.json").read_text(encoding="utf-8"))
            info["archived"], info["for_world"] = True, info.get("for_world") or doc["title"]
            runtime.write_json(pf / "project.json", info)
            done.append(n)
        return {"world": slug, "archived": done, "next": "the Constructs page keeps them under Archived"}
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


def _edits(folder):
    (folder / "edits").mkdir(exist_ok=True)
    return folder / "edits" / "log.jsonl"


def _log(folder, before, entry):
    """Keep the world as it was (edits/<id>-before.json) and say what changed (edits/log.jsonl): every change undoes."""
    _edits(folder)
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


def remove_by_hand(slug, pid):
    """A placement taken out of a world by the user (the card's Remove); what stood on it goes too only if the user
    asks again for each: it is refused while anything stands on it."""
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    idx = next((i for i, p in enumerate(doc["placements"]) if p["id"] == pid), None)
    if idx is None:
        raise ConstructError("no placement %r in %s" % (pid, slug))
    if idx == 0:
        raise ConstructError("%s holds the others; it stays" % pid)
    on_it = [p["id"] for p in doc["placements"] if p.get("on", "").split("/")[0] == pid]
    if on_it:
        raise ConstructError("%s carries %s; take those off first" % (pid, ", ".join(on_it)))
    before = json.loads(path.read_text(encoding="utf-8"))
    doc["placements"].pop(idx)
    checked = _save_checked(path, doc, folder)
    stamp = _log(folder, before, {"op": "remove", "by": "user", "placement": pid})
    build, job_id = _rebuild_later(slug, folder, path)
    return dict(_summary(checked), world=slug, removed=pid, build=build, job_id=job_id, undo="edits/%s-before.json" % stamp)


def duplicate_by_hand(slug, pid):
    """Another of a placement's construct, set down beside it (the card's Duplicate), facing the same way."""
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    src = next((p for p in doc["placements"] if p["id"] == pid), None)
    if src is None or "sky" in src:
        raise ConstructError("no placement %r to duplicate in %s" % (pid, slug))
    res = check(doc, folder)
    row = next(r for r in res["placements"] if r["id"] == pid)
    width = (row.get("size_m") or [1, 1, 1])[0]
    base, n = re.sub(r"-\d+$", "", pid), 2
    new_id = "%s-%d" % (base, n)
    while any(p["id"] == new_id for p in doc["placements"]):
        n += 1
        new_id = "%s-%d" % (base, n)
    twin = json.loads(json.dumps(src))
    twin["id"] = new_id
    twin.pop("note", None)
    at = list(twin.get("at") or [0.0, 0.0, 0.0])
    at[0] = round(at[0] + width + 0.4, 3)
    twin["at"] = at
    doc["placements"].append(twin)
    before = json.loads(path.read_text(encoding="utf-8"))
    checked = check(doc, folder, settle=[new_id])
    if checked.get("errors"):
        raise ConstructError("the world would not be valid:\n" + "\n".join(checked["errors"]))
    doc = checked.pop("doc", doc)
    checked.pop("moved", None)
    runtime.write_json(path, doc)
    stamp = _log(folder, before, {"op": "duplicate", "by": "user", "placement": new_id, "args": {"of": pid}})
    build, job_id = _rebuild_later(slug, folder, path)
    return dict(_summary(checked), world=slug, placed=new_id, build=build, job_id=job_id, undo="edits/%s-before.json" % stamp)


def still(slug, build, camera):
    """A picture of a project's build from the given camera: <project>/stills/<id>.png, listed with its files."""
    if not re.match(r"^\d{8}-\d{6}-[0-9a-f]{4}$", str(build)):
        raise ConstructError("which build? (its id)")
    folder = runtime.project_dir(slug)
    page = runtime.shown_root() / slug / build / "construct.html"
    if not page.is_file():
        raise ConstructError("no build %s of %s" % (build, slug))
    cam = {k: camera.get(k) for k in ("target", "yaw", "pitch", "dist", "focus") if isinstance(camera, dict) and k in camera}
    if cam and not (isinstance(cam.get("target"), list) and len(cam["target"]) == 3 and all(isinstance(v, (int, float)) for v in cam["target"])):
        raise ConstructError("the camera is {target: [x, y, z], yaw, pitch, dist}")
    out = folder / "stills" / ("%s.png" % runtime.new_id())
    out.parent.mkdir(parents=True, exist_ok=True)
    spec = Path(tempfile.mkstemp(prefix=".still-", suffix=".json", dir=str(folder))[1])
    try:
        runtime.write_json(spec, {"page": str(page), "camera": cam, "out": str(out),
                                  "mode": camera.get("mode") if isinstance(camera, dict) else None,
                                  "solid": bool(camera.get("solid")) if isinstance(camera, dict) else False})
        code, _, err = runtime.run_child("still", str(spec), timeout=180, cwd=folder)
    finally:
        spec.unlink(missing_ok=True)
    if code != 0 or not out.is_file():
        raise ConstructError("the picture could not be made: %s" % ((err or "").strip().splitlines() or ["no browser"])[-1])
    runtime.record_item(slug, "file", out, title="Picture")
    return str(out)


def save_view(slug, name, camera):
    """The camera where someone left it, kept as a named view of the world (a button for the next visit, a shot)."""
    label = str(name).replace("-", " ").replace("_", " ").strip()[:48] or "View"
    vid = runtime.slugify(label)[:40] or "view"
    if not isinstance(camera, dict) or not (isinstance(camera.get("target"), list) and len(camera["target"]) == 3):
        raise ConstructError("the camera is {target: [x, y, z], yaw, pitch, dist}")
    args = {"op": "view", "world": slug, "id": vid, "label": label.capitalize()}
    folder = runtime.project_dir(slug)
    path, doc = _load(folder)
    pr = doc.setdefault("presentation", {})
    views = [v for v in pr.get("views", []) if v.get("id") != vid]
    views.append({"id": vid, "label": label.capitalize(), "target": [round(float(x), 3) for x in camera["target"]],
                  "yaw": round(float(camera.get("yaw", 0)) % 360, 2), "pitch": max(-89, min(89, round(float(camera.get("pitch", 15)), 2))),
                  "distance_m": max(0.05, round(float(camera.get("dist", 10)), 3))})
    pr["views"] = views
    before = json.loads(path.read_text(encoding="utf-8"))
    _save_checked(path, doc, folder)
    _log(folder, before, {"op": "view", "by": "user", "placement": vid, "args": {"camera": True}})
    build, job_id = _rebuild_later(slug, folder, path)
    return {"world": slug, "view": vid, "build": build, "job_id": job_id}


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
