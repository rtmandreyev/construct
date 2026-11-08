"""Worlds: whole constructs placed in one scene.

A world places constructs (and other worlds) by reference. Each placed construct is kept whole: its parts, sources,
facts, provenance, critic record and articulations are its own, under its placement's id (`vespa/legshield`,
`vespa/photo-front`). A world is not a bigger construct: a construct stays within a construct's budgets and
checks, and a world has budgets of its own, for many constructs at once.

    {"format": "construct-world", "version": 1, "id": "my-villa", "title": "My Villa Savoye",
     "summary": "...", "origin": {"lat": 48.924, "lon": 2.028},
     "placements": [
       {"id": "villa", "construct": "villa-savoye"},
       {"id": "eames", "construct": "eames-lounge-chair", "on": "villa/salon-floor", "at": [3.2, 0, -1.5], "yaw": 30},
       {"id": "vespa", "construct": "constructs/vespa-gs150/scene.json", "on": "villa", "at": [4, 0, 6], "yaw": 90},
       {"id": "saturn", "construct": "saturn", "sky": {"diameter_m": 1.165e8, "distance_m": 3.84e8,
                                                       "azimuth": 120, "elevation": 25}},
       {"id": "district", "construct": "district.world.json", "at": [600, 0, 0]}],
     "presentation": {"framing": {"yaw": 30, "pitch": 18}, "views": [{"id": "salon", "target": "eames"}]},
     "animation": {"assembly": {"seconds": 40}}}

Placement: `at` (metres; with `on`, x and z are on the host and y is a lift above its top), `yaw` (degrees about
+Y), `rotate` (degrees, after yaw), `scale` (1 is real size; anything else is said wherever the construct is
shown), `on` (a placement, or a placement's part: it stands on that part's top), `floating` (it is meant to
hover: a ship, a lamp on a wire), `sky` (far away at its real angular size: a planet, a moon), `note` (why it is
there). A placement's construct is a path to a scene or a world (relative to the world's file), or a name a
resolver knows (the plugin's projects and stock constructs, the repository's gallery).

The compiled world has the shape of a construct's geometry, so the viewer, the solid view, provenance and the
exports read it as they read a construct; it adds `world` (the placements). Placements of the same construct
are compiled once.
"""

import json
import math
from pathlib import Path

from . import scene as scene_mod

WORLD_FORMAT = "construct-world"
WORLD_VERSION = 1
MAX_PLACEMENTS = 4096
MAX_DEPTH = 8                 # worlds inside worlds: a city, its districts, their buildings, their rooms
WORLD_EXTENT = 1.0e6          # metres from the origin: a city with room to spare (a construct's own is 500 m)
WORLD_MAX_LINES = 400000      # a world's page; a construct's own budget is scene.MAX_LINES
WORLD_MAX_TRIS = 400000
WORLD_MAX_POINTS = 60000
WORLD_MAX_SOLID_TRIS = 2000000
SKY_RENDER = 6.0              # a sky placement is drawn this many world radii away, at its real angular size
TOP = {"format", "version", "id", "title", "summary", "origin", "placements", "presentation", "animation", "authoring"}
PLACEMENT = {"id", "construct", "label", "at", "yaw", "rotate", "scale", "on", "floating", "sky", "note"}
SKY = {"diameter_m", "distance_m", "azimuth", "elevation", "spin", "of"}
VIEW = {"id", "label", "target", "yaw", "pitch", "distance"}
MAX_VIEWS = 48


class WorldError(ValueError):
    pass


def _ident(v):
    """A construct's id rule (scene.py): lowercase letters, digits, - _ . ; at most 64; no `/` (it joins paths)."""
    return isinstance(v, str) and 0 < len(v) <= 64 and v[0].isalnum() and \
        all(c.isalnum() or c in "-_." for c in v) and v == v.lower()


def is_world(doc):
    return isinstance(doc, dict) and doc.get("format") == WORLD_FORMAT


# ---------------------------------------------------------------------------- validation

