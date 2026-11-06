"""FreeCAD: a construct as named solids with its joints, saved as a FreeCAD document (.FCStd) and STEP.

Construct writes what it knows as data (every part's closed pieces and surfaces in millimetres,
Z up, its role, certainty, source and stage, and each articulation's type, axis, pivot and amount),
then runs FreeCAD on it: its app off screen when it is there, so the document opens with every part
showing (FreeCAD's command line saves the model but not how it looks), else `freecadcmd`. In FreeCAD:
  - each part is a `Part::Feature` labelled with its id (its label as `Label2`), its closed pieces
    sewn into solids and refined (coplanar facets merged into faces), its open surfaces kept as
    shells; its provenance in the property group "Construct";
  - parts that do not move sit in a group per assembly stage (`stage-0`, `stage-1`, …); the parts of
    an articulation sit in a group for it (`joint-<id>`), nested as the joints ride on one another,
    with the joint's type, axis, pivot and range, an `Open` placement (set the group's Placement to it
    to open the joint) and its axis drawn as a line;
  - STEP keeps the same tree and names.

Parts drawn only in lines and the construct's annotations are left out, as in a print.

With `exact` (the default), parts are rebuilt from their own parameters as true CAD shapes: boxes,
cylinders, cones, spheres and tori as exact solids, lathes revolved from a spline through their profile,
extrusions from their profile, lofts as smooth NURBS surfaces through their sections, tubes swept along a
spline; profiles keep their sharp corners and are smooth between them. Each is checked against the
construct's own surfaces (the same box, within a tolerance); a shape that fails, and every other kind
(curves, paths, terrain, the architecture kit), is faceted as the construct draws it. Python standard
library only on this side; FreeCAD 1.0 or newer on the other.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import printing, product, scene as scene_mod


class FreeCADError(RuntimeError):
    """FreeCAD could not be found or did not finish."""


def find_freecad(given=None):
    """A FreeCAD command line to run: the one given (None if it is not there), $CONSTRUCT_FREECAD,
    `freecadcmd` on the PATH, or the usual installs."""
    if given:
        return given if os.path.isfile(given) else shutil.which(given)
    cands = [os.environ.get("CONSTRUCT_FREECAD"), shutil.which("freecadcmd"), shutil.which("FreeCADCmd"),
             "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
             os.path.expanduser("~/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"),
             "/usr/bin/freecadcmd", "/usr/bin/FreeCADCmd"]
    cands += sorted(glob.glob(r"C:\Program Files\FreeCAD*\bin\FreeCADCmd.exe"), reverse=True)
    return next((c for c in cands if c and os.path.isfile(c)), None)


def _mm(p):
    """A construct point (metres, Y up) in FreeCAD's frame (millimetres, Z up)."""
    return [round(p[0] * 1000.0, 4), round(-p[2] * 1000.0, 4), round(p[1] * 1000.0, 4)]


def _dir(v):
    return [v[0], -v[2], v[1]]


EXACT_TYPES = ("box", "cylinder", "cone", "sphere", "torus", "lathe", "extrude", "loft", "tube")
# metres, Y up -> millimetres, Z up
FRAME = ((1000.0, 0.0, 0.0), (0.0, 0.0, -1000.0), (0.0, 1000.0, 0.0))


