"""Kits: a construct as a model kit to print, glue and paint, as a Revell or Tamiya kit is.

The construct already knows what a kit needs: its parts by name, the order they go together in (its
build stages), its joints, and, from a material map, its colours. A kit is made from them:
  - each part becomes pieces of its own, at the kit's scale, in voxels like a print (`printing`):
    closed parts solid, open surfaces and thin parts thickened to the wall; where two parts overlap,
    the later one is trimmed, so pieces meet flush and fit when glued; mirrored copies (four wheels)
    are separate pieces; a bit too small to print is merged into the piece it touches;
  - the parts drawn only in lines (seams, grilles, tracery) are engraved into the pieces they lie on,
    as a kit's panel lines;
  - each piece lies on its largest flat face, and the pieces are packed onto print plates the size of a
    bed and numbered in the order they are glued;
  - the booklet: the plates with their numbers, then the steps (the construct's stages, a few pieces
    at a time, each glued to the piece it touches most), a picture for each, and a painting guide;
    glass is a clear piece.

A kit is checked like a construct: `check` names pieces too small to handle, steps that attach a piece
to nothing built yet, pieces too big for the bed, and too many pieces. A plan (`kit.json`) records what a
critic decided: parts to merge into one piece, small parts to keep apart, parts that are clear, a title.

Python standard library only.
"""

import html
import fnmatch
import io
import json
import math
import zipfile
from pathlib import Path

from . import export, printing, product, scene as scene_mod

SCALE = 24                 # 1:24, a common scale for car kits
DETAIL_MM = 0.35           # one voxel
WALL_MM = 0.8
MIN_PIECE_MM = 2.0         # a piece smaller than this on every side is merged into what it touches
MIN_VOLUME_MM3 = 4.0
BED_MM = (250.0, 210.0, 220.0)
GAP_MM = 4.0               # between pieces on a plate
STEP_MOST = 6              # pieces in one step, at most
MANY_PIECES = 160
GLASS = ("glass", "glazing", "window", "windscreen", "windshield", "visor", "canopy", "lens")
SLIVER_MM = 1.5          # thinner than this, a small piece is a chip and a long one breaks
PLAN_KEYS = {"title", "merge", "keep", "clear", "opaque", "order", "notes"}


CRITIC = """You are an experienced designer of plastic model kits (Revell, Tamiya), reviewing a kit that Construct
made from a construct, before anyone prints it. You see kit.json (every piece: number, name, the construct parts
in it, size in mm, stage, paint, what it is glued to; the steps; the plates; the machine checks) and the booklet's
pictures (img/step-N.png: what is built so far in grey, the step's new pieces in pink; img/complete.png).

Judge it as a kit a careful hobbyist would build:
- pieces: too small or thin to handle or print (under about 2 mm, or a sliver), pieces that a real kit would
  mould as one (a row of slats, a bezel and its lamp), pieces a real kit keeps apart (wheels, mirrors, glass,
  bumpers, anything painted a different colour from what it is glued to);
- steps: whether each step is something you could do with glue and tweezers, sub-assemblies (wheels, the
  interior) built apart, nothing glued in a place that later pieces cover or block;
- paint: pieces that would need masking because they mix two paints;
- count: a 1:24 car of about 20 cm is usually 120 to 190 pieces (Revell's 1:24 Land Rover Series III: 184).

Answer with JSON only:
{"verdict": "one sentence", "findings": [{"issue": "...", "pieces": [numbers], "fix": "..."}],
 "plan": {"merge": [["part id or pattern", ...], ...], "keep": ["part id or pattern", ...],
          "clear": ["part id or pattern", ...]}}
Use only part ids that appear in kit.json (pieces[].parts); patterns may use * (e.g. "slat-*"). A merge group
becomes one piece; keep exempts small parts from being merged away; clear marks clear plastic. Change only what
your findings justify."""


class KitError(ValueError):
    """A kit that cannot be made: a bad plan, a scene with nothing to print, a scale out of range."""


# ---------------------------------------------------------------------------- voxel sets (column bitsets)

def _count(cols):
    return sum(bin(m).count("1") for m in cols.values())


def _bbox(cols):
    ks = [(m & -m).bit_length() - 1 for m in cols.values()] + [m.bit_length() - 1 for m in cols.values()]
    return (min(c[0] for c in cols), max(c[0] for c in cols), min(c[1] for c in cols), max(c[1] for c in cols),
            min(ks), max(ks))


def _and_not(a, b):
    out = {}
    for c, m in a.items():
        m &= ~b.get(c, 0)
        if m:
            out[c] = m
    return out


def _or_into(a, b):
    for c, m in b.items():
        a[c] = a.get(c, 0) | m


