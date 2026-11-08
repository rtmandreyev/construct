"""The NetLogo ops of child.py (run in the child process, never imported by Hermes).

    netlogo-run <spec.json>    instrument a model, run it headless (once, or N seeded runs as one BehaviorSpace
                               experiment), draw the run(s) and build the construct; small single runs are drawn
                               every few seconds while they run (previews)
    netlogo-draw <spec.json>   draw recorded runs (one, or two to eight side by side) and build the construct

Both write into the job's work folder: progress.json (ticks done, for the job's progress), previews.json (the
preview builds, newest last, for the plugin to show) and outcome.json (what was made, for the plugin's result).
Everything else they write is inside the project folder the spec names.
"""

import html
import json
import os
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

PLACEHOLDER = "construct-run-placeholder.jsonl"
PREVIEW_EVERY = 4.0         # seconds before the first preview; each next one waits twice as long as the last
PREVIEW_MAX = 4             # previews per run at most: with the final build, all stay among the builds a project keeps
PREVIEW_BYTES = 4 << 20     # a recording larger than this is not previewed (a preview must build in a few seconds)
PREVIEW_SLOW = 6.0          # a preview that took longer than this ends the previews
MAX_SECONDS = 3 * 3600      # a run that takes longer than this is stopped
COMPARED = 8                # runs drawn side by side at most (Construct's limit); the summary covers all


def run(op, args):
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if op == "netlogo-run":
        return run_model(spec)
    if op == "netlogo-draw":
        return draw(spec)
    sys.stderr.write("unknown op %r\n" % op)
    return 2


# ---------------------------------------------------------------------------- small helpers

def _build_id():
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def _write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(".%s.%s.tmp" % (path.name, secrets.token_hex(3)))
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _say(text):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _fail(text):
    sys.stderr.write(text.rstrip() + "\n")
    return 1


# ---------------------------------------------------------------------------- the model's credit and licence

def credit_of(text, path, library=None):
    """The credit and licence a model carries in its Info tab (the Models Library's own wording), or None for a
    model that names no licence and is not in the library."""
    in_library = False
    if library:
        try:
            Path(path).resolve().relative_to(Path(library).resolve())
            in_library = True
        except ValueError:
            pass
    m = re.search(r"<info>(.*?)</info>", text, re.S)
    info = m.group(1) if m else ""
    if info.startswith("<![CDATA["):
        info = info[9:-3] if info.endswith("]]>") else info[9:]
    else:
        info = html.unescape(info)
    lic = re.search(r"Attribution-NonCommercial-ShareAlike\s*(\d\.\d)?", info)
    if not lic and not in_library:
        return None
    cite = re.search(r"For the model itself:\s*\*\s*([^\n]+)", info)
    copy = re.search(r"(?m)Copyright\s+(\d{4}(?:\s*[-,]\s*\d{4})*)\s+(.+?)\.?[ \t]*$", info)
    url = re.search(r"https?://ccl\.northwestern\.edu/netlogo/models/[A-Za-z0-9_%-]+", info)
    name = Path(path).stem
    version = (lic.group(1) if lic and lic.group(1) else "3.0") if lic else None
    out = {"model": name, "library": in_library,
           "citation": " ".join(cite.group(1).split()).strip() if cite else None,
           "copyright": "© %s %s" % (copy.group(1), copy.group(2).strip()) if copy else None,
           "url": url.group(0) if url else None}
    if version:
        out["licence"] = "CC BY-NC-SA %s" % version
        out["licence_url"] = "https://creativecommons.org/licenses/by-nc-sa/%s/" % version
    else:
        out["licence"] = None
        out["licence_url"] = None
    out["line"] = "%s%s%s" % (
        out["copyright"] + ", " if out["copyright"] else "",
        "NetLogo Models Library" if in_library else "the model's author",
        ", licensed under %s" % out["licence"] if out["licence"] else " (see the model's Info tab for its licence)")
    return out


