
"""A NetLogo run as a film in Blender: every recorded turtle, tick by tick, as light that moves.

A construct of a run holds the run's shape (sampled to about 18,000 line segments); this draws the recording
itself, every turtle at every tick, so a long run with many agents loses nothing. Each turtle is a
small glowing arrowhead in its own NetLogo colour, pointing where it goes, with a trail that fades
behind it; a link is a thin line of light between its two agents while the recording has it; the
patches are a floor of cells in the patch reporter's colours, tick by tick; the world's edge is a line
of light. The film plays the run at 30 ticks a second.

Nothing is invented: positions, colours, births and deaths are the recording's; between two ticks
a turtle is placed on the straight line between its recorded places (never across a wrap of the
world). The frame handler moves the agents as the scene plays or renders; the objects carry the
recording's path, so a saved .blend replays it wherever the add-on is installed.

    from construct_hologram import runfilm
    runfilm.build("flocking-run.jsonl")          # in Blender: File > Import > NetLogo Run (.jsonl)

It runs inside Blender (bpy and the NumPy Blender bundles); outside, importing it does nothing, so the
rest of Construct stays standard library only. `construct netlogo-film` runs it in Blender for you.
"""

import json
import math
import os

try:   # only inside Blender
    import bpy
    import numpy as np
except ImportError:
    bpy = np = None

WORLD = 10.0          # metres across the world's longer side, as a construct of a run draws it
TPS = 30.0            # the film's clock: ticks a second
TRAIL_S = 0.35        # seconds of trail behind each turtle
TRAIL_POINTS = 12     # points along each trail
ARROW = 0.11          # an arrowhead's length, metres
ACCENT = (0.82, 0.42, 0.82)
PATCH_CELLS = 128     # the patches' floor: at most this many cells along a side (a block of patches each)
# NetLogo's colours: a number 0..140, ten to a hue, 0 black to 9.9 white (as Construct's bridge reads them)
NL_BASE = [(141, 141, 141), (215, 50, 41), (241, 105, 19), (156, 109, 70), (237, 237, 47), (87, 176, 58),
           (42, 209, 57), (27, 158, 119), (82, 196, 196), (43, 140, 190), (52, 93, 169), (124, 80, 164),
           (167, 27, 106), (224, 127, 150)]
_CACHE = {}


def netlogo_rgb(c):
    """A NetLogo colour (a number, or an RGB(A) list) as linear RGB 0..1."""
    if isinstance(c, list) and len(c) >= 3:
        rgb = [max(0, min(255, v)) / 255 for v in c[:3]]
    else:
        c = float(c) % 140
        base = NL_BASE[int(c // 10)]
        shade = c % 10 - 5
        rgb = [(b + (255 - b) * shade / 5 if shade > 0 else b * (1 + shade / 5)) / 255 for b in base]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]


# ---------------------------------------------------------------------------- the recording

def _no_constant(name):   # this file runs inside Blender too: nothing of Construct's is imported here
    raise ValueError("%s is not a number a run can hold" % name)


def parse(path):
    """(header, frames, end, patch rows) of a recording, in plain Python (no NumPy: it runs outside Blender too, to
    refuse a bad recording before Blender starts)."""
    header, frames, end, patch_rows = None, [], None, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line, parse_constant=_no_constant)
            except ValueError as exc:
                raise ValueError("%s: not a recording line (%s)" % (path, exc))
            if not isinstance(row, dict):
                raise ValueError("%s: a recording line is an object, one tick or the header" % path)
            if header is None and "construct-netlogo" in row:
                header = row
            elif "t" in row and "turtles" in row:
                frames.append(row)
            if "t" in row and "patches" in row:
                patch_rows.append((row["t"], row["patches"]))
            elif "end" in row:
                end = row["end"]
    if header is None or not frames:
        raise ValueError("%s is not a Construct recording with turtles (construct:run or construct.nls)" % os.path.basename(path))
    return header, frames, end, patch_rows


