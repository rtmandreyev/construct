"""The NetLogo tools: run a model headless, repeat and compare runs, draw recorded runs (see netlogo_child.py).

    construct_netlogo_run    a model (a path, or a name in the user's installed Models Library) run headless as a
                             background job, once (shown growing while it runs) or N seeded runs (compared, with a
                             summary across runs), drawn into a construct project and published like any construct
    construct_netlogo_draw   recorded runs (run.jsonl) drawn into a project, one or two to eight side by side; no
                             NetLogo needed

NetLogo is found as Construct finds it: the plugin's `netlogo_folder` setting, CONSTRUCT_NETLOGO (NetLogo's folder),
then the usual install places; Java is NetLogo's own bundled runtime, else JAVA_HOME, a Homebrew OpenJDK or `java`
on the PATH. Nothing is installed or downloaded. Library models stay where they are: a run copies one into its own
project (in the plugin's data folder), never into the plugin.
"""

import json
import os
import re
import secrets
import shutil
import sys
import threading
import contextvars
import time
from pathlib import Path

from . import jobs, netlogo_child, runtime, tools
from .runtime import ConstructError

WAIT = 300           # seconds a run's call waits for the job to end (within Hermes's 420 s tool deadline)
QUICK = 20           # once a live preview is shown, the call answers after this long if the run still goes on
DRAW_WAIT = 240
FIND_EVERY = 600     # seconds NetLogo's whereabouts are cached for
VIEWS = ("auto", "space-time", "network-time", "phase", "field", "pulse")
_found = {"at": 0.0, "value": None}
_library = {"at": 0.0, "root": None, "models": []}
_plock = threading.Lock()
_finished = set()    # jobs whose final construct is published: no preview may follow it


# ---------------------------------------------------------------------------- finding NetLogo and Java

def _version_key(path):
    nums = re.findall(r"\d+", Path(path).name)
    return tuple(int(n) for n in nums) or (0,)


def _candidates():
    out = []
    for given in (runtime.setting("netlogo_folder", ""), os.environ.get("CONSTRUCT_NETLOGO")):
        if given and str(given).strip():
            p = Path(str(given).strip()).expanduser()
            out.append(p.parent if p.suffix == ".app" else p)
    home = Path.home()
    roots = [Path("/Applications"), home / "Applications", home, Path("/opt"), Path("/usr/local"),
             Path("/usr/local/share"), Path("C:/Program Files"), Path("C:/Program Files (x86)")]
    found = []
    for root in roots:
        try:
            found += [p for p in root.glob("NetLogo*") if p.is_dir() and not p.name.endswith(".app")]
        except OSError:
            continue
    return out + sorted(found, key=_version_key, reverse=True)


def _jar(folder):
    for sub in ("app", "lib/app", "Java"):
        jars = sorted((folder / sub).glob("netlogo-[0-9]*.jar"), key=_version_key, reverse=True) \
            if (folder / sub).is_dir() else []
        if jars:
            return jars[0]
    return None


def _java(folder):
    exe = "java.exe" if os.name == "nt" else "java"
    for rel in ("runtime/Contents/Home/bin", "lib/runtime/bin", "runtime/bin"):   # NetLogo's own Java first
        if (folder / rel / exe).is_file():
            return folder / rel / exe
    home = os.environ.get("JAVA_HOME")
    cands = [Path(home) / "bin" / exe] if home else []
    cands += [Path("/opt/homebrew/opt/openjdk@17/bin/java"), Path("/opt/homebrew/opt/openjdk/bin/java"),
              Path("/usr/local/opt/openjdk@17/bin/java"), Path("/usr/local/opt/openjdk/bin/java")]
    for c in cands:
        if c.is_file():
            return c
    which = shutil.which("java")
    if which and sys.platform == "darwin" and which == "/usr/bin/java":   # macOS's stub, without a JDK behind it
        jvms = Path("/Library/Java/JavaVirtualMachines")
        if not (jvms.is_dir() and any(jvms.iterdir())):
            return None
    return Path(which) if which else None


