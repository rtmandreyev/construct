"""A simulation you can hold: a NetLogo run as printed plates, one per moment, that stack in order on pins.

Each plate is the world at one tick, seen from above: every turtle a raised dot (taller where its
true/false state is on: infected, lit, moving), every link a low ridge. Two pin holes of different
sizes key the plates so they stack one way round, and each plate's number is engraved as dots in its
corner. Pins and spacer sleeves are printed too, and a key card says what each plate is: its tick,
its counts, the model and the recording's fingerprint. Stacked, the plates replay the run from the
bottom up; taken apart, they step back through time.

The plates are made like a print (`printing`): voxels at the print's own scale, so every file is one
watertight solid. Python standard library only.
"""

import hashlib
import math
from pathlib import Path

from . import netlogo, printing

COUNT = 6              # plates, unless the ticks are given
SIZE_MM = 100.0        # the world's longer side on a plate
DETAIL_MM = 0.25       # one voxel
BORDER_MM = 8.0        # the rim around the world: pins and the plate's number
THICK_MM = 2.4         # a plate
DOT_MM = 2.0           # a turtle's dot (no smaller than the world allows)
LOW_MM, HIGH_MM = 1.0, 3.0   # a dot's height: state off, state on (or every dot, with no state)
LINK_MM = (0.8, 0.6)   # a link's ridge: width, height
GAP_MM = HIGH_MM + 2.0 # between plates: the tallest dot and some air
PINS_MM = (3.0, 4.0)   # the two pins, so a plate fits one way round
CLEAR_MM = 0.3         # a hole's clearance over its pin
SLEEVE_MM = 2.0        # a spacer sleeve's wall


class PlatesError(ValueError):
    """Plates that cannot be made: a run without turtles, a tick outside the run, a world too small to print."""


def _state_index(run, wanted=None):
    """The true/false turtle variable shown by height (the one named, or the first): (its name, its index in a
    turtle row), or (None, None)."""
    names = run["header"].get("turtle-vars") or []
    if wanted and wanted not in names:
        raise PlatesError("no turtle variable %r in the recording (it has: %s)" % (wanted, ", ".join(names) or "none"))
    for k, name in enumerate(names):
        if wanted and name != wanted:
            continue
        vals = {row[5 + k] for f in run["frames"][:50] for row in f.get("turtles", ()) if len(row) > 5 + k}
        if vals and vals <= {True, False}:
            return name, 5 + k
        if wanted:
            raise PlatesError("%r is not a true/false variable" % wanted)
    return None, None


def _frame_at(run, tick):
    best = None
    for f in run["frames"]:
        if f["t"] <= tick:
            best = f
        else:
            break
    return best


def _links_at(run, tick):
    links = []
    for f in run["frames"]:
        if f["t"] > tick:
            break
        if "links" in f:
            links = f["links"]
    return links


def choose_ticks(run, count=COUNT, at=None):
    """The moments to print: the given ticks, or `count` evenly spaced from the first to the last."""
    first, last = run["frames"][0]["t"], run["frames"][-1]["t"]
    if at:
        bad = [t for t in at if not first <= t <= last]
        if bad:
            raise PlatesError("tick %s is outside the run (%d to %d)" % (bad[0], first, last))
        return sorted(set(int(t) for t in at))
    if count < 2:
        raise PlatesError("at least 2 plates")
    return sorted({int(round(first + (last - first) * k / (count - 1))) for k in range(count)})


class _Plate:
    """A voxel set on a plate's lattice: columns are (i, j) ints, bit k is the layer k."""

    def __init__(self, w_mm, d_mm, h):
        self.h = h
        self.n = (int(math.ceil(w_mm / h)), int(math.ceil(d_mm / h)))
        self.cols = {}

    def disc(self, x, y, r, k0, k1, cut=False):
        """Set (or clear) layers k0..k1 in a disc of radius r mm at (x, y) mm."""
        m = ((1 << (k1 - k0 + 1)) - 1) << k0
        i0, i1 = max(0, int((x - r) / self.h)), min(self.n[0] - 1, int((x + r) / self.h))
        j0, j1 = max(0, int((y - r) / self.h)), min(self.n[1] - 1, int((y + r) / self.h))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                cx, cy = (i + 0.5) * self.h, (j + 0.5) * self.h
                if (cx - x) ** 2 + (cy - y) ** 2 <= r * r:
                    self._put((i, j), m, cut)

    def ridge(self, a, b, w, k0, k1):
        m = ((1 << (k1 - k0 + 1)) - 1) << k0
        (ax, ay), (bx, by) = a, b
        i0, i1 = max(0, int((min(ax, bx) - w) / self.h)), min(self.n[0] - 1, int((max(ax, bx) + w) / self.h))
        j0, j1 = max(0, int((min(ay, by) - w) / self.h)), min(self.n[1] - 1, int((max(ay, by) + w) / self.h))
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy or 1e-9
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                cx, cy = (i + 0.5) * self.h, (j + 0.5) * self.h
                t = max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / ll))
                if (cx - ax - t * dx) ** 2 + (cy - ay - t * dy) ** 2 <= (w / 2) ** 2:
                    self._put((i, j), m, False)

    def slab(self, k1):
        m = (1 << (k1 + 1)) - 1
        for i in range(self.n[0]):
            for j in range(self.n[1]):
                self.cols[(i, j)] = self.cols.get((i, j), 0) | m

    def _put(self, c, m, cut):
        if cut:
            self.cols[c] = self.cols.get(c, 0) & ~m
        else:
            self.cols[c] = self.cols.get(c, 0) | m

    def mesh(self, title):
        cols = {c: m for c, m in self.cols.items() if m}
        printing._manifold(cols)
        verts, faces = printing._surface_flat(cols)
        verts = [[p[0] * self.h, p[1] * self.h, p[2] * self.h] for p in verts]
        bad = printing._edges_ok(faces)
        return {"vertices": verts, "triangles": faces, "title": title,
                "report": {"scale": "plate", "watertight": bad == 0, "bad_edges": bad}}


