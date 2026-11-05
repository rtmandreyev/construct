"""The Desktop half's backend: the built constructs, read from the plugin's data folder.

Routes (mounted at /api/plugins/construct/):
    GET /projects                    the gallery: each project's newest build, newest first
    GET /view?project=&build=        one build: its page (the full HTML), its loader and its card
    GET /thumb?project=&build=       its small still, as a data URL

Everything is read from <data>/shown/<project>/<build>/, by ids that must match their patterns; a path is
never taken from a request. Nothing here writes.
"""

import base64
import json
import re
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
BUILD = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
PAGE_MAX = 64 * 1024 * 1024
THUMB_MAX = 2 * 1024 * 1024
LIST_MAX = 200


class NotFound(Exception):
    pass


def data_dir():
    from plugins.plugin_storage import plugin_data_dir   # follows the profile the request acts for
    return Path(plugin_data_dir("construct"))


def build_dir(root, project, build=None):
    """The shown folder of one build (the newest when `build` is None), checked to lie inside <root>/shown."""
    if not isinstance(project, str) or not SLUG.match(project):
        raise NotFound("no such project")
    shown = (Path(root) / "shown").resolve()
    folder = (shown / project).resolve()
    if folder.parent != shown or not folder.is_dir():
        raise NotFound("no such project")
    if build is None:
        builds = sorted(p.name for p in folder.iterdir() if p.is_dir() and BUILD.match(p.name))
        if not builds:
            raise NotFound("no build yet")
        build = builds[-1]
    if not isinstance(build, str) or not BUILD.match(build):
        raise NotFound("no such build")
    target = (folder / build).resolve()
    if target.parent != folder or not target.is_dir():
        raise NotFound("no such build")
    return target


def _card(folder):
    try:
        card = json.loads((folder / "card.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        card = {}
    card = {k: card.get(k) for k in ("title", "parts", "counts", "size_m", "audit_ok", "created", "page", "has_thumb")}
    card.update(project=folder.parent.name, build=folder.name)
    return card


def projects(root):
    rows = []
    shown = Path(root) / "shown"
    if not shown.is_dir():
        return rows
    for p in shown.iterdir():
        if not p.is_dir() or not SLUG.match(p.name):
            continue
        try:
            folder = build_dir(root, p.name)
        except NotFound:
            continue
        card = _card(folder)
        card["builds"] = sum(1 for b in p.iterdir() if b.is_dir() and BUILD.match(b.name))
        rows.append(card)
    rows.sort(key=lambda c: c["build"], reverse=True)
    return rows[:LIST_MAX]


def view(root, project, build=None):
    folder = build_dir(root, project, build)
    page, loader = folder / "construct.html", folder / "loader.html"
    if not page.is_file() or not loader.is_file():
        raise NotFound("the build has no page")
    if page.stat().st_size > PAGE_MAX:
        raise NotFound("the page is larger than %d MB" % (PAGE_MAX // 1048576))
    return {"html": page.read_text(encoding="utf-8"), "loader": loader.read_text(encoding="utf-8"), "card": _card(folder)}


def thumb(root, project, build=None):
    folder = build_dir(root, project, build)
    shot = folder / "thumb.png"
    if not shot.is_file() or shot.stat().st_size > THUMB_MAX:
        raise NotFound("no thumbnail")
    return {"data_url": "data:image/png;base64," + base64.b64encode(shot.read_bytes()).decode("ascii")}


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
