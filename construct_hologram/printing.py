"""3D printing: a construct as one watertight body, written as STL or 3MF, with the checks a print needs.

A construct is drawn from many overlapping shapes, some of them open surfaces; a slicer wants one
closed surface. So the print is made in voxels, at the print's own scale:
  - each closed piece of a part's surface is filled by ray parity (orientation does not matter), the
    voxels whose centres are inside;
  - open surfaces (a shell, a panel), and closed pieces too thin to fill, are thickened to the wall;
  - every part is joined into one solid, and gaps between parts up to `join` wide are closed (floating
    parts, the construct's annotations, are left out); with `lines`, parts drawn only as lines become
    raised lines;
  - sealed cavities are filled (the print is solid; the slicer makes its own infill);
  - the boundary of the solid is the surface: every edge shared by exactly two triangles, edges
    touching only diagonally filled first; it is then smoothed, never by more than half a voxel, and
    each vertex within a voxel of the construct's own surface moved onto it (flat faces come out flat).

The checks: watertight, separate pieces (and those that would start in the air), fits the bed,
overhangs that need supports, what was thickened, and the scale (1:N of the real object).

Python standard library only.
"""

import math
import struct
import zipfile
from pathlib import Path

from . import product, scene as scene_mod

FORMATS = ("stl", "3mf")
SIZE_MM = 100.0            # the longest side, unless a scale is given
DETAIL_MM = 0.4            # one voxel: a common nozzle's width
WALL_MM = 0.8              # the thinnest wall printed: two lines of a 0.4 mm nozzle
JOIN_MM = 1.6              # gaps between parts up to this wide are closed, so the print is one piece
BED_MM = (250.0, 210.0, 220.0)   # a common desktop printer's build volume (Prusa MK4)
OVERHANG_DEGREES = 45.0    # steeper than this from the vertical, a downward face needs support
MAX_CELLS = 600            # voxels along the longest side, at most
SNAP_VOXELS = 1.0           # a vertex this close to the construct's surface moves onto it
SMOOTH_STEPS = 16          # Taubin passes: enough to round a cylinder's voxel steps
EPS = 1.2345e-4            # rays pass just off the voxel centres, never exactly through a vertex


class PrintError(ValueError):
    """A print that cannot be made: an unknown format, a scene with nothing to print, a size out of range."""


# ---------------------------------------------------------------------------- the construct's surfaces

def _surfaces(g, lines):
    """(closed pieces, open pieces, rods, report) in the print frame (Z up, metres): pieces are lists of
    triangles, rods are segments."""
    styles, parts = g["styles"], g["parts"]
    by_style, left_out, floating = {}, set(), set()
    f = g["fills"]
    for i in range(0, len(f), 15):
        si = int(f[i + 3])
        part = parts[int(styles[si][6])]
        if part.get("floating"):
            floating.add(part["id"])
            continue
        by_style.setdefault(si, []).append(tuple((f[i + 5 * j], -f[i + 5 * j + 2], f[i + 5 * j + 1]) for j in range(3)))
    filled = {int(styles[si][6]) for si in by_style}
    rods = []
    ln = g["lines"]
    for i in range(0, len(ln), 9):
        pi = int(styles[int(ln[i + 6])][6])
        if pi in filled:
            continue
        part = parts[pi]
        if part.get("floating"):
            floating.add(part["id"])
        elif lines:
            rods.append(((ln[i], -ln[i + 2], ln[i + 1]), (ln[i + 3], -ln[i + 5], ln[i + 4])))
        else:
            left_out.add(part["id"])
    closed, open_ = [], []
    for si, tris in by_style.items():
        pid = parts[int(styles[si][6])]["id"]
        for piece in _pieces(tris):
            (closed if _is_closed(piece) else open_).append((pid, piece))
    return closed, open_, rods, {"lines_left_out": sorted(left_out), "floating_left_out": sorted(floating)}


def _key(p):
    return (round(p[0], 7), round(p[1], 7), round(p[2], 7))