def find_netlogo(fresh=False):
    """{"folder", "jar", "java", "extensions", "models", "version"} for the NetLogo found here, or None (cached)."""
    if not fresh and time.time() - _found["at"] < FIND_EVERY:
        return _found["value"]
    value = None
    for folder in _candidates():
        try:
            jar = _jar(folder) if folder.is_dir() else None
        except OSError:
            jar = None
        if not jar:
            continue
        java = _java(folder)
        ext = next((p for p in (folder / "extensions", folder / "app" / "extensions", folder / "lib" / "app" / "extensions")
                    if p.is_dir()), None)
        models = next((p for p in (folder / "models", folder / "lib" / "models", folder / "app" / "models") if p.is_dir()),
                      None)
        m = re.search(r"netlogo-([0-9][0-9.]*)\.jar$", jar.name)
        value = {"folder": str(folder), "jar": str(jar), "java": str(java) if java else None,
                 "extensions": str(ext) if ext else None, "models": str(models) if models else None,
                 "version": m.group(1).rstrip(".") if m else None}
        break
    _found.update(at=time.time(), value=value)
    return value


def ready():
    """check_fn of construct_netlogo_run: the runtime, NetLogo and a Java to run it (cheap: cached file checks)."""
    try:
        runtime.vendor_root()
        found = find_netlogo()
        return bool(found and found.get("java"))
    except Exception:
        return False


def library_models(found):
    """The installed Models Library's models (.nlogox, .nlogox3d), cached."""
    root = found.get("models") if found else None
    if not root:
        return []
    if _library["root"] != root or time.time() - _library["at"] > FIND_EVERY:
        models = sorted(p for p in Path(root).rglob("*.nlogox*") if p.suffix.lower() in (".nlogox", ".nlogox3d"))
        _library.update(at=time.time(), root=root, models=models)
    return list(_library["models"])


def _row(p, root):
    rel = p.relative_to(root)
    return {"name": p.stem, "folder": str(rel.parent), "path": str(p)}


def _search(words, found):
    if not found:
        return {"netlogo": None,
                "how": "NetLogo was not found (Construct looks at the plugin's NetLogo folder setting, CONSTRUCT_NETLOGO "
                       "and the usual install places). Say so; do not install it. A recorded run (run.jsonl) can still "
                       "be drawn with construct_netlogo_draw."}
    models = library_models(found)
    root = Path(found["models"]) if found.get("models") else None
    out = {"netlogo": found["folder"], "version": found["version"], "java": found["java"],
           "library": found.get("models"), "library_models": len(models)}
    terms = [w for w in re.split(r"\s+", words.lower()) if w]
    if terms and root:
        hits = [p for p in models if all(t in str(p.relative_to(root)).lower() for t in terms)]
        hits.sort(key=lambda p: (p.stem.lower() != words.strip().lower(), "3D" in p.relative_to(root).parts[:1],
                                 len(p.parts), p.stem.lower()))
        out["models"] = [_row(p, root) for p in hits[:30]]
        if len(hits) > 30:
            out["more"] = len(hits) - 30
    out["licence"] = ("Models Library models are CC BY-NC-SA (each says so in its Info tab): a run of one is for "
                      "non-commercial use, shared alike, with the model's credit.")
    out["next"] = "call construct_netlogo_run with model set to a name or path"
    return out


