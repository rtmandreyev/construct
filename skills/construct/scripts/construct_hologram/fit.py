"""How a construct's solids fit: what the line art forgives and a solid, a print or a kit does not.

check(scene) -> {"issues": [...], "parts": n}. Each issue names its parts, says what is wrong and where (metres,
the scene's frame), so an agent or a person can fix them one by one and check again:

- "pokes": a part that goes in one side of another and out of the other, so a bit of it sticks out where it
  should not (a fender's edge standing up through a bonnet, a pillar overshooting the roof). A part only set
  into another (a badge in its panel, a column in the dash) is not reported: what is left of it outside stays
  one piece.
- "buried": a part almost wholly inside another, so a solid never shows it (it may be meant: a hidden stiffener;
  or it may say the other is far too thick, a fender that swallows the strut tower behind it).
Only what shows from outside is reported as poking: a shaft through a floor inside the car is hidden. A poke is
confirmed on its two parts alone at finer voxels: a thin part that only touches another is cut in two by coarse ones.
- "crosses-glass": a solid part passing through a pane (a pillar through a quarter window). What holds the pane's
  edge (a frame, a rail, the wall it is set in) is not reported; otherwise glass is left out of "pokes" and "buried".
- "open": a solid shape left open where it shows (an uncapped tube end, a lathe whose profile stops short of its
  axis): a solid, an export or a print shows into it.

tipping(...) asks the audit's question "is it held?" on the same voxels: a part standing with its weight off what it
stands on (the audit's `tips` warning).
"""

import math

from . import export, printing, scene as scene_mod

CELLS = 160          # voxels along the longest side: fine enough for a part a hundredth of the object across
POKE = 0.002        # the bit sticking out, as a share of the part: below this it is a voxel's rounding
TIP = 0.25          # above this it is not a tip sticking out but a part passing through (an axle through hubs)
BURIED = 0.95
FINE = 4             # a poke is confirmed on its two parts alone, at voxels this many times finer
FINE_CELLS = 400     # (but at most this many along the two parts' longest side)
OPEN = 0.25          # an open shell whose edge shows over this share of it has a hole you can see


def _volumes(g, n_cells, surfaces=None, h=None):
    """Per part index: its solid's voxels (a dict of bit columns, printing's grid) and its surface triangles. With
    `surfaces` ((closed, open) pieces, a few parts' own) and `h`, those alone, at that voxel size."""
    closed, open_ = surfaces or printing._surfaces(g, False)[:2]
    pts = [p for _, piece in closed + open_ for t in piece for p in t]
    if not pts:
        return None, {}, {}
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    h = h or max(hi[a] - lo[a] for a in range(3)) / n_cells or 1e-6
    grid = printing._Grid(lo, hi, h, 2)
    vox, tris = {}, {}
    for pid, piece in closed:
        inside = {}
        printing._fill(grid, piece, inside)
        if not printing._popcount(inside):   # too thin to fill: its surface stands for it
            printing._mark_surface(grid, piece, inside)
        for c, m in inside.items():
            vox.setdefault(pid, {})[c] = vox.setdefault(pid, {}).get(c, 0) | m
        tris.setdefault(pid, []).extend(piece)
    for pid, piece in open_:
        surf = {}
        printing._mark_surface(grid, piece, surf)
        for c, m in surf.items():
            vox.setdefault(pid, {})[c] = vox.setdefault(pid, {}).get(c, 0) | m
        tris.setdefault(pid, []).extend(piece)
    return grid, vox, tris


def solids(scene, cells=CELLS, grid=False):
    """(per part id: its solid as voxels, a dict of bit columns; the voxel's size in metres), for asking which
    parts really meet; with `grid`, the voxel lattice itself in place of its size (None when nothing is solid)."""
    lattice, vox, _ = _volumes(scene_mod.compile_scene(scene, solid=True), cells)
    if grid:
        return vox, lattice
    return vox, (lattice.h if lattice else 0.0)


def touch(a, b, reach=1):
    """Whether two parts' voxels meet or lie within `reach` voxels of each other."""
    if not a or not b:
        return False
    if len(b) < len(a):   # the same question either way round: walk the smaller
        a, b = b, a
    for (x, y), m in a.items():
        grow = m
        for i in range(1, reach + 1):
            grow |= m << i | m >> i
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if grow & b.get((x + dx, y + dy), 0):
                    return True
    return False


def _components(cols):
    from . import kit
    return kit._components(cols)


def _count(cols):
    return sum(bin(m).count("1") for m in cols.values())