def _components(cols):
    """The separate solids of a voxel set (joined by faces), each as its own set, largest first."""
    runs = {c: printing._runs(m) for c, m in cols.items() if m}
    seen, out = set(), []
    for c, rs in runs.items():
        for r in rs:
            if (c, r) in seen:
                continue
            seen.add((c, r))
            stack, part = [(c, r)], {}
            while stack:
                (i, j), (k0, k1) = stack.pop()
                part[(i, j)] = part.get((i, j), 0) | (((1 << (k1 - k0 + 1)) - 1) << k0)
                for n in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    for r2 in runs.get(n, ()):
                        if r2[0] <= k1 and r2[1] >= k0 and (n, r2) not in seen:
                            seen.add((n, r2))
                            stack.append((n, r2))
            out.append(part)
    return sorted(out, key=_count, reverse=True)


def _contact(a, b):
    """How many voxel faces two sets share."""
    if len(a) > len(b):
        a, b = b, a
    n = 0
    for (i, j), m in a.items():
        here = b.get((i, j), 0)
        n += bin(m & (here << 1)).count("1") + bin(m & (here >> 1)).count("1")
        for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            n += bin(m & b.get(c, 0)).count("1")
    return n


# ---------------------------------------------------------------------------- the plan

def load_plan(plan):
    """A kit plan: {"title", "merge": [[part ids or patterns, ...], ...], "keep": [...], "clear": [...], "notes"}."""
    if plan is None:
        return {}
    if isinstance(plan, (str, Path)):
        try:
            doc = json.loads(Path(plan).read_text(encoding="utf-8"))
        except OSError as exc:
            raise KitError("cannot read the plan %s: %s" % (plan, exc.strerror or exc))
        except ValueError as exc:
            raise KitError("the plan %s is not JSON: %s" % (plan, exc))
    else:
        doc = plan
    if not isinstance(doc, dict) or not set(doc) <= PLAN_KEYS:
        raise KitError("a kit plan is an object with %s" % ", ".join(sorted(PLAN_KEYS)))
    for key in ("merge", "keep", "clear", "opaque", "order"):
        if key in doc and not isinstance(doc[key], list):
            raise KitError("plan.%s: a list" % key)
    if not all(isinstance(g, list) and g and all(isinstance(x, str) for x in g) for g in doc.get("merge", [])):
        raise KitError("plan.merge: a list of groups, each a list of part ids or patterns")
    if not all(isinstance(g, dict) and isinstance(g.get("name"), str) and isinstance(g.get("parts"), list)
               for g in doc.get("order", [])):
        raise KitError('plan.order: a list of sub-assemblies, each {"name": "...", "parts": [ids or patterns]}')
    return doc


def _matches(pid, patterns):
    return any(fnmatch.fnmatchcase(pid, p) for p in patterns)


# ---------------------------------------------------------------------------- making the kit