def read(path):
    """The recording as arrays: positions [ticks, agents, 2] in metres, alive [ticks, agents], each agent's
    colour per tick, the ticks and the world's size."""
    path = os.path.abspath(path)
    key = (path, os.path.getmtime(path))
    if key in _CACHE:
        return _CACHE[key]
    header, frames, end, patch_rows = parse(path)
    w = header["world"]
    x0, x1, y0, y1 = w["min-pxcor"] - 0.5, w["max-pxcor"] + 0.5, w["min-pycor"] - 0.5, w["max-pycor"] + 0.5
    scale = WORLD / max(x1 - x0, y1 - y0)
    ids = sorted({row[0] for f in frames for row in f["turtles"]})
    col = {who: i for i, who in enumerate(ids)}
    T, N = len(frames), len(ids)
    pos = np.zeros((T, N, 3), dtype=np.float32)
    alive = np.zeros((T, N), dtype=bool)
    colour = np.zeros((T, N, 3), dtype=np.float32)
    has_z = False
    vars_ = header.get("turtle-vars", [])
    hid = 5 + vars_.index("hidden?") if "hidden?" in vars_ else None   # recorded when a model hides turtles
    for t, f in enumerate(frames):
        for row in f["turtles"]:
            i = col[row[0]]
            pos[t, i, 0] = (row[2] - (x0 + x1) / 2) * scale
            pos[t, i, 1] = (row[3] - (y0 + y1) / 2) * scale
            alive[t, i] = True
            colour[t, i] = netlogo_rgb(row[4])
            if hid is not None and len(row) > hid and row[hid] is True:   # hidden in NetLogo: unlit here, barely there
                colour[t, i] *= 0.12
            if header.get("zcor"):   # a NetLogo 3D run: the height last in each row, the floor at the world's bottom
                has_z = True
                pos[t, i, 2] = (row[-1] - w.get("min-pzcor", 0) + 0.5) * scale
    # where an agent is not alive (before its birth, after its death), it keeps its nearest known place, so nothing
    # is drawn where it never was; a change of alive is never interpolated (see _at)
    last_alive = np.where(alive, np.arange(T)[:, None], -1)
    np.maximum.accumulate(last_alive, axis=0, out=last_alive)
    first_alive = alive.argmax(axis=0)
    src = np.where(last_alive < 0, first_alive[None, :], last_alive)
    cols = np.arange(N)[None, :]
    pos, colour = pos[src, cols], colour[src, cols]
    links, link_on = _links(frames, col)
    data = {"header": header, "ticks": np.array([f["t"] for f in frames], dtype=np.float64), "pos": pos, "alive": alive,
            "links": links, "link_on": link_on, "patches": _patches(header, patch_rows, scale),
            "colour": colour, "end": end, "size": ((x1 - x0) * scale, (y1 - y0) * scale), "jump": 0.5 * WORLD,
            "depth": (w.get("max-pzcor", 0) - w.get("min-pzcor", 0) + 1) * scale if header.get("zcor") else 0.0,
            "has_z": has_z, "path": path}
    for old in list(_CACHE)[:-3]:   # a few runs at once, each read once
        del _CACHE[old]
    _CACHE[key] = data
    return data


def _links(frames, col):
    """The links: every pair of agents ever linked [L, 2] (their columns), and which are linked at each record
    [T, L]. A recording writes the links when their number changes, so each set holds until the next."""
    pairs, now, rows = {}, set(), []
    for f in frames:
        if "links" in f:
            now = set()
            for a, b, *_ in f["links"]:
                if a in col and b in col:
                    key = (col[a], col[b])
                    now.add(pairs.setdefault(key, len(pairs)))
        rows.append(sorted(now))
    on = np.zeros((len(frames), len(pairs)), dtype=bool)
    for t, idx in enumerate(rows):
        on[t, idx] = True
    return np.array(sorted(pairs, key=pairs.get), dtype=np.int64).reshape(-1, 2), on


