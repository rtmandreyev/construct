"""The NetLogo bridge: record a run with construct.nls, then turn the recording into a construct.

  instrument(model, title, ...)   a copy of a NetLogo model that records itself, and a BehaviorSpace
                                  experiment to run it headless
  read_run(path)                  the recording (JSON Lines: a header, one line per record)
  scene_from_run(run, view, ...)  a construct-scene v2, deterministically, without a model:

    space-time    each turtle's track, rising with time (the floor is the world, height is ticks)
    network-time  the network on the floor; a node rises to the tick a turtle variable first turned
                  true, and the links between risen nodes climb from the earlier to the later
    phase         two reporters as the floor's axes, time as height: the phase portrait, rising
    field         the front of change: where each patch's reporter first (or last) changed, drawn every
                  few ticks and raised to its tick (isochrones), nothing where nothing changed
    pulse         a state turtles switch on and off again and again (a flash): one ring per tick, its area the
                  share of turtles in that state, so turtles in step make wide plates with nothing between

Moving turtles (space-time) and turtles that switch on and off (pulse) are measured by their order (alignment,
synchrony); when it forms early in a long run, the construct is drawn over that window (settle_window), and says so.

Every data part is `verified` against the recording (a `dataset` source naming the model, NetLogo's
version and the seed); the build rises from the floor, so a construct's assembly replays the run.

  data_lock(scene)                the fingerprint of what the recording says, kept as the `data_lock`
                                  fact; the audit refuses a scene whose data no longer matches it
  apply_art(scene, art)           an art-direction layer on top: views, emphasis, labels, milestones
                                  and callouts, never the data

Python standard library only.
"""

import hashlib
import html
import json
import math
import re
from pathlib import Path
from xml.sax.saxutils import escape

from . import product

FLOOR = 10.0         # metres: the world's longer side on the floor
HEIGHT = 6.0         # metres: tick 0 to the last tick (a space-time cube is as tall as it is wide)
SOLID_NODES = 200    # --solid: at most this many turtles as spheres (a scene holds 256 parts)
SOLID_TUBES = 12     # --solid: the phase cycle as at most this many tubes of MAX_TUBE points
MAX_TUBE = 64        # points in one tube (the scene's limit)
MAX_SEGMENTS = 18000  # of the line budget (24,000), for the data; the scene stays under 1 MB
VIEWS = ("space-time", "network-time", "phase", "field", "pulse")
NLS = Path(__file__).resolve().parent / "construct.nls"   # the recorder, copied beside a model
TONES = ("identity", "data", "accent", "bright", "dust", "structure")
# each view's hero: a field's fronts climb like a slope, so it is seen from above its rise
FRAMING = {"space-time": {"yaw": 32, "pitch": 20}, "network-time": {"yaw": 30, "pitch": 26},
           "phase": {"yaw": 35, "pitch": 24}, "field": {"yaw": -38, "pitch": 46},
           "pulse": {"yaw": 30, "pitch": 16}}


LOCK = "data_lock"     # the fact that holds the fingerprint
LOCKED_FACTS = ("view", "coordinates")   # the bridge's own facts beside the run's: how the data is drawn
LOOSE = ("label", "look", "note")        # how a data part is shown, which art direction may change
ART_KEYS = {"title", "summary", "credit", "facts", "parts", "annotations", "looks", "presentation", "animation",
            "legend", "reading"}


class NetLogoError(ValueError):
    pass


# ---------------------------------------------------------------------------- the model

def _list(items):
    return "[" + " ".join(json.dumps(i) for i in items) + "]"


def _buttons(text):
    """The Interface's buttons, in order: (command, forever?, kind: Observer, Turtle, Patch or Link)."""
    out = []
    for m in re.finditer(r"<button([^>]*)>([^<]*)</button>", text):
        attrs, cmd = m.group(1), html.unescape(m.group(2)).strip()
        kind = re.search(r'kind="(\w+)"', attrs)
        if cmd:
            out.append((cmd, 'forever="true"' in attrs, kind.group(1) if kind else "Observer"))
    return out


def instrument(text, title, run_file, turtles=(), reporters=(), patches=None, every=1, seed=None, ticks=500,
               skip_turtles=False, setup=None, go=None):
    """A NetLogo model (.nlogox text) that records itself: `__includes ["construct.nls"]`, the recording
    set up after setup's `reset-ticks`, `construct-record` after go's `tick` (in a procedure they call,
    when not in their own body; at the end of setup and go in a model that never ticks). Setup and go
    are the model's `setup` and `go`, else the commands of its own buttons. Returns (model text,
    experiment XML for `NetLogo_Console --headless --setup-file`)."""
    m = re.search(r"<code><!\[CDATA\[(.*?)\]\]></code>", text, re.S)
    escaped = False
    if not m:   # some files keep the code as escaped XML instead of a CDATA section
        m = re.search(r"<code>(.*?)</code>", text, re.S)
        escaped = True
    if not m:
        raise NetLogoError("not a NetLogo 7 model (.nlogox): no <code> section")
    code = html.unescape(m.group(1)) if escaped else m.group(1)
    if "construct-record" in code:
        raise NetLogoError("this model already records itself (construct-record is in its code)")
    if re.search(r"__includes\s*\[", code):
        code = re.sub(r"__includes\s*\[", '__includes ["construct.nls" ', code, count=1)
    else:
        code = '__includes ["construct.nls"]\n\n' + code
    start = ['construct-start %s %s' % (json.dumps(title), json.dumps(run_file))]
    if seed is not None:
        start.append("construct-seed %d" % seed)
    if turtles:
        start.append("construct-track-turtles %s" % _list(turtles))
    if reporters:
        start.append("construct-track-reporters %s" % _list(reporters))
    if patches:
        start.append("construct-track-patches %s %d" % (json.dumps(patches[0]), patches[1]))
    if every > 1:
        start.append("construct-record-every %d" % every)
    if skip_turtles:
        start.append("construct-skip-turtles")
    start.append("construct-record")

    def proc_body(name, code):
        return re.search(r"(?mi)^\s*to(?:-report)?\s+%s(?=[\s\[]).*?^\s*end\b" % re.escape(name), code, re.S)

    def inputs(name):
        b = proc_body(name, code)
        i = re.match(r"(?i)\s*to\s+\S+\s*\[([^\]]*)\]", b.group(0)) if b else None
        return i.group(1).split() if i else []

    def procs(cmd):   # the model's procedures a command calls, in order
        words = re.findall(r"[A-Za-z][\w\-?!.]*", re.sub(r";[^\n]*", "", cmd))
        return [w for i, w in enumerate(words) if w not in words[:i] and proc_body(w, code)]

    def holder(proc, word, code, depth=0, seen=()):
        """The procedure where `word` happens: proc itself, or one it calls (a few levels down)."""
        b = proc_body(proc, code)
        if not b:
            return None
        body = re.sub(r";[^\n]*", "", b.group(0))
        if re.search(r"(?mi)^\s*%s\b" % word, body):
            return proc
        if depth >= 3:
            return None
        for name in re.findall(r"[A-Za-z][\w\-?!.]*", body.split("\n", 1)[1] if "\n" in body else ""):
            if name not in seen and name != proc and proc_body(name, code):
                found = holder(name, word, code, depth + 1, seen + (proc,))
                if found:
                    return found
        return None

    # setup and go: the model's own button for them (its whole command), its own procedure, else its other
    # buttons (a forever button is go; a turtle's forever button is asked of every turtle; a step button)
    buttons = [(c, f) for c, f, k in _buttons(text) if k == "Observer"]
    asked = set()   # commands run by asking the turtles: recorded after the ask, never inside it

    def choose(flag, given):
        if given:
            if len(given.split()) == 1 and inputs(given):
                hint = [c for c, _ in buttons if flag in c and "\n" not in c]
                raise NetLogoError("`%s` takes inputs (%s): give the command with --%s%s" % (
                    given, " ".join(inputs(given)), flag,
                    ", such as one of this model's buttons: " + ", ".join('--%s "%s"' % (flag, x) for x in hint[:3])
                    if hint else ' "%s ..."' % given))
            if not procs(given) and not re.search(r"\b(reset-ticks|tick)\b", given):
                raise NetLogoError("no `to %s` procedure in the model (name it with --setup or --go)" % given.split()[0])
            return given
        own = [c for c, f in buttons if c.split()[0].lower() == flag and (f or flag == "setup")
               and not (len(c.split()) == 1 and inputs(c))]
        if own:
            return own[0]
        if flag == "go":   # go as a turtle procedure, behind a turtle's forever button
            turtle = [c for c, f, k in _buttons(text) if f and k == "Turtle" and c.split()[0].lower() == "go"]
            if turtle:
                asked.add("ask turtles [ %s ]" % turtle[0])
                return "ask turtles [ %s ]" % turtle[0]
        if proc_body(flag, code) and not inputs(flag):
            return flag
        ok = [c for c, f in buttons if (f if flag == "go" else not f) and not (len(c.split()) == 1 and inputs(c))]
        words = ("go",) if flag == "go" else ("setup", "reset", "init", "new", "start")
        if flag == "setup":   # one that fills the world before one that empties it (setup-random before setup-blank)
            ok = sorted(ok, key=lambda c: bool(re.search(r"(?i)blank|clear|empty|erase", c)))
        for w in words:
            for c in ok:
                if re.search(r"(?i)\b%s" % w, c):
                    return c
        if ok:
            return ok[0]
        if flag == "go":
            turtle = [c for c, f, k in _buttons(text) if f and k == "Turtle"]
            if turtle:
                asked.add("ask turtles [ %s ]" % turtle[0])
                return "ask turtles [ %s ]" % turtle[0]
            step = [c for c, f in buttons if not f and re.search(r"(?i)\b(go|step|iterate|run|once|next)", c)
                    and not re.search(r"(?i)\b(setup|reset|clear)", c)]
            if step:
                return step[0]
        if proc_body(flag, code):
            return choose(flag, flag)   # it takes inputs: say so, with the buttons that give them
        raise NetLogoError("no `to %s` procedure and no %s button in the model: name the command with --%s" % (
            flag, "forever" if flag == "go" else "setup", flag))

    setup, go = choose("setup", setup), choose("go", go)

    def place(cmd, word, lines):
        """`lines` after `word` in the procedures cmd calls; else at the end of the first one (a model
        that never ticks); else after the command itself. Returns the command the experiment runs."""
        nonlocal code
        if cmd in asked:   # a turtle's command: the record follows the ask, in the observer's context
            return cmd + "\n" + "\n".join(lines)
        for proc in procs(cmd):
            where = holder(proc, word, code)
            if where:
                b = proc_body(where, code)
                body = b.group(0)
                hits = list(re.finditer(r"(?m)^(\s*)(%s)\b(.*)$" % word, body))
                h = hits[-1] if word == "tick" else hits[0]
                new = body[:h.end()] + "".join("\n%s%s" % (h.group(1), ln) for ln in lines) + body[h.end():]
                code = code[:b.start()] + new + code[b.end():]
                return cmd
        if procs(cmd) and not re.search(r"(?m)^\s*%s\b" % word, cmd):
            b = proc_body(procs(cmd)[0], code)
            body = b.group(0)
            e = list(re.finditer(r"(?mi)^\s*end\b", body))[-1]
            new = body[:e.start()].rstrip() + "".join("\n  %s" % ln for ln in lines) + "\n" + body[e.start():]
            code = code[:b.start()] + new + code[b.end():]
            return cmd
        return cmd + "\n" + "\n".join(lines)   # the button's own code holds it: the button records too

    new_setup = place(setup, "reset-ticks", start)
    new_go = place(go, "tick", ["construct-record"])
    if escaped:
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    model = text[:m.start(1)] + code + text[m.end(1):]
    for old, new in ((setup, new_setup), (go, new_go)):
        if new != old and old not in asked:   # rewrite the button, so pressing it in NetLogo records as the experiment does
            model = re.sub(r"(<button[^>]*>)([^<]*)(</button>)",
                           lambda b: b.group(1) + escape(new) + b.group(3) if html.unescape(b.group(2)).strip() == old
                           else b.group(0), model)
    setup_cmd = ("random-seed %d\n" % seed if seed is not None else "") + escape(new_setup)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<experiments>\n'
           '  <experiment name="construct" repetitions="1" sequentialRunOrder="true" runMetricsEveryStep="false" '
           'timeLimit="%d">\n    <setup>%s</setup>\n    <go>%s</go>\n    <postRun>construct-finish</postRun>\n'
           '    <metrics>\n      <metric>count turtles</metric>\n    </metrics>\n  </experiment>\n</experiments>\n'
           % (ticks, setup_cmd, escape(new_go)))
    return model, xml


