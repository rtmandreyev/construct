"""3D export: a construct as a glTF 2.0 binary (.glb) or a Wavefront OBJ.

The export reads a solid compile (`scene.compile_scene(scene, solid=True)`): every shape keeps its
surfaces, not only the hologram's fills. Nothing is invented on the way out.

glTF (.glb):
  - each part is a named node under its stage (`stage-0`, `stage-1`, …), with its role, certainty,
    source and basis in `extras.construct`; the construct's facts and sources are on the root;
  - surfaces are triangle meshes with smoothed normals, box-projected texture coordinates and a
    material per role (or from a material map; parts named for glazing get glass); the line art
    comes as edges (`wire="edges"`), as thin tubes (`"tubes"`), as tubes for the design lines only
    (`"seams"`: the parts drawn as lines, not the edges of surfaces) or not at all (`"none"`), with an
    unlit material per tone; points come as a point primitive;
  - `merge` merges every part that does not move into one mesh per material, for game engines;
  - articulations are pivot nodes: the animation `open` plays them in their order groups, and
    `open:<id>` plays one; periodic motions (spin, swing, bob) loop in the animation `idle`;
  - every vertex carries its build phase (0..1, the assembly order) as the attribute `_PHASE`.

OBJ (.obj and .mtl): the same surfaces and edges, one object per part, in one pose; no animation.

Python standard library only.
"""

import fnmatch
import json
import math
import struct
from pathlib import Path

from . import product, scene as scene_mod

FORMATS = ("glb", "obj")
WIRES = ("edges", "tubes", "seams", "none")
POSES = ("closed", "open")
FRAMES = ("y-up", "z-up")

GROUP_SECONDS = 1.5          # one order group of the `open` animation, as the viewer plays it
CREASE_DEGREES = 40.0        # faces meeting at more than this keep a hard edge

# a neutral, matte default per role (sRGB hex, metallic, roughness); a material map replaces it
ROLE_MATERIAL = {
    "mass": ("#c9c6c1", 0.0, 0.55),
    "identity": ("#dcd8d0", 0.0, 0.45),
    "structure": ("#8f9197", 0.35, 0.5),
    "detail": ("#6f7177", 0.3, 0.5),
    "data": ("#8fd3ff", 0.0, 0.4),
    "ornament": ("#a597b3", 0.0, 0.6),
    "ground": ("#3b3640", 0.0, 0.9),
    "artwork": ("#ebe7df", 0.0, 0.6),
}
# the house palette's tones, for the light (edges, tubes, points)
TONE_COLOR = dict(zip(scene_mod.TONES, ("#d16bd0", "#f6eaff", "#eadcf3", "#b7a4c8", "#9682d7", "#eadcf3",
                                        "#8fd3ff", "#6f6080")))
MATERIAL_KEYS = {"parts", "name", "color", "metallic", "roughness", "emissive", "finish"}
# a material map's finishes: physically based defaults (a rule's own metallic and roughness win),
# exported with standard glTF extensions; the Blender add-on turns each into its procedural shader
FINISHES = {
    "paint": {"metallic": 0.0, "roughness": 0.38, "clearcoat": 1.0},
    "brushed": {"metallic": 1.0, "roughness": 0.32},
    "chrome": {"metallic": 1.0, "roughness": 0.05},
    "wood": {"metallic": 0.0, "roughness": 0.55},
    "rubber": {"metallic": 0.0, "roughness": 0.92},
    "plastic": {"metallic": 0.0, "roughness": 0.45},
    "glass": {"metallic": 0.0, "roughness": 0.03, "transmission": 0.92},
    "light": {"metallic": 0.0, "roughness": 0.4, "glow": 4.0},
}


class ExportError(ValueError):
    pass


# ---------------------------------------------------------------------------- small maths

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _quat(axis, degrees):
    """A rotation about a unit axis, as glTF's (x, y, z, w); right-handed, like the compiler's."""
    x, y, z = _unit(axis)
    h = math.radians(degrees) / 2
    s = math.sin(h)
    return (x * s, y * s, z * s, math.cos(h))


def _ease(u):
    return u * u * (3 - 2 * u)


def _hex(color, where):
    c = color.lstrip("#") if isinstance(color, str) else ""
    if len(c) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in c):
        raise ExportError("%s: a colour is \"#rrggbb\", not %r" % (where, color))
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _linear(rgb):
    return tuple(round(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4, 5) for v in rgb)


def smooth_normals(tris, crease=CREASE_DEGREES):
    """One normal per triangle corner: the faces around a point that meet at less than `crease`
    degrees share a smooth normal; sharper edges stay hard. Degenerate triangles get (0, 1, 0)."""
    faces = [_unit(_cross(_sub(b, a), _sub(c, a))) for a, b, c in tris]
    key = lambda p: (round(p[0], 5), round(p[1], 5), round(p[2], 5))
    around = {}
    for fi, tri in enumerate(tris):
        for p in tri:
            around.setdefault(key(p), []).append(fi)
    cos_crease = math.cos(math.radians(crease))
    out = []
    for fi, tri in enumerate(tris):
        f = faces[fi]
        if f == (0.0, 0.0, 0.0):
            out.extend([(0.0, 1.0, 0.0)] * 3)
            continue
        for p in tri:
            acc = [0.0, 0.0, 0.0]
            for gi in set(around[key(p)]):
                g = faces[gi]
                if f[0] * g[0] + f[1] * g[1] + f[2] * g[2] >= cos_crease:
                    acc = [acc[k] + g[k] for k in range(3)]
            n = _unit(acc)
            out.append(n if n != (0.0, 0.0, 0.0) else f)
    return out


def box_uvs(tris):
    """Texture coordinates for every triangle corner by box projection, in metres: each triangle is
    projected along the axis its face points most along. Enough to texture a part or lightmap it
    after an engine repacks the coordinates; no shape needs unwrapping by hand."""
    out = []
    for a, b, c in tris:
        n = _cross(_sub(b, a), _sub(c, a))
        ax = max(range(3), key=lambda k: abs(n[k]))
        u, v = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
        out.extend([(p[u], p[v]) for p in (a, b, c)])
    return out


# a part named for its glazing gets glass when no material map says otherwise
GLASS_WORDS = ("glass", "glazing", "window", "windscreen", "windshield", "visor", "canopy")
# what holds or works the glass is not glass: a windscreen frame, a window seal or crank
NOT_GLASS_WORDS = ("frame", "surround", "seal", "rim", "trim", "bezel", "pillar", "post", "wiper", "rubber", "gasket",
                   "divider", "rail", "channel", "washer", "crank", "winder", "regulator", "sill", "lever", "hinge",
                   "catch", "latch", "handle", "bracket", "mount", "stay", "strut", "louvre", "shade", "blind", "sticker")


def is_glass_name(pid):
    """Whether a part's id names glass (a windscreen, a side window), not what holds it (a windscreen frame)."""
    low = pid.lower()
    return any(w in low for w in GLASS_WORDS) and not any(w in low for w in NOT_GLASS_WORDS)