def make(scene, scale=SCALE, size=None, detail=DETAIL_MM, wall=WALL_MM, plan=None, materials=None, bed=BED_MM):
    """The kit of `scene`: {"title", "scale", "pieces": [...], "steps": [...], "plates": [...], "report"}.
    Each piece: number, name, parts, stage, clear, paint, size_mm, mesh (vertices mm, triangles, lying on
    the bed), cols (voxels where it sits in the model)."""
    plan = load_plan(plan)
    if size is None and not (isinstance(scale, (int, float)) and scale > 0):
        raise KitError("scale: a positive N, for 1:N")
    if size is not None and not size > 0:
        raise KitError("size: a positive number of millimetres")
    if not (detail > 0 and wall > 0) or len(bed) != 3 or not all(b > 0 for b in bed):
        raise KitError("detail, wall and the bed (WxDxH): positive numbers of millimetres")
    rules = export._load_materials(materials)
    g = scene_mod.compile_scene(scene, solid=True)
    closed, open_, rods, rep = printing._surfaces(g, True)
    if not closed and not open_:
        raise KitError("nothing to make a kit of: the construct has no surfaces")
    pts = [p for _, piece in closed + open_ for t in piece for p in t]
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    longest = max(hi[a] - lo[a] for a in range(3))
    mm_per_m = (size / longest) if size else 1000.0 / scale
    if longest * mm_per_m / detail > printing.MAX_CELLS:
        raise KitError("too fine: %.0f voxels along the longest side (at most %d); use a coarser detail or a "
                       "smaller kit" % (longest * mm_per_m / detail, printing.MAX_CELLS))
    h = detail / mm_per_m
    r = max(1, int(math.ceil(wall / detail / 2.0 - 0.25)))
    grid = printing._Grid(lo, hi, h, r + 3)
    info = {p["id"]: p for p in scene["parts"]}

    # each part's voxels
    vox = {}
    for pid, piece in closed:
        inside, surface = {}, {}
        printing._fill(grid, piece, inside)
        printing._mark_surface(grid, piece, surface)
        if _count(inside) >= _count(surface):
            _or_into(vox.setdefault(pid, {}), inside)
        else:
            _or_into(vox.setdefault(pid, {}), printing._dilate(surface, r, grid.n))
    for pid, piece in open_:
        shell = {}
        printing._mark_surface(grid, piece, shell)
        _or_into(vox.setdefault(pid, {}), printing._dilate(shell, r, grid.n))
    grooves = {}
    printing._mark_rods(grid, rods, grooves)

    # the plan's merges: those parts are one piece from the start
    groups, taken = [], set()
    for group in plan.get("merge", []):   # a part matched by two groups joins the first
        members = [pid for pid in vox if _matches(pid, group) and pid not in taken]
        if len(members) > 1:
            groups.append(members)
            taken.update(members)
    owner = {pid: pid for pid in vox}
    own_vox = {pid: dict(v) for pid, v in vox.items()}   # each part's own voxels, to name what a merge falls into
    for members in groups:
        head = max(members, key=lambda p: _count(vox[p]))
        for pid in members:
            if pid != head:
                _or_into(vox[head], vox.pop(pid))
                owner[pid] = head
    members_of = {}
    for pid, head in owner.items():
        members_of.setdefault(head, []).append(pid)

    # each part's paint, and whether it is clear plastic
    clear, opaque = plan.get("clear", []), plan.get("opaque", [])
    paint = {pid: _paint(pid, info[pid], rules) for pid in vox}
    is_clear = {pid: (paint[pid].get("finish") == "glass" or _matches(pid, clear)
                      or (any(w in pid.lower() for w in GLASS)
                          and not any(w in pid.lower() for w in export.NOT_GLASS_WORDS)))
                and not _matches(pid, opaque) for pid in vox}   # the plan's `opaque` overrides a glassy name

    # trimmed in build order: an earlier, larger part keeps what two parts share, and clear parts yield to the
    # rest (a roof stays whole where it meets the glass)
    order = sorted(vox, key=lambda p: (is_clear[p], min(info[m]["stage"] for m in members_of[p]), -_count(vox[p])))
    taken, pieces = {}, []
    for pid in order:
        mine = _and_not(vox[pid], taken)
        _or_into(taken, mine)
        comps = _components(mine)
        names = []
        for comp in comps:   # a merge that falls apart: each bit named for the part it mostly is
            mem = members_of[pid]
            names.append(pid if len(mem) == 1 else max(mem, key=lambda m: sum(
                bin(mm & own_vox[m].get(c, 0)).count("1") for c, mm in comp.items())))
        for k, comp in enumerate(comps):
            same = names.count(names[k])
            nth = names[:k + 1].count(names[k])
            pieces.append({"name": names[k] if same == 1 else "%s (%d of %d)" % (names[k], nth, same),
                           "parts": sorted(members_of[pid]), "head": pid, "paint": paint[pid], "clear": is_clear[pid],
                           "stage": info[pid]["stage"], "cols": comp})   # the head's: its largest member

    # bits too small to print, merged into the piece they touch most
    keep = plan.get("keep", [])
    vol_min = MIN_VOLUME_MM3 / detail ** 3
    side_min = MIN_PIECE_MM / detail
    merged_away, dropped = [], []
    while True:
        small = None
        for p in pieces:
            if _matches(p["head"], keep):
                continue
            b = _bbox(p["cols"])
            if max(b[1] - b[0], b[3] - b[2], b[5] - b[4]) + 1 < side_min or _count(p["cols"]) < vol_min:
                small = p
                break
        if small is None:
            break
        pieces.remove(small)
        # into what a kit would mould it with: never across clear and opaque plastic, a piece of its own part or
        # of its own paint first, then the one it touches most
        def fit(q):   # a fragment of a part (or a merge group) goes back to its own piece if it is near
            if q["clear"] != small["clear"]:
                return (0, 0, 0)
            if q["head"] == small["head"]:
                near = _near(small["cols"], q["cols"], grid.n, 4)
                if near:
                    return (1, 1, near)
            touch = _contact(small["cols"], q["cols"])
            return (0, q["paint"]["name"] == small["paint"]["name"], touch) if touch else (0, 0, 0)
        best = max(pieces, key=fit, default=None)
        if best is None or fit(best)[2] == 0:
            dropped.append(small["name"])
            continue
        _or_into(best["cols"], small["cols"])
        best["parts"] = sorted(set(best["parts"]) | set(small["parts"]))
        merged_away.append((small["name"], best["name"]))

    # panel lines: engraved where solid lies behind them
    if grooves:
        grooves = printing._dilate(grooves, 1, grid.n)
        for p in pieces:
            backed = printing._dilate(printing._erode(p["cols"], 1, grid.n), 1, grid.n)
            for c, m in list(p["cols"].items()):
                cut = m & grooves.get(c, 0) & backed.get(c, 0)
                if cut:
                    p["cols"][c] = m & ~cut
            p["cols"] = printing._drop_specks({c: m for c, m in p["cols"].items() if m}, 8)

    pieces = [p for p in pieces if p["cols"]]
    if len(pieces) == 0:
        raise KitError("nothing left to print")
    groups = plan.get("order", [])
    for p in pieces:   # the plan's sub-assemblies, in order; what none names comes after
        p["group"] = next((i for i, g in enumerate(groups) if any(_matches(m, g["parts"]) for m in p["parts"])),
                          len(groups))
        p["group_name"] = groups[p["group"]]["name"] if p["group"] < len(groups) else None

    _order(pieces, grid.n)
    _line_art(scene, pieces, grid)
    for p in pieces:
        p["mesh"], p["size_mm"], p["down"] = _piece_mesh(p["cols"], detail)
    plates = _pack(pieces, bed)
    kit = {"title": plan.get("title") or "%s, a kit" % scene["title"], "construct": scene["title"],
           "scale": "1:%s" % printing._ratio(1000.0 / mm_per_m), "detail_mm": detail, "pieces": pieces,
           "plates": plates, "steps": _steps(pieces), "bed_mm": list(bed),
           "merged": merged_away, "dropped": dropped, "plan": plan,
           "size_mm": [round((hi[a] - lo[a]) * mm_per_m, 1) for a in (0, 1, 2)]}
    kit["report"] = check(kit)
    return kit