def _overlap(a, b):
    n, cells = 0, []
    for c, m in a.items():
        both = m & b.get(c, 0)
        if both:
            k = bin(both).count("1")
            n += k
            cells.append((c, both, k))
    return n, cells


def _where(grid, cells):
    """The middle of an overlap, in the scene's frame (metres, Y up)."""
    tot = sum(k for _, _, k in cells) or 1
    x = sum((c[0] + 0.5) * k for c, _, k in cells) / tot
    y = sum((c[1] + 0.5) * k for c, _, k in cells) / tot
    z = sum((sum(i for i in range(both.bit_length()) if both >> i & 1) / k + 0.5) * k for _, both, k in cells) / tot
    p = [grid.origin[0] + x * grid.h, grid.origin[1] + y * grid.h, grid.origin[2] + z * grid.h]   # print frame, Z up
    return [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]


def report(result, most=20):
    """The fit in plain lines, what shows most first."""
    issues = result["issues"]
    if not issues:
        return "fit: nothing pokes through or hides (%d parts as solids)" % result["parts"]
    counts = {}
    for i in issues:
        counts[i["code"]] = counts.get(i["code"], 0) + 1
    lines = ["fit: %s, the most visible first (some may be meant: a part set through another by design)"
             % ", ".join("%d %s" % (n, c) for c, n in sorted(counts.items()))]
    lines += ["  %s: %s" % (i["code"], i["message"]) for i in issues[:most]]
    if len(issues) > most:
        lines.append("  ... and %d more (--json lists them all)" % (len(issues) - most))
    return "\n".join(lines)


_RIMS = {}


def _rim(cols):
    """A thin set's edge: its voxels with clearly fewer neighbours in the set than its most surrounded ones."""
    key = id(cols)
    if key not in _RIMS:
        count = {}
        for (x, y), m in cols.items():
            for z in range(m.bit_length()):
                if m >> z & 1:
                    count[(x, y, z)] = sum(cols.get((x + dx, y + dy), 0) >> (z + dz) & 1 if z + dz >= 0 else 0
                                           for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)) - 1
        most = max(count.values(), default=0)
        rim = {}
        for (x, y, z), n in count.items():
            if n < 0.75 * most:
                rim[(x, y)] = rim.get((x, y), 0) | 1 << z
        _RIMS.clear()
        _RIMS[key] = (cols, rim)
    return _RIMS[key][1]


def _stray(small, big, alone, shows=None, through=False):
    """What of `small` stands out on the far side of `big` once `big` is taken out of it: (stray pieces, their
    voxels) or None. `alone` is how many pieces `small` is in by itself (a thin skin may be); `shows` counts what of
    a piece is seen from outside (None: all of it). A part that passes through by design (an axle through hubs)
    leaves most of itself on both sides: that is a poke only when `through` (nothing passes through glass)."""
    n_small = _count(small)
    out = {c: m & ~big.get(c, 0) for c, m in small.items()}
    comps = sorted(_components({c: m for c, m in out.items() if m}), key=lambda c: -_count(c))
    if len(comps) <= alone:
        return None
    seen = shows or _count
    stray = [c for c in comps[alone:] if _count(c) >= POKE * n_small and _count(c) >= 2 and seen(c) >= 2]
    if not stray:
        return None
    k = sum(_count(c) for c in stray)
    if not through and (_count(comps[0]) < 0.5 * n_small or k > TIP * n_small):
        return None   # a part that passes through by design (an axle, a spoke)
    return stray, k