def _tube(a, b, r):
    """A square tube along one segment: 8 triangles, their normals, and which end each corner is at
    (0 at a, 1 at b)."""
    d = _unit(_sub(b, a))
    if d == (0.0, 0.0, 0.0):
        return [], [], []
    ref = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(d, ref))
    v = _cross(d, u)
    ring = [(u[0] * c + v[0] * s, u[1] * c + v[1] * s, u[2] * c + v[2] * s)
            for c, s in ((1, 0), (0, 1), (-1, 0), (0, -1))]
    tris, norms = [], []
    for k in range(4):
        n0, n1 = ring[k], ring[(k + 1) % 4]
        p0 = (a[0] + n0[0] * r, a[1] + n0[1] * r, a[2] + n0[2] * r)
        p1 = (a[0] + n1[0] * r, a[1] + n1[1] * r, a[2] + n1[2] * r)
        q0 = (b[0] + n0[0] * r, b[1] + n0[1] * r, b[2] + n0[2] * r)
        q1 = (b[0] + n1[0] * r, b[1] + n1[1] * r, b[2] + n1[2] * r)
        tris += [(p0, p1, q1), (p0, q1, q0)]
        norms += [n0, n1, n1, n0, n1, n0]
    return tris, norms, [0, 0, 1, 0, 1, 1] * 4


# ---------------------------------------------------------------------------- reading a compile

# Godot reads these name endings as import instructions (a "-wheel" becomes a VehicleWheel3D, a "-col" a
# collision body); a part whose id ends so is named with "-part" after it, its id kept in extras
GODOT_HINTS = ("-noimp", "-col", "-colonly", "-convcol", "-convcolonly", "-occ", "-occonly", "-navmesh", "-rigid",
               "-vehicle", "-wheel", "-loop", "-cycle")


def _node_name(pid):
    return pid + "-part" if pid.lower().endswith(GODOT_HINTS) else pid


def _own_colours(g):
    """Each part's own colour (look.color), from the styles that carry it: {part id: '#rrggbb'}."""
    out = {}
    for st, c in zip(g["styles"], g.get("style_colors") or []):
        if c and int(st[6]) >= 0:
            out[g["parts"][int(st[6])]["id"]] = c
    return out


def _load_materials(materials):
    """A material map: {"materials": [{"parts": ["hull", "tile-*"], "color": "#rrggbb", "finish", "metallic",
    "roughness", "emissive", "name"}]}; the first rule whose pattern matches a part id wins."""
    if materials is None:
        return []
    doc = materials
    if isinstance(materials, (str, Path)):
        doc = json.loads(Path(materials).read_text(encoding="utf-8"))
    rules = doc.get("materials") if isinstance(doc, dict) else None
    if not isinstance(rules, list):
        raise ExportError("a material map is {\"materials\": [{\"parts\": [...], \"color\": \"#rrggbb\", ...}]}")
    out = []
    for i, r in enumerate(rules):
        w = "materials[%d]" % i
        if not isinstance(r, dict) or not set(r) <= MATERIAL_KEYS or "parts" not in r:
            raise ExportError("%s: keys are %s, and \"parts\" is required" % (w, ", ".join(sorted(MATERIAL_KEYS))))
        pats = [r["parts"]] if isinstance(r["parts"], str) else r["parts"]
        if not isinstance(pats, list) or not pats or not all(isinstance(p, str) for p in pats):
            raise ExportError("%s.parts: a part id, a pattern like \"tile-*\", or a list of them" % w)
        for k in ("metallic", "roughness"):
            if k in r and not (isinstance(r[k], (int, float)) and 0 <= r[k] <= 1):
                raise ExportError("%s.%s: a number from 0 to 1" % (w, k))
        finish = r.get("finish")
        if finish is not None and finish not in FINISHES:
            raise ExportError("%s.finish: one of %s" % (w, ", ".join(FINISHES)))
        f = FINISHES.get(finish, {})
        color = _hex(r.get("color", "#cccccc"), w + ".color")
        out.append({"patterns": pats, "name": str(r.get("name", "map:%d" % i)), "color": color, "finish": finish,
                    "metallic": float(r.get("metallic", f.get("metallic", 0.0))),
                    "roughness": float(r.get("roughness", f.get("roughness", 0.5))),
                    "emissive": _hex(r["emissive"], w + ".emissive") if "emissive" in r else
                    (color if finish == "light" else None),
                    "clearcoat": f.get("clearcoat"), "transmission": f.get("transmission"), "glow": f.get("glow")})
    return out


def _groups(g):
    """The compile's packed arrays, grouped by (part, joint, motion slot): triangles with their phases,
    segments and points by tone."""
    styles = g["styles"]
    out = {}

    def grp(si):
        st = styles[si]
        k = (int(st[6]), int(st[9]), int(st[7]))
        if k not in out:
            out[k] = {"tris": [], "tri_phase": [], "segs": {}, "pts": {}}
        return out[k], scene_mod.TONES[int(st[0])]

    f = g["fills"]
    for i in range(0, len(f), 15):
        o, _ = grp(int(f[i + 3]))
        o["tris"].append(tuple((f[i + 5 * j], f[i + 5 * j + 1], f[i + 5 * j + 2]) for j in range(3)))
        o["tri_phase"].append(tuple(f[i + 5 * j + 4] for j in range(3)))
    ln = g["lines"]
    for i in range(0, len(ln), 9):
        o, tone = grp(int(ln[i + 6]))
        o["segs"].setdefault(tone, []).append(((ln[i], ln[i + 1], ln[i + 2]), (ln[i + 3], ln[i + 4], ln[i + 5]),
                                               ln[i + 7], ln[i + 8]))
    pt = g["points"]
    for i in range(0, len(pt), 7):
        o, tone = grp(int(pt[i + 4]))
        o["pts"].setdefault(tone, []).append(((pt[i], pt[i + 1], pt[i + 2]), pt[i + 6]))
    return out


def _wire_radius(g, wire_radius):
    if wire_radius is not None:
        if not wire_radius > 0:
            raise ExportError("--wire-radius: a positive number of metres")
        return float(wire_radius)
    return max(g["bounds"]["radius"] * 0.0009, 1e-4)


# ---------------------------------------------------------------------------- pieces: bodies physics can knock apart

PIECE_CELLS = 10        # a large piece is cut into surface patches about 1/10 of the object across
PIECE_THICK = 0.15      # each patch is given this share of a cell as thickness, inward
PIECE_INSET = 0.003     # every shape is pulled in by this share of the object, so touching parts start apart
PIECE_DENSITY = 300.0   # kg per cubic metre of a shape's box: masses in proportion, not real


def _components(tris):
    """The connected pieces of a triangle list, as lists of triangle indices."""
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    keys = [[tuple(round(x, 6) for x in p) for p in t] for t in tris]
    for ks in keys:
        for k in ks[1:]:
            ra, rb = find(ks[0]), find(k)
            if ra != rb:
                parent[ra] = rb
    out = {}
    for i, ks in enumerate(keys):
        out.setdefault(find(ks[0]), []).append(i)
    return list(out.values())


def _mean(pts):
    return [sum(p[a] for p in pts) / len(pts) for a in range(3)]