def resolve_model(model, found):
    """An absolute .nlogox path, or a model's name in the installed library."""
    if not isinstance(model, str) or not model.strip() or len(model) > 1000:
        raise ConstructError("model must be a .nlogox path or a model's name in the NetLogo Models Library")
    text = model.strip()
    p = Path(text).expanduser()
    if p.is_absolute() or "/" in text or "\\" in text or text.lower().endswith((".nlogox", ".nlogo", ".nlogox3d", ".nlogo3d")):
        if not p.is_absolute() or not p.is_file():
            raise ConstructError("no model at %s (give an absolute path, or a model's name in the library)" % text)
        path = p.resolve()
    else:
        models = library_models(found)
        if not models:
            raise ConstructError("no NetLogo Models Library was found beside NetLogo (%s); give the model's path" %
                                 found["folder"])
        root = Path(found["models"])
        exact = [m for m in models if m.stem.lower() == text.lower()]
        two_d = [m for m in exact if m.suffix.lower() == ".nlogox"]
        hits = two_d or exact or [m for m in models if text.lower() in m.stem.lower()]
        if not hits:
            raise ConstructError("no model named %r in the installed library; search it with construct_netlogo_run "
                                 "{\"search\": \"...\"}" % text)
        if len(hits) > 1 and not (two_d and len(two_d) == 1):
            raise ConstructError("%d library models match %r: %s. Give the exact name or the path." % (
                len(hits), text, "; ".join("%s (%s)" % (h.stem, h.relative_to(root).parent) for h in hits[:12])))
        path = hits[0]
    if path.suffix.lower() in (".nlogo", ".nlogo3d"):
        raise ConstructError("%s is a NetLogo 6 file: open it in NetLogo 7 and save it as .nlogox, then run that" % path.name)
    if path.suffix.lower() not in (".nlogox", ".nlogox3d"):
        raise ConstructError("%s is not a NetLogo model (.nlogox)" % path.name)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ConstructError("%s is larger than 8 MB; that is not a model file" % path.name)
    return path


# ---------------------------------------------------------------------------- argument checks

def _strings(args, key, most=12, longest=400):
    v = args.get(key)
    if v is None:
        return None
    if not isinstance(v, list) or len(v) > most or any(not isinstance(x, str) or not x.strip() or len(x) > longest
                                                        or "\n" in x for x in v):
        raise ConstructError("%s must be a list of at most %d one-line strings" % (key, most))
    return [x.strip() for x in v]


def _text(args, key, longest=400):
    v = args.get(key)
    if v is None:
        return None
    if not isinstance(v, str) or not v.strip() or len(v) > longest or "]]>" in v:
        raise ConstructError("%s must be a non-empty string of at most %d characters" % (key, longest))
    return v.strip()


OPTION_CHOICES = {"time": ("linear", "sqrt"), "change": ("first", "last"), "landmarks": ("on", "off"),
                  "colors": ("run", "house")}
OPTION_NUMBERS = {"smooth": (2, 500), "levels": (2, 128), "resolution": (8, 256), "max_agents": (1, 1000)}
OPTION_TEXT = ("state", "x", "z", "window")


def _options(args):
    o = args.get("options")
    if o is None:
        return {}
    if not isinstance(o, dict):
        raise ConstructError("options must be an object")
    known = set(OPTION_CHOICES) | set(OPTION_NUMBERS) | set(OPTION_TEXT)
    unknown = sorted(set(o) - known)
    if unknown:
        raise ConstructError("unknown option(s) %s; options are %s" % (", ".join(unknown), ", ".join(sorted(known))))
    out = {}
    for k in OPTION_CHOICES:
        if o.get(k) is not None:
            out[k] = tools._choice(o, k, OPTION_CHOICES[k])
    for k, (lo, hi) in OPTION_NUMBERS.items():
        if o.get(k) is not None:
            out[k] = tools._number(o, k, lo, hi, integer=True)
    for k in OPTION_TEXT:
        if o.get(k) is not None:
            out[k] = _text(o, k, 120)
    if "window" in out and not re.match(r"^(auto|whole|[0-9]+(\.[0-9]+)?)$", out["window"]):
        raise ConstructError("options.window must be auto, whole or a tick such as 800")
    return out


def _view(args):
    return tools._choice(args, "view", list(VIEWS), "auto")


def _title(args):
    t = args.get("title")
    if t is not None and (not isinstance(t, str) or not t.strip() or len(t) > 120):
        raise ConstructError("title must be a string of at most 120 characters")
    return t.strip() if t else None