def _pieces(tris):
    """The connected pieces of a triangle list (triangles sharing a vertex)."""
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in tris:
        ks = [_key(p) for p in t]
        for k in ks[1:]:
            ra, rb = find(ks[0]), find(k)
            if ra != rb:
                parent[ra] = rb
    out = {}
    for t in tris:
        out.setdefault(find(_key(t[0])), []).append(t)
    return list(out.values())


def _is_closed(tris):
    """Every edge shared by exactly two triangles (whatever their winding)."""
    edges = {}
    for t in tris:
        ks = [_key(p) for p in t]
        if ks[0] == ks[1] or ks[1] == ks[2] or ks[0] == ks[2]:
            continue
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e = (ks[a], ks[b]) if ks[a] < ks[b] else (ks[b], ks[a])
            edges[e] = edges.get(e, 0) + 1
    return bool(edges) and all(n == 2 for n in edges.values())


# ---------------------------------------------------------------------------- voxels

class _Grid:
    """The voxel lattice (voxel sets are dicts of one Python int per (x, y) column, bit k for layer k);
    `origin` and `h` in metres."""

    def __init__(self, lo, hi, h, pad):
        self.h = h
        self.origin = tuple(lo[a] - pad * h for a in range(3))
        self.n = tuple(int(math.ceil((hi[a] - lo[a]) / h)) + 2 * pad for a in range(3))

    def to_cell(self, p):
        return tuple((p[a] - self.origin[a]) / self.h for a in range(3))


def _scan(tri, axis):
    """Where rays along `axis` through the voxel centres cross the triangle (in cell units):
    yields (a, b, depth) with a, b the cell indices of the other two axes, in axis order."""
    a_ax, b_ax = [x for x in range(3) if x != axis]
    pts = [(p[a_ax], p[b_ax], p[axis]) for p in tri]
    area = (pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) - (pts[2][0] - pts[0][0]) * (pts[1][1] - pts[0][1])
    if abs(area) < 1e-12:
        return
    b_lo, b_hi = min(p[1] for p in pts), max(p[1] for p in pts)
    for j in range(int(math.floor(b_lo - 0.5 - EPS)) + 1, int(math.floor(b_hi - 0.5 - EPS)) + 1):
        bc = j + 0.5 + EPS
        xs = []
        for u, v in ((0, 1), (1, 2), (2, 0)):
            p, q = pts[u], pts[v]
            if (p[1] <= bc) != (q[1] <= bc):
                t = (bc - p[1]) / (q[1] - p[1])
                xs.append((p[0] + t * (q[0] - p[0]), p[2] + t * (q[2] - p[2])))
        if len(xs) != 2:
            continue
        (a0, d0), (a1, d1) = sorted(xs)
        for i in range(int(math.floor(a0 - 0.5 - EPS)) + 1, int(math.floor(a1 - 0.5 - EPS)) + 1):
            ac = i + 0.5 + EPS
            yield i, j, d0 + (d1 - d0) * (ac - a0) / (a1 - a0) if a1 > a0 else d0


def _mark_surface(grid, tris, out):
    """The voxels a surface passes through, from rays along all three axes, into `out` (a column dict)."""
    for t in tris:
        c = [grid.to_cell(p) for p in t]
        for axis in range(3):
            for a, b, d in _scan(c, axis):
                k = int(math.floor(d))
                ijk = [0, 0, 0]
                rest = [x for x in range(3) if x != axis]
                ijk[rest[0]], ijk[rest[1]], ijk[axis] = a, b, k
                i, j, k = ijk
                if 0 <= i < grid.n[0] and 0 <= j < grid.n[1] and 0 <= k < grid.n[2]:
                    out[(i, j)] = out.get((i, j), 0) | (1 << k)
        # a triangle smaller than a voxel: its corners
        for p in c:
            i, j, k = (int(math.floor(x)) for x in p)
            if 0 <= i < grid.n[0] and 0 <= j < grid.n[1] and 0 <= k < grid.n[2]:
                out[(i, j)] = out.get((i, j), 0) | (1 << k)


