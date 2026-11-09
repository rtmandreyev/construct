"""Read an exported file back, as a check that it holds what Construct said it wrote (construct_export's summary).

Standard library only, each reader bounded: glTF binary (nodes, meshes, animations, bounds through the node tree),
OBJ, STL (binary or text), 3MF (its model XML), STEP (products, solids, faces by surface kind, bounds from its
vertices, approximate) and FreeCAD documents (their objects). Each returns a small dict; a file that cannot be read says why.
"""

import json
import math
import re
import struct
import zipfile
from pathlib import Path

READ_MAX = 512 * 1024 * 1024
NAMES_MAX = 60


def human(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def _bounds(lo, hi, unit):
    """{"x", "y", "z"} extents in the file's unit, and the same in metres and millimetres."""
    if lo is None or any(math.isinf(v) for v in lo + hi):
        return None
    to_m = {"m": 1.0, "mm": 0.001, "cm": 0.01, "in": 0.0254}[unit]
    ext = [hi[a] - lo[a] for a in range(3)]
    return {"m": [round(e * to_m, 4) for e in ext], "mm": [round(e * to_m * 1000, 1) for e in ext],
            "min": [round(v, 5) for v in lo], "max": [round(v, 5) for v in hi], "unit": unit}


# ---------------------------------------------------------------------------- glTF binary

def _mat_mul(a, b):
    return [sum(a[r + 4 * k] * b[k + 4 * c] for k in range(4)) for c in range(4) for r in range(4)]   # column-major


def _node_matrix(node):
    if isinstance(node.get("matrix"), list) and len(node["matrix"]) == 16:
        return [float(x) for x in node["matrix"]]
    tx, ty, tz = (node.get("translation") or [0, 0, 0])[:3]
    qx, qy, qz, qw = (node.get("rotation") or [0, 0, 0, 1])[:4]
    sx, sy, sz = (node.get("scale") or [1, 1, 1])[:3]
    r = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy + qz * qw), 2 * (qx * qz - qy * qw),
         2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz + qx * qw),
         2 * (qx * qz + qy * qw), 2 * (qy * qz - qx * qw), 1 - 2 * (qx * qx + qy * qy)]
    return [r[0] * sx, r[1] * sx, r[2] * sx, 0, r[3] * sy, r[4] * sy, r[5] * sy, 0, r[6] * sz, r[7] * sz, r[8] * sz, 0,
            tx, ty, tz, 1]


def _apply(m, p):
    return [m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
            m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]]


def glb(path):
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        return {"error": "not a binary glTF (no glTF header)"}
    version, total = struct.unpack_from("<II", data, 4)
    clen, ctype = struct.unpack_from("<II", data, 12)
    if ctype != 0x4E4F534A:
        return {"error": "the first chunk is not JSON"}
    doc = json.loads(data[20:20 + clen].decode("utf-8"))
    nodes, meshes, accessors = doc.get("nodes", []), doc.get("meshes", []), doc.get("accessors", [])
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    triangles = 0

    def visit(i, parent, depth=0):
        nonlocal triangles
        if depth > 64 or not 0 <= i < len(nodes):
            return
        node = nodes[i]
        m = _mat_mul(parent, _node_matrix(node))
        if isinstance(node.get("mesh"), int) and 0 <= node["mesh"] < len(meshes):
            for prim in meshes[node["mesh"]].get("primitives", []):
                acc = accessors[prim["attributes"]["POSITION"]] if "POSITION" in prim.get("attributes", {}) else None
                if acc and acc.get("min") and acc.get("max"):
                    a, b = acc["min"], acc["max"]
                    for corner in ([x, y, z] for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])):
                        p = _apply(m, corner)
                        for k in range(3):
                            lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
                if prim.get("mode", 4) == 4:
                    idx = accessors[prim["indices"]]["count"] if isinstance(prim.get("indices"), int) else (acc or {}).get("count", 0)
                    triangles += idx // 3
        for c in node.get("children", []):
            visit(c, m, depth + 1)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    scene = (doc.get("scenes") or [{}])[doc.get("scene", 0) if isinstance(doc.get("scene"), int) else 0]
    for root in scene.get("nodes", []):
        visit(root, ident)
    anims = []
    for a in doc.get("animations", []):
        seconds = 0.0
        for ch in a.get("channels", []):
            smp = a["samplers"][ch["sampler"]]
            inp = accessors[smp["input"]]
            seconds = max(seconds, float((inp.get("max") or [0])[0]))
        anims.append({"name": a.get("name", ""), "channels": len(a.get("channels", [])), "seconds": round(seconds, 2)})
    named = [n.get("name") for n in nodes if n.get("name") and isinstance(n.get("mesh"), int)]
    return {"gltf_version": doc.get("asset", {}).get("version"), "nodes": len(nodes), "meshes": len(meshes),
            "named_parts": len(set(named)), "part_names": sorted(set(named))[:NAMES_MAX],
            "materials": len(doc.get("materials", [])), "triangles": triangles, "animations": anims,
            "physics": bool((doc.get("extensionsUsed") or []) and any("physics" in e.lower() for e in doc["extensionsUsed"])),
            "bounds": _bounds(lo if triangles or lo[0] != math.inf else None, hi, "m"), "bytes_declared": total}