def _constants(args, settings):
    c = args.get("constants")
    if c is None:
        return {}
    if not isinstance(c, dict) or len(c) > 40:
        raise ConstructError("constants must be an object of at most 40 settings")
    out = {}
    for k, v in c.items():
        if not isinstance(k, str) or not re.match(r"^[^\s\"<>&\[\]]{1,64}$", k):
            raise ConstructError("constants: %r is not a variable name" % k)
        if settings and k.lower() not in {s.lower() for s in settings}:
            raise ConstructError("constants: the model has no setting %r; its settings are %s" % (
                k, ", ".join(sorted(settings)[:40])))
        if not isinstance(v, (bool, int, float, str)) or (isinstance(v, str) and len(v) > 200):
            raise ConstructError("constants: %s must be a number, true/false or a string" % k)
        s = settings.get(k) or next((x for n, x in settings.items() if n.lower() == k.lower()), None)
        if s and s["kind"] == "chooser" and s.get("choices"):
            allowed = [_literal(x) for x in s["choices"]]
            match = next((a for a in allowed if str(v) == str(a)), None)
            if match is None:
                raise ConstructError("constants: %s is one of %s" % (k, ", ".join(str(a) for a in allowed)))
            v = match   # a numeric chooser stays a number, a string one a string
        out[k] = v
    return out


def _literal(x):
    """A chooser's choice as NetLogo writes it: a quoted string, a number, or a word (true/false)."""
    try:
        return json.loads(x)
    except ValueError:
        return x


def _settings_brief(settings):
    rows = {}
    for k, s in list(settings.items())[:30]:
        if s["kind"] == "slider":
            rows[k] = "slider %s..%s (default %s)" % (s.get("min"), s.get("max"), s.get("default"))
        elif s["kind"] == "switch":
            rows[k] = "switch (default %s)" % ("true" if s.get("default") else "false")
        elif s["kind"] == "chooser":
            rows[k] = "chooser: %s (default %s)" % (", ".join(s.get("choices", [])[:10]), s.get("default"))
        else:
            rows[k] = "input"
    return rows


def custom_run(args):
    """What makes a construct_netlogo_run call one the user approves whatever the settings: setup/go code the agent
    wrote, or a model outside the installed Models Library (NetLogo code runs with the user's rights). An empty list:
    a library model run as it is."""
    if not isinstance(args, dict) or args.get("model") is None:
        return []
    why = []
    for key in ("setup", "go"):
        if isinstance(args.get(key), str) and args[key].strip():
            why.append("its own %s code: %s" % (key, " ".join(args[key].split())[:300]))
    found = find_netlogo()
    try:
        path = resolve_model(args["model"], found) if found else None
    except ConstructError:
        path = None   # the call fails before anything runs, and says why
    library = (found or {}).get("models")
    if path is not None and not (library and runtime.inside(path, [Path(library).resolve()])):
        why.append("a model outside the installed Models Library: %s" % path)
    return why


# ---------------------------------------------------------------------------- the run tool