def _patches(header, patch_rows, scale):
    """The patches as a floor of cells: each cell a block of patches (at most PATCH_CELLS a side), coloured by the
    patch reporter at each record: NetLogo's colours for a colour, else from dark to the accent over the run's
    range. None without a patch reporter recorded."""
    if not patch_rows or not header.get("patch-reporter"):
        return None
    w = header["world"]
    cols, rows = w["max-pxcor"] - w["min-pxcor"] + 1, w["max-pycor"] - w["min-pycor"] + 1
    step = max(1, math.ceil(max(cols, rows) / PATCH_CELLS))
    keep = [r * cols + c for r in range(0, rows, step) for c in range(0, cols, step)]   # rows from the top (sort patches)
    vals = np.array([[v[i] if i < len(v) and isinstance(v[i], (int, float)) and not isinstance(v[i], bool) else 0.0
                      for i in keep] for _, v in patch_rows], dtype=np.float32)
    if "color" in header["patch-reporter"]:
        col = np.array([[netlogo_rgb(float(x)) for x in row] for row in vals], dtype=np.float32)
    else:
        lo, hi = float(vals.min()), float(vals.max())
        f = (vals - lo) / ((hi - lo) or 1.0)
        col = (0.04 + f[..., None] * (np.array(ACCENT, np.float32) - 0.04)).astype(np.float32)
    nc, nr = len(range(0, cols, step)), len(range(0, rows, step))
    cell = step * scale
    x0 = -(cols * scale) / 2
    y1 = (rows * scale) / 2
    return {"ticks": np.array([t for t, _ in patch_rows], dtype=np.float64), "colour": col, "cols": nc, "rows": nr,
            "cell": cell, "x0": x0, "y1": y1}


def seconds_of(data):
    """How long the film is: the run at TPS ticks a second."""
    return (data["ticks"][-1] - data["ticks"][0]) / TPS


# ---------------------------------------------------------------------------- where everything is at a moment

def _at(data, tick):
    """Positions and aliveness at a fractional tick: between two records, the straight line, except across
    a wrap of the world, where the turtle jumps."""
    ticks = data["ticks"]
    k = int(np.clip(np.searchsorted(ticks, tick, side="right") - 1, 0, len(ticks) - 1))
    k2 = min(k + 1, len(ticks) - 1)
    span = ticks[k2] - ticks[k]
    u = 0.0 if span <= 0 else float(np.clip((tick - ticks[k]) / span, 0, 1))
    a, b = data["pos"][k], data["pos"][k2]
    far = (np.linalg.norm(b - a, axis=1) > data["jump"]) | (data["alive"][k] != data["alive"][k2])   # a wrap, a birth, a death
    p = a + (b - a) * u
    p[far] = (a if u < 0.5 else b)[far]
    return p, data["alive"][k] & (data["alive"][k2] | (u < 0.5)), k


def state(data, tick, trail_ticks):
    """Everything the objects show at a tick: each agent's place, heading, colour and whether it lives,
    and its trail (TRAIL_POINTS places back in time, cut where it wrapped)."""
    p, alive, k = _at(data, tick)
    q, _, _ = _at(data, tick + 1)
    d = q - p
    d[np.linalg.norm(d, axis=1) > data["jump"]] = 0
    trail = np.empty((TRAIL_POINTS, p.shape[0], 3), dtype=np.float32)
    trail[0] = p
    stopped = np.zeros(p.shape[0], dtype=bool)   # once a trail meets a wrap or the agent's birth, it stays there
    for j in range(1, TRAIL_POINTS):
        trail[j], was, _ = _at(data, max(data["ticks"][0], tick - trail_ticks * j / (TRAIL_POINTS - 1)))
        stopped |= (np.linalg.norm(trail[j] - trail[j - 1], axis=1) > data["jump"]) | ~was
        trail[j][stopped] = trail[j - 1][stopped]
    return p, d, alive, data["colour"][k], trail


# ---------------------------------------------------------------------------- the objects