def _fill(grid, tris, out):
    """A closed piece's inside, by the parity of vertical rays, into `out`. A column whose crossings do
    not pair up (a ray through an edge) is left to the surface."""
    hits = {}
    for t in tris:
        for i, j, d in _scan([grid.to_cell(p) for p in t], 2):
            hits.setdefault((i, j), []).append(d)
    top = grid.n[2] - 1
    for col, ds in hits.items():
        if len(ds) % 2:
            continue
        ds.sort()
        m = 0
        for z0, z1 in zip(ds[0::2], ds[1::2]):
            k0, k1 = max(int(math.ceil(z0 - 0.5)), 0), min(int(math.floor(z1 - 0.5)), top)
            if k1 >= k0:
                m |= ((1 << (k1 - k0 + 1)) - 1) << k0
        if m:
            out[col] = out.get(col, 0) | m


def _mark_rods(grid, rods, out):
    for a, b in rods:
        ca, cb = grid.to_cell(a), grid.to_cell(b)
        n = max(1, int(math.ceil(2 * max(abs(cb[x] - ca[x]) for x in range(3)))))
        for s in range(n + 1):
            p = [ca[x] + (cb[x] - ca[x]) * s / n for x in range(3)]
            i, j, k = (int(math.floor(x)) for x in p)
            if 0 <= i < grid.n[0] and 0 <= j < grid.n[1] and 0 <= k < grid.n[2]:
                out[(i, j)] = out.get((i, j), 0) | (1 << k)


def _dilate(cols, r, n):
    """Grow a voxel set by `r` voxels in every direction (a cube)."""
    full = (1 << n[2]) - 1
    for _ in range(r):
        cols = {c: (m | (m << 1) | (m >> 1)) & full for c, m in cols.items()}
        for axis in (0, 1):
            out = dict(cols)
            for (i, j), m in cols.items():
                for d in (-1, 1):
                    c = (i + d, j) if axis == 0 else (i, j + d)
                    if 0 <= c[0] < n[0] and 0 <= c[1] < n[1]:
                        out[c] = out.get(c, 0) | m
            cols = out
    return cols


def _erode(cols, r, n):
    """Shrink a voxel set by `r` voxels in every direction (the complement grown)."""
    full = (1 << n[2]) - 1
    comp = {(i, j): full & ~cols.get((i, j), 0) for i in range(n[0]) for j in range(n[1])}
    grown = _dilate(comp, r, n)
    return {c: m for c, m in ((c, full & ~grown.get(c, 0)) for c in cols) if m}


def _close(cols, r, n):
    """Close gaps and slits up to 2r voxels wide (grow, then shrink back)."""
    return _erode(_dilate(cols, r, n), r, n) if r else cols


def _fill_voids(cols, n):
    """Fill the empty space the outside cannot reach (a sealed cavity): the print is solid. Returns the
    voxels filled."""
    full = (1 << n[2]) - 1
    empty = {(i, j): _runs(full & ~cols.get((i, j), 0)) for i in range(n[0]) for j in range(n[1])}
    seen = set()
    stack = [((i, j), r) for (i, j), rs in empty.items() for r in rs
             if i in (0, n[0] - 1) or j in (0, n[1] - 1) or r[0] == 0 or r[1] == n[2] - 1]
    seen.update(stack)
    while stack:
        (i, j), (k0, k1) = stack.pop()
        for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            for r2 in empty.get(c, ()):
                if r2[0] <= k1 and r2[1] >= k0 and (c, r2) not in seen:
                    seen.add((c, r2))
                    stack.append((c, r2))
    added = 0
    for c, rs in empty.items():
        for r in rs:
            if (c, r) not in seen:
                cols[c] = cols.get(c, 0) | (((1 << (r[1] - r[0] + 1)) - 1) << r[0])
                added += r[1] - r[0] + 1
    return added


