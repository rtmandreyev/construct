"""3D printing: a construct as one watertight body, written as STL or 3MF, with the checks a print needs.

A construct is drawn from many overlapping shapes, some of them open surfaces; a slicer wants one
closed surface. So the print is made in voxels, at the print's own scale:
  - each closed piece of a part's surface is filled by ray parity (orientation does not matter), the
    voxels whose centres are inside;
  - open surfaces (a shell, a panel), and closed pieces too thin to fill, are thickened to the wall;
  - every part is joined into one solid, and gaps between parts up to `join` wide are closed (floating
    parts, the construct's annotations, are left out); parts drawn only as lines are left out, cut into
    the surface as grooves (`lines="engrave"`, like a model kit's panel lines) or raised (`"raised"`);
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
MAX_CELLS = 900            # voxels along the longest side, at most (900: a 36 cm print at 0.4 mm, ~3 min, ~3 GB)

# printer classes: the build volume (mm), the finest voxel worth printing (mm) and the thinnest wall (mm). Classes,
# not models: a printer's own numbers can go in --bed, --detail and --wall.
PRINTERS = {
    "small": {"label": "a small FDM printer (Bambu Lab A1 mini class)", "kind": "FDM",
              "bed": (180.0, 180.0, 180.0), "detail": 0.4, "wall": 0.8},
    "desktop": {"label": "a desktop FDM printer (Prusa MK4 class)", "kind": "FDM",
                "bed": (250.0, 210.0, 220.0), "detail": 0.4, "wall": 0.8},
    "cube": {"label": "a 256 mm FDM printer (Bambu Lab X1, P1 and A1 class)", "kind": "FDM",
             "bed": (256.0, 256.0, 256.0), "detail": 0.4, "wall": 0.8},
    "large": {"label": "a large FDM printer (Prusa XL, Creality K2 Plus class)", "kind": "FDM",
              "bed": (350.0, 350.0, 350.0), "detail": 0.4, "wall": 0.8},
    "resin": {"label": "a resin printer (10-inch class)", "kind": "resin",
              "bed": (218.0, 122.0, 220.0), "detail": 0.05, "wall": 0.4},
}
FIT_MARGIN = 0.96          # a fitted print leaves this much of the bed (a brim, a skirt)
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


def _drop_specks(cols, smallest=32):
    """Remove the separate solids smaller than `smallest` voxels (slivers left between grooves): too small to
    print, and each would be a piece of its own."""
    runs = {c: _runs(m) for c, m in cols.items() if m}
    seen = set()
    for c, rs in runs.items():
        for r in rs:
            if (c, r) in seen:
                continue
            seen.add((c, r))
            stack, members, size = [(c, r)], [], 0
            while stack:
                (i, j), (k0, k1) = item = stack.pop()
                members.append(item)
                size += k1 - k0 + 1
                for n in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    for r2 in runs.get(n, ()):
                        if r2[0] <= k1 and r2[1] >= k0 and (n, r2) not in seen:
                            seen.add((n, r2))
                            stack.append((n, r2))
            if size < smallest:
                for col, (k0, k1) in members:
                    cols[col] &= ~(((1 << (k1 - k0 + 1)) - 1) << k0)
    return {c: m for c, m in cols.items() if m}


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


def _surface_flat(cols):
    """The same boundary as `_surface`, with each row of a flat face merged into one strip: far fewer
    triangles for plates and slabs. Every lattice point another face uses on a strip's edge is kept on it,
    so the surface stays watertight (no T-junctions)."""
    import bisect
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

    rows = {}   # (+1 top or -1 bottom, z, j) -> the cells' i
    for (i, j), m in cols.items():
        for k in _bits(m & ~(m >> 1)):
            rows.setdefault((1, k + 1, j), []).append(i)
        for k in _bits(m & ~(m << 1)):
            rows.setdefault((-1, k, j), []).append(i)
        for k in _bits(m & ~cols.get((i + 1, j), 0)):
            quad((i + 1, j, k), (i + 1, j + 1, k), (i + 1, j + 1, k + 1), (i + 1, j, k + 1))
        for k in _bits(m & ~cols.get((i - 1, j), 0)):
            quad((i, j, k), (i, j, k + 1), (i, j + 1, k + 1), (i, j + 1, k))
        for k in _bits(m & ~cols.get((i, j + 1), 0)):
            quad((i, j + 1, k), (i, j + 1, k + 1), (i + 1, j + 1, k + 1), (i + 1, j + 1, k))
        for k in _bits(m & ~cols.get((i, j - 1), 0)):
            quad((i, j, k), (i + 1, j, k), (i + 1, j, k + 1), (i, j, k + 1))
    on_line = {}   # (y, z) -> the x of every lattice point the walls use
    for x, y, z in verts:
        on_line.setdefault((y, z), set()).add(x)
    on_line = {k: sorted(xs) for k, xs in on_line.items()}
    runs = {}
    for key, xs in rows.items():
        xs.sort()
        rs, start = [], xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b != a + 1:
                rs.append((start, a + 1))
                start = b
        runs[key] = rs

    def edge(key, y, x0, x1, other):
        pts = {x0, x1}
        line = on_line.get((y, key[1]), ())
        lo = bisect.bisect_right(line, x0)
        while lo < len(line) and line[lo] < x1:
            pts.add(line[lo])
            lo += 1
        for r0, r1 in runs.get(other, ()):
            if x0 < r0 < x1:
                pts.add(r0)
            if x0 < r1 < x1:
                pts.add(r1)
        return sorted(pts)

    for key, rs in runs.items():
        up, z, j = key
        for x0, x1 in rs:
            lo = edge(key, j, x0, x1, (up, z, j - 1))
            hi = edge(key, j + 1, x0, x1, (up, z, j + 1))
            a = b = 0
            while a < len(lo) - 1 or b < len(hi) - 1:
                if b == len(hi) - 1 or (a < len(lo) - 1 and lo[a + 1] <= hi[b + 1]):
                    tri = (v((lo[a], j, z)), v((lo[a + 1], j, z)), v((hi[b], j + 1, z)))
                    a += 1
                else:
                    tri = (v((lo[a], j, z)), v((hi[b + 1], j + 1, z)), v((hi[b], j + 1, z)))
                    b += 1
                faces.append(tri if up > 0 else (tri[0], tri[2], tri[1]))
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


def _snap(verts, tris, limit=SNAP_VOXELS, keep=()):
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
    for n, p in enumerate(verts):
        if n in keep:
            out.append(p)
            continue
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

LINES = ("none", "engrave", "raised")


def _extent(closed, open_, rods):
    pts = [p for _, piece in closed + open_ for t in piece for p in t] + [p for r in rods for p in r]
    if not pts:
        return None, None
    return [min(p[a] for p in pts) for a in range(3)], [max(p[a] for p in pts) for a in range(3)]


def fit_mm_per_m(dims_m, bed, margin=FIT_MARGIN):
    """The largest scale (mm of print per metre of object) at which an object of `dims_m` (the print frame: width,
    depth, height) stands on `bed` (width, depth, height mm): turned on the bed as it fits best, never laid down."""
    foot = sorted(dims_m[:2], reverse=True)
    plate = sorted(bed[:2], reverse=True)
    inf = float("inf")
    return min(plate[0] / foot[0] if foot[0] else inf, plate[1] / foot[1] if foot[1] else inf,
               bed[2] / dims_m[2] if dims_m[2] else inf) * margin


def printers(scene, lines="none", wall=None):
    """For each printer class: the largest print of `scene` that stands on it, the voxel it allows, the smallest
    feature of the real object that survives, and how many parts print as themselves (kept), only thicker than they
    are (thickened, a panel or a rod under the wall) or barely at all (lost, under two voxels)."""
    g = scene_mod.compile_scene(scene, solid=True)
    lines = {True: "raised", False: "none", None: "none"}.get(lines, lines)
    closed, open_, rods, _ = _surfaces(g, lines != "none")
    lo, hi = _extent(closed, open_, rods)
    if lo is None:
        raise PrintError("nothing to print: the construct has no surfaces (try --lines raised for one drawn in lines)")
    dims = [hi[a] - lo[a] for a in range(3)]
    longest = max(dims)
    printed = {pid for pid, _ in closed + open_}
    boxes = []
    for p in g["parts"]:
        if p["id"] in printed and p["instances"]:
            b = p["instances"][0]
            boxes.append(sorted(b["max"][a] - b["min"][a] for a in range(3)))
    out = []
    for name, pr in PRINTERS.items():
        mm = fit_mm_per_m(dims, pr["bed"])
        detail = max(pr["detail"], math.ceil(longest * mm / MAX_CELLS * 1000) / 1000.0)
        w = wall if wall is not None else pr["wall"]
        lost = sum(1 for b in boxes if b[2] * mm < 2 * detail)
        thick = sum(1 for b in boxes if b[2] * mm >= 2 * detail and b[0] * mm < w)
        out.append({"printer": name, "label": pr["label"], "kind": pr["kind"], "bed_mm": list(pr["bed"]),
                    "scale": "1:%s" % _ratio(1000.0 / mm), "size_mm": [round(d * mm, 1) for d in dims],
                    "detail_mm": detail, "limited_by_grid": detail > pr["detail"],
                    "smallest_real_mm": round(detail * 1000.0 / mm, 1), "parts": len(boxes),
                    "kept": len(boxes) - lost - thick, "thickened": thick, "lost": lost})
    return out


def make(scene, size=SIZE_MM, scale=None, detail=DETAIL_MM, wall=WALL_MM, join=JOIN_MM, lines="none", bed=BED_MM,
         fit=False, coarsen=False, exact=False):
    """The print of `scene`: {"vertices": [[x, y, z] mm], "triangles": [[a, b, c]], "report": {...}}.
    `size` is the longest side in mm, or `scale` N prints at 1:N of the construct's real size, or `fit` the largest
    that stands on `bed`; gaps up to `join` mm wide are closed. `coarsen`: a voxel finer than the grid allows is
    widened (and the report says so) rather than refused. `exact`: the construct's own closed solids, as they are, as
    parts of one object the slicer joins (only open and too-thin surfaces go through the voxels); 3MF only."""
    if not detail > 0 or not wall > 0 or join < 0:
        raise PrintError("detail and wall: positive numbers of millimetres; join: 0 or more")
    g = scene_mod.compile_scene(scene, solid=True)
    lines = {True: "raised", False: "none", None: "none"}.get(lines, lines)
    if lines not in LINES:
        raise PrintError("lines: one of %s" % ", ".join(LINES))
    closed, open_, rods, report = _surfaces(g, lines != "none")
    if not closed and not open_ and not rods:
        raise PrintError("nothing to print: the construct has no surfaces (try --lines raised for one drawn in lines)")
    lo, hi = _extent(closed, open_, rods)
    longest = max(hi[a] - lo[a] for a in range(3))
    if not longest > 0:
        raise PrintError("nothing to print: the construct has no extent")
    if fit:
        mm_per_m = fit_mm_per_m([hi[a] - lo[a] for a in range(3)], bed)
    elif scale is not None:
        if not scale > 0:
            raise PrintError("scale: a positive N, for 1:N")
        mm_per_m = 1000.0 / scale
    else:
        if not size > 0:
            raise PrintError("size: a positive number of millimetres")
        mm_per_m = size / longest
    cells = longest * mm_per_m / detail
    asked = detail
    if cells > MAX_CELLS and coarsen:
        detail = math.ceil(longest * mm_per_m / MAX_CELLS * 1000) / 1000.0
        cells = longest * mm_per_m / detail
    if cells > MAX_CELLS:
        raise PrintError("%.0f voxels along the longest side (at most %d): use a coarser --detail (at least %.2f mm)"
                         " or a smaller print" % (cells, MAX_CELLS, longest * mm_per_m / MAX_CELLS))
    h = detail / mm_per_m
    r = max(1, int(math.ceil(wall / detail / 2.0 - 0.25)))
    rj = int(round(join / detail / 2.0))
    grid = _Grid(lo, hi, h, r + rj + 2)
    solid, shells, thickened, true, kept = {}, {}, set(), [], []
    if exact and lines == "engrave":
        raise PrintError("engraving cuts into the voxel print: an exact print takes lines none or raised")
    wall_m, voxeled = wall / mm_per_m, set()
    for pid, piece in closed:   # filled where the voxel centres are inside; too thin for that, a shell
        inside, surface = {}, {}
        _fill(grid, piece, inside)
        _mark_surface(grid, piece, surface)
        if _popcount(inside) >= _popcount(surface) and exact:
            kept.append((pid, piece))
        elif _popcount(inside) >= _popcount(surface):
            for c, m in inside.items():
                solid[c] = solid.get(c, 0) | m
            true.extend(piece)
        else:
            grown = _inflate(piece, wall_m) if exact else None   # exact: its own shape, grown to the wall
            if grown:
                kept.append((pid, grown))
            else:
                for c, m in surface.items():
                    shells[c] = shells.get(c, 0) | m
                voxeled.add(pid)
            thickened.add(pid)
    for pid, piece in open_:
        shell = _solidify(piece, wall_m) if exact else None    # exact: a true shell, the wall thick
        if shell:
            kept.append((pid, shell))
        else:
            _mark_surface(grid, piece, shells)
            voxeled.add(pid)
        thickened.add(pid)
    report["thickened"] = sorted(thickened)
    if exact:
        report["thickened_in_voxels"] = sorted(voxeled)
    grooves = {}
    _mark_rods(grid, rods, grooves if lines == "engrave" else shells)
    if exact:
        return _exact(g, kept, shells, grid, lo, mm_per_m, detail, r, rj, bed, report,
                      {"detail_mm": detail, "detail_asked_mm": asked, "wall_mm": wall, "join_mm": join})
    if shells:
        shells = _dilate(shells, r, grid.n)
    cols = _close({c: m for c, m in _union(solid, shells).items() if m}, rj, grid.n)
    voids = _fill_voids(cols, grid.n)
    if grooves:   # the line art cut into the surface, as a model kit's panel lines: one voxel deep, and only
        # where there is solid behind it, so a groove never cuts a thin part through
        grooves = _dilate(grooves, 1, grid.n)
        backed = _dilate(_erode(cols, 1, grid.n), 1, grid.n)
        cut = {}
        for c, m in grooves.items():
            m &= cols.get(c, 0) & backed.get(c, 0)
            if m:
                cut[c] = m
                cols[c] &= ~m
        grooves = cut
        cols = _drop_specks({c: m for c, m in cols.items() if m})
    filled = _manifold(cols)
    # the bed: the lowest layer at z = 0
    low = min((m & -m).bit_length() - 1 for m in cols.values())
    if low:
        cols = {c: m >> low for c, m in cols.items()}
    bodies = _bodies(cols)
    verts, faces = _surface(cols, grid.n)
    cut = {(i, j, k - low) for (i, j), m in grooves.items() for k in _bits(m)} if grooves else set()
    keep = {n for n, (x, y, z) in enumerate(verts)   # a groove's corners stay sharp: not snapped back to the surface
            if any((x - a, y - b, z - c) in cut for a in (0, 1) for b in (0, 1) for c in (0, 1))} if cut else set()
    verts = _smooth(verts, faces)
    verts = _snap(verts, [[(q[0], q[1], q[2] - low) for q in map(grid.to_cell, t)] for t in true], keep=keep)
    i0 = min(c[0] for c in cols)
    j0 = min(c[1] for c in cols)
    verts = [[(p[0] - i0) * detail, (p[1] - j0) * detail, p[2] * detail] for p in verts]
    extent = [max(p[a] for p in verts) - min(p[a] for p in verts) for a in range(3)]
    if _turned([verts], extent, bed):
        extent = [extent[1], extent[0], extent[2]]
        report["turned"] = True
    report.update(_checks(verts, faces, bodies, extent, bed))
    report.update({"size_mm": [round(x, 1) for x in extent], "scale": "1:%s" % _ratio(1000.0 / mm_per_m),
                   "detail_mm": detail, "detail_asked_mm": asked, "wall_mm": wall, "join_mm": join,
                   "smallest_real_mm": round(detail * 1000.0 / mm_per_m, 1), "voxels": sum(b[0] for b in bodies),
                   "filled_for_manifold": filled, "cavities_filled": voids, "triangles": len(faces)})
    return {"vertices": verts, "triangles": faces, "report": report, "title": g["title"]}


def _fits(extent, bed):
    return extent[0] <= bed[0] and extent[1] <= bed[1] and extent[2] <= bed[2]


def _turned(meshes, extent, bed):
    """Turn the print a quarter on the bed (about Z, so windings keep) when it fits only that way; in place.
    True if turned."""
    if _fits(extent, bed) or not _fits((extent[1], extent[0], extent[2]), bed):
        return False
    for verts in meshes:
        for p in verts:
            p[0], p[1] = p[1], extent[0] - p[0]
    return True


def _orient(verts, faces):
    """Wind a closed surface one way, then outward: neighbours agree across every edge (a walk from triangle to
    triangle, flipping as it goes), and the enclosed volume comes out positive."""
    by_edge = {}
    for n, (a, b, c) in enumerate(faces):
        for u, w in ((a, b), (b, c), (c, a)):
            by_edge.setdefault((min(u, w), max(u, w)), []).append(n)
    faces = [list(t) for t in faces]
    done = [False] * len(faces)
    for start in range(len(faces)):
        if done[start]:
            continue
        done[start], todo = True, [start]
        while todo:
            n = todo.pop()
            a, b, c = faces[n]
            for u, w in ((a, b), (b, c), (c, a)):
                for m in by_edge[(min(u, w), max(u, w))]:
                    if m == n or done[m]:
                        continue
                    x, y, z = faces[m]
                    if (u, w) in ((x, y), (y, z), (z, x)):   # the same direction twice: flip the neighbour
                        faces[m] = [x, z, y]
                    done[m] = True
                    todo.append(m)
    vol = 0.0
    for a, b, c in faces:
        p, q, r = verts[a], verts[b], verts[c]
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0]))
    return [[a, c, b] for a, b, c in faces] if vol < 0 else faces


def _weld(tris):
    """(points, faces) of a triangle list, corners that meet welded; degenerate triangles dropped."""
    index, pts, faces = {}, [], []
    for t in tris:
        f = []
        for p in t:
            k = _key(p)
            if k not in index:
                index[k] = len(pts)
                pts.append(tuple(p))
            f.append(index[k])
        if len(set(f)) == 3:
            faces.append(f)
    return pts, faces


def _offsets(pts, faces):
    """Per point, the move that carries each face around it out by one unit along its normal (least squares
    over the faces, weighted by area; directions no face constrains are left alone): flat ground moves along
    its normal, an edge along both faces, a box's corner along its diagonal, so walls keep their thickness at
    edges and corners. None where the faces disagree too much (a crease folded back)."""
    acc = [[0.0] * 9 + [0.0] * 3 for _ in pts]
    for a, b, c in faces:
        p, q, r = pts[a], pts[b], pts[c]
        u = [q[i] - p[i] for i in range(3)]
        v = [r[i] - p[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        area = math.sqrt(sum(x * x for x in n))
        if not area > 0:
            continue
        n = [x / area for x in n]
        for i in (a, b, c):
            m = acc[i]
            for j in range(3):
                for k in range(3):
                    m[3 * j + k] += area * n[j] * n[k]
                m[9 + j] += area * n[j]
    out = []
    for m in acc:
        w = m[0] + m[4] + m[8]
        if not w > 0:
            out.append(None)
            continue
        vals, vecs = _eigen3([[m[3 * j + k] for k in range(3)] for j in range(3)])
        bvec = m[9:12]
        top = max(vals)
        sol = [0.0, 0.0, 0.0]
        for lam, u in zip(vals, vecs):   # the least-squares move, leaving out only directions no face constrains
            if lam > 1e-6 * top:
                k = sum(u[j] * bvec[j] for j in range(3)) / lam
                sol = [sol[j] + k * u[j] for j in range(3)]
        if not 0 < sum(x * x for x in sol) <= 9.0:
            sol = _damped(m, w)   # a tight curve (a spring's coil): rounding drives the exact move astray
        out.append(sol if sol and sum(x * x for x in sol) <= 9.0 else None)   # more than 3x the wall: a fold
    return out


def _damped(m, w):
    """The least-squares move with a little damping, scaled back so the faces move one unit on average: steady
    where the faces around a point barely differ, a little short at a thin part's edges."""
    A = [[m[3 * j + k] + (1e-3 * w if j == k else 0.0) for k in range(3)] for j in range(3)]
    bvec = m[9:12]
    det3 = lambda M: (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
                      + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
    det = det3(A)
    if abs(det) < 1e-12 * w ** 3:
        return None
    sol = [det3([[bvec[j] if k == col else A[j][k] for k in range(3)] for j in range(3)]) / det for col in range(3)]
    mv = [sum(m[3 * j + k] * sol[k] for k in range(3)) for j in range(3)]
    vmv = sum(sol[j] * mv[j] for j in range(3))
    return [x * sum(sol[j] * bvec[j] for j in range(3)) / vmv for x in sol] if vmv > 0 else None


def _eigen3(a):
    """Eigenvalues and unit eigenvectors of a symmetric 3x3 matrix (Jacobi rotations)."""
    a = [row[:] for row in a]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _ in range(32):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda ij: abs(a[ij[0]][ij[1]]))
        if abs(a[p][q]) < 1e-15 * (abs(a[0][0]) + abs(a[1][1]) + abs(a[2][2]) + 1e-300):
            break
        theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
        t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
        c = 1.0 / math.sqrt(t * t + 1.0)
        s = t * c
        for k in range(3):   # A = A J, then A = J^T A
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    return [a[i][i] for i in range(3)], [[v[k][i] for k in range(3)] for i in range(3)]


