"""Where Construct lives and how it runs: projects, the shown pages, and Construct as a child process.

Construct runs as a child of the interpreter Hermes runs on (`sys.executable -I -B`), importing the
vendored package from `_vendor/` (or, in a source checkout, the repository's own package two folders
up). The child inherits the environment as it is; nothing here reads or changes it.

Everything the plugin writes sits under its data folder (`plugin_data_dir("construct")`), or under the
projects folder the user chose in the plugin's settings:

    <data>/projects/<slug>/          scene.json, project.json, builds/, review/, exports/, films/, work/
    <data>/shown/<slug>/<build>/     construct.html, loader.html, thumb.png, card.json: what chat and gallery show
    <data>/jobs/<id>/                job.json, log.txt, exit.json (and a film's frames while it renders)
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHILD = HERE / "child.py"
LOADER = HERE / "templates" / "loader.html"

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
BUILD = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
JOB = re.compile(r"^[0-9a-f]{12}$")
KEEP_BUILDS = 6          # builds kept per project (older ones are pruned, with their shown copies)
PAGE_MAX = 64 * 1024 * 1024

_state = {"data": None, "projects": None, "config": None}


class ConstructError(Exception):
    """A request the plugin cannot carry out; the message says why, in words for the model."""


# ---------------------------------------------------------------------------- folders

def configure(data=None, projects=None, config=None):
    """Test seam and host wiring: a fixed data folder, a fixed projects folder, or a config reader
    (`config(key, default)`, the plugin context's `get_config`)."""
    if data is not None:
        _state["data"] = Path(data)
    if projects is not None:
        _state["projects"] = Path(projects)
    if config is not None:
        _state["config"] = config


def data_dir():
    if _state["data"] is not None:
        _state["data"].mkdir(parents=True, exist_ok=True)
        return _state["data"]
    from plugins.plugin_storage import plugin_data_dir   # resolved each call: it follows the active profile
    return Path(plugin_data_dir("construct"))


def setting(key, default=None):
    reader = _state["config"]
    if reader is None:
        return default
    try:
        value = reader(key, default)
    except Exception:   # a malformed config entry must not break a tool: the default applies
        return default
    return default if value is None else value


def projects_root():
    if _state["projects"] is not None:
        root = _state["projects"]
    else:
        chosen = str(setting("projects_folder", "") or "").strip()
        root = Path(chosen).expanduser() if chosen else data_dir() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def shown_root():
    root = data_dir() / "shown"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def jobs_root():
    root = data_dir() / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def allowed_roots():
    """The folders the plugin may write into."""
    return [data_dir().resolve(), projects_root()]


def inside(path, roots):
    p = Path(path).resolve()
    for r in roots:
        try:
            p.relative_to(r)
            return True
        except ValueError:
            continue
    return False


def vendor_root():
    """The folder that holds the `construct_hologram` package the child imports."""
    for cand in (HERE / "_vendor", HERE.parents[2] if len(HERE.parents) > 2 else None):
        if cand is not None and (cand / "construct_hologram" / "__init__.py").is_file():
            return cand
    raise ConstructError("the Construct runtime is missing from the plugin (_vendor/construct_hologram)")


def examples_dir():
    for cand in (HERE / "examples", vendor_root() / "construct_hologram" / "examples" / "v2"):
        if cand.is_dir() and any(cand.glob("*.json")):
            return cand
    raise ConstructError("no example scenes are bundled with the plugin")


def examples():
    """Bundled example scenes by name (the file name without .json, or .params.json for a parameter document)."""
    return {re.sub(r"(\.params)?\.json$", "", p.name): p for p in sorted(examples_dir().glob("*.json"))
            if not p.name.endswith(".materials.json")}


# ---------------------------------------------------------------------------- projects

def slugify(text):
    out = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:48].strip("-")
    return out or "construct"


def new_project(title):
    """A fresh project folder named after the title (a number added when the name is taken)."""
    root, base = projects_root(), slugify(title)
    for n in range(1, 1000):
        slug = base if n == 1 else "%s-%d" % (base, n)
        folder = root / slug
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        return slug, folder
    raise ConstructError("too many projects named %r" % base)


def project_dir(slug):
    if not isinstance(slug, str) or not SLUG.match(slug):
        raise ConstructError("project must be a project id as construct_start returned it (lower-case letters, "
                             "digits and dashes)")
    folder = projects_root() / slug
    if not folder.is_dir():
        known = ", ".join(sorted(p.name for p in projects_root().iterdir() if p.is_dir())[:20]) or "none yet"
        raise ConstructError("no project %r (projects: %s); start one with construct_start" % (slug, known))
    return folder


