"""Where Construct lives and how it runs: projects, the shown pages, and Construct as a child process.

Construct runs as a child of the interpreter Hermes runs on (`sys.executable -I -B`), importing the
vendored package from `_vendor/` (or, in a source checkout, the repository's own package two folders
up). The child is given only what a program needs of Hermes's environment, and Construct's own settings (child_env).

Everything the plugin writes sits under its data folder (`plugin_data_dir("construct")`), or under the
projects folder the user chose in the plugin's settings:

    <data>/projects/<slug>/          scene.json, project.json, builds/, review/, exports/, films/, work/
    <data>/shown/<slug>/<build>/     construct.html, loader.html, thumb.png, card.json: what chat and gallery show
    <data>/jobs/<id>/                job.json, log.txt, exit.json (and a film's frames while it renders)
"""

import json
import os
import re
import unicodedata
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


def examples():
    """The stock constructs by name: {"scene", "materials", "thumb", "kit_plan"} paths (see stock.py)."""
    from . import stock
    pkg = HERE / "examples"
    if (pkg / "catalog.json").is_file():
        return {p.name: stock.package_files(p) for p in sorted(pkg.iterdir())
                if p.is_dir() and stock.NAME.match(p.name) and (p / "scene.json").is_file()}
    root = HERE.parents[2] if len(HERE.parents) > 2 else HERE
    found = {n: stock.source_files(root, n) for n in stock.STOCK}
    found = {n: f for n, f in found.items() if f["scene"].is_file()}
    if not found:
        raise ConstructError("no example constructs are bundled with the plugin")
    return found


def example_worlds():
    """The worlds that ship with the plugin, by name: {name: {"folder", "title", "summary", "constructs"}}."""
    index = HERE / "examples" / "worlds.json"
    if index.is_file():
        rows = json.loads(index.read_text(encoding="utf-8"))
        base = HERE / "examples" / "worlds"
    else:   # a source checkout: the repository's own
        base = (HERE.parents[2] if len(HERE.parents) > 2 else HERE) / "examples" / "worlds"
        rows = []
        for d in sorted(base.iterdir()) if base.is_dir() else []:
            if (d / "world.json").is_file():
                doc = json.loads((d / "world.json").read_text(encoding="utf-8"))
                rows.append({"name": d.name, "title": doc["title"], "summary": doc.get("summary", ""),
                             "constructs": sorted({q["construct"] for q in doc["placements"]
                                                   if not q["construct"].endswith(".json")})})
    return {r["name"]: dict(r, folder=base / r["name"]) for r in rows}


def gallery():
    """The gallery's constructs by name (the package's examples/gallery.json; in a source checkout, the repository's
    own examples): {name: row}."""
    from . import stock
    pkg = HERE / "examples" / "gallery.json"
    if pkg.is_file():
        doc = json.loads(pkg.read_text(encoding="utf-8"))
    else:
        root = HERE.parents[2] if len(HERE.parents) > 2 else HERE
        doc = stock.gallery_index(root)
    return {r["name"]: r for r in doc.get("constructs", [])}


def gallery_files(name):
    """A gallery construct's scene and material map: read from the repository in a source checkout, else fetched
    once from GitHub (this release's tag) into the plugin's data folder."""
    from . import stock
    rows = gallery()
    if name not in rows:
        raise ConstructError("no gallery construct %r" % name)
    root = HERE.parents[2] if len(HERE.parents) > 2 else HERE
    local = root / rows[name]["files"]["scene"]
    if not (HERE / "examples" / "gallery.json").is_file() and local.is_file():
        m = rows[name]["files"].get("materials")
        return {"scene": local, "materials": root / m if m else None}
    dest = data_dir() / "gallery" / name
    if not (dest / "scene.json").is_file():
        code, out, _ = run_child("version", timeout=30)
        if code != 0 or not out.strip():
            raise ConstructError("could not read Construct's version to fetch %s from the gallery" % name)
        try:
            stock.fetch_gallery(name, dest, out.strip(), {"constructs": list(rows.values())})
        except (OSError, ValueError) as exc:
            raise ConstructError("could not fetch %s from the gallery: %s" % (name, exc))
    m = dest / "scene.materials.json"
    return {"scene": dest / "scene.json", "materials": m if m.is_file() else None}


def catalog():
    """The stock constructs described: title, parts, one line, how each was made."""
    from . import stock
    index = HERE / "examples" / "catalog.json"
    if index.is_file():
        try:
            return json.loads(index.read_text(encoding="utf-8"))
        except ValueError:
            pass
    root = HERE.parents[2] if len(HERE.parents) > 2 else HERE
    return [stock.describe(n, f["scene"], stock.source_files(root, n)["readme"]) for n, f in examples().items()]