def _edge_uses(faces):
    uses = {}
    for a, b, c in faces:
        for u, w in ((a, b), (b, c), (c, a)):
            uses.setdefault((min(u, w), max(u, w)), []).append((u, w))
    return uses


def _solidify(tris, wall):
    """An open surface as a closed shell `wall` thick (metres), half to each side, closed along its open edges:
    what a slicer can print, and what the surface looks like. None when it is not a simple surface (an edge
    shared by three faces, a fold) and must go through the voxels instead."""
    pts, faces = _weld(tris)
    if not faces:
        return None
    uses = _edge_uses(faces)
    if any(len(u) > 2 for u in uses.values()):
        return None
    faces = _orient(pts, faces)
    offs = _offsets(pts, faces)
    if any(o is None for o in offs):
        return None
    h = wall / 2.0
    outer = [tuple(p[i] + o[i] * h for i in range(3)) for p, o in zip(pts, offs)]
    inner = [tuple(p[i] - o[i] * h for i in range(3)) for p, o in zip(pts, offs)]
    out = [(outer[a], outer[b], outer[c]) for a, b, c in faces] + [(inner[a], inner[c], inner[b]) for a, b, c in faces]
    for (a, b), (u, w) in ((k, v[0]) for k, v in _edge_uses(faces).items() if len(v) == 1):
        out += [(outer[w], outer[u], inner[u]), (outer[w], inner[u], inner[w])]   # the wall along an open edge
    return out