def _piece_shapes(tris, comp, cell, inset):
    """Convex point sets for one connected piece: the piece itself if it is small, else one patch per cell of a
    grid over it (so a hollow shell is a skin of patches, not a solid block); each patch given thickness toward
    the piece's middle (a flat open surface, on both sides of its plane), and pulled in by `inset`."""
    pts = [p for i in comp for p in tris[i]]
    lo, hi = _bounds(pts)
    middle = _mean(pts)
    clusters = {}
    if math.dist(lo, hi) > 2 * cell:
        for i in comp:
            c = _mean(tris[i])
            clusters.setdefault(tuple(int((c[a] - lo[a]) / cell) for a in range(3)), []).append(i)
    else:
        clusters[0] = comp
    out = []
    for idx in clusters.values():
        cpts = list({tuple(p) for i in idx for p in tris[i]})
        size = math.dist(*_bounds(cpts))
        t = min(cell * PIECE_THICK, max(size, 1e-4) * 0.5)
        hull = list(cpts)
        for p in cpts:   # inward, toward the middle, never past it
            v = _sub(middle, p)
            ln = math.sqrt(_dot(v, v))
            if ln > 1e-9:
                k = min(t, ln * 0.5) / ln
                hull.append(tuple(p[a] + v[a] * k for a in range(3)))
        lo_, hi_ = _bounds(hull)
        if min(hi_[a] - lo_[a] for a in range(3)) < t * 0.2:   # flat (an open panel): thickness both ways
            a, b_, c = tris[idx[0]]
            n = _cross(_sub(b_, a), _sub(c, a))
            ln = math.sqrt(_dot(n, n))
            if ln > 0:
                n = [x / ln * t * 0.5 for x in n]
                hull += [tuple(p[k] + s_ * n[k] for k in range(3)) for p in cpts for s_ in (1, -1)]
        hc = _mean(hull)
        d = min(inset, size * 0.2)
        shrunk = []
        for p in hull:
            v = _sub(p, hc)
            ln = math.sqrt(_dot(v, v))
            shrunk.append(tuple(hc[a] + v[a] * max(0.0, 1 - d / ln) if ln > 0 else hc[a] for a in range(3)))
        out.append(shrunk)
    return out


QUALITY = (("good", 20.0, "#3fbf6a"), ("fair", 10.0, "#e0a43a"), ("thin", 0.0, "#e04848"))


def smallest_angle(t):
    """A triangle's smallest angle, in degrees (0 for a degenerate one)."""
    out = 180.0
    for i in range(3):
        p, q, r = t[i], t[(i + 1) % 3], t[(i + 2) % 3]
        u, w = _sub(q, p), _sub(r, p)
        nu, nw = math.sqrt(_dot(u, u)), math.sqrt(_dot(w, w))
        if not nu or not nw:
            return 0.0
        out = min(out, math.degrees(math.acos(max(-1.0, min(1.0, _dot(u, w) / (nu * nw))))))
    return out


def quality_class(t):
    a = smallest_angle(t)
    return next(name for name, lo, _ in QUALITY if a >= lo)


def triangle_quality(g):
    """How well shaped the surfaces' triangles are: the share whose smallest angle is under 10 degrees (thin
    slivers, which subdivide and shade badly) and under 20 (fair)."""
    n = thin = fair = 0
    f = g["fills"]
    for i in range(0, len(f), 15):
        a = smallest_angle([(f[i + 5 * j], f[i + 5 * j + 1], f[i + 5 * j + 2]) for j in range(3)])
        n += 1
        thin += a < 10.0
        fair += 10.0 <= a < 20.0
    return {"triangles": n, "thin": thin, "fair": fair,
            "thin_share": round(thin / n, 3) if n else 0.0, "fair_share": round(fair / n, 3) if n else 0.0}


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _neg(a):
    return (-a[0], -a[1], -a[2])


def _intersect(A, B, steps=64):
    """Whether the convex hulls of point sets A and B intersect (GJK on their Minkowski difference)."""
    def support(d):
        p = max(A, key=lambda q: _dot(q, d))
        q = min(B, key=lambda r: _dot(r, d))
        return _sub(p, q)
    d = _sub(_mean(A), _mean(B))
    if not any(d):
        d = (1.0, 0.0, 0.0)
    simplex = [support(d)]
    d = _neg(simplex[0])
    for _ in range(steps):
        if not any(abs(x) > 1e-15 for x in d):
            return True
        p = support(d)
        if _dot(p, d) < 0:
            return False
        simplex.append(p)
        a = simplex[-1]
        ao = _neg(a)
        if len(simplex) == 2:
            b_ = simplex[0]
            ab = _sub(b_, a)
            d = _cross(_cross(ab, ao), ab) if _dot(ab, ao) > 0 else ao
            if _dot(ab, ao) <= 0:
                simplex = [a]
        elif len(simplex) == 3:
            c, b_ = simplex[0], simplex[1]
            ab, ac = _sub(b_, a), _sub(c, a)
            abc = _cross(ab, ac)
            if _dot(_cross(abc, ac), ao) > 0:
                if _dot(ac, ao) > 0:
                    simplex, d = [c, a], _cross(_cross(ac, ao), ac)
                else:
                    simplex, d = [b_, a], (_cross(_cross(ab, ao), ab) if _dot(ab, ao) > 0 else ao)
            elif _dot(_cross(ab, abc), ao) > 0:
                simplex, d = [b_, a], (_cross(_cross(ab, ao), ab) if _dot(ab, ao) > 0 else ao)
            elif _dot(abc, ao) > 0:
                d = abc
            else:
                simplex, d = [b_, c, a], _neg(abc)
        else:
            d_, c, b_ = simplex[0], simplex[1], simplex[2]
            ab, ac, ad = _sub(b_, a), _sub(c, a), _sub(d_, a)
            abc, acd, adb = _cross(ab, ac), _cross(ac, ad), _cross(ad, ab)
            if _dot(abc, ad) > 0:
                abc = _neg(abc)
            if _dot(acd, ab) > 0:
                acd = _neg(acd)
            if _dot(adb, ac) > 0:
                adb = _neg(adb)
            if _dot(abc, ao) > 0:
                simplex, d = [c, b_, a], abc
            elif _dot(acd, ao) > 0:
                simplex, d = [d_, c, a], acd
            elif _dot(adb, ao) > 0:
                simplex, d = [b_, d_, a], adb
            else:
                return True
    return True


def _shrunk(pts, f):
    c = _mean(pts)
    return [tuple(c[a] + (p[a] - c[a]) * f for a in range(3)) for p in pts]


def _assemblies(copies, deep=0.7):
    """Which pieces belong together: two whose shapes still meet with the smaller shrunk to `deep` of its size
    are interlocked (a rim in its tyre, an axle through its hubs) and become one body. Pieces that move (a door)
    stay apart. Returns a group index per copy."""
    group = list(range(len(copies)))

    def root(i):
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i
    boxes = []
    for c in copies:
        pts = [p for h in c["hulls"] for p in h]
        boxes.append(([min(p[a] for p in pts) for a in range(3)], [max(p[a] for p in pts) for a in range(3)]))
    for i in range(len(copies)):
        if copies[i]["moving"]:
            continue
        for j in range(i + 1, len(copies)):
            if copies[j]["moving"] or root(i) == root(j):
                continue
            (lo1, hi1), (lo2, hi2) = boxes[i], boxes[j]
            if any(lo1[a] > hi2[a] or lo2[a] > hi1[a] for a in range(3)):
                continue
            hit = False
            for h1 in copies[i]["hulls"]:
                for h2 in copies[j]["hulls"]:
                    small, big = (h1, h2) if math.dist(*_bounds(h1)) < math.dist(*_bounds(h2)) else (h2, h1)
                    if _intersect(_shrunk(small, deep), big):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                group[root(i)] = root(j)
    return [root(i) for i in range(len(copies))]


def _bounds(pts):
    return [min(p[a] for p in pts) for a in range(3)], [max(p[a] for p in pts) for a in range(3)]


# ---------------------------------------------------------------------------- glTF

