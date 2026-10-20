"""Measured terrain: a construct sampled from elevation data the user supplies.

    construct terrain --dem tile.asc --center 45.9763,7.6586 --extent 3000 --title "Matterhorn" \\
        --source-title "swissALTI3D, ©swisstopo" --gpx hornli.gpx --mark "Summit=45.9763,7.6586" \\
        --from NE --out matterhorn.json

Reads an ESRI ASCII grid (.asc) or an XYZ text export (x y z per line, a regular grid); it never
downloads anything. Coordinates in the grid's reference system: Swiss LV95 (EPSG:2056), UTM
(EPSG:326xx / 327xx) or longitude/latitude degrees (EPSG:4326); WGS84 points (a GPX track,
--center, --mark) are converted to it. The relief is resampled onto a grid of at most 100 per
side and scaled by the ladder (spot, site, valley, massif, range: each class twice the stage size
of the one before) with an optional vertical exaggeration, which is stated. The result is a
construct scene: the terrain part (verified, cited to the dataset: MEASURED TERRAIN), the route
draped on the surface, markers, the facts (extent, elevations, scale) and a view from the side
you ask for. Without data, a hand-made heightfield stays inferred: SKETCHED TERRAIN.
"""

import json
import math
import re
from pathlib import Path

LADDER = [("spot", 100.0, 1.0), ("site", 1000.0, 2.0), ("valley", 8000.0, 4.0), ("massif", 30000.0, 8.0),
          ("range", math.inf, 16.0)]   # class, largest extent in metres, stage width in metres
VIEW_YAW = {"S": 0, "SE": 45, "E": 90, "NE": 135, "N": 180, "NW": 225, "W": 270, "SW": 315}


# the densest grid that stays inside the 24,000-triangle budget with its skirt (2(n-1)^2 + 8(n-1))
MAX_RESOLUTION = 100


class TerrainError(Exception):
    pass


# ---------------------------------------------------------------------------- reference systems

def wgs84_to_lv95(lat, lon):
    """swisstopo's approximate formulas (about 1 m): WGS84 degrees -> LV95 metres (E, N)."""
    p = (lat * 3600 - 169028.66) / 10000
    l = (lon * 3600 - 26782.5) / 10000
    e = 2600072.37 + 211455.93 * l - 10938.51 * l * p - 0.36 * l * p * p - 44.54 * l ** 3
    n = 1200147.07 + 308807.95 * p + 3745.25 * l * l + 76.63 * p * p - 194.56 * l * l * p + 119.79 * p ** 3
    return e, n


