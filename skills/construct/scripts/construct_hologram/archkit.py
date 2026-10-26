"""The architecture kit: towers, roofs, dormers, facades, battlements and buttresses as shapes.

Repeated, ornate architecture costs a model too much to author part by part, so it stops early
and the castle looks unfinished. These shapes give it in a few numbers each, drawn in the same
line classes as every other shape (outline, contour, detail) with glass faces:

    tower        radius, height, sides (0 round), roof cone|pyramid|spire|onion|flat|none,
                 roof_height, taper, eave, windows [rows, per_row]
    roof         size [w, d], height, style gable|hip, ridge x|z, overhang, courses
    dormer       width, height, depth, roof_height (a window in a roof, facing +Z)
    facade       size [w, h], rows, cols, opening [w, h], arch round|pointed|flat|none,
                 kind windows|arcade (a wall facing +Z with its openings)
    battlements  radius or path [[x, z], ...] (closed), height, merlon, gap, thickness
    buttress     width, depth, height, steps (stepped, against a wall at z = 0, out along +Z)

Every shape stands on its local origin (y = 0 at the base); place and turn it with `at` and
`rotate`, copy it with `repeat` and `mirror`.
"""

import math

from .shapes import CONTOUR, DETAIL, OUTLINE, Mesh, _ring, extrude

ROOFS = ("cone", "pyramid", "spire", "onion", "flat", "none")
ARCHES = ("round", "pointed", "flat", "none")


def _add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