def credit_scene(sc, credit):
    """The construct with the model's credit: a source naming the model and two facts (outside the data lock)."""
    if not credit:
        return sc
    title = credit.get("citation") or "%s, %s" % (credit["model"], credit["line"])
    src = {"id": "model", "kind": "document", "title": title[:300], "rights": "reference_only"}
    if credit.get("url"):
        src["ref"] = credit["url"]
    sc["sources"] = [s for s in sc.get("sources", []) if s.get("id") != "model"] + [src]
    facts = [f for f in sc.get("facts", []) if f.get("key") not in ("model_credit", "model_licence")]
    facts.append({"key": "model_credit", "value": ("%s: %s" % (credit["model"], credit["line"]))[:300],
                  "certainty": "verified", "source": "model"})
    if credit.get("licence"):
        facts.append({"key": "model_licence", "value": "%s (%s)" % (credit["licence"], credit["licence_url"]),
                      "certainty": "verified", "source": "model",
                      "note": "This construct, its recording and its model copy derive from the model, so they are "
                              "under the model's licence: non-commercial use, share alike, keep the credit."})
    sc["facts"] = facts
    subject = dict(sc.get("subject") or {})
    summary = subject.get("summary", "")
    tail = " Model: %s." % credit["line"]
    if tail not in summary:
        subject["summary"] = (summary + tail)[:1200]
    sc["subject"] = subject
    return sc