# ---------------------------------------------------------------------------- projects

_FOLD = str.maketrans({"ß": "ss", "æ": "ae", "ø": "o", "œ": "oe", "đ": "d", "ł": "l", "þ": "th", "ð": "d"})


def slugify(text):
    """A project id from a title: accents folded (Börshuset, Kraków, Łódź keep their letters), the rest dashes."""
    t = unicodedata.normalize("NFKD", str(text or "").lower().translate(_FOLD))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    out = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48].strip("-")
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


def scene_stamp(scene):
    """What a build records of its scene, so the Constructs page can say the scene changed since."""
    try:
        st = Path(scene).stat()
        return {"scene_mtime_ns": st.st_mtime_ns, "scene_bytes": st.st_size}
    except OSError:
        return {}


def stamp_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def new_id():
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


# ---------------------------------------------------------------------------- the child

# what the child is given of Hermes's environment, where provider keys live: what a program needs to start and keep
# its files (the same names as construct_hologram/procenv.py, which the plugin cannot import), and Construct's own
# settings (CONSTRUCT_ENV); never the rest, where provider keys live
CHILD_ENV = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP", "LANG", "LANGUAGE", "LC_ALL",
             "LC_CTYPE", "LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
             "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "DISPLAY", "WAYLAND_DISPLAY", "FONTCONFIG_FILE", "FONTCONFIG_PATH",
             "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
             "PROGRAMFILES", "PROGRAMFILES(X86)", "USERPROFILE", "USERNAME", "HOMEDRIVE", "HOMEPATH",
             "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "JAVA_HOME", "FREECAD_USER_HOME", "FREECAD_USER_DATA",
             "FREECAD_USER_TEMP")


# Construct's own settings: where it finds its programs, and its test switches (never the critic's endpoint or key)
CONSTRUCT_ENV = ("CONSTRUCT_BLENDER", "CONSTRUCT_FREECAD", "CONSTRUCT_NETLOGO", "CONSTRUCT_GODOT",
                 "CONSTRUCT_PRUSASLICER", "CONSTRUCT_FFMPEG", "CONSTRUCT_JAVAC", "HOLOGRAM_CHROME",
                 "HOLOGRAM_SKIP_CAPTURE")


def child_env():
    return {k: os.environ.get(k) for k in CHILD_ENV + CONSTRUCT_ENV if os.environ.get(k) is not None}


def child_argv(op, *args):
    """The argv that runs `child.py <op> ...` on Hermes's interpreter, isolated and without bytecode."""
    return [sys.executable, "-I", "-B", str(CHILD), str(vendor_root()), op] + [str(a) for a in args]


def run_child(op, *args, timeout=120, cwd=None):
    """Run a short child to its end: (exit code, stdout, stderr). A child that outlives `timeout` is stopped."""
    try:
        r = subprocess.run(child_argv(op, *args), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=str(cwd) if cwd else None, env=child_env())
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

def write_loader(target, title, page="construct.html"):
    """The small page chat shows first: it asks the host for the construct (or a kit's page) and replaces itself
    with it; opened from disk, it goes to `page` beside it."""
    text = LOADER.read_text(encoding="utf-8")
    safe = re.sub(r"[^A-Za-z0-9 .,:;'()&+/-]", "", str(title or "Construct"))[:80] or "Construct"
    page = page if page in ("construct.html", "assembly.html", "booklet.html") else "construct.html"
    Path(target).write_text(text.replace("__TITLE__", safe).replace("__PAGE__", page), encoding="utf-8")


ITEM_KINDS = ("export", "film", "kit", "run", "compare", "plates", "file")
ITEMS_MAX = 200


def record_item(slug, kind, path, title="", summary=None):
    """List a file a project made (an export, a film, a kit, a run's recording...) on the Constructs page: an entry in
    shown/<slug>/items.json, newest last. The page reads files only through these entries, by id."""
    if kind not in ITEM_KINDS or not SLUG.match(str(slug or "")):
        return None
    path = Path(path)
    folder = shown_root() / slug
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / "items.json"
    try:
        items = json.loads(index.read_text(encoding="utf-8"))
        items = items if isinstance(items, list) else []
    except (OSError, ValueError):
        items = []
    item = {"id": new_id(), "kind": kind, "path": str(path), "name": path.name, "title": str(title or "")[:120],
            "created": stamp_iso(), "bytes": path.stat().st_size if path.is_file() else None,
            "summary": summary if isinstance(summary, dict) else {}}
    items = [i for i in items if i.get("path") != str(path)] + [item]
    write_json(index, items[-ITEMS_MAX:])
    return item


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