@tools.tool("construct_netlogo_run")
def run_tool(args):
    found = find_netlogo(fresh=True)
    if args.get("model") is None:
        if args.get("search") is None:
            raise ConstructError("give model (a .nlogox path or a library model's name), or search to find one")
        if not isinstance(args["search"], str) or len(args["search"]) > 80:
            raise ConstructError("search must be a string of at most 80 characters")
        return _search(args["search"], found)
    if not found:
        raise ConstructError("NetLogo was not found on this machine (Construct looks at the plugin's NetLogo folder "
                             "setting, CONSTRUCT_NETLOGO and the usual install places). Say so; do not install it. A "
                             "recorded run can still be drawn with construct_netlogo_draw.")
    if not found.get("java"):
        raise ConstructError("NetLogo is at %s, but no Java runtime was found to run it (NetLogo's own, JAVA_HOME or "
                             "java on the PATH). Say so; do not install one." % found["folder"])
    path = resolve_model(args.get("model"), found)
    text = path.read_text(encoding="utf-8", errors="replace")
    settings = netlogo_child.model_settings(text)
    runs = tools._number(args, "runs", 1, 100, integer=True) or 1
    seed = tools._number(args, "seed", 0, 2000000000, integer=True)
    seed = secrets.randbelow(1000000) if seed is None else seed
    ticks = tools._number(args, "ticks", 1, 100000, integer=True) or 1000
    view, options, title = _view(args), _options(args), _title(args)
    model_3d = tools._bool(args, "model_3d")
    if model_3d and runs > 1:
        raise ConstructError("model_3d is for one run; draw one of the runs with construct_netlogo_draw for its 3D model")
    live = tools._bool(args, "live", True)
    constants = _constants(args, settings)
    turtles, reporters = _strings(args, "turtles"), _strings(args, "reporters")
    patches = _text(args, "patches", 200)
    no_turtles = tools._bool(args, "no_turtles")
    every = tools._number(args, "every", 1, 1000, integer=True)
    record = None
    if turtles is not None or reporters is not None or patches is not None or no_turtles or every:
        record = {"turtles": turtles or [], "reporters": reporters or [], "patches": patches, "no_turtles": no_turtles,
                  "every": every or 1}
    setup, go = _text(args, "setup"), _text(args, "go")
    library = found.get("models")
    in_library = bool(library) and runtime.inside(path, [Path(library).resolve()])
    model_title = path.stem
    slug, folder = runtime.new_project(title or (model_title if runs == 1 else "%s %d runs" % (model_title, runs)))
    credit = netlogo_child.credit_of(text, path, library)
    runtime.write_json(folder / "project.json", {
        "slug": slug, "title": title or model_title, "scene": "scene.json", "origin": "netlogo", "from": str(path),
        "created": runtime.stamp_iso(),
        "netlogo": {"model": str(path), "library": in_library, "runs": runs, "seed": seed, "ticks": ticks,
                    "constants": constants, "view": view, "credit": credit}})
    spec = {"project": str(folder), "slug": slug, "model": str(path), "model_title": model_title, "title": title,
            "runs": runs, "seed": seed, "ticks": ticks, "setup": setup, "go": go, "constants": constants,
            "record": record, "view": view, "options": options, "model_3d": model_3d, "live": live,
            "netlogo": found}
    label = "NetLogo run of %s" % model_title if runs == 1 else "%d NetLogo runs of %s" % (runs, model_title)
    job_id = jobs.start("netlogo-run", "netlogo-run", project=slug, label=label, cwd=folder, spec=spec,
                        finish={"slug": slug, "runs": runs, "model": model_title})
    out = _wait_run(job_id, slug, label)
    if out.get("state") == "running":
        out["model"] = {"path": str(path), "library": in_library, "settings": _settings_brief(settings)}
        if credit:
            out["credit"] = credit["line"]
    return out


def _work(job_id):
    return runtime.jobs_root() / job_id / "work"


def _event(job_id, slug, build, ticks, final):
    fn = jobs._watch.get("event")
    if fn is None:
        return
    try:
        fn("run.preview", {"job_id": job_id, "project": slug, "build": build, "ticks": ticks, "final": bool(final)})
    except Exception:   # no Desktop connected: nothing to tell
        pass


