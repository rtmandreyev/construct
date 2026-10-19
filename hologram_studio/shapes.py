"""Geometry primitives for hologram scenes (format version 2).

Every primitive is built in its own local frame (metres, Y up) and returns a Mesh:
line segments with an edge class, translucent triangles and sprite points. Nothing
here knows about certainty, colour or animation: scene.py assigns those. Pure
standard library and deterministic: the same parameters always give the same bytes.

Edge classes say what a line is to the object, which decides how strongly it draws:
  OUTLINE  the primary silhouette and construction edges
  CONTOUR  secondary rings, meridians and section lines that model a curved surface
  DETAIL   fine hatching and small repeated detail (fades first with distance)
"""

import math

OUTLINE, CONTOUR, DETAIL = 0, 1, 2


class Mesh:
    __slots__ = ("lines", "tris", "points")

    def __init__(self):
        self.lines = []   # (a, b, edge_class)
        self.tris = []    # (a, b, c)
        self.points = []  # (p, sprite_shape)

    def line(self, a, b, cls=OUTLINE):
        self.lines.append((tuple(a), tuple(b), cls))

    def loop(self, pts, cls=OUTLINE, closed=True):
        n = len(pts)
        for i in range(n if closed else n - 1):
            self.line(pts[i], pts[(i + 1) % n], cls)

    def quad(self, a, b, c, d):
        self.tris.append((tuple(a), tuple(b), tuple(c)))
        self.tris.append((tuple(a), tuple(c), tuple(d)))

    def extend(self, other):
        self.lines.extend(other.lines)
        self.tris.extend(other.tris)
        self.points.extend(other.points)


# ---------------------------------------------------------------------------- helpers

def _ring(radius_x, radius_z, y, n, start=0.0):
    return [(radius_x * math.cos(start + 2 * math.pi * i / n), y,
             radius_z * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def _every(n, wanted):
    """Indices spread evenly over n for `wanted` items (at least 1, at most n)."""
    wanted = max(1, min(n, wanted))
    return sorted({int(round(i * n / wanted)) % n for i in range(wanted)})


def catmull_rom(points, samples_per_span):
    """A smooth curve through the points (centripetal-free uniform Catmull-Rom)."""
    if len(points) < 3:
        return [tuple(p) for p in points]
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(samples_per_span):
            t = s / samples_per_span
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t
                                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(3)))
    out.append(tuple(points[-1]))
    return out


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    length = math.sqrt(_dot(a, a))
    return (a[0] / length, a[1] / length, a[2] / length) if length > 1e-12 else (0.0, 0.0, 0.0)