def _layers(mm, h):
    return max(1, int(round(mm / h)))


def make(run, count=COUNT, at=None, size=SIZE_MM, detail=DETAIL_MM, title=None, state=None, tall=True):
    """The plates of a run: {"plates": [{"tick", "number", "mesh", "turtles", "on", "links"}], "pins": [mesh],
    "sleeves": mesh, "state": name, "tall": value}. A turtle's dot is tall where `state` (the first true/false
    variable, unless named) is `tall`."""
    if not any(f.get("turtles") for f in run["frames"]):
        raise PlatesError("the run has no turtles to show")
    world = run["header"]["world"]
    wx0, wx1 = world["min-pxcor"] - 0.5, world["max-pxcor"] + 0.5
    wy0, wy1 = world["min-pycor"] - 0.5, world["max-pycor"] + 0.5
    s = size / max(wx1 - wx0, wy1 - wy0)                 # mm per patch
    w_mm, d_mm = (wx1 - wx0) * s + 2 * BORDER_MM, (wy1 - wy0) * s + 2 * BORDER_MM
    if s * 1.0 < 0.5:
        raise PlatesError("the world is %d patches across: too many for %g mm (a patch would be %.2f mm); "
                          "print larger (--size)" % (max(wx1 - wx0, wy1 - wy0), size, s))
    h = detail
    ticks = choose_ticks(run, count, at)
    state, si = _state_index(run, state)
    dot = max(min(DOT_MM, s * 0.9), 1.0)
    k_top = _layers(THICK_MM, h) - 1
    k_low, k_high = k_top + _layers(LOW_MM, h), k_top + _layers(HIGH_MM, h)
    pins = [(BORDER_MM / 2, BORDER_MM / 2, PINS_MM[0]), (w_mm - BORDER_MM / 2, d_mm - BORDER_MM / 2, PINS_MM[1])]
    to_mm = lambda x, y: ((x - wx0) * s + BORDER_MM, (y - wy0) * s + BORDER_MM)
    name = title or run["header"].get("title") or "run"
    plates = []
    for n, tick in enumerate(ticks, 1):
        f = _frame_at(run, tick)
        p = _Plate(w_mm, d_mm, h)
        p.slab(k_top)
        turtles = {row[0]: row for row in f.get("turtles", ())}
        links = _links_at(run, tick)
        half = (wx1 - wx0) / 2
        drawn = 0
        for a, b, _ in links:
            if a in turtles and b in turtles:
                ta, tb = turtles[a], turtles[b]
                if abs(ta[2] - tb[2]) > half or abs(ta[3] - tb[3]) > half:
                    continue   # a link across the world's wrapped edge
                p.ridge(to_mm(ta[2], ta[3]), to_mm(tb[2], tb[3]), LINK_MM[0], k_top + 1,
                        k_top + _layers(LINK_MM[1], h))
                drawn += 1
        on = 0
        for row in turtles.values():
            hi = si is None or bool(row[si]) == tall
            on += si is not None and bool(row[si]) == tall
            x, y = to_mm(row[2], row[3])
            p.disc(x, y, dot / 2, k_top + 1, k_high if hi else k_low)
        for x, y, d in pins:   # through holes for the pins
            p.disc(x, y, (d + CLEAR_MM) / 2, 0, k_high, cut=True)
        for k in range(n):     # the plate's number: n dots, engraved in the front right corner
            p.disc(w_mm - BORDER_MM - 2.0 - 2.4 * k, BORDER_MM / 2, 0.7, k_top - _layers(0.6, h) + 1, k_high, cut=True)
        plates.append({"tick": tick, "number": n, "turtles": len(turtles), "on": on, "links": drawn,
                       "mesh": p.mesh("%s, plate %d (tick %d)" % (name, n, tick))})
    stack = len(ticks) * THICK_MM + (len(ticks) - 1) * GAP_MM
    pin_meshes = []
    for d in PINS_MM:
        p = _Plate(d + 2, d + 2, h)
        p.disc((d + 2) / 2, (d + 2) / 2, d / 2, 0, _layers(stack + THICK_MM, h) - 1)
        pin_meshes.append(p.mesh("%s, %g mm pin" % (name, d)))
    sl = _Plate(4 * (max(PINS_MM) + CLEAR_MM + 2 * SLEEVE_MM + 2), 2 * (max(PINS_MM) + CLEAR_MM + 2 * SLEEVE_MM + 2), h)
    k_sl = _layers(GAP_MM, h) - 1
    pitch = max(PINS_MM) + CLEAR_MM + 2 * SLEEVE_MM + 2
    for row, d in enumerate(PINS_MM):
        for col in range(4):
            cx, cy = pitch * (col + 0.5), pitch * (row + 0.5)
            p_out = (d + CLEAR_MM) / 2 + SLEEVE_MM
            sl.disc(cx, cy, p_out, 0, k_sl)
            sl.disc(cx, cy, (d + CLEAR_MM) / 2, 0, k_sl, cut=True)
    return {"plates": plates, "pins": pin_meshes, "sleeves": sl.mesh("%s, spacer sleeves" % name),
            "state": state, "tall": tall, "size_mm": [round(w_mm, 1), round(d_mm, 1)], "stack_mm": round(stack, 1),
            "title": name}