# ---------------------------------------------------------------------------- OBJ

def obj(path):
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    names, verts, faces = [], 0, 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                xs = line.split()
                try:
                    p = [float(xs[1]), float(xs[2]), float(xs[3])]
                except (IndexError, ValueError):
                    continue
                verts += 1
                for k in range(3):
                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
            elif line.startswith("f "):
                faces += 1
            elif line.startswith(("o ", "g ")):
                names.append(line[2:].strip())
    return {"objects": len(set(names)), "part_names": sorted(set(names))[:NAMES_MAX], "vertices": verts, "faces": faces,
            "bounds": _bounds(lo if verts else None, hi, "m")}


# ---------------------------------------------------------------------------- STL

def stl(path):
    data = Path(path).read_bytes()
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    if len(data) >= 84 and len(data) == 84 + 50 * struct.unpack_from("<I", data, 80)[0]:
        n = struct.unpack_from("<I", data, 80)[0]
        for t in struct.iter_unpack("<12fH", data[84:84 + 50 * n]):
            for v in (t[3:6], t[6:9], t[9:12]):
                for k in range(3):
                    if v[k] < lo[k]:
                        lo[k] = v[k]
                    if v[k] > hi[k]:
                        hi[k] = v[k]
        kind = "binary"
    else:
        text = data.decode("utf-8", errors="replace")
        n = 0
        for m in re.finditer(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text):
            v = [float(x) for x in m.groups()]
            for k in range(3):
                lo[k], hi[k] = min(lo[k], v[k]), max(hi[k], v[k])
            n += 1
        n //= 3
        kind = "text"
    return {"stl": kind, "triangles": n, "bounds": _bounds(lo if n else None, hi, "mm")}


# ---------------------------------------------------------------------------- 3MF

UNITS_3MF = {"millimeter": "mm", "centimeter": "cm", "meter": "m", "inch": "in"}