def _line_art(scene, pieces, grid):
    """Each piece's lines, as the hologram draws them (metres, the print frame, Z up): its own parts', and those
    of the parts drawn only in lines that lie on it (a seam on a door is the door's)."""
    holo = scene_mod.compile_scene(scene)
    st, ln, parts = holo["styles"], holo["lines"], holo["parts"]
    art = {}
    for i in range(0, len(ln), 9):
        part = parts[int(st[int(ln[i + 6])][6])]
        if part.get("floating"):
            continue
        art.setdefault(part["id"], []).append(((ln[i], -ln[i + 2], ln[i + 1]), (ln[i + 3], -ln[i + 5], ln[i + 4])))
    owner = {m: p for p in pieces for m in p["parts"]}
    for pid, segs in art.items():
        if pid in owner:
            continue
        a, b = segs[len(segs) // 2]
        cell = grid.to_cell([(a[k] + b[k]) / 2 for k in range(3)])
        i, j, k = (int(math.floor(x)) for x in cell)

        def near(p):
            return sum(bin(p["cols"].get((i + di, j + dj), 0) >> max(k - 3, 0) & 0x7F).count("1")
                       for di in range(-3, 4) for dj in range(-3, 4))
        best = max(pieces, key=near)
        if near(best):
            owner[pid] = best
    for p in pieces:
        p["art"] = []
    for pid, segs in art.items():
        if pid in owner:
            owner[pid]["art"].extend(segs)


def _paint(pid, part, rules):
    for r in rules:
        if _matches(pid, r["patterns"]):
            return {"name": r["name"], "color": "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in r["color"]),
                    "finish": r.get("finish")}
    c = part.get("look", {}).get("color")
    return {"name": part["role"], "color": c or "#c8c4cc", "finish": None}


NEAR = 2   # voxels: pieces this close can be glued


def _near(a, b, n, d=NEAR):
    """How much of `b` lies within `d` voxels of `a` (0: they cannot be glued)."""
    if _count(a) > _count(b):
        a, b = b, a
    grown = printing._dilate(a, d, n)
    return sum(bin(m & b.get(c, 0)).count("1") for c, m in grown.items())


def _order(pieces, n):
    """Numbers in gluing order. The largest piece of the first stage is the base; then, again and again, the
    piece of the earliest stage that touches what is built (the largest first); when none does, the largest
    left starts a sub-assembly of its own, as a kit's wheels are built apart. Each piece is glued to the
    built piece it touches most."""
    rank = lambda p: (p.get("group", 0), p["stage"], -_count(p["cols"]))
    left = sorted(pieces, key=rank)
    boxes = [_bbox(p["cols"]) for p in left]
    touch = {}
    for a in range(len(left)):
        for b in range(a + 1, len(left)):
            A, B = boxes[a], boxes[b]   # boxes apart by more than NEAR cannot touch
            if A[0] > B[1] + NEAR or B[0] > A[1] + NEAR or A[2] > B[3] + NEAR or B[2] > A[3] + NEAR \
                    or A[4] > B[5] + NEAR or B[4] > A[5] + NEAR:
                continue
            t = _near(left[a]["cols"], left[b]["cols"], n)
            if t:
                touch[(id(left[a]), id(left[b]))] = touch[(id(left[b]), id(left[a]))] = t
    placed, out = [], []
    while left:
        ready = [p for p in left if any((id(p), id(q)) in touch for q in placed)]
        if ready and min(map(rank, ready)) [:1] > rank(left[0])[:1]:
            ready = []   # the next sub-assembly in the plan starts before anything of a later one
        p = min(ready, key=rank) if ready else left[0]
        left.remove(p)
        onto = max(placed, key=lambda q: (q.get("group") == p.get("group") and (id(p), id(q)) in touch,
                                          touch.get((id(p), id(q)), 0)), default=None)   # its own assembly first
        p["onto"] = onto if onto is not None and (id(p), id(onto)) in touch else None
        p["touches"] = sum(1 for q in pieces if q is not p and (id(p), id(q)) in touch)
        placed.append(p)
        out.append(p)
    pieces[:] = out
    for k, p in enumerate(pieces, 1):
        p["number"] = k


def _steps(pieces):
    """The booklet's steps: the gluing order, a few pieces at a time, a new step where a stage or a
    sub-assembly begins."""
    steps, cur = [], None
    for p in pieces:
        if (cur is None or len(cur["pieces"]) >= STEP_MOST or p.get("group") != cur["group"]
                or (p.get("group_name") is None and (p["onto"] is None or p["stage"] != cur["stage"]))):
            cur = {"stage": p["stage"], "group": p.get("group"), "name": p.get("group_name"), "pieces": [], "glue": []}
            steps.append(cur)
        cur["pieces"].append(p["number"])
        cur["glue"].append((p["number"], p["onto"]["number"] if p["onto"] else None))
    for k, st in enumerate(steps, 1):
        st["number"] = k
    return steps


# a rotation that lays a piece on the face pointing `down` (its outward direction) onto the bed
LAY = {(0, 0, -1): lambda x, y, z: (x, y, z), (0, 0, 1): lambda x, y, z: (x, -y, -z),
       (-1, 0, 0): lambda x, y, z: (-z, y, x), (1, 0, 0): lambda x, y, z: (z, y, -x),
       (0, -1, 0): lambda x, y, z: (x, -z, y), (0, 1, 0): lambda x, y, z: (x, z, -y)}


def _piece_mesh(cols, detail):
    """A piece's surface, lying on its largest flat face, in mm, its lowest corner at the origin."""
    i0, i1, j0, j1, k0, k1 = _bbox(cols)
    area = {(0, 0, -1): sum(1 for m in cols.values() if m >> k0 & 1),
            (0, 0, 1): sum(1 for m in cols.values() if m >> k1 & 1),
            (-1, 0, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if i == i0),
            (1, 0, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if i == i1),
            (0, -1, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if j == j0),
            (0, 1, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if j == j1)}
    down = max(area, key=lambda d: (area[d], d == (0, 0, -1)))
    work = dict(cols)
    printing._manifold(work)
    verts, faces = printing._surface(work, None)
    verts = printing._smooth(verts, faces, steps=6)
    lay = LAY[down]
    verts = [lay(*(x * detail for x in p)) for p in verts]
    lo = [min(v[a] for v in verts) for a in range(3)]
    verts = [[v[a] - lo[a] for a in range(3)] for v in verts]
    size = [round(max(v[a] for v in verts), 2) for a in range(3)]
    return {"vertices": verts, "triangles": faces}, size, list(down)


def _pack(pieces, bed):
    """Pieces onto plates the size of the bed: rows (shelves), tallest first, GAP_MM apart."""
    w, d = bed[0] - 2 * GAP_MM, bed[1] - 2 * GAP_MM
    plates, current = [], None
    for p in sorted(pieces, key=lambda p: (-p["size_mm"][1], -p["size_mm"][0])):
        pw, pd = p["size_mm"][0], p["size_mm"][1]
        if pw > w and pd <= w and pw <= d:   # turn it a quarter to fit
            p["mesh"]["vertices"] = [[v[1], pw - v[0], v[2]] for v in p["mesh"]["vertices"]]
            pw, pd = pd, pw
            p["size_mm"] = [pw, pd, p["size_mm"][2]]
        if pw > w or pd > d or p["size_mm"][2] > bed[2]:
            p["too_big"] = True
            plates.append({"number": len(plates) + 1, "pieces": [(p["number"], GAP_MM, GAP_MM)]})
            continue
        placed = False
        for plate in ([current] if current else []):
            x, y, row = plate["cursor"]
            if x + pw <= w:
                plate["pieces"].append((p["number"], GAP_MM + x, GAP_MM + y))
                plate["cursor"] = (x + pw + GAP_MM, y, max(row, pd))
                placed = True
            elif y + row + GAP_MM + pd <= d:
                y += row + GAP_MM
                plate["pieces"].append((p["number"], GAP_MM, GAP_MM + y))
                plate["cursor"] = (pw + GAP_MM, y, pd)
                placed = True
        if not placed:
            current = {"number": len(plates) + 1, "pieces": [(p["number"], GAP_MM, GAP_MM)],
                       "cursor": (pw + GAP_MM, 0.0, pd)}
            plates.append(current)
    for plate in plates:
        plate.pop("cursor", None)
    return plates


# ---------------------------------------------------------------------------- the checks

def check(kit):
    """What a kit's critic would flag before anyone prints it: {"ok", "problems": [{code, piece, message}],
    "counts"}."""
    problems = []
    for p in kit["pieces"]:
        s = sorted(p["size_mm"])
        if s[-1] < MIN_PIECE_MM:
            problems.append({"code": "tiny", "piece": p["number"],
                             "message": "%d (%s) is %.1f mm across: too small to handle; merge it (plan.merge)"
                                        % (p["number"], p["name"], s[-1])})
        if s[0] < SLIVER_MM and MIN_PIECE_MM <= s[-1] < 6.0:
            problems.append({"code": "sliver", "piece": p["number"],
                             "message": "%d (%s) is a %.1f mm sliver: merge it into what it belongs to (plan.merge)"
                                        % (p["number"], p["name"], s[0])})
        elif s[0] < SLIVER_MM and s[-1] >= 60.0:
            problems.append({"code": "fragile", "piece": p["number"],
                             "message": "%d (%s) is %.1f mm thick and %.0f mm long: it will break; merge it into a "
                                        "thicker piece" % (p["number"], p["name"], s[0], s[-1])})
        if p.get("too_big"):
            problems.append({"code": "too-big", "piece": p["number"],
                             "message": "%d (%s) is %s mm: bigger than the bed" % (
                                 p["number"], p["name"], " x ".join("%g" % x for x in p["size_mm"]))})
        if not p.get("touches") and len(kit["pieces"]) > 1:
            problems.append({"code": "floats", "piece": p["number"],
                             "message": "%d (%s) touches no other piece: it has nothing to be glued to; merge it "
                                        "into what it belongs to (plan.merge)" % (p["number"], p["name"])})
    split = {}
    for p in kit["pieces"]:   # "body (1 of 3)": a merge whose parts do not touch came out in pieces
        if " of " in p["name"] and p["name"].endswith(")") and len(p["parts"]) > 1:   # a merge, not a part's copies
            split.setdefault(p["name"].rsplit(" (", 1)[0], []).append(p["number"])
    for name, nums in sorted(split.items()):
        problems.append({"code": "split", "piece": nums[0],
                         "message": "%s came out in %d pieces (%s): its parts do not touch; split the merge or bridge "
                                    "it" % (name, len(nums), ", ".join(str(n) for n in nums))})
    if len(kit["pieces"]) > MANY_PIECES:
        problems.append({"code": "many-pieces", "piece": None,
                         "message": "%d pieces: more than a kit this size usually has (%d); merge the small "
                                    "details into their parents" % (len(kit["pieces"]), MANY_PIECES)})
    return {"ok": not problems, "problems": problems,
            "counts": {"pieces": len(kit["pieces"]), "plates": len(kit["plates"]), "steps": len(kit["steps"]),
                       "clear": sum(1 for p in kit["pieces"] if p["clear"]),
                       "merged": len(kit["merged"]), "dropped": len(kit["dropped"])}}


# ---------------------------------------------------------------------------- pictures

# a view from one of four corners: a turn of the model about the vertical; (du, dv) are the grid directions
# that point right-and-towards the camera on screen
VIEWS = {0: ((1, 0), (0, 1)), 90: ((0, -1), (1, 0)), 180: ((-1, 0), (0, -1)), 270: ((0, 1), (-1, 0))}
FRONT = 90   # the construct's front (+Z) is the print frame's -Y: seen from the front three-quarter


def _drawing(kit, highlight, done, w=900, hgt=600):
    """A step drawn as the construct draws itself, in lines (SVG): what is built so far faint, the step's new
    pieces bright, each with its number in a callout, seen from the corner that faces them (the whole model
    from the front three-quarter)."""
    shown = [p for p in kit["pieces"] if (p["number"] in done or p["number"] in highlight) and p.get("art")]
    if not shown:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"></svg>' % (w, hgt)

    def centre(ps):
        pts = [q for p in ps for seg in p["art"] for q in seg]
        return [sum(q[a] for q in pts) / len(pts) for a in range(3)] if pts else [0.0, 0.0, 0.0]
    new = [p for p in shown if p["number"] in highlight]
    ca = centre([p for p in kit["pieces"] if p.get("art")])
    view = FRONT
    if new:
        cn = centre(new)
        off = (cn[0] - ca[0], cn[1] - ca[1])
        span = max(abs(q[a] - ca[a]) for p in kit["pieces"] for seg in p.get("art", []) for q in seg for a in (0, 1))
        if math.hypot(*off) > 0.12 * span:
            view = max(VIEWS, key=lambda v: (VIEWS[v][0][0] + VIEWS[v][1][0]) * off[0]
                       + (VIEWS[v][0][1] + VIEWS[v][1][1]) * off[1] + (1e-6 if v == FRONT else 0))
    (dui, duj), (dvi, dvj) = VIEWS[view]

    def proj(q):
        u, v = q[0] * dui + q[1] * duj, q[0] * dvi + q[1] * dvj
        return ((u - v) * 0.866, (u + v) * 0.35 - q[2] * 0.95)
    every = [proj(q) for p in shown for seg in p["art"] for q in seg]
    xs, ys = [q[0] for q in every], [q[1] for q in every]
    pad = 70
    sc = min((w - 2 * pad) / ((max(xs) - min(xs)) or 1), (hgt - 2 * pad) / ((max(ys) - min(ys)) or 1))
    ox = pad + ((w - 2 * pad) - (max(xs) - min(xs)) * sc) / 2 - min(xs) * sc
    oy = pad + ((hgt - 2 * pad) - (max(ys) - min(ys)) * sc) / 2 - min(ys) * sc
    xy = lambda q: (ox + proj(q)[0] * sc, oy + proj(q)[1] * sc)

    def path(segs):
        return "".join("M%.1f %.1fL%.1f %.1f" % (*xy(a), *xy(b)) for a, b in segs)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">' % (w, hgt),
           '<rect width="100%" height="100%" fill="#0f0c14"/>',
           '<path d="%s" stroke="#b7a4c8" stroke-opacity="0.32" stroke-width="0.6" fill="none"/>'
           % path([seg for p in shown if p["number"] not in highlight for seg in p["art"]]),
           '<path d="%s" stroke="#f0b8ef" stroke-opacity="0.95" stroke-width="1.1" fill="none"/>'
           % path([seg for p in new for seg in p["art"]])]
    mid = (w / 2, hgt / 2)
    for p in new:   # a callout: the piece's number, out from the model, a leader line to the piece
        c = centre([p])
        px, py = xy(c)
        dx, dy = px - mid[0], py - mid[1]
        d = math.hypot(dx, dy) or 1
        lx = min(max(px + dx / d * 46, 18), w - 18)
        ly = min(max(py + dy / d * 46, 18), hgt - 18)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#d16bd0" stroke-width="0.8"/>'
                   % (px, py, lx, ly))
        out.append('<circle cx="%.1f" cy="%.1f" r="13" fill="#17121f" stroke="#d16bd0" stroke-width="1.2"/>'
                   '<text x="%.1f" y="%.1f" fill="#f6eaff" font-size="12" font-family="monospace" '
                   'text-anchor="middle" dominant-baseline="central">%d</text>' % (lx, ly, lx, ly, p["number"]))
    out.append("</svg>")
    return "".join(out)


