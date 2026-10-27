"""Construct for Blender: import a construct as a 3D model with its parts, joints and build.

File > Import > Construct (.json, .glb) reads a construct scene (or a parameter document), compiles
it with the bundled Construct runtime and exports it to glTF in memory, or reads a .glb written by
`construct export`. Blender's own glTF importer brings in the parts, stages and motion; this
add-on then gives the construct three controls on its root object, all plain custom properties
driving the scene, so the .blend keeps working without the add-on:

  build   0..1  the assembly: every vertex appears at its build phase, with a bright front
  open    0..1  every joint, in its order groups (hinges, turns, slides, lifts)
  metal   0..1  light to metal: 0 is the hologram (light lines, ghost surfaces), 1 the solid model
              with its lines as dark seams

and `wire` (metres), the thickness of the line art. The Construct panel in the sidebar (N) shows
them, with an operator that keyframes a reveal.
"""

import json
import math
import os
import tempfile

import bmesh
import bpy
import mathutils
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .construct_hologram import export as c_export, params as c_params, product as c_product

PROPS = (("build", 1.0, "Assembly: each part appears at its build phase"),
         ("open", 0.0, "Opens every joint, in its order groups"),
         ("metal", 1.0, "Light to metal: 0 is the hologram, 1 the solid model"))
# the line art's tone for each role (as the hologram draws it), in the house palette
ROLE_TONE = {"mass": "hairline", "structure": "structure", "detail": "structure", "identity": "identity",
             "data": "accent", "ornament": "dust", "ground": "faint", "artwork": "hairline"}
FRONT = 0.025          # how far behind the build front a surface still glows (build phase)
ACCENT = "#d16bd0"


def _rgb(hex_color):
    lin = c_export._linear(c_export._hex(hex_color, "colour"))
    return (lin[0], lin[1], lin[2], 1.0)


# ---------------------------------------------------------------------------- reading

