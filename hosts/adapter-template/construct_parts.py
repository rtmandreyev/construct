"""A Construct adapter, as small as one can be: a construct to a parts sheet and one STL per part.

    python3 construct_parts.py scene.json OUT/

Writes OUT/parts.csv (each part's name, role, build stage, size in millimetres, how its size and its shape
are known, and its source) and OUT/<part>.stl (its solid, in millimetres, Z up). Copy it and change what it
writes: everything an adapter needs is in the compiled geometry (docs/ADAPTERS.md).

Apache-2.0, like Construct. Python 3.10+, standard library only; Construct itself on the path.
"""
import csv
import sys
from pathlib import Path

from construct_hologram import scene, studio


def parts(scene_path):
    """The construct's parts, each with its triangles in metres (Z up): [{"part": {...}, "triangles": [...]}]."""
    g = scene.compile_scene(studio.load(scene_path), solid=True)   # solid: every surface, as the exporters use
    g = scene.reframe(g, "z-up")                                   # the contract is Y up, front +Z; STL is Z up
    part_of = g["style_fields"].index("part")
    stride, f = g["fill_stride"], g["fills"]
    out = [{"part": p, "triangles": []} for p in g["parts"]]
    for i in range(0, len(f), 3 * stride):                         # a triangle is three vertices: x y z style phase
        corners = [tuple(f[i + k * stride: i + k * stride + 3]) for k in range(3)]
        out[int(g["styles"][int(f[i + 3])][part_of])]["triangles"].append(corners)
    return g, out


def size_mm(part):
    """The part's overall size, all its copies together, in millimetres: width, depth, height (Z up)."""
    lo = [min(c["min"][k] for c in part["instances"]) for k in range(3)]
    hi = [max(c["max"][k] for c in part["instances"]) for k in range(3)]
    return [round((b - a) * 1000, 1) for a, b in zip(lo, hi)]


def write_stl(path, name, triangles):
    with open(path, "w", encoding="ascii") as fh:
        fh.write("solid %s\n" % name)
        for tri in triangles:
            fh.write("facet normal 0 0 0\n outer loop\n")   # readers compute the normal from the winding
            for x, y, z in tri:
                fh.write("  vertex %.4f %.4f %.4f\n" % (x * 1000, y * 1000, z * 1000))
            fh.write(" endloop\nendfacet\n")
        fh.write("endsolid %s\n" % name)


def main(scene_path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    g, made = parts(scene_path)
    with open(out / "parts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "label", "role", "stage", "width_mm", "depth_mm", "height_mm", "size_known", "shape_known",
                    "source", "stl"])
        for m in made:
            p = m["part"]
            axes = p.get("certainty_axes") or {"size": p["certainty"], "shape": p["certainty"]}
            stl = ""
            if m["triangles"]:   # a part drawn only in lines has no solid
                stl = p["id"] + ".stl"
                write_stl(out / stl, p["id"], m["triangles"])
            w.writerow([p["id"], p["label"], p["role"], p["stage"], *size_mm(p), axes["size"], axes["shape"],
                        p["source"], stl])
    print("wrote %s: %d parts, %d with a solid" % (out, len(made), sum(1 for m in made if m["triangles"])))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[2].strip())
    main(sys.argv[1], sys.argv[2])
