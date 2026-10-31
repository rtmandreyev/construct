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
STEP_MOST = 24             # pieces in one step, at most (any number of one kind)
STEP_KINDS = 4             # kinds of piece in one step, at most
MANY_PIECES = 160
GLASS = ("glass", "glazing", "window", "windscreen", "windshield", "visor", "canopy", "lens")
SLIVER_MM = 1.5          # thinner than this, a small piece is a chip and a long one breaks
FRAGILE_MM = 2.0         # thinner than this, a piece (chrome, trim) goes on with the details, last
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

    # each part's voxels, and the true surfaces of its filled solids (the pieces' surfaces snap back onto them, so a
    # round part prints round and a flat face flat, not stepped)
    vox, true, whole = {}, {}, {}   # whole: each part's closed solids, as they are
    for pid, piece in closed:
        inside, surface = {}, {}
        printing._fill(grid, piece, inside)
        printing._mark_surface(grid, piece, surface)
        if _count(inside) >= _count(surface):
            _or_into(vox.setdefault(pid, {}), inside)
            true.setdefault(pid, []).extend([tuple(grid.to_cell(q)) for q in t] for t in piece)
            whole.setdefault(pid, []).append([[tuple(grid.to_cell(q)) for q in t] for t in piece])
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
            if not any(m & grooves.get(c, 0) for c, m in p["cols"].items()):
                continue   # no panel line crosses it
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

    moves = {}
    for a in scene_mod.compile_scene(scene)["articulations"]:   # what opens: the articulations each part rides on
        for pid in a["parts"]:
            moves.setdefault(pid, set()).add(a["id"])
    for p in pieces:
        p["moves"] = tuple(sorted(moves.get(p["head"], ())))
    raw = _order(pieces, grid.n, scene.get("subject", {}).get("category") == "architecture", detail)
    for p in pieces:   # its own middle in the scene's frame (metres, Y up): two copies of one part are two places
        b = _bbox(p["cols"])
        q = [grid.origin[a] + (b[2 * a] + b[2 * a + 1] + 1) / 2.0 * grid.h for a in range(3)]
        p["centre"] = [round(q[0], 5), round(q[2], 5), round(-q[1], 5)]
    _line_art(scene, pieces, grid)
    for p in pieces:
        # a piece that is one closed solid, untouched by the trimming, is printed as it is: exact, every facet
        exact = None
        if len(p["parts"]) == 1 and len(whole.get(p["head"], ())) == 1 and _count(p["cols"]) == _count(vox[p["head"]]) \
                and _count(own_vox[p["head"]]) == _count(p["cols"]):
            exact = whole[p["head"]][0]
        p["exact"] = exact is not None
        p["mesh"], p["size_mm"], p["down"] = _piece_mesh(p["cols"], detail, [t for m in p["parts"] for t in true.get(m, ())],
                                                         exact)
    plates = _pack(pieces, bed)
    kit = {"title": plan.get("title") or "%s, a kit" % scene["title"], "construct": scene["title"],
           "scale": "1:%s" % printing._ratio(1000.0 / mm_per_m), "detail_mm": detail, "pieces": pieces,
           "plates": plates, "steps": _flatten(_combine(_steps(pieces, raw), pieces), pieces), "bed_mm": list(bed), "scene": scene,
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
    def near_at(seg):
        a, b = seg
        i, j, k = (int(math.floor(x)) for x in grid.to_cell([(a[n] + b[n]) / 2 for n in range(3)]))
        return lambda p: sum(bin(p["cols"].get((i + di, j + dj), 0) >> max(k - 3, 0) & 0x7F).count("1")
                             for di in range(-3, 4) for dj in range(-3, 4))
    listed = {}
    for p in pieces:
        p["art"] = []
        for m in p["parts"]:
            listed.setdefault(m, []).append(p)
    for pid, segs in art.items():
        if len(listed.get(pid, ())) == 1:
            listed[pid][0]["art"].extend(segs)
        elif pid in listed:   # a merge that came out in pieces: each line goes to the piece it lies on
            for seg in segs:
                near = near_at(seg)
                max(listed[pid], key=near)["art"].append(seg)
        else:   # a part drawn only in lines: the piece it lies on (a seam on a door is the door's)
            near = near_at(segs[len(segs) // 2])
            best = max(pieces, key=near)
            if near(best):
                best["art"].extend(segs)


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


def _touches(pieces, n):
    """{(id a, id b): voxels of contact} for the pieces that can be glued together."""
    boxes = [_bbox(p["cols"]) for p in pieces]
    touch = {}
    for a in range(len(pieces)):
        for b in range(a + 1, len(pieces)):
            A, B = boxes[a], boxes[b]   # boxes apart by more than NEAR cannot touch
            if A[0] > B[1] + NEAR or B[0] > A[1] + NEAR or A[2] > B[3] + NEAR or B[2] > A[3] + NEAR \
                    or A[4] > B[5] + NEAR or B[4] > A[5] + NEAR:
                continue
            t = _near(pieces[a]["cols"], pieces[b]["cols"], n)
            if t:
                touch[(id(pieces[a]), id(pieces[b]))] = touch[(id(pieces[b]), id(pieces[a]))] = t
    return touch


def _order(pieces, n, ground_up=False, detail=DETAIL_MM):
    """Which piece each is glued to, and the order a builder glues them in.

    The pieces form a tree grown from the base (the largest piece of the first stage) along the strongest joins:
    contact, more where a piece rests on the one below it, less into clear plastic, and never from a part that
    stays put onto one that moves (a pillar is not glued to a door). Then the build walks the tree: a piece's own
    attachments go on at the bench before it is fitted (glass into its shell before the shell meets the chassis,
    a tyre onto its rim before the wheel goes on), earlier stages first, and what opens (a door, a bonnet) is
    hung last."""
    touch = _touches(pieces, n)
    cnt = {id(p): _count(p["cols"]) for p in pieces}   # each piece's size, counted once
    rank = lambda p: (p.get("group", 0), p["stage"], -cnt[id(p)])
    zc = {id(p): (lambda b: (b[4] + b[5]) / 2.0)(_bbox(p["cols"])) for p in pieces}

    def weight(p, q):   # the join of p onto q (q nearer the base)
        t = touch.get((id(p), id(q)), 0)
        if not t or not set(q.get("moves") or ()) <= set(p.get("moves") or ()):
            return 0.0   # what stays put never hangs on what moves (a pillar is not glued to a door)
        w = float(t) * (1.5 if zc[id(q)] < zc[id(p)] else 1.0)
        if p.get("moves") and p.get("moves") == q.get("moves"):
            w *= 2.0   # a door's glass and handle go into the door
        if p["clear"] != q["clear"]:
            w *= 0.5 if q["clear"] else 0.8   # glass goes into its frame; nothing is glued onto glass if it can help it
        return w
    held = {id(p): sum(t for (a, _), t in touch.items() if a == id(p)) for p in pieces}
    # how foundational a piece is: its sub-assembly in the plan, its stage, then how much holds onto it
    # (what opens comes after what stays put, and within a door the largest piece holds the rest; the construct's
    # stages say how its light is built, not what holds what, so they only break ties)
    # (a building goes up from the ground: what starts lower holds what starts higher)
    low = {id(p): _bbox(p["cols"])[4] // 3 if ground_up else 0 for p in pieces}
    found = lambda p: (p.get("group", 0), len(p.get("moves") or ()), low[id(p)],
                       -cnt[id(p)] if p.get("moves") else -held[id(p)], p["stage"], -cnt[id(p)])
    parent = {}
    chain_head = {}   # each moving group's largest piece: the one that hangs on the fixed body
    for p in pieces:
        if p.get("moves"):
            k = p["moves"]
            if k not in chain_head or cnt[id(p)] > cnt[id(chain_head[k])]:
                chain_head[k] = p
    for p in pieces:   # each onto the most firmly joined piece that is more foundational than it
        hosts = [q for q in pieces if q is not p and found(q) < found(p) and weight(p, q)]
        own = [q for q in hosts if p.get("moves") and q.get("moves") == p.get("moves")]
        if p.get("moves") and chain_head.get(p["moves"]) is not p:   # a lid is not hung from its handle
            own = own or [chain_head[p["moves"]]]
        elif p.get("moves"):   # the lid itself hangs on what it opens from, not on its own handle
            own, hosts = [], [q for q in hosts if q.get("moves") != p["moves"]]
        if p["clear"] and not own:   # glass goes into the last opaque part that frames it (the roof, not the nose)
            frames = [q for q in pieces if q is not p and not q["clear"] and weight(p, q)]
            best = max((weight(p, q) for q in frames), default=0)
            frames = [q for q in frames if weight(p, q) >= 0.3 * best]
            if frames:
                parent[id(p)] = max(frames, key=found)
                continue
        q = max(own or hosts, key=lambda q: weight(p, q), default=None)   # a door's glass goes into the door
        parent[id(p)] = q
    base = min(pieces, key=found)

    def above(q, p):   # whether p is q or under it, following the hosts down to the base
        seen = set()
        while q is not None and id(q) not in seen:
            if q is p:
                return True
            seen.add(id(q))
            q = parent[id(q)]
        return False
    for p in sorted(pieces, key=found):   # a ring of hosts (glass into its frame, the frame onto that glass) reaches no
        if parent[id(p)] is not None and above(parent[id(p)], p):   # base: its most foundational piece finds another
            parent[id(p)] = None
    for p in sorted(pieces, key=found):   # staged before what holds it (wheels before their axles): its best join
        if p is not base and parent[id(p)] is None:
            hosts = [q for q in pieces if q is not p and weight(p, q) and not above(q, p)
                     and found(q)[0] <= found(p)[0]]   # never onto a later sub-assembly of the plan (a floor onto a door)
            parent[id(p)] = max(hosts, key=lambda q: weight(p, q), default=None)
    kids = {}
    for p in pieces:
        if parent[id(p)] is not None:
            kids.setdefault(id(parent[id(p)]), []).append(p)
    box = {id(p): _bbox(p["cols"]) for p in pieces}

    def encloses(c, others):   # a shell over its siblings (a body over the interior) goes on after them
        b = box[id(c)]
        return sum(1 for o in others if o is not c and all(
            b[2 * a] <= (box[id(o)][2 * a] + box[id(o)][2 * a + 1]) / 2 <= b[2 * a + 1] for a in range(3)))
    for k in kids.values():   # (a list reads as empty while it is sorted: the siblings from a copy)
        sib = list(k)
        # its own small parts first (glass into a body before a chassis closes it), then what is built apart, and
        # a shell over the rest last
        k.sort(key=lambda c: (rank(c)[0], encloses(c, sib) > 0, bool(kids.get(id(c))), rank(c)))
    roots = [p for p in pieces if parent[id(p)] is None]
    roots.sort(key=lambda p: (p is not base, rank(p)))
    out, steps, hung, details = [], [], [], []

    def roomy(step, c):   # a step takes a few kinds of piece, however many of each (all the sill courses at once)
        kinds = {_kind_of(q["name"]) for q in step["pieces"]} | {_kind_of(c["name"])}
        return (len(kinds) <= STEP_KINDS and len(step["pieces"]) < STEP_MOST) or len(kinds) == 1

    def thin(c):
        b = _bbox(c["cols"])
        return (min(b[1] - b[0], b[3] - b[2], b[5] - b[4]) + 1) * detail

    kind_thin = {}
    for p in pieces:
        kind_thin.setdefault(_kind_of(p["name"]), []).append(thin(p))

    holds = {_kind_of(p["name"]) for p in pieces if kids.get(id(p))}

    def frail(c):   # copies of one part are alike: judged by their kind's usual thickness, not each one's voxels, and
        t = sorted(kind_thin[_kind_of(c["name"])])   # one that holds something (the left skin, with its button) is not
        return t[len(t) // 2] < FRAGILE_MM and _kind_of(c["name"]) not in holds   # a detail: nor is its mirror

    def built_on(c):   # what goes onto c at the bench: its attachments that neither open nor wait for the details
        return [d for d in kids.get(id(c), []) if set(d.get("moves") or ()) == set(c.get("moves") or ())
                and (kids.get(id(d)) or not frail(d) or d["clear"])]

    def build(p, bench):
        """Glue p's subtree onto p: leaves directly, sub-assemblies built at the bench first, then fitted."""
        opens = lambda c: set(c.get("moves") or ()) != set(p.get("moves") or ())   # it rides a hinge its host does not
        mine = [c for c in kids.get(id(p), []) if not opens(c)]
        hung.extend((c, p) for c in kids.get(id(p), []) if opens(c))
        fragile = [c for c in mine if not kids.get(id(c)) and frail(c) and not c["clear"]]
        details.extend((c, p) for c in fragile)   # fragile chrome and trim go on once the structure is built
        mine = [c for c in mine if c not in fragile]
        # a sub-assembly needs something to build at the bench: one whose only attachments open or are fragile (they
        # come later anyway) is glued on as a single piece
        subs = [c for c in mine if built_on(c)]
        leaves = [c for c in mine if c not in subs]
        for c in mine:   # in the kids' order: earlier first, and a shell after what it closes over
            if c in subs:
                out.append(c)
                steps.append({"kind": "bench", "root": c, "pieces": [c], "onto": None})
                build(c, True)
                steps.append({"kind": "fit", "root": c, "pieces": [], "onto": p, "assembly": c})
            else:
                out.append(c)
                last = steps[-1] if steps else None
                if last and roomy(last, c) and (
                        (last["kind"] == "glue" and last["onto"] is p)
                        or (last["kind"] == "bench" and last["root"] is p)):   # the bench step takes its first pieces
                    last["pieces"].append(c)
                else:
                    steps.append({"kind": "glue", "root": None, "pieces": [c], "onto": p, "bench": bench})
                if kids.get(id(c)):   # its fragile or opening attachments, for later
                    build(c, bench)
    for r in roots:
        out.append(r)
        steps.append({"kind": "base" if r is base else "loose", "root": r, "pieces": [r], "onto": None})
        build(r, r is not base)
    first = {}
    for c, _ in details:
        first.setdefault(_kind_of(c["name"]), len(first))
    at = {id(c): k for k, c in enumerate(out)}
    details.sort(key=lambda cp: (at.get(id(cp[1]), 0) // 6, first[_kind_of(cp[0]["name"])]))   # by where they go, alike together
    for c, p in details:   # the details: fragile pieces, onto their hosts, now that nothing will knock them off
        out.append(c)
        last = steps[-1] if steps else None
        if last and last["kind"] == "glue" and last.get("details") and roomy(last, c):
            last["pieces"].append(c)
        else:
            steps.append({"kind": "glue", "root": None, "pieces": [c], "onto": p, "details": True})
    while hung:   # what opens goes on last: built at the bench, then hung on its hinge
        c, p = hung.pop(0)
        out.append(c)
        steps.append({"kind": "bench" if kids.get(id(c)) else "glue", "root": c if kids.get(id(c)) else None,
                      "pieces": [c], "onto": None if kids.get(id(c)) else p, "hang": True})
        if kids.get(id(c)):
            build(c, True)
            steps.append({"kind": "fit", "root": c, "pieces": [], "onto": p, "assembly": c, "hang": True})
    reached = {id(c) for c in out}
    for p in pieces:   # never lose a piece: one the walk did not reach is built on its own, and the check says so
        if id(p) not in reached:
            parent[id(p)] = None
            out.append(p)
            steps.append({"kind": "loose", "root": p, "pieces": [p], "onto": None})
    assert len(out) == len(pieces), "a piece was walked twice"
    pieces[:] = out
    for k, p in enumerate(pieces, 1):
        p["number"] = k
        q = parent[id(p)]
        p["onto"] = q
        p["touches"] = sum(1 for o in pieces if o is not p and (id(p), id(o)) in touch)
    return steps


def _subtree(p, pieces):
    """p and every piece glued onto it, at any depth."""
    out = {p["number"]}
    grew = True
    while grew:
        grew = False
        for q in pieces:
            if q["onto"] is not None and q["onto"]["number"] in out and q["number"] not in out:
                out.add(q["number"])
                grew = True
    return out


SIDE_WORDS = {"left", "right", "l", "r", "front", "rear", "fl", "fr", "rl", "rr", "inner", "outer", "upper", "lower"}


def _kind_of(name):
    """What a piece is, whichever side or copy it is: "tyre-front (1 of 2)" and "tyre-rear-1" are both "tyre"."""
    base = name.split(" (")[0].lower()
    words = [w for w in base.replace("_", "-").split("-") if w and not w.isdigit() and w not in SIDE_WORDS]
    return "-".join(words) or base


SMALL_NEST = 4   # pieces: a sub-assembly built inside another this small is glued in place, not built apart


def _flatten(steps, pieces):
    """At the bench, a small sub-assembly inside another (a button on its lever, the lever on its ring) is glued
    on in one step, not built apart and fitted; then steps on the same few pieces run together, as a kit sheet
    says it: "the focus ring onto the distance ring, the lever onto the focus ring, the button onto the lever"."""
    by = {p["number"]: p for p in pieces}

    def spans():
        out = []
        for i, st in enumerate(steps):
            if st.get("kind") == "bench":
                j = next((k for k in range(i + 1, len(steps)) if steps[k].get("kind") == "fit"
                          and steps[k].get("assembly") == st["assembly"]), None)
                if j is not None:
                    out.append((i, j))
        return out
    changed = True
    while changed:
        changed = False
        sp = spans()
        for i, j in sp:
            inner = any(a < i and j < b for a, b in sp)                 # inside another sub-assembly
            leaf = not any(i < a and b < j for a, b in sp)               # with none of its own
            new = [n for t in steps[i:j + 1] for n in t.get("new", [])]
            if inner and leaf and len(new) <= SMALL_NEST and not steps[j].get("hang") and steps[i].get("times", 1) == 1:
                root, host = steps[i]["assembly"], steps[j]["onto"]
                glue = [(root, host)] + [g for t in steps[i:j] for g in t["glue"] if g != (root, None)]
                steps[i:j + 1] = [{"stage": steps[i]["stage"], "group": None, "kind": "glue", "hang": False, "details": False,
                                   "pieces": list(new), "new": list(new), "assembly": None, "onto": host, "glue": glue}]
                changed = True
                break
    out = []
    for st in steps:   # what goes onto the pieces just glued, at once: one step
        last = out[-1] if out else None
        if last and st.get("kind") == "glue" and last.get("kind") in ("glue", "bench") and not (
                st.get("details") or st.get("hang") or last.get("details") or last.get("hang")
                or st.get("times", 1) > 1 or last.get("times", 1) > 1):
            here = set(last.get("new", [])) | {h for _, h in last["glue"] if h is not None}
            kinds = {_kind_of(by[n]["name"]) for n in last.get("new", []) + st.get("new", [])}
            alone = last.get("kind") == "bench" and len(last["new"]) == 1   # a bench step of its root alone
            if all(h in here or h in st["new"] for _, h in st["glue"]) and len(kinds) <= STEP_KINDS + alone \
                    and len(last["new"]) + len(st["new"]) <= STEP_MOST:
                for key in ("pieces", "new", "glue"):
                    last[key] = last.get(key, []) + st.get(key, [])
                continue
        out.append(st)
    for k, st in enumerate(out, 1):
        st["number"] = k
        st["name"] = _title(st, by)
    return out


def _combine(steps, pieces):
    """Sub-assemblies built the same way more than once (four wheels, two doors, fourteen key sections) become one
    step each, done that many times: the same kinds of pieces, of about the same size, glued in the same order (how
    many of a kind each takes may differ: one key section has three black keys, the next two)."""
    by = {p["number"]: p for p in pieces}

    def sizes(i, j):   # each step's new pieces: each kind's largest size
        out = []
        for t in steps[i:j + 1]:
            k = {}
            for n in t.get("new", []):
                d = sorted(by[n]["size_mm"])
                k[_kind_of(by[n]["name"])] = max(k.get(_kind_of(by[n]["name"]), d), d)
            out.append(k)
        return out

    def alike(a, b):   # the same kinds, each within a quarter of the other's size
        return all(set(x) == set(y) and all(abs(p - q) <= 0.25 * max(p, q, 0.5) for k in x for p, q in zip(x[k], y[k]))
                   for x, y in zip(a, b))
    spans = []
    for i, st in enumerate(steps):
        if st.get("kind") == "bench":
            j = next((k for k in range(i + 1, len(steps)) if steps[k].get("kind") == "fit"
                      and steps[k].get("assembly") == st["assembly"]), None)
            if j is not None:
                sig = tuple((t.get("kind"), tuple(sorted({_kind_of(by[n]["name"]) for n in t.get("new", [])})))
                            for t in steps[i:j + 1])
                spans.append((i, j, sig, tuple(t.get("kind") for t in steps[i:j + 1])))
    gone = set()
    for a, (i, j, sig, form) in enumerate(spans):
        if i in gone:
            continue
        times = 1
        for (k, l, sig2, form2) in spans[a + 1:]:
            if k in gone or k <= j:
                continue   # only a later sub-assembly, not one inside this one
            copies = set(by[steps[i]["assembly"]].get("parts", ())) & set(by[steps[k]["assembly"]].get("parts", ()))
            same = sig2 == sig and alike(sizes(i, j), sizes(k, l))
            if not (same or (copies and form2 == form)):
                continue   # built the same way, of the same pieces; or copies of one part (key sections) built alike
            if not same:
                steps[i]["alike"] = False   # done alike, of pieces that differ: not "N x the same"
            for d in range(j - i + 1):
                for key in ("pieces", "new", "glue"):
                    steps[i + d][key] = steps[i + d].get(key, []) + steps[k + d].get(key, [])
            gone.update(range(k, l + 1))
            times += 1
        if times > 1:
            for d in range(j - i + 1):
                steps[i + d]["times"] = times
                steps[i + d]["alike"] = steps[i].get("alike", True)
                steps[i + d]["name"] = _title(steps[i + d], by)
    out = [st for n, st in enumerate(steps) if n not in gone]
    for k, st in enumerate(out, 1):
        st["number"] = k
    return out


def _steps(pieces, raw=None):
    """The booklet's steps: each says what is glued to what, and whether it is done at the bench (a
    sub-assembly, drawn on its own) or on the model."""
    if raw is None:   # pieces numbered elsewhere: one step per piece, in order
        raw = [{"kind": "glue", "pieces": [p], "onto": p["onto"]} for p in pieces]
    steps = []
    for st in raw:
        steps.append({"stage": st["pieces"][0]["stage"] if st["pieces"] else st["root"]["stage"],
                      "group": None, "kind": st["kind"], "hang": bool(st.get("hang")), "details": bool(st.get("details")),
                      "pieces": [p["number"] for p in st["pieces"]] or [st["root"]["number"]],
                      "new": [p["number"] for p in st["pieces"]],
                      "assembly": st["root"]["number"] if st.get("root") is not None else None,
                      "onto": st["onto"]["number"] if st.get("onto") is not None else None,
                      "glue": [(p["number"], p["onto"]["number"] if p["onto"] and not (st["kind"] == "bench" and p is st["root"])
                                else None) for p in st["pieces"]]
                      if st["kind"] != "fit" else [(st["root"]["number"], st["onto"]["number"])]})
    by = {p["number"]: p for p in pieces}
    for k, st in enumerate(steps, 1):
        st["number"] = k
        st["name"] = _title(st, by)
    return steps


def _label(name):
    """A piece's name as a builder says it: "leg-front (1 of 2)" is the leg front, "black-keys-3" the black keys."""
    words = [w for w in name.split(" (")[0].replace("_", "-").split("-") if w]
    while len(words) > 1 and words[-1].isdigit():
        words.pop()
    return " ".join(words)


def _counted(nums, by):
    """Pieces by what they are: "the lid hinge", "4 black keys" (said once however many)."""
    seen = {}
    for n in nums:
        k = _label(by[n]["name"])
        seen[k] = seen.get(k, 0) + 1
    words = ["the %s" % k if c == 1 else "%d × %s" % (c, k) for k, c in seen.items()]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _title(st, by):
    """A step's title, said as an instruction: what to do, with what, onto what."""
    times, kind = st.get("times", 1), st.get("kind")
    hosts = []
    for _, h in st.get("glue", []):
        if h is not None and h not in st.get("new", []) and _label(by[h]["name"]) not in hosts:
            hosts.append(_label(by[h]["name"]))
    onto = "the " + " and the ".join(hosts[:2]) if 1 <= len(hosts) <= 2 else "their places"
    if kind == "base":
        return "Start with %s" % _counted(st["new"], by)
    if kind == "loose":
        return "%s, on its own: nothing it can be glued to holds it (see the notes)" % by[st["assembly"]]["name"]
    root = "" if st.get("assembly") is None else _label(by[st["assembly"]]["name"]) if times == 1 else \
        _kind_of(by[st["assembly"]]["name"]).replace("-", " ")   # done more than once: the wheel, whichever side
    if kind == "bench":
        rest = [n for n in st["new"] if _label(by[n]["name"]) != root]
        what = ("%d × the %s" if st.get("alike", True) else "the %d %s assemblies") % (times, root) if times > 1 else "the %s" % root
        return "At the bench: build %s" % what + (", with %s" % _counted(rest, by) if rest and times == 1 else "")
    if kind == "fit":
        what = "the %d %s assemblies" % (times, root) if times > 1 else "the %s assembly" % root
        return "%s %s %s %s" % ("Hang" if st.get("hang") else "Fit", what, "on" if st.get("hang") else "onto", onto)
    if st.get("details"):
        return "Details, last: %s" % _counted(st["new"], by)
    if st.get("hang"):
        return "Hang %s on %s" % (_counted(st["new"], by), onto)
    pairs = [(n, h) for n, h in st.get("glue", []) if h is not None]
    if 1 < len(pairs) <= 4 and all(h == pairs[k][0] for k, (_, h) in enumerate(pairs[1:])):   # a chain, each onto the last
        return "Glue " + ", then ".join("the %s onto the %s" % (_label(by[n]["name"]), _label(by[h]["name"]))
                                        for n, h in pairs)
    return "Glue %s onto %s" % (_counted(st["new"], by), onto)


# a rotation that lays a piece on the face pointing `down` (its outward direction) onto the bed
LAY = {(0, 0, -1): lambda x, y, z: (x, y, z), (0, 0, 1): lambda x, y, z: (x, -y, -z),
       (-1, 0, 0): lambda x, y, z: (-z, y, x), (1, 0, 0): lambda x, y, z: (z, y, -x),
       (0, -1, 0): lambda x, y, z: (x, -z, y), (0, 1, 0): lambda x, y, z: (x, z, -y)}


def _piece_mesh(cols, detail, true=(), exact=None):
    """A piece's surface, lying on its largest flat face, in mm, its lowest corner at the origin: smoothed, and
    snapped onto `true` (its parts' own surfaces, in grid cells) where it lies within a voxel of them, so it keeps
    their roundness and their flat faces."""
    i0, i1, j0, j1, k0, k1 = _bbox(cols)
    area = {(0, 0, -1): sum(1 for m in cols.values() if m >> k0 & 1),
            (0, 0, 1): sum(1 for m in cols.values() if m >> k1 & 1),
            (-1, 0, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if i == i0),
            (1, 0, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if i == i1),
            (0, -1, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if j == j0),
            (0, 1, 0): sum(bin(m).count("1") for (i, j), m in cols.items() if j == j1)}
    down = max(area, key=lambda d: (area[d], d == (0, 0, -1)))
    if exact:   # the part's own solid, wound outward
        verts, faces = printing._weld(exact)
        faces = [tuple(f) for f in printing._orient(verts, faces)]
        verts = [list(v) for v in verts]
    else:
        work = dict(cols)
        printing._manifold(work)
        verts, faces = printing._surface(work, None)
        verts = printing._smooth(verts, faces, steps=6)   # fewer passes than a print's: the snap does the rest
        if true:
            verts = printing._snap(verts, list(true))
    lay = LAY[down]
    verts = [lay(*(x * detail for x in p)) for p in verts]
    lo = [min(v[a] for v in verts) for a in range(3)]
    verts = [[v[a] - lo[a] for a in range(3)] for v in verts]
    size = [round(max(v[a] for v in verts), 2) for a in range(3)]
    return {"vertices": verts, "triangles": faces}, size, list(down)


def _pack(pieces, bed):
    """Pieces onto plates the size of the bed: the opaque ones, then the clear ones on plates of their own (printed
    in clear filament or resin, as a kit moulds its glass apart); rows (shelves), tallest first, GAP_MM apart."""
    plates = _shelves([p for p in pieces if not p["clear"]], bed, 0)
    clear = _shelves([p for p in pieces if p["clear"]], bed, len(plates))
    for pl in clear:
        pl["clear"] = True
    return plates + clear


def _shelves(pieces, bed, before):
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
            plates.append({"number": before + len(plates) + 1, "pieces": [(p["number"], GAP_MM, GAP_MM)]})
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
            current = {"number": before + len(plates) + 1, "pieces": [(p["number"], GAP_MM, GAP_MM)],
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
        if p.get("touches") and p["onto"] is None and p["number"] != 1:
            problems.append({"code": "unheld", "piece": p["number"],
                             "message": "%d (%s) touches only pieces of later sub-assemblies: nothing earlier holds it; "
                                        "give it a face on the piece it belongs to, or move it in the plan's order"
                                        % (p["number"], p["name"])})
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


STEP_COLOURS = ("#1f6fd1", "#e3731b", "#1f9e5a", "#c2309a", "#0f9aa8", "#d23a3a", "#7a52d6", "#9a7a12")


def _drawing(kit, highlight, done, onto=None, w=900, hgt=600):
    """A step drawn as the construct draws itself, in lines on paper (SVG): what is built so far in grey, the
    piece it all goes onto darker, and each new piece in a colour of its own with its number in a callout of
    that colour and a chip of its paint, seen from the corner that faces them (the whole model from the front
    three-quarter)."""
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
    # exploded, as a kit's sheet draws it: each new piece (a fitted sub-assembly as one) a little away from where it
    # goes, along the line from what it goes onto, an arrow to its place
    pts = [q for p in shown for seg in p["art"] for q in seg]
    size = max(max(q[a] for q in pts) - min(q[a] for q in pts) for a in range(3)) or 1.0
    away = {}
    drawn = {p["number"] for p in shown}
    for p in new:
        top = p
        while top.get("onto") is not None and top["onto"]["number"] in highlight:
            top = top["onto"]
        host = top.get("onto")
        if host is None or host["number"] not in drawn or not host.get("art"):
            continue
        a, b = centre([top]), centre([host])
        hb = [(min(q[k] for seg in host["art"] for q in seg), max(q[k] for seg in host["art"] for q in seg)) for k in range(3)]
        out_of = [a[k] - hb[k][1] if a[k] > hb[k][1] else a[k] - hb[k][0] if a[k] < hb[k][0] else 0.0 for k in range(3)]
        k = max(range(3), key=lambda k: abs(out_of[k]) / ((hb[k][1] - hb[k][0]) or size))
        if out_of[k]:   # off one side of its host (a leg under the case): straight out that way
            d = [0.0, 0.0, 0.0]
            d[k] = math.copysign(1.0, out_of[k])
        else:   # within its host's bounds: away from its middle
            d = [a[k] - b[k] for k in range(3)]
        n = math.sqrt(sum(x * x for x in d))
        if n < 1e-3 * size:   # in its host's middle (a dial in its face): straight out, up
            d, n = [0.0, 0.0, 1.0], 1.0
        reach = 0.16 * size
        away[p["number"]] = [d[k] / n * reach for k in range(3)]

    def proj(q):
        u, v = q[0] * dui + q[1] * duj, q[0] * dvi + q[1] * dvj
        return ((u - v) * 0.866, (u + v) * 0.35 - q[2] * 0.95)

    def moved(p, seg):
        o = away.get(p["number"])
        return [[q[k] + o[k] for k in range(3)] for q in seg] if o else seg
    every = [proj(q) for p in shown for seg in p["art"] for q in seg]
    every += [proj(q) for p in new if p["number"] in away for seg in p["art"] for q in moved(p, seg)]
    xs, ys = [q[0] for q in every], [q[1] for q in every]
    pad = 70
    sc = min((w - 2 * pad) / ((max(xs) - min(xs)) or 1), (hgt - 2 * pad) / ((max(ys) - min(ys)) or 1))
    ox = pad + ((w - 2 * pad) - (max(xs) - min(xs)) * sc) / 2 - min(xs) * sc
    oy = pad + ((hgt - 2 * pad) - (max(ys) - min(ys)) * sc) / 2 - min(ys) * sc
    xy = lambda q: (ox + proj(q)[0] * sc, oy + proj(q)[1] * sc)

    def path(segs):
        return "".join("M%.1f %.1fL%.1f %.1f" % (*xy(a), *xy(b)) for a, b in segs)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">' % (w, hgt),
           '<rect width="100%" height="100%" fill="#f6f3ee"/>',
           '<path d="%s" stroke="#8d8794" stroke-opacity="0.45" stroke-width="0.6" fill="none"/>'
           % path([seg for p in shown if p["number"] not in highlight and p["number"] != onto for seg in p["art"]])]
    target = [p for p in shown if p["number"] == onto and p["number"] not in highlight]
    if target:
        out.append('<path d="%s" stroke="#3a3542" stroke-opacity="0.85" stroke-width="0.9" fill="none"/>'
                   % path([seg for p in target for seg in p["art"]]))
    colour = {p["number"]: STEP_COLOURS[k % len(STEP_COLOURS)] for k, p in enumerate(new)}
    out.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#3a3542"/></marker></defs>')
    for p in new:
        if p["number"] in away:   # where it goes, faint; the piece itself out where it is held up to it
            out.append('<path d="%s" stroke="%s" stroke-opacity="0.35" stroke-width="0.8" stroke-dasharray="3 3" fill="none"/>'
                       % (path(p["art"]), colour[p["number"]]))
        out.append('<path d="%s" stroke="%s" stroke-width="1.4" fill="none"/>'
                   % (path([moved(p, seg) for seg in p["art"]]), colour[p["number"]]))
    for p in new:   # the arrows: from the held piece to its place
        if p["number"] in away and (p.get("onto") is None or p["onto"]["number"] not in highlight):
            c = centre([p])
            a, b = xy([c[k] + away[p["number"]][k] * 0.78 for k in range(3)]), xy([c[k] + away[p["number"]][k] * 0.22 for k in range(3)])
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3a3542" stroke-width="1.3" marker-end="url(#ah)"/>'
                       % (a[0], a[1], b[0], b[1]))
    mid = (w / 2, hgt / 2)
    for p in new:   # a callout: the piece's number, out from the model, a leader line to the piece, its paint
        c = centre([p])
        if p["number"] in away:
            c = [c[k] + away[p["number"]][k] for k in range(3)]
        px, py = xy(c)
        dx, dy = px - mid[0], py - mid[1]
        d = math.hypot(dx, dy) or 1
        lx = min(max(px + dx / d * 46, 18), w - 34)
        ly = min(max(py + dy / d * 46, 18), hgt - 18)
        col = colour[p["number"]]
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>' % (px, py, lx, ly, col))
        out.append('<circle cx="%.1f" cy="%.1f" r="13" fill="%s"/>'
                   '<text x="%.1f" y="%.1f" fill="#ffffff" font-size="12" font-weight="700" font-family="monospace" '
                   'text-anchor="middle" dominant-baseline="central">%d</text>' % (lx, ly, col, lx, ly, p["number"]))
        out.append('<rect x="%.1f" y="%.1f" width="9" height="9" rx="2" fill="%s" stroke="#3a3542" stroke-width="0.6"/>'
                   % (lx + 15, ly - 4.5, p["paint"]["color"]))
    out.append("</svg>")
    return "".join(out)


def _hex_rgb(c):
    c = (c or "#c8c4cc").lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if len(c) == 6 else (200, 196, 204)


def _raster(items, w, h, bg=(246, 243, 238)):
    """A small z-buffered rasteriser (standard library only): `items` are (triangle in screen pixels with depth
    toward the viewer, (r, g, b)); returns PNG bytes."""
    from . import png
    zb = [-1e30] * (w * h)
    px = bytearray(bytes(bg) * (w * h))
    for (a, b, c), col in items:
        lx, hx = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
        ly, hy = min(a[1], b[1], c[1]), max(a[1], b[1], c[1])
        if hx - lx < 1.0 and hy - ly < 1.0:   # smaller than a pixel (a dense mesh): its middle is enough
            x, y = int((lx + hx) / 2), int((ly + hy) / 2)
            if 0 <= x < w and 0 <= y < h:
                z, i = (a[2] + b[2] + c[2]) / 3, y * w + x
                if z > zb[i]:
                    zb[i] = z
                    px[3 * i:3 * i + 3] = bytes(col)
            continue
        x0, x1 = max(0, int(lx)), min(w - 1, int(hx) + 1)
        y0, y1 = max(0, int(ly)), min(h - 1, int(hy) + 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x0 > x1 or y0 > y1 or abs(den) < 1e-12:
            continue
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                l1 = ((b[1] - c[1]) * (x + 0.5 - c[0]) + (c[0] - b[0]) * (y + 0.5 - c[1])) / den
                l2 = ((c[1] - a[1]) * (x + 0.5 - c[0]) + (a[0] - c[0]) * (y + 0.5 - c[1])) / den
                l3 = 1 - l1 - l2
                if l1 < -1e-4 or l2 < -1e-4 or l3 < -1e-4:
                    continue
                z = l1 * a[2] + l2 * b[2] + l3 * c[2]
                i = y * w + x
                if z > zb[i]:
                    zb[i] = z
                    px[3 * i:3 * i + 3] = bytes(col)
    return png.encode_rows(w, h, px)


def _shade(n, col, light=(0.45, 0.7, 0.55)):
    ln = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
    ll = math.sqrt(light[0] * light[0] + light[1] * light[1] + light[2] * light[2])
    k = 0.42 + 0.58 * abs(n[0] * light[0] + n[1] * light[1] + n[2] * light[2]) / ln / ll
    return (int(min(255, col[0] * k)), int(min(255, col[1] * k)), int(min(255, col[2] * k)))


def _thumb(mesh, colour, size=132):
    """A piece as it comes off the plate, seen from above at an angle, in its paint (PNG bytes)."""
    vs, fs = mesh["vertices"], mesh["triangles"]
    cy, sy, cp, sp = math.cos(math.radians(35)), math.sin(math.radians(35)), math.cos(math.radians(32)), math.sin(math.radians(32))

    def tf(v):
        x1, y1 = v[0] * cy - v[1] * sy, v[0] * sy + v[1] * cy
        return (x1, y1 * sp + v[2] * cp, -y1 * cp + v[2] * sp)
    P = [tf(v) for v in vs]
    xs, ys = [p[0] for p in P], [p[1] for p in P]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    sc = size * 0.84 / span
    ox, oy = size / 2 - (max(xs) + min(xs)) / 2 * sc, size / 2 + (max(ys) + min(ys)) / 2 * sc
    col = _hex_rgb(colour)
    if max(col) < 90:   # a black piece drawn black has no shape: lift it to a dark grey its shading shows on
        col = tuple(int(c * 0.5 + 72) for c in col)
    items = []
    for f in fs:
        a, b, c = (P[i] for i in f)
        u = [b[k] - a[k] for k in range(3)]
        w_ = [c[k] - a[k] for k in range(3)]
        n = (u[1] * w_[2] - u[2] * w_[1], u[2] * w_[0] - u[0] * w_[2], u[0] * w_[1] - u[1] * w_[0])
        items.append(([(ox + q[0] * sc, oy - q[1] * sc, q[2]) for q in (a, b, c)], _shade(n, col)))
    return _raster(items, size, size, bg=(255, 255, 255))


def _plate_png(kit, plate, w=640):
    """The plate seen from above: each piece's real outline and relief, in its paint (PNG bytes, and its height)."""
    bw, bd = kit["bed_mm"][0], kit["bed_mm"][1]
    sc = w / bw
    h = int(bd * sc)
    by = {p["number"]: p for p in kit["pieces"]}
    items = []
    for num, x0, y0 in plate["pieces"]:
        p = by[num]
        col = (159, 211, 240) if p["clear"] else _hex_rgb(p["paint"]["color"])
        vs = p["mesh"]["vertices"]
        for f in p["mesh"]["triangles"]:
            a, b, c = (vs[i] for i in f)
            u = [b[k] - a[k] for k in range(3)]
            w_ = [c[k] - a[k] for k in range(3)]
            n = (u[1] * w_[2] - u[2] * w_[1], u[2] * w_[0] - u[0] * w_[2], u[0] * w_[1] - u[1] * w_[0])
            items.append(([((x0 + q[0]) * sc, (y0 + q[1]) * sc, q[2]) for q in (a, b, c)], _shade(n, col, (0.3, -0.4, 0.86))))
    return _raster(items, w, h), h


def _plate_map(kit, plate, w=640):
    """The plate seen from above: each piece's footprint and its number (SVG)."""
    bw, bd = kit["bed_mm"][0], kit["bed_mm"][1]
    sc = w / bw
    by = {p["number"]: p for p in kit["pieces"]}
    import base64
    img, h = _plate_png(kit, plate, w)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%">' % (w, h),
           '<rect width="100%" height="100%" fill="#f6f3ee" stroke="#ddd8cf"/>',
           '<image href="data:image/png;base64,%s" x="0" y="0" width="%d" height="%d"/>' % (base64.b64encode(img).decode(), w, h)]
    placed, small = [], []   # every piece numbered, as on a sprue: on it when it is large enough, beside it with a
    for num, x, y in plate["pieces"]:   # short line when it is not, where no other number is
        p = by[num]
        fw, fd = p["size_mm"][0] * sc, p["size_mm"][1] * sc
        cx, cy = x * sc + fw / 2, y * sc + fd / 2
        if min(fw, fd) < 9:
            small.append((num, cx, cy, fw, fd))
            continue
        r = max(7, min(11, int(min(fw, fd) * 0.45)))
        placed.append((cx, cy, r))
        out.append('<circle cx="%.1f" cy="%.1f" r="%d" fill="#ffffff" fill-opacity="0.85" stroke="#1d1a22" stroke-width="0.8"/>'
                   '<text x="%.1f" y="%.1f" fill="#1d1a22" font-size="%d" font-weight="700" font-family="monospace" '
                   'text-anchor="middle" dominant-baseline="central">%d</text>' % (cx, cy, r, cx, cy, max(8, r + 1), num))
    for num, cx, cy, fw, fd in small:
        r = 6.5
        spots = [(cx, cy - fd / 2 - 9 - k * 14) for k in range(3)] + [(cx, cy + fd / 2 + 9 + k * 14) for k in range(3)] + \
                [(cx + fw / 2 + 9 + k * 14, cy) for k in range(3)] + [(cx - fw / 2 - 9 - k * 14, cy) for k in range(3)]
        spots = [(sx, sy) for sx, sy in spots if r <= sx <= w - r and r <= sy <= h - r] or [(cx, cy)]
        sx, sy = next(((sx, sy) for sx, sy in spots if all(math.hypot(sx - px, sy - py) > r + pr + 1 for px, py, pr in placed)),
                      spots[0])
        placed.append((sx, sy, r))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#1d1a22" stroke-width="0.6"/>'
                   '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#ffffff" stroke="#1d1a22" stroke-width="0.7"/>'
                   '<text x="%.1f" y="%.1f" fill="#1d1a22" font-size="7.5" font-weight="700" font-family="monospace" '
                   'text-anchor="middle" dominant-baseline="central">%d</text>' % (cx, cy, sx, sy, sx, sy, r, sx, sy, num))
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
    done, bench = set(), []   # bench: the sub-assemblies being built off the model, innermost last
    for s in kit["steps"]:
        new = set(s.get("new", s["pieces"]))
        if s.get("kind") == "bench":
            bench.append(s["assembly"])
        if s.get("kind") == "fit":   # the finished sub-assembly goes onto what it was built for
            asm = _subtree(by[s["assembly"]], kit["pieces"])
            if bench and bench[-1] == s["assembly"]:
                bench.pop()
            ctx = done if not bench else done & _subtree(by[bench[-1]], kit["pieces"])
            pic = _drawing(kit, asm, ctx - asm, s.get("onto"))
        else:   # at the bench only the sub-assembly is drawn; on the model, everything built so far
            ctx = done if not bench else done & _subtree(by[bench[-1]], kit["pieces"])
            pic = _drawing(kit, new, ctx, s.get("onto"))
        (out / "img" / ("step-%d.svg" % s["number"])).write_text(pic, encoding="utf-8")
        done |= new
    (out / "img" / "complete.svg").write_text(_drawing(kit, set(), done), encoding="utf-8")
    for p in kit["pieces"]:   # each part as it comes off the plate, for the booklet's "you need" pictures
        (out / "img" / ("part-%d.png" % p["number"])).write_bytes(_thumb(p["mesh"], "#9fd3f0" if p["clear"] else p["paint"]["color"]))
    (out / "booklet.html").write_text(booklet(kit), encoding="utf-8")
    if kit.get("scene"):
        (out / "assembly.html").write_text(assembly(kit), encoding="utf-8")
        files.append(out / "assembly.html")
    (out / "kit.json").write_text(json.dumps(summary(kit), indent=1) + "\n", encoding="utf-8")
    return [str(f) for f in files] + [str(out / "booklet.html"), str(out / "kit.json")]


def summary(kit):
    """The kit without its geometry: what a critic reads, and what the tests check."""
    return {"title": kit["title"], "construct": kit["construct"], "scale": kit["scale"], "size_mm": kit["size_mm"],
            "report": kit["report"], "plan": kit["plan"], "merged": kit["merged"], "dropped": kit["dropped"],
            "pieces": [{"number": p["number"], "name": p["name"], "parts": p["parts"], "stage": p["stage"],
                        "size_mm": p["size_mm"], "clear": p["clear"], "paint": p["paint"]["name"],
                        "glued_to": p["onto"]["number"] if p["onto"] else None} for p in kit["pieces"]],
            "steps": [{"number": s["number"], "name": s.get("name"), "kind": s.get("kind"), "pieces": s["pieces"],
                       "glue": s["glue"]} for s in kit["steps"]],
            "plates": [{"number": pl["number"], "clear": bool(pl.get("clear")), "pieces": [n for n, _, _ in pl["pieces"]]}
                       for pl in kit["plates"]]}


ASSEMBLY_JS = r"""
// the kit's steps in 3D: each step's pieces drop into place in their paint, what is built stays as it is, the step's
// instructions big at the top with a line to each piece, the controls at the bottom
(function () {
  var K = __KIT__, COLS = __COLOURS__;
  var at = -1, playing = false;
  var css = document.createElement("style");
  css.textContent =
    ".help,.rounds{display:none!important}" +
    // a light studio backdrop, as a kit's box shows its model: dark paints read on it as well as light ones
    "html,body{background:radial-gradient(ellipse at 50% 38%,#f1efeb 0%,#d6d2cc 55%,#aaa59e 100%)!important}" +
    ".caption .title{color:#2a2530!important}.caption .meta,.caption div{color:#4d4656!important}" +
    ".caption,.caption *{text-shadow:none!important}.kt .more{color:#6b6475;font:700 14px -apple-system,sans-serif}" +
    ".kt{position:fixed;left:50%;top:14px;transform:translateX(-50%);width:min(980px,calc(100% - 24px));z-index:5;" +
    "background:rgba(250,248,244,.94);color:#1d1a22;border-radius:14px;box-shadow:0 6px 30px rgba(0,0,0,.35);" +
    "padding:14px 20px 12px;font:15px/1.4 -apple-system,'Segoe UI',sans-serif;max-height:38vh;overflow:auto}" +
    ".kt .n{font:600 12px/1 -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#6b6475}" +
    ".kt h2{font:700 24px/1.2 -apple-system,sans-serif;margin:4px 0 6px}.kt .x{display:inline-block;margin-left:8px;" +
    "padding:2px 10px;border-radius:12px;background:#1d1a22;color:#fff;font:700 16px/1.3 -apple-system,sans-serif}" +
    ".kt .bench{display:inline-block;margin:0 0 8px;padding:3px 10px;border-radius:8px;background:#e6eef9;color:#1f4f8f;" +
    "font-size:13px}.kt ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 18px}" +
    ".kt li{display:flex;align-items:center;gap:8px;font-size:16px}.kt .num{min-width:30px;height:30px;border-radius:15px;" +
    "color:#fff;font:700 14px/30px ui-monospace,monospace;text-align:center;padding:0 6px}.kt .chip{width:14px;height:14px;" +
    "border-radius:3px;border:1px solid #777}.kt .onto{color:#6b6475}" +
    ".kc{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:5;display:flex;align-items:center;gap:10px;" +
    "background:rgba(20,16,26,.88);border:1px solid #3a2f48;border-radius:28px;padding:8px 12px;color:#f1e9f7;" +
    "font:14px -apple-system,sans-serif}.kc button{background:#2f2540;color:#fff;border:0;border-radius:20px;" +
    "padding:9px 18px;font:600 15px -apple-system,sans-serif;cursor:pointer}.kc button:hover{background:#4a3a63}" +
    ".kc .pg{min-width:72px;text-align:center;color:#cbbcd8}.kbar{position:fixed;left:0;bottom:0;height:4px;" +
    "background:#d16bd0;z-index:5;transition:width .3s}" +
    "svg.kl{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:4}" +
    ".tag{position:fixed;transform:translate(-50%,-50%);pointer-events:none;border-radius:13px;color:#fff;" +
    "font:700 12px/26px ui-monospace,monospace;min-width:26px;padding:0 6px;text-align:center;z-index:4;" +
    "box-shadow:0 0 0 2px rgba(255,255,255,.85)}" +
    "@media(max-width:640px){.kt{top:8px;padding:10px 12px}.kt h2{font-size:18px}.kt li{font-size:14px}" +
    ".kc{bottom:10px;gap:6px}.kc button{padding:8px 12px}}";
  document.head.appendChild(css);
  var top = document.createElement("div"); top.className = "kt"; document.body.appendChild(top);
  var ctl = document.createElement("div"); ctl.className = "kc"; document.body.appendChild(ctl);
  var bar = document.createElement("div"); bar.className = "kbar"; document.body.appendChild(bar);
  var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("class", "kl"); document.body.appendChild(svg);
  ctl.innerHTML = "<button data-a=prev>&#9664; Previous</button><button data-a=play>&#9654; Play</button>" +
    "<span class=pg></span><button data-a=next>Next &#9654;</button><button data-a=done>Finished</button>";
  ctl.querySelectorAll("button").forEach(function (b) { b.onclick = function () { act(b.getAttribute("data-a")); }; });
  var tags = [];
  function esc(x) { var d = document.createElement("div"); d.textContent = x; return d.innerHTML; }
  function lab(name) {   // as a builder says it: "leg-front (1 of 2)" is the leg front, "black-keys-3" the black keys
    var w = name.replace(/ \(\d+ of \d+\)$/, "").split(/[-_]+/).filter(Boolean);
    while (w.length > 1 && /^\d+$/.test(w[w.length - 1])) w.pop();
    return w.join(" ");
  }
  function onto(ns) {
    var u = ns.filter(function (v, i, a) { return a.indexOf(v) === i; });
    return "<span class=onto>onto the " + esc(lab(K.pieces[u[0]].name)) + " (" + u.join(", ") + ")</span>";
  }
  function rows(s) {   // one row per kind of piece: a repeated step shows each kind once, with all its numbers
    var seen = {}, out = [];
    s.glue.forEach(function (g, i) {
      var p = K.pieces[g[0]], key = s.kind === "fit" ? "fit" : p.kind + "|" + (g[1] ? K.pieces[g[1]].kind : "");
      if (!seen[key]) { seen[key] = { nums: [], p: p, onto: g[1] ? K.pieces[g[1]] : null, ontoN: [], c: COLS[out.length % COLS.length] }; out.push(seen[key]); }
      seen[key].nums.push(g[0]); if (g[1]) seen[key].ontoN.push(g[1]);
    });
    return out;
  }
  function show(k) {
    var s = K.steps[k], rs = rows(s);
    var list = rs.map(function (r) {   // a long run of one kind: its first numbers, its last, and how many
      var shown = r.nums.length > 6 ? r.nums.slice(0, 2).concat([null], r.nums.slice(-1)) : r.nums;
      var nums = shown.map(function (n) { return n === null ? "<span class=more>&hellip;</span>" :
        "<span class=num data-n=" + n + " style='background:" + r.c + "'>" + n + "</span>"; }).join("") +
        (r.nums.length > 6 ? "<span class=more>&times;" + r.nums.length + "</span>" : "");
      if (s.kind === "fit") return "<li>" + nums + " the " + esc(lab(r.p.name)) + " assembl" + (r.nums.length > 1 ? "ies" : "y") +
        " " + onto(r.ontoN) + "</li>";
      return "<li>" + nums + esc(lab(r.p.name)) +
        "<span class=chip style='background:" + r.p.color + "'></span><span class=onto>" + esc(r.p.paint) + "</span>" +
        (r.onto ? onto(r.ontoN) : s.kind === "bench" ? "<span class=onto>start of this assembly</span>" : "") +
        (r.p.clear ? " <i>clear</i>" : "") + "</li>";
    }).join("");
    top.innerHTML = "<div class=n>" + esc(K.title) + " &middot; step " + (k + 1) + " of " + K.steps.length + "</div>" +
      "<h2>" + esc(s.name || "Step " + (k + 1)) + (s.times > 1 ? "<span class=x>&times; " + s.times + "</span>" : "") + "</h2>" +
      (s.kind === "bench" ? "<div class=bench>At the bench: build this on its own first (shown here in place)</div>" :
       s.bench ? "<div class=bench>Still at the bench: onto the sub-assembly, not the model yet</div>" : "") +
      "<ul>" + list + "</ul>";
    ctl.querySelector(".pg").textContent = (k + 1) + " / " + K.steps.length;
    ctl.querySelector("[data-a=play]").innerHTML = playing ? "&#10073;&#10073; Pause" : "&#9654; Play";
    bar.style.width = ((k + 1) / K.steps.length * 100) + "%";
    tags.forEach(function (t) { t.el.remove(); });
    tags = [];
    rs.forEach(function (r, ri) {   // a tag on each piece and a line from its badge; many alike: one tag at their middle
      var li = top.querySelectorAll("ul li")[ri];
      var group = r.nums.length > 4 ? [r.nums] : r.nums.map(function (n) { return [n]; });
      group.forEach(function (ns) {
        var el = document.createElement("div"); el.className = "tag"; el.style.background = r.c;
        el.textContent = ns.length > 1 ? "\u00d7" + ns.length : ns[0];
        document.body.appendChild(el);
        tags.push({ el: el, ns: ns, c: r.c, badge: li && li.querySelector(".num[data-n='" + ns[0] + "']") });
      });
    });
    history.replaceState(null, "", "#step-" + (k + 1));
  }
  var T = 0, from = 0, to = 0, startAt = 0, DUR = 1300, lastLines = "";
  var focus = null, camFrom = null, camAt = 0;
  function aim(k) {   // the camera on the step's pieces: their middle, closer in for small ones; you can still turn it
    var H = HOLO.hologram, cs = K.steps[k].glue.map(function (g) { return K.pieces[g[0]].centre; }).filter(Boolean);
    if (!cs.length) return;
    var m = [0, 1, 2].map(function (a) { return cs.reduce(function (s, c) { return s + c[a]; }, 0) / cs.length; });
    var spread = Math.max.apply(null, cs.map(function (c) { return Math.hypot(c[0] - m[0], c[1] - m[1], c[2] - m[2]); }));
    var fit = HOLO.fitted("hero"), now = H.userCamera || HOLO.camera() || fit;
    var low = m[1] < H.C[1];   // under the model (legs, the chassis): look from a little below, as a sheet
    focus = { target: m, yaw: now.yaw, pitch: low ? -14 : Math.max(18, now.pitch), fov: now.fov || 34,   // turns it over
              dist: fit.dist * Math.max(0.55, Math.min(1, (spread + 0.12 * H.R) * 2.4 / H.R)) };
    camFrom = { target: (now.target || fit.target).slice(), yaw: now.yaw, pitch: now.pitch, dist: now.dist, fov: now.fov || 34 };
    camFrom.pitch0 = now.pitch;
    camAt = performance.now();
  }
  function go(k) {
    k = Math.max(0, Math.min(K.steps.length - 1, k));
    from = at >= 0 && k > at ? K.steps[at].build : (k > 0 ? K.steps[k - 1].build : 0); to = K.steps[k].build;
    at = k; startAt = performance.now(); show(k); aim(k);
  }
  function act(a) {
    if (a === "prev") { playing = false; go(at - 1); }
    else if (a === "next") { playing = false; go(at + 1); }
    else if (a === "play") { playing = !playing; if (playing && !startAt) go(at + 1 < K.steps.length ? at + 1 : 0); else show(at); }
    else if (a === "done") { playing = false; at = K.steps.length - 1; show(at); from = to = 0.9999; startAt = 0;
      focus = null; HOLO.hologram.userCamera = null;
      tags.forEach(function (t) { t.el.remove(); }); tags = []; svg.textContent = "";
      HOLO.renderAt(T, { solid: true, open: 0, build: 0.9999, highlight: [0, 0], fly: 0, reveal: K.reveal }); }
  }
  window.addEventListener("hashchange", function () {
    var m = /#step-(\d+)/.exec(location.hash); if (m && parseInt(m[1], 10) - 1 !== at) go(parseInt(m[1], 10) - 1); });
  window.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") act("next"); else if (e.key === "ArrowLeft") act("prev"); });
  function tick(now) {
    if (focus) {   // glide to the step's pieces; after that the camera is yours (and comes back here if it wanders off)
      var H = HOLO.hologram, u = Math.min(1, (now - camAt) / 900), e = u * u * (3 - 2 * u);
      if (u < 1 || !H.userCamera) {
        H.userCamera = { target: [0, 1, 2].map(function (a) { return camFrom.target[a] + (focus.target[a] - camFrom.target[a]) * e; }),
                         yaw: camFrom.yaw, pitch: camFrom.pitch + (focus.pitch - camFrom.pitch) * e,
                         dist: camFrom.dist + (focus.dist - camFrom.dist) * e, fov: 34 };
        if (u >= 1) camFrom = { target: focus.target.slice(), yaw: H.userCamera.yaw, pitch: H.userCamera.pitch, dist: focus.dist,
                                fov: 34 };
        if (!startAt) HOLO.renderAt(T, { solid: true, open: 0, build: to, highlight: K.steps[at].window, fly: 0, reveal: K.reveal });
      }
    }
    if (startAt) {
      var u = Math.min(1, (now - startAt) / DUR), s = K.steps[at];
      HOLO.renderAt(T, { solid: true, open: 0, build: from + (to - from) * u, highlight: s.window, fly: u < 1 ? 0.35 : 0,
                         reveal: K.reveal });
      if (u >= 1) { startAt = 0; if (playing) setTimeout(function () { if (playing) go(at + 1 < K.steps.length ? at + 1 : 0); }, 1100); }
    }
    var lines = "", spots = [];
    tags.forEach(function (t) {   // each number on its piece, and a line from its badge in the instructions
      var qs = t.ns.map(function (n) { var c = K.pieces[n].centre; return c && HOLO.project(c); }).filter(Boolean);
      t.el.style.display = qs.length ? "block" : "none";
      if (!qs.length) return;
      var q = [qs.reduce(function (s, v) { return s + v[0]; }, 0) / qs.length, qs.reduce(function (s, v) { return s + v[1]; }, 0) / qs.length];
      for (var k = 0; k < 12 && spots.some(function (o) { return Math.hypot(o[0] - q[0], o[1] - q[1]) < 30; }); k++)
        q = [q[0] + (k % 2 ? -1 : 1) * 16, q[1] + 15];   // numbers that would sit on each other step aside
      spots.push(q);
      t.el.style.left = q[0] + "px"; t.el.style.top = q[1] + "px";
      var b = t.badge && t.badge.getBoundingClientRect(), tb = top.getBoundingClientRect();
      if (b && b.width) lines += "<line x1='" + (b.left + b.width / 2) + "' y1='" + Math.min(b.bottom, tb.bottom) + "' x2='" + q[0] +
        "' y2='" + q[1] + "' stroke='" + t.c + "' stroke-width='2' stroke-opacity='.8'/>";
    });
    if (lines !== lastLines) { svg.innerHTML = lines; lastLines = lines; }   // only when something moved
    requestAnimationFrame(tick);
  }
  function start() {
    if (!window.HOLO || !HOLO.timeline) return setTimeout(start, 60);
    T = HOLO.timeline().settled + 1;
    var m = /#step-(\d+)/.exec(location.hash), k = m ? parseInt(m[1], 10) - 1 : 0;
    go(k); requestAnimationFrame(tick);
  }
  start();
})();
"""


def assembly(kit):
    """The steps in 3D (HTML): the construct's solid view painted with the kit's paints, each step's pieces dropping
    into place in gluing order and the rest stepping back, a panel saying what goes onto what, numbers on the
    pieces; drag to turn it, the arrow keys to step."""
    from . import render
    scene, steps, n = kit["scene"], kit["steps"], max(1, len(kit["steps"]))
    by = {p["number"]: p for p in kit["pieces"]}
    scene = dict(scene, presentation=dict(scene.get("presentation") or {}, background="transparent"))   # the page's backdrop
    g = scene_mod.compile_scene(scene)
    phase_of, colour_of = {}, {}
    for k, s in enumerate(steps):
        new = s.get("new", [])
        for j, num in enumerate(new):   # one after another within the step, each whole at once
            for pid in by[num]["parts"]:
                phase_of.setdefault(pid, round((k + 0.82 * j / max(1, len(new))) / n, 5))
                colour_of.setdefault(pid, by[num]["paint"]["color"])
    g["style_colors"] = [colour_of.get(g["parts"][int(st[6])]["id"]) for st in g["styles"]]
    boxes = {}
    for part in g["parts"]:
        for ins in part.get("instances", []):
            boxes.setdefault(part["id"], []).append([(ins["min"][a] + ins["max"][a]) / 2 for a in range(3)])
    pieces = {}
    for p in kit["pieces"]:
        cs = [p["centre"]] if p.get("centre") else [c for pid in p["parts"] for c in boxes.get(pid, [])]
        pieces[p["number"]] = {"name": p["name"], "kind": _kind_of(p["name"]), "paint": p["paint"]["name"],
                               "color": p["paint"]["color"],
                               "clear": p["clear"], "centre": [round(sum(c[a] for c in cs) / len(cs), 5) for a in range(3)]
                               if cs else None}
    data = {"title": kit["title"], "pieces": pieces, "reveal": round(0.08 / n, 5),
            "steps": [{"name": s.get("name"), "kind": s.get("kind"), "glue": s["glue"], "times": s.get("times", 1),
                       "window": [round(k / n, 5), round((k + 1) / n, 5)], "build": round((k + 0.9) / n, 5)}
                      for k, s in enumerate(steps)]}
    spans = []   # each sub-assembly's steps at the bench: from its bench step to the step that fits it
    for t in steps:
        if t.get("kind") == "bench":
            end = next((u["number"] for u in steps if u.get("kind") == "fit" and u.get("assembly") == t["assembly"]
                        and u["number"] > t["number"]), t["number"])
            spans.append((t["number"], end))
    for k, s in enumerate(steps):
        data["steps"][k]["bench"] = s.get("kind") == "glue" and any(a < s["number"] < b for a, b in spans)
    js = ASSEMBLY_JS.replace("__KIT__", json.dumps(data)).replace("__COLOURS__", json.dumps(list(STEP_COLOURS)))
    html, _ = render.build_html(g, None, solid=render.solid_payload(scene, g, phase_of), extra=js)
    return html


def booklet(kit):
    """The instruction booklet (HTML, on paper): a cover, what you need, the plates, then a card per step: the parts
    you need as pictures, what goes onto what in the colours of the drawing, and the drawing."""
    by = {p["number"]: p for p in kit["pieces"]}
    e = html.escape
    has3d = bool(kit.get("scene"))
    paints = {}
    for p in kit["pieces"]:
        paints.setdefault((p["paint"]["name"], p["paint"]["color"]), []).append(p["number"])
    rows = ['<header class=cover><div class=brand>Construct kit</div><h1>%s</h1><p class=sub>%s scale &middot; %d pieces on '
            '%d plates &middot; %d steps &middot; %s &times; %s &times; %s mm built</p>'
            '<img class=hero src="img/complete.svg" alt="The finished model">%s</header>' % (
                e(kit["title"]), kit["scale"], len(kit["pieces"]), len(kit["plates"]), len(kit["steps"]), *kit["size_mm"],
                '<p class=b3d><a href="assembly.html">Watch it built in 3D, step by step &rarr;</a> Turn it, replay any step.</p>'
                if has3d else "")]
    rows.append("<section class=start><h2>Before you start</h2><div class=need><div><h3>You need</h3><ul><li>The plates, "
                "printed (clear plates in clear filament or resin)</li><li>Plastic cement or super glue</li><li>A sharp "
                "knife and fine sanding paper</li><li>The paints below</li></ul></div><div><h3>Paints</h3><table>%s</table>"
                "</div></div>" % "".join(
                    "<tr><td><span class=chip style='background:%s'></span></td><td>%s</td><td class=nums>%s</td></tr>"
                    % (c, e(n), ", ".join(str(x) for x in nums)) for (n, c), nums in sorted(paints.items())))
    rep = kit["report"]
    if rep["problems"]:
        rows.append("<details class=warn><summary>Notes from the check (%d)</summary><ul>%s</ul></details>"
                    % (len(rep["problems"]), "".join("<li>%s</li>" % e(p["message"]) for p in rep["problems"])))
    rows.append("</section><section><h2>Plates</h2>")
    for plate in kit["plates"]:
        rows.append("<figure class=plate><img src='img/plate-%d.svg' alt='Plate %d'><figcaption>Plate %d%s</figcaption></figure>"
                    % (plate["number"], plate["number"], plate["number"], " &middot; clear" if plate.get("clear") else ""))
    rows.append("</section><section><h2>Building it</h2>")
    for s in kit["steps"]:
        kind = s.get("kind")
        seen, groups = {}, []
        for k, (num, onto) in enumerate(s["glue"]):
            key = "fit" if kind == "fit" else (_kind_of(by[num]["name"]), _kind_of(by[onto]["name"]) if onto else "")
            if key not in seen:
                seen[key] = {"nums": [], "onto": [], "col": STEP_COLOURS[len(groups) % len(STEP_COLOURS)]}
                groups.append(seen[key])
            seen[key]["nums"].append(num)
            if onto and onto not in seen[key]["onto"]:
                seen[key]["onto"].append(onto)
        items, need = [], []
        for g in groups:
            p = by[g["nums"][0]]
            run = g["nums"] if len(g["nums"]) <= 6 else g["nums"][:2] + [None] + g["nums"][-1:]   # a long run, shortened
            badges = "".join("&hellip; " if n is None else "<span class=num style='background:%s'>%d</span>" % (g["col"], n)
                             for n in run) + (" <b>&times;%d</b> " % len(g["nums"]) if len(g["nums"]) > 6 else "")
            if kind == "fit":
                items.append("<li>%s the %s assembl%s onto %s</li>" % (badges, e(_label(p["name"])), "ies" if len(g["nums"]) > 1
                                                                       else "y", ", ".join(str(o) for o in g["onto"])))
                continue
            onto = " onto %s <b>%s</b>" % (", ".join(str(o) for o in g["onto"]), e(_label(by[g["onto"][0]]["name"]))) \
                if g["onto"] else (" &mdash; the base" if g["nums"][0] == 1 else " &mdash; start of this assembly"
                                   if kind == "bench" else "")
            items.append("<li>%s %s <span class=chip style='background:%s'></span><span class=paint>%s</span>%s%s</li>" % (
                badges, e(_label(p["name"])), p["paint"]["color"], e(p["paint"]["name"]), onto,
                " <i>clear</i>" if p["clear"] else ""))
            need.append("<figure><img src='img/part-%d.png' alt='%s'><figcaption><span class=num style='background:%s'>%s</span>%s"
                        "<br><span class=chip style='background:%s'></span> %s</figcaption></figure>" % (
                            g["nums"][0], e(_label(p["name"])), g["col"],
                            ", ".join(str(n) for n in g["nums"][:3]) + ("&hellip;" if len(g["nums"]) > 3 else ""),
                            " <b>&times;%d</b>" % len(g["nums"]) if len(g["nums"]) > 1 else "", p["paint"]["color"],
                            e(p["paint"]["name"])))
        times = s.get("times", 1)
        tag = {"bench": "<div class=tagb>Build this on its own first</div>", "fit": "<div class=tagf>Fit it</div>"}.get(kind, "")
        if s.get("details"):
            tag = "<div class=tagd>Fragile: fit these last</div>"
        link = " <a class=b3d href='assembly.html#step-%d'>3D</a>" % s["number"] if has3d else ""
        # as a kit's sheet reads: the step and what to do, the parts it takes, the drawing large, what goes where
        rows.append("<article class='step %s'><div class=head><span class=sn>%d</span><div><h3>%s%s</h3>%s</div>%s</div>"
                    "%s<img class=pic src='img/step-%d.svg' alt='Step %d'><ul class=legend>%s</ul></article>" % (
                        kind or "", s["number"], e(s.get("name") or "Step %d" % s["number"]),
                        " <span class=x>&times;%d</span>" % times if times > 1 else "", tag, link,
                        "<div class=need-row>%s</div>" % "".join(need) if need else "",
                        s["number"], s["number"], "".join(items)))
    rows.append("</section>")
    css = ("body{margin:0;background:#fbfaf7;color:#1d1a22;font:16px/1.5 -apple-system,'Segoe UI',sans-serif}"
           "main{max-width:1040px;margin:0 auto;padding:28px 18px 60px}h1{font:700 40px/1.1 -apple-system,sans-serif;margin:6px 0}"
           "h2{font:700 26px/1.2 -apple-system,sans-serif;margin:34px 0 12px;border-bottom:3px solid #1d1a22;padding-bottom:6px}"
           ".brand{font:700 12px/1 -apple-system,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#c2309a}"
           ".sub{color:#5f5869;margin:0 0 14px}img{max-width:100%}.hero{width:100%;border-radius:12px;border:1px solid #ddd8cf}"
           ".b3d{font-weight:600}.b3d a,a.b3d{color:#1f6fd1}.need{display:grid;grid-template-columns:1fr 1fr;gap:24px}"
           "h3{margin:0 0 6px}table{border-collapse:collapse}td{padding:3px 8px;border-bottom:1px solid #e4dfd6}"
           ".nums{color:#6b6475;font-size:13px}.paint{color:#6b6475;font-size:13px;margin:0 6px 0 4px}.chip{display:inline-block;width:14px;height:14px;border-radius:3px;"
           "border:1px solid #777;vertical-align:-2px}.warn{margin:14px 0;border:1px solid #d23a3a;border-radius:8px;padding:8px 14px}"
           ".warn summary{cursor:pointer;font-weight:600}.plate{margin:12px 0}.plate img{border:1px solid #ddd8cf;border-radius:8px}"
           "figcaption{font-size:13px;color:#5f5869}.step{border:1px solid #e4dfd6;border-radius:14px;padding:16px 18px;"
           "margin:18px 0;background:#fff;break-inside:avoid}"
           ".step.bench{border-color:#9cc0ea;background:#f6f9fd}.step.fit{border-color:#c8b6e0;background:#faf7fd}"
           ".head{display:flex;align-items:center;gap:14px;margin-bottom:10px}.head>div{flex:1}.sn{min-width:56px;height:56px;"
           "border-radius:28px;background:#1d1a22;color:#fff;font:800 28px/56px -apple-system,sans-serif;text-align:center}"
           ".head h3{font:700 22px/1.25 -apple-system,sans-serif;margin:0 0 4px}.x{display:inline-block;padding:1px 9px;"
           "border-radius:11px;background:#1d1a22;color:#fff;font-size:15px}.tagb,.tagf,.tagd{display:inline-block;"
           "font-size:13px;padding:2px 10px;border-radius:8px;margin-bottom:8px}.tagb{background:#e1ecfa;color:#1f4f8f}"
           ".tagf{background:#ece3f7;color:#5b3d8a}.tagd{background:#fbe7d4;color:#8a4b12}.need-row{display:flex;flex-wrap:wrap;"
           "gap:10px;margin:0 0 12px;padding:10px;background:#f6f3ee;border-radius:10px}.need-row figure{margin:0;"
           "text-align:center}.need-row img{width:96px;height:96px;border:1px solid #e4dfd6;border-radius:8px;background:#fff;"
           "display:block}.need-row figcaption{margin-top:4px;color:#1d1a22}.step ul{list-style:none;padding:0;margin:10px 0 0}"
           ".legend{display:flex;flex-wrap:wrap;gap:4px 22px}.step li{margin:4px 0;font-size:16px}.num{display:inline-block;min-width:26px;padding:0 6px;margin-right:3px;"
           "border-radius:13px;color:#fff;font:700 13px/26px ui-monospace,monospace;text-align:center}"
           ".pic{width:100%;border:1px solid #e4dfd6;border-radius:10px;background:#f6f3ee}"
           "@media(max-width:720px){.need{grid-template-columns:1fr}h1{font-size:30px}.need-row img{width:72px;height:72px}}"
           "@media print{body{background:#fff}.b3d{display:none}.step{box-shadow:none}h2{break-after:avoid}}")
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style><main>%s</main>" % (e(kit["title"]), css, "".join(rows)))