class _Bin:
    """The binary chunk, with one bufferView per accessor (4-byte aligned)."""

    def __init__(self):
        self.data = bytearray()
        self.views, self.accessors = [], []

    def add(self, fmt, rows, kind, ctype, target=None, minmax=False):
        start = len(self.data)
        n = len(rows)
        if fmt in ("f", "I", "H"):
            self.data += struct.pack("<%d%s" % (n, fmt), *rows)
            count = n
        else:
            flat = [x for r in rows for x in r]
            self.data += struct.pack("<%d%s" % (len(flat), fmt[0]), *flat)
            count = n
        while len(self.data) % 4:
            self.data.append(0)
        view = {"buffer": 0, "byteOffset": start, "byteLength": len(self.data) - start}
        if target:
            view["target"] = target
        self.views.append(view)
        acc = {"bufferView": len(self.views) - 1, "componentType": ctype, "count": count, "type": kind}
        if minmax and n:
            if kind == "SCALAR":
                acc["min"], acc["max"] = [min(rows)], [max(rows)]
            else:
                dims = len(rows[0])
                acc["min"] = [min(r[k] for r in rows) for k in range(dims)]
                acc["max"] = [max(r[k] for r in rows) for k in range(dims)]
        self.accessors.append(acc)
        return len(self.accessors) - 1


def _f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def _primitive(b, mode, positions, normals, phases, material, uvs=None):
    """Indexed vertices (deduplicated), as one glTF primitive."""
    index, verts, idx = {}, [], []
    for i, p in enumerate(positions):
        k = (tuple(_f32(x) for x in p), tuple(_f32(x) for x in normals[i]) if normals else None, _f32(phases[i]),
             tuple(_f32(x) for x in uvs[i]) if uvs else None)
        if k not in index:
            index[k] = len(verts)
            verts.append(k)
        idx.append(index[k])
    attrs = {"POSITION": b.add("fff", [v[0] for v in verts], "VEC3", 5126, 34962, minmax=True)}
    if normals:
        attrs["NORMAL"] = b.add("fff", [v[1] for v in verts], "VEC3", 5126, 34962)
    if uvs:
        attrs["TEXCOORD_0"] = b.add("ff", [v[3] for v in verts], "VEC2", 5126, 34962)
    attrs["_PHASE"] = b.add("f", [v[2] for v in verts], "SCALAR", 5126, 34962)
    small = len(verts) < 65536
    prim = {"attributes": attrs, "mode": mode, "material": material,
            "indices": b.add("H" if small else "I", idx, "SCALAR", 5123 if small else 5125, 34963)}
    return prim