def _exact_spec(part):
    """What FreeCAD needs to build a part from its parameters: the shape in its own frame (metres, Y up) and,
    for each copy, the 4x4 matrix that places it in FreeCAD's frame. None for a shape it cannot build."""
    sh = part["shape"]
    t = sh["type"]
    if t not in EXACT_TYPES:
        return None
    spec = {"type": t}
    if t == "box":
        spec.update(size=list(sh["size"]), base=sh.get("anchor") == "base")
    elif t in ("cylinder", "cone"):
        spec.update(r0=sh.get("radius", sh.get("radius_bottom")), r1=sh.get("radius", sh.get("radius_top")),
                    height=sh["height"], caps=sh.get("caps", True))
    elif t == "sphere":
        radii = sh.get("radii") or [sh["radius"]] * 3
        spec.update(radii=list(radii), base=sh.get("anchor") == "base")
    elif t == "torus":
        spec.update(major=sh["major"], minor=sh["minor"])
    elif t == "lathe":
        spec.update(profile=[list(p) for p in sh["profile"]])
    elif t == "extrude":
        spec.update(profile=[list(p) for p in sh["profile"]], height=sh["height"], axis=sh.get("axis", "y"))
    elif t == "loft":
        from . import shapes
        spec.update(rings=[[[x, y, sec[0]] for x, y in shapes.loft_ring(sec[1], sec[2], sec[3],
                                                                          sec[4] if len(sec) > 4 else None,
                                                                          sh.get("round", 0.35))]
                           for sec in sh["sections"]])
    elif t == "tube":
        r = sh["radius"]
        if isinstance(r, list) and max(r) - min(r) > 1e-9:
            return None   # a tapered tube: faceted, as drawn
        spec.update(path=[list(p) for p in sh["path"]], radius=max(r) if isinstance(r, list) else r,
                    smooth=sh.get("smooth", True))
    mats = []
    for xf, _, _, _ in scene_mod._instances(part):
        o = xf((0.0, 0.0, 0.0))
        cols = [[xf(e)[k] - o[k] for k in range(3)] for e in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
        lin = [[cols[c][r] for c in range(3)] for r in range(3)]   # rows of the copy's linear map
        m = [[sum(FRAME[i][k] * lin[k][j] for k in range(3)) for j in range(3)] +
             [sum(FRAME[i][k] * o[k] for k in range(3))] for i in range(3)]
        mats.append(m + [[0.0, 0.0, 0.0, 1.0]])
    spec["matrices"] = mats
    return spec


def payload(scene, exact=True):
    """The data FreeCAD builds from: {"title", "id", "parts": [...], "articulations": [...], "left_out"}."""
    g = scene_mod.compile_scene(scene, solid=True)
    styles, parts = g["styles"], g["parts"]
    tris = {}
    f = g["fills"]
    for i in range(0, len(f), 15):
        pi = int(styles[int(f[i + 3])][6])
        if not parts[pi].get("floating"):
            tris.setdefault(pi, []).append(tuple(tuple(_mm((f[i + 5 * j], f[i + 5 * j + 1], f[i + 5 * j + 2])))
                                                 for j in range(3)))
    out_parts, left_out = [], []
    for pi, part in enumerate(parts):
        if pi not in tris:
            left_out.append(part["id"])
            continue
        solids, shells = [], []
        for piece in printing._pieces(tris[pi]):
            (solids if printing._is_closed(piece) else shells).append([list(map(list, t)) for t in piece])
        out_parts.append({"id": part["id"], "label": part.get("label") or "", "role": part["role"],
                          "certainty": part["certainty"], "source": part.get("source") or "",
                          "basis": list(part.get("basis") or []), "stage": part["stage"],
                          "chain": list(g["joints"][part["joint"]]) if part.get("joint", -1) >= 0 else [],
                          "solids": solids, "shells": shells,
                          "exact": _exact_spec(scene["parts"][pi]) if exact else None})
    arts = []
    for a in g["articulations"]:
        rot = a["type"] in ("hinge", "turn")
        arts.append({"id": a["id"], "type": a["type"], "axis": _dir(a["axis"]),
                     "pivot": _mm(a["pivot"]) if a.get("pivot") else None,
                     "amount": a["amount"] if rot else round(a["amount"] * 1000.0, 4),
                     "unit": "deg" if rot else "mm", "order": a["order"]})
    return {"title": g["title"], "id": g["id"], "contract": g["contract"],
            "application": "%s %s" % (product.TITLE, product.VERSION), "parts": out_parts,
            "articulations": arts, "left_out": left_out}


# Runs inside FreeCAD: reads its job (JOB, put before this when the script is written), writes its result beside it.
SCRIPT = r'''
import json, os, re
import FreeCAD, Part, Mesh, Import

job = json.load(open(JOB, encoding="utf-8"))
data = json.load(open(job["payload"], encoding="utf-8"))
doc = FreeCAD.newDocument(re.sub(r"[^A-Za-z0-9_]", "_", data["id"]) or "construct")
V = FreeCAD.Vector


def name(prefix, s):
    return prefix + re.sub(r"[^A-Za-z0-9_]", "_", s)


def group(label, parent=None):
    o = doc.addObject("App::Part", name("g_", label))
    o.Label = label
    (parent.addObject if parent else (lambda x: None))(o)
    return o


def shape_of(tris, solid):
    m = Mesh.Mesh([[V(*p) for p in t] for t in tris])
    s = Part.Shape()
    s.makeShapeFromMesh(m.Topology, 0.001)
    if solid:
        try:
            sol = Part.makeSolid(s).removeSplitter()
            if sol.isValid() and sol.Volume > 0:
                return sol, True
        except Exception:
            pass
    try:
        s = s.removeSplitter()
    except Exception:
        pass
    return s, False


def _smooth_wire(pts, closed, smooth=True):
    """A wire through points: splines between the sharp corners (a turn of more than 35 degrees), straight
    where a run is two points; with `smooth` off, the polygon itself."""
    import math
    P = [V(*p) for p in pts]
    if closed and (P[0] - P[-1]).Length < 1e-12:
        P = P[:-1]
    if not smooth:
        return Part.Wire(Part.makePolygon(P + ([P[0]] if closed else [])))
    n = len(P)

    def turn(i):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        u, w = b - a, c - b
        if u.Length < 1e-12 or w.Length < 1e-12:
            return 0.0
        return math.degrees(u.getAngle(w))
    idx = range(n) if closed else range(1, n - 1)
    corners = [i for i in idx if turn(i) > 35.0]
    if closed and not corners:
        if n < 3:
            return None
        bs = Part.BSplineCurve()
        bs.interpolate(P, PeriodicFlag=True)
        return Part.Wire(bs.toShape())
    if not closed:
        corners = [0] + corners + [n - 1]
    edges = []
    m = len(corners)
    for k in range(m if closed else m - 1):
        a, b = corners[k], corners[(k + 1) % m]
        run = [P[(a + j) % n] for j in range(((b - a) % n if closed else b - a) + 1)] if b != a else [P[a]] + P[a + 1:] + P[:a + 1]
        if len(run) == 2:
            edges.append(Part.LineSegment(run[0], run[1]).toShape())
        elif len(run) > 2:
            bs = Part.BSplineCurve()
            bs.interpolate(run)
            edges.append(bs.toShape())
    return Part.Wire(Part.__sortEdges__(edges)) if edges else None


def _ring_wire(pts, smooth):
    P = []
    for p in pts:   # a point on top of the last is dropped (a tiny corner rounding)
        q = V(*p)
        if not P or (q - P[-1]).Length > 1e-7:
            P.append(q)
    if (P[0] - P[-1]).Length < 1e-7:
        P = P[:-1]
    if not smooth:
        return Part.Wire(Part.makePolygon(P + [P[0]]))
    bs = Part.BSplineCurve()
    bs.interpolate(P, PeriodicFlag=True)
    return Part.Wire(bs.toShape())


def exact_shape(spec, smooth=True):
    """One copy's local shape (metres, Y up), and whether it is closed: smooth (splines through profiles and
    sections) or, the second try, straight between the construct's own points."""
    t = spec["type"]
    Y = V(0, 1, 0)
    if t == "box":
        w, h, d = spec["size"]
        return Part.makeBox(w, h, d, V(-w / 2, 0 if spec["base"] else -h / 2, -d / 2)), True
    if t in ("cylinder", "cone"):
        r0, r1, h = spec["r0"], spec["r1"], spec["height"]
        s = Part.makeCylinder(r0, h, V(0, 0, 0), Y) if abs(r0 - r1) < 1e-12 else Part.makeCone(r0, r1, h, V(0, 0, 0), Y)
        if not spec["caps"]:
            side = [f for f in s.Faces if f.Surface.__class__.__name__ not in ("Plane",)]
            return Part.Shell(side), False
        return s, True
    if t == "sphere":
        rx, ry, rz = spec["radii"]
        s = Part.makeSphere(1.0)
        m = FreeCAD.Matrix()
        m.scale(rx, ry, rz)
        if spec["base"]:
            m.move(V(0, ry, 0))
        return s.transformGeometry(m), True
    if t == "torus":
        return Part.makeTorus(spec["major"], spec["minor"], V(0, 0, 0), Y), True
    if t == "lathe":
        prof = spec["profile"]
        w = _smooth_wire([[r, y, 0.0] for r, y in prof], False, smooth)
        s = w.revolve(V(0, 0, 0), Y, 360)
        closed = prof[0][0] <= 1e-9 and prof[-1][0] <= 1e-9
        if closed:
            try:
                sol = Part.Solid(Part.Shell(s.Faces))
                if sol.isValid():
                    return sol, True
            except Exception:
                pass
        return s, False
    if t == "extrude":
        ax = spec["axis"]
        place = {"y": lambda u, v, w: (u, w, v), "z": lambda u, v, w: (u, v, w), "x": lambda u, v, w: (w, v, u)}[ax]
        wire = _smooth_wire([place(u, v, 0.0) for u, v in spec["profile"]], True, smooth)
        d = V(*place(0.0, 0.0, spec["height"]))
        return Part.Face(wire).extrude(d), True
    if t == "loft":
        # every section one closed spline through its points (their rounding is in the points), so the sections
        # match edge for edge; smooth along the length too, kept low in degree; else ruled, polygons, as drawn
        wires = [_ring_wire(r, smooth) for r in spec["rings"]]
        return (Part.makeLoft(wires, True, False, False, 3) if smooth else Part.makeLoft(wires, True, True)), True
    if t == "tube":
        path = [V(*p) for p in spec["path"]]
        if spec["smooth"] and smooth and len(path) > 2:
            bs = Part.BSplineCurve()
            bs.interpolate(path)
            spine = Part.Wire(bs.toShape())
        else:
            spine = Part.Wire(Part.makePolygon(path))
        e0 = spine.Edges[0]
        circle = Part.Wire(Part.makeCircle(spec["radius"], e0.valueAt(e0.FirstParameter), e0.tangentAt(e0.FirstParameter)))
        return spine.makePipeShell([circle], True, True, 2), True   # rounded where a polyline path turns
    return None, False


why = {}


def exact_part(p):
    """The part as true shapes, every copy placed; None when it does not match the construct's own surfaces."""
    spec = p.get("exact")
    if not spec:
        return None
    pts = [q for piece in p["solids"] + p["shells"] for t in piece for q in t]
    if not pts:
        return None
    lo = [min(q[k] for q in pts) for k in range(3)]
    hi = [max(q[k] for q in pts) for k in range(3)]
    size = max(hi[k] - lo[k] for k in range(3)) or 1.0
    for smooth in (True, False):
        got = _placed(p, spec, smooth, lo, hi, size)
        if got:
            return got
    return None


def _placed(p, spec, smooth, lo, hi, size):
    try:
        local, closed = exact_shape(spec, smooth)
        if local is None or local.isNull():
            why[p["id"]] = "no shape"
            return None
        copies = []
        for rows in spec["matrices"]:
            m = FreeCAD.Matrix(*[x for r in rows for x in r])
            lin = [[rows[i][j] for j in range(3)] for i in range(3)]
            det = (lin[0][0] * (lin[1][1] * lin[2][2] - lin[1][2] * lin[2][1]) -
                   lin[0][1] * (lin[1][0] * lin[2][2] - lin[1][2] * lin[2][0]) +
                   lin[0][2] * (lin[1][0] * lin[2][1] - lin[1][1] * lin[2][0]))
            cols = [sum(lin[i][j] ** 2 for i in range(3)) ** 0.5 for j in range(3)]
            rigid = det > 0 and max(cols) - min(cols) < 1e-6 * max(cols)
            if rigid:   # a rotation, a uniform scale and a move: the surfaces stay exact (a cylinder a cylinder)
                c = local.copy()
                c.transformShape(m, False, True)
            else:       # a mirror or a stretch: as NURBS
                c = local.transformGeometry(m)
            copies.append(c)
        shape = copies[0] if len(copies) == 1 else Part.makeCompound(copies)
        if not shape.isValid():
            why[p["id"]] = "not a valid shape"
            return None
        bb = shape.optimalBoundingBox(True, False)   # the tight box (a NURBS box is its control points')
        got = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
        want = lo + hi
        off = max(abs(a - b) for a, b in zip(got, want))
        if off > 0.04 * size + 0.05:
            why[p["id"]] = "%.2f mm from the construct's surfaces (%s)" % (off, ", ".join("%.1f" % (a - b) for a, b in zip(got, want)))
            return None
        return shape, closed
    except Exception as exc:
        why[p["id"]] = "%s: %s" % (type(exc).__name__, exc)
        return None


root = group(data["id"])
root.addProperty("App::PropertyString", "Title", "Construct").Title = data["title"]
root.addProperty("App::PropertyString", "Contract", "Construct").Contract = data["contract"]
root.addProperty("App::PropertyString", "MadeBy", "Construct").MadeBy = data["application"]
stages, joints = {}, {}
for a in sorted(data["articulations"], key=lambda a: a["order"]):
    joints[a["id"]] = a
groups = {}


def joint_group(chain):
    # a later articulation rides on the earlier ones: the first is outermost
    parent = root
    for k in range(len(chain)):
        key = tuple(chain[:k + 1])
        if key not in groups:
            a = data["articulations"][chain[k]]
            gj = group("joint-" + a["id"], parent)
            gj.addProperty("App::PropertyString", "JointType", "Joint").JointType = a["type"]
            gj.addProperty("App::PropertyVector", "Axis", "Joint").Axis = V(*a["axis"])
            pivot = V(*a["pivot"]) if a["pivot"] else V(0, 0, 0)
            gj.addProperty("App::PropertyVector", "Pivot", "Joint").Pivot = pivot
            gj.addProperty("App::PropertyFloat", "Amount", "Joint").Amount = a["amount"]
            gj.addProperty("App::PropertyString", "Unit", "Joint").Unit = a["unit"]
            if a["unit"] == "deg":
                opened = FreeCAD.Placement(V(0, 0, 0), FreeCAD.Rotation(V(*a["axis"]), a["amount"]), pivot)
            else:
                opened = FreeCAD.Placement(V(*a["axis"]) * a["amount"], FreeCAD.Rotation())
            gj.addProperty("App::PropertyPlacement", "Open", "Joint",
                           "set Placement to this to open the joint").Open = opened
            groups[key] = gj
        parent = groups[key]
    return parent


made, invalid, surfaces, exact, faceted = 0, [], [], [], []
for p in data["parts"]:
    shapes, all_solid = [], True
    got = exact_part(p)
    if got:
        shapes, all_solid = [got[0]], got[1]
        exact.append(p["id"])
    else:
        if p.get("exact"):
            faceted.append(p["id"])
        for tris in p["solids"]:
            s, ok = shape_of(tris, True)
            shapes.append(s)
            all_solid &= ok
        for tris in p["shells"]:
            shapes.append(shape_of(tris, False)[0])
            all_solid = False
    if not shapes:
        continue
    o = doc.addObject("Part::Feature", name("p_", p["id"]))
    o.Shape = shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)
    o.Label = p["id"]
    o.Label2 = p["label"]
    for key, kind in (("role", "String"), ("certainty", "String"), ("source", "String"), ("stage", "Integer")):
        prop = key.capitalize()
        o.addProperty("App::Property" + kind, prop, "Construct")
        setattr(o, prop, p[key])
    o.addProperty("App::PropertyStringList", "Basis", "Construct").Basis = p["basis"]
    if p["chain"]:
        joint_group(p["chain"]).addObject(o)
    else:
        if p["stage"] not in stages:
            stages[p["stage"]] = group("stage-%d" % p["stage"], root)
        stages[p["stage"]].addObject(o)
    made += 1
    if not all_solid:
        surfaces.append(p["id"])
    if not o.Shape.isValid():
        invalid.append(p["id"])

for key, gj in groups.items():
    objs = [o for o in gj.Group if o.TypeId == "Part::Feature"]
    a = data["articulations"][key[-1]]
    if objs:
        bb = objs[0].Shape.BoundBox
        for o in objs[1:]:
            bb.add(o.Shape.BoundBox)
        half = max(bb.XLength, bb.YLength, bb.ZLength) * 0.6 or 10.0
        c = V(*a["pivot"]) if a["pivot"] else bb.Center
        line = doc.addObject("Part::Feature", name("axis_", a["id"]))
        line.Shape = Part.makeLine(c - V(*a["axis"]) * half, c + V(*a["axis"]) * half)
        line.Label = "axis-" + a["id"]
        gj.addObject(line)

doc.recompute()
if FreeCAD.GuiUp:   # run as the app (off screen): save how it looks, so the model shows when opened
    for o in doc.Objects:
        if getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = True

result = {"parts": made, "joints": len(groups), "invalid": invalid, "surfaces": surfaces, "files": [],
          "exact": exact, "faceted": faceted, "why": why}
boxes = [o.Shape.BoundBox for o in doc.Objects if o.TypeId == "Part::Feature" and not o.Shape.isNull()]
if boxes:
    bb = boxes[0]
    for b in boxes[1:]:
        bb.add(b)
    result["box"] = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
if job.get("fcstd"):
    doc.saveAs(job["fcstd"])
    result["files"].append(job["fcstd"])
if job.get("step"):
    Import.export([root], job["step"])
    result["files"].append(job["step"])
json.dump(result, open(job["result"], "w", encoding="utf-8"))
if FreeCAD.GuiUp:
    os._exit(0)   # the app has done its job: leave without asking about the open document
'''


def _app(exe):
    """FreeCAD's own app beside its command line, if there is one: run off screen, it saves how the model looks
    (the command line saves the model only, and FreeCAD then opens it with every part hidden)."""
    exe = Path(exe)
    for cand in (exe.parent.parent.parent / "MacOS" / "FreeCAD", exe.parent / "freecad", exe.parent / "FreeCAD.exe"):
        if cand.is_file() and cand != exe:
            return str(cand)
    return None


# what FreeCAD is given of this process's environment: what a program needs to start, find its libraries and keep its
# files on Windows, macOS and Linux, and FreeCAD's own settings; never the rest (API keys among it)
_FREECAD_ENV = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE",
                "LD_LIBRARY_PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR",
                "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
                "PROGRAMFILES", "USERPROFILE", "USERNAME", "HOMEDRIVE", "HOMEPATH", "NUMBER_OF_PROCESSORS",
                "PROCESSOR_ARCHITECTURE", "FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP")


