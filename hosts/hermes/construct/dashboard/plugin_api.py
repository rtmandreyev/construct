"""The Desktop half's backend: the constructs, their files, the shipped examples and the tutorials.

Routes (mounted at /api/plugins/construct/):
    GET /projects                        the Constructs page: each project with its builds, kits and files, newest first
    GET /view?project=&build=            one build: its page (the full HTML), its loader and its card
    GET /thumb?project=&build=           its small still, as a data URL
    GET /kit?project=&kit=&page=         a model kit's page (assembly: its steps in 3D; booklet), its loader and card
    GET /item?project=&item=             a file a project made (an export, a film), as a data URL, with its summary
    GET /examples                        the constructs the plugin ships to start from
    GET /example-thumb?name=             one's still, as a data URL
    GET /tutorials                       the Learn page's tutorials (skills/construct/tutorials/*.md)

Built pages are read from <data>/shown/<project>/, by ids that must match their patterns. A project's files are found
through the index the plugin's tools write (shown/<project>/items.json), by item id, and only when the file lies in
that project's folder and is of a kind the page shows; a path is never taken from a request. Nothing here writes.
"""

import base64
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
BUILD = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
PAGE_MAX = 64 * 1024 * 1024
THUMB_MAX = 2 * 1024 * 1024
ITEM_MAX = 48 * 1024 * 1024
LIST_MAX = 200
ITEM_TYPES = {".glb": "model/gltf-binary", ".obj": "text/plain", ".stl": "model/stl", ".3mf": "model/3mf",
              ".step": "model/step", ".stp": "model/step", ".fcstd": "application/zip", ".mp4": "video/mp4",
              ".jsonl": "application/json", ".json": "application/json", ".csv": "text/csv"}
CARD_KEYS = ("title", "parts", "counts", "size_m", "audit_ok", "created", "page", "has_thumb", "kind", "preview", "job_id",
             "ticks", "source")


class NotFound(Exception):
    pass


def data_dir():
    from plugins.plugin_storage import plugin_data_dir   # follows the profile the request acts for
    return Path(plugin_data_dir("construct"))


def _project_folder(root, project):
    if not isinstance(project, str) or not SLUG.match(project):
        raise NotFound("no such project")
    shown = (Path(root) / "shown").resolve()
    folder = (shown / project).resolve()
    if folder.parent != shown or not folder.is_dir():
        raise NotFound("no such project")
    return folder


def _child(folder, name):
    if not isinstance(name, str) or not BUILD.match(name):
        raise NotFound("no such build")
    target = (folder / name).resolve()
    if target.parent != folder.resolve() or not target.is_dir():
        raise NotFound("no such build")
    return target


def build_dir(root, project, build=None):
    """The shown folder of one build (the newest when `build` is None), checked to lie inside <root>/shown."""
    folder = _project_folder(root, project)
    if build is None:
        builds = sorted(p.name for p in folder.iterdir() if p.is_dir() and BUILD.match(p.name))
        if not builds:
            raise NotFound("no build yet")
        build = builds[-1]
    return _child(folder, build)


def _read_json(path, default):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return value if isinstance(value, type(default)) else default


def _card(folder):
    raw = _read_json(folder / "card.json", {})
    card = {k: raw.get(k) for k in CARD_KEYS}
    card.update(project=folder.parent.name, build=folder.name)
    card["changed_since"] = _changed(raw)
    return card


def _changed(raw):
    """Whether the scene changed after this build (its size or time differs from what the build recorded)."""
    scene, mtime = raw.get("scene"), raw.get("scene_mtime_ns")
    if not isinstance(scene, str) or not isinstance(mtime, int):
        return None
    try:
        st = Path(scene).stat()
    except OSError:
        return None
    return st.st_mtime_ns != mtime or st.st_size != raw.get("scene_bytes")


def _kit_card(folder):
    raw = _read_json(folder / "card.json", {})
    card = {k: raw.get(k) for k in ("title", "pieces", "plates", "steps", "has_3d", "size_mm", "scale", "created", "folder",
                                    "booklet")}
    card.update(project=folder.parent.parent.name, kit=folder.name, kind="kit")
    return card