def read_project(folder):
    try:
        return json.loads((folder / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"slug": folder.name, "scene": "scene.json"}


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(".%s.%s.tmp" % (path.name, secrets.token_hex(3)))
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def resolve(args):
    """(slug, project folder, scene path) for a call that names a `project`, a `scene` path, or both.

    A scene given by path (anywhere the user names) is read where it is; its outputs go to the project of the
    same name, made on first use."""
    project, scene = args.get("project"), args.get("scene")
    if project is not None and not isinstance(project, str):
        raise ConstructError("project must be a string")
    if scene is not None and not isinstance(scene, str):
        raise ConstructError("scene must be a path (a string)")
    if not project and not scene:
        raise ConstructError("name a project (from construct_start) or a scene path")
    if project:
        folder = project_dir(project)
        if scene:
            path = Path(scene).expanduser()
            path = path if path.is_absolute() else folder / path
        else:
            info = read_project(folder)
            path = Path(info.get("scene") or "scene.json")
            path = path if path.is_absolute() else folder / path
        if not path.is_file():
            raise ConstructError("the scene %s does not exist" % path)
        return project, folder, path.resolve()
    path = Path(scene).expanduser()
    if not path.is_absolute():
        raise ConstructError("a scene without a project must be an absolute path")
    if not path.is_file():
        raise ConstructError("the scene %s does not exist" % path)
    path = path.resolve()
    root = projects_root()
    if inside(path, [root]):   # a scene inside a project already: that project
        rel = path.relative_to(root)
        if len(rel.parts) > 1 and SLUG.match(rel.parts[0]):
            return rel.parts[0], root / rel.parts[0], path
    stem = path.stem[:-7] if path.stem.endswith(".params") else path.stem
    slug = slugify(path.parent.name if stem in ("scene", "construct") else stem)
    folder = root / slug
    info = read_project(folder) if folder.is_dir() else None
    if info is None or info.get("scene") != str(path):
        if info is not None:   # the name is taken by another scene: a new project
            slug, folder = new_project(slug)
        else:
            folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "project.json", {"slug": slug, "title": path.stem, "scene": str(path), "origin": "path",
                                             "created": stamp_iso()})
    return slug, folder, path


def stamp_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def new_id():
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


# ---------------------------------------------------------------------------- the child

def child_argv(op, *args):
    """The argv that runs `child.py <op> ...` on Hermes's interpreter, isolated and without bytecode."""
    return [sys.executable, "-I", "-B", str(CHILD), str(vendor_root()), op] + [str(a) for a in args]


def run_child(op, *args, timeout=120, cwd=None):
    """Run a short child to its end: (exit code, stdout, stderr). A child that outlives `timeout` is stopped."""
    try:
        r = subprocess.run(child_argv(op, *args), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=str(cwd) if cwd else None)
    except subprocess.TimeoutExpired:
        raise ConstructError("Construct did not answer within %d s" % timeout)
    return r.returncode, r.stdout, r.stderr


_programs = {"at": 0.0, "found": None}


def programs(fresh=False):
    """Which outside programs Construct can find here (a browser, ffmpeg, FreeCAD, Blender), as Construct's
    own finders see them; cached for ten minutes."""
    if fresh or _programs["found"] is None or time.time() - _programs["at"] > 600:
        try:
            code, out, _ = run_child("programs", timeout=30)
            found = json.loads(out) if code == 0 else {}
        except (ConstructError, ValueError):
            found = {}
        _programs.update(at=time.time(), found=found)
    return dict(_programs["found"] or {})


# ---------------------------------------------------------------------------- shown pages

def write_loader(target, title):
    """The small page chat shows first: it asks the host for the construct and replaces itself with it."""
    text = LOADER.read_text(encoding="utf-8")
    safe = re.sub(r"[^A-Za-z0-9 .,:;'()&+/-]", "", str(title or "Construct"))[:80] or "Construct"
    Path(target).write_text(text.replace("__TITLE__", safe), encoding="utf-8")


def link_or_copy(src, dst):
    dst = Path(dst)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def prune(folder, keep=KEEP_BUILDS):
    """Remove all but the newest `keep` build folders in `folder`."""
    if not folder.is_dir():
        return
    builds = sorted(p for p in folder.iterdir() if p.is_dir() and BUILD.match(p.name))
    for old in builds[:-keep] if keep else builds:
        shutil.rmtree(old, ignore_errors=True)


def show(slug, build, page, card, thumb=None):
    """Put a built page where chat and the gallery read it: shown/<slug>/<build>/ with its loader and card."""
    folder = shown_root() / slug / build
    folder.mkdir(parents=True, exist_ok=True)
    link_or_copy(page, folder / "construct.html")
    if thumb and Path(thumb).is_file():
        link_or_copy(thumb, folder / "thumb.png")
    write_loader(folder / "loader.html", card.get("title"))
    card = dict(card, has_thumb=(folder / "thumb.png").is_file())
    write_json(folder / "card.json", card)
    prune(shown_root() / slug)
    return folder