def _popcount(cols):
    return sum(bin(m).count("1") for m in cols.values())


def _union(*sets):
    out = {}
    for s in sets:
        for c, m in s.items():
            out[c] = out.get(c, 0) | m
    return out


def _manifold(cols):
    """Fill the voxels that make an edge non-manifold (two voxels meeting only along an edge), until none
    is left. Returns how many were filled."""
    added = 0
    while True:
        changed = 0
        corners = {(i + di, j + dj) for (i, j) in cols for di in (-1, 0) for dj in (-1, 0)}
        # edges along z: four columns around it
        for (i, j) in corners:
            a = cols.get((i, j), 0)
            b, c, d = cols.get((i + 1, j), 0), cols.get((i, j + 1), 0), cols.get((i + 1, j + 1), 0)
            x1 = a & d & ~b & ~c
            x2 = b & c & ~a & ~d
            if x1:
                cols[(i + 1, j)] = b | x1
                changed += bin(x1).count("1")
            if x2:
                cols[(i, j)] = cols.get((i, j), 0) | x2
                changed += bin(x2).count("1")
        # edges along y (columns side by side in x) and along x (side by side in y)
        for di, dj in ((1, 0), (0, 1)):
            for (i, j) in list(cols):
                p, q = cols.get((i, j), 0), cols.get((i + di, j + dj), 0)
                x1 = p & (q >> 1) & ~q & ~(p >> 1)        # (here, k) and (there, k+1)
                x2 = q & (p >> 1) & ~p & ~(q >> 1)        # (there, k) and (here, k+1)
                if x1:
                    cols[(i + di, j + dj)] = q | x1
                    changed += bin(x1).count("1")
                if x2:
                    cols[(i, j)] = cols.get((i, j), 0) | x2
                    changed += bin(x2).count("1")
        added += changed
        if not changed:
            return added


def _bits(m):
    k = 0
    while m:
        if m & 1:
            yield k
        m >>= 1
        k += 1


def _runs(m):
    """The runs of set bits: (first, last)."""
    out, k = [], 0
    while m:
        low = (m & -m).bit_length() - 1
        m >>= low
        k += low
        length = (~m & (m + 1)).bit_length() - 1
        out.append((k, k + length - 1))
        m >>= length
        k += length
    return out


def _bodies(cols):
    """The separate solids: a list of (voxel count, lowest layer), largest first; voxels joined by faces."""
    runs = {c: _runs(m) for c, m in cols.items() if m}
    seen, out = set(), []
    for c, rs in runs.items():
        for r in rs:
            if (c, r) in seen:
                continue
            seen.add((c, r))
            stack, size, low = [(c, r)], 0, r[0]
            while stack:
                (i, j), (k0, k1) = stack.pop()
                size += k1 - k0 + 1
                low = min(low, k0)
                for n in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    for r2 in runs.get(n, ()):
                        if r2[0] <= k1 and r2[1] >= k0 and (n, r2) not in seen:
                            seen.add((n, r2))
                            stack.append((n, r2))
            out.append((size, low))
    return sorted(out, reverse=True)


# ---------------------------------------------------------------------------- the surface