def validate(doc):
    """Problems with a world document, as `where: message` strings (an empty list: it is valid)."""
    errs = []
    err = lambda where, msg: errs.append("%s: %s" % (where, msg))
    if not isinstance(doc, dict):
        return ["world: expected an object"]
    for k in sorted(set(doc) - TOP):
        err("world." + k, "unknown key (allowed: %s)" % ", ".join(sorted(TOP)))
    if doc.get("format") != WORLD_FORMAT:
        err("world.format", "expected %r" % WORLD_FORMAT)
    if doc.get("version") != WORLD_VERSION:
        err("world.version", "expected %d" % WORLD_VERSION)
    for k in ("id", "title"):
        if not isinstance(doc.get(k), str) or not doc.get(k).strip():
            err("world." + k, "expected a non-empty string")
    if isinstance(doc.get("id"), str) and not _ident(doc["id"]):
        err("world.id", "expected a lowercase id (letters, digits, - _ .; at most 64)")
    o = doc.get("origin")
    if o is not None:
        if not isinstance(o, dict) or set(o) - {"lat", "lon", "alt_m"} or not _num(o.get("lat"), -90, 90) \
                or not _num(o.get("lon"), -180, 180) or ("alt_m" in o and not _num(o["alt_m"], -1e4, 1e5)):
            err("world.origin", "expected {lat: -90..90, lon: -180..180, alt_m?}")
    ps = doc.get("placements")
    if not isinstance(ps, list) or not 1 <= len(ps) <= MAX_PLACEMENTS:
        err("world.placements", "expected 1..%d placements" % MAX_PLACEMENTS)
        return errs
    seen = set()
    for i, p in enumerate(ps):
        w = "world.placements[%d]" % i
        if not isinstance(p, dict):
            err(w, "expected an object")
            continue
        for k in sorted(set(p) - PLACEMENT):
            err(w + "." + k, "unknown key (allowed: %s)" % ", ".join(sorted(PLACEMENT)))
        pid = p.get("id")
        if not _ident(pid):
            err(w + ".id", "expected a lowercase id (letters, digits, - _ .; at most 64)")
        elif pid in seen:
            err(w + ".id", "%r is placed twice; give each placement its own id" % pid)
        else:
            seen.add(pid)
        if not isinstance(p.get("construct"), str) or not p["construct"].strip():
            err(w + ".construct", "expected a construct's name or a path to its scene (or to a world)")
        if "at" in p and not _vec(p["at"], WORLD_EXTENT):
            err(w + ".at", "expected [x, y, z] in metres, within %g m of the origin" % WORLD_EXTENT)
        if "yaw" in p and not _num(p["yaw"], -3600, 3600):
            err(w + ".yaw", "expected degrees")
        if "rotate" in p and not _vec(p["rotate"], 3600):
            err(w + ".rotate", "expected [x, y, z] in degrees")
        if "scale" in p and not _num(p["scale"], 1e-6, 1e6, open_lo=True):
            err(w + ".scale", "expected a positive number (1 is real size)")
        if "floating" in p and not isinstance(p["floating"], bool):
            err(w + ".floating", "expected true or false")
        if "note" in p and not isinstance(p["note"], str):
            err(w + ".note", "expected text")
        if "label" in p and not isinstance(p["label"], str):
            err(w + ".label", "expected text")
        if "on" in p:
            on = p["on"]
            host = on.split("/", 1)[0] if isinstance(on, str) else None
            if host is None or host not in seen or host == pid:
                err(w + ".on", "expected an earlier placement's id, or `placement/part-id`")
            if "sky" in p:
                err(w + ".on", "a sky placement stands on nothing")
        sky = p.get("sky")
        if sky is not None:
            if not isinstance(sky, dict) or set(sky) - SKY:
                err(w + ".sky", "expected {diameter_m, distance_m, of?, azimuth?, elevation?, spin?}")
            else:
                if not _num(sky.get("diameter_m"), 0, 1e22, open_lo=True):
                    err(w + ".sky.diameter_m", "expected the real diameter in metres")
                if not _num(sky.get("distance_m"), 0, 1e27, open_lo=True):
                    err(w + ".sky.distance_m", "expected the distance in metres")
                elif _num(sky.get("diameter_m"), 0, 1e22, open_lo=True) and sky["distance_m"] <= sky["diameter_m"]:
                    err(w + ".sky.distance_m", "expected a distance larger than the diameter")
                if "of" in sky and not (isinstance(sky["of"], str) and sky["of"].strip()):
                    err(w + ".sky.of", "expected the id of the part whose real diameter diameter_m is (a planet's globe)")
                for k, lo, hi in (("azimuth", -360, 360), ("elevation", -90, 90), ("spin", -3600, 3600)):
                    if k in sky and not _num(sky[k], lo, hi):
                        err(w + ".sky." + k, "expected degrees in %g..%g" % (lo, hi))
            if "at" in p or "scale" in p:
                err(w + ".sky", "a sky placement's place and size come from its distance and diameter: drop at/scale")
    an = doc.get("animation")
    if an is not None:
        asm = an.get("assembly", {}) if isinstance(an, dict) else None
        if not isinstance(an, dict) or not isinstance(asm, dict) or set(an) - {"assembly", "camera", "idle"}:
            err("world.animation", "expected {assembly?: {seconds?, order?}, camera?, idle?}")
        else:
            if "seconds" in asm and not _num(asm["seconds"], 1, 3600):
                err("world.animation.assembly.seconds", "expected 1..3600")
            if "order" in asm and (not isinstance(asm["order"], list) or set(asm["order"]) - seen):
                err("world.animation.assembly.order", "expected placement ids")
    pr = doc.get("presentation")
    if pr is not None:
        if not isinstance(pr, dict) or set(pr) - {"framing", "views"}:
            err("world.presentation", "expected {framing?, views?}")
        else:
            views = pr.get("views", [])
            if not isinstance(views, list) or len(views) > MAX_VIEWS:
                err("world.presentation.views", "expected at most %d views" % MAX_VIEWS)
                views = []
            vids = set()
            for i, v in enumerate(views):
                vw = "world.presentation.views[%d]" % i
                if not isinstance(v, dict) or set(v) - VIEW or not _ident(v.get("id")):
                    err(vw, "expected {id, label?, target?, yaw?, pitch?, distance?} with a lowercase id")
                    continue
                if v["id"] in vids:
                    err(vw + ".id", "%r is named twice" % v["id"])
                vids.add(v["id"])
                if "label" in v and not (isinstance(v["label"], str) and 0 < len(v["label"]) <= 48):
                    err(vw + ".label", "expected a short name (at most 48 characters)")
                t = v.get("target")
                if t is not None and not (isinstance(t, str) and t.split("/", 1)[0] in seen):
                    err(vw + ".target", "expected a placement id or `placement/part-id`")
                for k, lo, hi in (("yaw", -3600, 3600), ("pitch", -89, 89), ("distance", 0.01, 100)):
                    if k in v and not _num(v[k], lo, hi):
                        err(vw + "." + k, "expected %g..%g" % (lo, hi))
    return errs


def _num(v, lo, hi, open_lo=False):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and \
        (v > lo if open_lo else v >= lo) and v <= hi


def _vec(v, lim):
    return isinstance(v, list) and len(v) == 3 and all(_num(x, -lim, lim) for x in v)


# ---------------------------------------------------------------------------- resolving

def load(path):
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc


def default_resolver(name, base_dir):
    """A construct's scene (or a world) by path, else by name from the repository's gallery."""
    cand = []
    p = Path(name)
    if name.endswith(".json"):
        cand.append(p if p.is_absolute() else Path(base_dir) / p)
    else:
        root = Path(__file__).resolve().parent.parent
        for d in (root / "examples" / name, root / "examples" / "films" / name, root / "hosts" / "hermes" / "examples" / name,
                  Path(__file__).resolve().parent / "examples" / name, Path(base_dir) / name):
            for f in ("scene.json", "scene.params.json", "world.json"):
                cand.append(d / f)
    for c in cand:
        if c.is_file():
            return c
    raise WorldError("no construct %r (looked for %s)" % (name, ", ".join(str(c) for c in cand[:4]) + ("…" if len(cand) > 4 else "")))