def _items(folder):
    out = []
    for i in reversed(_read_json(folder / "items.json", [])):
        if not isinstance(i, dict) or not BUILD.match(str(i.get("id", ""))):
            continue
        row = {k: i.get(k) for k in ("id", "kind", "name", "title", "created", "bytes", "path")}
        summary = i.get("summary") if isinstance(i.get("summary"), dict) else {}
        row["summary"] = summary.get("summary") if isinstance(summary.get("summary"), str) else ""
        row["exists"] = isinstance(i.get("path"), str) and Path(i["path"]).is_file()
        out.append(row)
    return out


def project(root, name):
    """One project as the Constructs page shows it: its builds (newest first; a run's previews only until its final
    one), its kits, its files, and whether the scene changed since the newest build."""
    folder = _project_folder(root, name)
    builds = [_card(b) for b in sorted((p for p in folder.iterdir() if p.is_dir() and BUILD.match(p.name)),
                                       key=lambda p: p.name, reverse=True)]
    final_jobs = {b.get("job_id") for b in builds if not b.get("preview")}
    builds = [b for b in builds if not (b.get("preview") and b.get("job_id") in final_jobs)]
    kits_dir = folder / "kits"
    kits = [_kit_card(k) for k in sorted((p for p in kits_dir.iterdir() if p.is_dir() and BUILD.match(p.name)),
                                         key=lambda p: p.name, reverse=True)] if kits_dir.is_dir() else []
    items = _items(folder)
    if not builds and not kits and not items:
        raise NotFound("nothing made yet")
    newest = builds[0] if builds else None
    stamps = [x.get("created") for x in builds + kits + items if x.get("created")]
    return {"project": name, "title": (newest or {}).get("title") or (kits[0]["title"] if kits else name),
            "created": min(stamps) if stamps else None, "updated": max(stamps) if stamps else None,
            "newest": newest, "builds": builds, "kits": kits, "items": items,
            "changed_since": bool(newest and newest.get("changed_since"))}


def projects(root):
    rows = []
    shown = Path(root) / "shown"
    if not shown.is_dir():
        return rows
    for p in shown.iterdir():
        if not p.is_dir() or not SLUG.match(p.name):
            continue
        try:
            rows.append(project(root, p.name))
        except NotFound:
            continue
    rows.sort(key=lambda r: r.get("updated") or "", reverse=True)
    return rows[:LIST_MAX]


