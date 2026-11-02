"""How a construct's solids fit: what the line art forgives and a solid, a print or a kit does not.

check(scene) -> {"issues": [...], "parts": n}. Each issue names its parts, says what is wrong and where (metres,
the scene's frame), so an agent or a person can fix them one by one and check again:

- "pokes": a part that goes in one side of another and out of the other, so a bit of it sticks out where it
  should not (a fender's edge standing up through a bonnet, a pillar overshooting the roof). A part only set
  into another (a badge in its panel, a column in the dash) is not reported: what is left of it outside stays
  one piece.
- "buried": a part almost wholly inside another, so a solid never shows it (it may be meant: a hidden stiffener;
  or it may say the other is far too thick, a fender that swallows the strut tower behind it).
Only what shows from outside is reported as poking: a shaft through a floor inside the car is hidden.

Glass is left out of "cuts" and "buried": a pane sits in its frame by design.
"""

import math

from . import export, printing, scene as scene_mod

CELLS = 160          # voxels along the longest side: fine enough for a part a hundredth of the object across
POKE = 0.002        # the bit sticking out, as a share of the part: below this it is a voxel's rounding
TIP = 0.25          # above this it is not a tip sticking out but a part passing through (an axle through hubs)
BURIED = 0.95


def _volumes(g, n_cells):
    """Per part index: its solid's voxels (a dict of bit columns, printing's grid) and its surface triangles."""
    closed, open_, _, _ = printing._surfaces(g, False)
    pts = [p for _, piece in closed + open_ for t in piece for p in t]
    if not pts:
        return None, {}, {}
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    h = max(hi[a] - lo[a] for a in range(3)) / n_cells or 1e-6
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


def solids(scene, cells=CELLS):
    """(per part id: its solid as voxels, a dict of bit columns; the voxel's size in metres), for asking which
    parts really meet."""
    grid, vox, _ = _volumes(scene_mod.compile_scene(scene, solid=True), cells)
    return vox, (grid.h if grid else 0.0)


def touch(a, b, reach=1):
    """Whether two parts' voxels meet or lie within `reach` voxels of each other."""
    if not a or not b:
        return False
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


def check(scene, cells=CELLS):
    """The fit of the construct's solids: {"issues": [...], "parts": n}, the worst first."""
    g = scene_mod.compile_scene(scene, solid=True)
    grid, vox, tris = _volumes(g, cells)
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
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a in glassy or b in glassy or not size[b]:
                continue
            A, B = box[a], box[b]
            if A[0] > B[1] or B[0] > A[1] or A[2] > B[3] or B[2] > A[3] or A[4] > B[5] or B[4] > A[5]:
                continue
            n, cells_ = _overlap(vox[b], vox[a])   # b is the smaller
            if not n:
                continue
            share = n / size[b]
            where = _where(grid, cells_)
            if share >= BURIED:
                issues.append({"code": "buried", "parts": [b, a], "share": round(share, 3), "at": where,
                               "message": "%s is %d%% inside %s: a solid never shows it (fine if it is meant to be "
                                          "hidden)" % (b, round(share * 100), a)})
            else:   # does b come out the far side of a? then what is left of b outside a falls into pieces
                for small, big in ((b, a), (a, b)):
                    out = {c: m & ~vox[big].get(c, 0) for c, m in vox[small].items()}
                    comps = sorted(_components({c: m for c, m in out.items() if m}), key=lambda c: -_count(c))
                    alone = pieces_of(small)   # a thin skin may already be in pieces by itself: only new pieces count
                    if len(comps) <= alone:
                        continue
                    stray = [c for c in comps[alone:] if _count(c) >= POKE * size[small] and _count(c) >= 2 and shows(c) >= 2]
                    if not stray or _count(comps[0]) < 0.5 * size[small] \
                            or sum(_count(c) for c in stray) > TIP * size[small]:
                        continue   # nothing out, or a part that passes through by design (an axle, a spoke)
                    k = sum(_count(c) for c in stray)
                    at = _where(grid, [(cc, m, bin(m).count("1")) for c in stray for cc, m in c.items()])
                    issues.append({"code": "pokes", "parts": [small, big], "share": round(k / size[small], 4), "at": at,
                                   "shows": sum(shows(c) for c in stray),
                                   "message": "%s pokes through %s: %d%% of %s sticks out on the far side, around %s m. "
                                              "Trim it to end at %s's face" % (small, big, max(1, round(k / size[small] * 100)),
                                                                             small, at, big)})
                    break
    order = {"pokes": 0, "buried": 1}
    issues.sort(key=lambda x: (order[x["code"]], -x.get("shows", 0), -x["share"]))   # what shows most first
    return {"issues": issues, "parts": len(vox)}