def _freecad_env(app):
    """The environment FreeCAD runs in: the names above as they are here, and off screen for its app."""
    env = {k: os.environ.get(k) for k in _FREECAD_ENV if os.environ.get(k) is not None}
    if app:
        env["QT_QPA_PLATFORM"] = "offscreen"
    return env


# what FreeCAD's app says off screen whether or not anything is wrong
_QT_NOISE = ("does not support grabbing", "does not support propagateSizeHints", "QOpenGLWidget is not supported",
             "imageFromFramebuffer failed", "Running: ")


def _stopped(r):
    """Why FreeCAD stopped before writing the model: how it ended and the last lines it said, without its
    launcher's copy of the environment or the Qt notices it always prints off screen."""
    how = "it was killed (signal %d)" % -r.returncode if r.returncode < 0 else "exit code %d" % r.returncode
    said = [s for s in (r.stdout + "\n" + r.stderr).splitlines() if s.strip()
            and not re.match(r"[A-Za-z_][A-Za-z0-9_]*=", s) and not any(n in s for n in _QT_NOISE)]
    hint = "" if said else "; it said nothing: if the machine was busy, try again"
    return "FreeCAD stopped before writing the model (%s%s)" % (how, hint) + "".join("\n" + s for s in said[-8:])


def make(scene, fcstd=None, step=None, freecad=None, timeout=900, exact=True):
    """Build the construct in FreeCAD and write the .FCStd and/or STEP. Returns a summary:
    {"parts", "joints", "invalid", "surfaces", "left_out", "files", "exact", "faceted"}: `exact` the parts made
    as true shapes, `faceted` those that could have been but did not match and were faceted."""
    if not fcstd and not step:
        raise FreeCADError("nothing to write: give an .FCStd or a STEP path")
    exe = find_freecad(freecad)
    if not exe:
        raise FreeCADError("FreeCAD not found: install FreeCAD 1.0 or newer, or set CONSTRUCT_FREECAD to its "
                           "freecadcmd")
    data = payload(scene, exact)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "payload.json").write_text(json.dumps(data), encoding="utf-8")
        (tmp / "build.py").write_text("JOB = %s\n" % json.dumps(str(tmp / "job.json")) + SCRIPT, encoding="utf-8")
        job = {"payload": str(tmp / "payload.json"), "result": str(tmp / "result.json"),
               "fcstd": str(Path(fcstd).resolve()) if fcstd else None,
               "step": str(Path(step).resolve()) if step else None}
        for p in (fcstd, step):
            if p:
                Path(p).resolve().parent.mkdir(parents=True, exist_ok=True)
        (tmp / "job.json").write_text(json.dumps(job), encoding="utf-8")
        app = _app(exe)
        try:
            r = subprocess.run([app or exe, str(tmp / "build.py")], cwd=tmp, env=_freecad_env(app), capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise FreeCADError("FreeCAD did not finish in %d s" % timeout)
        if not (tmp / "result.json").is_file():
            raise FreeCADError(_stopped(r))
        out = json.loads((tmp / "result.json").read_text(encoding="utf-8"))
    if fcstd and app and out.get("box"):
        _frame(Path(fcstd), out["box"])
    out["left_out"] = data["left_out"]
    return out


# FreeCAD's isometric view: from the (+x, -y, +z) corner, Z up
ISO_AXIS, ISO_ANGLE, ISO_DIR = (0.7447, 0.3085, 0.5959), 1.2133, (-0.5774, 0.5774, -0.5774)


def _frame(path, box):
    """Open the document framed: an isometric camera that fits the model, in its display layer (the app off
    screen cannot fit the view itself)."""
    import zipfile
    centre = [(box[k] + box[k + 3]) / 2 for k in range(3)]
    size = max(1.0, sum((box[k + 3] - box[k]) ** 2 for k in range(3)) ** 0.5)
    pos = [centre[k] - ISO_DIR[k] * size * 1.5 for k in range(3)]
    camera = ("OrthographicCamera {\n  viewportMapping ADJUST_CAMERA\n  position %g %g %g\n"
              "  orientation %g %g %g  %g\n  nearDistance %g\n  farDistance %g\n  aspectRatio 1\n  focalDistance %g\n"
              "  height %g\n\n}\n" % (*pos, *ISO_AXIS, ISO_ANGLE, size * 0.5, size * 2.5, size * 1.5, size * 0.8))
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    out = []
    for info, data in items:
        if info.filename == "GuiDocument.xml":
            text = data.decode("utf-8")
            start = text.find("<Camera settings=")
            if start >= 0:
                end = text.index("/>", start) + 2
                text = text[:start] + '<Camera settings="%s"/>' % camera.replace("\n", "&#10;") + text[end:]
            data = text.encode("utf-8")
        out.append((info, data))
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in out:
            z.writestr(info, data)
    tmp.replace(path)