def check(scene, cells=CELLS):
    """The fit of the construct's solids: {"issues": [...], "parts": n}, the worst first."""
    g = scene_mod.compile_scene(scene, solid=True)
    closed, open_ = printing._surfaces(g, False)[:2]
    grid, vox, tris = _volumes(g, cells, (closed, open_))
    issues = []
    if grid is None:
        return {"issues": issues, "parts": 0}
    glassy = {pid for pid in vox if export.is_glass_name(pid)}
    size = {pid: _count(v) for pid, v in vox.items()}
    box = {}
    for pid, v in vox.items():
        xs = [c[0] for c in v]
        ys = [c[1] for c in v]
        zs = [i for m in v.values() for i in (m.bit_length() - 1, (m & -m).bit_length() - 1)]
        box[pid] = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    ids = sorted(vox, key=lambda p: -size[p])
    split = {}

    def pieces_of(pid):
        if pid not in split:
            split[pid] = len(_components(vox[pid]))
        return split[pid]
    # the outside: what is not inside the whole object once its enclosed hollows are filled (a tip that pokes into a
    # closed cabin or an engine bay is hidden; one that pokes out into the air shows)
    solid = {}
    for v in vox.values():
        for c, m in v.items():
            solid[c] = solid.get(c, 0) | m
    printing._fill_voids(solid, grid.n)

    def shows(cols):
        n = 0
        for (x, y), m in cols.items():
            around = (solid.get((x + 1, y), 0) & solid.get((x - 1, y), 0) & solid.get((x, y + 1), 0)
                      & solid.get((x, y - 1), 0) & (solid.get((x, y), 0) << 1) & (solid.get((x, y), 0) >> 1))
            n += bin(m & ~around).count("1")
        return n

    def confirmed(small, big, through):
        """The same question on the two parts alone, with voxels FINE times finer: a thin part that only touches
        another (a 2 cm diffuser on a strake, at 3 cm voxels) cuts it in two at the coarse size, not at the fine.
        A part whose finer voxels fall apart by themselves (an open surface, marked voxel by voxel) cannot say: the
        coarse answer stands."""
        pair = ([q for q in closed if q[0] in (small, big)], [q for q in open_ if q[0] in (small, big)])
        pts = [x for _, piece in pair[0] + pair[1] for t in piece for x in t]
        extent = max(max(x[a] for x in pts) - min(x[a] for x in pts) for a in range(3))
        _, fv, _ = _volumes(None, 0, pair, max(grid.h / FINE, extent / FINE_CELLS))
        if small not in fv or big not in fv:
            return True
        alone = len(_components(fv[small]))
        if alone > pieces_of(small):
            return True
        return _stray(fv[small], fv[big], alone, through=through) is not None
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (a in glassy and b in glassy) or not size[b]:
                continue
            A, B = box[a], box[b]
            if A[0] > B[1] or B[0] > A[1] or A[2] > B[3] or B[2] > A[3] or A[4] > B[5] or B[4] > A[5]:
                continue
            n, cells_ = _overlap(vox[b], vox[a])   # b is the smaller
            if not n:
                continue
            if a in glassy or b in glassy:   # a solid part through a pane: the glass shows it standing through
                pane, part = (a, b) if a in glassy else (b, a)
                if any(m & _rim(vox[pane]).get(c, 0) for c, m in vox[part].items()):
                    continue   # it holds the pane's edge (a frame, a rail, a wall the window is set in)
                got = _stray(vox[part], vox[pane], pieces_of(part), through=True)
                if got and confirmed(part, pane, True):
                    stray, k = got
                    at = _where(grid, [(cc, m, bin(m).count("1")) for c in stray for cc, m in c.items()])
                    issues.append({"code": "crosses-glass", "parts": [part, pane], "share": round(k / size[part], 4),
                                   "at": at, "shows": k,
                                   "message": "%s passes through the glass %s around %s m: a solid shows it standing "
                                              "through the pane. Stop it at the glass, or split the pane around it (a "
                                              "pillar between two panes)" % (part, pane, at)})
                continue
            share = n / size[b]
            where = _where(grid, cells_)
            if share >= BURIED:
                issues.append({"code": "buried", "parts": [b, a], "share": round(share, 3), "at": where,
                               "message": "%s is %d%% inside %s: a solid never shows it (fine if it is meant to be "
                                          "hidden)" % (b, round(share * 100), a)})
            else:   # does b come out the far side of a? then what is left of b outside a falls into pieces
                for small, big in ((b, a), (a, b)):
                    got = _stray(vox[small], vox[big], pieces_of(small), shows)
                    if not got or not confirmed(small, big, False):
                        continue
                    stray, k = got
                    at = _where(grid, [(cc, m, bin(m).count("1")) for c in stray for cc, m in c.items()])
                    issues.append({"code": "pokes", "parts": [small, big], "share": round(k / size[small], 4), "at": at,
                                   "shows": sum(shows(c) for c in stray),
                                   "message": "%s pokes through %s: %d%% of %s sticks out on the far side, around %s m. "
                                              "Trim it to end at %s's face" % (small, big, max(1, round(k / size[small] * 100)),
                                                                             small, at, big)})
                    break
    issues += _open_shells(scene, grid, vox, open_)
    order = {"crosses-glass": 0, "pokes": 0, "open": 1, "buried": 2}
    issues.sort(key=lambda x: (order[x["code"]], -x.get("shows", 0), -x["share"]))   # what shows most first
    return {"issues": issues, "parts": len(vox)}


OPEN_SHAPES = ("tube", "cylinder", "cone", "lathe", "extrude", "loft", "sphere", "torus")