def _plate_map(kit, plate, w=640):
    """The plate seen from above: each piece's footprint and its number (SVG)."""
    bw, bd = kit["bed_mm"][0], kit["bed_mm"][1]
    sc = w / bw
    by = {p["number"]: p for p in kit["pieces"]}
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d">' % (w, int(bd * sc), w),
           '<rect width="100%" height="100%" fill="#17121f" stroke="#2b2338"/>']
    for num, x, y in plate["pieces"]:
        p = by[num]
        fw, fd = p["size_mm"][0] * sc, p["size_mm"][1] * sc
        fill = "#8fd3ff33" if p["clear"] else "#d16bd022"
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="#d16bd0" stroke-width="1"/>'
                   % (x * sc, y * sc, fw, fd, fill))
        out.append('<text x="%.1f" y="%.1f" fill="#eadcf3" font-size="%d" font-family="monospace" '
                   'text-anchor="middle" dominant-baseline="middle">%d</text>'
                   % (x * sc + fw / 2, y * sc + fd / 2, max(9, min(16, int(min(fw, fd) * 0.6))), num))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------- files

def _3mf(objects, title):
    """One 3MF with several objects (the pieces on a plate), each named, placed where it lies."""
    res, items = [], []
    for n, (name, mesh, dx, dy) in enumerate(objects, 1):
        v = "".join('<vertex x="%.3f" y="%.3f" z="%.3f"/>' % (p[0] + dx, p[1] + dy, p[2]) for p in mesh["vertices"])
        t = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % f for f in mesh["triangles"])
        res.append('<object id="%d" type="model" name="%s"><mesh><vertices>%s</vertices><triangles>%s</triangles>'
                   '</mesh></object>' % (n, html.escape(name, quote=True), v, t))
        items.append('<item objectid="%d"/>' % n)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Title">%s</metadata>'
             '<metadata name="Application">%s %s</metadata><resources>%s</resources><build>%s</build></model>\n'
             % (html.escape(title), product.TITLE, product.VERSION, "".join(res), "".join(items)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/'
                   'vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>\n')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>\n')
        z.writestr("3D/3dmodel.model", model)
    return buf.getvalue()