def _surface(cols, n):
    """The boundary of the voxel set as an indexed triangle mesh on the voxel lattice, wound outward."""
    verts, index, faces = [], {}, []

    def v(p):
        if p not in index:
            index[p] = len(verts)
            verts.append(p)
        return index[p]

    def quad(a, b, c, d):
        ia, ib, ic, id_ = v(a), v(b), v(c), v(d)
        faces.append((ia, ib, ic))
        faces.append((ia, ic, id_))

    for (i, j), m in cols.items():
        for k in _bits(m & ~(m >> 1)):          # top faces
            quad((i, j, k + 1), (i + 1, j, k + 1), (i + 1, j + 1, k + 1), (i, j + 1, k + 1))
        for k in _bits(m & ~(m << 1)):          # bottom faces
            quad((i, j, k), (i, j + 1, k), (i + 1, j + 1, k), (i + 1, j, k))
        for k in _bits(m & ~cols.get((i + 1, j), 0)):
            quad((i + 1, j, k), (i + 1, j + 1, k), (i + 1, j + 1, k + 1), (i + 1, j, k + 1))
        for k in _bits(m & ~cols.get((i - 1, j), 0)):
            quad((i, j, k), (i, j, k + 1), (i, j + 1, k + 1), (i, j + 1, k))
        for k in _bits(m & ~cols.get((i, j + 1), 0)):
            quad((i, j + 1, k), (i, j + 1, k + 1), (i + 1, j + 1, k + 1), (i + 1, j + 1, k))
        for k in _bits(m & ~cols.get((i, j - 1), 0)):
            quad((i, j, k), (i + 1, j, k), (i + 1, j, k + 1), (i, j, k + 1))
    return [list(p) for p in verts], faces


def _smooth(verts, faces, steps=SMOOTH_STEPS, limit=0.5):
    """Taubin smoothing (no shrinking), each vertex kept within `limit` voxels of where it started and the
    bed (the lowest layer) kept flat."""
    nbrs = [set() for _ in verts]
    for a, b, c in faces:
        nbrs[a].update((b, c))
        nbrs[b].update((a, c))
        nbrs[c].update((a, b))
    nbrs = [tuple(s) for s in nbrs]
    inv = [1.0 / len(s) for s in nbrs]
    floor = min(p[2] for p in verts)
    axes = []
    for a in range(3):
        xs = [p[a] for p in verts]
        lo, hi = [x - limit for x in xs], [x + limit for x in xs]
        if a == 2:   # the bed stays where it is
            lo = [floor if x == floor else y for x, y in zip(xs, lo)]
            hi = [floor if x == floor else y for x, y in zip(xs, hi)]
        axes.append((xs, lo, hi))
    out = []
    for xs, lo, hi in axes:
        for step in range(2 * steps):
            f = 0.5 if step % 2 == 0 else -0.53
            xs = [min(max(x + f * (sum([xs[n] for n in ns]) * w - x), l), u)
                  for x, ns, w, l, u in zip(xs, nbrs, inv, lo, hi)]
        out.append(xs)
    return [list(p) for p in zip(*out)]