def _open_shells(scene, grid, vox, open_):
    """Solid shapes left open where it shows: an uncapped tube end, a lathe whose profile stops short of its axis.
    The light forgives the hole; a solid, an export or a print shows into it (or makes a skin of it)."""
    info = {p["id"]: p for p in scene["parts"]}
    edges_of = {}
    for pid, piece in open_:
        p = info.get(pid)
        if not p or p["role"] not in ("mass", "structure", "identity") or export.is_glass_name(pid) \
                or p["shape"]["type"] not in OPEN_SHAPES:
            continue
        edges = {}
        for t in piece:
            ks = [printing._key(x) for x in t]
            for i, j in ((0, 1), (1, 2), (2, 0)):
                e = (ks[i], ks[j]) if ks[i] < ks[j] else (ks[j], ks[i])
                edges[e] = edges.get(e, 0) + 1
        edges_of.setdefault(pid, []).extend(e for e, n in edges.items() if n == 1)
    owners = {}
    floor = min(((m & -m).bit_length() - 1 for v in vox.values() for m in v.values()), default=0) + 1
    if edges_of:
        for q, v in vox.items():
            for c, m in v.items():
                owners.setdefault(c, []).append((q, m))
    out = []
    for pid, rim in sorted(edges_of.items()):
        total = shown = 0.0
        at = [0.0, 0.0, 0.0]
        for a, b in rim:
            length = math.dist(a, b)
            total += length
            c = grid.to_cell([(a[k] + b[k]) / 2 for k in range(3)])
            x, y, z = int(c[0]), int(c[1]), int(c[2])
            covered = z <= floor or any(q != pid and (m >> max(0, z - 1)) & 0b111   # on the ground: its underside
                          for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q, m in owners.get((x + dx, y + dy), ()))
            if not covered:   # nothing of another part where its edge is: the hole shows
                shown += length
                at = [at[k] + (a[k] + b[k]) / 2 * length for k in range(3)]
        if not total or shown < OPEN * total or shown < 3 * grid.h:
            continue
        at = [round(at[0] / shown, 3), round(at[2] / shown, 3), round(-at[1] / shown, 3)]
        how = {"tube": "set \"caps\": true", "cylinder": "set \"caps\": true", "cone": "set \"caps\": true",
               "lathe": "start and end its profile on its axis (x 0)", "extrude": "keep its caps (\"caps\": true)"}.get(
                   info[pid]["shape"]["type"], "close its surface")
        out.append({"code": "open", "parts": [pid], "share": round(shown / total, 3), "at": at, "shows": 0,
                    "message": "%s is an open shell: %.3g m of its edge shows a hole, around %s m. A solid, an export or "
                               "a print shows into it: %s, or end it inside the part it meets" % (pid, shown, at, how)})
    return out


# ---------------------------------------------------------------------------- is it held?
#
# A part standing on something stays up while its weight is over what it stands on: over the outline, seen from above,
# of everywhere it touches. A back board standing on a rail along its bottom edge and leaning back, with nothing behind
# it, has its weight off that line and falls over. A part fixed into the side of another or hung from it does not
# stand: most of where it touches is not on top of what holds it, and a joint holds what a resting edge does not.

LINE = 3.0    # a contact this many voxels wide or less is a line (an edge standing on something), or a point
SLACK = 1.5   # voxels the weight may sit off the contact before it counts: the voxels' own rounding


def _centre(cols):
    """The middle of a voxel set (voxel units, the print frame: bit k is the height)."""
    n = sx = sy = sz = 0.0
    for (x, y), m in cols.items():
        for a, b in printing._runs(m):
            k = b - a + 1
            n += k
            sx, sy, sz = sx + (x + 0.5) * k, sy + (y + 0.5) * k, sz + (a + b + 1) / 2.0 * k
    return [sx / n, sy / n, sz / n]


def _grow(cols, reach):
    """A voxel set grown by `reach` voxels each way (a cube around every voxel)."""
    out = cols
    for axis in (0, 1):
        grown = {}
        for (x, y), m in out.items():
            for d in range(-reach, reach + 1):
                c = (x + d, y) if axis == 0 else (x, y + d)
                grown[c] = grown.get(c, 0) | m
        out = grown
    for c, m in out.items():
        g = m
        for i in range(1, reach + 1):
            g |= m << i | m >> i
        out[c] = g
    return out