def _glb_of(path, wire_radius=None):
    """A .glb path for the file: itself, or a construct compiled and exported to a temporary file."""
    if path.lower().endswith(".glb"):
        return path, None
    with open(path, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    if c_params.is_params(doc):
        doc = c_params.expand(doc)
    out, _ = c_export.render(doc, "glb", wire="edges", wire_radius=wire_radius)
    fd, tmp = tempfile.mkstemp(suffix=".glb", prefix="construct-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(out["glb"])
    return tmp, tmp


def _info(obj):
    c = obj.get("construct")
    return c.to_dict() if hasattr(c, "to_dict") else (c or {})


# ---------------------------------------------------------------------------- drivers

def _drive(owner, path, index, root, names, expression):
    fc = owner.driver_add(path, index) if index is not None else owner.driver_add(path)
    d = fc.driver
    d.type = "SCRIPTED"
    for name in names:
        v = d.variables.new()
        v.name, v.type = name, "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = root
        v.targets[0].data_path = '["%s"]' % name
    d.expression = expression
    return fc


def _value_node(nodes, root, name, location):
    n = nodes.new("ShaderNodeValue")
    n.label, n.location = name, location
    _drive(n.outputs[0], "default_value", None, root, [name], name)
    return n


def _math(nodes, links, op, a, b=None, location=(0, 0), clamp=False, c=None):
    n = nodes.new("ShaderNodeMath")
    n.operation, n.location, n.use_clamp = op, location, clamp
    for i, x in enumerate((a, b, c)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            links.new(x, n.inputs[i])
    return n.outputs[0]


def _reveal(nodes, links, root, x=-900):
    """(visible, glow): visible is 1 once the build has passed this point, glow fades behind the front."""
    phase = nodes.new("ShaderNodeAttribute")
    phase.attribute_type, phase.attribute_name, phase.location = "GEOMETRY", "_PHASE", (x, 200)
    build = _value_node(nodes, root, "build", (x, 0))
    behind = _math(nodes, links, "SUBTRACT", build.outputs[0], phase.outputs["Fac"], (x + 200, 100))
    visible = _math(nodes, links, "GREATER_THAN", behind, -0.0001, (x + 400, 200))
    near = _math(nodes, links, "DIVIDE", behind, FRONT, (x + 400, 0))
    fade = _math(nodes, links, "SUBTRACT", 1.0, near, (x + 600, 0), clamp=True)
    building = _math(nodes, links, "LESS_THAN", build.outputs[0], 0.9999, (x + 600, -200))
    glow = _math(nodes, links, "MULTIPLY", _math(nodes, links, "MULTIPLY", fade, visible, (x + 800, 0)),
                 building, (x + 1000, 0))
    return visible, glow


def _surface(mat, root):
    """A solid material: its own surface, ghosted in the hologram, revealed by the build, glowing at the front."""
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    shader = out.inputs["Surface"].links[0].from_node if out.inputs["Surface"].links else None
    if shader is None:
        shader = nodes.new("ShaderNodeBsdfPrincipled")
    visible, glow = _reveal(nodes, links, root)
    metal = _value_node(nodes, root, "metal", (-900, -400))
    ghost = _math(nodes, links, "MULTIPLY_ADD", metal.outputs[0], 0.94, (-700, -400), c=0.06)
    alpha = _math(nodes, links, "MULTIPLY", ghost, visible, (-500, -300))
    clear = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(alpha, mix.inputs[0])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(shader.outputs[0], mix.inputs[2])
    front = nodes.new("ShaderNodeEmission")
    front.inputs["Color"].default_value = _rgb(ACCENT)
    strength = _math(nodes, links, "MULTIPLY", glow, 14.0, (-300, -500))
    links.new(strength, front.inputs["Strength"])
    add = nodes.new("ShaderNodeAddShader")
    links.new(mix.outputs[0], add.inputs[0])
    links.new(front.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    mix.location, add.location, out.location = (200, 0), (400, 0), (600, 0)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"


def _light_material(tone, root, name):
    """The line art: light in the hologram, dark seams on the metal, revealed by the build."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    visible, glow = _reveal(nodes, links, root)
    metal = _value_node(nodes, root, "metal", (-900, -400))
    light = nodes.new("ShaderNodeEmission")
    light.inputs["Color"].default_value = _rgb(c_export.TONE_COLOR[tone])
    links.new(_math(nodes, links, "MULTIPLY_ADD", glow, 10.0, (-300, 200), c=4.0), light.inputs["Strength"])
    seam = nodes.new("ShaderNodeBsdfPrincipled")
    seam.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1.0)
    seam.inputs["Roughness"].default_value = 0.6
    look = nodes.new("ShaderNodeMixShader")
    links.new(metal.outputs[0], look.inputs[0])
    links.new(light.outputs[0], look.inputs[1])
    links.new(seam.outputs[0], look.inputs[2])
    clear = nodes.new("ShaderNodeBsdfTransparent")
    show = nodes.new("ShaderNodeMixShader")
    links.new(visible, show.inputs[0])
    links.new(clear.outputs[0], show.inputs[1])
    links.new(look.outputs[0], show.inputs[2])
    links.new(show.outputs[0], out.inputs["Surface"])
    look.location, show.location = (200, 0), (450, 0)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    return mat


def _tube_group(root, name):
    """Geometry nodes: line art (loose edges) to thin tubes, keeping the build phase; the radius
    follows the construct's `wire`."""
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, ln = ng.nodes, ng.links
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    to_curve, circle, to_mesh = n.new("GeometryNodeMeshToCurve"), n.new("GeometryNodeCurvePrimitiveCircle"), \
        n.new("GeometryNodeCurveToMesh")
    circle.inputs["Resolution"].default_value = 4
    _drive(circle.inputs["Radius"], "default_value", None, root, ["wire"], "wire")
    ln.new(gi.outputs[0], to_curve.inputs["Mesh"])
    ln.new(to_curve.outputs[0], to_mesh.inputs["Curve"])
    ln.new(circle.outputs["Curve"], to_mesh.inputs["Profile Curve"])
    ln.new(to_mesh.outputs[0], go.inputs[0])
    gi.location, to_curve.location, circle.location, to_mesh.location, go.location = \
        (-600, 0), (-350, 80), (-350, -150), (-100, 0), (150, 0)
    return ng


# ---------------------------------------------------------------------------- the construct

def _split_lines(obj):
    """Move a mesh's loose edges (the line art) into a new mesh, with their build phase."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    loose = [e for e in bm.edges if not e.link_faces]
    if not loose:
        bm.free()
        return None
    layer = bm.verts.layers.float.get("_PHASE")
    index, coords, phases, edges = {}, [], [], []
    for e in loose:
        pair = []
        for v in e.verts:
            if v not in index:
                index[v] = len(coords)
                coords.append(tuple(v.co))
                phases.append(v[layer] if layer else 1.0)
            pair.append(index[v])
        edges.append(tuple(pair))
    bmesh.ops.delete(bm, geom=loose, context="EDGES")
    bm.to_mesh(obj.data)
    bm.free()
    me = bpy.data.meshes.new(obj.data.name + ":light")
    me.from_pydata(coords, edges, [])
    me.attributes.new("_PHASE", "FLOAT", "POINT").data.foreach_set("value", phases)
    return me


def setup(root, objects, wire_radius, metal=1.0, keep_animations=False):
    """Give an imported construct its controls: build, open, metal and wire."""
    info = _info(root)
    for name, default, desc in PROPS:
        root[name] = metal if name == "metal" else default
        root.id_properties_ui(name).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=desc)
    root["wire"] = wire_radius
    root.id_properties_ui("wire").update(min=0.0, soft_max=wire_radius * 5, description="Line art radius (m)",
                                         subtype="DISTANCE")
    root.update_tag()   # the evaluated copy must see the new properties before any driver reads them

    # the joints: drivers on the pivots replace the imported `open` animations
    arts = {a["id"]: a for a in info.get("articulations", [])}
    orders = sorted({a["order"] for a in arts.values()})
    groups = max(1, len(orders))
    dead = set()
    for o in objects:
        ad = o.animation_data
        if ad and not keep_animations:
            for t in list(ad.nla_tracks):
                if any(s.action and s.action.name.split(".")[0].startswith("open") for s in t.strips):
                    dead |= {s.action for s in t.strips if s.action}
                    ad.nla_tracks.remove(t)
            if ad.action and ad.action.name.split(".")[0].startswith("open"):
                dead.add(ad.action)
                ad.action = None
        a = arts.get(_info(o).get("articulation"))
        if not a:
            continue
        k = orders.index(a["order"])
        u = "smoothstep(%d, %d, open * %d)" % (k, k + 1, groups)
        x, y, z = a["axis"]
        axis = (x, -z, y)                                  # glTF Y up to Blender Z up
        if a["type"] in ("hinge", "turn"):
            o.rotation_mode = "AXIS_ANGLE"
            o.rotation_axis_angle = (0.0,) + axis
            _drive(o, "rotation_axis_angle", 0, root, ["open"], "%.8f * %s" % (math.radians(a["amount"]), u))
        else:
            rest = tuple(o.location)
            for i in range(3):
                _drive(o, "location", i, root, ["open"], "%.8f + %.8f * %s" % (rest[i], axis[i] * a["amount"], u))
    for act in dead:
        if act.users == 0:
            bpy.data.actions.remove(act)

    # the surfaces: revealed by the build, ghosted in the hologram
    done = set()
    for o in objects:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m and m not in done and not m.name.startswith("construct:light"):
                _surface(m, root)
                done.add(m)

    # the line art: its own objects, as tubes, light or seams
    group, lights = _tube_group(root, "%s:light" % info.get("id", "construct")), {}
    for o in list(objects):
        if o.type != "MESH":
            continue
        me = _split_lines(o)
        if me is None:
            continue
        tone = ROLE_TONE.get(_info(o).get("role"), "hairline")
        if tone not in lights:
            lights[tone] = _light_material(tone, root, "%s:light:%s" % (info.get("id", "construct"), tone))
        lo = bpy.data.objects.new(o.name.replace(":mesh", "") + ":light", me)
        for col in o.users_collection:
            col.objects.link(lo)
        lo.parent = o
        lo.data.materials.append(lights[tone])
        mod = lo.modifiers.new("Construct Light", "NODES")
        mod.node_group = group
    for m in list(bpy.data.materials):
        if m.name.startswith("construct:light") and m.users == 0:
            bpy.data.materials.remove(m)
    return root


def import_construct(path, wire_scale=1.0, metal=1.0, keep_animations=False):
    """Import a construct (.json scene or parameter document, or a Construct .glb). Returns its root."""
    glb, tmp = _glb_of(path)
    before = set(bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=glb)
    finally:
        if tmp:
            os.remove(tmp)
    objects = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in objects if "scene_sha256" in _info(o)]
    if not roots:
        raise ValueError("not a construct: no Construct root in %s" % os.path.basename(path))
    root = roots[0]
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for o in objects:
        if o.type == "MESH":
            for c in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(c)
                lo = [min(lo[i], w[i]) for i in range(3)]
                hi = [max(hi[i], w[i]) for i in range(3)]
    size = math.dist(lo, hi) if lo[0] != math.inf else 1.0
    return setup(root, objects, max(size * 0.00045, 0.0001) * wire_scale, metal, keep_animations)


def construct_root(obj):
    while obj is not None:
        if "scene_sha256" in _info(obj) and "build" in obj:
            return obj
        obj = obj.parent
    return None


# ---------------------------------------------------------------------------- operators and panel

class CONSTRUCT_OT_import(bpy.types.Operator, ImportHelper):
    """Import a construct with its parts, joints and build: a scene (.json) or a Construct .glb"""
    bl_idname = "import_scene.construct"
    bl_label = "Import Construct"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json;*.glb", options={"HIDDEN"})
    wire_scale: FloatProperty(name="Line thickness", default=1.0, min=0.0, soft_max=5.0,
                              description="Line art radius, as a multiple of the default for the object's size")
    start_as: bpy.props.EnumProperty(name="Start as", default="METAL",
                                     items=(("METAL", "Metal", "The solid model"),
                                            ("LIGHT", "Light", "The hologram")))
    keep_animations: BoolProperty(name="Keep open animations", default=False,
                                  description="Keep the file's open actions besides the Open control")

    def execute(self, context):
        try:
            root = import_construct(self.filepath, self.wire_scale, 1.0 if self.start_as == "METAL" else 0.0,
                                    self.keep_animations)
        except Exception as exc:   # a scene the compiler refuses, a file that is not a construct
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        for o in context.selected_objects:
            o.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        self.report({"INFO"}, "Imported %s" % _info(root).get("title", root.name))
        return {"FINISHED"}


class CONSTRUCT_OT_animate(bpy.types.Operator):
    """Keyframe a reveal on the active construct: assemble as light, turn to metal, then open"""
    bl_idname = "construct.animate_reveal"
    bl_label = "Keyframe a Reveal"
    bl_options = {"REGISTER", "UNDO"}

    assemble: IntProperty(name="Assemble (frames)", default=120, min=1)
    to_metal: IntProperty(name="To metal (frames)", default=48, min=1)
    open_frames: IntProperty(name="Open (frames)", default=48, min=0)

    @classmethod
    def poll(cls, context):
        return construct_root(context.active_object) is not None

    def execute(self, context):
        root = construct_root(context.active_object)
        f0 = context.scene.frame_current
        keys = [("build", f0, 0.0), ("metal", f0, 0.0), ("open", f0, 0.0), ("build", f0 + self.assemble, 1.0),
                ("metal", f0 + self.assemble, 0.0), ("metal", f0 + self.assemble + self.to_metal, 1.0)]
        if self.open_frames:
            end = f0 + self.assemble + self.to_metal
            keys += [("open", end, 0.0), ("open", end + self.open_frames, 1.0)]
        for name, frame, value in keys:
            root[name] = value
            root.keyframe_insert('["%s"]' % name, frame=frame)
        context.scene.frame_end = max(context.scene.frame_end, keys[-1][1] + 24)
        return {"FINISHED"}


class CONSTRUCT_PT_panel(bpy.types.Panel):
    bl_label = "Construct"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Construct"

    def draw(self, context):
        root = construct_root(context.active_object)
        col = self.layout.column()
        if root is None:
            col.label(text="Select a construct")
            col.operator(CONSTRUCT_OT_import.bl_idname, icon="IMPORT")
            return
        info = _info(root)
        col.label(text=info.get("title", root.name))
        for name, label in (("build", "Build"), ("open", "Open"), ("metal", "Light ↔ Metal"), ("wire", "Lines")):
            col.prop(root, '["%s"]' % name, text=label, slider=name != "wire")
        col.separator()
        col.operator(CONSTRUCT_OT_animate.bl_idname, icon="KEY_HLT")
        part = context.active_object
        if part is not root and "certainty" in _info(part):
            p = _info(part)
            box = col.box()
            box.label(text="%s: %s" % (p.get("id"), p.get("role")))
            box.label(text="certainty: %s" % p.get("certainty"))


def _menu(self, context):
    self.layout.operator(CONSTRUCT_OT_import.bl_idname, text="Construct (.json, .glb)")


CLASSES = (CONSTRUCT_OT_import, CONSTRUCT_OT_animate, CONSTRUCT_PT_panel)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)


VERSION = c_product.VERSION