def _apex_roof(m, ring, apex, sides, meridians):
    """A roof from a ring of points up to an apex: generators (every vertex of a polygon, or
    `meridians` of a round one), a contour halfway, faces."""
    n = len(ring)
    edges = range(n) if sides else range(0, n, max(1, n // meridians))
    for i in edges:
        m.line(ring[i], apex, OUTLINE if sides else CONTOUR)
    mid = [tuple(p[k] + (apex[k] - p[k]) * 0.5 for k in range(3)) for p in ring]
    m.loop(mid, DETAIL)
    for i in range(n):
        m.tris.append((ring[i], ring[(i + 1) % n], apex))


def tower(radius, height, sides=0, roof="cone", roof_height=None, taper=1.0, eave=0.0, windows=None, segments=32,
          profile="straight"):
    """`profile` "parabolic": the shaft narrows ever faster towards the top (a paraboloid, as the
    bell towers of the Sagrada Familia), ending at `taper` times the base radius."""
    m = Mesh()
    n = sides if sides >= 3 else segments
    start = math.pi / 2 - math.pi / n if sides >= 3 else 0.0  # a polygon shows a face to the front
    rt = radius * taper

    def r_at(y):
        if profile == "parabolic":
            k = 1 - min(1.0, taper) ** 2
            return radius * math.sqrt(max(0.0, 1 - k * y / height))
        return radius + (rt - radius) * y / height
    if profile == "parabolic":
        levels = [height * (1 - (1 - k / 8) ** 1.5) for k in range(9)]
    else:
        levels = [0.0, height] if sides >= 3 else [0.0, height * 0.33, height * 0.66, height]
    rings = [_ring(r_at(y), r_at(y), y, n, start) for y in levels]
    for k, ring in enumerate(rings):
        m.loop(ring, OUTLINE if k in (0, len(rings) - 1) else DETAIL)
    for i in (range(n) if sides >= 3 else range(0, n, max(1, n // 12))):
        m.loop([rg[i] for rg in rings], OUTLINE if sides >= 3 else CONTOUR, closed=False)
    for lo, hi in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            m.quad(lo[i], lo[j], hi[j], hi[i])
    if windows:
        rows, per = max(1, int(windows[0])), max(1, int(windows[1]))
        for r in range(rows):
            y = height * (0.3 + 0.55 * (r + 0.5) / rows)
            ry = r_at(y)
            ww = min(0.5 * ry, 2 * math.pi * ry / per * 0.35)
            wh = min(height / rows * 0.45, ww * 2.2)
            for c in range(per):
                a = start + math.pi / n + 2 * math.pi * c / per if sides >= 3 else 2 * math.pi * c / per + math.pi / 2
                centre = (ry * 1.01 * math.cos(a), y, ry * 1.01 * math.sin(a))
                t = (-math.sin(a), 0.0, math.cos(a))
                _window(m, centre, t, (0.0, 1.0, 0.0), ww, wh, "round")
    top = height
    re = rt + eave
    eave_ring = _ring(re, re, top, n, start)
    if eave > 0:
        m.loop(eave_ring, OUTLINE)
        for i in range(n):
            m.quad(rings[-1][i], rings[-1][(i + 1) % n], eave_ring[(i + 1) % n], eave_ring[i])
    if roof in ("cone", "pyramid", "spire"):
        rh = roof_height or re * {"cone": 1.4, "pyramid": 1.1, "spire": 3.2}[roof]
        rn = 4 if roof == "pyramid" and sides < 3 else n
        base = eave_ring if rn == n else _ring(re * 1.41, re * 1.41, top, 4, math.pi / 4)
        apex = (0.0, top + rh, 0.0)
        _apex_roof(m, base, apex, sides >= 3 or roof == "pyramid", 8)
        if base is not eave_ring:  # otherwise the eave (or, without one, the shaft's top ring) is drawn
            m.loop(base, OUTLINE)
        if roof == "spire":
            m.loop(_ring(re * 0.55, re * 0.55, top + rh * 0.18, n, start), CONTOUR)  # the collar
            m.line(apex, (0.0, top + rh * 1.08, 0.0), OUTLINE)  # the finial
    elif roof == "onion":
        rh = roof_height or re * 1.8
        prof = [(re, 0.0), (re * 1.22, 0.22), (re * 1.12, 0.46), (re * 0.62, 0.72), (re * 0.18, 0.9), (0.0, 1.0)]
        rings_o = [_ring(r, r, top + f * rh, segments, 0.0) for r, f in prof]
        for k, ring in enumerate(rings_o[:-1]):
            if k == 0 and (eave > 0 or sides < 3):
                continue  # the eave, or the round shaft's top ring
            m.loop(ring, OUTLINE if k in (0, 1) else CONTOUR)
        for i in range(0, segments, max(1, segments // 8)):
            m.loop([rg[i] for rg in rings_o], CONTOUR, closed=False)
        for k in range(len(prof) - 1):
            for i in range(segments):
                j = (i + 1) % segments
                m.quad(rings_o[k][i], rings_o[k][j], rings_o[k + 1][j], rings_o[k + 1][i])
        m.line((0.0, top + rh, 0.0), (0.0, top + rh * 1.12, 0.0), OUTLINE)
    elif roof == "flat":
        for i in range(1, n - 1):
            m.tris.append((eave_ring[0], eave_ring[i + 1], eave_ring[i]))
    return m


def roof(width, depth, height, style="gable", ridge="x", overhang=0.0, courses=0):
    """A pitched roof standing on y = 0 (its eaves), centred; the ridge runs along `ridge`."""
    m = Mesh()
    W, D = width + 2 * overhang, depth + 2 * overhang
    if ridge == "z":
        W, D = D, W

    def p(x, y, z):
        return (z, y, x) if ridge == "z" else (x, y, z)
    a, b, c, d = p(-W / 2, 0, -D / 2), p(W / 2, 0, -D / 2), p(W / 2, 0, D / 2), p(-W / 2, 0, D / 2)
    m.loop([a, b, c, d], OUTLINE)
    if style == "hip":
        half = max(0.0, (W - D) / 2)
        r1, r2 = p(-half, height, 0), p(half, height, 0)
        m.line(r1, r2, OUTLINE)
        for corner, end in ((a, r1), (d, r1), (b, r2), (c, r2)):
            m.line(corner, end, OUTLINE)
        m.quad(a, b, r2, r1)
        m.quad(d, r1, r2, c)
        m.tris += [(a, r1, d), (b, c, r2)]
    else:
        r1, r2 = p(-W / 2, height, 0), p(W / 2, height, 0)
        m.line(r1, r2, OUTLINE)
        for corner, end in ((a, r1), (d, r1), (b, r2), (c, r2)):
            m.line(corner, end, OUTLINE)
        m.quad(a, b, r2, r1)
        m.quad(d, r1, r2, c)
        m.tris += [(a, d, r1), (b, r2, c)]  # the gable ends
    for k in range(1, max(0, int(courses)) + 1):
        f = k / (courses + 1)
        y, z = height * f, D / 2 * (1 - f)
        x0, x1 = -W / 2 + (D / 2 * f if style == "hip" else 0.0), W / 2 - (D / 2 * f if style == "hip" else 0.0)
        m.line(p(x0, y, z), p(x1, y, z), DETAIL)
        m.line(p(x0, y, -z), p(x1, y, -z), DETAIL)
    return m


def _arch_points(left, right, top_y, kind, n=10):
    """The head of an opening from its two springing points (x, y), as (x, y) points."""
    (x0, y0), (x1, _) = left, right
    w = x1 - x0
    if kind == "round":
        return [(x0 + w / 2 - w / 2 * math.cos(math.pi * k / n), y0 + w / 2 * math.sin(math.pi * k / n)) for k in range(n + 1)]
    if kind == "pointed":
        # an equilateral arch: each side an arc of radius w centred on the opposite springing point
        half = n // 2
        left = [(x0 + w / 2 * k / half, y0 + math.sqrt(max(0.0, w * w - (x0 + w / 2 * k / half - x1) ** 2)))
                for k in range(half + 1)]
        right = [(x0 + w / 2 + w / 2 * k / half, y0 + math.sqrt(max(0.0, w * w - (x0 + w / 2 + w / 2 * k / half - x0) ** 2)))
                 for k in range(1, half + 1)]
        return left + right
    return [(x0, top_y), (x1, top_y)]


def _window(m, centre, t, up, w, h, arch):
    """A window frame on a surface: its sill, jambs and head, centred on `centre` (3-D), with
    `t` along the surface and `up` vertical."""
    def at(u, v):
        return _add(_add(centre, t, u), up, v)
    spring = h / 2 - (w / 2 if arch == "round" else w * 0.866 if arch == "pointed" else 0)
    pts = [(-w / 2, spring), (-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, spring)]
    m.loop([at(u, v) for u, v in pts], CONTOUR, closed=False)
    head = _arch_points((-w / 2, spring), (w / 2, spring), h / 2, arch if arch in ("round", "pointed") else "flat")
    m.loop([at(u, v) for u, v in head], CONTOUR, closed=False)


def facade(width, height, rows=1, cols=4, opening=None, arch="round", kind="windows", outline=True):
    """A wall in the XY plane facing +Z (base at y = 0, centred on x) with a grid of openings:
    windows (sill, jambs, arched head, a mullion) or an arcade (openings to the ground, piers
    between)."""
    m = Mesh()
    a, b, c, d = (-width / 2, 0, 0), (width / 2, 0, 0), (width / 2, height, 0), (-width / 2, height, 0)
    if outline:  # on a box's face the box draws these edges already
        m.loop([a, b, c, d], OUTLINE)
    m.quad(a, b, c, d)
    cols, rows = max(1, int(cols)), max(1, int(rows))
    bay, storey = width / cols, height / rows
    ow, oh = opening if opening else (bay * (0.62 if kind == "arcade" else 0.42), storey * (0.78 if kind == "arcade" else 0.55))
    ow, oh = min(ow, bay * 0.9), min(oh, storey * 0.95)
    for r in range(rows):
        y_base = r * storey + (0 if kind == "arcade" and r == 0 else (storey - oh) * 0.45)
        if r:
            m.line((-width / 2, r * storey, 0.002), (width / 2, r * storey, 0.002), DETAIL)  # a string course
        for k in range(cols):
            x = -width / 2 + bay * (k + 0.5)
            spring = y_base + oh - (ow / 2 if arch == "round" else ow * 0.866 if arch == "pointed" else 0)
            z = 0.003
            jambs = [(x - ow / 2, spring), (x - ow / 2, y_base), (x + ow / 2, y_base), (x + ow / 2, spring)]
            if kind == "arcade" and r == 0:
                jambs = [(x - ow / 2, spring), (x - ow / 2, y_base)], [(x + ow / 2, y_base), (x + ow / 2, spring)]
                for seg in jambs:
                    m.loop([(u, v, z) for u, v in seg], OUTLINE, closed=False)
            else:
                m.loop([(u, v, z) for u, v in jambs], CONTOUR, closed=False)
                m.line((x, y_base, z), (x, spring, z), DETAIL)  # the mullion
            if arch != "none":
                head = _arch_points((x - ow / 2, spring), (x + ow / 2, spring), y_base + oh, arch)
                m.loop([(u, v, z) for u, v in head], OUTLINE if kind == "arcade" else CONTOUR, closed=False)
    return m


def battlements(height, merlon, gap, thickness, radius=None, path=None):
    """Merlons along a closed wall top (a circle of `radius`, or a polygon `path` of [x, z])."""
    m = Mesh()
    if radius:
        n = max(8, int(2 * math.pi * radius / (merlon + gap)) * 2)
        path = [(radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pts = [tuple(p) for p in path]
    segs = list(zip(pts, pts[1:] + pts[:1]))
    total = sum(math.dist(a, b) for a, b in segs)
    count = max(1, int(round(total / (merlon + gap))))
    pitch = total / count
    for k in range(count):
        s = k * pitch + gap / 2
        acc = 0.0
        for a, b in segs:
            L = math.dist(a, b)
            if acc + L >= s:
                f = (s - acc) / L if L else 0.0
                cx, cz = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                tx, tz = ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L else (1.0, 0.0)
                break
            acc += L
        nx, nz = tz, -tx
        w = min(merlon, pitch * 0.9)
        corners = []
        for du, dn in ((0, -thickness / 2), (w, -thickness / 2), (w, thickness / 2), (0, thickness / 2)):
            corners.append((cx + tx * du + nx * dn, cz + tz * du + nz * dn))
        low = [(x, 0.0, z) for x, z in corners]
        high = [(x, height, z) for x, z in corners]
        m.loop(low, CONTOUR)
        m.loop(high, OUTLINE)
        for p, q in zip(low, high):
            m.line(p, q, CONTOUR)
        for i in range(4):
            j = (i + 1) % 4
            m.quad(low[i], low[j], high[j], high[i])
        m.quad(*high)
    return m


def buttress(width, depth, height, steps=2):
    """A stepped buttress against a wall at z = 0, projecting along +Z, centred on x."""
    steps = max(1, min(int(steps), 4))
    prof = [(0.0, 0.0), (depth, 0.0)]
    d = depth
    for k in range(steps):
        y_hi = height * (0.45 + 0.4 * k / steps)
        d2 = depth * (1 - 0.35 * (k + 1) / steps)
        prof += [(d, y_hi), (d2, y_hi + height * 0.06)]
        d = d2
    prof += [(d, height * 0.9), (0.0, height)]
    m = extrude([(z, y) for z, y in prof], width, axis="x")
    m.lines = [((a[0] - width / 2, a[1], a[2]), (b[0] - width / 2, b[1], b[2]), cls) for a, b, cls in m.lines]
    m.tris = [tuple((p[0] - width / 2, p[1], p[2]) for p in t) for t in m.tris]
    return m


def dormer(width, height, depth, roof_height=None):
    """A dormer window: cheeks and a front facing +Z (base at y = 0, back at z = 0) under a small
    gable roof whose ridge runs back into the main roof."""
    m = Mesh()
    rh = roof_height or width * 0.45
    w, h, dz = width / 2, height, depth
    fl, fr, ftl, ftr = (-w, 0, dz), (w, 0, dz), (-w, h, dz), (w, h, dz)
    bl, br, btl, btr = (-w, h, 0), (w, h, 0), (-w, 0, 0), (w, 0, 0)
    m.loop([fl, fr, ftr, ftl], OUTLINE)
    m.quad(fl, fr, ftr, ftl)
    for a, b in ((fl, btl), (fr, btr), (ftl, bl), (ftr, br)):
        m.line(a, b, CONTOUR)
    m.quad(fl, btl, bl, ftl)
    m.quad(btr, fr, ftr, br)
    _window(m, (0.0, h * 0.5, dz + 0.002), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), width * 0.6, h * 0.7, "flat")
    apex_f, apex_b = (0.0, h + rh, dz + width * 0.05), (0.0, h + rh, 0.0)
    eave_fl, eave_fr = (-w * 1.1, h, dz + width * 0.05), (w * 1.1, h, dz + width * 0.05)
    eave_bl, eave_br = (-w * 1.1, h, 0.0), (w * 1.1, h, 0.0)
    for a, b in ((eave_fl, apex_f), (apex_f, eave_fr), (apex_f, apex_b), (eave_fl, eave_bl), (eave_fr, eave_br)):
        m.line(a, b, OUTLINE)
    m.quad(eave_fl, apex_f, apex_b, eave_bl)
    m.quad(apex_f, eave_fr, eave_br, apex_b)
    m.tris.append((eave_fl, eave_fr, apex_f))
    return m


def shell(span, height, reach, bulge=0.25, ribs=12, rows=8):
    """A sail-like shell (the Sydney Opera House's roofs): from a base edge on y = 0 (centred on
    x, `span` wide) up to an apex `height` high and `reach` behind it (towards -Z), bulging
    forward and up by `bulge` of its height, drawn as a fan of ribs with cross courses."""
    m = Mesh()
    ax, ay, az = 0.0, height, -reach
    nl = math.hypot(reach, height) or 1.0
    nrm = (0.0, reach / nl, height / nl)  # perpendicular to the base-to-apex line: forward and up

    def at(t, s):
        bx = -span / 2 + span * t
        f = math.sin(math.pi * s) * bulge * height * (1 - 0.6 * (2 * t - 1) ** 2)
        return (bx + (ax - bx) * s, ay * s + nrm[1] * f, az * s + nrm[2] * f)
    ribs = max(3, int(ribs))
    rows = max(2, int(rows))
    grid = [[at(k / (ribs - 1), r / rows) for r in range(rows + 1)] for k in range(ribs)]
    for k, rib in enumerate(grid):
        m.loop(rib, OUTLINE if k in (0, ribs - 1) else CONTOUR, closed=False)
    m.loop([grid[k][0] for k in range(ribs)], OUTLINE, closed=False)  # the base edge
    for r in range(1, rows):
        m.loop([grid[k][r] for k in range(ribs)], DETAIL, closed=False)
    for k in range(ribs - 1):
        for r in range(rows):
            m.quad(grid[k][r], grid[k + 1][r], grid[k + 1][r + 1], grid[k][r + 1])
    return m