# ---------------------------------------------------------------------------- the recording

def read_run(path):
    run = parse_run(Path(path).read_text(encoding="utf-8"))
    run["dir"] = str(Path(path).resolve().parent)   # where the run is (its model and data beside it)
    return run


def parse_run(text):
    """A recording (construct.nls or the extension's JSON Lines) as {header, frames, end}."""
    header, frames, end = None, [], None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise NetLogoError("line %d: not JSON (%s)" % (n, exc))
        if "construct-netlogo" in row:
            header = row
        elif "t" in row:
            frames.append(row)
        elif "end" in row:
            end = row["end"]
    if header is None or not frames:
        raise NetLogoError("not a construct.nls recording: no header or no records")
    return {"header": header, "frames": frames, "end": end}


class _World:
    def __init__(self, header, last_tick, height=HEIGHT, time="linear"):
        w = header["world"]
        self.x0, self.x1, self.y0, self.y1 = w["min-pxcor"] - 0.5, w["max-pxcor"] + 0.5, w["min-pycor"] - 0.5, \
            w["max-pycor"] + 0.5
        self.w, self.h = self.x1 - self.x0, self.y1 - self.y0
        self.k = FLOOR / max(self.w, self.h)
        self.cx, self.cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        self.last = max(1, last_tick)
        self.top = height
        self.sqrt = time == "sqrt"   # early ticks stretched, when most of a run happens early

    def floor(self, x, y, t=0.0):
        return [round((x - self.cx) * self.k, 3), round(self.height(t), 3), round(-(y - self.cy) * self.k, 3)]

    def height(self, t):
        f = max(0.0, t) / self.last
        return self.top * (math.sqrt(f) if self.sqrt else f)

    def jump(self, a, b):   # a wrap around the world's edge is not a move
        return abs(a[0] - b[0]) > self.w / 2 or abs(a[1] - b[1]) > self.h / 2

    def outline(self):
        hw, hd = self.w * self.k / 2, self.h * self.k / 2
        return [[[-hw, 0, -hd], [hw, 0, -hd], [hw, 0, hd], [-hw, 0, hd], [-hw, 0, -hd]]]


def _chunks(points, n=256):
    """A polyline in pieces of at most n points that share their ends."""
    out, i = [], 0
    while i < len(points) - 1:
        out.append(points[i:i + n])
        i += n - 1
    return [c for c in out if len(c) >= 2]


def _part(pid, label, role, shape, stage=0, certainty="verified", tone=None, weight=None, alpha=None):
    p = {"id": pid, "label": label, "role": role, "shape": shape, "certainty": certainty, "stage": stage,
         "source": "run"}
    look = {k: v for k, v in (("tone", tone), ("weight", weight), ("alpha", alpha)) if v is not None}
    if look:
        p["look"] = look
    return p


def _frame_axis(world):
    """The world's floor outline, and a time axis at its back-left corner with a mark every fifth."""
    hw, hd = world.w * world.k / 2, world.h * world.k / 2
    axis = [[[-hw, 0, -hd], [-hw, world.top, -hd]]]
    for i in range(1, 6):
        y = world.top * i / 5
        axis.append([[-hw, y, -hd], [-hw + 0.25, y, -hd]])
    plate = _part("world", "The world's floor", "mass", {"type": "box", "size": [round(2 * hw, 4), 0.03, round(2 * hd, 4)]},
                  alpha=0.5, weight=0.5)
    plate["at"] = [0, -0.015, 0]
    return [plate, _part("time-axis", "Time, tick 0 to %d" % world.last, "ground", {"type": "paths", "paths": axis})]


# ---------------------------------------------------------------------------- views

def _space_time(run, world, opts):
    tracks = {}
    if not any("turtles" in f for f in run["frames"]):
        raise NetLogoError("space-time needs turtles in the recording (it skipped them)")
    for f in run["frames"]:
        for row in f.get("turtles", []):
            tracks.setdefault(row[0], {"breed": row[1], "pts": []})["pts"].append((row[2], row[3], f["t"]))
    whos = sorted(tracks)
    cap = opts.get("max_agents") or 150
    if len(whos) > cap:   # evenly by who
        whos = [whos[int(i * len(whos) / cap)] for i in range(cap)]
    frames = max(len(tracks[w]["pts"]) for w in whos)
    stride = max(1, math.ceil(len(whos) * frames / MAX_SEGMENTS))
    by_breed = {}
    for w in whos:
        pts = tracks[w]["pts"]
        keep = pts[::stride] + ([pts[-1]] if (len(pts) - 1) % stride else [])
        run_, pieces = [], []
        for a in keep:
            if run_ and world.jump(run_[-1], a):
                pieces.append(run_)
                run_ = []
            run_.append(a)
        pieces.append(run_)
        for piece in pieces:
            if len(piece) >= 2:
                by_breed.setdefault(tracks[w]["breed"], []).extend(
                    _chunks([world.floor(x, y, t) for x, y, t in piece]))
    parts = []
    for i, (breed, paths) in enumerate(sorted(by_breed.items(), key=lambda kv: -len(kv[1]))[:len(TONES)]):
        parts.append(_part("tracks-%s" % re.sub(r"[^a-z0-9]+", "-", breed.lower()).strip("-"),
                           "The %s, tick by tick" % breed, "identity", {"type": "paths", "paths": paths[:4000],
                                                                       "detail": True},
                           tone=TONES[i], alpha=0.6))
        if min(v[1] for path in paths[:4000] for v in path) > 0.001:   # a breed born mid-run: its tracks start in the air
            parts[-1]["floating"] = True
    n_all = len(tracks)
    summary = ("Each turtle's track rising with time: the floor is the world, height is ticks, so a turtle that "
               "stands still draws a vertical line and a moving one leans.")
    facts = [("agents_drawn", "%d of %d turtles%s" % (len(whos), n_all, "" if len(whos) == n_all else
                                                       ", chosen evenly by who")),
             ("sampling", "every %d record%s" % (stride, "" if stride == 1 else "s"))]
    return parts, summary, facts


# ---- order over time: what moving turtles and turtles that switch on and off are measured by

EVENT_ONSETS = 4      # pulse: at least this many turnings on per turtle, on average, to be a rhythm
PULSE_RINGS = 700     # pulse: at most this many rings (of 24 segments), within the data budget
SETTLED = 0.9         # the window: until the order has come this far from its start to where it stays
SHORT_RUN = 500       # the window: only for runs at least this long


def _turtle_frames(run):
    return [f for f in run["frames"] if f.get("turtles")]


SAMPLE_TURTLES = 200   # turtles the measures follow, chosen evenly by who: enough for a share, quick on any run
REGULAR = 0.5          # pulse: the spread of a turtle's gaps between events (their deviation over their mean)


_MEMO = []   # (frames, what, value): the last few measures worked out, the frames held so their id is not reused


def _memo(run, what, make):
    """A measure of a run's frames, worked out once while it is among the last few."""
    for frames, w, value in _MEMO:
        if frames is run["frames"] and w == what:
            return value
    value = make()
    _MEMO.append((run["frames"], what, value))
    del _MEMO[:-6]
    return value


def _sample_whos(run):
    """At most SAMPLE_TURTLES turtles, evenly by who, from every turtle the run recorded."""
    whos = sorted({r[0] for f in _turtle_frames(run) for r in f["turtles"]})
    return set(whos if len(whos) <= SAMPLE_TURTLES else [whos[int(i * len(whos) / SAMPLE_TURTLES)]
                                                         for i in range(SAMPLE_TURTLES)])


def _event_signals(run):
    """The states a turtle can switch on and off: each true/false turtle variable, hidden? too (a colour that
    changes shows a state, not a rhythm). For each, the event is its rarer value (a flash is the short state),
    with a sample of turtles' records, their onsets per turtle and how regular their gaps are. Worked out once
    for a run (and once for a window of it)."""
    return _memo(run, "signals", lambda: _signals_of(run))