def _polygon_area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def triangulate(poly):
    """Ear clipping for a simple polygon [(u, v)]: index triples, counter-clockwise."""
    n = len(poly)
    if n < 3:
        return []
    idx = list(range(n))
    if _polygon_area2(poly) < 0:
        idx.reverse()

    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    out, guard = [], 0
    while len(idx) > 3 and guard < 4 * n * n:
        guard += 1
        clipped = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0:
                continue  # reflex
            if any(inside(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            out.append((i0, i1, i2))
            idx.pop(k)
            clipped = True
            break
        if not clipped:
            break  # not simple: give up on the remainder rather than loop
    if len(idx) == 3:
        out.append(tuple(idx))
    return out


# ---------------------------------------------------------------------------- primitives

def box(size, ribs=0):
    """An axis-aligned box centred on the origin; `ribs` adds evenly spaced vertical
    detail lines on the four faces (panels, windows, planks)."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    c = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
         (-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz)]
    m = Mesh()
    m.loop(c[0:4])
    m.loop(c[4:8])
    for i in range(4):
        m.line(c[i], c[i + 4])
    for face in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        m.quad(*(c[i] for i in face))
    for r in range(1, ribs + 1):
        f = r / (ribs + 1)
        x = -hx + 2 * hx * f
        z = -hz + 2 * hz * f
        m.line((x, -hy, hz), (x, hy, hz), DETAIL)
        m.line((x, -hy, -hz), (x, hy, -hz), DETAIL)
        m.line((hx, -hy, z), (hx, hy, z), DETAIL)
        m.line((-hx, -hy, z), (-hx, hy, z), DETAIL)
    return m


def frustum(r0, r1, height, segments=32, ribs=6, caps=True, rings=0):
    """A cylinder (r0 == r1) or truncated cone along +Y from y=0 to y=height."""
    m = Mesh()
    bottom, top = _ring(r0, r0, 0.0, segments), _ring(r1, r1, height, segments)
    if r0 > 0:
        m.loop(bottom)
    if r1 > 0:
        m.loop(top)
    for i in _every(segments, ribs):
        m.line(bottom[i], top[i], CONTOUR)
    for k in range(1, rings + 1):
        f = k / (rings + 1)
        r = r0 + (r1 - r0) * f
        m.loop(_ring(r, r, height * f, segments), DETAIL)
    for i in range(segments):
        j = (i + 1) % segments
        m.quad(bottom[i], bottom[j], top[j], top[i])
        if caps:
            if r0 > 0:
                m.tris.append(((0.0, 0.0, 0.0), bottom[j], bottom[i]))
            if r1 > 0:
                m.tris.append(((0.0, height, 0.0), top[i], top[j]))
    return m


def ellipsoid(radii, lat=8, lon=12, segments=32):
    """A sphere/ellipsoid centred on the origin: latitude rings and meridians."""
    rx, ry, rz = radii
    m = Mesh()
    for i in range(1, lat):
        phi = math.pi * i / lat - math.pi / 2
        y, s = ry * math.sin(phi), math.cos(phi)
        m.loop(_ring(rx * s, rz * s, y, segments), OUTLINE if i == lat // 2 else CONTOUR)
    rows = max(lat, 6)
    for j in range(lon):
        th = 2 * math.pi * j / lon
        pts = []
        for i in range(rows + 1):
            phi = math.pi * i / rows - math.pi / 2
            pts.append((rx * math.cos(phi) * math.cos(th), ry * math.sin(phi), rz * math.cos(phi) * math.sin(th)))
        m.loop(pts, CONTOUR, closed=False)
    grid_rows, grid_cols = max(lat, 6), max(segments // 2, 12)
    grid = [[(rx * math.cos(math.pi * i / grid_rows - math.pi / 2) * math.cos(2 * math.pi * j / grid_cols),
              ry * math.sin(math.pi * i / grid_rows - math.pi / 2),
              rz * math.cos(math.pi * i / grid_rows - math.pi / 2) * math.sin(2 * math.pi * j / grid_cols))
             for j in range(grid_cols)] for i in range(grid_rows + 1)]
    for i in range(grid_rows):
        for j in range(grid_cols):
            k = (j + 1) % grid_cols
            m.quad(grid[i][j], grid[i][k], grid[i + 1][k], grid[i + 1][j])
    return m


def torus(major, minor, segments=32, sides=10, rings=8):
    """A torus around the Y axis: the tube's circle at `rings` stations and the
    inner, outer, top and bottom circles."""
    m = Mesh()

    def at(u, v):
        return ((major + minor * math.cos(v)) * math.cos(u), minor * math.sin(v),
                (major + minor * math.cos(v)) * math.sin(u))

    for v, cls in ((0.0, OUTLINE), (math.pi, OUTLINE), (math.pi / 2, CONTOUR), (-math.pi / 2, CONTOUR)):
        m.loop([at(2 * math.pi * i / segments, v) for i in range(segments)], cls)
    for i in _every(segments, rings):
        u = 2 * math.pi * i / segments
        m.loop([at(u, 2 * math.pi * k / sides) for k in range(sides)], CONTOUR)
    for i in range(segments):
        for k in range(sides):
            u0, u1 = 2 * math.pi * i / segments, 2 * math.pi * (i + 1) / segments
            v0, v1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
            m.quad(at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1))
    return m


def lathe(profile, segments=32, meridians=8, every_ring=True):
    """Revolve a profile [(radius, y), ...] about the Y axis: bottles, towers, domes,
    lamps. Rings at every profile point (the first and last are outline), meridians
    following the profile."""
    m = Mesh()
    rings = [_ring(r, r, y, segments) for r, y in profile]
    for k, (r, _) in enumerate(profile):
        if r <= 1e-9:
            continue
        edge = k in (0, len(profile) - 1)
        if edge or every_ring:
            m.loop(rings[k], OUTLINE if edge else CONTOUR)
    for i in _every(segments, meridians):
        m.loop([rings[k][i] for k in range(len(profile))], CONTOUR, closed=False)
    for k in range(len(profile) - 1):
        for i in range(segments):
            j = (i + 1) % segments
            m.quad(rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i])
    return m


def extrude(profile, height, axis="y", ribs=0, caps=True):
    """Extrude a closed polygon profile [(u, v), ...] by `height`.

    axis "y": the profile lies in XZ (a footprint, u=x, v=z) and rises along +Y.
    axis "z": the profile lies in XY (a front elevation, u=x, v=y) and runs along +Z
              (a gabled house front, a letterform, a bracket).
    axis "x": the profile lies in ZY (u=z, v=y) and runs along +X."""
    def place(u, v, w):
        if axis == "y":
            return (u, w, v)
        if axis == "z":
            return (u, v, w)
        return (w, v, u)

    m = Mesh()
    low = [place(u, v, 0.0) for u, v in profile]
    high = [place(u, v, height) for u, v in profile]
    m.loop(low)
    m.loop(high)
    for a, b in zip(low, high):
        m.line(a, b)
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        m.quad(low[i], low[j], high[j], high[i])
        for r in range(1, ribs + 1):
            f = r / (ribs + 1)
            pa = tuple(low[i][k] + (low[j][k] - low[i][k]) * f for k in range(3))
            pb = tuple(high[i][k] + (high[j][k] - high[i][k]) * f for k in range(3))
            m.line(pa, pb, DETAIL)
    if caps:
        for a, b, c in triangulate(profile):
            m.tris.append((low[a], low[c], low[b]))
            m.tris.append((high[a], high[b], high[c]))
    return m


def _frames(path):
    """Parallel-transport frames along a polyline: (tangent, normal, binormal)."""
    tangents = []
    for i in range(len(path)):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        tangents.append(_norm(_sub(b, a)))
    t0 = tangents[0]
    helper = (0.0, 1.0, 0.0) if abs(t0[1]) < 0.9 else (1.0, 0.0, 0.0)
    normal = _norm(_cross(t0, helper))
    frames = []
    for t in tangents:
        normal = _norm(_sub(normal, tuple(t[k] * _dot(normal, t) for k in range(3))))
        if normal == (0.0, 0.0, 0.0):
            helper = (0.0, 1.0, 0.0) if abs(t[1]) < 0.9 else (1.0, 0.0, 0.0)
            normal = _norm(_cross(t, helper))
        frames.append((t, normal, _cross(t, normal)))
    return frames


def tube(path, radii, sides=8, smooth=True, samples=8, ring_every=2, longitudinal=4, caps=False):
    """Sweep a circle along a 3-D path: limbs, tentacles, cables, branches, pipes.
    `radii` is one radius or one per path point (tapered between them)."""
    pts = catmull_rom(path, samples) if smooth and len(path) >= 3 else [tuple(p) for p in path]
    n = len(pts)
    if isinstance(radii, (int, float)):
        rad = [float(radii)] * n
    else:
        rad = []
        for i in range(n):
            f = i / max(1, n - 1) * (len(radii) - 1)
            k = min(int(f), len(radii) - 2)
            rad.append(radii[k] + (radii[k + 1] - radii[k]) * (f - k))
    frames = _frames(pts)
    circles = []
    for p, (t, nrm, bin_), r in zip(pts, frames, rad):
        circles.append([tuple(p[k] + r * (math.cos(2 * math.pi * s / sides) * nrm[k]
                                          + math.sin(2 * math.pi * s / sides) * bin_[k]) for k in range(3))
                        for s in range(sides)])
    m = Mesh()
    for i, circle in enumerate(circles):
        if i in (0, n - 1):
            m.loop(circle, OUTLINE)
        elif ring_every and i % ring_every == 0:
            m.loop(circle, CONTOUR)
    for s in _every(sides, longitudinal):
        m.loop([circles[i][s] for i in range(n)], OUTLINE, closed=False)
    for i in range(n - 1):
        for s in range(sides):
            q = (s + 1) % sides
            m.quad(circles[i][s], circles[i][q], circles[i + 1][q], circles[i + 1][s])
    if caps:
        for end in (0, n - 1):
            centre = pts[end]
            for s in range(sides):
                m.tris.append((centre, circles[end][s], circles[end][(s + 1) % sides]))
    return m


def curve(points, smooth=False, closed=False, samples=8, cls=OUTLINE):
    m = Mesh()
    if smooth and len(points) >= 3:
        src = list(points) + ([points[0], points[1]] if closed else [])
        pts = catmull_rom(src, samples)
        if closed:
            pts = pts[samples:-samples] if len(pts) > 2 * samples else pts
    else:
        pts = [tuple(p) for p in points]
    m.loop(pts, cls, closed=closed)
    return m


def plane(width, height, divisions=0):
    """A flat rectangle facing +Z (an artwork face, a sign, a panel)."""
    hw, hh = width / 2, height / 2
    c = [(-hw, -hh, 0.0), (hw, -hh, 0.0), (hw, hh, 0.0), (-hw, hh, 0.0)]
    m = Mesh()
    m.loop(c)
    m.quad(*c)
    for k in range(1, divisions + 1):
        f = k / (divisions + 1)
        m.line((-hw + width * f, -hh, 0.0), (-hw + width * f, hh, 0.0), DETAIL)
        m.line((-hw, -hh + height * f, 0.0), (hw, -hh + height * f, 0.0), DETAIL)
    return m


def grid(width, depth, divisions):
    """A survey grid on the ground plane (XZ), centred on the origin."""
    m = Mesh()
    hw, hd = width / 2, depth / 2
    for k in range(divisions + 1):
        f = k / divisions
        cls = OUTLINE if k in (0, divisions) else DETAIL
        m.line((-hw + width * f, 0.0, -hd), (-hw + width * f, 0.0, hd), cls)
        m.line((-hw, 0.0, -hd + depth * f), (hw, 0.0, -hd + depth * f), cls)
    return m


def _hash01(seed, i, k):
    x = math.sin(seed * 12.9898 + i * 78.233 + k * 37.719) * 43758.5453
    return x - math.floor(x)


def scatter(count, region, size, seed, shape=3):
    """Deterministic points filling a box [w, h, d] or an ellipsoid shell/volume:
    dust, spores, sparks, stars. `region` is ("box", w, h, d) or ("sphere", r, shell)."""
    m = Mesh()
    for i in range(count):
        u, v, w = _hash01(seed, i, 1), _hash01(seed, i, 2), _hash01(seed, i, 3)
        if region[0] == "box":
            p = ((u - 0.5) * region[1], (v - 0.5) * region[2], (w - 0.5) * region[3])
        else:
            r = region[1] * (1.0 - region[2] * w if region[2] > 0 else w ** (1 / 3))
            th, ph = 2 * math.pi * u, math.acos(2 * v - 1)
            p = (r * math.sin(ph) * math.cos(th), r * math.cos(ph), r * math.sin(ph) * math.sin(th))
        m.points.append((p, shape))
    return m