def to_gltf(g, wire="edges", pose="closed", materials=None, wire_radius=None, merge=False, colliders=False,
            pieces=False, quality=False):
    """The glTF document (a dict) and its binary chunk, from a solid compile. With `merge`, every part
    that does not move is merged into one mesh per material (a game engine's handful of draw calls);
    the parts that move keep their own nodes, pivots and animations. With `colliders`, each part's surfaces
    get a box around them, `<part>-convcolonly` (a collision shape in Godot, moving with its joint); with
    `pieces`, each part's mesh is `<part>-rigid`, a body of its own that physics can knock apart; `pieces="glued"`,
    everything that does not move is one body and each hinged or sliding part one more, its joint in its extras
    (`construct.joint`: the body it hangs on, pivot, axis, travel) for an engine to connect (docs/GODOT.md)."""
    glued = pieces == "glued"
    pieces = bool(pieces)
    if pieces and merge:
        raise ExportError("--pieces keeps every part apart; it does not go with --merge")
    if quality and (merge or pieces):
        raise ExportError("--quality colours each part's own triangles; it does not go with --merge or --pieces")
    colliders = colliders and not pieces   # a piece's body makes its own shape from its mesh
    if wire not in WIRES:
        raise ExportError("wire: one of %s" % ", ".join(WIRES))
    if pose not in POSES:
        raise ExportError("pose: one of %s" % ", ".join(POSES))
    rules = _load_materials(materials)
    parts, arts, motions, joints = g["parts"], g["articulations"], g["motions"], g["joints"]
    own = _own_colours(g)
    b = _Bin()
    nodes, meshes, mats, mat_index = [], [], [], {}
    used_ext = set()

    def material(key, spec, extra=None):
        if key in mat_index:
            return mat_index[key]
        name, rgb, metallic, rough, emissive, is_unlit = spec
        extra = extra or {}
        m = {"name": name, "doubleSided": True,
             "pbrMetallicRoughness": {"baseColorFactor": list(_linear(rgb)) + [1.0], "metallicFactor": metallic,
                                      "roughnessFactor": rough}}
        if emissive:
            m["emissiveFactor"] = list(_linear(emissive))
        ext = {}
        if is_unlit:
            ext["KHR_materials_unlit"] = {}
        if extra.get("clearcoat"):
            ext["KHR_materials_clearcoat"] = {"clearcoatFactor": extra["clearcoat"], "clearcoatRoughnessFactor": 0.08}
        if extra.get("transmission"):
            ext["KHR_materials_transmission"] = {"transmissionFactor": extra["transmission"]}
            ext["KHR_materials_ior"] = {"ior": 1.5}
            # engines without transmission (Godot's importer, for one) still see through it
            m["pbrMetallicRoughness"]["baseColorFactor"][3] = 0.35
            m["alphaMode"] = "BLEND"
        if extra.get("glow"):
            ext["KHR_materials_emissive_strength"] = {"emissiveStrength": extra["glow"]}
        if ext:
            m["extensions"] = ext
            used_ext.update(ext)
        if extra.get("finish"):
            m["extras"] = {"construct": {"finish": extra["finish"]}}
        mats.append(m)
        mat_index[key] = len(mats) - 1
        return mat_index[key]

    def solid_material(part):
        for r in rules:
            if any(fnmatch.fnmatchcase(part["id"], p) for p in r["patterns"]):
                return material(("map", r["name"]), (r["name"], r["color"], r["metallic"], r["roughness"],
                                                     r["emissive"], False), r)
        if is_glass_name(part["id"]):
            f = FINISHES["glass"]
            return material(("glass", None), ("construct:glass", _hex("#cfd8de", "glass"), f["metallic"],
                                              f["roughness"], None, False), dict(f, finish="glass"))
        rgb, metallic, rough = ROLE_MATERIAL.get(part["role"], ROLE_MATERIAL["mass"])
        if part["id"] in own:   # the part's own colour, finished as its role is
            c = own[part["id"]]
            return material(("own", c, part["role"]), ("construct:" + c, _hex(c, "color"), metallic, rough, None, False))
        emissive = _hex(rgb, "role") if part["role"] == "data" else None
        return material(("role", part["role"]), ("construct:" + part["role"], _hex(rgb, "role"), metallic, rough,
                                                 emissive, False))

    def light_material(tone, colour=None):
        if wire == "seams":   # the design lines of a finished model: dark seams, lit like any surface
            return material(("seam", None), ("construct:seam", _hex("#141416", "seam"), 0.0, 1.0, None, False))
        rgb = _hex(colour or TONE_COLOR[tone], "tone")
        return material(("light", colour or tone), ("construct:light:" + (colour or tone), rgb, 0.0, 1.0, rgb, True))

    def node(spec):
        nodes.append(spec)
        return len(nodes) - 1

    def collider(pid, tris, parent, translation):
        """A box around a part's surfaces, as a collision shape: Godot reads `-convcolonly` as a convex shape
        and draws nothing; other engines see a box named for its part."""
        pts = [q for t in tris for q in t]
        lo = [min(q[k] for q in pts) for k in range(3)]
        hi = [max(q[k] for q in pts) for k in range(3)]
        c = [[(lo, hi)[(v >> k) & 1][k] for k in range(3)] for v in range(8)]
        quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
        pos = [c[i] for a, b_, c_, d in quads for i in (a, b_, c_, a, c_, d)]
        mat = material(("collider", None), ("construct:collider", (0.5, 0.9, 0.6), 0.0, 1.0, None, True))
        meshes.append({"name": pid + "-collider", "primitives": [_primitive(b, 4, pos, None, [0.0] * len(pos), mat)]})
        n = node({"name": pid + "-convcolonly", "mesh": len(meshes) - 1, "translation": list(translation),
                  "extras": {"construct": {"part": pid, "collider": "box"}}})
        nodes[parent].setdefault("children", []).append(n)
        counts["colliders"] = counts.get("colliders", 0) + 1

    shapes, copies, pnode_of = [], [], {}   # OMI_physics_shape's shapes; the pieces, gathered, then made bodies

    def bodies(part, gr, parent, origin, chain=-1):
        """`pieces`: each copy of a part (a mirrored tyre, a repeated window) a rigid body of its own
        (OMI_physics_body, which Godot imports as a RigidBody3D), its mesh and several convex shapes inside."""
        tris = gr["tris"]
        boxes = [(b_["min"], b_["max"]) for b_ in part["instances"]] or [(None, None)]

        def which(p):
            best, at = None, 0
            for i, (lo, hi) in enumerate(boxes):
                if lo is None:
                    return 0
                c = [(lo[a] + hi[a]) / 2 for a in range(3)]
                inside = all(lo[a] - 1e-6 <= p[a] <= hi[a] + 1e-6 for a in range(3))
                key = (0 if inside else 1, math.dist(p, c))
                if best is None or key < best:
                    best, at = key, i
            return at
        by_copy = {}
        for comp in _components(tris):
            by_copy.setdefault(which(_mean([p for i in comp for p in tris[i]])), []).append(comp)
        segs_of = {}
        for tone, segs in gr["segs"].items():
            for sg in segs:
                segs_of.setdefault(which(_mean([sg[0], sg[1]])), {}).setdefault(tone, []).append(sg)
        cell = 2 * g["bounds"]["radius"] / PIECE_CELLS
        inset = 2 * g["bounds"]["radius"] * PIECE_INSET
        for n_copy, (ci, comps) in enumerate(sorted(by_copy.items())):
            copies.append({"part": part, "gr": gr, "comps": comps, "segs": segs_of.get(ci, {}), "parent": parent,
                           "origin": origin, "moving": origin != (0.0, 0.0, 0.0) or parent != pnode_of[part["id"]],
                           "chain": chain,
                           "name": part["id"] if len(by_copy) == 1 else "%s-%d" % (part["id"], n_copy + 1),
                           "copy": n_copy + 1,
                           "hulls": [h for comp in comps for h in _piece_shapes(tris, comp, cell, inset)]})

    def emit_bodies():
        """The pieces, as bodies: interlocked pieces together (an assembly), each with its parts' meshes."""
        groups_of, joint_of = {}, {}
        if glued:   # one body for what stays put; one for each articulation chain, its joint in its extras
            for c in copies:
                groups_of.setdefault(c["chain"], []).append(c)
            for chain in groups_of:
                if chain >= 0:
                    a = arts[joints[chain][-1]]
                    outer = next((k for k in groups_of if k >= 0 and list(joints[k]) == list(joints[chain][:-1])), -1)
                    joint_of[chain] = {"type": a["type"], "articulation": a["id"], "to": outer,
                                       "pivot": [round(x, 6) for x in a.get("pivot") or (0.0, 0.0, 0.0)],
                                       "axis": [round(x, 6) for x in a["axis"]], "amount": a["amount"],
                                       "unit": a.get("unit", "deg" if a["type"] in ("hinge", "turn") else "m")}
        else:
            for i, gi in enumerate(_assemblies(copies)):
                groups_of.setdefault(gi, []).append(copies[i])
        names = {}
        for key, members in groups_of.items():
            members.sort(key=lambda c: (c["moving"] and key == -1 and glued, -sum(len(h) for h in c["hulls"])))
            if glued:
                names[key] = "%s-body" % g["id"] if key == -1 else "%s-%s" % (g["id"], joint_of[key]["articulation"])
        for key, members in groups_of.items():
            head = members[0]
            pts = [p for c in members for comp in c["comps"] for i in comp for p in c["gr"]["tris"][i]]
            centre = _mean(pts)
            kids, mass = [], 0.0
            for c in members:
                tris, gr, part = c["gr"]["tris"], c["gr"], c["part"]
                idx = [i for comp in c["comps"] for i in comp]
                local = [tuple(_sub(p, centre) for p in tris[i]) for i in idx]
                prims = [_primitive(b, 4, [p for t in local for p in t], smooth_normals(local),
                                    [x for i in idx for x in gr["tri_phase"][i]], solid_material(part), box_uvs(local))]
                counts["triangles"] += len(local)
                for tone, segs in sorted(c["segs"].items()):
                    if wire == "edges":
                        prims.append(_primitive(b, 1, [_sub(p, centre) for sg in segs for p in sg[:2]], None,
                                                [x for sg in segs for x in sg[2:]], light_material(tone, own.get(part["id"]))))
                        counts["edges"] += len(segs)
                meshes.append({"name": c["name"], "primitives": prims})
                kids.append(node({"name": c["name"] + ":mesh", "mesh": len(meshes) - 1,
                                  "extras": {"construct": {"part": part["id"], "role": part["role"], "copy": c["copy"]}}}))
                for hull in c["hulls"]:
                    pts_ = [_sub(p, centre) for p in hull]
                    lo, hi = _bounds(pts_)
                    mass += max((hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]), 1e-7) * PIECE_DENSITY
                    # the points as a fan of triangles: an importer takes the convex hull of a shape's vertices
                    fan = [i for k in range(1, len(pts_) - 1) for i in (0, k, k + 1)]
                    acc = b.add("fff", pts_, "VEC3", 5126, 34962, minmax=True)
                    meshes.append({"name": "%s-shape-%d" % (c["name"], len(shapes)), "primitives": [
                        {"attributes": {"POSITION": acc}, "mode": 4, "indices": b.add("I", fan, "SCALAR", 5125, 34963)}]})
                    shapes.append({"type": "convex", "convex": {"mesh": len(meshes) - 1}})
                    kids.append(node({"name": "%s-shape-%d" % (c["name"], len(shapes) - 1),
                                      "extensions": {"OMI_physics_body": {"collider": {"shape": len(shapes) - 1}}}}))
            name = names.get(key) or (head["name"] if len(members) == 1 else head["name"] + "-assembly")
            extra = {"piece": name, "parts": [c["name"] for c in members]}
            if key in joint_of:
                extra["joint"] = dict(joint_of[key], to=names[joint_of[key]["to"]] if joint_of[key]["to"] in names
                                      else names.get(-1))
            body = node({"name": _node_name(name), "translation": _sub(centre, head["origin"]), "children": kids,
                         "extensions": {"OMI_physics_body": {"motion": {"type": "dynamic",
                                                                        "mass": round(min(max(mass, 0.05), 2000.0), 3)}}},
                         "extras": {"construct": extra}})
            nodes[head["parent"]].setdefault("children", []).append(body)
            counts["pieces"] = counts.get("pieces", 0) + 1
        used_ext.update(("OMI_physics_body", "OMI_physics_shape"))


    root = node({"name": g["id"], "children": []})
    stage_nodes = {}
    for s in g["stages"]:
        stage_nodes[s["stage"]] = node({"name": "stage-%d" % s["stage"], "children": [],
                                        "extras": {"construct": {"stage": s["stage"], "order": s["index"]}}})
        nodes[root]["children"].append(stage_nodes[s["stage"]])

    art_nodes = {i: [] for i in range(len(arts))}       # articulation -> [(node, base translation)]
    motion_nodes = {i: [] for i in range(len(motions))}
    groups = _groups(g)
    radius = _wire_radius(g, wire_radius)
    counts = {"triangles": 0, "edges": 0, "points": 0}

    merged, merged_parts = {}, []   # (mode, material) -> positions, normals, phases, uvs

    def bucket(mode, mat, pos, nor, ph, uv):
        m = merged.setdefault((mode, mat), ([], [], [], []))
        for lst, add in zip(m, (pos, nor or [], ph, uv or [])):
            lst.extend(add)

    for pi, part in enumerate(parts):
        keys = sorted(k for k in groups if k[0] == pi)
        moving = [k for k in keys if k[1] >= 0 or k[2] >= 0]
        if merge and keys and not moving:
            merged_parts.append(part["id"])
        extras = {"construct": {k: part[k] for k in ("id", "label", "role", "certainty", "certainty_axes", "basis",
                                                     "source", "stage", "shape", "floating") if k in part}}
        extras["construct"]["instances"] = len(part["instances"])
        pnode = None
        if not (merge and keys and not moving):
            pnode = node({"name": _node_name(part["id"]), "extras": extras})
            nodes[stage_nodes[part["stage"]]]["children"].append(pnode)
            pnode_of[part["id"]] = pnode
        if not keys:
            continue
        surfaced = any(groups[k]["tris"] for k in keys)   # its lines are construction lines, not seams
        for k in keys:
            _, jt, slot = k
            gr = groups[k]
            prims = []
            static = merge and jt < 0 and slot < 0
            if gr["tris"]:
                pos = [p for t in gr["tris"] for p in t]
                nor, ph, uv = smooth_normals(gr["tris"]), [x for t in gr["tri_phase"] for x in t], box_uvs(gr["tris"])
                if static:
                    bucket(4, solid_material(part), pos, nor, ph, uv)
                elif quality:   # each triangle coloured by its smallest angle: green good, amber fair, red thin
                    for qname, _, qcol in QUALITY:
                        idx = [i for i, t in enumerate(gr["tris"]) if quality_class(t) == qname]
                        if idx:
                            prims.append(_primitive(b, 4, [pos[3 * i + j] for i in idx for j in range(3)],
                                                    [nor[3 * i + j] for i in idx for j in range(3)],
                                                    [ph[3 * i + j] for i in idx for j in range(3)],
                                                    material(("quality", qname), ("construct:quality:" + qname,
                                                                                  _hex(qcol, "quality"), 0.0, 0.8, None, False)),
                                                    [uv[3 * i + j] for i in idx for j in range(3)]))
                else:
                    prims.append(_primitive(b, 4, pos, nor, ph, solid_material(part), uv))
                counts["triangles"] += len(gr["tris"])
            for tone, segs in sorted(gr["segs"].items()):
                if wire == "edges":
                    pos, ph = [p for s in segs for p in s[:2]], [x for s in segs for x in s[2:]]
                    if static:
                        bucket(1, light_material(tone, own.get(part["id"])), pos, None, ph, None)
                    else:
                        prims.append(_primitive(b, 1, pos, None, ph, light_material(tone, own.get(part["id"]))))
                    counts["edges"] += len(segs)
                elif wire == "tubes" or (wire == "seams" and not surfaced):
                    pos, nor, ph = [], [], []
                    for a, c, pa, pc in segs:
                        tris, norms, ends = _tube(a, c, radius)
                        pos += [p for t in tris for p in t]
                        nor += norms
                        ph += [pc if e else pa for e in ends]
                    if pos and static:
                        bucket(4, light_material(tone, own.get(part["id"])), pos, nor, ph, None)
                        counts["triangles"] += len(pos) // 3
                    elif pos:
                        prims.append(_primitive(b, 4, pos, nor, ph, light_material(tone, own.get(part["id"]))))
                        counts["triangles"] += len(pos) // 3
            for tone, pts in sorted(gr["pts"].items()):
                if static:
                    bucket(0, light_material(tone, own.get(part["id"])), [p for p, _ in pts], None, [x for _, x in pts], None)
                else:
                    prims.append(_primitive(b, 0, [p for p, _ in pts], None, [x for _, x in pts], light_material(tone, own.get(part["id"]))))
                counts["points"] += len(pts)
            if not prims:
                continue
            meshes.append({"name": part["id"], "primitives": prims})
            mesh = len(meshes) - 1
            if jt < 0 and slot < 0 and len(keys) == 1 and not (pieces and gr["tris"]):
                nodes[pnode]["mesh"] = mesh
                if colliders and gr["tris"]:
                    collider(part["id"], gr["tris"], pnode, [0.0, 0.0, 0.0])
                continue
            # a chain of pivot nodes: the first articulation is outermost, a periodic motion inside them
            parent, origin = pnode, (0.0, 0.0, 0.0)
            for ai in (joints[jt] if jt >= 0 else []):
                a = arts[ai]
                piv = tuple(a["pivot"]) if a["type"] in ("hinge", "turn") and a.get("pivot") else origin
                base = _sub(piv, origin)
                spec = {"name": "%s:%s" % (part["id"], a["id"]), "translation": list(base),
                        "extras": {"construct": {"part": part["id"], "articulation": a["id"]}}}
                if pose == "open":
                    if a["type"] in ("hinge", "turn"):
                        spec["rotation"] = list(_quat(a["axis"], a["amount"]))
                    else:
                        spec["translation"] = [base[i] + a["axis"][i] * a["amount"] for i in range(3)]
                n = node(spec)
                nodes[parent].setdefault("children", []).append(n)
                art_nodes[ai].append((n, base))
                parent, origin = n, piv
            if slot >= 0 and motions[slot]["type"] != "pulse":
                m = motions[slot]
                piv = tuple(m["pivot"]) if m["type"] in ("spin", "swing") else origin
                base = _sub(piv, origin)
                n = node({"name": "%s:motion-%d" % (part["id"], slot), "translation": list(base),
                          "extras": {"construct": {"part": part["id"], "motion": slot}}})
                nodes[parent].setdefault("children", []).append(n)
                motion_nodes[slot].append((n, base))
                parent, origin = n, piv
            if pieces and gr["tris"]:
                bodies(part, gr, parent, origin, jt)
                continue
            n = node({"name": "%s:mesh" % part["id"], "mesh": mesh,
                      "translation": [-x for x in origin], "extras": {"construct": {"part": part["id"], "role": part["role"]}}})
            nodes[parent].setdefault("children", []).append(n)
            if colliders and gr["tris"]:
                collider(part["id"], gr["tris"], parent, [-x for x in origin])

    if copies:
        emit_bodies()
    if merged:
        prims = [_primitive(b, mode, pos, nor or None, ph, mat, uv or None)
                 for (mode, mat), (pos, nor, ph, uv) in sorted(merged.items())]
        meshes.append({"name": "merged", "primitives": prims})
        n = node({"name": "merged", "mesh": len(meshes) - 1,
                  "extras": {"construct": {"merged_parts": merged_parts,
                                           "note": "every part that does not move, one primitive per material"}}})
        nodes[root]["children"].append(n)
        if colliders:   # the merged parts keep a collision shape each, beside the one mesh
            index = {p["id"]: i for i, p in enumerate(parts)}
            for pid in merged_parts:
                tris = [t for k, gr in groups.items() if k[0] == index[pid] for t in gr["tris"]]
                if tris:
                    collider(pid, tris, n, [0.0, 0.0, 0.0])
    animations = _animations(b, arts, motions, art_nodes, motion_nodes)
    for n in nodes:
        if "translation" in n and all(abs(x) < 1e-12 for x in n["translation"]):
            del n["translation"]
        if "children" in n and not n["children"]:   # glTF forbids an empty array (a stage merged away)
            del n["children"]
    doc = {
        "asset": {"version": "2.0", "generator": "%s %s (%s)" % (product.TITLE, product.VERSION, product.CONTRACT)},
        "scene": 0, "scenes": [{"name": g["title"], "nodes": [root]}],
        "nodes": nodes, "meshes": meshes, "materials": mats, "accessors": b.accessors, "bufferViews": b.views,
        "buffers": [{"byteLength": len(b.data)}],
    }
    if animations:
        doc["animations"] = animations
    if used_ext:
        doc["extensionsUsed"] = sorted(used_ext)
    if shapes:
        doc.setdefault("extensions", {})["OMI_physics_shape"] = {"shapes": shapes}
    nodes[root]["extras"] = {"construct": {
        "format": g["format"], "contract": g["contract"], "id": g["id"], "title": g["title"],
        "subject": g["subject"], "scene_sha256": g["scene_sha256"], "frame": g["frame"],
        "units": "metres", "pose": pose, "wire": wire,
        "build_phase": "every vertex's _PHASE (0..1) is when it appears in the assembly; stages are the "
                       "children of this node",
        "sources": g["provenance"]["sources"], "facts": g["provenance"]["facts"],
        "articulations": [{k: a[k] for k in ("id", "type", "axis", "pivot", "amount", "unit", "order", "parts")}
                          for a in arts],
        "motions": [{k: m[k] for k in ("part", "type", "period", "rpm", "degrees", "distance", "amount", "phase")}
                    for m in motions]}}
    summary = {"parts": len(parts), "nodes": len(nodes), "meshes": len(meshes), "materials": len(mats),
               "animations": [a["name"] for a in animations], **counts}
    return doc, bytes(b.data), summary