def _page(path, loader):
    if not path.is_file() or not loader.is_file():
        raise NotFound("the page is not there")
    if path.stat().st_size > PAGE_MAX:
        raise NotFound("the page is larger than %d MB" % (PAGE_MAX // 1048576))
    return path.read_text(encoding="utf-8"), _current_loader(loader.read_text(encoding="utf-8"))


def _current_loader(stored):
    """The loader as this version of the plugin writes it, with the stored one's title and page: a card shown before
    an update gets the update's fixes (the loader holds the card's CSS and its relay to the host)."""
    template = HERE / "templates" / "loader.html"
    if not template.is_file():
        return stored
    title = re.search(r"<title>([^<]*)</title>", stored)
    page = re.search(r'data-page="([a-z.]+)"', stored)
    if not title or not page or page.group(1) not in ("construct.html", "assembly.html", "booklet.html"):
        return stored
    return template.read_text(encoding="utf-8").replace("__TITLE__", title.group(1)).replace("__PAGE__", page.group(1))


def view(root, project, build=None):
    folder = build_dir(root, project, build)
    html, loader = _page(folder / "construct.html", folder / "loader.html")
    return {"html": html, "loader": loader, "card": _card(folder), "kind": "construct"}


def kit(root, project, kit_id, page="assembly"):
    if page not in ("assembly", "booklet"):
        raise NotFound("no such page")
    folder = _project_folder(root, project) / "kits"
    if not folder.is_dir():
        raise NotFound("no kit")
    target = _child(folder, kit_id)
    html, loader = _page(target / (page + ".html"), target / "loader.html")
    return {"html": html, "loader": loader, "card": _kit_card(target), "kind": page}


def thumb(root, project, build=None):
    folder = build_dir(root, project, build)
    shot = folder / "thumb.png"
    if not shot.is_file() or shot.stat().st_size > THUMB_MAX:
        raise NotFound("no thumbnail")
    return {"data_url": "data:image/png;base64," + base64.b64encode(shot.read_bytes()).decode("ascii")}


def item(root, project, item_id):
    """A file the project's tools made, by its id in the project's index; only a file inside that project's own
    folder (a folder named after the project) and of a kind the page shows."""
    folder = _project_folder(root, project)
    if not isinstance(item_id, str) or not BUILD.match(item_id):
        raise NotFound("no such file")
    entry = next((i for i in _read_json(folder / "items.json", []) if isinstance(i, dict) and i.get("id") == item_id), None)
    if not entry or not isinstance(entry.get("path"), str):
        raise NotFound("no such file")
    path = Path(entry["path"])
    if path.is_symlink() or not path.is_file():
        raise NotFound("the file is no longer there")
    path = path.resolve()
    if project not in path.parts[:-1] or path.suffix.lower() not in ITEM_TYPES:
        raise NotFound("not a file this page shows")
    if path.stat().st_size > ITEM_MAX:
        raise NotFound("too large to show here (%d MB); open it from its folder" % (path.stat().st_size // 1048576))
    mime = ITEM_TYPES[path.suffix.lower()]
    summary = entry.get("summary") if isinstance(entry.get("summary"), dict) else {}
    return {"name": path.name, "kind": entry.get("kind"), "summary": summary,
            "data_url": "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode("ascii"))}


def examples(base=HERE):
    rows = _read_json(Path(base) / "examples" / "catalog.json", [])
    return [r for r in rows if isinstance(r, dict) and SLUG.match(str(r.get("name", "")))]


def example_thumb(name, base=HERE):
    if not isinstance(name, str) or not SLUG.match(name):
        raise NotFound("no such example")
    shot = Path(base) / "examples" / name / "thumb.jpg"
    if not shot.is_file() or shot.stat().st_size > THUMB_MAX:
        raise NotFound("no still")
    return {"data_url": "data:image/jpeg;base64," + base64.b64encode(shot.read_bytes()).decode("ascii")}


TUTORIAL_FILE = re.compile(r"^(\d{2})-([a-z0-9-]{1,60})\.md$")


def parse_tutorial(text):
    """A tutorial file: its front matter (key: value lines between ---) and its sections (## Prompt, ## Steps...)."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and re.match(r"^[a-z_]+$", k.strip()):
            meta[k.strip()] = v.strip()
    sections, name = {}, None
    for line in m.group(2).splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            name = h.group(1).lower()
            sections[name] = []
        elif name:
            sections[name].append(line)
    return meta, {k: "\n".join(v).strip() for k, v in sections.items()}


def tutorials(base=HERE):
    folder = Path(base) / "skills" / "construct" / "tutorials"
    rows = []
    for p in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        m = TUTORIAL_FILE.match(p.name)
        got = parse_tutorial(p.read_text(encoding="utf-8")) if m else None
        if not got:
            continue
        meta, sections = got
        prompt = sections.get("prompt", "")
        if not meta.get("title") or not prompt:
            continue
        rows.append({"id": m.group(2), "file": "tutorials/" + p.name, "order": int(m.group(1)),
                     "title": meta["title"][:120], "summary": meta.get("summary", "")[:200],
                     "group": meta.get("group", "Everyday")[:60], "example": meta.get("example") or None,
                     "needs": [n.strip() for n in meta.get("needs", "").split(",") if n.strip()],
                     "time": meta.get("time", "")[:40], "status": meta.get("status", "ready"), "prompt": prompt[:1200]})
    return rows


try:
    from fastapi import APIRouter, HTTPException
except ImportError:   # outside Hermes (tests without FastAPI): the functions above still work
    APIRouter = None

if APIRouter is not None:
    router = APIRouter()

    def _answer(fn, *args):
        try:
            return fn(data_dir(), *args)
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.get("/projects")
    def get_projects():
        return {"projects": projects(data_dir())}

    @router.get("/view")
    def get_view(project: str, build: str = None):
        return _answer(view, project, build)

    @router.get("/thumb")
    def get_thumb(project: str, build: str = None):
        return _answer(thumb, project, build)

    @router.get("/kit")
    def get_kit(project: str, kit: str, page: str = "assembly"):
        return _answer(globals()["kit"], project, kit, page)

    @router.get("/item")
    def get_item(project: str, item: str):
        return _answer(globals()["item"], project, item)

    @router.get("/examples")
    def get_examples():
        return {"examples": examples()}

    @router.get("/example-thumb")
    def get_example_thumb(name: str):
        try:
            return example_thumb(name)
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.get("/tutorials")
    def get_tutorials():
        return {"tutorials": tutorials()}