def threemf(path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".model")), None)
        if not name:
            return {"error": "no 3D model inside"}
        if z.getinfo(name).file_size > READ_MAX:
            return {"error": "the model is too large to read back"}
        objects, items, unit = {}, [], "mm"
        cur = None
        with z.open(name) as fh:
            for event, el in ET.iterparse(fh, events=("start", "end")):
                tag = el.tag.rsplit("}", 1)[-1]
                if event == "start" and tag == "model":
                    unit = UNITS_3MF.get(el.get("unit", "millimeter"), "mm")
                elif event == "start" and tag == "object":
                    cur = {"name": el.get("name") or "", "lo": [math.inf] * 3, "hi": [-math.inf] * 3, "v": 0, "t": 0}
                    objects[el.get("id")] = cur
                elif event == "end" and tag == "vertex" and cur is not None:
                    p = [float(el.get(a, 0)) for a in "xyz"]
                    for k in range(3):
                        cur["lo"][k], cur["hi"][k] = min(cur["lo"][k], p[k]), max(cur["hi"][k], p[k])
                    cur["v"] += 1
                    el.clear()
                elif event == "end" and tag == "triangle" and cur is not None:
                    cur["t"] += 1
                    el.clear()
                elif event == "end" and tag == "item":
                    items.append((el.get("objectid"), el.get("transform")))
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for oid, tf in items or [(k, None) for k in objects]:
        o = objects.get(oid)
        if not o or not o["v"]:
            continue
        m = [float(x) for x in tf.split()] if tf else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        for c in ([x, y, z] for x in (o["lo"][0], o["hi"][0]) for y in (o["lo"][1], o["hi"][1]) for z in (o["lo"][2], o["hi"][2])):
            p = [c[0] * m[0] + c[1] * m[3] + c[2] * m[6] + m[9], c[0] * m[1] + c[1] * m[4] + c[2] * m[7] + m[10],
                 c[0] * m[2] + c[1] * m[5] + c[2] * m[8] + m[11]]
            for k in range(3):
                lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
    named = [o["name"] for o in objects.values() if o["name"]]
    return {"objects": len(objects), "build_items": len(items), "part_names": named[:NAMES_MAX],
            "triangles": sum(o["t"] for o in objects.values()), "vertices": sum(o["v"] for o in objects.values()),
            "bounds": _bounds(lo if lo[0] != math.inf else None, hi, unit)}


# ---------------------------------------------------------------------------- STEP

SURFACES = {"PLANE": "plane", "CYLINDRICAL_SURFACE": "cylinder", "CONICAL_SURFACE": "cone",
            "SPHERICAL_SURFACE": "sphere", "TOROIDAL_SURFACE": "torus", "SURFACE_OF_REVOLUTION": "revolved",
            "SURFACE_OF_LINEAR_EXTRUSION": "extruded", "B_SPLINE_SURFACE": "spline",
            "B_SPLINE_SURFACE_WITH_KNOTS": "spline", "RATIONAL_B_SPLINE_SURFACE": "spline"}


def step(path):
    size = Path(path).stat().st_size
    if size > READ_MAX:
        return {"error": "too large to read back"}
    text = Path(path).read_text(encoding="latin-1")
    if "ISO-10303-21" not in text[:200]:
        return {"error": "not a STEP file (no ISO-10303-21 header)"}
    ents = {}
    for m in re.finditer(r"#(\d+)\s*=\s*([A-Z_0-9]+)\s*\(", text):
        ents[m.group(2)] = ents.get(m.group(2), 0) + 1
    products = re.findall(r"=\s*PRODUCT\s*\(\s*'((?:[^']|'')*)'", text)
    surfaces = {}
    for k, v in SURFACES.items():
        if ents.get(k):
            surfaces[v] = surfaces.get(v, 0) + ents[k]
    points = {m.group(1): m.group(2) for m in re.finditer(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)", text)}
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    seen = 0
    for ref in re.findall(r"VERTEX_POINT\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*\)", text):
        xyz = points.get(ref)
        if not xyz:
            continue
        try:
            p = [float(x) for x in xyz.split(",")[:3]]
        except ValueError:
            continue
        if len(p) == 3:
            seen += 1
            for k in range(3):
                lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
    unit = "mm" if re.search(r"SI_UNIT\s*\(\s*\.MILLI\.\s*,\s*\.METRE\.\s*\)", text) else \
        ("m" if re.search(r"SI_UNIT\s*\(\s*\$\s*,\s*\.METRE\.\s*\)", text) else "mm")
    curved = sum(v for k, v in surfaces.items() if k != "plane")
    bounds = _bounds(lo if seen else None, hi, unit)
    if bounds:   # a curved face (a cylinder's side, a fender) reaches past the vertices on its edges
        bounds["approximate"] = "from the vertices only: curved parts can reach further"
    return {"schema": (re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text) or [None, None])[1],
            "products": len(products), "part_names": [p.replace("''", "'") for p in products][:NAMES_MAX],
            "solids": ents.get("MANIFOLD_SOLID_BREP", 0) + ents.get("BREP_WITH_VOIDS", 0),
            "faceted_solids": ents.get("FACETED_BREP", 0), "shells": ents.get("SHELL_BASED_SURFACE_MODEL", 0),
            "faces": ents.get("ADVANCED_FACE", 0) + ents.get("FACE_SURFACE", 0), "surfaces": surfaces,
            "curved_faces": curved, "bounds": bounds}