def _closest(p, a, b, c):
    """The point of triangle abc nearest to p (Ericson, Real-Time Collision Detection, 5.1.5)."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    d1 = ab[0] * ap[0] + ab[1] * ap[1] + ab[2] * ap[2]
    d2 = ac[0] * ap[0] + ac[1] * ap[1] + ac[2] * ap[2]
    if d1 <= 0 and d2 <= 0:
        return a
    bp = (p[0] - b[0], p[1] - b[1], p[2] - b[2])
    d3 = ab[0] * bp[0] + ab[1] * bp[1] + ab[2] * bp[2]
    d4 = ac[0] * bp[0] + ac[1] * bp[1] + ac[2] * bp[2]
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3)
        return (a[0] + v * ab[0], a[1] + v * ab[1], a[2] + v * ab[2])
    cp = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
    d5 = ab[0] * cp[0] + ab[1] * cp[1] + ab[2] * cp[2]
    d6 = ac[0] * cp[0] + ac[1] * cp[1] + ac[2] * cp[2]
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6)
        return (a[0] + w * ac[0], a[1] + w * ac[1], a[2] + w * ac[2])
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return (b[0] + w * (c[0] - b[0]), b[1] + w * (c[1] - b[1]), b[2] + w * (c[2] - b[2]))
    den = 1.0 / (va + vb + vc)
    v, w = vb * den, vc * den
    return (a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w, a[2] + ab[2] * v + ac[2] * w)


def _snap(verts, tris, limit=SNAP_VOXELS):
    """Move each vertex onto the construct's own surface (the filled pieces') when it lies within `limit`
    voxels of it, so flat and sloping faces come out flat, not stepped; the bed stays flat."""
    cells = {}
    for ti, t in enumerate(tris):
        u = [t[1][x] - t[0][x] for x in range(3)]
        w = [t[2][x] - t[0][x] for x in range(3)]
        if sum((u[(x + 1) % 3] * w[(x + 2) % 3] - u[(x + 2) % 3] * w[(x + 1) % 3]) ** 2 for x in range(3)) < 1e-18:
            continue   # no area: nothing to land on
        for axis in range(3):
            rest = [x for x in range(3) if x != axis]
            for a, b, d in _scan(t, axis):
                ijk = [0, 0, 0]
                ijk[rest[0]], ijk[rest[1]], ijk[axis] = a, b, int(math.floor(d))
                cells.setdefault(tuple(ijk), set()).add(ti)
        for q in t:
            cells.setdefault(tuple(int(math.floor(x)) for x in q), set()).add(ti)
    floor = min(p[2] for p in verts)
    near = [(di, dj, dk) for di in (-1, 0, 1) for dj in (-1, 0, 1) for dk in (-1, 0, 1)]
    lim2 = limit * limit
    out = []
    for p in verts:
        ci, cj, ck = int(math.floor(p[0])), int(math.floor(p[1])), int(math.floor(p[2]))
        cand = set()
        for di, dj, dk in near:
            cand |= cells.get((ci + di, cj + dj, ck + dk), set())
        best, best_d = None, lim2
        for ti in cand:
            q = _closest(p, *tris[ti])
            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
            if d < best_d:
                best, best_d = q, d
        if best is None:
            out.append(p)
        else:
            out.append([best[0], best[1], floor if p[2] == floor else best[2]])
    return out


def _edges_ok(faces):
    """(open or over-shared edges, shared the wrong way): both 0 for a watertight, consistently wound surface."""
    edges = {}
    for a, b, c in faces:
        for u, w in ((a, b), (b, c), (c, a)):
            edges[(u, w)] = edges.get((u, w), 0) + 1
    bad = sum(1 for (u, w), n in edges.items() if n != 1 or edges.get((w, u), 0) != 1)
    return bad


# ---------------------------------------------------------------------------- the print

def make(scene, size=SIZE_MM, scale=None, detail=DETAIL_MM, wall=WALL_MM, join=JOIN_MM, lines=False, bed=BED_MM):
    """The print of `scene`: {"vertices": [[x, y, z] mm], "triangles": [[a, b, c]], "report": {...}}.
    `size` is the longest side in mm, or `scale` N prints at 1:N of the construct's real size; gaps up to
    `join` mm wide are closed."""
    if not detail > 0 or not wall > 0 or join < 0:
        raise PrintError("detail and wall: positive numbers of millimetres; join: 0 or more")
    g = scene_mod.compile_scene(scene, solid=True)
    closed, open_, rods, report = _surfaces(g, lines)
    if not closed and not open_ and not rods:
        raise PrintError("nothing to print: the construct has no surfaces (try --lines for one drawn in lines)")
    pts = [p for _, piece in closed + open_ for t in piece for p in t] + [p for r in rods for p in r]
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    longest = max(hi[a] - lo[a] for a in range(3))
    if not longest > 0:
        raise PrintError("nothing to print: the construct has no extent")
    if scale is not None:
        if not scale > 0:
            raise PrintError("scale: a positive N, for 1:N")
        mm_per_m = 1000.0 / scale
    else:
        if not size > 0:
            raise PrintError("size: a positive number of millimetres")
        mm_per_m = size / longest
    cells = longest * mm_per_m / detail
    if cells > MAX_CELLS:
        raise PrintError("%.0f voxels along the longest side (at most %d): use a coarser --detail (at least %.2f mm)"
                         " or a smaller print" % (cells, MAX_CELLS, longest * mm_per_m / MAX_CELLS))
    h = detail / mm_per_m
    r = max(1, int(math.ceil(wall / detail / 2.0 - 0.25)))
    rj = int(round(join / detail / 2.0))
    grid = _Grid(lo, hi, h, r + rj + 2)
    solid, shells, thickened, true = {}, {}, set(), []
    for pid, piece in closed:   # filled where the voxel centres are inside; too thin for that, a shell
        inside, surface = {}, {}
        _fill(grid, piece, inside)
        _mark_surface(grid, piece, surface)
        if _popcount(inside) >= _popcount(surface):
            for c, m in inside.items():
                solid[c] = solid.get(c, 0) | m
            true.extend(piece)
        else:
            for c, m in surface.items():
                shells[c] = shells.get(c, 0) | m
            thickened.add(pid)
    for pid, piece in open_:
        _mark_surface(grid, piece, shells)
        thickened.add(pid)
    report["thickened"] = sorted(thickened)
    _mark_rods(grid, rods, shells)
    if shells:
        shells = _dilate(shells, r, grid.n)
    cols = _close({c: m for c, m in _union(solid, shells).items() if m}, rj, grid.n)
    voids = _fill_voids(cols, grid.n)
    filled = _manifold(cols)
    # the bed: the lowest layer at z = 0
    low = min((m & -m).bit_length() - 1 for m in cols.values())
    if low:
        cols = {c: m >> low for c, m in cols.items()}
    bodies = _bodies(cols)
    verts, faces = _surface(cols, grid.n)
    verts = _smooth(verts, faces)
    verts = _snap(verts, [[(q[0], q[1], q[2] - low) for q in map(grid.to_cell, t)] for t in true])
    i0 = min(c[0] for c in cols)
    j0 = min(c[1] for c in cols)
    verts = [[(p[0] - i0) * detail, (p[1] - j0) * detail, p[2] * detail] for p in verts]
    extent = [max(p[a] for p in verts) - min(p[a] for p in verts) for a in range(3)]
    report.update(_checks(verts, faces, bodies, extent, bed))
    report.update({"size_mm": [round(x, 1) for x in extent], "scale": "1:%s" % _ratio(1000.0 / mm_per_m),
                   "detail_mm": detail, "wall_mm": wall, "join_mm": join, "voxels": sum(b[0] for b in bodies),
                   "filled_for_manifold": filled, "cavities_filled": voids, "triangles": len(faces)})
    return {"vertices": verts, "triangles": faces, "report": report, "title": g["title"]}


def _ratio(n):
    return ("%.0f" % n) if n >= 10 else ("%.1f" % n).rstrip("0").rstrip(".")


def _checks(verts, faces, bodies, extent, bed):
    bad = _edges_ok(faces)
    cos_o = math.cos(math.radians(OVERHANG_DEGREES))
    over = down = 0.0
    floor_area = 0.0
    for a, b, c in faces:
        p, q, r = verts[a], verts[b], verts[c]
        u = [q[x] - p[x] for x in range(3)]
        w = [r[x] - p[x] for x in range(3)]
        nx, ny, nz = u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]
        area = math.sqrt(nx * nx + ny * ny + nz * nz) / 2
        if not area:
            continue
        if p[2] == q[2] == r[2] == 0.0:
            floor_area += area
            continue
        if nz < 0:
            down += area
            if -nz / (2 * area) > cos_o:
                over += area
    pieces = len(bodies)
    in_air = sum(1 for _, low in bodies if low > 0)
    fits = all(e <= b for e, b in zip(sorted(extent[:2], reverse=True) + [extent[2]],
                                       sorted(bed[:2], reverse=True) + [bed[2]]))
    return {"watertight": bad == 0, "bad_edges": bad, "pieces": pieces, "pieces_in_air": in_air,
            "fits_bed": fits, "bed_mm": list(bed), "on_bed_mm2": round(floor_area, 1),
            "overhang_mm2": round(over, 1), "needs_supports": over > 0.02 * max(down, 1e-9) and over > 1.0}


def notes(report):
    """The report in plain sentences, problems first."""
    out = []
    if not report["watertight"]:
        out.append("NOT watertight: %d edges are open or shared by more than two triangles" % report["bad_edges"])
    if report["pieces_in_air"]:
        out.append("%d of %d pieces would start in the air: print with supports, or close wider gaps (--join)"
                   % (report["pieces_in_air"], report["pieces"]))
    elif report["pieces"] > 1:
        out.append("%d separate pieces, all on the bed" % report["pieces"])
    if not report["fits_bed"]:
        out.append("does not fit a %s mm bed: print smaller (--size) or cut it" % "x".join("%g" % b for b in report["bed_mm"]))
    if report["needs_supports"]:
        out.append("overhangs need supports (%.0f mm2 face down steeper than %g degrees)"
                   % (report["overhang_mm2"], OVERHANG_DEGREES))
    if report["thickened"]:
        out.append("thickened to the %g mm wall: %s" % (report["wall_mm"], _list(report["thickened"])))
    if report["lines_left_out"]:
        out.append("drawn only in lines, not printed (--lines prints them raised): %s" % _list(report["lines_left_out"]))
    if report["floating_left_out"]:
        out.append("annotations, not printed: %s" % _list(report["floating_left_out"]))
    out.append("watertight" if report["watertight"] else "")
    return [x for x in out if x]


def _list(ids, most=6):
    return ", ".join(ids[:most]) + (" and %d more" % (len(ids) - most) if len(ids) > most else "")


# ---------------------------------------------------------------------------- files

def to_stl(p):
    """A binary STL (millimetres)."""
    v = p["vertices"]
    head = ("%s %s: %s" % (product.TITLE, product.VERSION, p["title"])).encode("ascii", "replace")[:80]
    out = [head.ljust(80, b" "), struct.pack("<I", len(p["triangles"]))]
    for a, b, c in p["triangles"]:
        pa, pb, pc = v[a], v[b], v[c]
        u = [pb[x] - pa[x] for x in range(3)]
        w = [pc[x] - pa[x] for x in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        ln = math.sqrt(sum(x * x for x in n)) or 1.0
        out.append(struct.pack("<12fH", n[0] / ln, n[1] / ln, n[2] / ln, *pa, *pb, *pc, 0))
    return b"".join(out)


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def to_3mf(p):
    """A 3MF package (millimetres): one object, the construct's title and scale as metadata."""
    v = ["<vertex x=\"%.4f\" y=\"%.4f\" z=\"%.4f\"/>" % tuple(q) for q in p["vertices"]]
    t = ["<triangle v1=\"%d\" v2=\"%d\" v3=\"%d\"/>" % f for f in p["triangles"]]
    model = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        ' <metadata name="Title">%s</metadata>' % _xml(p["title"]),
        ' <metadata name="Application">%s %s</metadata>' % (product.TITLE, product.VERSION),
        ' <metadata name="Description">%s</metadata>' % _xml("Printed at %s; %s" % (
            p["report"]["scale"], "watertight" if p["report"]["watertight"] else "not watertight")),
        ' <resources>', '  <object id="1" type="model" name="%s">' % _xml(p["title"]), '   <mesh>',
        '    <vertices>', "\n".join(v), '    </vertices>', '    <triangles>', "\n".join(t), '    </triangles>',
        '   </mesh>', '  </object>', ' </resources>', ' <build>', '  <item objectid="1"/>', ' </build>', '</model>', ""])
    types = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '</Types>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>\n')
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
    return buf.getvalue()


def write(scene, path, fmt=None, **kw):
    """Make the print of `scene` and write it to `path` (.stl or .3mf). Returns the report."""
    path = Path(path)
    fmt = fmt or path.suffix.lower().lstrip(".")
    if fmt not in FORMATS:
        raise PrintError("format: stl or 3mf (from --format or the file's extension), not %r" % fmt)
    p = make(scene, **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_stl(p) if fmt == "stl" else to_3mf(p))
    return dict(p["report"], format=fmt, files=[str(path)])