def wgs84_to_utm(lat, lon, zone, south=False):
    """Transverse Mercator on WGS84 (Krüger series, millimetre-level within a zone)."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    al = [n / 2 - 2 * n * n / 3 + 5 * n ** 3 / 16, 13 * n * n / 48 - 3 * n ** 3 / 5, 61 * n ** 3 / 240]
    lam0 = math.radians(-183 + 6 * zone)
    phi, lam = math.radians(lat), math.radians(lon) - lam0
    e = 2 * math.sqrt(n) / (1 + n)
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi, eta = math.atan2(t, math.cos(lam)), math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    x = eta + sum(al[j] * math.cos(2 * (j + 1) * xi) * math.sinh(2 * (j + 1) * eta) for j in range(3))
    y = xi + sum(al[j] * math.sin(2 * (j + 1) * xi) * math.cosh(2 * (j + 1) * eta) for j in range(3))
    return 500000 + k0 * A * x, (10000000 if south else 0) + k0 * A * y


def to_crs(crs, lat, lon):
    if crs == "EPSG:2056":
        return wgs84_to_lv95(lat, lon)
    if crs == "EPSG:4326":
        return lon, lat
    m = re.fullmatch(r"EPSG:32([67])(\d\d)", crs)
    if m:
        return wgs84_to_utm(lat, lon, int(m.group(2)), m.group(1) == "7")
    raise TerrainError("unsupported reference system %r (EPSG:2056, EPSG:326xx/327xx or EPSG:4326)" % crs)


def guess_crs(x, y):
    if 2.4e6 < x < 2.9e6 and 1.0e6 < y < 1.4e6:
        return "EPSG:2056"
    if -180 <= x <= 180 and -90 <= y <= 90:
        return "EPSG:4326"
    raise TerrainError("cannot tell the grid's reference system: give --crs (EPSG:2056, EPSG:326xx or EPSG:4326)")


# ---------------------------------------------------------------------------- reading elevation

class Grid:
    """A regular elevation grid: z[row][col], row 0 at the north (largest y), cell centres."""

    def __init__(self, x0, y_top, cell, z, nodata=None):
        self.x0, self.y_top, self.cell, self.z, self.nodata = x0, y_top, cell, z, nodata
        self.rows, self.cols = len(z), len(z[0])

    def height(self, x, y):
        """Bilinear elevation at (x, y), or None outside the grid or on missing data."""
        c, r = (x - self.x0) / self.cell, (self.y_top - y) / self.cell
        if not (0 <= c <= self.cols - 1 and 0 <= r <= self.rows - 1):
            return None
        c0, r0 = min(int(c), self.cols - 2), min(int(r), self.rows - 2)
        fc, fr = c - c0, r - r0
        vals = [self.z[r0][c0], self.z[r0][c0 + 1], self.z[r0 + 1][c0], self.z[r0 + 1][c0 + 1]]
        if any(v is None for v in vals):
            return None
        top = vals[0] * (1 - fc) + vals[1] * fc
        bot = vals[2] * (1 - fc) + vals[3] * fc
        return top * (1 - fr) + bot * fr


def read_asc(path):
    head, data = {}, []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            if parts[0][:1].isalpha() and len(parts) == 2 and not data:
                head[parts[0].lower()] = float(parts[1])
            else:
                data.extend(parts)
    try:
        cols, rows, cell = int(head["ncols"]), int(head["nrows"]), head["cellsize"]
    except KeyError:
        raise TerrainError("not an ESRI ASCII grid (ncols, nrows, cellsize missing)")
    if len(data) != rows * cols:
        raise TerrainError("the grid holds %d values, expected %d" % (len(data), rows * cols))
    nodata = head.get("nodata_value")
    x0 = head["xllcenter"] if "xllcenter" in head else head.get("xllcorner", 0.0) + cell / 2
    y0 = head["yllcenter"] if "yllcenter" in head else head.get("yllcorner", 0.0) + cell / 2
    vals = [float(v) for v in data]
    z = [[None if nodata is not None and v == nodata else v for v in vals[r * cols:(r + 1) * cols]] for r in range(rows)]
    return Grid(x0, y0 + (rows - 1) * cell, cell, z, nodata)


def read_xyz(path):
    pts = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            parts = line.replace(",", " ").replace(";", " ").split()
            if len(parts) < 3:
                continue
            try:
                pts.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue  # a header
    if len(pts) < 4:
        raise TerrainError("no x y z rows found")
    xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
    cell = min(b - a for a, b in zip(xs, xs[1:])) if len(xs) > 1 else 1.0
    cols, rows = int(round((xs[-1] - xs[0]) / cell)) + 1, int(round((ys[-1] - ys[0]) / cell)) + 1
    if rows * cols > 25_000_000:
        raise TerrainError("the grid is too large: crop it first")
    z = [[None] * cols for _ in range(rows)]
    for x, y, h in pts:
        z[int(round((ys[-1] - y) / cell))][int(round((x - xs[0]) / cell))] = h
    return Grid(xs[0], ys[-1], cell, z)


def read_dem(path):
    p = Path(path)
    if p.suffix.lower() in (".asc", ".grd"):
        return read_asc(p)
    if p.suffix.lower() in (".xyz", ".txt", ".csv"):
        return read_xyz(p)
    if p.suffix.lower() in (".tif", ".tiff"):
        raise TerrainError("GeoTIFF is not read directly: export an ASCII grid "
                           "(e.g. gdal_translate -of AAIGrid tile.tif tile.asc) or XYZ")
    raise TerrainError("unknown elevation format %r (.asc or .xyz)" % p.suffix)


DEM_SUFFIXES = (".asc", ".grd", ".xyz", ".txt", ".csv")


def dem_files(paths):
    """The elevation files named: files, or every .asc/.xyz in a folder (tiles of one dataset)."""
    out = []
    for path in ([paths] if isinstance(paths, (str, Path)) else list(paths)):
        p = Path(path)
        if p.is_dir():
            found = sorted(q for q in p.iterdir() if q.suffix.lower() in DEM_SUFFIXES)
            if not found:
                raise TerrainError("no .asc or .xyz files in %s" % p)
            out += found
        else:
            if p.suffix.lower() in (".tif", ".tiff"):
                read_dem(p)  # raises the conversion hint
            if p.suffix.lower() not in DEM_SUFFIXES:
                raise TerrainError("unknown elevation format %r (.asc or .xyz)" % p.suffix)
            out.append(p)
    if not out:
        raise TerrainError("no elevation files given")
    return out


def _points(path):
    """Stream (x, y, z) from one file: XYZ rows, or an ASCII grid's cell centres (missing values skipped)."""
    if Path(path).suffix.lower() in (".asc", ".grd"):
        g = read_asc(path)
        for r, row in enumerate(g.z):
            for c, h in enumerate(row):
                if h is not None:
                    yield g.x0 + c * g.cell, g.y_top - r * g.cell, h
        return
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            parts = line.replace(",", " ").replace(";", " ").split()
            if len(parts) < 3:
                continue
            try:
                yield float(parts[0]), float(parts[1]), float(parts[2])
            except ValueError:
                continue  # a header