def _animations(b, arts, motions, art_nodes, motion_nodes):
    out = []

    def channels(samplers, chans, node, path, times, values, kind):
        inp = b.add("f", times, "SCALAR", 5126, minmax=True)
        outp = b.add("ffff" if kind == "VEC4" else "fff", values, kind, 5126)
        samplers.append({"input": inp, "output": outp, "interpolation": "LINEAR"})
        chans.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})

    def art_value(a, base, u):
        if a["type"] in ("hinge", "turn"):
            return "rotation", list(_quat(a["axis"], a["amount"] * u)), "VEC4"
        return "translation", [base[i] + a["axis"][i] * a["amount"] * u for i in range(3)], "VEC3"

    def art_keys(a, t0):
        n = max(5, int(abs(a["amount"]) / 15) + 2 if a["type"] in ("hinge", "turn") else 5)
        return [(t0 + GROUP_SECONDS * i / (n - 1), _ease(i / (n - 1))) for i in range(n)]

    def add_art_clip(name, plan, total):
        samplers, chans = [], []
        for ai, t0 in plan:
            a = arts[ai]
            keys = art_keys(a, t0)
            if t0 > 0:
                keys = [(0.0, 0.0)] + keys
            if keys[-1][0] < total - 1e-9:
                keys.append((total, 1.0))
            for n, base in art_nodes[ai]:
                path, _, kind = art_value(a, base, 0)
                channels(samplers, chans, n, path, [t for t, _ in keys],
                         [art_value(a, base, u)[1] for _, u in keys], kind)
        if chans:
            out.append({"name": name, "samplers": samplers, "channels": chans})

    if arts:
        orders = sorted({a["order"] for a in arts})
        total = GROUP_SECONDS * len(orders)
        add_art_clip("open", [(i, GROUP_SECONDS * orders.index(a["order"])) for i, a in enumerate(arts)], total)
        if len(arts) > 1:
            for i, a in enumerate(arts):
                add_art_clip("open:" + a["id"], [(i, 0.0)], GROUP_SECONDS)

    moving = [i for i, m in enumerate(motions) if m["type"] != "pulse" and motion_nodes[i]
              and (m["type"] != "spin" or m["rpm"])]
    if moving:
        periods = [60.0 / abs(motions[i]["rpm"]) if motions[i]["type"] == "spin" else motions[i]["period"]
                   for i in moving]
        tenths = [max(1, int(round(p * 10))) for p in periods]
        lcm = 1
        for t in tenths:
            lcm = lcm * t // math.gcd(lcm, t)
        total = lcm / 10 if lcm <= 1200 else max(periods)   # loops cleanly when the periods allow it
        samplers, chans = [], []
        for i, period in zip(moving, periods):
            m = motions[i]
            n = int(math.ceil(total / period * 12)) + 1
            times = [total * k / (n - 1) for k in range(n)]
            for node_i, base in motion_nodes[i]:
                if m["type"] == "spin":
                    vals = [list(_quat(m["axis"], math.degrees(m["rpm"] * 2 * math.pi / 60 * t + 2 * math.pi * m["phase"])))
                            for t in times]
                    channels(samplers, chans, node_i, "rotation", times, vals, "VEC4")
                elif m["type"] == "swing":
                    vals = [list(_quat(m["axis"], m["degrees"] * math.sin(2 * math.pi * (t / m["period"] + m["phase"]))))
                            for t in times]
                    channels(samplers, chans, node_i, "rotation", times, vals, "VEC4")
                else:   # bob
                    ax = _unit(m["axis"])
                    vals = [[base[k] + ax[k] * m["distance"] * math.sin(2 * math.pi * (t / m["period"] + m["phase"]))
                             for k in range(3)] for t in times]
                    channels(samplers, chans, node_i, "translation", times, vals, "VEC3")
        out.append({"name": "idle", "samplers": samplers, "channels": chans})
    return out


