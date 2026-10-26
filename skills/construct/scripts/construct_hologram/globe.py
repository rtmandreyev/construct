"""A measured globe from coastline data the user supplies (standard library only).

    construct globe --coastlines ne_110m_coastline.geojson --title "Earth" \
        --source-title "Natural Earth 1:110m coastline (public domain)" --output earth.json

Reads GeoJSON (LineString, MultiLineString, Polygon, MultiPolygon; longitude, latitude in
degrees), simplifies the lines just enough to stay inside the line budget (Douglas-Peucker in
degrees, the tolerance stated), and writes a construct scene: the coastlines on a sphere as a
`globe` part (verified, cited to the dataset: MEASURED COASTLINES), a graticule, the axis
through the poles at the axial tilt and a slow spin about it. The tilt and the mean radius are
facts cited to published constants. Nothing is downloaded.
"""

import json
import math
import re
from pathlib import Path

# published constants, cited in the scene
OBLIQUITY_DEG = 23.439279  # 84381.406 arcsec at J2000 (IAU 2006 precession)
OBLIQUITY_SOURCE = "IAU 2006 precession (Capitaine, Wallace and Chapront 2003): obliquity of the ecliptic at J2000, 84381.406 arcsec"
MEAN_RADIUS_M = 6371008.8  # IUGG mean radius R1 of the GRS 80 ellipsoid
RADIUS_SOURCE = "IUGG: mean Earth radius R1 = 6371.0088 km (Moritz, Geodetic Reference System 1980)"
STAGE_RADIUS = 0.5
MAX_SEGMENTS = 14000  # coastline segments: the rest of the 24,000-line budget is graticule and axis


class GlobeError(Exception):
    pass


def read_geojson(path):
    """Every line and ring in a GeoJSON file as lists of [lon, lat]."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GlobeError("cannot read %s: %s" % (path, exc))
    geoms = []

    def visit(g):
        if not isinstance(g, dict):
            return
        t = g.get("type")
        if t == "FeatureCollection":
            for f in g.get("features", []):
                visit(f)
        elif t == "Feature":
            visit(g.get("geometry"))
        elif t == "GeometryCollection":
            for x in g.get("geometries", []):
                visit(x)
        elif t == "LineString":
            geoms.append(g["coordinates"])
        elif t in ("MultiLineString", "Polygon"):
            geoms.extend(g["coordinates"])
        elif t == "MultiPolygon":
            for poly in g["coordinates"]:
                geoms.extend(poly)
    visit(doc)
    lines = []
    for line in geoms:
        pts = [[float(p[0]), float(p[1])] for p in line if isinstance(p, (list, tuple)) and len(p) >= 2]
        pts = [p for p in pts if -180 <= p[0] <= 180 and -90 <= p[1] <= 90]
        if len(pts) >= 2:
            lines.append(pts)
    if not lines:
        raise GlobeError("no lines or polygons with longitude/latitude coordinates in %s" % path)
    return lines


def _dp(pts, tol):
    """Douglas-Peucker in degrees (iterative); keeps the ends."""
    if len(pts) < 3 or tol <= 0:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = pts[i], pts[j]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, k = -1.0, None
        for m in range(i + 1, j):
            px, py = pts[m]
            d = abs(dy * (px - ax) - dx * (py - ay)) / norm if norm else math.hypot(px - ax, py - ay)
            if d > best:
                best, k = d, m
        if k is not None and best > tol:
            keep[k] = True
            stack += [(i, k), (k, j)]
    return [p for p, f in zip(pts, keep) if f]


def dedupe(lines):
    """Lines with every segment drawn once: a segment already drawn (in either direction) splits
    its line there. Coastline files repeat shared edges; drawn twice they bead and brighten."""
    seen, out = set(), []
    for line in lines:
        run = [line[0]]
        for a, b in zip(line, line[1:]):
            key = tuple(sorted(((round(a[0], 4), round(a[1], 4)), (round(b[0], 4), round(b[1], 4)))))
            if key in seen or key[0] == key[1]:
                if len(run) >= 2:
                    out.append(run)
                run = [b]
                continue
            seen.add(key)
            run.append(b)
        if len(run) >= 2:
            out.append(run)
    return out


def extent(line):
    """A line's size in degrees of arc (longitude scaled by the cosine of its latitude)."""
    lons, lats = [p[0] for p in line], [p[1] for p in line]
    k = math.cos(math.radians(sum(lats) / len(lats)))
    return max((max(lons) - min(lons)) * k, max(lats) - min(lats))


MIN_TOLERANCE = 0.12  # degrees: about a pixel on a full-frame globe
SMALL_ISLANDS = (0.5, 1.0, 2.0)  # degrees: islands below these are left out, smallest first, only when needed