def _inflate(tris, wall):
    """A closed solid too thin to print, grown so that its thinnest wall is at least `wall` (metres), barely
    more (its thickness is estimated from its volume and area, which never overstates it): its own shape, a
    little fuller. None when its surface folds."""
    pts, faces = _weld(tris)
    if not faces or any(len(u) != 2 for u in _edge_uses(faces).values()):
        return None
    faces = _orient(pts, faces)
    area = vol = 0.0
    for a, b, c in faces:
        p, q, r = pts[a], pts[b], pts[c]
        u = [q[i] - p[i] for i in range(3)]
        v = [r[i] - p[i] for i in range(3)]
        area += 0.5 * math.sqrt((u[1] * v[2] - u[2] * v[1]) ** 2 + (u[2] * v[0] - u[0] * v[2]) ** 2 + (u[0] * v[1] - u[1] * v[0]) ** 2)
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6.0
    thick = 2.0 * vol / area if area > 0 else 0.0   # a slab's thickness, a rod's half-diameter: thin either way
    grow = max(0.0, (wall - thick) / 2.0)
    offs = _offsets(pts, faces)
    if any(o is None for o in offs):
        return None
    moved = [tuple(p[i] + o[i] * grow for i in range(3)) for p, o in zip(pts, offs)]
    return [(moved[a], moved[b], moved[c]) for a, b, c in faces]