def _follow(job_id, slug, state):
    """Show a running run's previews as the child writes them (the newest each time), and when the job ends make
    its final construct at once (its finisher publishes it), so a card that follows the run ends on it."""
    shown = 0
    while True:
        try:
            done = jobs.ended(job_id)
        except ConstructError:
            return
        try:
            previews = json.loads((_work(job_id) / "previews.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previews = []
        if done is None and len(previews) > shown:
            p = previews[-1]
            shown = len(previews)
            with _plock:
                if job_id in _finished:
                    return
                try:
                    res = tools.publish(slug, p["build"], Path(p["out"]), p["scene"], kind="construct",
                                        extra_card={"source": "netlogo", "preview": True, "ticks": p["ticks"],
                                                    "job_id": job_id})
                except Exception:   # a preview that cannot be shown: the run goes on
                    res = None
                if res is not None:
                    state["preview"] = dict(res, ticks=p["ticks"])
                    _event(job_id, slug, p["build"], p["ticks"], False)
        if done is not None:
            try:
                jobs.status(job_id)   # the finisher publishes the final construct (once) and tells the Desktop
            except Exception:
                pass
            return
        time.sleep(1.0)


def _wait_run(job_id, slug, label):
    state = {"preview": None}
    context = contextvars.copy_context()   # the thread keeps the call's context, as jobs.watch does
    threading.Thread(target=context.run, args=(_follow, job_id, slug, state), daemon=True,
                     name="construct-netlogo-%s" % job_id).start()
    started = time.time()
    while True:
        done = jobs.wait(job_id, 1.0)
        if done is not None:
            return jobs.status(job_id)
        elapsed = time.time() - started
        if (state["preview"] and elapsed >= QUICK) or elapsed >= WAIT:
            break
    jobs.watch(job_id, label)
    out = {"job_id": job_id, "state": "running", "kind": "netlogo-run", "project": slug,
           "progress": jobs.progress(job_id),
           "next": "the run goes on in the background; call construct_job with this job_id for the final construct "
                   "(its MEDIA line), or to cancel it"}
    p = state["preview"]
    if p:
        out.update({"preview": {"build": p["build"], "ticks": p["ticks"], "title": p.get("title")},
                    "file_path": p["file_path"], "media_tag": p["media_tag"], "media": p["media"],
                    "next": "put the MEDIA line in your reply: the construct grows there while the run goes on. Then "
                            "call construct_job with this job_id for the final construct"})
    return out


def _items(slug, outcome):
    files = outcome.get("files", {})
    model = outcome.get("model_title") or ""
    recs = files.get("recordings") or ([files["recording"]] if files.get("recording") else [])
    seeds = [r.get("seed") for r in (outcome.get("summary") or {}).get("per_run", [])] if outcome.get("summary") else []
    for i, rec in enumerate(recs):
        seed = seeds[i] if i < len(seeds) else (outcome.get("run") or {}).get("seed")
        runtime.record_item(slug, "run", rec, ("%s, seed %s" % (model, seed)) if model and seed is not None
                            else Path(rec).name, {"seed": seed} if seed is not None else None)
    if files.get("summary"):
        s = outcome["summary"]
        runtime.record_item(slug, "compare", files["summary"], "%d runs compared" % s["runs"],
                            {"runs": s["runs"], "ticks": s["ticks"], "final": s["final"]})
    if files.get("counts_csv"):
        runtime.record_item(slug, "file", files["counts_csv"], "Counts at every record (CSV)")
    if files.get("glb"):
        runtime.record_item(slug, "export", files["glb"], "3D model of the run (glb)")


def _next(slug, outcome):
    rec = "run.jsonl"
    recs = (outcome.get("files") or {}).get("recordings") or []
    if outcome.get("kind") != "run" and recs:
        try:
            rec = Path(recs[0]).relative_to(runtime.project_dir(slug)).as_posix()
        except (ValueError, ConstructError):
            rec = recs[0]
    tips = ["put the MEDIA line in your reply%s" % (" with the model's credit line (CC BY-NC-SA: non-commercial, share "
                                                    "alike)" if (outcome.get("credit") or {}).get("licence") else ""),
            "project %s works with construct_inspect, construct_check, construct_review and construct_export "
            "(glb, obj, stl, 3mf, fcstd, step)" % slug,
            "another view: construct_netlogo_draw {\"project\": \"%s\", \"view\": \"...\"}" % slug,
            "printed plates: construct_command {\"project\": \"%s\", \"argv\": [\"netlogo-plates\", \"%s\", \"--out\", "
            "\"plates\"]}; a Blender film: [\"netlogo-film\", \"%s\", \"--out\", \"film.mp4\"]" % (slug, rec, rec)]
    return "; ".join(tips)


def _finish_run(rec, done, tail):
    try:
        outcome = json.loads((_work(rec["id"]) / "outcome.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConstructError("the NetLogo run failed:\n%s" % tail)
    slug = rec["finish"]["slug"]
    extra = {"source": "netlogo", "preview": False, "job_id": rec["id"]}
    if outcome["kind"] == "run":
        extra["ticks"] = outcome["run"]["ticks"]
    elif outcome.get("summary"):
        extra["runs"] = outcome["summary"]["runs"]
    with _plock:
        _finished.add(rec["id"])
        result = tools.publish(slug, outcome["build"], Path(outcome["out"]), outcome["scene"], tail, extra_card=extra)
    _items(slug, outcome)
    _remember(slug, outcome)
    _event(rec["id"], slug, outcome["build"], extra.get("ticks"), True)
    _brief_audit(result)
    result.update({"view": outcome.get("view"), "files": outcome.get("files")})
    if outcome.get("why"):
        result["view_chosen_because"] = outcome["why"]
    if outcome["kind"] == "run":
        result["run"] = outcome["run"]
        result["recorded"] = outcome.get("recorded")
        if outcome["run"].get("warning"):
            result["warning"] = outcome["run"]["warning"]
    elif outcome["kind"] == "runs":
        s = dict(outcome["summary"])
        s.pop("per_run", None)
        result["summary"] = s
        result["compared"] = len(outcome.get("compared") or [])
    else:
        result["runs"] = outcome.get("runs")
    if outcome.get("constants"):
        result["constants"] = outcome["constants"]
    credit = outcome.get("credit")
    if credit:
        result["credit"] = {"line": credit["line"], "citation": credit.get("citation"), "licence": credit.get("licence"),
                            "readme": str(runtime.project_dir(slug) / "README.md")}
    result["next"] = _next(slug, outcome)
    return result


def _brief_audit(result):
    """A clean audit in a word (the report is in the build folder); one with problems in full."""
    a = result.get("audit") or {}
    if a.get("ok") and not a.get("errors"):
        result["audit"] = {"ok": True, "warnings": len(a.get("warnings") or [])}


def _remember(slug, outcome):
    """The project's record of its NetLogo side, so a redraw finds its recordings and credit."""
    try:
        folder = runtime.project_dir(slug)
    except ConstructError:
        return
    info = runtime.read_project(folder)
    nl = dict(info.get("netlogo") or {})
    files = outcome.get("files") or {}
    recs = files.get("recordings") or ([files["recording"]] if files.get("recording") else [])
    if recs and not (outcome.get("kind") == "draw" and nl.get("recordings")):   # a redraw keeps the full list
        nl["recordings"] = [str(Path(r).relative_to(folder)) if runtime.inside(r, [folder]) else r for r in recs]
    if outcome.get("compared"):
        nl["compared"] = [str(Path(r).relative_to(folder)) for r in outcome["compared"]]
    if outcome.get("credit"):
        nl["credit"] = outcome["credit"]
    nl["view"] = outcome.get("view")
    info["netlogo"] = nl
    info["scene"] = str(Path(outcome["scene"]).relative_to(folder)) if runtime.inside(outcome["scene"], [folder]) \
        else outcome["scene"]
    runtime.write_json(folder / "project.json", info)


# ---------------------------------------------------------------------------- the draw tool

def _first_title(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for _ in range(5):
                line = fh.readline()
                if not line:
                    break
                row = json.loads(line) if line.strip() else {}
                if isinstance(row, dict) and "construct-netlogo" in row:
                    return str(row.get("title") or "")[:80]
    except (OSError, ValueError):
        pass
    return ""


@tools.tool("construct_netlogo_draw")
def draw_tool(args):
    recordings, project = args.get("recordings"), args.get("project")
    if (recordings is None) == (project is None):
        raise ConstructError("give recordings (absolute .jsonl paths) or a project made by construct_netlogo_run")
    view, options, title = _view(args), _options(args), _title(args)
    model_3d = tools._bool(args, "model_3d")
    labels = _strings(args, "labels", 8, 40)
    credit, scene_name = None, "scene.json"
    if project is not None:
        slug = runtime.project_id(project)
        folder = runtime.project_dir(slug)
        info = runtime.read_project(folder)
        nl = info.get("netlogo") or {}
        names = nl.get("compared") or nl.get("recordings") or []
        paths = [(folder / n) if not Path(n).is_absolute() else Path(n) for n in names[:8]]
        if not paths:
            paths = [folder / "run.jsonl"] if (folder / "run.jsonl").is_file() else sorted((folder / "runs").glob("*.jsonl"))[:8]
        paths = [p for p in paths if p.is_file()]
        if not paths:
            raise ConstructError("project %s holds no NetLogo recording" % project)
        credit = nl.get("credit")
        scene_name = "scene-%s-%s.json" % (view, runtime.new_id())
        if labels is None and len(paths) > 1:
            labels = ["seed %s" % s if s is not None else p.stem for p, s in
                      ((p, _seed_of(p)) for p in paths)]
    else:
        if not isinstance(recordings, list) or not 1 <= len(recordings) <= 8:
            raise ConstructError("recordings must be a list of 1 to 8 absolute paths")
        paths = []
        for r in recordings:
            p = Path(str(r)).expanduser()
            if not p.is_absolute() or not p.is_file():
                raise ConstructError("%s is not an existing file (give absolute paths)" % r)
            if p.stat().st_size > 512 * 1024 * 1024:
                raise ConstructError("%s is larger than 512 MB" % r)
            paths.append(p.resolve())
        name = title or _first_title(paths[0]) or paths[0].stem
        slug, folder = runtime.new_project(name if len(paths) == 1 else "%s compared" % name)
        runtime.write_json(folder / "project.json", {"slug": slug, "title": name, "scene": "scene.json",
                                                     "origin": "netlogo-recording", "from": [str(p) for p in paths],
                                                     "created": runtime.stamp_iso(), "netlogo": {}})
    if labels is not None and len(labels) != len(paths):
        raise ConstructError("%d labels for %d recordings" % (len(labels), len(paths)))
    if len(paths) > 1 and model_3d:
        raise ConstructError("model_3d is for one recording")
    art = None
    if args.get("art") is not None:
        if len(paths) > 1:
            raise ConstructError("art is for one recording")
        a = Path(str(args["art"])).expanduser()
        a = a if a.is_absolute() else folder / a
        if not a.is_file():
            raise ConstructError("no art layer at %s" % a)
        art = str(a.resolve())
    found = find_netlogo()
    spec = {"project": str(folder), "recordings": [str(p) for p in paths], "view": view, "options": options,
            "title": title, "labels": labels, "model_3d": model_3d, "art": art, "credit": credit,
            "scene_name": scene_name, "library": (found or {}).get("models")}
    label = "drawing of %s" % slug
    job_id = jobs.start("netlogo-draw", "netlogo-draw", project=slug, label=label, cwd=folder, spec=spec,
                        finish={"slug": slug})
    return tools._waited(job_id, "netlogo-draw", DRAW_WAIT, label)


def _seed_of(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        return row.get("seed") if isinstance(row, dict) else None
    except (OSError, ValueError):
        return None


def _finish_draw(rec, done, tail):
    try:
        outcome = json.loads((_work(rec["id"]) / "outcome.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConstructError("the drawing failed:\n%s" % tail)
    slug = rec["finish"]["slug"]
    result = tools.publish(slug, outcome["build"], Path(outcome["out"]), outcome["scene"], tail,
                           extra_card={"source": "netlogo"})
    files = outcome.get("files") or {}
    folder = runtime.project_dir(slug)
    for r in files.get("recordings", []):   # only the copies this drawing made: a project's own are listed already
        if runtime.inside(r, [folder]) and not any(i.get("path") == r for i in _listed(slug)):
            runtime.record_item(slug, "run", r, Path(r).name)
    if files.get("counts_csv"):
        runtime.record_item(slug, "file", files["counts_csv"], "Counts at every record (CSV)")
    if files.get("glb"):
        runtime.record_item(slug, "export", files["glb"], "3D model of the run (glb)")
    _remember(slug, dict(outcome, kind="draw"))
    _brief_audit(result)
    result.update({"view": outcome.get("view"), "runs": outcome.get("runs"), "files": files})
    if outcome.get("why"):
        result["view_chosen_because"] = outcome["why"]
    credit = outcome.get("credit")
    if credit:
        result["credit"] = {"line": credit["line"], "citation": credit.get("citation"), "licence": credit.get("licence"),
                            "readme": str(folder / "README.md")}
    result["next"] = _next(slug, outcome)
    return result


def _listed(slug):
    try:
        items = json.loads((runtime.shown_root() / slug / "items.json").read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


jobs.register_finisher("netlogo-run", _finish_run)
jobs.register_finisher("netlogo-draw", _finish_draw)

HANDLERS = {"construct_netlogo_run": run_tool, "construct_netlogo_draw": draw_tool}
CHECKS = {"construct_netlogo_run": ready}