def _cell_of(path):
    """The grid spacing of a file, from its header or its first rows."""
    if Path(path).suffix.lower() in (".asc", ".grd"):
        return read_asc(path).cell
    xs = set()
    for i, (x, _, _) in enumerate(_points(path)):
        xs.add(x)
        if i > 2000:
            break
    xs = sorted(xs)
    if len(xs) < 2:
        raise TerrainError("cannot tell the grid spacing of %s" % path)
    return min(b - a for a, b in zip(xs, xs[1:]))


def first_point(paths):
    for p in dem_files(paths):
        for pt in _points(p):
            return pt
    raise TerrainError("no x y z values found")


def bounds(paths):
    """(xmin, ymin, xmax, ymax) of every point (one streaming pass)."""
    xmin = ymin = math.inf
    xmax = ymax = -math.inf
    for p in dem_files(paths):
        for x, y, _ in _points(p):
            xmin, xmax, ymin, ymax = min(xmin, x), max(xmax, x), min(ymin, y), max(ymax, y)
    if xmin == math.inf:
        raise TerrainError("no x y z values found")
    return xmin, ymin, xmax, ymax


def read_area(paths, area, spacing=None):
    """One grid from several tiles, cropped to area = (xmin, ymin, xmax, ymax) with a small margin
    and thinned to about half the sampling spacing (the full 2 m data of a massif would not fit in
    memory, and the sampler never needs it). The true lowest and highest points inside the area
    are kept as `zmin_true` / `zmax_true`, so a summit is never under-reported by the thinning."""
    files = dem_files(paths)
    cell = _cell_of(files[0])
    k = max(1, int((spacing or cell) / (2 * cell)))
    step = cell * k
    margin = 2 * step
    ax0, ay0, ax1, ay1 = area[0] - margin, area[1] - margin, area[2] + margin, area[3] + margin
    x0 = y0 = None
    kept = {}
    zlo, zhi = math.inf, -math.inf
    for f in files:
        for x, y, h in _points(f):
            if not (ax0 <= x <= ax1 and ay0 <= y <= ay1):
                continue
            if area[0] <= x <= area[2] and area[1] <= y <= area[3]:
                zlo, zhi = min(zlo, h), max(zhi, h)
            if x0 is None:
                x0, y0 = x, y
            i, j = round((x - x0) / cell), round((y - y0) / cell)
            if i % k == 0 and j % k == 0:
                kept[(i // k, j // k)] = h
    if len(kept) < 4:
        raise TerrainError("the elevation data does not cover the area")
    ii, jj = [a for a, _ in kept], [b for _, b in kept]
    imin, imax, jmin, jmax = min(ii), max(ii), min(jj), max(jj)
    z = [[kept.get((i, j)) for i in range(imin, imax + 1)] for j in range(jmax, jmin - 1, -1)]
    g = Grid(x0 + imin * step, y0 + jmax * step, step, z)
    g.zmin_true, g.zmax_true = zlo, zhi
    return g


def read_gpx(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    pts = []
    for tag in re.findall(r"<(?:trkpt|rtept)\b[^>]*>", text):
        lat, lon = re.search(r'lat="([-0-9.]+)"', tag), re.search(r'lon="([-0-9.]+)"', tag)
        if lat and lon:
            pts.append((float(lat.group(1)), float(lon.group(1))))
    if len(pts) < 2:
        raise TerrainError("the GPX file has no track points")
    return pts


# ---------------------------------------------------------------------------- the construct

def ladder(extent, cls=None):
    for name, top, stage in LADDER:
        if (cls and name == cls) or (not cls and extent <= top):
            return name, stage
    raise TerrainError("unknown scale class %r (spot, site, valley, massif, range)" % cls)


def build(dem, center=None, extent=None, bbox=None, crs=None, resolution=72, cls=None, exaggeration=1.0,
          title="Terrain", source_title="Elevation data", source_ref=None, rights="permitted", gpx=None,
          marks=(), view_from="S", identifier=None):
    if isinstance(dem, Grid):
        grid, fx, fy = dem, dem.x0, dem.y_top
    else:
        grid = None
        fx, fy, _ = first_point(dem)
    crs = crs or guess_crs(fx, fy)
    if bbox:
        xmin, ymin, xmax, ymax = bbox
    elif center and extent:
        cx, cy = to_crs(crs, *center)
        half = extent / 2 if crs != "EPSG:4326" else extent / 2 / 111320.0
        xmin, xmax, ymin, ymax = cx - half, cx + half, cy - half, cy + half
    elif grid is not None:
        xmin, xmax = grid.x0, grid.x0 + (grid.cols - 1) * grid.cell
        ymin, ymax = grid.y_top - (grid.rows - 1) * grid.cell, grid.y_top
    else:
        xmin, ymin, xmax, ymax = bounds(dem)
    if grid is None:
        # read only the area, thinned to the sampling: tiles of a whole massif stay small
        grid = read_area(dem, (xmin, ymin, xmax, ymax), max(xmax - xmin, ymax - ymin) / max(8, min(int(resolution), MAX_RESOLUTION)))
    # metres per unit of the grid's coordinates (degrees in EPSG:4326)
    mx = 111320.0 * math.cos(math.radians((ymin + ymax) / 2)) if crs == "EPSG:4326" else 1.0
    my = 110540.0 if crs == "EPSG:4326" else 1.0
    width_m, depth_m = (xmax - xmin) * mx, (ymax - ymin) * my
    if width_m <= 0 or depth_m <= 0:
        raise TerrainError("the area is empty")
    n = max(8, min(int(resolution), MAX_RESOLUTION))
    cols = n if width_m >= depth_m else max(8, int(round(n * width_m / depth_m)))
    rows = n if depth_m >= width_m else max(8, int(round(n * depth_m / width_m)))
    real = []
    for r in range(rows):
        y = ymax - (ymax - ymin) * r / (rows - 1)
        row = []
        for c in range(cols):
            h = grid.height(xmin + (xmax - xmin) * c / (cols - 1), y)
            if h is None:
                raise TerrainError("the area reaches beyond the elevation data (or into missing values): "
                                   "make it smaller or supply a larger tile")
            row.append(h)
        real.append(row)
    zmin = min(min(r) for r in real)
    zmax = max(max(r) for r in real)
    # the facts report the data's own extremes inside the area, not the sampled grid's
    true_lo, true_hi = getattr(grid, "zmin_true", zmin), getattr(grid, "zmax_true", zmax)
    extent_m = max(width_m, depth_m)
    cls, stage = ladder(extent_m, cls)
    s = stage / extent_m
    v = s * exaggeration
    base = 0.02 * stage  # a plinth under the lowest point
    heights = [[round(base + (h - zmin) * v, 5) for h in row] for row in real]
    contour_real = _nice((zmax - zmin) / 12)
    size = [round(width_m * s, 5), round(depth_m * s, 5)]

    def place(lat, lon, lift=0.0):
        x, y = to_crs(crs, lat, lon)
        h = grid.height(x, y)
        if h is None:
            return None
        return [round(((x - xmin) * mx - width_m / 2) * s, 5), round(base + (h - zmin) * v + lift, 5),
                round((-(y - ymin) * my + depth_m / 2) * s, 5)]
    ident = identifier or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "terrain"
    scene = {
        "format": "construct-scene", "version": 2, "id": ident, "title": title,
        "subject": {"category": "architecture" if cls in ("spot", "site") else "other", "accuracy": "documented",
                    "synthetic": False, "summary": "%s: measured terrain, %.0f x %.0f m, elevation %.0f-%.0f m, at 1:%s%s."
                    % (title, width_m, depth_m, true_lo, true_hi, _ratio(s), "" if exaggeration == 1 else
                       ", heights exaggerated %gx" % exaggeration)},
        "units": "m", "seed": 7,
        "sources": [{"id": "dem", "kind": "dataset", "title": source_title, "rights": rights,
                     **({"ref": source_ref} if source_ref else {})}],
        "facts": [
            {"key": "terrain.extent", "value": "%.0f x %.0f" % (width_m, depth_m), "unit": "m", "certainty": "verified", "source": "dem"},
            {"key": "elevation.min", "value": round(true_lo, 1), "unit": "m", "certainty": "verified", "source": "dem"},
            {"key": "elevation.max", "value": round(true_hi, 1), "unit": "m", "certainty": "verified", "source": "dem"},
            {"key": "terrain.class", "value": cls, "certainty": "inferred", "note": "from the extent, on the scale ladder"},
            {"key": "terrain.scale", "value": "1:%s" % _ratio(s), "certainty": "inferred", "note": "the stage scale for this class"},
            {"key": "terrain.vertical_exaggeration", "value": exaggeration, "certainty": "decorative",
             "note": "1 means true heights"}],
        "parts": [{"id": "terrain", "label": "Terrain", "role": "mass", "certainty": "verified", "source": "dem", "stage": 0,
                   "basis": ["terrain.extent", "elevation.min", "elevation.max"],
                   "shape": {"type": "terrain", "size": size, "heights": heights,
                             "contour": round(contour_real * v, 6), "grid_every": max(2, n // 12)},
                   "note": "sampled from the elevation data on a %dx%d grid; contours every %g m" % (cols, rows, contour_real)}],
        "annotations": [],
        "presentation": {"framing": {"yaw": VIEW_YAW.get(view_from.upper(), 0), "pitch": 24, "fit": 1.0}},
        "animation": {"assembly": {"style": "ceremony", "seconds": 5.0, "interference": True},
                      "idle": {"life": "calm", "events": ["scan", "sweep", "shimmer"], "cadence": [6, 12], "strength": 0.5},
                      "camera": {"drift": 4, "breathe": 0.02}},
    }
    if gpx:
        track = read_gpx(gpx)
        pts = [q for q in (place(lat, lon, lift=0.002 * stage) for lat, lon in track) if q]
        if len(pts) < 2:
            raise TerrainError("the route lies outside the terrain")
        pts = pts[:: max(1, len(pts) // 200)]
        scene["sources"].append({"id": "track", "kind": "measurement", "title": "The route (GPX)", "rights": "user_private"})
        scene["parts"].append({"id": "route", "label": "Route", "role": "data", "certainty": "user_supplied", "source": "track",
                               "stage": 2, "shape": {"type": "curve", "points": pts}, "look": {"glow": 0.8}})
        scene["annotations"].append({"id": "route", "text": "Route", "part": "route"})
    for i, mark in enumerate(marks):
        name, _, coords = mark.partition("=")
        try:
            lat, lon = (float(x) for x in coords.split(","))
        except ValueError:
            raise TerrainError("--mark is Name=lat,lon")
        q = place(lat, lon, lift=0.004 * stage)
        if q is None:
            raise TerrainError("%s lies outside the terrain" % name)
        pid = "mark-%d" % (i + 1)
        scene["parts"].append({"id": pid, "label": name, "role": "identity", "certainty": "user_supplied", "stage": 3,
                               "shape": {"type": "marker", "sprite": "ring", "size_px": 14}, "at": q})
        scene["annotations"].append({"id": pid, "text": name, "part": pid})
    if not scene["annotations"]:
        del scene["annotations"]
    return scene


def _nice(x):
    if x <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(x))
    return next(m * p for m in (1, 2, 5, 10) if m * p >= x)


def _ratio(s):
    r = 1 / s
    return "{:,}".format(int(round(r, -int(math.floor(math.log10(r))) + 2))).replace(",", " ")