def write(kit, out):
    """The kit's files in `out`: plate-N.3mf, booklet.html with its pictures, kit.json (what a critic reads)."""
    out = Path(out)
    for old in (out / "img").glob("*") if (out / "img").is_dir() else ():   # no pictures from an earlier build
        old.unlink()
    (out / "img").mkdir(parents=True, exist_ok=True)
    by = {p["number"]: p for p in kit["pieces"]}
    files = []
    for plate in kit["plates"]:
        objs = [("%d %s" % (num, by[num]["name"]), by[num]["mesh"], x, y) for num, x, y in plate["pieces"]]
        path = out / ("plate-%d.3mf" % plate["number"])
        path.write_bytes(_3mf(objs, "%s, plate %d" % (kit["title"], plate["number"])))
        files.append(path)
        (out / "img" / ("plate-%d.svg" % plate["number"])).write_text(_plate_map(kit, plate), encoding="utf-8")
    done = set()
    for s in kit["steps"]:
        (out / "img" / ("step-%d.svg" % s["number"])).write_text(_drawing(kit, set(s["pieces"]), done), encoding="utf-8")
        done |= set(s["pieces"])
    (out / "img" / "complete.svg").write_text(_drawing(kit, set(), done), encoding="utf-8")
    (out / "booklet.html").write_text(booklet(kit), encoding="utf-8")
    (out / "kit.json").write_text(json.dumps(summary(kit), indent=1) + "\n", encoding="utf-8")
    return [str(f) for f in files] + [str(out / "booklet.html"), str(out / "kit.json")]