def key_card(result, run, recording=None):
    """What each plate is, and how to put them together (Markdown)."""
    hdr = run["header"]
    lines = ["# %s: a run you can hold" % result["title"], "",
             "%d plates, %s x %s mm, stacked %s mm tall on two pins (3 mm and 4 mm: a plate fits one way round)."
             % (len(result["plates"]), result["size_mm"][0], result["size_mm"][1], result["stack_mm"]), "",
             "Plate 1 goes at the bottom. Each plate's number is the dots in its front right corner. Push the pins "
             "through plate 1, then a sleeve on each pin, then plate 2, and so on: the run rises from the first "
             "tick to the last.", ""]
    st = result["state"]
    tv = "true" if result["tall"] else "false"
    lines += ["| Plate | Tick | Turtles | %s | Links |" % ("With %s %s (the tall dots)" % (st, tv) if st else "—"),
              "| --- | --- | --- | --- | --- |"]
    for p in result["plates"]:
        lines.append("| %d | %d | %d | %s | %d |" % (p["number"], p["tick"], p["turtles"], p["on"] if st else "—",
                                                    p["links"]))
    lines += ["", "Each dot is one turtle where it was at that tick; %s Links are the low ridges."
              % ("a tall dot is one with `%s` %s, a short one %s." % (st, tv, "false" if result["tall"] else "true")
                 if st else "every dot is the same height."),
              "", "Model: %s (NetLogo %s), seed %s." % (hdr.get("title", "?"), hdr.get("netlogo", "?"),
                                                      hdr.get("seed") if hdr.get("seed") is not None else "not recorded")]
    if recording:
        digest = hashlib.sha256(Path(recording).read_bytes()).hexdigest()
        lines += ["Recording: `%s`, sha256 `%s`: the plates show this recording and nothing else."
                  % (Path(recording).name, digest)]
    return "\n".join(lines) + "\n"


def write(run, out, fmt="3mf", recording=None, **kw):
    """Make the plates and write them to the folder `out`: plate-NN-tick-T, pin-3mm, pin-4mm, sleeves, KEY.md."""
    if fmt not in printing.FORMATS:
        raise PlatesError("format: 3mf or stl")
    res = make(run, **kw)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    enc = printing.to_3mf if fmt == "3mf" else printing.to_stl
    files = []
    for p in res["plates"]:
        path = out / ("plate-%02d-tick-%d.%s" % (p["number"], p["tick"], fmt))
        path.write_bytes(enc(p["mesh"]))
        files.append(path)
    for d, m in zip(PINS_MM, res["pins"]):
        path = out / ("pin-%gmm.%s" % (d, fmt))
        path.write_bytes(enc(m))
        files.append(path)
    path = out / ("sleeves.%s" % fmt)
    path.write_bytes(enc(res["sleeves"]))
    files.append(path)
    (out / "KEY.md").write_text(key_card(res, run, recording), encoding="utf-8")
    files.append(out / "KEY.md")
    res["files"] = [str(f) for f in files]
    res["watertight"] = all(m["report"]["watertight"] for m in [p["mesh"] for p in res["plates"]] + res["pins"]
                            + [res["sleeves"]])
    return res