def _exact(g, kept, shells, grid, lo, mm_per_m, detail, r, rj, bed, report, extra):
    """The exact print: each closed piece as it is, one mesh each, and the thickened surfaces as one more; in
    millimetres, on the bed at z = 0."""
    objects = []
    for pid, piece in kept:
        index, verts, faces = {}, [], []
        for t in piece:
            tri = []
            for p in t:
                k = _key(p)
                if k not in index:
                    index[k] = len(verts)
                    verts.append([(p[a] - lo[a]) * mm_per_m for a in range(3)])
                tri.append(index[k])
            if len(set(tri)) == 3:
                faces.append(tri)
        objects.append({"name": pid, "vertices": verts, "triangles": _orient(verts, faces)})
    if shells:
        cols = _close({c: m for c, m in _dilate(shells, r, grid.n).items() if m}, rj, grid.n)
        _fill_voids(cols, grid.n)
        _manifold(cols)
        verts, faces = _surface(cols, grid.n)
        verts = _smooth(verts, faces)
        off = [(grid.origin[a] - lo[a]) * mm_per_m for a in range(3)]
        objects.append({"name": "thickened surfaces", "vertices": [[off[a] + p[a] * detail for a in range(3)] for p in verts],
                        "triangles": faces})
    if not objects:
        raise PrintError("nothing to print")
    low = [min(p[a] for o in objects for p in o["vertices"]) for a in range(3)]
    for o in objects:
        o["vertices"] = [[p[a] - low[a] for a in range(3)] for p in o["vertices"]]
    span = [max(p[a] for o in objects for p in o["vertices"]) for a in range(3)]
    if _turned([o["vertices"] for o in objects], span, bed):
        report["turned"] = True
    boxes = [[[min(p[a] for p in o["vertices"]) for a in range(3)], [max(p[a] for p in o["vertices"]) for a in range(3)]]
             for o in objects]
    # pieces, by their boxes: objects whose boxes meet (within the join) print as one
    near = extra["join_mm"] + detail
    group = list(range(len(boxes)))

    def root(i):
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if all(boxes[i][0][a] - near <= boxes[j][1][a] and boxes[j][0][a] - near <= boxes[i][1][a] for a in range(3)):
                group[root(i)] = root(j)
    roots = {root(i) for i in range(len(boxes))}
    grounded = {root(i) for i, b in enumerate(boxes) if b[0][2] <= near}
    extent = [max(b[1][a] for b in boxes) for a in range(3)]
    bad = sum(_edges_ok(o["triangles"]) for o in objects)
    fits = all(e <= b for e, b in zip(sorted(extent[:2], reverse=True) + [extent[2]], sorted(bed[:2], reverse=True) + [bed[2]]))
    report.update(extra)
    thick = set(report.get("thickened", ()))
    report.update({"exact": True, "objects": len(objects), "exact_parts": sorted({pid for pid, _ in kept} - thick),
                   "shelled": sorted(thick - set(report.get("thickened_in_voxels", ()))),
                   "watertight": bad == 0, "bad_edges": bad, "pieces": len(roots), "pieces_in_air": len(roots - grounded),
                   "fits_bed": fits, "bed_mm": list(bed), "needs_supports": None,
                   "size_mm": [round(x, 1) for x in extent], "scale": "1:%s" % _ratio(1000.0 / mm_per_m),
                   "smallest_real_mm": round(detail * 1000.0 / mm_per_m, 1),
                   "triangles": sum(len(o["triangles"]) for o in objects)})
    return {"objects": objects, "report": report, "title": g["title"]}


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
    if report.get("exact"):
        out = ["turned a quarter on the bed, the way it fits"] if report.get("turned") else []
        if not report["watertight"]:
            out.append("NOT watertight: %d open edges" % report["bad_edges"])
        out.append("exact: %d of the construct's solids as they are%s, parts of one object the slicer joins"
                   % (len(report["exact_parts"]), " and its thickened surfaces" if report.get("thickened") else ""))
        if report["pieces_in_air"]:
            out.append("%d of %d pieces (by their boxes) would start in the air: print with supports"
                       % (report["pieces_in_air"], report["pieces"]))
        elif report["pieces"] > 1:
            out.append("%d separate pieces (by their boxes), all on the bed" % report["pieces"])
        if not report["fits_bed"]:
            out.append("does not fit a %s mm bed: --fit, a larger printer (--printers) or cut it"
                       % "x".join("%g" % b for b in report["bed_mm"]))
        if report.get("shelled"):
            out.append("thickened to %g mm as true shells, their own shape (open or too thin): %s"
                       % (report["wall_mm"], _list(report["shelled"])))
        if report.get("thickened_in_voxels"):
            out.append("thickened to %g mm in voxels of %g mm (a surface that folds or branches): %s"
                       % (report["wall_mm"], report["detail_mm"], _list(report["thickened_in_voxels"])))
        out.append("the slicer decides supports and the finest detail: the solids keep the construct's own")
        return out
    out = []
    if not report["watertight"]:
        out.append("NOT watertight: %d edges are open or shared by more than two triangles" % report["bad_edges"])
    if report["pieces_in_air"]:
        out.append("%d of %d pieces would start in the air: print with supports, or close wider gaps (--join)"
                   % (report["pieces_in_air"], report["pieces"]))
    elif report["pieces"] > 1:
        out.append("%d separate pieces, all on the bed" % report["pieces"])
    if not report["fits_bed"]:
        out.append("does not fit a %s mm bed: print smaller (--size), fit it (--fit), a larger printer "
                   "(--printers) or cut it" % "x".join("%g" % b for b in report["bed_mm"]))
    if report.get("detail_asked_mm") and report["detail_mm"] > report["detail_asked_mm"]:
        out.append("voxel %g mm, not %g: the finest this size allows (%d along the longest side)"
                   % (report["detail_mm"], report["detail_asked_mm"], MAX_CELLS))
    out.append("features under about %g mm on the real object are lost or thickened" % report["smallest_real_mm"])
    if report.get("turned"):
        out.append("turned a quarter on the bed, the way it fits")
    if report["needs_supports"]:
        out.append("overhangs need supports (%.0f mm2 face down steeper than %g degrees)"
                   % (report["overhang_mm2"], OVERHANG_DEGREES))
    if report["thickened"]:
        out.append("thickened to the %g mm wall: %s" % (report["wall_mm"], _list(report["thickened"])))
    if report["lines_left_out"]:
        out.append("drawn only in lines, not printed (--lines engrave cuts them in, --lines raised raises them): %s"
                   % _list(report["lines_left_out"]))
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