def _signals_of(run):
    h, tf = run["header"], _turtle_frames(run)
    keep = _sample_whos(run)
    out = []
    for i, name in enumerate(h.get("turtle-vars", [])):
        seq = {}
        for f in tf:
            for r in f["turtles"]:
                if r[0] in keep:
                    seq.setdefault(r[0], []).append((f["t"], r[5 + i] if len(r) > 5 + i else None, r[2], r[3]))
        allv = [v for sq in seq.values() for _, v, _, _ in sq]
        if not allv or not all(isinstance(v, bool) for v in allv):
            continue
        rare = sum(1 for v in allv if v) <= len(allv) / 2
        on = (lambda v: v is True) if rare else (lambda v: v is False)
        word = ("it was shown (hidden? turned false)" if name == "hidden?" and not rare else
                "%s turned %s" % (name, "true" if rare else "false"))
        times = {w: [b[0] for a, b in zip(sq, sq[1:]) if not on(a[1]) and on(b[1])] for w, sq in seq.items()}
        spreads = []
        for ts in times.values():
            gaps = [b - a for a, b in zip(ts, ts[1:])]
            if len(gaps) >= 3:
                m = sum(gaps) / len(gaps)
                spreads.append(math.sqrt(sum((g - m) ** 2 for g in gaps) / len(gaps)) / m if m else 9.0)
        out.append({"state": name, "word": word, "on": on, "seq": seq,
                    "mean": sum(len(ts) for ts in times.values()) / len(times),
                    "repeat": sum(1 for ts in times.values() if len(ts) >= 2) / len(times),
                    "regular": sorted(spreads)[len(spreads) // 2] if spreads else 9.0})
    return out


def _event_choice(run):
    """The state that switches on and off as a rhythm: at least EVENT_ONSETS times per turtle on average, for
    most turtles, at gaps regular to within REGULAR; None if none does."""
    best = None
    for s in _event_signals(run):
        if (s["mean"] >= EVENT_ONSETS and s["repeat"] >= 0.5 and s["regular"] <= REGULAR
                and (best is None or s["mean"] > best["mean"] * 1.05)):
            best = s
    return best


def _onsets(s):
    """Each turtle's ticks of turning on, for one state."""
    out = {}
    for w, seq in s["seq"].items():
        out[w] = [b[0] for a, b in zip(seq, seq[1:]) if not s["on"](a[1]) and s["on"](b[1])]
    return out


def _phase_at(times, t, k=0):
    """Where a turtle is in its own cycle at tick t, from its events (0 at one, 2 pi at the next): the phase of a
    rhythm known only by its events. None before its first event or after its last. k: a search hint."""
    while k + 1 < len(times) and times[k + 1] <= t:
        k += 1
    if not times or t < times[0] or k + 1 >= len(times):
        return None, k
    return 2 * math.pi * (t - times[k]) / (times[k + 1] - times[k]), k


def _value(run, state, row):
    """A turtle's value of a state in one record's row: a turtle variable, or its colour."""
    if state == "color":
        return row[4]
    i = run["header"]["turtle-vars"].index(state)
    return row[5 + i] if len(row) > 5 + i else None


def _headings(run, world):
    """Each moving turtle's direction from one record to the next (unit vectors, wraps excluded), per record, for
    a sample of turtles."""
    tf = _turtle_frames(run)
    keep = _sample_whos(run)
    out = []
    for a, b in zip(tf, tf[1:]):
        pos = {r[0]: (r[2], r[3], r[1]) for r in a["turtles"] if r[0] in keep}
        dirs = []
        for r in b["turtles"]:
            p = pos.get(r[0])
            if p is None or world.jump(p, (r[2], r[3])):
                continue
            dx, dy = r[2] - p[0], r[3] - p[1]
            d = math.hypot(dx, dy)
            if d > 1e-6:
                dirs.append((r[0], p[2], p[0], p[1], dx / d, dy / d))
        out.append((a["t"], dirs))
    return out


def _alignment(run, world):
    """Moving turtles' alignment at each record: the length of their mean heading, 0 when they head every way,
    1 when all head one way. Worked out once for a run (and once for a window of it)."""
    return _memo(run, "alignment", lambda: [(t, math.hypot(sum(d[4] for d in dirs), sum(d[5] for d in dirs)) / len(dirs))
                                            for t, dirs in _headings(run, world) if len(dirs) >= 2])


def _synchrony(run, s):
    """Turtles that switch on and off: their synchrony at each record, the order parameter r (the length of the
    mean of e^(i phase), each turtle's phase from its own events), 0 each on its own rhythm, 1 all in step."""
    onsets = _onsets(s)
    hint = {w: 0 for w in onsets}
    out = []
    for f in _turtle_frames(run):
        cx = cy = 0.0
        n = 0
        for w, times in onsets.items():
            ph, hint[w] = _phase_at(times, f["t"], hint[w])
            if ph is not None:
                cx += math.cos(ph)
                cy += math.sin(ph)
                n += 1
        if n >= 2:
            out.append((f["t"], math.hypot(cx, cy) / n))
    return out


def _order(run, world, view, opts):
    """The measure of order for a view, if it has one: (its name, its values over the run)."""
    if view == "space-time":
        return "alignment", _alignment(run, world)
    if view == "pulse":
        st = opts.get("state") or (_event_choice(run) or {}).get("state")
        sig = next((x for x in _event_signals(run) if x["state"] == st), None)
        return ("synchrony", _synchrony(run, sig)) if sig else (None, [])
    return None, []


def settle_window(series, last):
    """Where order forms: the tick by which a measure has come SETTLED of the way from its start to the level it
    keeps, with a margin, when that is well before the end of the run; None when the order never forms or forms
    late (the whole run is then the story)."""
    if len(series) < 20 or last < SHORT_RUN:   # a short run is not squeezed: drawn whole
        return None
    k = max(1, len(series) // 20)
    smooth = [(series[i][0], sum(v for _, v in series[max(0, i - k):i + 1]) / len(series[max(0, i - k):i + 1]))
              for i in range(len(series))]
    start = sum(v for _, v in series[:k]) / k
    tail = series[-max(1, len(series) * 3 // 10):]
    keep = sum(v for _, v in tail) / len(tail)
    if keep - start < 0.15:   # no order forms that a window would show
        return None
    reach = next((t for t, v in smooth[k:] if v >= start + SETTLED * (keep - start)), None)
    if reach is None:
        return None
    end = int(math.ceil(min(last, reach * 1.3 + 0.05 * last)))
    return end if end <= 0.6 * last else None


def _pulse(run, world, opts):
    signals = {s["state"]: s for s in _event_signals(run)}
    state = opts.get("state") or (_event_choice(run) or {}).get("state")
    if not state:
        raise NetLogoError("pulse needs a turtle state that switches on and off again and again at regular gaps (a "
                           "true/false variable, hidden? too); none does here")
    if state not in signals:
        raise NetLogoError("no turtle state %r in the recording (%s)" % (state, ", ".join(sorted(signals))))
    s = signals[state]
    tf = _turtle_frames(run)
    share = [(f["t"], sum(1 for r in f["turtles"] if s["on"](_value(run, state, r))) / max(1, len(f["turtles"])))
             for f in tf]
    group = max(1, math.ceil(len(share) / PULSE_RINGS))   # a long run: the most at once in each group of records
    rings = []
    R = 0.45 * min(world.w, world.h)
    for g in range(0, len(share), group):
        t, v = max(share[g:g + group], key=lambda tv: tv[1])
        if v > 0.005:
            rad = R * math.sqrt(v)   # the ring's area is the share
            rings.append([world.floor(world.cx + rad * math.cos(2 * math.pi * k / 24),
                                      world.cy + rad * math.sin(2 * math.pi * k / 24), t) for k in range(25)])
    full = [[world.floor(world.cx + R * math.cos(2 * math.pi * k / 48), world.cy + R * math.sin(2 * math.pi * k / 48), t)
             for k in range(49)] for t in (0, world.last)]
    parts = [_part("pulse-%d" % (i // 4000), "How many at once: a ring per tick, its area the share",
                   "identity", {"type": "paths", "paths": rings[i:i + 4000], "detail": True}, tone="bright", alpha=0.9)
             for i in range(0, len(rings), 4000)]
    parts.append(_part("pulse-all", "The full width: every turtle at once", "ground", {"type": "paths", "paths": full},
                       alpha=0.3))
    peak = max(v for _, v in share)
    tenth = max(1, len(share) // 10)
    top = lambda part: sorted((v for _, v in part), reverse=True)[:max(1, len(part) // 20)]
    early, late = top(share[:tenth]), top(share[-tenth:])
    summary = ("The run's pulse rising with time: one ring per tick, its area the share of turtles in that state "
               "then (%s), so turtles on their own make a thin, ragged column and turtles in step make wide plates "
               "with nothing between." % s["word"])
    facts = [("event", "%s, %.1f times per turtle on average" % (s["word"], sum(len(v) for v in _onsets(s).values())
                                                                / max(1, len(s["seq"])))),
             ("together", "at most %d%% of the turtles at once; the most at once early in the run %d%%, late %d%%" % (
                 round(100 * peak), round(100 * sum(early) / len(early)), round(100 * sum(late) / len(late))))]
    if group > 1:
        facts.append(("sampling", "each ring the most at once in a group of %d records" % group))
    opts["_series"] = {"name": "at once", "values": [[t, round(v, 3)] for t, v in _sampled(share)]}
    return parts, summary, facts


APPEARED = "@appeared"   # network-time's state for a network that grows: each turtle at the tick it appeared


def _network_time(run, world, opts):
    var = opts.get("state")
    names = run["header"]["turtle-vars"]
    if var != APPEARED and var not in names:
        raise NetLogoError("network-time needs --state, a turtle variable the recording tracked (%s)" %
                           (", ".join(names) or "none were: use construct-track-turtles"))
    vi = 5 + names.index(var) if var != APPEARED else None
    links = next((f["links"] for f in reversed(run["frames"]) if "links" in f), None)
    if not links:
        raise NetLogoError("network-time needs links in the recording")
    last = run["frames"][-1]["turtles"]
    pos = {r[0]: (r[2], r[3]) for r in last}
    when = {}
    for f in run["frames"]:
        for r in f["turtles"]:
            v = True if vi is None else r[vi]
            if r[0] not in when and (v is True or (isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0)):
                when[r[0]] = f["t"]
    floor_paths = [[world.floor(*pos[a]), world.floor(*pos[b])] for a, b, _ in links if a in pos and b in pos]
    stems = [[world.floor(*pos[w]), world.floor(*pos[w], t)] for w, t in when.items() if w in pos]
    climb = []
    for a, b, _ in links:
        if a in when and b in when and a in pos and b in pos:
            lo, hi = (a, b) if when[a] <= when[b] else (b, a)
            climb.append([world.floor(*pos[lo], when[lo]), world.floor(*pos[hi], when[hi])])
    parts = [_part("network", "The network, as NetLogo laid it out", "ground", {"type": "paths", "paths": floor_paths,
                                                                              "detail": True}, tone="faint")]
    if stems:   # one part per colour the turtles ended in, so each can be drawn in it
        ended = {r[0]: r[4] for r in last}
        by, called = {}, {}
        bead = 0.012 * FLOOR
        for w, stem in zip((w for w in when if w in pos), stems):
            c = netlogo_rgb(ended.get(w))
            called[c] = netlogo_name(ended.get(w))
            top = stem[1]   # a ring of light where the turtle rose to: the bead it ends in
            ring = [[round(top[0] + bead * math.cos(math.pi * k / 4), 4), top[1],
                     round(top[2] + bead * math.sin(math.pi * k / 4), 4)] for k in range(9)]
            by.setdefault(c, []).extend([stem, ring])
        label = ("Each turtle, risen to the tick it appeared" if vi is None else
                 "Each turtle, risen to the tick %s turned true" % var)
        for c, group in sorted(by.items(), key=lambda kv: -len(kv[1])):
            pid = "risen" if len(by) == 1 else "risen-" + c[1:]
            parts.append(_part(pid, label if len(by) == 1 else label + " (%s at the end)" % called[c], "data",
                               {"type": "paths", "paths": group}, tone="dust", weight=0.8))
    if climb:
        parts.append(_part("climb", "Links between risen turtles, from the earlier to the later", "identity",
                           {"type": "paths", "paths": climb}))
    summary = ("The network on the floor; each turtle rises to the tick %s, and each link between two risen "
               "turtles climbs from the earlier to the later." % ("it appeared" if vi is None else
                                                                 "its %s first turned true" % var))
    facts = [("state", "the tick each turtle appeared" if vi is None else var),
             ("turned", "%d of %d turtles" % (len(when), len(pos)))]
    if opts.get("solid"):   # a solid for each turtle, for a 3D model: risen where it turned, else on the floor
        who = sorted(pos)
        pick = who if len(who) <= SOLID_NODES else [who[round(i * (len(who) - 1) / (SOLID_NODES - 1))]
                                                    for i in range(SOLID_NODES)]
        r = round(0.012 * FLOOR, 3)
        for w in pick:
            at = world.floor(*pos[w], when.get(w, 0))
            node = _part("node-%d" % w, "Turtle %d%s" % (w, ", risen at tick %g" % when[w] if w in when else ""), "data",
                         {"type": "sphere", "radius": r, "lat": 3, "lon": 5})
            node["at"] = [at[0], round(at[1] + (0 if w in when else r), 3), at[2]]
            node["floating"] = w in when
            parts.append(node)
        facts.append(("solids", "a sphere for %d of %d turtles%s" % (len(pick), len(who),
                                                                     ", chosen evenly by who" if len(pick) < len(who) else "")))
    return parts, summary, facts


def _phase(run, world, opts):
    names = run["header"]["reporters"]
    if len(names) < 2:
        raise NetLogoError("phase needs two reporters in the recording (construct-track-reporters)")
    xs, zs = opts.get("x") or names[0], opts.get("z") or names[1]
    for n in (xs, zs):
        if n not in names:
            raise NetLogoError("no reporter %r in the recording (%s)" % (n, ", ".join(names)))
    ix, iz = names.index(xs), names.index(zs)
    rows = [(f["t"], f["reporters"][ix], f["reporters"][iz]) for f in run["frames"] if "reporters" in f]
    win = int(opts.get("smooth") or 0)
    if win > 1:   # a centred moving average over `win` records, so the cycle shows through tick-to-tick noise
        half_w = win // 2
        raw = rows
        rows = []
        for i, (t, _, _) in enumerate(raw):
            seg = raw[max(0, i - half_w):i + half_w + 1]
            rows.append((t, sum(r[1] for r in seg) / len(seg), sum(r[2] for r in seg) / len(seg)))
    lo_x, hi_x = min(r[1] for r in rows), max(r[1] for r in rows)
    lo_z, hi_z = min(r[2] for r in rows), max(r[2] for r in rows)
    half = FLOOR / 2

    def at(t, a, b, y=None):
        X = -half + FLOOR * (a - lo_x) / ((hi_x - lo_x) or 1)
        Z = half - FLOOR * (b - lo_z) / ((hi_z - lo_z) or 1)
        return [round(X, 3), round(world.height(t) if y is None else y, 3), round(Z, 3)]

    stride = max(1, math.ceil(len(rows) / 4000))
    rows = rows[::stride] + ([rows[-1]] if (len(rows) - 1) % stride else [])
    rising = _chunks([at(t, a, b) for t, a, b in rows])
    shadow = _chunks([at(t, a, b, 0.0) for t, a, b in rows])
    wall_x = _chunks([[at(t, a, lo_z)[0], world.height(t), half + 0.0] for t, a, _ in rows])
    wall_z = _chunks([[-half, world.height(t), at(t, lo_x, b)[2]] for t, _, b in rows])
    axes = [[[-half, 0, half], [half, 0, half]], [[-half, 0, half], [-half, 0, -half]]]
    time_axis = [[[-half, 0, -half], [-half, world.top, -half]]] + [
        [[-half, world.top * i / 5, -half], [-half + 0.25, world.top * i / 5, -half]] for i in range(1, 6)]
    plate = _part("plate", "The floor", "mass", {"type": "box", "size": [FLOOR, 0.03, FLOOR]}, alpha=0.5, weight=0.5)
    plate["at"] = [0, -0.015, 0]
    parts = [plate, _part("time-axis", "Time, tick 0 to %d" % world.last, "ground", {"type": "paths", "paths": time_axis}),
             _part("phase", "%s and %s, rising with time" % (xs, zs), "identity", {"type": "paths", "paths": rising}),
             _part("phase-floor", "The classic phase plot, on the floor", "ground", {"type": "paths", "paths": shadow},
                   tone="faint"),
             _part("wall-x", "%s over time" % xs, "data", {"type": "paths", "paths": wall_x, "detail": True},
                   tone="data", alpha=0.6),
             _part("wall-z", "%s over time" % zs, "data", {"type": "paths", "paths": wall_z, "detail": True},
                   tone="dust", alpha=0.6),
             _part("axes", "%s (left to right), %s (front to back)" % (xs, zs), "ground", {"type": "paths",
                                                                                         "paths": axes})]
    summary = ("A phase portrait rising in time: across the floor %s, front to back %s, height is ticks; its "
               "shadow on the floor is the classic phase plot, and the two walls carry each against time."
               % (xs, zs))
    facts = [("x", "%s, %g to %g" % (xs, round(lo_x, 2), round(hi_x, 2))),
             ("z", "%s, %g to %g" % (zs, round(lo_z, 2), round(hi_z, 2)))]
    if win > 1:
        facts.append(("smoothing", "a centred moving average over %d records" % win))
    if opts.get("solid"):   # the rising cycle as a solid: a chain of tubes along it, for a 3D model
        line = [v for chunk in rising for v in chunk]
        step = max(1, math.ceil((len(line) - 1) / (SOLID_TUBES * (MAX_TUBE - 1))))
        line = line[::step] + ([line[-1]] if (len(line) - 1) % step else [])
        k = 0
        for i in range(0, len(line) - 1, MAX_TUBE - 1):
            seg = line[i:i + MAX_TUBE]
            if len(seg) >= 2:
                tube = _part("phase-solid-%d" % k, "%s and %s, rising with time, as a solid" % (xs, zs), "data",
                             {"type": "tube", "path": seg, "radius": round(0.008 * FLOOR, 3), "sides": 8,
                              "samples": 2, "longitudinal": 0, "ring_every": 16})
                tube["floating"] = True
                parts.append(tube)
                k += 1
        facts.append(("solids", "the rising cycle as %d tubes through %d of its points" % (k, len(line))))
    return [p for p in parts if p["shape"].get("paths", True)], summary, facts


def _isolines(grid, level):
    """Marching squares over a grid of ticks (None where nothing changed): the line where the change
    reached `level`, as (row, col) segments; cells with a corner that never changed draw nothing."""
    segs = []
    for r in range(len(grid) - 1):
        a_row, b_row = grid[r], grid[r + 1]
        for c in range(len(a_row) - 1):
            q = (a_row[c], a_row[c + 1], b_row[c + 1], b_row[c])   # clockwise from the top left
            if None in q:
                continue
            pts = []
            corners = ((r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c))
            for i in range(4):
                v0, v1 = q[i], q[(i + 1) % 4]
                if (v0 < level) != (v1 < level):
                    f = (level - v0) / (v1 - v0)
                    (r0, c0), (r1, c1) = corners[i], corners[(i + 1) % 4]
                    pts.append((r0 + f * (r1 - r0), c0 + f * (c1 - c0)))
            if len(pts) == 2:
                segs.append(tuple(pts))
            elif len(pts) == 4:   # a saddle: pair by the centre
                segs += [(pts[0], pts[1]), (pts[2], pts[3])]
    return segs


def _chain(segs):
    """Join segments that share ends into polylines."""
    key = lambda p: (round(p[0], 4), round(p[1], 4))
    ends = {}
    for i, (a, b) in enumerate(segs):
        ends.setdefault(key(a), []).append(i)
        ends.setdefault(key(b), []).append(i)
    used, lines = set(), []
    for i in range(len(segs)):
        if i in used:
            continue
        used.add(i)
        line = list(segs[i])
        for grow_front in (False, True):
            while True:
                tip = line[0] if grow_front else line[-1]
                nxt = next((j for j in ends.get(key(tip), []) if j not in used), None)
                if nxt is None:
                    break
                used.add(nxt)
                a, b = segs[nxt]
                other = b if key(a) == key(tip) else a
                if grow_front:
                    line.insert(0, other)
                else:
                    line.append(other)
        lines.append(line)
    return lines


def _field(run, world, opts):
    h = run["header"]
    src = h.get("patch-reporter")
    samples = [(f["t"], f["patches"]) for f in run["frames"] if "patches" in f]
    if not src or len(samples) < 2:
        raise NetLogoError("field needs a patch reporter recorded at least twice (construct-track-patches)")
    w = h["world"]
    cols, rows = w["max-pxcor"] - w["min-pxcor"] + 1, w["max-pycor"] - w["min-pycor"] + 1
    mode = opts.get("change") or "first"
    when = [None] * len(samples[0][1])
    for (_, before), (t, vals) in zip(samples, samples[1:]):   # each change, sample to sample
        for i, v in enumerate(vals):
            if v != before[i] and (when[i] is None or mode == "last"):
                when[i] = t
    # blocks of patches, about 64 across: each block the earliest change among its patches, so a sparse
    # field (a forest with gaps) still has a continuous front; a block where nothing changed stays empty
    step = max(1, math.ceil(max(cols, rows) / int(opts.get("resolution") or 64)))
    grid = []
    for r0 in range(0, rows, step):
        row = []
        for c0 in range(0, cols, step):
            ts = [when[r * cols + c] for r in range(r0, min(rows, r0 + step)) for c in range(c0, min(cols, c0 + step))]
            ts = [t for t in ts if t is not None]
            row.append((min(ts) if mode == "first" else max(ts)) if ts else None)
        grid.append(row)
    changed = [t for t in when if t is not None]
    if not changed:
        raise NetLogoError("field: no patch's %s changed during the run" % src)
    levels = int(opts.get("levels") or 32)
    t0, t1 = min(changed), max(changed)
    fronts = []
    for k in range(1, levels + 1):
        level = t0 + (t1 - t0) * k / (levels + 1)
        y = world.height(level)
        for line in _chain(_isolines(grid, level)):
            pts = [world.floor(w["min-pxcor"] + (c * step) + step / 2 - 0.5, w["max-pycor"] - (r * step) - step / 2 + 0.5)
                   for r, c in line]
            fronts.extend(_chunks([[p[0], round(y, 3), p[2]] for p in pts]))
    fronts.sort(key=len, reverse=True)
    kept, budget = [], 20000   # within one part's 4000 polylines and 30000 points, and the scene's 24000 lines
    for f in fronts[:4000]:
        if len(f) > budget:
            break
        kept.append(f)
        budget -= len(f)
    fronts = kept
    if not fronts:
        raise NetLogoError("field: the patches' %s changed all at once, so there is no front to draw; try another view"
                           % src)
    parts = [_part("fronts", "Where the %s %s changed, every %s ticks, raised to its tick" % (
        src, mode, round((t1 - t0) / (levels + 1), 1)), "identity", {"type": "paths", "paths": fronts})]
    parts[0]["floating"] = True   # each front hangs at its own tick, above the floor
    summary = ("The front of change: where each patch's %s %s changed, drawn every few ticks and raised to its "
               "tick, so the run's spread rises as a stack of fronts; where nothing changed, nothing is drawn."
               % (src, mode))
    facts = [("patch_reporter", src), ("changed", "%d of %d patches" % (len(changed), len(when))),
             ("fronts", "%d levels, tick %d to %d" % (levels, t0, t1))]
    if step > 1:
        facts.append(("grid", "%d x %d patches in blocks of %d" % (cols, rows, step)))
    if opts.get("solid"):   # the change as a surface, for a 3D model: each block at the height of its tick
        gr, gc = len(grid), len(grid[0])
        keep = max(1, math.ceil(max(gr, gc) / 128))   # the scene's terrain holds 128 x 128
        rows_k = list(range(0, gr, keep)); cols_k = list(range(0, gc, keep))
        heights = [[round(world.height(grid[r][c]) if grid[r][c] is not None else world.top, 3) for c in cols_k]
                   for r in rows_k]
        if len(rows_k) >= 2 and len(cols_k) >= 2:
            x0 = w["min-pxcor"] + step / 2 - 0.5
            y0 = w["max-pycor"] - step / 2 + 0.5
            a = world.floor(x0, y0)
            b = world.floor(x0 + cols_k[-1] * step, y0 - rows_k[-1] * step)
            surf = _part("surface", "When each place changed, as a surface (at the top: never in the run)", "data",
                         {"type": "terrain", "size": [round(b[0] - a[0], 3), round(b[2] - a[2], 3)], "heights": heights,
                          "grid_every": 0, "skirt": True})
            surf["at"] = [round((a[0] + b[0]) / 2, 3), 0, round((a[2] + b[2]) / 2, 3)]
            parts.append(surf)
            facts.append(("solids", "a surface of %d x %d blocks; blocks that never changed sit at the top" %
                          (len(cols_k), len(rows_k))))
    return parts, summary, facts


def choose_view(run, exclude=()):
    """The view that shows a recording best, and its options, with the reason: a network with a variable that
    turned (network-time), patches that changed (field), two counts that move (phase), else the agents' paths."""
    h, frames = run["header"], run["frames"]
    last = frames[-1]["t"] or 1
    links = next((f["links"] for f in reversed(frames) if "links" in f), None)   # the links at the end, as drawn
    if links:
        best = None
        for i, var in enumerate(h.get("turtle-vars", [])):
            if var == "hidden?":   # being hidden is how a turtle is shown, not a spread
                continue
            turned = {}
            for f in frames:
                for r in f.get("turtles", []):
                    if len(r) > 5 + i and r[5 + i] is True and r[0] not in turned:
                        turned[r[0]] = f["t"]
            if len(set(turned.values())) > 1:   # it turned at different times: a spread to show
                if best is None or len(turned) > best[1]:
                    best = (var, len(turned), sorted(turned.values()))
        if best:
            early = best[2][len(best[2]) // 2] < 0.3 * last
            return "network-time", dict(state=best[0], time="sqrt" if early else "linear"), \
                "a network, and %s turned true for %d turtles" % (best[0], best[1])
        born = {}
        for f in frames:
            for r in f.get("turtles", []):
                born.setdefault(r[0], f["t"])
        later = [t for t in born.values() if t > frames[0]["t"]]
        if len(later) >= max(3, 0.1 * len(born)):
            early = sorted(born.values())[len(born) // 2] < 0.3 * last
            return "network-time", dict(state=APPEARED, time="sqrt" if early else "linear"), \
                "a network that grew: %d of %d turtles appeared during the run" % (len(later), len(born))
    samples = [f["patches"] for f in frames if "patches" in f]
    if len(samples) >= 2:
        changed = sum(1 for a, b in zip(samples[0], samples[-1]) if a != b)
        moments = set()   # when each patch first changed: a front needs changes at several different times
        stamps = [f["t"] for f in frames if "patches" in f]
        for i in range(len(samples[0])):
            for k in range(1, len(samples)):
                if samples[k][i] != samples[k - 1][i]:
                    moments.add(stamps[k])
                    break
            if len(moments) >= 4:
                break
        if changed >= 0.02 * len(samples[0]) and len(moments) >= 4 and "field" not in exclude:
            return "field", {}, "%d of %d patches changed" % (changed, len(samples[0]))
    ev = _event_choice(run)
    if ev:   # turtles switching a state on and off as a rhythm: when they do it, and whether together
        return "pulse", dict(state=ev["state"]), "turtles switch on and off: %s, %.0f times each on average" % (
            ev["word"], ev["mean"])
    names = h.get("reporters", [])
    moving = []
    for i, n in enumerate(names):
        vals = [f["reporters"][i] for f in frames if isinstance((f.get("reporters") or [None] * (i + 1))[i], (int, float))]
        if len(set(vals)) > 2:
            mean = sum(vals) / len(vals)
            moving.append((sum((v - mean) ** 2 for v in vals) / len(vals) / (abs(mean) + 1), n))
    if len(moving) >= 2:
        x, z = [n for _, n in sorted(moving, reverse=True)[:2]]
        return "phase", dict(x=x, z=z, smooth=max(1, len(frames) // 150)), "%s and %s move together" % (x, z)
    w = h["world"]
    size = max(w["max-pxcor"] - w["min-pxcor"], w["max-pycor"] - w["min-pycor"]) or 1
    first = {r[0]: (r[2], r[3]) for r in next((f["turtles"] for f in frames if f.get("turtles")), [])}
    moved = []
    for f in frames[1:]:
        for r in f.get("turtles", []):
            if r[0] in first:
                moved.append(abs(r[2] - first[r[0]][0]) + abs(r[3] - first[r[0]][1]))
    moving = bool(moved) and sorted(moved)[len(moved) // 2] > 0.02 * size
    if moving:
        return "space-time", {}, "agents that move"
    if len(samples) >= 2 and any(a != b for a, b in zip(samples[0], samples[-1])) and "field" not in exclude:
        return "field", {}, "the agents barely move; the patches changed"
    if any(f.get("turtles") for f in frames):
        return "space-time", {}, "the agents barely move and nothing else changed: where they stood, over time"
    if "field" in exclude:
        raise NetLogoError("the patches change everywhere at once, which none of the four views can draw yet (no "
                           "turtles that move, no two counts that move): track two counts with construct:track-reporter "
                           "for the phase view")
    raise NetLogoError("nothing in the recording to draw: no turtles, no changing patches, no two moving counts")


def _landmarks(reading, world, view):
    """The moments worth marking, computed from the run's first count: for a count that rises and holds, where it is
    half way and most of the way (90%) from its start to its height; for one that rises and falls, its peak. Each a
    dashed frame at its tick, in the accent, with its value: inferred, like an art layer's milestones, and under the
    data lock (they are the recording's, computed)."""
    series = (reading.get("series") or [None])[0]
    if not series or len(series["values"]) < 5:
        return [], []
    vals = series["values"]
    name = series["name"]
    v0 = vals[0][1]
    top_t, top = max(vals, key=lambda tv: tv[1])
    last = vals[-1][1]
    if top - v0 <= 1e-9:
        return [], []
    marks = []
    if view == "pulse":   # a share that beats every cycle: the first time half, then all (or most), are on at once
        for frac, word in ((0.5, "Half at once"), (0.99 if top >= 0.99 else 0.9 * top, "All at once" if top >= 0.99 else
                                                    "Most at once")):
            t, v = next((tv for tv in vals if tv[1] >= frac), (None, None))
            if t is not None and (not marks or t > marks[-1][1]):
                marks.append((word, t, v))
    elif last >= v0 + 0.8 * (top - v0):   # rises and holds
        for frac, word in ((0.5, "Half way"), (0.9, "Most of the way")):
            t, v = next((tv for tv in vals if tv[1] >= v0 + frac * (top - v0)), (None, None))
            if t is not None and (not marks or t > marks[-1][1]):
                marks.append((word, t, v))
    else:   # rises and falls: its peak
        marks.append(("Peak", top_t, top))
    share = view == "pulse"
    if name.endswith("? now"):   # a true/false state counted now: in words
        name = "turtles with %s true" % name[:-4]
    fmt = lambda v: ("%d" % v) if float(v).is_integer() else ("%.2f" % v)
    hw, hd = world.w * world.k / 2, world.h * world.k / 2
    parts, facts = [], []
    for i, (word, t, v) in enumerate(marks):
        y = round(world.height(t), 3)
        frame = [[-hw, y, -hd], [hw, y, -hd], [hw, y, hd], [-hw, y, hd], [-hw, y, -hd]]
        key = "landmark_%d" % (i + 1)
        what = ("%d%% of the turtles" % round(100 * v)) if share else "%s %s" % (fmt(v), name)
        part = _part(key.replace("_", "-"), ("%s: %s · tick %s" % (word, what, fmt(t)))[:80], "data",
                     {"type": "paths", "paths": [frame]}, certainty="inferred", tone="accent", weight=1.0, alpha=0.9)
        part["floating"] = True
        part["basis"] = [key]
        part["look"]["line"] = "dashed"
        parts.append(part)
        facts.append((key, "%s: %s at tick %s" % (word.lower(), what, fmt(t))))
    return parts, facts


def _window(run, view, opts, last):
    """The window a view is drawn over: the run up to where its order formed (settle_window), automatically for
    moving turtles and turtles that switch on and off; `window` "whole" draws the whole run, a number ends it
    there. None: the whole run."""
    want = opts.get("window")
    if view not in ("space-time", "pulse") or want == "whole" or opts.get("span"):   # a shared scale: whole runs
        return None
    measure, series = _order(run, _World(run["header"], last), view, opts)
    if want not in (None, "auto"):
        try:
            end = int(float(want))
        except (TypeError, ValueError):
            raise NetLogoError("window: whole, auto, or the tick to end at")
        if not 0 < end < last:
            raise NetLogoError("window: a tick between 1 and %d" % (last - 1))
    else:
        end = settle_window(series, last) if series else None
        if end is None:
            return None
    k = max(1, len(series) // 20)
    upto = [v for t, v in series if t <= end]
    opts["_window"] = {"measure": measure or "order", "end": end,
                       "start": sum(v for _, v in series[:k]) / k if series else 0.0,
                       "reached": sum(upto[-k:]) / len(upto[-k:]) if upto else 0.0}
    return opts["_window"]


def scene_from_run(run, view, title=None, **opts):
    """A construct-scene v2 from a recording, for one of VIEWS ("auto": the one choose_view picks)."""
    if view == "auto":
        view, auto, _ = choose_view(run)
        given = {k: v for k, v in opts.items() if v not in (None, False)}
        if view == "field":   # patches that changed, but perhaps all at once: no fronts, then the next view
            try:
                return scene_from_run(run, "field", title, **dict(auto, **given))
            except NetLogoError:
                view, auto, _ = choose_view(run, exclude=("field",))
        opts = dict(auto, **given)
    if view not in VIEWS:
        raise NetLogoError("view: one of %s" % ", ".join(VIEWS))
    h, frames = run["header"], run["frames"]
    last = run["end"] if run["end"] is not None else frames[-1]["t"]
    time = opts.get("time") or "linear"
    if time not in ("linear", "sqrt"):
        raise NetLogoError("time: linear or sqrt")
    tall = view in ("space-time", "pulse")   # a cube: time as tall as the world is wide
    whole = last
    window = _window(run, view, opts, last)
    if window:   # the window where the order formed: the run up to its end
        run = dict(run, frames=[f for f in frames if f["t"] <= window["end"]], end=window["end"])
        frames, last = run["frames"], window["end"]
    world = _World(h, max(last, opts.get("span") or 0), FLOOR if tall else HEIGHT, time)   # span: a shared scale
    data, summary, extra = {"space-time": _space_time, "network-time": _network_time, "phase": _phase,
                            "field": _field, "pulse": _pulse}[view](run, world, opts)
    if view == "space-time" and not opts.get("_series"):
        align = _alignment(run, world)
        if align:
            opts["_series"] = {"name": "alignment", "values": [[t, round(v, 3)] for t, v in _sampled(align)]}
    if view == "phase":
        parts = [p for p in data]
    else:
        parts = _frame_axis(world) + data
    reading = _reading(run, view, world, opts, time)
    if opts.get("landmarks", "on") not in ("off", False):   # the moments worth marking, from the counts
        marks, mark_facts = _landmarks(reading, world, view)
        parts += marks
        extra = list(extra) + mark_facts
    title = title or (h["title"] + (" (ticks 0 to %d of %d)" % (last, whole) if window else ""))
    seed = h.get("seed")
    model = "%s (NetLogo %s%s)" % (h["title"], h.get("netlogo", "?"), ", random-seed %s" % seed if seed is not None else "")
    facts = [{"key": "model", "value": h["title"], "certainty": "verified", "source": "run"},
             {"key": "netlogo", "value": str(h.get("netlogo", "")), "certainty": "verified", "source": "run"},
             {"key": "ticks", "value": last, "certainty": "verified", "source": "run"},
             {"key": "view", "value": view, "certainty": "user_supplied", "source": "request"},
             {"key": "coordinates", "value": "Y is up. The floor is %s, %g m across its longer side; height is "
                                             "time, %g m from tick 0 to tick %d%s." % (
                                                 "the NetLogo world" if view != "phase" else "the two reporters",
                                                 FLOOR, world.top, last,
                                                 ", as the square root of the tick" if time == "sqrt" else ""),
              "certainty": "user_supplied", "source": "request"}]
    if seed is not None:
        facts.append({"key": "seed", "value": seed, "certainty": "verified", "source": "run"})
    facts += [{"key": k, "value": v, "certainty": "inferred" if k.startswith("landmark_") else "verified", "source": "run"}
              for k, v in extra]
    if window:
        facts.append({"key": "window", "value": "ticks 0 to %d of %d" % (last, whole), "certainty": "verified",
                      "source": "run", "note": "Where the %s formed: %.2f at the start, %.2f by tick %d, and it stays "
                                               "near there for the rest of the run. The whole run is in the recording "
                                               "(and in the film); --window whole draws all of it." % (
                                                   window["measure"], window["start"], window["reached"], last)})
    room = 64 - len("netlogo--") - len(view)   # a scene id is at most 64 characters
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:room].strip("-") or "netlogo-run"
    sc = {
        "format": product.SCENE_FORMAT, "version": 2, "id": "netlogo-%s-%s" % (slug, view), "title": title,
        "subject": {"category": "other", "accuracy": "documented", "synthetic": False,
                    "summary": "One run of NetLogo's %s. %s" % (h["title"], summary)},
        "units": "m", "seed": 7,
        "sources": [{"id": "request", "kind": "user_request", "title": "A construct of a NetLogo run",
                     "rights": "user_private"},
                    {"id": "run", "kind": "dataset", "title": "A run of %s, recorded with construct.nls" % model,
                     "rights": "permitted"}],
        "facts": facts, "parts": parts,
        "annotations": _legend(parts, time == "sqrt"),
        # no projector or motes: on a construct of data, nothing should look like data that isn't
        "presentation": {"framing": FRAMING[view], "atmosphere": {"haze": 0.6, "grid": False, "projector": False,
                                                                   "motes": 0},
                         "labels": True},   # the legend is how a run is read: shown from the start
        "animation": {"assembly": {"style": "build", "seconds": 12.0},
                      "idle": {"life": "calm", "events": ["scan"], "cadence": [8, 14], "strength": 0.4},
                      "camera": {"drift": 4, "breathe": 0.02}},
    }
    sc["reading"] = reading
    if opts.get("colors", "run") != "house":   # the run's own colours, made to read as light
        for pid, c in run_colours(run, sc).items():
            for part in sc["parts"]:
                if part["id"] == pid:
                    part.setdefault("look", {})["color"] = light_colour(c)
    if view == "space-time" and any(k == "sampling" and v != "every 1 record" for k, v in extra):
        sc["reading"]["how"].append("A long run of moving agents is dense here: this is its shape; for its motion, "
                                    "every agent at every tick, make its film (construct netlogo-film).")
    if h.get("clock") == "steps":   # a model that never starts the tick counter: its records are steps
        sc = _in_steps(sc)
    return lock(sc)


# ---------------------------------------------------------------------------- the legend

LEGEND_DIRS = ((1, 0.4, 1), (-1, 0.4, 1), (1, 0.4, -1), (-1, 0.4, -1), (0, 1, 0), (0.2, 0.2, 1))


# NetLogo's colours: a number 0..140, ten to a hue (5, 15, 25 ... the base colours), 0 black to 9.9 white
NL_BASE = [(141, 141, 141), (215, 50, 41), (241, 105, 19), (156, 109, 70), (237, 237, 47), (87, 176, 58),
           (42, 209, 57), (27, 158, 119), (82, 196, 196), (43, 140, 190), (52, 93, 169), (124, 80, 164),
           (167, 27, 106), (224, 127, 150)]


NL_NAMES = ("gray", "red", "orange", "brown", "yellow", "green", "lime", "turquoise", "cyan", "sky", "blue", "violet",
            "magenta", "pink")


def netlogo_name(c):
    """A NetLogo colour as NetLogo would say it: "red", "light blue", "dark green", "black", "white"."""
    if not isinstance(c, (int, float)) or isinstance(c, bool):
        return netlogo_rgb(c)
    c = float(c) % 140
    shade = c % 10
    if shade < 0.5:
        return "black"
    if shade >= 9.5:
        return "white"
    name = NL_NAMES[int(c // 10)]
    return ("dark " if shade < 3.5 else "light " if shade > 6.5 else "") + name


def netlogo_rgb(c):
    """A NetLogo colour (a number, or an RGB(A) list) as '#rrggbb'."""
    if isinstance(c, list) and len(c) >= 3:
        rgb = [max(0, min(255, int(round(v)))) for v in c[:3]]
    elif isinstance(c, (int, float)) and not isinstance(c, bool):
        c = float(c) % 140
        base = NL_BASE[int(c // 10)]
        shade = c % 10 - 5   # -5 black .. 0 the base .. +4.9 near white
        if shade < 0:
            rgb = [round(v * (1 + shade / 5)) for v in base]
        else:
            rgb = [round(v + (255 - v) * shade / 5) for v in base]
    else:
        rgb = [200, 200, 200]
    return "#%02x%02x%02x" % tuple(rgb)


def _lightness(c):
    r, g, b = (int(c[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return (max(r, g, b) + min(r, g, b)) / 2


def light_colour(c):
    """A NetLogo colour made to read as light on the hologram's dark ground: the hue kept, a dark colour lifted, a
    pale one held back from white, the saturation capped so it glows rather than shouts."""
    import colorsys
    r, g, b = (int(c[k:k + 2], 16) / 255 for k in (1, 3, 5))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    light = min(max(light, 0.5), 0.82)
    sat = min(sat, 0.82)
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in colorsys.hls_to_rgb(hue, light, sat))


def run_colours(run, scene):
    """Each part of a run's construct that has a colour in the run: a node its turtle's last colour, a breed's
    tracks the breed's most common colour, the field the colour the patches changed to."""
    from collections import Counter
    last = run["frames"][-1].get("turtles") or next((f["turtles"] for f in reversed(run["frames"]) if f.get("turtles")), [])
    colour = {r[0]: netlogo_rgb(r[4]) for r in last}
    breed = {}
    for r in last:
        breed.setdefault(r[1], Counter())[colour[r[0]]] += 1
    patch = None
    if run["header"].get("patch-reporter") == "pcolor":
        samples = [f["patches"] for f in run["frames"] if "patches" in f]
        if len(samples) >= 2:   # the colour the patches changed to, or from when they ended dark (food eaten)
            pairs = [(a, b) for a, b in zip(samples[0], samples[-1]) if a != b]
            to = Counter(netlogo_rgb(b) for _, b in pairs).most_common(1)
            frm = Counter(netlogo_rgb(a) for a, _ in pairs).most_common(1)
            if to:
                patch = to[0][0] if _lightness(to[0][0]) > 0.15 or not frm else frm[0][0]
    out = {}
    for part in scene["parts"]:
        pid = part["id"]
        if pid.startswith("node-") and pid[5:].isdigit() and int(pid[5:]) in colour:
            out[pid] = colour[int(pid[5:])]
        elif pid.startswith("tracks-") and pid[7:] in breed:
            out[pid] = breed[pid[7:]].most_common(1)[0][0]
        elif pid in ("surface", "fronts") and patch:
            out[pid] = patch
        elif pid.startswith("risen-") and len(pid) == 12:   # the turtles that ended in this colour
            out[pid] = "#" + pid[6:]
    return out


def materials_from_run(run, scene):
    """A material map (export --materials) in the run's own colours: each turtle's last colour, each breed's
    most common one, the colour patches changed to; the frame dark, the time axis grey."""
    from collections import Counter
    last = run["frames"][-1].get("turtles") or next((f["turtles"] for f in reversed(run["frames"]) if f.get("turtles")), [])
    colour = {r[0]: netlogo_rgb(r[4]) for r in last}
    breed = {}
    for r in last:
        breed.setdefault(r[1], Counter())[colour[r[0]]] += 1
    groups = {}
    accent = "#d16bd0"
    patch = None
    h = run["header"]
    if h.get("patch-reporter") == "pcolor":
        samples = [f["patches"] for f in run["frames"] if "patches" in f]
        if len(samples) >= 2:
            changed = Counter(netlogo_rgb(b) for a, b in zip(samples[0], samples[-1]) if a != b)
            patch = changed.most_common(1)[0][0] if changed else None
    for part in scene["parts"]:
        pid = part["id"]
        if part["role"] == "mass":                 # the world's floor plate
            c = "#1a1a1e"
        elif part["role"] == "ground":             # axes, the time axis, what is drawn on the floor
            c = "#8d8d8d"
        elif pid.startswith("node-") and pid[5:].isdigit():
            c = colour.get(int(pid[5:]), accent)
        elif pid.startswith("tracks-") and pid[7:] in breed:
            c = breed[pid[7:]].most_common(1)[0][0]
        elif pid in ("surface", "fronts"):
            c = patch or accent
        elif part.get("source") == "run":
            c = accent
        else:
            continue
        groups.setdefault(c, []).append(pid)
    return {"about": "Colours from the NetLogo run itself (each turtle's last colour, each breed's most common one, "
                     "the colour patches changed to); written by construct netlogo --materials-out.",
            "materials": [{"parts": ids, "name": "netlogo %s" % c, "color": c, "finish": "plastic", "roughness": 0.5}
                          for c, ids in groups.items()]}


def _legend(parts, sqrt=False):
    """The automatic legend: each part from the run labelled with what it is (its own label), the label's
    dot on a real point of the part, a different side for each so they don't pile up. L shows them."""
    out, named = [], set()
    shown = []
    for q in parts:   # a part split in pieces (over 4,000 lines) is named once
        if q.get("source") == "run" and q["role"] != "mass" and q["label"] not in named:
            named.add(q["label"])
            shown.append(q)
    for i, p in enumerate(shown):
        pts = [v for path in p["shape"].get("paths", []) for v in path]
        if not pts:
            continue
        lo = [min(v[k] for v in pts) for k in range(3)]
        hi = [max(v[k] for v in pts) for k in range(3)]
        anchor = [(lo[0] + hi[0]) / 2, hi[1], (lo[2] + hi[2]) / 2]   # the compiler's anchor: the box's top centre
        d = LEGEND_DIRS[i % len(LEGEND_DIRS)]
        # the dot on the lower part of what it names, so the label appears as soon as its part starts to be drawn
        early = [v for v in pts if v[1] <= lo[1] + 0.25 * (hi[1] - lo[1])] or pts
        best = max(early, key=lambda v: v[0] * d[0] + v[1] * d[1] + v[2] * d[2])
        text = p["label"] + (" (height: the square root of time)" if sqrt and p["id"] == "time-axis" else "")
        out.append({"id": "legend-" + p["id"], "part": p["id"], "text": text[:80],
                    "offset": [round(best[k] - anchor[k], 3) for k in range(3)]})
    return out


# ---------------------------------------------------------------------------- the data lock

def _canon(v):
    """Numbers as rounded floats, so rewriting 1.0 as 1, or reformatting the file, keeps the fingerprint."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 5)
    if isinstance(v, dict):
        return {k: _canon(x) for k, x in v.items()}
    return [_canon(x) for x in v]


def _locked_source(scene):
    """The source the data lock covers: the lock fact's own (`run` for a NetLogo run, `run-a` for two compared)."""
    fact = next((f for f in scene.get("facts", []) if f.get("key") == LOCK), None)
    return (fact or {}).get("source") or "run"


def data_lock(scene, source=None):
    """The fingerprint of what the data says: its source (the recording, or a track), its facts and how the
    data is drawn (view, coordinates), and every part from it, without how a part is shown (label, look,
    note)."""
    src = source or _locked_source(scene)
    ids = [s.get("id") for s in scene.get("sources", [])]
    # a lock covers its own source; two runs compared (run-a and run-b) are locked together
    srcs = ({"run-a", "run-b"} & set(ids) if src in ("run-a", "run-b") else {src}) or {src}
    facts = sorted(({k: v for k, v in f.items() if k != "note"} for f in scene.get("facts", [])
                    if f.get("key") != LOCK and (f.get("source") in srcs or f.get("key") in LOCKED_FACTS)),
                   key=lambda f: f["key"])
    parts = sorted(({k: v for k, v in p.items() if k not in LOOSE} for p in scene.get("parts", [])
                    if p.get("source") in srcs), key=lambda p: p["id"])
    data = {"source": [s for s in scene.get("sources", []) if s.get("id") in srcs], "facts": facts, "parts": parts}
    r = scene.get("reading") or {}
    if r.get("clock") or r.get("series"):   # the replay's clock and counts are the run's data too
        data["reading"] = {"clock": r.get("clock"), "series": r.get("series", [])}
    text = json.dumps(_canon(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def compare_runs(run_a, run_b, view, labels=("A", "B"), title=None, **opts):
    """Two runs side by side, drawn the same way on one time scale (the longer run's): A on the left, B on the
    right, every part, fact, label and count marked with its run, one data lock over both recordings. For a
    lesson: the same model with a slider moved, or another seed."""
    if view == "auto":
        view, auto, _ = choose_view(run_a)
        opts = dict(auto, **{k: v for k, v in opts.items() if v not in (None, False)})
    end = lambda r: r["end"] if r["end"] is not None else r["frames"][-1]["t"]
    span = max(end(run_a), end(run_b))
    scenes = [scene_from_run(r, view, title, span=span, **dict(opts, landmarks="off")) for r in (run_a, run_b)]
    gap = FLOOR * 1.35
    parts, facts, sources, notes, series = [], [], [], [], []
    for k, (sc, tag) in enumerate(zip(scenes, labels)):
        sid, px, dx = "run-" + "ab"[k], "ab"[k] + "-", (-gap / 2, gap / 2)[k]
        for p in sc["parts"]:
            q = json.loads(json.dumps(p))
            q["id"], q["label"] = px + p["id"], ("%s: %s" % (tag, p["label"]))[:80]
            if q.get("source") == "run":
                q["source"] = sid
            at = q.get("at") or [0, 0, 0]
            q["at"] = [round(at[0] + dx, 3), at[1], at[2]]
            parts.append(q)
        for f in sc["facts"]:
            if f["key"] == LOCK or (k and f["key"] in LOCKED_FACTS):
                continue
            g = dict(f)
            if f["key"] not in LOCKED_FACTS:
                g["key"] = "%s_%s" % ("ab"[k], f["key"])
                if f.get("source") == "run":
                    g["source"] = sid
            facts.append(g)
        for s in sc["sources"]:
            if s["id"] == "run":
                sources.append(dict(s, id=sid, title=("%s: %s" % (tag, s["title"]))[:200]))
            elif k == 0:
                sources.append(dict(s))
        roles = {p["id"]: p["role"] for p in sc["parts"]}
        for a in sc.get("annotations", []):   # the full legend on the left; on the right, its main part's alone
            if k == 0 or roles.get(a["part"]) == "identity":
                notes.append(dict(a, id=px + a["id"], part=px + a["part"], text=("%s: %s" % (tag, a["text"]))[:80]))
        for s in (sc["reading"].get("series") or [])[:3]:
            series.append(dict(s, name=("%s: %s" % (tag, s["name"]))[:40]))
    a, h = scenes[0], run_a["header"]
    out = dict(a, id=("netlogo-compare-%s" % a["id"].replace("netlogo-", ""))[:64], parts=parts, facts=facts,
               sources=sources, annotations=notes,
               title=title or "%s: %s and %s" % (h["title"], labels[0], labels[1]),
               subject=dict(a["subject"], summary="Two runs of NetLogo's %s side by side, drawn the same way on one "
                                                  "time scale: %s on the left, %s on the right." % (h["title"], *labels)))
    out["presentation"] = dict(a["presentation"], framing={"yaw": 0, "pitch": 26})
    out["reading"] = {"how": (["Two runs side by side, drawn the same way: %s on the left, %s on the right, on one "
                               "time scale (the longer run's)." % labels] + a["reading"]["how"])[:8],
                      "clock": dict(a["reading"]["clock"])}
    if series:
        out["reading"]["series"] = series
    out["facts"].append({"key": LOCK, "value": data_lock(out, "run-a"), "certainty": "verified", "source": "run-a",
                         "note": "Both runs' data as the bridge drew them, under one lock (sources run-a and run-b)."})
    return out


def counts_csv(run):
    """The run's counts at every record, as CSV: the clock, each tracked reporter, and each breed's turtles
    (`count <breed>`, unless the model already reports it)."""
    h, frames = run["header"], run["frames"]
    clock = "step" if h.get("clock") == "steps" else "tick"
    names = list(h.get("reporters", []))
    breeds = [b for b in sorted({row[1] for f in frames for row in f.get("turtles", [])}) if "count %s" % b not in names]
    cell = lambda x: '"%s"' % str(x).replace('"', '""') if any(ch in str(x) for ch in ',"\n') else str(x)
    lines = [",".join(cell(x) for x in [clock] + names + ["count %s" % b for b in breeds])]
    for f in frames:
        rep = f.get("reporters") or []
        vals = [("" if v is None else v) for v in (rep + [None] * len(names))[:len(names)]]
        counts = [sum(1 for row in f.get("turtles", []) if row[1] == b) for b in breeds] if "turtles" in f else [""] * len(breeds)
        lines.append(",".join(cell(x) for x in [f["t"]] + vals + counts))
    return "\n".join(lines) + "\n"


def _sampled(frames, n=300):
    """At most n frames, evenly by record, the first and last kept."""
    if len(frames) <= n:
        return frames
    return [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)]


def _reading(run, view, world, opts, time):
    """How to read the construct, its clock (time to height) and counts over time, for the page's replay."""
    h, frames = run["header"], run["frames"]
    last = world.last
    sq = time == "sqrt"
    how = {
        "space-time": [
            "The floor is the NetLogo world; height is time, from tick 0 on the floor to tick %d at the top%s." % (
                last, " (the square root of time, so the early ticks are stretched)" if sq else ""),
            "Each line is one turtle's path: upright where it stood still, leaning where it moved, flatter the "
            "faster it went.",
            "Lines that run side by side are turtles moving together.",
            "A line that starts above the floor is a turtle born then; one that stops before the top, a turtle "
            "that died or left."],
        "network-time": [
            "The floor is the network as NetLogo laid it out.",
            ("Each turtle rises to the tick it appeared: the network as it grew." if opts.get("state") == APPEARED else
             "Each turtle rises to the tick its %s first turned true; one left on the floor never turned." % opts.get("state")),
            "A link climbs from the earlier of its two turtles to the later: a steep climb joins two turtles that "
            "turned far apart in time (the link need not be the way it spread).",
            "Height is time, tick 0 to %d%s." % (last, ", as its square root, so the early spread is stretched" if sq else "")],
        "phase": [
            "Across the floor: %s; front to back: %s; height: time, tick 0 to %d." % (
                opts.get("x") or (h["reporters"] + ["", ""])[0], opts.get("z") or (h["reporters"] + ["", ""])[1], last),
            "Its shadow on the floor is the classic phase plot, and the walls show each quantity against time.",
            "A loop that rises is a cycle repeating; a spiral that narrows is a cycle settling down; a line "
            "that runs to a wall is one quantity running out."],
        "field": [
            "Each contour is where the patches' %s had changed by that tick, raised to its tick: the fronts "
            "of change, stacked in time." % h.get("patch-reporter"),
            "Contours close together: the change moved slowly there; far apart: it moved fast.",
            "Where nothing changed, nothing is drawn."],
        "pulse": [
            "Height is time, from tick 0 on the floor to tick %d at the top: one ring for each tick." % last,
            "A ring's area is the share of turtles in that state at that tick (%s); the faint circle at the floor "
            "and the top is every turtle at once." % (
                (_event_choice(run) or {}).get("word") if not opts.get("state") else
                next((s["word"] for s in _event_signals(run) if s["state"] == opts.get("state")), opts.get("state"))),
            "A thin, ragged column is turtles on their own rhythms; wide plates with nothing between are turtles in "
            "step, all at once.",
            "Where the column opens into plates is where they fell into step."],
    }[view]
    w = opts.get("_window")
    if w:   # drawn over the window where the order formed: say so, second
        how.insert(1, "This shows ticks 0 to %d, where the %s formed (%.2f at the start, %.2f by tick %d); after "
                      "that it stays near there. The whole run is in the recording and its film." % (
                          last, w["measure"], w["start"], w["reached"], last))
    picked = _sampled(frames)
    series = []
    if h.get("reporters"):
        for i, name in enumerate(h["reporters"][:4]):
            vals = [[f["t"], round(f["reporters"][i], 4)] for f in picked
                    if isinstance((f.get("reporters") or [None] * (i + 1))[i], (int, float))
                    and not isinstance(f["reporters"][i], bool)]
            if vals:
                series.append({"name": name[:40], "values": vals})
    elif view == "network-time" and opts.get("state") == APPEARED:
        series.append({"name": "turtles", "values": [[f["t"], len(f.get("turtles", []))] for f in picked if "turtles" in f]})
    elif view == "network-time":
        vi = 5 + h["turtle-vars"].index(opts.get("state"))
        series.append({"name": (opts.get("state") + " now")[:40], "values": [
            [f["t"], sum(1 for r in f.get("turtles", []) if len(r) > vi and r[vi] is True)] for f in picked]})
    elif view == "space-time":
        series.append({"name": "turtles", "values": [[f["t"], len(f.get("turtles", []))] for f in picked
                                                     if "turtles" in f]})
    elif view == "field":
        sampled = _sampled([f for f in frames if "patches" in f])
        first = sampled[0]["patches"] if sampled else []
        series.append({"name": "patches changed", "values": [
            [f["t"], sum(1 for a, b in zip(first, f["patches"]) if a != b)] for f in sampled]})
    if opts.get("_series"):   # the view's own measure (synchrony, alignment), first
        series.insert(0, opts["_series"])
    reading = {"how": how, "clock": {"label": "tick", "from": 0, "to": last, "top": world.top,
                                     "scale": "sqrt" if sq else "linear"}}
    series = [s for s in series if len({v[1] for v in s["values"]}) > 1]   # a count that never moves says nothing
    if series:
        reading["series"] = series
    return reading


def _in_steps(scene):
    """The scene's words for time as steps, not ticks, and a fact that says why."""
    word = lambda s: re.sub(r"\btick(s?)\b", r"step\1", s) if isinstance(s, str) else s
    for p in scene["parts"]:
        p["label"] = word(p["label"])
    for a in scene.get("annotations", []):
        a["text"] = word(a["text"])
    scene["subject"]["summary"] = word(scene["subject"]["summary"])
    if scene.get("reading"):
        scene["reading"]["how"] = [word(x) for x in scene["reading"]["how"]]
        scene["reading"]["clock"]["label"] = "step"
    for f in scene["facts"]:
        f["value"] = word(f["value"])
    scene["facts"].append({"key": "clock", "value": "steps", "certainty": "verified", "source": "run",
                           "note": "The model never starts NetLogo's tick counter, so each record is one step "
                                   "(one go), numbered from 0."})
    return scene


def _id_groups(ids):
    """Part ids for a note, numbered ones as a group: "network, risen, node-* (150)"."""
    out, seen = [], {}
    for i in ids:
        m = re.match(r"(.*-)\d+$", i)
        key = m.group(1) + "*" if m else i
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 1:
            out.append(key)
    return ", ".join(k if seen[k] == 1 else "%s (%d)" % (k, seen[k]) for k in out)


def lock(scene):
    """The scene with its data_lock fact."""
    run_parts = [p["id"] for p in scene["parts"] if p.get("source") == "run"]
    scene["facts"] = [f for f in scene["facts"] if f["key"] != LOCK] + [
        {"key": LOCK, "value": data_lock(scene), "certainty": "verified", "source": "run",
         "note": ("The data as the bridge drew it from the recording: %d parts (%s), the run's facts and the view. "
                 "The audit refuses the scene if any of it changes." % (len(run_parts), _id_groups(run_parts)))[:600]}]
    return scene


def lock_problem(scene):
    """None when the scene has no data lock or its data is as the bridge drew it; else what is wrong."""
    fact = next((f for f in scene.get("facts", []) if f.get("key") == LOCK), None)
    if fact is None or fact.get("value") == data_lock(scene):
        return None
    return ("the data drawn from the NetLogo recording changed since the bridge drew it (a part, fact or source "
            "with source \"run\", or the view or coordinates fact). Restore them from `construct netlogo`; art "
            "direction may change only a data part's label, look and note, and adds its own parts and facts "
            "with another source (docs/NETLOGO.md, Art direction).")


# ---------------------------------------------------------------------------- art direction

def apply_art(scene, art):
    """An art-direction layer (art.json) on a locked scene: a title and summary, views and atmosphere,
    the label, look or note of data parts (`looks`), and new parts, facts and annotations of its own, credited
    to `credit` (the model that directed it). Never the data: the result keeps the bridge's lock."""
    if not isinstance(art, dict):
        raise NetLogoError("art: expected a JSON object")
    unknown = sorted(set(art) - ART_KEYS)
    if unknown:
        raise NetLogoError("art: unknown key %s (one of %s)" % (", ".join(unknown), ", ".join(sorted(ART_KEYS))))
    if lock_problem(scene) or not any(f["key"] == LOCK for f in scene["facts"]):
        raise NetLogoError("art goes on a scene as `construct netlogo` drew it (locked, unchanged)")
    out = json.loads(json.dumps(scene))
    credit = art.get("credit")
    if not isinstance(credit, str) or not credit.strip():
        raise NetLogoError("art.credit: name the model (or person) that directed it, e.g. \"Claude Opus 5.5\"")
    out["sources"].append({"id": "art", "kind": "generated", "title": "Art direction by %s" % credit.strip(),
                           "rights": "synthetic"})
    if "title" in art:
        out["title"] = art["title"]
    if "summary" in art:
        out["subject"]["summary"] = art["summary"]
    if "reading" in art:   # its own way of reading the construct; the clock and counts stay the run's
        r = art["reading"]
        if not isinstance(r, dict) or set(r) - {"how"} or not isinstance(r.get("how"), list):
            raise NetLogoError("art.reading: only `how`, a list of lines (the clock and counts are the run's)")
        out["reading"] = dict(out.get("reading") or {}, how=list(r["how"]))
    data_ids = {p["id"] for p in out["parts"]}
    for pid, change in (art.get("looks") or {}).items():
        if pid not in data_ids:
            raise NetLogoError("art.looks: no data part %r (one of %s)" % (pid, ", ".join(sorted(data_ids))))
        if not isinstance(change, dict) or set(change) - set(LOOSE):
            raise NetLogoError("art.looks.%s: only %s" % (pid, ", ".join(LOOSE)))
        part = next(p for p in out["parts"] if p["id"] == pid)
        for k, v in change.items():
            part[k] = dict(part.get("look", {}), **v) if k == "look" else v
    for kind in ("facts", "parts"):
        for item in art.get(kind) or []:
            if not isinstance(item, dict):
                raise NetLogoError("art.%s: expected objects" % kind)
            if item.get("source") == "run" or (kind == "facts" and item.get("key") in LOCKED_FACTS + (LOCK,)):
                raise NetLogoError("art.%s: %r claims the recording; art's own %s use source \"art\" (or none)"
                                   % (kind, item.get("id") or item.get("key"), kind))
            out[kind].append(dict(item))
    for a in out.get("annotations", []):   # the automatic legend follows a data part's new label
        part = next((p for p in out["parts"] if "legend-" + p["id"] == a["id"]), None)
        if part is not None:
            a["text"] = part["label"][:80]
    if art.get("legend") is False:
        out["annotations"] = [a for a in out.get("annotations", []) if not a["id"].startswith("legend-")]
    if art.get("annotations"):
        out["annotations"] = out.get("annotations", []) + [dict(a) for a in art["annotations"]]
    if "presentation" in art:
        out["presentation"] = dict(out["presentation"], **art["presentation"])
    if "animation" in art:
        out["animation"] = art["animation"]
    return out
