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

The solids are faceted, as the construct draws them: exact for boxes and prisms, a polygon for a
cylinder. Python standard library only on this side; FreeCAD 1.0 or newer on the other.
"""

import glob
import json
import os
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


def payload(scene):
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
                          "solids": solids, "shells": shells})
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


# Runs inside FreeCAD: reads the job named by $CONSTRUCT_FREECAD_JOB, writes its result beside it.
SCRIPT = r'''
import json, os, re
import FreeCAD, Part, Mesh, Import

job = json.load(open(os.environ["CONSTRUCT_FREECAD_JOB"], encoding="utf-8"))
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


made, invalid, surfaces = 0, [], []
for p in data["parts"]:
    shapes, all_solid = [], True
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

result = {"parts": made, "joints": len(groups), "invalid": invalid, "surfaces": surfaces, "files": []}
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


def make(scene, fcstd=None, step=None, freecad=None, timeout=900):
    """Build the construct in FreeCAD and write the .FCStd and/or STEP. Returns a summary:
    {"parts", "joints", "invalid", "surfaces", "left_out", "files"}."""
    if not fcstd and not step:
        raise FreeCADError("nothing to write: give an .FCStd or a STEP path")
    exe = find_freecad(freecad)
    if not exe:
        raise FreeCADError("FreeCAD not found: install FreeCAD 1.0 or newer, or set CONSTRUCT_FREECAD to its "
                           "freecadcmd")
    data = payload(scene)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "payload.json").write_text(json.dumps(data), encoding="utf-8")
        (tmp / "build.py").write_text(SCRIPT, encoding="utf-8")
        job = {"payload": str(tmp / "payload.json"), "result": str(tmp / "result.json"),
               "fcstd": str(Path(fcstd).resolve()) if fcstd else None,
               "step": str(Path(step).resolve()) if step else None}
        for p in (fcstd, step):
            if p:
                Path(p).resolve().parent.mkdir(parents=True, exist_ok=True)
        (tmp / "job.json").write_text(json.dumps(job), encoding="utf-8")
        env = dict(os.environ, CONSTRUCT_FREECAD_JOB=str(tmp / "job.json"))
        app = _app(exe)
        if app:
            env["QT_QPA_PLATFORM"] = "offscreen"
        try:
            r = subprocess.run([app or exe, str(tmp / "build.py")], cwd=tmp, env=env, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            raise FreeCADError("FreeCAD did not finish in %d s" % timeout)
        if not (tmp / "result.json").is_file():
            tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
            raise FreeCADError("FreeCAD stopped before writing the model:\n" + tail)
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