def pack_glb(doc, binary):
    """The .glb bytes: a 12-byte header, the JSON chunk and the binary chunk."""
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    doc_len = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<4sII", b"glTF", 2, doc_len) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def read_glb(data):
    """The JSON document and the binary chunk of .glb bytes (for checks and tests)."""
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ExportError("not a glTF 2.0 binary")
    jlen, jtype = struct.unpack_from("<I4s", data, 12)
    doc = json.loads(data[20:20 + jlen].decode("utf-8"))
    off = 20 + jlen
    blen, btype = struct.unpack_from("<I4s", data, off)
    if jtype != b"JSON" or btype != b"BIN\0":
        raise ExportError("unexpected chunk types")
    return doc, data[off + 8:off + 8 + blen]


# ---------------------------------------------------------------------------- OBJ

def to_obj(g, name, wire="edges", pose="closed", materials=None, frame="y-up", wire_radius=None):
    """The OBJ and MTL texts: one object per part, in one pose, with smoothed normals."""
    if wire not in WIRES:
        raise ExportError("wire: one of %s" % ", ".join(WIRES))
    rules = _load_materials(materials)
    parts, arts, joints = g["parts"], g["articulations"], g["joints"]
    own = _own_colours(g)
    radius = _wire_radius(g, wire_radius)

    def place(p, jt):
        if pose == "open" and jt >= 0:
            p = scene_mod._chain_apply(joints[jt], arts, p)
        return (p[0], -p[2], p[1]) if frame == "z-up" else tuple(p)

    def placen(n, jt):
        if pose == "open" and jt >= 0:   # a direction turns with the chain; the pivots cancel out
            o = scene_mod._chain_apply(joints[jt], arts, (0.0, 0.0, 0.0))
            q = scene_mod._chain_apply(joints[jt], arts, n)
            n = (q[0] - o[0], q[1] - o[1], q[2] - o[2])
        return (n[0], -n[2], n[1]) if frame == "z-up" else n

    mtl, used = [], {}

    def matname(part):
        own_c = own.get(part["id"])
        for r in rules:
            if any(fnmatch.fnmatchcase(part["id"], p) for p in r["patterns"]):
                spec = (r["color"], r["roughness"], r["emissive"], 0.25 if r["finish"] == "glass" else 1.0)
                nm = r["name"]
                break
        else:
            rgb, _, rough = ROLE_MATERIAL.get(part["role"], ROLE_MATERIAL["mass"])
            spec, nm = (_hex(own_c or rgb, "role"), rough, None, 1.0), "construct-" + (own_c[1:] if own_c else part["role"])
        nm = nm.replace(" ", "_")
        if nm not in used:
            used[nm] = spec
        return nm

    def lightname(tone, colour=None):
        if wire == "seams":
            used.setdefault("construct-seam", (_hex("#141416", "seam"), 1.0, None, 1.0))
            return "construct-seam"
        nm = "construct-light-" + (colour[1:] if colour else tone)
        if nm not in used:
            rgb = _hex(colour or TONE_COLOR[tone], "tone")
            used[nm] = (rgb, 1.0, rgb, 1.0)
        return nm

    groups = _groups(g)
    out = ["# %s %s: %s" % (product.TITLE, product.VERSION, g["title"]),
           "# metres, %s, pose %s; contract %s" % ("Z up" if frame == "z-up" else "Y up", pose, g["contract"]),
           "mtllib %s.mtl" % name]
    nv = nn = nt = 0
    counts = {"triangles": 0, "edges": 0}
    named = {}
    for (pi, jt, _), gr in sorted(groups.items()):
        part = parts[pi]
        if not gr["tris"] and not (gr["segs"] and wire != "none"):
            continue
        k = named[part["id"]] = named.get(part["id"], -1) + 1
        out.append("o %s" % (part["id"] if k == 0 else "%s.%d" % (part["id"], k)))
        if gr["tris"]:
            out.append("usemtl %s" % matname(part))
            tris = gr["tris"]
            normals = smooth_normals(tris)
            # positions shared between faces (a subdivision surface needs them welded); normals and
            # texture coordinates per corner, so a hard edge stays hard
            index, pos = {}, []
            corner = []
            for t in tris:
                ids = []
                for p in t:
                    key = tuple(round(x, 7) for x in p)
                    if key not in index:
                        index[key] = len(pos)
                        pos.append(p)
                    ids.append(index[key])
                corner.append(ids)
            for p in pos:
                out.append("v %.6f %.6f %.6f" % place(p, jt))
            for uv in box_uvs(tris):
                out.append("vt %.5f %.5f" % uv)
            for n in normals:
                out.append("vn %.5f %.5f %.5f" % placen(n, jt))
            k = 0
            while k < len(tris):   # a quad the construct drew as (a, b, c) and (a, c, d) is one face again
                a, b, c = corner[k]
                if k + 1 < len(tris):
                    a2, c2, d = corner[k + 1]
                    if a2 == a and c2 == c and len({a, b, c, d}) == 4:
                        out.append("f " + " ".join("%d/%d/%d" % (nv + v + 1, nt + 3 * kk + j + 1, nn + 3 * kk + j + 1)
                                                   for v, kk, j in ((a, k, 0), (b, k, 1), (c, k, 2), (d, k + 1, 2))))
                        counts["quads"] = counts.get("quads", 0) + 1
                        k += 2
                        continue
                out.append("f " + " ".join("%d/%d/%d" % (nv + v + 1, nt + 3 * k + j + 1, nn + 3 * k + j + 1)
                                           for j, v in enumerate((a, b, c))))
                k += 1
            nv += len(pos)
            nt += 3 * len(tris)
            nn += 3 * len(gr["tris"])
            counts["triangles"] += len(gr["tris"])
        for tone, segs in sorted(gr["segs"].items()):
            if wire == "none" or (wire == "seams" and gr["tris"]):   # seams: only the parts drawn as lines
                continue
            out.append("usemtl %s" % lightname(tone, own.get(part["id"])))
            if wire == "edges":
                for a, c, _, _ in segs:
                    out.append("v %.6f %.6f %.6f" % place(a, jt))
                    out.append("v %.6f %.6f %.6f" % place(c, jt))
                    out.append("l %d %d" % (nv + 1, nv + 2))
                    nv += 2
                counts["edges"] += len(segs)
            else:
                for a, c, _, _ in segs:
                    tris, norms, _ = _tube(a, c, radius)
                    for t in tris:
                        for p in t:
                            out.append("v %.6f %.6f %.6f" % place(p, jt))
                    for n in norms:
                        out.append("vn %.5f %.5f %.5f" % placen(n, jt))
                    for k in range(len(tris)):
                        a0 = nv + 3 * k + 1
                        out.append("f %d//%d %d//%d %d//%d" % (a0, nn + 3 * k + 1, a0 + 1, nn + 3 * k + 2, a0 + 2,
                                                               nn + 3 * k + 3))
                    nv += 3 * len(tris)
                    nn += 3 * len(tris)
                    counts["triangles"] += len(tris)
    for nm, (rgb, rough, emissive, opacity) in used.items():
        mtl += ["newmtl %s" % nm, "Kd %.4f %.4f %.4f" % rgb, "Ks 0.04 0.04 0.04",
                "Ns %.1f" % (900 * (1 - rough) ** 2 + 4), "d %.2f" % opacity, "illum 2"]
        if emissive:
            mtl.append("Ke %.4f %.4f %.4f" % emissive)
        mtl.append("")
    return "\n".join(out) + "\n", "\n".join(mtl), counts