def summary(kit):
    """The kit without its geometry: what a critic reads, and what the tests check."""
    return {"title": kit["title"], "construct": kit["construct"], "scale": kit["scale"], "size_mm": kit["size_mm"],
            "report": kit["report"], "plan": kit["plan"], "merged": kit["merged"], "dropped": kit["dropped"],
            "pieces": [{"number": p["number"], "name": p["name"], "parts": p["parts"], "stage": p["stage"],
                        "size_mm": p["size_mm"], "clear": p["clear"], "paint": p["paint"]["name"],
                        "glued_to": p["onto"]["number"] if p["onto"] else None} for p in kit["pieces"]],
            "steps": [{"number": s["number"], "name": s.get("name"), "pieces": s["pieces"]} for s in kit["steps"]],
            "plates": [{"number": pl["number"], "pieces": [n for n, _, _ in pl["pieces"]]} for pl in kit["plates"]]}


def booklet(kit):
    """The instruction booklet (HTML): the parts, the plates, the steps, the paints."""
    by = {p["number"]: p for p in kit["pieces"]}
    e = html.escape
    paints = {}
    for p in kit["pieces"]:
        paints.setdefault((p["paint"]["name"], p["paint"]["color"]), []).append(p["number"])
    rows = []
    rows.append("<h1>%s</h1><p class=sub>A kit of the construct <b>%s</b> at %s: %d pieces on %d plates, %d steps. "
                "%s x %s x %s mm built.</p>" % (
                    e(kit["title"]), e(kit["construct"]), kit["scale"], len(kit["pieces"]), len(kit["plates"]),
                    len(kit["steps"]), *kit["size_mm"]))
    rows.append("<img class=hero src='img/complete.svg' alt='The finished model'>")
    rep = kit["report"]
    if rep["problems"]:
        rows.append("<div class=warn><b>Before you print:</b><ul>%s</ul></div>"
                    % "".join("<li>%s</li>" % e(p["message"]) for p in rep["problems"]))
    rows.append("<h2>Plates</h2><p>Print each plate as it is. The numbers are the order you glue the pieces in; "
                "blue pieces are clear (print them in a clear filament).</p>")
    for plate in kit["plates"]:
        rows.append("<h3>Plate %d</h3><img class=plate src='img/plate-%d.svg' alt='Plate %d'>"
                    % (plate["number"], plate["number"], plate["number"]))
    rows.append("<h2>Steps</h2>")
    for s in kit["steps"]:
        glue = []
        for num, onto in s["glue"]:
            p = by[num]
            what = "<b>%d</b> %s" % (num, e(p["name"]))
            glue.append("<li>%s%s%s</li>" % (what, " to <b>%d</b>" % onto if onto else
                                            (", the base" if num == 1 else ": it starts an assembly of its own"),
                                            " (clear)" if p["clear"] else ""))
        rows.append("<div class=step><h3>Step %d%s</h3><img src='img/step-%d.svg' alt='Step %d'><ul>%s</ul></div>"
                    % (s["number"], ": " + e(s["name"]) if s.get("name") else "", s["number"], s["number"], "".join(glue)))
    rows.append("<h2>Paints</h2><table><tr><th></th><th>Colour</th><th>Pieces</th></tr>%s</table>" % "".join(
        "<tr><td><span class=chip style='background:%s'></span></td><td>%s <code>%s</code></td><td>%s</td></tr>"
        % (c, e(n), c, ", ".join(str(x) for x in nums)) for (n, c), nums in sorted(paints.items())))
    css = ("body{margin:0;background:#0d0a12;color:#eadcf3;font:15px/1.5 -apple-system,sans-serif}main{max-width:900px;"
           "margin:0 auto;padding:32px 16px}h1{font-weight:500}.sub{color:#a796b8}img{max-width:100%;border:1px solid "
           "#2b2338;border-radius:8px;background:#120f18}.step{display:grid;grid-template-columns:1fr 1fr;gap:16px;"
           "align-items:center;border-top:1px solid #2b2338;padding:12px 0}@media(max-width:640px){.step{grid-template-"
           "columns:1fr}}table{border-collapse:collapse}td,th{border-bottom:1px solid #2b2338;padding:4px 8px;text-align:"
           "left}.chip{display:inline-block;width:18px;height:18px;border-radius:4px;border:1px solid #555}code{color:"
           "#8fd3ff}.warn{border:1px solid #d16bd0;border-radius:8px;padding:8px 14px;margin:12px 0}")
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style><main>%s</main>" % (e(kit["title"]), css, "".join(rows)))