# ---------------------------------------------------------------------------- FreeCAD

def fcstd(path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        if "Document.xml" not in z.namelist():
            return {"error": "no Document.xml inside"}
        if z.getinfo("Document.xml").file_size > READ_MAX:
            return {"error": "too large to read back"}
        root = ET.fromstring(z.read("Document.xml"))
        breps = sum(1 for n in z.namelist() if n.lower().endswith((".brp", ".brep")))
    kinds, labels = {}, []
    objs = root.find("Objects")
    for o in (objs if objs is not None else []):
        kinds[o.get("type")] = kinds.get(o.get("type"), 0) + 1
    data = root.find("ObjectData")
    for o in (data if data is not None else []):
        for prop in o.iter("Property"):
            if prop.get("name") == "Label":
                s = prop.find("String")
                if s is not None and o.get("name", "").startswith("p_"):
                    labels.append(s.get("value"))
    return {"objects": sum(kinds.values()), "solids": kinds.get("Part::Feature", 0), "groups": kinds.get("App::Part", 0) + kinds.get("App::DocumentObjectGroup", 0),
            "part_names": labels[:NAMES_MAX], "shape_files": breps}


READERS = {".glb": glb, ".obj": obj, ".stl": stl, ".3mf": threemf, ".step": step, ".stp": step, ".fcstd": fcstd}


def read(path):
    """What the file holds, read from the file itself: {"file", "bytes", "size", ...the format's counts}."""
    path = Path(path)
    out = {"file": path.name, "bytes": path.stat().st_size, "size": human(path.stat().st_size)}
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        return out
    try:
        out.update(reader(path))
    except Exception as exc:   # a file that does not read back is reported, never raised: that is the finding
        out["error"] = "could not read it back: %s: %s" % (type(exc).__name__, exc)
    return out


def construct_report(text):
    """The counts Construct printed while writing (export/print/freecad), for the summary beside the read-back."""
    out = {}
    m = re.search(r"wrote .*?: (\d+) parts, (\d+) triangles, (\d+) edges(?:; animations: (.*))?", text)
    if m:
        out.update(parts=int(m.group(1)), triangles=int(m.group(2)), edges=int(m.group(3)))
        if m.group(4):
            out["animations"] = [a.strip() for a in m.group(4).split(",") if a.strip() and a.strip() != "none"]
    m = re.search(r"wrote .*?: (\d+) named parts, (\d+) joints?", text)
    if m:
        out.update(parts=int(m.group(1)), joints=int(m.group(2)))
    m = re.search(r"true shapes \(exact solids, splines, NURBS\): (\d+) of (\d+) parts", text)
    if m:
        out.update(exact=int(m.group(1)), faceted=int(m.group(2)) - int(m.group(1)))
    elif "named parts" in text:
        out.update(exact=0, faceted=out.get("parts", 0))
    for key, label in (("not_matching", "faceted, the true shape did not match the construct"),
                       ("surfaces", "surfaces, not solids"), ("left_out", "drawn only in lines, left out"),
                       ("invalid", "FreeCAD found these shapes invalid")):
        m = re.search(re.escape(label) + r"[^:]*: (.+)", text)
        if m:
            out[key] = m.group(1).strip()[:400]
    return out