# ---------------------------------------------------------------------------- one call

def render(scene, fmt="glb", wire="edges", pose="closed", materials=None, frame="y-up", wire_radius=None,
           name="construct", merge=False, colliders=False, pieces=False, quality=False):
    """Compile `scene` solid and export it in memory: {"glb": bytes} or {"obj": text, "mtl": text}, with a
    summary."""
    if fmt not in FORMATS:
        raise ExportError("format: glb or obj (from --format or the file's extension), not %r" % fmt)
    if frame not in FRAMES:
        raise ExportError("frame: one of %s" % ", ".join(FRAMES))
    if fmt == "glb" and frame != "y-up":
        raise ExportError("glTF is Y up by definition; --frame z-up is for OBJ")
    g = scene_mod.compile_scene(scene, solid=True)
    if fmt == "glb":
        doc, binary, summary = to_gltf(g, wire, pose, materials, wire_radius, merge, colliders, pieces, quality)
        out = {"glb": pack_glb(doc, binary)}
        summary["bytes"] = len(out["glb"])
    else:
        text, mtl, counts = to_obj(g, name, wire, pose, materials, frame, wire_radius)
        out = {"obj": text, "mtl": mtl}
        summary = {"parts": len(g["parts"]), **counts}
    if quality and fmt != "glb":
        raise ExportError("--quality is a glTF view (each triangle coloured); give a .glb")
    summary.update({"format": fmt, "pose": pose, "wire": wire, "quality": triangle_quality(g)})
    return out, summary


def export(scene, path, fmt=None, wire="edges", pose="closed", materials=None, frame="y-up", wire_radius=None,
           merge=False, colliders=False, pieces=False, quality=False):
    """Compile `scene` solid and write it to `path` (.glb, or .obj with its .mtl beside it). Returns a summary."""
    path = Path(path)
    fmt = fmt or path.suffix.lower().lstrip(".")
    out, summary = render(scene, fmt, wire, pose, materials, frame, wire_radius, name=path.stem, merge=merge,
                          colliders=colliders, pieces=pieces, quality=quality)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "glb":
        path.write_bytes(out["glb"])
        summary["files"] = [str(path)]
    else:
        path.write_text(out["obj"], encoding="utf-8")
        path.with_suffix(".mtl").write_text(out["mtl"], encoding="utf-8")
        summary["files"] = [str(path), str(path.with_suffix(".mtl"))]
    return summary