def write_readme(folder, credit, what):
    """README.md in the project: how the construct was made, and for a credited model its credit and licence."""
    lines = ["# %s" % what["title"], "", what["how"], ""]
    if credit:
        lines += ["**Credit:** %s%s." % (credit.get("citation") or credit["model"],
                                          "" if not credit.get("copyright") else " %s" % credit["copyright"]), ""]
        if credit.get("licence"):
            lines += ["**License:** everything in this folder derives from the model (its instrumented copy, the "
                      "recordings, the scene and its builds), so it is under [%s](%s), not under Construct's own "
                      "licence: non-commercial use only, share alike, and keep this credit." % (
                          credit["licence"], credit["licence_url"]), ""]
        else:
            lines += ["**License:** the model's own licence (its Info tab) applies to everything in this folder.", ""]
    Path(folder, "README.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------- what to record

def model_settings(text):
    """The model's settings: its sliders, switches, choosers and inputs, by variable."""
    out = {}
    for m in re.finditer(r"<slider\b([^>]*)>", text):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if a.get("variable"):
            out[a["variable"]] = {"kind": "slider", "min": a.get("min"), "max": a.get("max"), "default": a.get("default")}
    for m in re.finditer(r"<switch\b([^>]*)>", text):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if a.get("variable"):
            out[a["variable"]] = {"kind": "switch", "default": a.get("on") == "true"}
    for m in re.finditer(r"<chooser\b([^>]*)>(.*?)</chooser>", text, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        choices = [html.unescape(c) for c in re.findall(r'<choice[^>]*value="([^"]*)"', m.group(2))]
        if a.get("variable"):
            cur = int(a.get("current", "0") or 0)
            out[a["variable"]] = {"kind": "chooser", "choices": choices,
                                  "default": choices[cur] if 0 <= cur < len(choices) else None}
    for m in re.finditer(r"<input\b([^>]*)>", text):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if a.get("variable"):
            out[a["variable"]] = {"kind": "input", "type": a.get("type")}
    return out


def _code(text):
    m = re.search(r"<code><!\[CDATA\[(.*?)\]\]></code>", text, re.S)
    if m:
        return m.group(1)
    m = re.search(r"<code>(.*?)</code>", text, re.S)
    return html.unescape(m.group(1)) if m else ""


def auto_record(text):
    """What Construct's NetLogo extension records without being told (construct:run): each true-or-false turtle
    variable (by NetLogo's naming, a ? at the end), hidden? when the model hides turtles, each breed's count and the
    patches' colours (every few ticks in a large world)."""
    code = re.sub(r";[^\n]*", "", _code(text))
    turtles = []
    for m in re.finditer(r"(?mi)^\s*turtles-own\s*\[([^\]]*)\]", code):   # a breed's own would fail on the others
        for v in m.group(1).split():
            v = v.lower()
            if v.endswith("?") and v not in turtles:
                turtles.append(v)
    if re.search(r"(?i)(\bhide-turtle\b|\bht\b|\bset\s+hidden\?)", code) and "hidden?" not in turtles:
        turtles.append("hidden?")
    breeds = [b.lower() for b in re.findall(r"(?mi)^\s*breed\s*\[\s*([^\s\]]+)", code)]
    reporters = ["count %s" % b for b in breeds]
    view = re.search(r"<view(?:3d)?\b([^>]*)>", text)
    patches = None
    if view and "<view3d" not in text:
        a = dict(re.findall(r'(\w+)="([^"]*)"', view.group(1)))
        try:
            n = (int(a["maxPxcor"]) - int(a["minPxcor"]) + 1) * (int(a["maxPycor"]) - int(a["minPycor"]) + 1)
        except (KeyError, ValueError):
            n = 1089
        patches = ("pcolor", max(1, min(4, -(-n // 16000))))
    return {"turtles": turtles[:8], "reporters": reporters[:8], "patches": patches, "no_turtles": False, "every": 1}


def _value_xml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return html.escape('"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"'), quote=True)


# ---------------------------------------------------------------------------- the run

def instrument(spec, text):
    """The instrumented copy (recording run-<seed>.jsonl beside it), construct.nls and the experiment, in
    <project>/netlogo/. Returns (model path, experiment path, what is recorded)."""
    from construct_hologram import netlogo as nl
    rec = spec.get("record") or auto_record(text)
    patches = rec.get("patches")
    if isinstance(patches, str):
        rep, _, every = patches.rpartition(":")
        patches = (rep, int(every)) if rep and every.isdigit() else (patches, 1)
    model, xml = nl.instrument(text, spec["model_title"], PLACEHOLDER, rec.get("turtles") or [], rec.get("reporters") or [],
                               patches, int(rec.get("every") or 1), None, int(spec["ticks"]),
                               bool(rec.get("no_turtles")), spec.get("setup"), spec.get("go"))
    base = int(spec["seed"])
    seed_expr = "(%d + behaviorspace-run-number - 1)" % base
    file_expr = '(word "run-" %s ".jsonl") construct-seed %s' % (seed_expr, seed_expr)
    quoted = json.dumps(PLACEHOLDER)
    if quoted not in model and quoted not in xml:
        raise RuntimeError("the recorder could not be placed in the model")
    model, xml = model.replace(quoted, file_expr), xml.replace(quoted, file_expr)
    xml = xml.replace('repetitions="1"', 'repetitions="%d"' % int(spec["runs"]), 1)
    xml = xml.replace("<setup>", "<setup>random-seed %s\n" % seed_expr, 1)
    constants = spec.get("constants") or {}
    if constants:
        sets = "".join('        <enumeratedValueSet variable="%s"><value value="%s"></value></enumeratedValueSet>\n' % (
            html.escape(k, quote=True), _value_xml(v)) for k, v in sorted(constants.items()))
        xml = xml.replace("    </metrics>\n", "    </metrics>\n    <constants>\n%s    </constants>\n" % sets, 1)
    out = Path(spec["project"]) / "netlogo"
    out.mkdir(parents=True, exist_ok=True)
    src = Path(spec["model"])
    suffix = src.suffix if src.suffix.lower().startswith(".nlogox") else ".nlogox"
    target = out / (src.name[:-len(src.suffix)] + "-construct" + suffix)
    target.write_text(model, encoding="utf-8")
    shutil.copyfile(nl.NLS, out / "construct.nls")
    exp = out / "construct-experiment.xml"
    exp.write_text(xml, encoding="utf-8")
    recorded = {"turtles": ([] if rec.get("no_turtles") else ["who", "breed", "xcor", "ycor", "color"]) + list(rec.get("turtles") or []),
                "reporters": list(rec.get("reporters") or []),
                "patches": "%s every %d ticks" % patches if patches else None, "every": int(rec.get("every") or 1),
                "chosen_by": "you" if spec.get("record") else "Construct (true/false turtle variables, breed counts, "
                                                              "patch colours)"}
    return target, exp, recorded


def headless_argv(spec, model, experiment, table):
    nlg = spec["netlogo"]
    argv = [nlg["java"], "-XX:MaxRAMPercentage=50", "-Dfile.encoding=UTF-8", "-Djava.awt.headless=true"]
    if nlg.get("extensions"):
        argv.append("-Dnetlogo.extensions.dir=" + nlg["extensions"])
    if nlg.get("models"):
        argv.append("-Dnetlogo.models.dir=" + nlg["models"])
    if str(model).lower().endswith(".nlogox3d"):
        argv.append("-Dorg.nlogo.is3d=true")
    return argv + ["-cp", nlg["jar"], "org.nlogo.headless.Main", "--model", str(model), "--setup-file", str(experiment),
                   "--experiment", "construct", "--threads", "1", "--table", str(table)]


class _Tail:
    """Follows a growing recording: the last record's tick, read incrementally (each byte once)."""

    def __init__(self, path):
        self.path, self.offset, self.rest, self.t, self.frames = Path(path), 0, b"", None, 0

    def poll(self):
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read()
        except OSError:
            return self.t
        self.offset += len(data)
        buf = self.rest + data
        lines = buf.split(b"\n")
        self.rest = lines.pop()
        for line in lines:
            m = re.match(rb'\{"t":(-?[0-9.eE+-]+)', line)
            if m:
                try:
                    self.t = float(m.group(1))
                    self.frames += 1
                except ValueError:
                    pass
        return self.t

    def complete(self):
        """The recording's complete lines so far (bytes)."""
        return self.offset - len(self.rest)


def _run_number(p):
    m = re.match(r"run-(-?\d+)\.jsonl$", p.name)
    return int(m.group(1)) if m else None


def _recordings(folder):
    return sorted((p for p in Path(folder).glob("run-*.jsonl") if _run_number(p) is not None),
                  key=lambda p: (p.stat().st_mtime, _run_number(p)))


def run_model(spec):
    from construct_hologram import netlogo as nl
    work, project = Path(spec["work"]), Path(spec["project"])
    work.mkdir(parents=True, exist_ok=True)
    text = Path(spec["model"]).read_text(encoding="utf-8")
    credit = credit_of(text, spec["model"], (spec.get("netlogo") or {}).get("models"))
    try:
        model, experiment, recorded = instrument(spec, text)
    except (nl.NetLogoError, RuntimeError) as exc:
        return _fail("netlogo-instrument: %s" % exc)
    runs, ticks = int(spec["runs"]), int(spec["ticks"])
    total = runs * ticks
    progress = work / "progress.json"
    _write_json(progress, {"total": total, "done": 0, "unit": "ticks"})
    log = open(work / "netlogo.log", "w", encoding="utf-8")
    argv = headless_argv(spec, model, experiment, work / "table.csv")
    _say("netlogo: %s" % " ".join(argv[-12:]))
    started = time.time()
    try:
        from construct_hologram import procenv
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                cwd=spec["netlogo"]["folder"], env=procenv.minimal(procenv.JAVA))
    except OSError as exc:
        log.close()
        return _fail("NetLogo could not start: %s" % exc)
    tails, previews, last_preview = {}, [], started
    live = runs == 1 and spec.get("live", True)
    try:
        while proc.poll() is None:
            time.sleep(1.0)
            if time.time() - started > MAX_SECONDS:
                proc.kill()
                return _fail("NetLogo ran longer than %d hours and was stopped" % (MAX_SECONDS // 3600))
            files = _recordings(model.parent)
            done = 0.0
            for i, f in enumerate(files):
                tail = tails.setdefault(f.name, _Tail(f))
                t = tail.poll() or 0.0
                done += ticks if i < len(files) - 1 else min(ticks, t)
            _write_json(progress, {"total": total, "done": int(min(total, done)), "unit": "ticks",
                                   "runs_done": max(0, len(files) - 1), "runs": runs})
            if live and files and len(previews) < PREVIEW_MAX and \
                    time.time() - last_preview >= PREVIEW_EVERY * 2 ** len(previews):
                last_preview = time.time()
                tail = tails[files[-1].name]
                if tail.frames >= 3 and tail.complete() <= PREVIEW_BYTES and \
                        (not previews or previews[-1]["ticks"] != tail.t):
                    took = time.time()
                    shown = preview(spec, files[-1], tail, credit)
                    if shown:
                        previews.append(shown)
                        _write_json(work / "previews.json", previews)
                    if time.time() - took > PREVIEW_SLOW:
                        live = False
    finally:
        if proc.poll() is None:
            proc.kill()
        log.close()
    code = proc.returncode
    files = sorted(_recordings(model.parent), key=_run_number)
    out_log = (work / "netlogo.log").read_text(encoding="utf-8", errors="replace")
    if not files:
        return _fail("NetLogo made no recording (exit %s). Its output:\n%s" % (code, out_log.strip()[-3000:]))
    good = []
    for f in files:
        try:
            good.append((f, nl.read_run(f)))
        except nl.NetLogoError as exc:
            _say("skipped %s: %s" % (f.name, exc))
    if not good:
        return _fail("NetLogo's recordings could not be read (exit %s). Its output:\n%s" % (code, out_log.strip()[-3000:]))
    if code != 0:
        _say("NetLogo exited with %s; drawing the %d recording(s) it made. Its output:\n%s" % (
            code, len(good), out_log.strip()[-1500:]))
    _write_json(progress, {"total": total, "done": total, "unit": "ticks", "runs_done": len(good), "runs": runs})
    about = {"model": spec["model"], "model_title": spec["model_title"], "recorded": recorded,
             "constants": spec.get("constants") or {}, "ticks_limit": ticks, "credit": credit,
             "instrumented": str(model), "previews": len(previews), "seconds": round(time.time() - started, 1),
             "seed_base": int(spec["seed"]),
             "steps": {str(k): v for k, v in table_steps(work / "table.csv").items()}}
    if len(good) == 1:
        return _finish_one(spec, good[0], about)
    return _finish_many(spec, good, about)


def _opts(spec):
    o = dict(spec.get("options") or {})
    if "smooth" in o and o["smooth"] is not None:
        o["smooth"] = int(o["smooth"])
    return o


def _draw_one(run, spec, title=None):
    """(scene, view, why) for one recording, as `construct netlogo --view ...` draws it."""
    from construct_hologram import netlogo as nl
    view, why = spec.get("view") or "auto", None
    if view == "auto":
        picked, _, why = nl.choose_view(run)
        if picked == "field":
            try:
                nl.scene_from_run(run, "field")
            except nl.NetLogoError:
                picked, _, why = nl.choose_view(run, exclude=("field",))
                why += "; the patches changed all at once"
    opts = _opts(spec)
    sc = nl.scene_from_run(run, view, title or spec.get("title"), solid=bool(spec.get("model_3d")), **opts)
    drawn = next((f["value"] for f in sc["facts"] if f["key"] == "view"), view)
    return sc, drawn, why


def preview(spec, path, tail, credit):
    """A build of the run so far (its complete records), into the project's builds folder."""
    from construct_hologram import netlogo as nl, studio
    try:
        with open(path, "rb") as fh:
            data = fh.read(tail.complete())
        run = nl.parse_run(data.decode("utf-8", errors="replace"))
        sc, _, _ = _draw_one(run, dict(spec, model_3d=False))
        t = run["frames"][-1]["t"]
        sc["title"] = ("%s (running: tick %s)" % (sc["title"], _tick(t)))[:120]
        sc = credit_scene(sc, credit)
        work = Path(spec["work"])
        scene_path = work / "preview-scene.json"
        scene_path.write_text(json.dumps(sc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        build = _build_id()
        out = Path(spec["project"]) / "builds" / build
        studio.build(str(scene_path), str(out))
        return {"build": build, "out": str(out), "scene": str(scene_path), "ticks": t, "at": time.time()}
    except Exception as exc:   # a preview is a nicety: the run goes on without it
        _say("preview skipped: %s: %s" % (type(exc).__name__, exc))
        return None


def _tick(t):
    return "%d" % t if float(t).is_integer() else "%g" % t


def _build(scene_path, out, thumb=True):
    from construct_hologram import render, studio
    geometry, report, text = studio.build(str(scene_path), str(out))
    page = Path(out) / "construct.html"
    if thumb and page.is_file() and render.find_browser():
        try:
            shot = render.stills(str(page), str(out), ["hero"], 480, 300)
            if shot:
                os.replace(shot[0], Path(out) / "thumb.png")
        except Exception as exc:   # a still for the gallery is a nicety
            sys.stderr.write("thumbnail: %s\n" % exc)
    return report


def _write_scene(path, sc):
    Path(path).write_text(json.dumps(sc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")


def _end(run):
    return run["end"] if run["end"] is not None else run["frames"][-1]["t"]


def _finals(run):
    """The run's last values: each recorded reporter, and each breed's turtles."""
    h, last = run["header"], run["frames"][-1]
    out = {}
    for name, v in zip(h.get("reporters", []), last.get("reporters") or []):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[name] = v
    if "turtles" in last:
        breeds = {}
        for row in last["turtles"]:
            breeds[row[1]] = breeds.get(row[1], 0) + 1
        for b, n in sorted(breeds.items()):
            out.setdefault("count %s" % b, n)
    return out


def _run_info(run, limit, steps=None):
    """A run in brief. `steps`: how many times BehaviorSpace ran go (its table), when known."""
    h = run["header"]
    end = _end(run)
    out = {"seed": h.get("seed"), "ticks": end, "records": len(run["frames"]), "netlogo": h.get("netlogo"),
           "stopped_by_itself": (steps < limit) if steps is not None else end < limit, "final": _finals(run)}
    whole = all(float(f["t"]).is_integer() for f in run["frames"][-50:])
    if steps is not None and steps >= limit and end < steps and whole and h.get("clock") != "steps":
        out["warning"] = ("go ran %d times but the clock stopped at tick %s: after that go probably failed each time "
                          "(NetLogo does not report a model's errors when it runs headless); open the model in NetLogo "
                          "and run it to see the error" % (steps, _tick(end)))
    return out


def table_steps(path):
    """BehaviorSpace's table: how many steps (runs of go) each run number took."""
    import csv
    try:
        rows = list(csv.reader(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()))
    except OSError:
        return {}
    out = {}
    for i, r in enumerate(rows):
        if r[:2] == ["[run number]", "[step]"]:
            for row in rows[i + 1:]:
                try:
                    out[int(row[0])] = int(float(row[1]))
                except (ValueError, IndexError):
                    continue
            break
    return out


def _steps_of(run, about):
    seed = run["header"].get("seed")
    if not isinstance(seed, int):
        return None
    return about.get("steps", {}).get(str(seed - about["seed_base"] + 1))


def _extras(spec, sc, run, project, stem):
    """counts.csv, and for model_3d the material map beside the scene and the .glb (<stem>.glb)."""
    from construct_hologram import export as export_mod, netlogo as nl
    files = {}
    csv = project / "counts.csv"
    csv.write_text(nl.counts_csv(run), encoding="utf-8")
    files["counts_csv"] = str(csv)
    if spec.get("model_3d"):
        mats = nl.materials_from_run(run, sc)
        mpath = project / "scene.materials.json"
        mpath.write_text(json.dumps(mats, indent=1) + "\n", encoding="utf-8")
        glb = project / "exports" / ("%s.glb" % stem)
        glb.parent.mkdir(parents=True, exist_ok=True)
        export_mod.export(sc, str(glb), wire="tubes", materials=mats)
        files["glb"], files["materials"] = str(glb), str(mpath)
    return files


def _finish_one(spec, item, about):
    from construct_hologram import netlogo as nl
    path, run = item
    project = Path(spec["project"])
    target = project / "run.jsonl"
    shutil.move(str(path), str(target))
    try:
        sc, view, why = _draw_one(nl.read_run(target), spec)
    except nl.NetLogoError as exc:
        return _fail("netlogo: the run was recorded (%s) but could not be drawn: %s" % (target, exc))
    sc = credit_scene(sc, about["credit"])
    scene = project / "scene.json"
    _write_scene(scene, sc)
    files = {"recording": str(target), "scene": str(scene)}
    files.update(_extras(spec, sc, run, project, "run"))
    build = _build_id()
    out = project / "builds" / build
    report = _build(scene, out)
    info = _run_info(run, about["ticks_limit"], _steps_of(run, about))
    write_readme(project, about["credit"], {
        "title": "%s: a NetLogo run" % sc["title"],
        "how": "One run of %s, run headless in NetLogo %s (random-seed %s, %s ticks%s) with Construct's recorder, "
               "and drawn as a construct (view %s) from the recording alone. `run.jsonl` is the recording, "
               "`scene.json` the construct, `netlogo/` the instrumented copy of the model (open it in NetLogo to run it "
               "again)." % (about["model_title"], info["netlogo"], info["seed"], _tick(info["ticks"]),
                            ", stopped by itself" if info["stopped_by_itself"] else "", view)})
    _write_json(Path(spec["work"]) / "outcome.json", dict(about, kind="run", build=build, out=str(out), scene=str(scene),
                                                          files=files, view=view, why=why, run=info,
                                                          audit_ok=report.get("ok")))
    _say("drew %s (view %s): %s" % (target, view, out))
    return 0


def summarize(runs, limit, about=None):
    """Across runs: each final value's min, median, mean and max, the ticks the runs ended at, and how many stopped
    by themselves."""
    infos = [_run_info(r, limit, _steps_of(r, about) if about else None) for r in runs]
    names = []
    for i in infos:
        names += [n for n in i["final"] if n not in names]
    stat = lambda xs: {"min": min(xs), "median": statistics.median(xs), "mean": round(statistics.fmean(xs), 4),
                       "max": max(xs), "runs": len(xs)}
    finals = {n: stat([i["final"][n] for i in infos if n in i["final"]]) for n in names[:24]}
    return {"runs": len(infos), "seeds": [i["seed"] for i in infos], "ticks": stat([i["ticks"] for i in infos]),
            "stopped_by_itself": sum(1 for i in infos if i["stopped_by_itself"]), "final": finals,
            "warnings": [("seed %s: " % i["seed"]) + i["warning"] for i in infos if i.get("warning")][:8],
            "per_run": [{"seed": i["seed"], "ticks": i["ticks"], "final": i["final"]} for i in infos]}


def _evenly(n, k):
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def _finish_many(spec, good, about):
    from construct_hologram import netlogo as nl
    project = Path(spec["project"])
    folder = project / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    moved = []
    for path, run in good:
        target = folder / ("run-%s.jsonl" % run["header"].get("seed", _run_number(path)))
        shutil.move(str(path), str(target))
        moved.append((target, run))
    runs = [r for _, r in moved]
    summary = summarize(runs, about["ticks_limit"], about)
    pick = _evenly(len(runs), COMPARED)
    shown = [runs[i] for i in pick]
    labels = ["seed %s" % r["header"].get("seed") for r in shown]
    try:
        sc = nl.compare(shown, spec.get("view") or "auto", labels, spec.get("title"), **_opts(spec))
    except nl.NetLogoError as exc:
        return _fail("netlogo-compare: the runs were recorded (%s) but could not be drawn: %s" % (folder, exc))
    sc = credit_scene(sc, about["credit"])
    scene = project / "scene.json"
    _write_scene(scene, sc)
    _write_json(project / "summary.json", summary)
    view = next((f["value"] for f in sc["facts"] if f["key"] == "view"), spec.get("view"))
    build = _build_id()
    out = project / "builds" / build
    report = _build(scene, out)
    write_readme(project, about["credit"], {
        "title": "%s: %d NetLogo runs" % (about["model_title"], len(runs)),
        "how": "%d runs of %s, run headless in NetLogo as one BehaviorSpace experiment with seeds %s, recorded with "
               "Construct's recorder (`runs/`), %s drawn side by side as a construct (`scene.json`, view %s), and "
               "summarised across all runs in `summary.json`." % (
                   len(runs), about["model_title"], ", ".join(str(s) for s in summary["seeds"][:12]) +
                   (" ..." if len(runs) > 12 else ""), "all" if len(shown) == len(runs) else "%d of them" % len(shown),
                   view)})
    files = {"recordings": [str(p) for p, _ in moved], "scene": str(scene), "summary": str(project / "summary.json")}
    _write_json(Path(spec["work"]) / "outcome.json", dict(about, kind="runs", build=build, out=str(out), scene=str(scene),
                                                          files=files, view=view, summary=summary,
                                                          compared=[str(moved[i][0]) for i in pick],
                                                          audit_ok=report.get("ok")))
    _say("drew %d runs side by side: %s" % (len(shown), out))
    return 0


# ---------------------------------------------------------------------------- recorded runs

def find_credit(run, path, library):
    """A recorded run's model credit: the model beside the recording (as the recorder leaves it), else the library
    model of the recording's title."""
    title = str(run["header"].get("title") or "")
    cands = []
    for p in sorted(Path(path).parent.glob("*.nlogox*")):
        cands.append(p)
    if library and title and re.match(r"^[\w .,'()&+-]{1,80}$", title):
        lib = Path(library)
        if lib.is_dir():
            cands += [p for p in lib.rglob("*.nlogox*") if p.stem.lower() == title.lower()]
    for p in cands:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        c = credit_of(text, p, library)
        if c:
            c["model"] = title or c["model"]
            return c
    return None


def draw(spec):
    from construct_hologram import netlogo as nl
    project = Path(spec["project"])
    work = Path(spec["work"])
    work.mkdir(parents=True, exist_ok=True)
    paths, runs = [], []
    for i, src in enumerate(spec["recordings"]):
        src = Path(src)
        try:
            run = nl.read_run(src)
        except (nl.NetLogoError, OSError, UnicodeDecodeError) as exc:
            return _fail("%s: %s" % (src, exc))
        try:
            src.resolve().relative_to(project.resolve())
            target = src
        except ValueError:   # a recording from elsewhere: copied into the project, which then holds all it shows
            target = project / ("run.jsonl" if len(spec["recordings"]) == 1 else "runs/%d-%s" % (i + 1, src.name))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        paths.append(target)
        runs.append(run)
    credit = spec.get("credit") or find_credit(runs[0], spec["recordings"][0], spec.get("library"))
    stem = spec.get("scene_name") or "scene.json"
    scene = project / stem
    files = {"recordings": [str(p) for p in paths], "scene": str(scene)}
    why = None
    try:
        if len(runs) == 1:
            sc, view, why = _draw_one(runs[0], spec)
            if spec.get("art"):
                sc = nl.apply_art(sc, json.loads(Path(spec["art"]).read_text(encoding="utf-8")))
        else:
            labels = spec.get("labels") or None
            sc = nl.compare(runs, spec.get("view") or "auto", labels, spec.get("title"), **_opts(spec))
            view = next((f["value"] for f in sc["facts"] if f["key"] == "view"), spec.get("view"))
    except (nl.NetLogoError, ValueError, OSError) as exc:
        return _fail("netlogo: %s" % exc)
    sc = credit_scene(sc, credit)
    _write_scene(scene, sc)
    if len(runs) == 1:
        files.update(_extras(spec, sc, runs[0], project, "run"))
    build = _build_id()
    out = project / "builds" / build
    report = _build(scene, out)
    if not (project / "README.md").is_file() or credit:
        write_readme(project, credit, {
            "title": sc["title"],
            "how": "%s drawn as a construct (view %s) from %s alone, with Construct's NetLogo bridge." % (
                "A NetLogo run" if len(runs) == 1 else "%d NetLogo runs side by side" % len(runs), view,
                "its recording" if len(runs) == 1 else "their recordings")})
    info = [_run_info(r, float("inf")) for r in runs]
    for i in info:
        i.pop("stopped_by_itself", None)
    _write_json(work / "outcome.json", {"kind": "draw", "build": build, "out": str(out), "scene": str(scene),
                                        "files": files, "view": view, "why": why, "runs": info, "credit": credit,
                                        "audit_ok": report.get("ok")})
    _say("drew %d recording(s) (view %s): %s" % (len(runs), view, out))
    return 0