def _read_scene(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if is_world(doc):
        return doc
    from . import params
    if params.is_params(doc):
        doc = params.expand(doc)
    return doc


# ---------------------------------------------------------------------------- transforms

def _yaw_rot(yaw, rotate):
    r = scene_mod._rot([0.0, yaw, 0.0])
    if rotate:
        r2 = scene_mod._rot(rotate)
        r = [[sum(r[i][k] * r2[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return r


class _Xf:
    """p' = t + s * R p"""

    def __init__(self, rot, scale, t):
        self.r, self.s, self.t = rot, scale, t

    def p(self, v):
        m = scene_mod._mul(self.r, v)
        return [self.t[k] + self.s * m[k] for k in range(3)]

    def d(self, v):   # a direction
        m = scene_mod._mul(self.r, v)
        n = math.sqrt(sum(x * x for x in m)) or 1.0
        return [x / n for x in m]

    def box(self, lo, hi):
        cs = [self.p([x, y, z]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        return [min(c[k] for c in cs) for k in range(3)], [max(c[k] for c in cs) for k in range(3)]


_r = scene_mod._r


# ---------------------------------------------------------------------------- compiling

def compile_world(doc, base_dir=".", resolver=None, solid=False, _depth=0, _stack=(), _cache=None):
    """The world as one geometry (the shape a construct compiles to, plus `world`). Raises WorldError."""
    errs = validate(doc)
    if errs:
        raise WorldError("\n".join(errs))
    if _depth > MAX_DEPTH:
        raise WorldError("worlds nested deeper than %d" % MAX_DEPTH)
    resolve = resolver or default_resolver
    cache = _cache if _cache is not None else {}
    out = _Empty()
    placements = doc["placements"]
    order = list(doc.get("animation", {}).get("assembly", {}).get("order", [])) or [p["id"] for p in placements]
    order += [p["id"] for p in placements if p["id"] not in order]
    weight = {pid: (3.0 if i == 0 else 1.0) for i, pid in enumerate(order)}
    total = sum(weight.values())
    start, acc = {}, 0.0
    for pid in order:
        start[pid] = acc / total
        acc += weight[pid]
    records, sky_parts = [], set()
    for p in placements:
        path = resolve(p["construct"], base_dir)
        key = (str(Path(path).resolve()), solid)
        if key in _stack:
            raise WorldError("placement %r: %s places itself" % (p["id"], p["construct"]))
        if key not in cache:
            src = _read_scene(path)
            if is_world(src):
                g = compile_world(src, Path(path).parent, resolver, solid, _depth + 1, _stack + (key,), cache)
            else:
                try:
                    g = scene_mod.compile_scene(src, solid=solid)
                except scene_mod.SceneError as e:
                    raise WorldError("placement %r: %s does not compile:\n%s" % (p["id"], p["construct"], e))
                g = dict(g)
                g["_scene"] = src
            g["_path"] = str(path)
            cache[key] = g
        g = cache[key]
        xf, info = _placement_xf(p, g, out)
        span = weight[p["id"]] / total
        _append(out, g, p["id"], xf, start[p["id"]], span, sky="sky" in p)
        rec = {"id": p["id"], "construct": p["construct"], "title": g["title"], "label": p.get("label", g["title"]),
               "subject": g.get("subject", {}), "at": [_r(x) for x in xf.t], "yaw": p.get("yaw", 0),
               "scale": _r(xf.s), "parts": len(g["parts"]), "kind": "world" if g.get("world") else "construct",
               "scene_sha256": g.get("scene_sha256"), **info}
        for k in ("rotate", "on", "floating", "note", "sky"):
            if k in p:
                rec[k] = p[k]
        critic = (g.get("provenance", {}).get("authoring") or {}).get("critic")
        if critic:
            rec["critic"] = {"verdict": critic.get("verdict"), "round": critic.get("round")}
        if g.get("world"):
            rec["placements"] = len(g["world"]["placements"])
        records.append(rec)
    n = len(out.lines) // 9, len(out.fills) // 15, len(out.points) // 7
    if not solid and (n[0] > WORLD_MAX_LINES or n[1] > WORLD_MAX_TRIS or n[2] > WORLD_MAX_POINTS):
        raise WorldError("world budget exceeded: %d lines (max %d), %d triangles (max %d), %d points (max %d)"
                         % (n[0], WORLD_MAX_LINES, n[1], WORLD_MAX_TRIS, n[2], WORLD_MAX_POINTS))
    if solid and n[1] > WORLD_MAX_SOLID_TRIS:
        raise WorldError("world budget exceeded: %d solid triangles (max %d)" % (n[1], WORLD_MAX_SOLID_TRIS))
    return _finish(doc, out, records, n, solid)


class _Empty:
    def __init__(self):
        self.parts, self.styles, self.style_colors = [], [], []
        self.lines, self.fills, self.points = [], [], []
        self.motions, self.arts, self.joints = [], [], []
        self.artwork, self.labels, self.annotations = [], [], []
        self.sources, self.facts, self.assets, self.checked = [], [], [], []
        self.first = None


def _bounds(parts, sky=False):
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for p in parts:
        if bool(p.get("sky")) != sky:
            continue
        for b in p["instances"]:
            for k in range(3):
                lo[k], hi[k] = min(lo[k], b["min"][k]), max(hi[k], b["max"][k])
    return (lo, hi) if lo[0] <= hi[0] else None


def _placement_xf(p, g, out):
    """Where a placement goes: its rotation, scale and translation, and what it stands on."""
    rot = _yaw_rot(p.get("yaw", 0.0), p.get("rotate"))
    info = {}
    if "sky" in p:
        sky = p["sky"]
        here = _bounds(out.parts) or ([-1, 0, -1], [1, 1, 1])
        c = [(here[0][k] + here[1][k]) / 2 for k in range(3)]
        rad = max(20.0, 0.5 * math.sqrt(sum((here[1][k] - here[0][k]) ** 2 for k in range(3))))
        dist = SKY_RENDER * rad
        az, el = math.radians(sky.get("azimuth", 0.0)), math.radians(sky.get("elevation", 30.0))
        d = [math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)]
        b = g["bounds"]
        model_d = max(b["max"][k] - b["min"][k] for k in range(3)) or 1.0
        if sky.get("of"):   # diameter_m is this part's (a planet's globe; its rings and moons come at the same scale)
            ob = [x for q in g["parts"] if q["id"] == sky["of"] for x in q["instances"]]
            if not ob:
                raise WorldError("placement %r: sky.of names no part %r of %s" % (p["id"], sky["of"], p["construct"]))
            model_d = max(max(x["max"][k] for x in ob) - min(x["min"][k] for x in ob) for k in range(3)) or 1.0
        ang = 2 * math.atan(sky["diameter_m"] / (2 * sky["distance_m"]))   # its real angular diameter
        scale = 2 * dist * math.tan(ang / 2) / model_d
        mid = [(b["min"][k] + b["max"][k]) / 2 for k in range(3)]
        m = scene_mod._mul(rot, mid)
        t = [c[k] + d[k] * dist - scale * m[k] for k in range(3)]
        info["angular_deg"] = _r(math.degrees(ang))
        return _Xf(rot, scale, t), info
    s = p.get("scale", 1.0)
    at = list(p.get("at", [0.0, 0.0, 0.0]))
    if "on" in p:
        host, _, part = p["on"].partition("/")
        prefix = host + "/" + (part if part else "")
        boxes = [b for q in out.parts if (q["id"] == prefix if part else q["id"].startswith(prefix)) and not q.get("sky")
                 for b in q["instances"]]
        if not boxes:
            raise WorldError("placement %r: nothing to stand on at %r" % (p["id"], p["on"]))
        lo = [min(b["min"][k] for b in boxes) for k in range(3)]
        hi = [max(b["max"][k] for b in boxes) for k in range(3)]
        b = g["bounds"]
        # its lowest point (rotated, scaled) on the host's top; x and z from `at` (else the host's middle)
        rlo, _ = _Xf(rot, s, [0, 0, 0]).box(b["min"], b["max"])
        top = hi[1]
        if part:   # a floor part: its top; a whole placement: the ground it stands on
            info["on_top"] = _r(top)
        else:
            top = lo[1]
        x = at[0] if "at" in p else (lo[0] + hi[0]) / 2
        z = at[2] if "at" in p else (lo[2] + hi[2]) / 2
        if "at" in p and not part:   # on a placement: `at` is relative to that placement's origin
            hrec = next(r for r in out.placed if r[0] == host)
            x, z = hrec[1][0] + at[0], hrec[1][2] + at[2]
        t = [x, top - rlo[1] + (at[1] if "at" in p else 0.0), z]
    else:
        t = at
    out.placed = getattr(out, "placed", []) + [(p["id"], t)]
    return _Xf(rot, s, t), info


def _pre(pid, s):
    return s if s is None else "%s/%s" % (pid, s)


def _append(out, g, pid, xf, start, span, sky=False):
    po, so, mo, ao, jo = len(out.parts), len(out.styles), len(out.motions), len(out.arts), len(out.joints)
    out.index = getattr(out, "index", -1) + 1
    if out.first is None:
        out.first = g
    out.placed = getattr(out, "placed", [])
    if not any(r[0] == pid for r in out.placed):
        out.placed.append((pid, xf.t))
    ph = lambda v: _r(start + span * min(1.0, max(0.0, v)))
    for st in g["styles"]:
        row = list(st)
        if row[6] >= 0:
            row[6] += po
        if row[7] >= 0:
            row[7] += mo
        if len(row) > 9 and row[9] >= 0:
            row[9] += jo
        if sky:   # far by design: the viewer's depth haze never fades it (a fade of -1)
            row[5] = -1
        out.styles.append(row)
    cols = g.get("style_colors") or [None] * len(g["styles"])
    out.style_colors.extend(cols)
    L = g["lines"]
    for i in range(0, len(L), 9):
        a, b = xf.p(L[i:i + 3]), xf.p(L[i + 3:i + 6])
        out.lines.extend([_r(a[0]), _r(a[1]), _r(a[2]), _r(b[0]), _r(b[1]), _r(b[2]), L[i + 6] + so, ph(L[i + 7]), ph(L[i + 8])])
    F = g["fills"]
    for i in range(0, len(F), 5):
        a = xf.p(F[i:i + 3])
        out.fills.extend([_r(a[0]), _r(a[1]), _r(a[2]), F[i + 3] + so, ph(F[i + 4])])
    P = g["points"]
    for i in range(0, len(P), 7):
        a = xf.p(P[i:i + 3])
        out.points.extend([_r(a[0]), _r(a[1]), _r(a[2]), P[i + 3], P[i + 4] + so, P[i + 5], ph(P[i + 6])])
    for p in g["parts"]:
        q = dict(p)
        q["id"] = _pre(pid, p["id"])
        q["placement"] = pid
        q["basis"] = [_pre(pid, x) for x in p.get("basis", [])]
        q["source"] = _pre(pid, p.get("source"))
        if p.get("joint", -1) >= 0:
            q["joint"] = p["joint"] + jo
        if sky or p.get("sky"):
            q["sky"] = True
        q["stage"] = out.index
        insts = []
        for b in p["instances"]:
            lo, hi = xf.box(b["min"], b["max"])
            nb = {"min": [_r(x) for x in lo], "max": [_r(x) for x in hi],
                  "motion_slot": b["motion_slot"] + mo if b.get("motion_slot", -1) >= 0 else -1,
                  "joint": b["joint"] + jo if b.get("joint", -1) >= 0 else -1}
            if "open_min" in b:
                olo, ohi = xf.box(b["open_min"], b["open_max"])
                nb["open_min"], nb["open_max"] = [_r(x) for x in olo], [_r(x) for x in ohi]
            insts.append(nb)
        q["instances"] = insts
        if p.get("motion") is not None and isinstance(p["motion"], int):
            q["motion"] = p["motion"] + mo
        out.parts.append(q)
    for m in g["motions"]:
        q = dict(m)
        q["axis"] = [_r(x) for x in xf.d(m["axis"])]
        q["pivot"] = [_r(x) for x in xf.p(m["pivot"])]
        if "distance" in q:
            q["distance"] = _r(q["distance"] * xf.s)
        out.motions.append(q)
    for a in g["articulations"]:
        q = dict(a)
        q["id"] = _pre(pid, a["id"])
        q["axis"] = [_r(x) for x in xf.d(a["axis"])]
        if a.get("pivot") is not None:
            q["pivot"] = [_r(x) for x in xf.p(a["pivot"])]
        if a["type"] in ("slide", "lift"):
            q["amount"] = _r(a["amount"] * xf.s)
        q["parts"] = [_pre(pid, x) for x in a["parts"]]
        q["instances"] = [[_pre(pid, x) if isinstance(x, str) else x + po, i] for x, i in a.get("instances", [])]
        q["placement"] = pid
        out.arts.append(q)
    for ch in g["joints"]:
        out.joints.append([i + ao for i in ch])
    for a in g.get("artwork", []):
        q = dict(a)
        q["part"] = _pre(pid, a["part"])
        q["asset_id"] = _pre(pid, a.get("asset_id"))
        q["corners"] = [[_r(x) for x in xf.p(c)] for c in a["corners"]]
        q["motion_slot"] = a["motion_slot"] + mo if a.get("motion_slot", -1) >= 0 else -1
        q["joint"] = a["joint"] + jo if a.get("joint", -1) >= 0 else -1
        q["phase"] = ph(a["phase"])
        out.artwork.append(q)
    for lb in g.get("labels", []):
        q = dict(lb)
        q["id"], q["part"] = _pre(pid, lb["id"]), _pre(pid, lb["part"])
        q["corners"] = [[_r(x) for x in xf.p(c)] for c in lb["corners"]]
        if lb.get("field"):
            q["field"] = _pre(pid, lb["field"])
        q["motion_slot"] = lb["motion_slot"] + mo if lb.get("motion_slot", -1) >= 0 else -1
        q["joint"] = lb["joint"] + jo if lb.get("joint", -1) >= 0 else -1
        q["phase"] = ph(lb["phase"])
        out.labels.append(q)
    for an in g.get("annotations", []):
        q = dict(an)
        q["id"], q["part"] = _pre(pid, an["id"]), _pre(pid, an["part"])
        q["anchor"] = [_r(x) for x in xf.p(an["anchor"])]
        q["joint"] = an["joint"] + jo if an.get("joint", -1) >= 0 else -1
        q["phase"] = ph(an["phase"])
        out.annotations.append(q)
    pv = g.get("provenance", {})
    for s in pv.get("sources", []):
        out.sources.append(dict(s, id=_pre(pid, s["id"]), placement=pid))
    for f in pv.get("facts", []):
        q = dict(f, key=_pre(pid, f["key"]), placement=pid)
        if f.get("source"):
            q["source"] = _pre(pid, f["source"])
        out.facts.append(q)
    for a in pv.get("assets", []):
        out.assets.append(dict(a, id=_pre(pid, a["id"]), placement=pid))
    for c in pv.get("checked", []):
        out.checked.append(dict(c, reference=_pre(pid, c["reference"])))


def _finish(doc, out, records, n, solid):
    first = out.first
    main = _bounds(out.parts) or ([0, 0, 0], [1, 1, 1])
    every = [p for p in out.parts]
    lo, hi = main
    centre = [_r((lo[k] + hi[k]) / 2) for k in range(3)]
    radius = _r(0.5 * math.sqrt(sum((hi[k] - lo[k]) ** 2 for k in range(3))))
    olo, ohi = list(lo), list(hi)
    for p in every:
        if p.get("sky"):
            continue
        for b in p["instances"]:
            if "open_min" in b:
                for k in range(3):
                    olo[k], ohi[k] = min(olo[k], b["open_min"][k]), max(ohi[k], b["open_max"][k])
    bounds = {"min": [_r(x) for x in lo], "max": [_r(x) for x in hi], "center": centre, "radius": radius,
              "open_min": [_r(x) for x in olo], "open_max": [_r(x) for x in ohi]}
    sky = _bounds(out.parts, sky=True)
    if sky:   # how far the camera must see: the sky placements, past everything else
        bounds["sky_far"] = _r(max(math.sqrt(sum((sky[j][k] - centre[k]) ** 2 for k in range(3))) for j in (0, 1)) * 1.5)
    pr = json.loads(json.dumps(first["presentation"]))
    wp = doc.get("presentation", {})
    pr["framing"] = dict({"yaw": 30, "pitch": 18, "fit": 1.0}, **wp.get("framing", {}))
    views = []
    for v in wp.get("views", []):
        views.append(dict(v))
    for r in records:   # a view of each placement, unless the world names its own
        if len(views) >= 48:
            break
        if not any(v["id"] == r["id"] for v in views) and "sky" not in r:
            views.append({"id": r["id"], "label": r["label"], "target": r["id"], "yaw": 35, "pitch": 18, "distance": 1.3})
    pr["views"] = views
    pr["labels"] = False
    anim = json.loads(json.dumps(first["animation"]))
    wa = doc.get("animation", {})
    secs = wa.get("assembly", {}).get("seconds", min(600.0, 8.0 + 3.0 * len(records)))
    anim["assembly"] = {"style": "ceremony", "seconds": secs, "interference": False}
    if "camera" in wa:
        anim["camera"] = dict(anim["camera"], **wa["camera"])
    else:
        anim["camera"]["tour"] = []
    if "idle" in wa:
        anim["idle"] = dict(anim["idle"], **wa["idle"])
    anchors = {"base": {"point": [centre[0], _r(lo[1]), centre[2]], "up": [0, 1, 0]}}
    g = {
        "format": first["format"], "version": first["version"], "generator": first["generator"],
        "contract": first["contract"], "frame": first["frame"],
        "id": doc["id"], "title": doc["title"],
        "subject": {"category": "world", "accuracy": "approximate", "synthetic": False,
                    "summary": doc.get("summary", "%d constructs placed together" % len(records))},
        "scene_sha256": scene_mod.canonical_sha256(doc),
        "provenance": {"sources": out.sources, "facts": out.facts, "assets": out.assets,
                       **({"authoring": json.loads(json.dumps(doc["authoring"]))} if doc.get("authoring") else {}),
                       **({"checked": out.checked} if out.checked else {})},
        "bounds": bounds, "anchors": anchors,
        "stages": [{"stage": i, "index": i} for i in range(len(records))],
        "parts": out.parts, "styles": out.styles, "style_fields": first["style_fields"],
        **({"style_colors": out.style_colors} if any(out.style_colors) else {}),
        "lines": out.lines, "line_stride": 9, "line_fields": first["line_fields"],
        "fills": out.fills, "fill_stride": 5, "fill_fields": first["fill_fields"],
        "points": out.points, "point_stride": 7, "point_fields": first["point_fields"],
        "motions": out.motions, "articulations": out.arts, "joints": out.joints,
        "artwork": out.artwork, "labels": out.labels, "annotations": out.annotations,
        "presentation": pr, "animation": anim,
        "counts": {"lines": n[0], "triangles": n[1], "points": n[2], "motions": len(out.motions),
                   "articulations": len(out.arts), "labels": len(out.labels),
                   "instances": sum(len(p["instances"]) for p in out.parts)},
        "world": {"format": WORLD_FORMAT, "version": WORLD_VERSION, "placements": records,
                  **({"origin": doc["origin"]} if doc.get("origin") else {})},
    }
    if solid:
        g["_scenes"] = True
    return g


# ---------------------------------------------------------------------------- checks

def audit(doc, g):
    """A world's own checks, beside each construct's: placements that collide, that stand on nothing, that are
    not at real size. Each placed construct's own audit is its own (it was checked where it was made)."""
    warnings, notes = [], []
    add = lambda code, pid, msg: warnings.append({"code": code, "part": pid, "message": msg})
    recs = {r["id"]: r for r in g["world"]["placements"]}
    # what takes up room: not the sky, and not a decorative cloud of points (motes, dust, a nebula's glow)
    solid = lambda p: not p.get("sky") and not (p.get("shape") == "points" and p.get("certainty") == "decorative")
    boxes = {}
    for p in g["parts"]:
        if not solid(p):
            continue
        for b in p["instances"]:
            lo, hi = boxes.setdefault(p["placement"], [list(b["min"]), list(b["max"])])
            for k in range(3):
                lo[k], hi[k] = min(lo[k], b["min"][k]), max(hi[k], b["max"][k])
    parts_of = {}
    for p in g["parts"]:
        if solid(p):
            parts_of.setdefault(p["placement"], []).extend((p["id"], b["min"], b["max"]) for b in p["instances"])
    ground = 0.0   # the world's ground plane (a construct's own foundations may go below it)
    hosts = {r["on"].split("/")[0] for r in recs.values() if r.get("on")}
    ids = [r["id"] for r in g["world"]["placements"]]
    for i, a in enumerate(ids):
        if a not in boxes:
            continue
        for b in ids[i + 1:]:
            if b not in boxes or a in hosts and recs[b].get("on", "").split("/")[0] == a or \
                    b in hosts and recs[a].get("on", "").split("/")[0] == b:
                continue   # a thing and what it stands on (a chair in its house) share space by design
            A, B = boxes[a], boxes[b]
            if not _meets(A, B):
                continue
            # their boxes cross; do their parts? (a scooter beside a shed shares the box of the shed's yard, not a wall)
            pa = [(lo, hi) for _, lo, hi in parts_of.get(a, []) if _meets((lo, hi), B)]
            pb = [(lo, hi) for _, lo, hi in parts_of.get(b, []) if _meets((lo, hi), A)]
            hits = sum(1 for x in pa if any(_meets(x, y) for y in pb))
            if hits:
                add("overlap", a, "%s and %s overlap (%d of %s's parts run into %s's)" % (a, b, hits, a, b))
    # a thing shares space with what it stands on (a chair in its house), but not with every part of it: a car
    # parked under a house must clear its columns. Each part's boxes against the host's, all but its support.
    for pid, r in recs.items():
        on = r.get("on")
        if not on or pid not in boxes:
            continue
        host, _, support = on.partition("/")
        A, hits = boxes[pid], []
        for hid, lo, hi in parts_of.get(host, []):
            if support and hid == on or not _meets((lo, hi), A):
                continue
            if any(_meets((lo, hi), (alo, ahi)) for _, alo, ahi in parts_of[pid]):
                hits.append(hid)
        if hits:
            shown = sorted(set(hits))
            add("collides", pid, "%s runs into %s (%s%s): move it, or stand it on the part it rests on" % (
                pid, host, ", ".join(x.split("/", 1)[1] for x in shown[:3]),
                " and %d more" % (len(shown) - 3) if len(shown) > 3 else ""))
    # what opens (a door, a lid, a cowl) needs room: each part's open pose against the other placements' parts
    opens = {}
    for p in g["parts"]:
        if solid(p):
            for b in p["instances"]:
                if "open_min" in b:
                    opens.setdefault(p["placement"], []).append((p["id"], b["open_min"], b["open_max"]))
    for a, moving in opens.items():
        for b in ids:
            if b == a or b not in parts_of or b not in boxes:
                continue
            skip = {recs[b].get("on"), recs[a].get("on")}   # what one of them stands on is shared by design
            hit = sorted({mid for mid, lo, hi in moving if mid not in skip and _meets((lo, hi), boxes[b])
                          and any(_meets((lo, hi), (blo, bhi)) for bid, blo, bhi in parts_of[b] if bid not in skip)})
            if hit:
                add("blocks", b, "%s is in the way of %s's %s when %s open%s: move it clear, unless that is never "
                    "opened" % (b, a, ", ".join(x.split("/", 1)[1] for x in hit[:3]),
                                "it" if len(hit) == 1 else "they", "s" if len(hit) == 1 else ""))
    for pid, r in recs.items():
        if "sky" in r:
            notes.append("%s: in the sky at its real angular size (%.4g°)" % (pid, r.get("angular_deg", 0)))
            continue
        if pid not in boxes:
            continue
        if not r.get("on") and not r.get("floating") and boxes[pid][0][1] > ground + 0.05:
            add("unsupported", pid, "%s stands on nothing (its lowest point is %.2f m above the ground); give it "
                "`on`, or `floating: true` if it hovers" % (pid, boxes[pid][0][1] - ground))
        if abs(r["scale"] - 1.0) > 1e-9:
            add("scaled", pid, "%s is shown at %g× its construct's size" % (pid, r["scale"]))
    b = g["bounds"]
    return {"ok": True, "errors": [], "warnings": warnings, "counts": dict(g["counts"], placements=len(recs)),
            "info": {"parts": len(g["parts"]), "counts": g["counts"], "placements": len(recs), "notes": notes,
                     "dimensions_m": {"width": _r(b["max"][0] - b["min"][0]), "height": _r(b["max"][1] - b["min"][1]),
                                      "depth": _r(b["max"][2] - b["min"][2])}}}


# ---------------------------------------------------------------------------- arranging by hand

MAX_ARRANGE = 256
ARRANGE_KEYS = {"id", "move", "turn", "pivot"}


def _ry(deg):
    a = math.radians(deg)
    return [[math.cos(a), 0.0, math.sin(a)], [0.0, 1.0, 0.0], [-math.sin(a), 0.0, math.cos(a)]]


def arrange(doc, g, changes):
    """The world after placements were moved and turned by hand (the page's arrange mode): a new document.

    Each change is {id, move: [dx, dy, dz] metres, turn: degrees about +Y, pivot: [x, z]} in the frame the
    placement stood in before; what stands on a placement (on it, or on one of its parts) is carried along, as a
    table carries what is on it. Each placement's `at` and `yaw` are written back the way it was placed (absolute,
    or on its host), so the world reads the same afterwards. Sky placements stay where the sky puts them.
    Raises WorldError for a change that names nothing or carries no numbers."""
    if not isinstance(changes, list) or not 0 < len(changes) <= MAX_ARRANGE:
        raise WorldError("arrange: 1..%d changes" % MAX_ARRANGE)
    recs = {r["id"]: r for r in g["world"]["placements"]}
    edits = {}
    for c in changes:
        if not isinstance(c, dict) or set(c) - ARRANGE_KEYS or c.get("id") not in recs:
            raise WorldError("arrange: each change is {id, move, turn, pivot} for a placement of this world")
        if "sky" in recs[c["id"]]:
            raise WorldError("arrange: %s is in the sky; place it with its sky angles" % c["id"])
        move = c.get("move", [0, 0, 0])
        if not _vec(move, 10000.0) or not _num(c.get("turn", 0), -3600, 3600) or \
                not (isinstance(c.get("pivot"), list) and len(c["pivot"]) == 2 and all(_num(v, -WORLD_EXTENT, WORLD_EXTENT) for v in c["pivot"])):
            raise WorldError("arrange: %s needs move [dx, dy, dz] (metres), turn (degrees) and pivot [x, z]" % c["id"])
        edits[c["id"]] = ([float(v) for v in move], float(c.get("turn", 0)), [float(v) for v in c["pivot"]])
    out = json.loads(json.dumps(doc))
    # rigid motions: x -> R x + t, composed host first (a placement's host is always placed before it)
    motion, moved = {}, []
    for p in out["placements"]:
        host = p.get("on", "").split("/")[0] if p.get("on") else None
        R, t, turn = (motion[host] if host in motion else (_ry(0), [0.0, 0.0, 0.0], 0.0))
        if p["id"] in edits:
            d, a, (cx, cz) = edits[p["id"]]
            E = _ry(a)
            c = [cx, 0.0, cz]
            Ec = scene_mod._mul(E, c)
            et = [c[k] + d[k] - Ec[k] for k in range(3)]
            # M = M_host * E
            R2 = [[sum(R[i][k] * E[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            Rt = scene_mod._mul(R, et)
            t = [Rt[k] + t[k] for k in range(3)]
            R, turn = R2, turn + a
        if host not in motion and p["id"] not in edits:
            continue
        motion[p["id"]] = (R, t, turn)
        if "sky" in p:
            continue
        r = recs[p["id"]]
        old = r["at"]
        Ro = scene_mod._mul(R, old)
        new = [Ro[k] + t[k] for k in range(3)]
        own_dy = edits[p["id"]][0][1] if p["id"] in edits else 0.0
        if p.get("on"):
            lift = (p.get("at") or [0.0, 0.0, 0.0])[1] + own_dy
            if "/" in p["on"]:
                at = [new[0], lift, new[2]]
            else:
                ho = recs[host]["at"]
                hm = motion.get(host)
                hn = [scene_mod._mul(hm[0], ho)[k] + hm[1][k] for k in range(3)] if hm else ho
                at = [new[0] - hn[0], lift, new[2] - hn[2]]
        else:
            at = new
        p["at"] = [_r(v) for v in at]
        if abs(turn) > 1e-9:
            y = (p.get("yaw", 0.0) + turn + 180.0) % 360.0 - 180.0
            p["yaw"] = _r(y)
        moved.append(p["id"])
    return out, moved


STEP_M = 0.6   # what a placement settles onto: the highest flat top under it within this height above its bottom


def _carried(doc, by):
    """The placements that stand, perhaps through others, on placement `by`."""
    on = {p["id"]: p.get("on", "").split("/")[0] for p in doc["placements"] if p.get("on")}
    out = set()
    for pid in on:
        cur, seen = pid, 0
        while cur in on and seen < 16:
            cur, seen = on[cur], seen + 1
            if cur == by:
                out.add(pid)
                break
    return out


def _flat(b):
    dx, dy, dz = (b["max"][k] - b["min"][k] for k in range(3))
    return dy < 0.6 * min(dx, dz) and dx * dz > 0.002


def settle(doc, g, ids, step=STEP_M):
    """Placements set down by hand land on what is under them: each of `ids` (not in the sky, not floating) stands on
    the highest flat top of any other placement (not one it carries) under the middle of its footprint, no higher
    than `step` above where it stands now: a floor, a deck, paving, a table, a roof it was lifted to. A new document
    and the ids that changed."""
    recs = {r["id"]: r for r in g["world"]["placements"]}
    out = json.loads(json.dumps(doc))
    changed = []
    for p in out["placements"]:
        if p["id"] not in ids or "sky" in p or p.get("floating") or p is out["placements"][0]:
            continue
        own = [b for q in g["parts"] if q.get("placement") == p["id"] and not q.get("sky") for b in q["instances"]]
        if not own:
            continue
        cx = (min(b["min"][0] for b in own) + max(b["max"][0] for b in own)) / 2
        cz = (min(b["min"][2] for b in own) + max(b["max"][2] for b in own)) / 2
        bottom = min(b["min"][1] for b in own)
        skip = {p["id"]} | _carried(out, p["id"])
        best = None
        for q in g["parts"]:
            pl = q.get("placement")
            if not pl or pl in skip or q.get("sky") or q.get("shape") == "points":
                continue
            for b in q["instances"]:
                if not _flat(b) or not (b["min"][0] <= cx <= b["max"][0] and b["min"][2] <= cz <= b["max"][2]):
                    continue
                top = b["max"][1]
                if top <= bottom + step and (best is None or top > best[0]):
                    best = (top, q["id"], pl)
        if best is None:
            continue
        top, part_id, owner = best
        target = "%s/%s" % (owner, part_id[len(owner) + 1:] if part_id.startswith(owner + "/") else part_id)
        if p.get("on") == target and abs(top - bottom) < 0.005:
            continue
        t = recs[p["id"]]["at"]
        p["on"], p["at"] = target, [_r(t[0]), 0.0, _r(t[2])]
        changed.append(p["id"])
    return out, changed


def drop_spot(doc, g, pid, margin=0.12):
    """Where a construct put into a world by hand first stands (it is then dragged where it belongs): on the widest
    floor of the world's first placement it fits on, at ground level or near it (a chair in a room, a car in a
    garage); else on clear ground in front of it (a car beside a shed). A new document."""
    recs = {r["id"]: r for r in g["world"]["placements"]}
    out = json.loads(json.dumps(doc))
    p = next(q for q in out["placements"] if q["id"] == pid)
    host = out["placements"][0]["id"]
    own = [b for q in g["parts"] if q.get("placement") == pid and not q.get("sky") for b in q["instances"]]
    hb = [b for q in g["parts"] if q.get("placement") == host and not q.get("sky") for b in q["instances"]]
    if not own or not hb or pid == host:
        return out
    lo = [min(b["min"][k] for b in own) for k in range(3)]
    hi = [max(b["max"][k] for b in own) for k in range(3)]
    w, d = hi[0] - lo[0], hi[2] - lo[2]
    centre = [(lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2]
    t = recs[pid]["at"]
    off = [centre[0] - t[0], centre[1] - t[2]]   # its middle from its origin, as it stands
    ground = min(b["min"][1] for b in hb)
    fits = []
    for q in g["parts"]:
        if q.get("placement") != host or q.get("sky"):
            continue
        for b in q["instances"]:
            sx, sz = b["max"][0] - b["min"][0], b["max"][2] - b["min"][2]
            if _flat(b) and b["max"][1] <= ground + 1.2 and sx >= w * (1 + margin) and sz >= d * (1 + margin):
                fits.append((sx * sz, q["id"], b))
    if fits:
        _, part, b = max(fits, key=lambda f: f[0])
        mx, mz = (b["min"][0] + b["max"][0]) / 2, (b["min"][2] + b["max"][2]) / 2
        p["on"] = "%s/%s" % (host, part[len(host) + 1:])
        p["at"] = [_r(mx - off[0]), 0.0, _r(mz - off[1])]
        return out
    # outside, in front of the host, clear of everything placed
    hlo = [min(b["min"][k] for b in hb) for k in range(3)]
    hhi = [max(b["max"][k] for b in hb) for k in range(3)]
    others = [(r_lo, r_hi) for q in g["world"]["placements"] if q["id"] not in (pid, host) and "sky" not in q
              for r_lo, r_hi in [_wbox(g, q["id"])] if r_lo]
    z = hhi[2] + d / 2 + 0.6
    for i in range(12):
        x = (hlo[0] + hhi[0]) / 2 + (((i + 1) // 2) * (w + 0.6) * (1 if i % 2 else -1) if i else 0)
        box = ([x - w / 2, 0, z - d / 2], [x + w / 2, 1, z + d / 2])
        if not any(_meets((box[0], box[1]), (a, b2), 0.0) for a, b2 in others if a[1] < 2.5):
            break
    ht = recs[host]["at"]
    p["on"] = host
    p["at"] = [_r(x - off[0] - ht[0]), 0.0, _r(z - off[1] - ht[2])]
    return out


def _wbox(g, pid):
    bs = [b for q in g["parts"] if q.get("placement") == pid and not q.get("sky") for b in q["instances"]]
    if not bs:
        return None, None
    return [min(b["min"][k] for b in bs) for k in range(3)], [max(b["max"][k] for b in bs) for k in range(3)]


def _meets(a, b, tol=0.01):
    """Two boxes ((min, max)) that interpenetrate by more than `tol` metres on every axis (touching is not meeting)."""
    return all(min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) > tol for k in range(3))


def _vol(b):
    return max(0.0, b[1][0] - b[0][0]) * max(0.0, b[1][1] - b[0][1]) * max(0.0, b[1][2] - b[0][2])


def check(world_path, resolver=None):
    """`construct check` for a world: the shape of a scene's report (ok, errors, warnings, diagnostics with a code,
    a path, a message and a hint, stats), from the world's validation, compilation and audit."""
    diags = []
    try:
        doc = load(world_path)
    except (OSError, ValueError, WorldError) as exc:
        doc, diags = None, [{"severity": "error", "code": "unreadable", "path": "world", "message": str(exc),
                             "hint": "a world is JSON with format construct-world (docs/WORLDS.md)"}]
    g = None
    if doc is not None:
        for e in validate(doc):
            where, _, msg = e.partition(": ")
            diags.append({"severity": "error", "code": "world", "path": where, "message": msg,
                          "hint": "see docs/WORLDS.md for each key"})
    if doc is not None and not diags:
        try:
            g = compile_world(doc, str(Path(world_path).parent), resolver)
        except WorldError as exc:
            diags.append({"severity": "error", "code": "placement", "path": "world.placements", "message": str(exc),
                          "hint": "name a construct that exists and a part that is there to stand on"})
    stats = None
    if g is not None:
        report = audit(doc, g)
        for x in report["warnings"]:
            diags.append({"severity": "warning", "code": x["code"], "path": "world.placements.%s" % x["part"],
                          "message": x["message"], "hint": {
                              "overlap": "move one of them (op move), or remove one",
                              "collides": "move it clear, or stand it on the part it rests on (on: host/part-id)",
                              "blocks": "move it out of the way of the door or lid, unless that is never opened",
                              "unsupported": "give it `on`, or `floating: true` if it hovers",
                              "scaled": "scale 1 is real size; leave it if the size is meant"}.get(x["code"])})
        b = g["bounds"]
        stats = dict(report["counts"], parts=len(g["parts"]),
                     size_m=[_r(b["max"][k] - b["min"][k]) for k in range(3)], notes=report["info"]["notes"])
    errors = sum(d["severity"] == "error" for d in diags)
    return {"ok": errors == 0, "needs_repair": errors > 0, "errors": errors,
            "warnings": sum(d["severity"] == "warning" for d in diags), "diagnostics": diags, "stats": stats,
            "world": True, "repair_text": "\n".join("%s: %s (%s)" % (d["path"], d["message"], d["hint"])
                                                    for d in diags if d["severity"] == "error")}


# ---------------------------------------------------------------------------- build and export

def _compiled_all(doc, base_dir, resolver, solid):
    cache = {}
    g = compile_world(doc, base_dir, resolver, solid, _cache=cache)
    return g, cache


def build(world_path, out_dir, resolver=None, force=True):
    """A world's page, like a construct's (construct.html, geometry.json, audit.json and audit.txt)."""
    from . import render
    path = Path(world_path)
    doc = load(path)
    g, cache = _compiled_all(doc, path.parent, resolver, False)
    report = audit(doc, g)
    # each placed construct's artwork, from its own folder, under its placement's id
    assets, notes = {}, []
    recs = g["world"]["placements"]
    for r in recs:
        src = next((c for (k, sld), c in cache.items() if not sld and c.get("_path") and
                    Path(c["_path"]).resolve() == Path(resolver(r["construct"], path.parent) if resolver else
                                                       default_resolver(r["construct"], path.parent)).resolve()), None)
        if src is None or not src.get("artwork"):
            continue
        a, n = render.embed_assets(src, str(Path(src["_path"]).parent))
        assets.update({"%s/%s" % (r["id"], k): v for k, v in a.items()})
        notes += ["%s: %s" % (r["id"], x) for x in n]
    solid_g, _ = _compiled_all(doc, path.parent, resolver, True)
    solid = render.solid_payload(None, g, solid=solid_g)
    html, _ = render.build_html(g, None, solid=solid, assets=assets)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("geometry.json", json.dumps(g, separators=(",", ":")) + "\n"), ("construct.html", html),
                       ("audit.json", json.dumps(report, indent=2) + "\n")):
        _write(out / name, text, force)
    text = format_report(report, g) + ("\n" + "\n".join("  note: " + n for n in notes) if notes else "")
    _write(out / "audit.txt", text + "\n", force)
    return g, report, text


def _write(path, text, force):
    if path.exists() and not force:
        raise WorldError("%s exists" % path)
    path.write_text(text, encoding="utf-8")


def format_report(report, g):
    recs = g["world"]["placements"]
    lines = ["world: %s (%d constructs placed)" % (g["title"], len(recs))]
    for r in recs:
        where = "in the sky, %.4g° across" % r.get("angular_deg", 0) if "sky" in r else \
            "at (%.2f, %.2f, %.2f) m%s" % (tuple(r["at"]) + (", on " + r["on"] if r.get("on") else "",))
        lines.append("  %-18s %-34s %s%s" % (r["id"], r["title"][:34], where,
                                              "" if abs(r["scale"] - 1) < 1e-9 else ", at %g×" % r["scale"]))
    c = report["counts"]
    lines.append("  %d parts' copies, %d lines, %d triangles, %d articulations" %
                 (c["instances"], c["lines"], c["triangles"], c["articulations"]))
    for w in report["warnings"]:
        lines.append("  warn [%s] %s" % (w["code"], w["message"]))
    for i in report["info"]["notes"]:
        lines.append("  info %s" % i)
    lines.append("world audit: %s (%d warnings)" % ("PASS" if report["ok"] else "FAIL", len(report["warnings"])))
    return "\n".join(lines)


def materials(doc, base_dir, resolver=None):
    """One material map for the world: each placed construct's own map (beside its scene: maps/finish.json,
    scene.materials.json or materials.json), its patterns under its placement's id."""
    rules = []
    for p in doc["placements"]:
        path = Path((resolver or default_resolver)(p["construct"], base_dir))
        src = None
        for c in (path.parent / "maps" / "finish.json", path.with_suffix(".materials.json"),
                  path.parent / "scene.materials.json", path.parent / "materials.json"):
            if c.is_file():
                src = c
                break
        if src is None:
            continue
        for r in json.loads(src.read_text(encoding="utf-8")).get("materials", []):
            pats = [r["parts"]] if isinstance(r["parts"], str) else r["parts"]
            q = {k: v for k, v in r.items() if k != "parts"}
            q["parts"] = ["%s/%s" % (p["id"], x) for x in pats]
            if "name" in q:
                q["name"] = "%s: %s" % (p["id"], q["name"])
            rules.append(q)
    return {"materials": rules} if rules else None


def export(world_path, out, fmt=None, wire="edges", pose="closed", materials_path=None, merge=False,
           colliders=False, pieces=False, resolver=None):
    """The world as one 3D file: one glTF (.glb) a game engine or Blender opens whole, every placed construct
    under its placement's id, its joints working; or OBJ."""
    from . import export as export_mod
    path = Path(world_path)
    doc = load(path)
    out = Path(out)
    fmt = fmt or out.suffix.lower().lstrip(".")
    g, _ = _compiled_all(doc, path.parent, resolver, True)
    mats = materials_path if materials_path else materials(doc, path.parent, resolver)
    if fmt == "glb":
        gdoc, binary, summary = export_mod.to_gltf(g, wire, pose, mats, None, merge, colliders, pieces, False)
        _world_nodes(gdoc, g)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = export_mod.pack_glb(gdoc, binary)
        out.write_bytes(data)
        summary.update({"bytes": len(data), "files": [str(out)], "format": "glb", "pose": pose, "wire": wire})
    elif fmt == "obj":
        text, mtl, counts = export_mod.to_obj(g, out.stem, wire, pose, mats, "y-up", None)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        out.with_suffix(".mtl").write_text(mtl, encoding="utf-8")
        summary = {"parts": len(g["parts"]), **counts, "files": [str(out), str(out.with_suffix(".mtl"))],
                   "format": "obj", "pose": pose, "wire": wire}
    else:
        raise WorldError("a world exports as .glb (glTF: Blender, Godot, Unity, Unreal, the web) or .obj")
    summary["placements"] = len(g["world"]["placements"])
    summary["quality"] = export_mod.triangle_quality(g)
    return summary


def _world_nodes(gdoc, g):
    """Name the glTF's per-stage groups after the placements (a world's stage is its placement) and write the
    placements into the root's extras: Blender and Godot then see each construct as its own group."""
    recs = g["world"]["placements"]
    for node in gdoc.get("nodes", []):
        c = (node.get("extras") or {}).get("construct") or {}
        if "stage" in c and set(c) <= {"stage", "order"} and isinstance(c["stage"], int) and c["stage"] < len(recs):
            r = recs[c["stage"]]
            node["name"] = r["id"]
            node.setdefault("extras", {})["construct"] = {"placement": r["id"], "title": r["title"],
                                                         "construct": r["construct"], "scale": r["scale"]}
    root = next((n for n in gdoc.get("nodes", []) if (n.get("extras") or {}).get("construct", {}).get("scene_sha256")), None)
    if root is not None:
        root["extras"]["construct"]["world"] = {"placements": recs}