def _hull(pts):
    """The convex hull of points in the plane, counter-clockwise."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _area(hull):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(hull, hull[1:] + hull[:1]))) / 2


def _outside(p, hull):
    """How far point p lies outside a convex polygon (0 inside), and the polygon's nearest point."""
    if len(hull) >= 3 and all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0
                              for a, b in zip(hull, hull[1:] + hull[:1])):
        return 0.0, p
    best = (math.inf, p)
    for a, b in zip(hull, hull[1:] + hull[:1]) if len(hull) > 1 else [(hull[0], hull[0])]:
        ab = (b[0] - a[0], b[1] - a[1])
        d = ab[0] * ab[0] + ab[1] * ab[1]
        t = 0.0 if d == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / d))
        q = (a[0] + ab[0] * t, a[1] + ab[1] * t)
        best = min(best, (math.dist(p, q), q))
    return best


def _bodies(cols, reach):
    """A part's solid as the bodies it makes: its separate pieces, those that meet (within `reach`) taken as one
    (a thin tube voxelised in pieces is one tube; its copies are each their own)."""
    pieces = _components(cols)
    if len(pieces) < 2:
        return pieces
    joined = _components(_grow(cols, max(1, (reach + 1) // 2)))
    owner = {}
    for k, comp in enumerate(joined):
        for c, m in comp.items():
            owner.setdefault(c, []).append((k, m))
    out = {}
    for piece in pieces:
        c, m = next(iter(piece.items()))
        k = next(k for k, mm in owner[c] if mm & m)
        body = out.setdefault(k, {})
        for c, m in piece.items():
            body[c] = body.get(c, 0) | m
    return [out[k] for k in sorted(out)]


def tipping(vox, grid, holders, reach=1, ground=0, sections=None):
    """The parts in `holders` ({part id: the ids of the parts it touches}) that stand with their weight off what they
    stand on, each body on its own (copies apart): [{"part", "by" (what it touches), "kind" (line, point or area: what
    it stands on, seen from above), "span" (that contact's length, metres), "lever" (metres from its weight to the
    contact), "toward" (front, back, left or right: where its weight lies), "at" (the contact's middle, the scene's
    frame)}]. `reach` is how near counts as touching, in voxels; `ground` the lowest layer, which a body's voxels at most
    a layer above stand on; `sections` a rod's thickness by part id, in metres."""
    out, grown = [], {}
    floor = (1 << (ground + 2)) - 1
    for pid in sorted(holders):
        if pid not in vox:
            continue
        bodies = _bodies(vox[pid], reach)
        mates = [q for q in sorted(holders[pid]) if q in vox and q != pid]
        for q in mates:
            if q not in grown:
                grown[q] = _grow(vox[q], reach)
        for body in bodies:
            if _count(body) < 8:
                continue
            contact, under, by = {}, {}, []
            for q in mates:
                hit = False
                for c, m in body.items():
                    m &= grown[q].get(c, 0)
                    if m:
                        hit = True
                        contact[c] = contact.get(c, 0) | m
                        # what it stands on lies under it: its own voxels or the few layers above them
                        lift = 0
                        for i in range(1, reach + 2):
                            lift |= vox[q].get(c, 0) << i
                        if m & lift:
                            under[c] = under.get(c, 0) | (m & lift)
                if hit:
                    by.append(q)
            low = {c: m & floor for c, m in body.items() if m & floor}
            if low:
                by.append("the ground")
                for c, m in low.items():
                    contact[c] = contact.get(c, 0) | m
                    under[c] = under.get(c, 0) | m
            if not contact:
                continue   # touching nothing is another check's
            if _count(under) < 0.5 * _count(contact):
                continue   # fixed into the side of something or hung from it: a fixing, not something it stands on
            weight = _centre(body)[:2]
            hull = _hull([(x + i, y + j) for (x, y) in contact for i in (0, 1) for j in (0, 1)])
            off, foot = _outside(weight, hull)
            if off <= SLACK:
                continue   # its weight is over what it stands on
            span = max(math.dist(a, b) for a in hull for b in hull)
            if (sections or {}).get(pid) is not None and span * grid.h <= sections[pid] + SLACK * grid.h:
                continue   # a rod's end, joined across its whole section (a bar welded on, a strut)
            at = [grid.origin[k] + v * grid.h for k, v in enumerate(_centre(contact))]
            r = (weight[0] - foot[0], weight[1] - foot[1])
            toward = max((("right", r[0]), ("left", -r[0]), ("back", r[1]), ("front", -r[1])), key=lambda e: e[1])[0]
            kind = "point" if span <= LINE else "line" if _area(hull) / span <= LINE else "area"
            out.append({"part": pid, "by": by, "kind": kind, "lever": round(off * grid.h, 4), "toward": toward,
                        "span": round(span * grid.h, 4), "at": [round(at[0], 3), round(at[2], 3), round(-at[1], 3)]})
    return out