def _emission(name, strength_attr=None):
    """An emissive material coloured by the agents' `col` (read from the instancer or the geometry)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "col"
    attr.attribute_type = "INSTANCER" if strength_attr is None else "GEOMETRY"
    mix = nt.nodes.new("ShaderNodeMix")   # the colour, a little toward white (line light, not paint), as bright as
    mix.data_type = "RGBA"                # it is: a dark turtle (an unlit firefly) stays dark
    mix.inputs["B"].default_value = (1, 1, 1, 1)
    lum = nt.nodes.new("ShaderNodeRGBToBW")
    toward = nt.nodes.new("ShaderNodeMath")
    toward.operation = "MULTIPLY"
    toward.inputs[1].default_value = 0.6
    nt.links.new(attr.outputs["Color"], lum.inputs[0])
    nt.links.new(lum.outputs[0], toward.inputs[0])
    nt.links.new(toward.outputs[0], mix.inputs["Factor"])
    nt.links.new(attr.outputs["Color"], mix.inputs["A"])
    nt.links.new(mix.outputs["Result"], em.inputs["Color"])
    level = nt.nodes.new("ShaderNodeValue")
    level.name = level.label = "glow"
    level.outputs[0].default_value = 3.0
    if strength_attr:
        fade = nt.nodes.new("ShaderNodeAttribute")
        fade.attribute_name = strength_attr
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(fade.outputs["Fac"], mul.inputs[0])
        nt.links.new(level.outputs[0], mul.inputs[1])
        nt.links.new(mul.outputs[0], em.inputs["Strength"])
    else:
        nt.links.new(level.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _socket(ng, name, kind, io):
    ng.interface.new_socket(name=name, in_out=io, socket_type=kind)


def _named(nt, name, kind="FLOAT"):
    n = nt.nodes.new("GeometryNodeInputNamedAttribute")
    n.data_type = kind
    n.inputs["Name"].default_value = name
    return n


def _agents_nodes(mat):
    """Geometry nodes for the agents: an arrowhead on each living point, pointing along `dir`."""
    ng = bpy.data.node_groups.new("Construct run: agents", "GeometryNodeTree")
    _socket(ng, "Geometry", "NodeSocketGeometry", "INPUT")
    _socket(ng, "Geometry", "NodeSocketGeometry", "OUTPUT")
    n, L = ng.nodes, ng.links
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    dead = n.new("FunctionNodeCompare")
    dead.data_type, dead.operation = "FLOAT", "LESS_THAN"
    dead.inputs[1].default_value = 0.5
    L.new(_named(ng, "alive").outputs["Attribute"], dead.inputs[0])
    drop = n.new("GeometryNodeDeleteGeometry")
    L.new(gi.outputs[0], drop.inputs["Geometry"])
    L.new(dead.outputs[0], drop.inputs["Selection"])
    cone = n.new("GeometryNodeMeshCone")
    cone.inputs["Vertices"].default_value = 3
    cone.inputs["Radius Bottom"].default_value = ARROW * 0.32
    cone.inputs["Radius Top"].default_value = 0.0
    cone.inputs["Depth"].default_value = ARROW
    align = n.new("FunctionNodeAlignRotationToVector")
    align.axis = "Z"
    L.new(_named(ng, "dir", "FLOAT_VECTOR").outputs["Attribute"], align.inputs["Vector"])
    inst = n.new("GeometryNodeInstanceOnPoints")
    L.new(drop.outputs[0], inst.inputs["Points"])
    L.new(cone.outputs["Mesh"], inst.inputs["Instance"])
    L.new(align.outputs[0], inst.inputs["Rotation"])
    setm = n.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = mat
    L.new(inst.outputs[0], setm.inputs["Geometry"])
    L.new(setm.outputs[0], go.inputs[0])
    return ng


def _trails_nodes(mat, width):
    """Geometry nodes for the trails: each agent's chain of points as a thin tube, thinning as it fades."""
    ng = bpy.data.node_groups.new("Construct run: trails", "GeometryNodeTree")
    _socket(ng, "Geometry", "NodeSocketGeometry", "INPUT")
    _socket(ng, "Geometry", "NodeSocketGeometry", "OUTPUT")
    n, L = ng.nodes, ng.links
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    curve = n.new("GeometryNodeMeshToCurve")
    L.new(gi.outputs[0], curve.inputs["Mesh"])
    circle = n.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = 5
    circle.inputs["Radius"].default_value = width
    tube = n.new("GeometryNodeCurveToMesh")
    L.new(curve.outputs[0], tube.inputs["Curve"])
    L.new(circle.outputs["Curve"], tube.inputs["Profile Curve"])
    L.new(_named(ng, "fade").outputs["Attribute"], tube.inputs["Scale"])
    setm = n.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = mat
    L.new(tube.outputs[0], setm.inputs["Geometry"])
    L.new(setm.outputs[0], go.inputs[0])
    return ng


def _mesh_object(name, verts, edges, collection):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    return obj