def fit_budget(lines, max_segments=MAX_SEGMENTS):
    """(lines, tolerance in degrees, smallest island kept in degrees, islands left out): the
    data drawn as it is when it fits; otherwise islands too small to read at globe scale are
    left out first, then the lines are simplified only as far as the budget needs."""
    lines = dedupe(lines)

    def fits(ls):
        return sum(len(q) - 1 for q in ls) <= max_segments and sum(len(q) for q in ls) <= 20000
    if fits(lines):
        return [[[round(x, 4), round(y, 4)] for x, y in q] for q in lines], 0.0, 0.0, 0
    kept, floor, dropped = lines, 0.0, 0
    for floor in SMALL_ISLANDS:
        closed = [q for q in lines if q[0] == q[-1] and len(q) > 3]
        small = [q for q in closed if extent(q) < floor]
        kept = [q for q in lines if not (q[0] == q[-1] and len(q) > 3 and extent(q) < floor)]
        dropped = len(small)
        if sum(len(q) for q in kept) <= 3 * 20000:
            break
    tol = 0.0
    while True:
        out = [q for q in (_dp(line, tol) for line in kept) if len(q) >= 2]
        if fits(out):
            return [[[round(x, 4), round(y, 4)] for x, y in q] for q in out], tol, floor, dropped
        # a segment shorter than about a pixel of the hero only beads: start there
        tol = MIN_TOLERANCE if tol == 0 else tol * 1.3


def build(coastlines, title="Earth", source_title="Coastline data", source_ref=None, rights="public_domain",
          graticule=30, tilt=True, rpm=1.0, identifier=None):
    lines, tol, floor, dropped = fit_budget(read_geojson(coastlines))
    points = sum(len(q) for q in lines)
    r = STAGE_RADIUS
    a = math.radians(OBLIQUITY_DEG if tilt else 0.0)
    axis = [round(math.sin(a), 6), round(math.cos(a), 6), 0.0]  # the north pole leans to the right
    ident = identifier or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "globe"
    scale = MEAN_RADIUS_M / r
    simplified = "; ".join(x for x in (
        ("%d islands smaller than %g° left out" % (dropped, floor)) if dropped else "",
        ("simplified to %g° to fit the line budget" % round(tol, 4)) if tol else "") if x) or "every point kept"
    facts = [
        {"key": "earth.mean_radius", "value": round(MEAN_RADIUS_M / 1000, 4), "unit": "km", "certainty": "verified",
         "source": "radius"},
        {"key": "globe.scale", "value": "1:%s" % format(int(round(scale, -3)), ","), "certainty": "inferred",
         "note": "the stage radius of %g m for the mean radius" % r},
        {"key": "coastline.points", "value": points, "certainty": "verified", "source": "coast", "note": simplified},
    ]
    if tilt:
        facts.append({"key": "earth.axial_tilt", "value": round(OBLIQUITY_DEG, 2), "unit": "deg", "certainty": "verified",
                      "source": "obliquity"})
    spin = {"type": "spin", "axis": axis, "rpm": rpm, "pivot": [0, 0, 0]} if rpm else None
    rotate = [0, 0, -round(math.degrees(a), 4)]
    parts = [
        {"id": "sphere", "label": title, "role": "mass", "certainty": "verified", "source": "radius", "stage": 0,
         "basis": ["earth.mean_radius"], "floating": True, "rotate": rotate,
         "shape": {"type": "globe", "radius": r, "paths": [], "graticule": graticule},
         "note": "a sphere of the mean radius" + (" with a %d° graticule" % graticule if graticule else "")},
        {"id": "coastlines", "label": "Coastlines", "role": "identity", "certainty": "verified", "source": "coast",
         "stage": 1, "basis": ["coastline.points"], "floating": True, "rotate": rotate,
         "shape": {"type": "globe", "radius": r, "paths": lines, "graticule": 0, "faces": False},
         "note": "coastlines from the dataset; " + simplified},
        {"id": "axis", "label": "Axis", "role": "structure", "certainty": "verified",
         "source": "obliquity" if tilt else "radius", "stage": 2, "floating": True,
         "basis": ["earth.axial_tilt"] if tilt else ["earth.mean_radius"],
         "shape": {"type": "tube", "radius": 0.006, "path": [[-axis[0] * r * 1.18, -axis[1] * r * 1.18, 0],
                                                              [axis[0] * r * 1.18, axis[1] * r * 1.18, 0]]}},
    ]
    if spin:
        for p in parts:
            p["motion"] = dict(spin)
    sources = [{"id": "coast", "kind": "dataset", "title": source_title, "rights": rights,
                **({"ref": source_ref} if source_ref else {})},
               {"id": "radius", "kind": "document", "title": RADIUS_SOURCE, "rights": "public_domain"}]
    if tilt:
        sources.append({"id": "obliquity", "kind": "document", "title": OBLIQUITY_SOURCE, "rights": "public_domain"})
    return {
        "format": "construct-scene", "version": 2, "id": ident, "title": title,
        "subject": {"category": "other", "accuracy": "documented", "synthetic": False,
                    "summary": "%s: measured coastlines (%d points) on a sphere at 1:%s%s." % (
                        title, points, format(int(round(scale, -3)), ","),
                        ", the axis at its %.2f° tilt" % OBLIQUITY_DEG if tilt else "")},
        "units": "m", "seed": 7, "sources": sources, "facts": facts, "parts": parts,
        "presentation": {"framing": {"yaw": 0, "pitch": 12, "fit": 1.0},
                         "views": [{"id": "north", "label": "From above the North Pole", "yaw": 0, "pitch": 80,
                                    "distance": 1.0}]},
        "animation": {"assembly": {"style": "ceremony", "seconds": 5.0, "interference": True},
                      "idle": {"life": "calm", "events": ["scan", "shimmer"], "cadence": [8, 14], "strength": 0.4},
                      "camera": {"drift": 0, "breathe": 0.015}},
    }
