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

Every data part is `verified` against the recording (a `dataset` source naming the model, NetLogo's
version and the seed); the build rises from the floor, so a construct's assembly replays the run.
Python standard library only.
"""

import json
import math
import re
from pathlib import Path

from . import product

FLOOR = 10.0         # metres: the world's longer side on the floor
HEIGHT = 6.0         # metres: tick 0 to the last tick (a space-time cube is as tall as it is wide)
MAX_SEGMENTS = 18000  # of the line budget (24,000), for the data; the scene stays under 1 MB
VIEWS = ("space-time", "network-time", "phase", "field")
NLS = Path(__file__).resolve().parent / "construct.nls"   # the recorder, copied beside a model
TONES = ("identity", "data", "accent", "bright", "dust", "structure")
# each view's hero: a field's fronts climb like a slope, so it is seen from above its rise
FRAMING = {"space-time": {"yaw": 32, "pitch": 20}, "network-time": {"yaw": 30, "pitch": 26},
           "phase": {"yaw": 35, "pitch": 24}, "field": {"yaw": -38, "pitch": 46}}


class NetLogoError(ValueError):
    pass


# ---------------------------------------------------------------------------- the model

def _list(items):
    return "[" + " ".join(json.dumps(i) for i in items) + "]"


def instrument(text, title, run_file, turtles=(), reporters=(), patches=None, every=1, seed=None, ticks=500,
               skip_turtles=False):
    """A NetLogo model (.nlogox text) that records itself: `__includes ["construct.nls"]`, the recording
    set up after setup's `reset-ticks`, `construct-record` after go's `tick`. Returns (model text,
    experiment XML for `NetLogo_Console --headless --setup-file`)."""
    m = re.search(r"<code><!\[CDATA\[(.*?)\]\]></code>", text, re.S)
    if not m:
        raise NetLogoError("not a NetLogo 7 model (.nlogox): no <code> section")
    code = m.group(1)
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

    def after(proc, word, lines, code):
        b = re.search(r"(?mi)^\s*to\s+%s\b.*?^\s*end\b" % proc, code, re.S)
        if not b:
            raise NetLogoError("no `to %s` procedure in the model" % proc)
        body = b.group(0)
        hits = list(re.finditer(r"(?m)^(\s*)(%s)\b(.*)$" % word, body))
        if not hits:
            raise NetLogoError("no `%s` in `%s`: add the construct lines by hand (see construct.nls)" % (word, proc))
        h = hits[-1] if word == "tick" else hits[0]
        pad = h.group(1)
        new = body[:h.end()] + "".join("\n%s%s" % (pad, ln) for ln in lines) + body[h.end():]
        return code[:b.start()] + new + code[b.end():]

    code = after("setup", "reset-ticks", start, code)
    code = after("go", "tick", ["construct-record"], code)
    model = text[:m.start(1)] + code + text[m.end(1):]
    setup = ("random-seed %d\n" % seed if seed is not None else "") + "setup"
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<experiments>\n'
           '  <experiment name="construct" repetitions="1" sequentialRunOrder="true" runMetricsEveryStep="false" '
           'timeLimit="%d">\n    <setup>%s</setup>\n    <go>go</go>\n    <postRun>construct-finish</postRun>\n'
           '    <metrics>\n      <metric>ticks</metric>\n    </metrics>\n  </experiment>\n</experiments>\n'
           % (ticks, setup))
    return model, xml


# ---------------------------------------------------------------------------- the recording

def read_run(path):
    header, frames, end = None, [], None
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
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
    n_all = len(tracks)
    summary = ("Each turtle's track rising with time: the floor is the world, height is ticks, so a turtle that "
               "stands still draws a vertical line and a moving one leans.")
    facts = [("agents_drawn", "%d of %d turtles%s" % (len(whos), n_all, "" if len(whos) == n_all else
                                                       ", chosen evenly by who")),
             ("sampling", "every %d record%s" % (stride, "" if stride == 1 else "s"))]
    return parts, summary, facts


def _network_time(run, world, opts):
    var = opts.get("state")
    names = run["header"]["turtle-vars"]
    if var not in names:
        raise NetLogoError("network-time needs --state, a turtle variable the recording tracked (%s)" %
                           (", ".join(names) or "none were: use construct-track-turtles"))
    vi = 5 + names.index(var)
    links = next((f["links"] for f in reversed(run["frames"]) if "links" in f), None)
    if not links:
        raise NetLogoError("network-time needs links in the recording")
    last = run["frames"][-1]["turtles"]
    pos = {r[0]: (r[2], r[3]) for r in last}
    when = {}
    for f in run["frames"]:
        for r in f["turtles"]:
            v = r[vi]
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
    if stems:
        parts.append(_part("risen", "Each turtle, risen to the tick %s turned true" % var, "data",
                           {"type": "paths", "paths": stems}, tone="dust", weight=0.6))
    if climb:
        parts.append(_part("climb", "Links between risen turtles, from the earlier to the later", "identity",
                           {"type": "paths", "paths": climb}))
    summary = ("The network on the floor; each turtle rises to the tick its %s first turned true, and each link "
               "between two risen turtles climbs from the earlier to the later." % var)
    facts = [("state", var), ("turned", "%d of %d turtles" % (len(when), len(pos)))]
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
    parts = [_part("fronts", "Where the %s %s changed, every %s ticks, raised to its tick" % (
        src, mode, round((t1 - t0) / (levels + 1), 1)), "identity", {"type": "paths", "paths": fronts[:4000]})]
    summary = ("The front of change: where each patch's %s %s changed, drawn every few ticks and raised to its "
               "tick, so the run's spread rises as a stack of fronts; where nothing changed, nothing is drawn."
               % (src, mode))
    facts = [("patch_reporter", src), ("changed", "%d of %d patches" % (len(changed), len(when))),
             ("fronts", "%d levels, tick %d to %d" % (levels, t0, t1))]
    if step > 1:
        facts.append(("grid", "%d x %d patches in blocks of %d" % (cols, rows, step)))
    return parts, summary, facts


def scene_from_run(run, view, title=None, **opts):
    """A construct-scene v2 from a recording, for one of VIEWS."""
    if view not in VIEWS:
        raise NetLogoError("view: one of %s" % ", ".join(VIEWS))
    h, frames = run["header"], run["frames"]
    last = run["end"] if run["end"] is not None else frames[-1]["t"]
    time = opts.get("time") or "linear"
    if time not in ("linear", "sqrt"):
        raise NetLogoError("time: linear or sqrt")
    world = _World(h, last, FLOOR if view == "space-time" else HEIGHT, time)
    data, summary, extra = {"space-time": _space_time, "network-time": _network_time, "phase": _phase,
                            "field": _field}[view](run, world, opts)
    if view == "phase":
        parts = [p for p in data]
    else:
        parts = _frame_axis(world) + data
    title = title or h["title"]
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
    facts += [{"key": k, "value": v, "certainty": "verified", "source": "run"} for k, v in extra]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "netlogo-run"
    return {
        "format": product.SCENE_FORMAT, "version": 2, "id": "netlogo-%s-%s" % (slug, view), "title": title,
        "subject": {"category": "other", "accuracy": "documented", "synthetic": False,
                    "summary": "One run of NetLogo's %s. %s" % (h["title"], summary)},
        "units": "m", "seed": 7,
        "sources": [{"id": "request", "kind": "user_request", "title": "A construct of a NetLogo run",
                     "rights": "user_private"},
                    {"id": "run", "kind": "dataset", "title": "A run of %s, recorded with construct.nls" % model,
                     "rights": "permitted"}],
        "facts": facts, "parts": parts,
        "presentation": {"framing": FRAMING[view], "atmosphere": {"haze": 0.6, "grid": False, "projector": True}},
        "animation": {"assembly": {"style": "build", "seconds": 12.0},
                      "idle": {"life": "calm", "events": ["scan"], "cadence": [8, 14], "strength": 0.4},
                      "camera": {"drift": 4, "breathe": 0.02}},
    }