def _mesh_xml(oid, name, verts, faces):
    return "\n".join(['  <object id="%d" type="model" name="%s">' % (oid, _xml(name)), '   <mesh>', '    <vertices>',
                      "\n".join("<vertex x=\"%.4f\" y=\"%.4f\" z=\"%.4f\"/>" % tuple(q) for q in verts),
                      '    </vertices>', '    <triangles>',
                      "\n".join("<triangle v1=\"%d\" v2=\"%d\" v3=\"%d\"/>" % tuple(f) for f in faces),
                      '    </triangles>', '   </mesh>', '  </object>'])


def to_3mf(p):
    """A 3MF package (millimetres): one object, the construct's title and scale as metadata. An exact print is one
    mesh holding every solid (closed, wound outward, overlapping: a slicer fills their union), with PrusaSlicer's
    volume table naming each solid as a part of that object."""
    config = None
    if "objects" in p:
        verts, faces, volumes = [], [], []
        for o in p["objects"]:
            base, first = len(verts), len(faces)
            verts.extend(o["vertices"])
            faces.extend([a + base, b + base, c + base] for a, b, c in o["triangles"])
            volumes.append((first, len(faces) - 1, o["name"]))
        resources, item = _mesh_xml(1, p["title"], verts, faces), 1
        config = "\n".join(['<?xml version="1.0" encoding="UTF-8"?>', '<config>', ' <object id="1" instances_count="1">',
                            '  <metadata type="object" key="name" value="%s"/>' % _xml(p["title"])] +
                           ['  <volume firstid="%d" lastid="%d">\n   <metadata type="volume" key="name" value="%s"/>\n'
                            '   <metadata type="volume" key="volume_type" value="ModelPart"/>\n  </volume>' % (a, b, _xml(n))
                            for a, b, n in volumes] + [' </object>', '</config>', ""])
    else:
        resources, item = _mesh_xml(1, p["title"], p["vertices"], p["triangles"]), 1
    model = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        ' <metadata name="Title">%s</metadata>' % _xml(p["title"]),
        ' <metadata name="Application">%s %s</metadata>' % (product.TITLE, product.VERSION),
        ' <metadata name="Description">%s</metadata>' % _xml("Printed at %s; %s" % (
            p["report"]["scale"], "watertight" if p["report"]["watertight"] else "not watertight")),
        ' <resources>', resources, ' </resources>', ' <build>', '  <item objectid="%d"/>' % item, ' </build>',
        '</model>', ""])
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
        if config:
            z.writestr("Metadata/Slic3r_PE_model.config", config)
    return buf.getvalue()


def write(scene, path, fmt=None, **kw):
    """Make the print of `scene` and write it to `path` (.stl or .3mf). Returns the report."""
    path = Path(path)
    fmt = fmt or path.suffix.lower().lstrip(".")
    if fmt not in FORMATS:
        raise PrintError("format: stl or 3mf (from --format or the file's extension), not %r" % fmt)
    if kw.get("exact") and fmt != "3mf":
        raise PrintError("an exact print is 3MF (its solids are parts of one object); STL has no parts")
    p = make(scene, **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_stl(p) if fmt == "stl" else to_3mf(p))
    return dict(p["report"], format=fmt, files=[str(path)])