def build(path, scene=None, trail_seconds=TRAIL_S, fps=30, camera=True):
    """Import a recording as a film: agents, trails, the links and the patches if it has them, the world's edge
    and a camera; the scene's frames span the run. Returns the collection."""
    if np is None:
        raise RuntimeError("the NetLogo run film needs NumPy (bundled with Blender)")
    data = read(path)
    sc = scene or bpy.context.scene
    title = data["header"].get("title", "NetLogo run")
    coll = bpy.data.collections.new("Construct run: %s" % title)
    sc.collection.children.link(coll)
    N = data["pos"].shape[1]

    agents = _mesh_object("agents", [(0, 0, 0)] * N, [], coll)
    for nm, kind in (("alive", "FLOAT"), ("dir", "FLOAT_VECTOR"), ("col", "FLOAT_COLOR")):
        agents.data.attributes.new(nm, kind, "POINT")
    amat = _emission("Construct run: agents")
    agents.modifiers.new("agents", "NODES").node_group = _agents_nodes(amat)

    edges = [(a * TRAIL_POINTS + j, a * TRAIL_POINTS + j + 1) for a in range(N) for j in range(TRAIL_POINTS - 1)]
    trails = _mesh_object("trails", [(0, 0, 0)] * (N * TRAIL_POINTS), edges, coll)
    for nm, kind in (("fade", "FLOAT"), ("col", "FLOAT_COLOR")):
        trails.data.attributes.new(nm, kind, "POINT")
    tmat = _emission("Construct run: trails", "fade")
    trails.modifiers.new("trails", "NODES").node_group = _trails_nodes(tmat, ARROW * 0.09)

    w, h = data["size"]
    z = data["depth"]
    box = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    lines = [(0, 1), (1, 2), (2, 3), (3, 0)]
    if z:   # a NetLogo 3D world: its box, the floor and the ceiling joined at the corners
        box += [(x, y, z) for x, y, _ in box]
        lines += [(4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    edge = _mesh_object("world", box, lines, coll)
    emat = _emission("Construct run: world", "fade")
    edge.data.attributes.new("fade", "FLOAT", "POINT").data.foreach_set("value", [0.25] * len(box))
    edge.data.attributes.new("col", "FLOAT_COLOR", "POINT").data.foreach_set("color", list(ACCENT + (1,)) * len(box))
    edge.modifiers.new("world", "NODES").node_group = _trails_nodes(emat, 0.006)
    _scale_trail_input(edge)

    extra = []
    L = len(data["links"])
    if L:   # the links: a thin line of light between the two agents, while the recording has it
        links = _mesh_object("links", [(0, 0, 0)] * (2 * L), [(2 * i, 2 * i + 1) for i in range(L)], coll)
        for nm, kind in (("fade", "FLOAT"), ("col", "FLOAT_COLOR")):
            links.data.attributes.new(nm, kind, "POINT")
        links.modifiers.new("links", "NODES").node_group = _trails_nodes(_emission("Construct run: links", "fade"),
                                                                         ARROW * 0.035)
        extra.append(links)
    pt = data["patches"]
    if pt:   # the patches: a floor of cells just under the agents, in the patch reporter's colours
        verts, faces, c, r0 = [], [], pt["cell"], pt["y1"]
        for r in range(pt["rows"]):
            for k in range(pt["cols"]):
                x, y = pt["x0"] + k * c, r0 - r * c
                base = len(verts)
                verts += [(x, y - c, -0.004), (x + c, y - c, -0.004), (x + c, y, -0.004), (x, y, -0.004)]
                faces.append((base, base + 1, base + 2, base + 3))
        me = bpy.data.meshes.new("patches")
        me.from_pydata(verts, [], faces)
        me.attributes.new("col", "FLOAT_COLOR", "FACE")
        floor = bpy.data.objects.new("patches", me)
        coll.objects.link(floor)
        me.materials.append(_floor_material())
        extra.append(floor)

    for obj in (agents, trails, edge, *extra):
        obj["construct_run"] = {"path": data["path"], "trail": trail_seconds, "fps": fps, "start": 1}

    sc.render.fps = fps
    sc.frame_start = 1
    sc.frame_end = 1 + int(math.ceil(seconds_of(data) * fps))
    if camera:
        _camera(sc, coll, max(w, h), z)
    _look(sc)
    update(sc, sc.frame_start)
    return coll


def _floor_material():
    """The patches' floor: each cell its own colour (a face attribute), dimly lit, so the agents stay in front."""
    mat = bpy.data.materials.new("Construct run: patches")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out, em, attr = nt.nodes.new("ShaderNodeOutputMaterial"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name, attr.attribute_type = "col", "GEOMETRY"
    em.inputs["Strength"].default_value = 0.55
    nt.links.new(attr.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _scale_trail_input(obj):
    """The world's edge is a closed loop of four points: its tube needs no fade, so the scale is constant."""
    ng = obj.modifiers[0].node_group
    tube = next(n for n in ng.nodes if n.bl_idname == "GeometryNodeCurveToMesh")
    for link in list(tube.inputs["Scale"].links):
        ng.links.remove(link)
    tube.inputs["Scale"].default_value = 1.0


def _camera(sc, coll, size, depth=0.0):
    """A slow orbit around the world, high enough to read the flock, close enough to feel it (further out
    for a 3D world, aimed at its middle)."""
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    coll.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 35
    cam.data.clip_end = size * 20
    target = bpy.data.objects.new("camera target", None)
    target.location = (0, 0, depth / 2)
    coll.objects.link(target)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    cam["construct_run_camera"] = {"radius": size * (1.45 if depth else 0.95), "height": depth / 2 + size * (0.45 if depth else 0.62),
                                   "degrees_per_second": 4.0}


def _look(sc):
    """A black world, EEVEE, and a bloom so the line light glows."""
    sc.render.engine = "BLENDER_EEVEE"
    world = bpy.data.worlds.new("Construct run: dark")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0, 0, 0, 1)
    sc.world = world
    sc.view_settings.view_transform = "Standard"
    if hasattr(sc, "compositing_node_group"):   # Blender 5: the compositor is a node group
        ng = bpy.data.node_groups.new("Construct run: glow", "CompositorNodeTree")
        _socket(ng, "Image", "NodeSocketColor", "OUTPUT")
        rl, glare, go = ng.nodes.new("CompositorNodeRLayers"), ng.nodes.new("CompositorNodeGlare"), ng.nodes.new("NodeGroupOutput")
        glare.inputs["Type"].default_value = "Bloom"
        glare.inputs["Threshold"].default_value = 0.6
        glare.inputs["Strength"].default_value = 0.9
        glare.inputs["Size"].default_value = 0.6
        ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
        ng.links.new(glare.outputs["Image"], go.inputs["Image"])
        sc.compositing_node_group = ng


# ---------------------------------------------------------------------------- each frame

def update(sc, frame):
    """Move every run object in the scene to this frame: agents, trails, links, patches, the camera."""
    for obj in [o for o in sc.objects if "construct_run" in o]:
        info = obj["construct_run"]
        try:
            data = read(info["path"])
        except (OSError, ValueError):
            beside = os.path.join(os.path.dirname(bpy.data.filepath or ""), os.path.basename(info["path"]))
            try:   # a .blend moved with its recording beside it
                data = read(beside)
            except (OSError, ValueError):
                continue
        seconds = (frame - info.get("start", 1)) / info.get("fps", sc.render.fps)
        tick = data["ticks"][0] + seconds * TPS
        p, d, alive, colour, trail = state(data, tick, info.get("trail", TRAIL_S) * TPS)
        me = obj.data
        if obj.name.startswith("agents"):
            me.vertices.foreach_set("co", p.ravel())
            me.attributes["alive"].data.foreach_set("value", alive.astype(np.float32))
            me.attributes["dir"].data.foreach_set("vector", d.ravel())
            me.attributes["col"].data.foreach_set("color", np.hstack([colour, np.ones((len(p), 1), np.float32)]).ravel())
            level = 4.3
        elif obj.name.startswith("trails"):
            pts = trail.transpose(1, 0, 2)   # agent by agent, newest first
            me.vertices.foreach_set("co", pts.ravel())
            fade = np.tile(np.linspace(1.0, 0.0, TRAIL_POINTS, dtype=np.float32) ** 1.5, (len(p), 1))
            fade[~alive] = 0
            me.attributes["fade"].data.foreach_set("value", fade.ravel())
            me.attributes["col"].data.foreach_set("color", np.repeat(np.hstack([colour, np.ones((len(p), 1), np.float32)]),
                                                                     TRAIL_POINTS, axis=0).ravel())
            level = 2.8
        elif obj.name.startswith("links"):
            k = int(np.clip(np.searchsorted(data["ticks"], tick, side="right") - 1, 0, len(data["ticks"]) - 1))
            a, b = data["links"][:, 0], data["links"][:, 1]
            me.vertices.foreach_set("co", np.stack([p[a], p[b]], axis=1).ravel())
            on = (data["link_on"][k] & alive[a] & alive[b]).astype(np.float32)
            me.attributes["fade"].data.foreach_set("value", np.repeat(on, 2))
            mid = np.hstack([(colour[a] + colour[b]) / 2, np.ones((len(a), 1), np.float32)])
            me.attributes["col"].data.foreach_set("color", np.repeat(mid, 2, axis=0).ravel())
            level = 1.6
        elif obj.name.startswith("patches"):
            pt = data["patches"]
            j = int(np.clip(np.searchsorted(pt["ticks"], tick, side="right") - 1, 0, len(pt["ticks"]) - 1))
            me.attributes["col"].data.foreach_set("color", np.hstack([pt["colour"][j], np.ones((len(pt["colour"][j]), 1),
                                                                                                np.float32)]).ravel())
            me.update()
            continue
        else:
            level = 1.9
        me.update()
        for mat in _materials_of(obj):
            node = mat.node_tree.nodes.get("glow")
            if node:
                node.outputs[0].default_value = level
    for cam in [o for o in sc.objects if "construct_run_camera" in o]:
        c = cam["construct_run_camera"]
        a = math.radians(30 + c["degrees_per_second"] * (frame - 1) / sc.render.fps)
        cam.location = (c["radius"] * math.sin(a), -c["radius"] * math.cos(a), c["height"])


def _materials_of(obj):
    mod = obj.modifiers[0] if obj.modifiers else None
    if mod and mod.node_group:
        for n in mod.node_group.nodes:
            if n.bl_idname == "GeometryNodeSetMaterial" and n.inputs["Material"].default_value:
                yield n.inputs["Material"].default_value


def render(run, out=None, blend=None, size="1920x1080", start=0.0, seconds=None, samples=16, trail=TRAIL_S):
    """In Blender: a fresh scene with the run's film, saved as `blend` and/or rendered to `out` (an .mp4). Returns
    the frame range."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    register()
    sc = bpy.context.scene
    build(run, sc, trail_seconds=trail)
    w, h = (int(x) for x in str(size).lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    first = 1 + int(round(start * sc.render.fps))
    sc.frame_start = first
    if seconds:
        sc.frame_end = first + int(round(seconds * sc.render.fps)) - 1
    sc.eevee.taa_render_samples = samples
    s = sc.render.image_settings
    if hasattr(s, "media_type"):
        s.media_type = "VIDEO"
    s.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.ffmpeg.audio_codec = "NONE"
    if out:
        sc.render.filepath = os.path.abspath(out)
    if blend:
        update(sc, sc.frame_start)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend))
    if out:
        bpy.ops.render.render(animation=True)
    return sc.frame_start, sc.frame_end


def find_blender(given=None):
    """A Blender to run: the one given (None if it is not there), $CONSTRUCT_BLENDER, `blender` on the PATH, or
    the usual installs."""
    import glob
    import shutil
    if given:
        return given if os.path.isfile(given) else shutil.which(given)
    cands = [os.environ.get("CONSTRUCT_BLENDER"), shutil.which("blender"),
             "/Applications/Blender.app/Contents/MacOS/Blender",
             os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"), "/usr/bin/blender", "/snap/bin/blender"]
    cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    return next((c for c in cands if c and os.path.isfile(c)), None)


_HANDLER = []


def register():
    """Move the run objects on every frame change (kept across file loads)."""
    if not _HANDLER:
        @bpy.app.handlers.persistent
        def on_frame(sc, *_):
            update(sc, sc.frame_current)
        _HANDLER.append(on_frame)
    if _HANDLER[0] not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_HANDLER[0])


def unregister():
    if _HANDLER and _HANDLER[0] in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(_HANDLER[0])
