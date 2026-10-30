"""Minimal MCP stdio server exposing Construct's tools.

Newline-delimited JSON-RPC 2.0 over stdin/stdout. Standard library only.
Never reads or writes files, never spawns processes, never fetches or renders.

Tools: construct_diagnose, construct_params_template, construct_expand_params,
construct_compile and construct_limits (the effort tier a host enforces) for scenes and parameter documents (contract construct/0.2); the legacy
v0.1 construction sheets (hologram_template, hologram_validate, hologram_compile). The 0.2
pre-release names hologram_diagnose, hologram_params_template, hologram_expand_params and
hologram_compile_scene are still answered for one release. Every tool works
only on the JSON in the request.
"""

import base64
import json
import sys

from . import diagnose, export, hologram, params, product, scene, tiers, __version__

PROTOCOL_VERSION = "2025-11-25"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

TOOLS = [
    {
        "name": "hologram_template",
        "description": "Return a synthetic starter tessera-hologram sheet for a kind.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(hologram.KINDS)},
                "title": {"type": "string", "maxLength": 500},
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "hologram_validate",
        "description": "Validate a tessera-hologram sheet; returns error list.",
        "inputSchema": {
            "type": "object",
            "properties": {"sheet": {"type": "object"}},
            "required": ["sheet"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "hologram_compile",
        "description": "Compile a tessera-hologram sheet into tessera-geometry.",
        "inputSchema": {
            "type": "object",
            "properties": {"sheet": {"type": "object"}},
            "required": ["sheet"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
    },
]


_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False, "idempotentHint": True}
_DOC = {"type": "object", "description": "a construct-scene (version 2) or a construct-params document"}
TOOLS += [
    {"name": "construct_diagnose",
     "description": "Check a v2 scene or parameter document (contract construct/0.2): every problem with a "
                    "JSON path, a code and a fix hint, plus repair_text to send back to the model that wrote it. "
                    "Give `text` (the model's raw answer) or `document` (parsed JSON).",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "maxLength": MAX_REQUEST_BYTES},
                                                      "document": _DOC},
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_params_template",
     "description": "A parameter document to fill in for an archetype (case, book, object, vessel) and variant: the "
                    "simple path for models that struggle with full scenes. Without arguments: every archetype.",
     "inputSchema": {"type": "object", "properties": {"archetype": {"type": "string", "enum": sorted(params.VARIANTS)},
                                                      "variant": {"type": "string"}},
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_expand_params",
     "description": "The full v2 scene a valid parameter document builds (or its diagnostics when it is not valid).",
     "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}}, "required": ["params"],
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_compile",
     "description": "Compile a valid v2 scene or parameter document into construct-geometry v2 (or return "
                    "its diagnostics). Artwork bytes are never read: slots carry asset ids and hashes only.",
     "inputSchema": {"type": "object", "properties": {"document": _DOC}, "required": ["document"],
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_export",
     "description": "A 3D model of a valid v2 scene or parameter document: glTF 2.0 (base64 .glb: named parts, "
                    "materials by role, the open and idle animations, each vertex's build phase as _PHASE) or OBJ "
                    "text with its MTL. Opens in Blender, Godot, Unreal, Unity (glTFast) and three.js.",
     "inputSchema": {"type": "object", "properties": {
         "document": _DOC, "format": {"type": "string", "enum": ["glb", "obj"]},
         "wire": {"type": "string", "enum": ["edges", "tubes", "seams", "none"]},
         "pose": {"type": "string", "enum": ["closed", "open"]},
         "frame": {"type": "string", "enum": ["y-up", "z-up"]},
         "merge": {"type": "boolean", "description": "merge the parts that do not move, one mesh per material"},
         "colliders": {"type": "boolean", "description": "a box collider per part (Godot: -convcolonly)"},
         "pieces": {"type": "boolean", "description": "the pieces it would break into, each a rigid body with convex "
                                                      "shapes (OMI_physics_body), interlocked parts together"},
         "materials": {"type": "object", "description": "a material map: {\"materials\": [{\"parts\": [...], "
                                                        "\"color\": \"#rrggbb\", \"metallic\", \"roughness\"}]}"}},
                     "required": ["document"], "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_print",
     "description": "One watertight body of a valid v2 scene or parameter document, to 3D print: 3MF (default) or "
                    "binary STL, base64, in millimetres, Z up, on the bed; with the checks (watertight, separate "
                    "pieces, fits the bed, overhangs that need supports, what was thickened) and the scale.",
     "inputSchema": {"type": "object", "properties": {
         "document": _DOC, "format": {"type": "string", "enum": ["3mf", "stl"]},
         "size": {"type": "number", "description": "the longest side in mm (default 100)"},
         "scale": {"type": "number", "description": "print at 1:N of the real size instead"},
         "detail": {"type": "number", "description": "the voxel size in mm (default 0.4)"},
         "wall": {"type": "number", "description": "open surfaces thickened to this wall in mm (default 0.8)"},
         "join": {"type": "number", "description": "gaps between parts up to this wide are closed, in mm (default 1.6)"},
         "lines": {"type": ["boolean", "string"], "enum": [True, False, "none", "engrave", "raised"],
                   "description": "the parts drawn only in lines: none, engrave (cut in) or raised (true)"},
         "printer": {"type": "string", "enum": ["small", "desktop", "cube", "large", "resin"],
                     "description": "a printer class: its bed, finest voxel and thinnest wall"},
         "fit": {"type": "boolean", "description": "the largest print that stands on the printer's bed"},
         "exact": {"type": "boolean", "description": "3MF: the construct's own solids, parts of one object the slicer "
                                                     "joins; only open and too-thin surfaces become voxels"},
         "compare_printers": {"type": "boolean",
                              "description": "instead of a print: for each printer class, the largest print and how "
                                             "much detail survives"}},
                     "required": ["document"], "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_netlogo_instrument",
     "description": "A NetLogo 7 model (.nlogox text) that records its run for Construct: the recorder included, "
                    "set up after setup's reset-ticks and recording after go's tick (or the model's own buttons; a model "
                    "that never ticks records by steps). Returns the model, a headless BehaviorSpace experiment and the "
                    "recorder (construct.nls) to save beside it; run it in NetLogo, then draw run.jsonl with "
                    "construct_netlogo_draw. NetLogo models in the library keep their own licence.",
     "inputSchema": {"type": "object", "properties": {
         "model": {"type": "string", "maxLength": 900000, "description": "the .nlogox file's text"},
         "title": {"type": "string", "maxLength": 120},
         "turtles": {"type": "array", "items": {"type": "string"}, "description": "turtle variables or reporters, per turtle"},
         "reporters": {"type": "array", "items": {"type": "string"}, "description": "observer reporters, each record"},
         "patches": {"type": "object", "properties": {"reporter": {"type": "string"}, "every": {"type": "integer", "minimum": 1}},
                     "required": ["reporter"], "additionalProperties": False},
         "every": {"type": "integer", "minimum": 1}, "seed": {"type": "integer"},
         "ticks": {"type": "integer", "minimum": 1, "description": "the experiment's length"},
         "skip_turtles": {"type": "boolean"},
         "setup": {"type": "string", "description": "the setup command, if not the model's own (with inputs: \"setup 4\")"},
         "go": {"type": "string", "description": "the go command, if not the model's own"}},
                     "required": ["model", "title"], "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_netlogo_draw",
     "description": "A construct of a recorded NetLogo run (the JSON Lines a run writes), computed from the data alone, "
                    "with its legend, how-to-read lines, replay clock and counts, and a data lock. Views: space-time "
                    "(moving agents), network-time (spreading on a network; give state), phase (two reporters in a "
                    "cycle), field (spreading over patches), pulse (turtles switching a state on and off: how many at once, "
                    "tick by tick), auto (the one the data suits). Moving agents and pulses are drawn over the window "
                    "where their order formed when it forms early (window: auto, whole, or a tick). Optional: an art-direction layer (art: views, labels, "
                    "milestones; never the data), solid (spheres, tubes, a surface, for a 3D model) and materials (the "
                    "run's own colours, for construct_export). Compile or export the scene with the other tools.",
     "inputSchema": {"type": "object", "properties": {
         "recording": {"type": "string", "maxLength": 950000, "description": "the run's JSON Lines (a larger run: "
                       "record with every > 1, or draw it with the command line)"},
         "view": {"type": "string", "enum": ["auto", "space-time", "network-time", "phase", "field", "pulse"]},
         "window": {"type": "string", "description": "space-time and pulse: auto (default), whole, or the tick to end at"},
         "landmarks": {"type": "string", "enum": ["on", "off"], "description": "the moments worth marking, from the counts (on by default)"},
         "colors": {"type": "string", "enum": ["run", "house"], "description": "run (default): the run's own NetLogo colours; house: Construct's tones"},
         "title": {"type": "string", "maxLength": 120},
         "state": {"type": "string"}, "x": {"type": "string"}, "z": {"type": "string"},
         "change": {"type": "string", "enum": ["first", "last"]}, "time": {"type": "string", "enum": ["linear", "sqrt"]},
         "max_agents": {"type": "integer", "minimum": 1}, "smooth": {"type": "integer", "minimum": 1},
         "levels": {"type": "integer", "minimum": 1}, "resolution": {"type": "integer", "minimum": 4},
         "solid": {"type": "boolean"}, "materials": {"type": "boolean"},
         "art": {"type": "object", "description": "an art-direction layer (docs/NETLOGO.md: credit, title, summary, "
                                                  "looks, parts, facts, annotations, presentation, animation, reading, legend)"}},
                     "required": ["recording", "view"], "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "construct_limits",
     "description": "The limits of a mode (fast, masterpiece, unbounded) or tier (wall clock, check and review "
                    "rounds, research counts) with any overrides applied, for the host to enforce: aim for genuinely "
                    "good, stop at the first limit. Overrides can raise a limit, never remove it. Also reads "
                    "'mode:'/'tier:'/'research:' from a request.",
     "inputSchema": {"type": "object", "properties": {
         "tier": {"type": "string", "enum": list(tiers.MODE_OF)},
         "request": {"type": "string", "maxLength": 20000},
         "overrides": {"type": "object", "additionalProperties": False,
                       "properties": {k: {"type": "number", "minimum": 0, "maximum": v} for k, v in tiers.CEILING.items()}}},
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
]


class _RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _valid_id(v):
    if isinstance(v, bool):
        return False
    return isinstance(v, (str, int))


def _tool_result(payload, is_error=False):
    text = json.dumps(payload, separators=(",", ":"))
    result = {"content": [{"type": "text", "text": text}]}
    if isinstance(payload, dict):
        result["structuredContent"] = payload
    if is_error:
        result["isError"] = True
    return result


def _call_tool(name, args):
    if not isinstance(args, dict):
        raise _RpcError(-32602, "params.arguments must be an object")
    if name == "hologram_template":
        extra = set(args) - {"kind", "title"}
        if extra:
            raise _RpcError(-32602, "unknown arguments")
        if "kind" not in args:
            raise _RpcError(-32602, "missing kind")
        try:
            sheet = hologram.template(args["kind"], args.get("title"))
        except hologram.SheetError as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
        return _tool_result(sheet)
    if name in ("hologram_validate", "hologram_compile"):
        extra = set(args) - {"sheet"}
        if extra:
            raise _RpcError(-32602, "unknown arguments")
        if "sheet" not in args:
            raise _RpcError(-32602, "missing sheet")
        sheet = args["sheet"]
        if name == "hologram_validate":
            errors = hologram.validate(sheet)
            return _tool_result({"valid": not errors, "errors": errors})
        try:
            compiled = hologram.compile_sheet(sheet)
        except hologram.SheetError as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
        return _tool_result(compiled)
    name = DEPRECATED.get(name, name)
    if name in V2_TOOLS:
        return _call_v2(name, args)
    raise _RpcError(-32602, "unknown tool")


V2_TOOLS = {"construct_diagnose": ({"text", "document"}, set()),
            "construct_params_template": ({"archetype", "variant"}, set()),
            "construct_expand_params": ({"params"}, {"params"}),
            "construct_compile": ({"document"}, {"document"}),
            "construct_export": ({"document", "format", "wire", "pose", "frame", "materials", "merge", "colliders", "pieces"},
                                 {"document"}),
            "construct_print": ({"document", "format", "size", "scale", "detail", "wall", "join", "lines", "printer", "fit",
                                 "compare_printers", "exact"}, {"document"}),
            "construct_limits": ({"tier", "request", "overrides"}, set()),
            "construct_netlogo_instrument": ({"model", "title", "turtles", "reporters", "patches", "every", "seed", "ticks",
                                              "skip_turtles", "setup", "go"}, {"model", "title"}),
            "construct_netlogo_draw": ({"recording", "view", "title", "state", "x", "z", "change", "time", "max_agents", "window", "landmarks", "colors",
                                        "smooth", "levels", "resolution", "solid", "materials", "art"}, {"recording", "view"})}
# the 0.2 pre-release names: still answered for one release, no longer listed
DEPRECATED = {"hologram_diagnose": "construct_diagnose", "hologram_params_template": "construct_params_template",
              "hologram_expand_params": "construct_expand_params", "hologram_compile_scene": "construct_compile"}


def _call_v2(name, args):
    allowed, required = V2_TOOLS[name]
    if set(args) - allowed:
        raise _RpcError(-32602, "unknown arguments")
    if required - set(args):
        raise _RpcError(-32602, "missing " + ", ".join(sorted(required - set(args))))
    if name == "construct_diagnose":
        if ("text" in args) == ("document" in args):
            raise _RpcError(-32602, "give exactly one of text or document")
        if "text" in args:
            if not isinstance(args["text"], str):
                raise _RpcError(-32602, "text must be a string")
            return _tool_result(diagnose.diagnose_text(args["text"]))
        return _tool_result(diagnose.diagnose_text(json.dumps(args["document"])))
    if name == "construct_limits":
        asked = tiers.from_request(args["request"]) if isinstance(args.get("request"), str) else {}
        tier = args.get("tier") or asked.get("tier") or tiers.DEFAULT
        try:
            lim = tiers.limits(tier, **(args.get("overrides") or {}))
        except (tiers.TierError, TypeError) as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
        return _tool_result({"limits": lim, "mode": lim["mode"], "research": asked.get("research", "auto"),
                             "stop": "the review judges it genuinely good, or any limit is reached; then deliver the "
                                     "best version so far with authoring.next"})
    if name in ("construct_netlogo_instrument", "construct_netlogo_draw"):
        return _call_netlogo(name, args)
    if name == "construct_params_template":
        if "archetype" not in args:
            return _tool_result({"archetypes": {a: sorted(v) for a, v in params.VARIANTS.items()},
                                 "describe": params.describe()})
        try:
            return _tool_result(params.template(args["archetype"], args.get("variant")))
        except scene.SceneError as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
    doc = args["params"] if name == "construct_expand_params" else args["document"]
    if not isinstance(doc, dict):
        raise _RpcError(-32602, "the document must be an object")
    report = diagnose.diagnose_text(json.dumps(doc))
    if not report["ok"]:
        return _tool_result(report, is_error=True)
    built = params.expand(doc) if params.is_params(doc) else doc
    if name == "construct_expand_params":
        if not params.is_params(doc):
            raise _RpcError(-32602, "not a construct-params document")
        return _tool_result(built)
    if name == "construct_export":
        try:
            out, summary = export.render(built, args.get("format", "glb"), args.get("wire", "edges"),
                                         args.get("pose", "closed"), args.get("materials"), args.get("frame", "y-up"),
                                         merge=bool(args.get("merge", False)), colliders=bool(args.get("colliders", False)),
                                         pieces=bool(args.get("pieces", False)))
        except (export.ExportError, scene.SceneError) as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
        if "glb" in out:
            out = {"glb_base64": base64.b64encode(out["glb"]).decode("ascii")}
        return _tool_result({**out, "summary": summary})
    if name == "construct_print":
        from . import printing
        fmt = args.get("format", "3mf")
        try:
            if fmt not in printing.FORMATS:
                raise printing.PrintError("format: 3mf or stl")
            if args.get("compare_printers"):
                return _tool_result({"printers": printing.printers(built, lines=args.get("lines", "none"))})
            kw = {k: args[k] for k in ("size", "scale", "detail", "wall", "join", "fit", "exact") if k in args}
            if kw.get("exact") and fmt != "3mf":
                raise printing.PrintError("an exact print is 3MF (its solids are parts of one object)")
            if args.get("printer"):
                pr = printing.PRINTERS.get(args["printer"])
                if pr is None:
                    raise printing.PrintError("printer: one of " + ", ".join(printing.PRINTERS))
                kw = dict({"detail": pr["detail"], "wall": pr["wall"]}, bed=pr["bed"], coarsen=True, **kw)
            p = printing.make(built, lines=args.get("lines", "none"), **kw)
        except (printing.PrintError, scene.SceneError, TypeError) as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
        data = printing.to_3mf(p) if fmt == "3mf" else printing.to_stl(p)
        return _tool_result({fmt + "_base64": base64.b64encode(data).decode("ascii"), "report": p["report"],
                             "notes": printing.notes(p["report"])})
    return _tool_result(scene.compile_scene(built))


def _call_netlogo(name, args):
    from . import netlogo
    try:
        if name == "construct_netlogo_instrument":
            pat = args.get("patches")
            model, xml = netlogo.instrument(args["model"], args["title"], "run.jsonl", tuple(args.get("turtles", ())),
                                            tuple(args.get("reporters", ())),
                                            (pat["reporter"], pat.get("every", 1)) if pat else None, args.get("every", 1),
                                            args.get("seed"), args.get("ticks", 500), bool(args.get("skip_turtles")),
                                            args.get("setup"), args.get("go"))
            return _tool_result({"model": model, "experiment": xml, "recorder": netlogo.NLS.read_text(encoding="utf-8"),
                                 "save": {"model": "Model-construct.nlogox", "experiment": "construct-experiment.xml",
                                          "recorder": "construct.nls (beside the model)"},
                                 "next": "Run it in NetLogo (setup, go), or headless: NetLogo_Console --headless --model "
                                         "Model-construct.nlogox --setup-file construct-experiment.xml --experiment "
                                         "construct --threads 1. It writes run.jsonl; draw it with construct_netlogo_draw."})
        run = netlogo.parse_run(args["recording"])
        opts = {k: args[k] for k in ("state", "x", "z", "change", "time", "max_agents", "smooth", "levels", "resolution",
                                     "window", "landmarks", "colors") if k in args}
        sc = netlogo.scene_from_run(run, args["view"], args.get("title"), solid=bool(args.get("solid")), **opts)
        if "art" in args:
            sc = netlogo.apply_art(sc, args["art"])
        out = {"scene": sc, "data_lock": "intact" if netlogo.lock_problem(sc) is None else "broken"}
        if args.get("materials"):
            out["materials"] = netlogo.materials_from_run(run, sc)
        return _tool_result(out)
    except netlogo.NetLogoError as exc:
        return _tool_result({"error": str(exc)}, is_error=True)


def _handle(msg, state):
    if not isinstance(msg, dict):
        raise _RpcError(-32600, "invalid request")
    if msg.get("jsonrpc") != "2.0":
        raise _RpcError(-32600, "invalid JSON-RPC version")
    method = msg.get("method")
    msg_id = msg.get("id")
    is_notification = "id" not in msg
    if not isinstance(method, str):
        if is_notification:
            return None
        raise _RpcError(-32600, "invalid request")
    if not is_notification and not _valid_id(msg_id):
        raise _RpcError(-32600, "invalid id")

    if is_notification:
        return None
    if method == "initialize":
        if not isinstance(msg.get("params", {}), dict):
            raise _RpcError(-32602, "initialize params must be an object")
        state["initialized"] = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": product.NAME, "version": __version__},
        }
    if method == "notifications/initialized":
        return None
    if method.startswith("notifications/"):
        return None
    if not state.get("initialized"):
        raise _RpcError(-32600, "server not initialized")
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = msg.get("params")
        if not isinstance(params, dict):
            raise _RpcError(-32602, "params must be an object")
        name = params.get("name")
        if not isinstance(name, str):
            raise _RpcError(-32602, "missing tool name")
        return _call_tool(name, params.get("arguments", {}))
    raise _RpcError(-32601, "method not found")


def _emit(obj):
    data = json.dumps(obj, separators=(",", ":"))
    if len(data.encode("utf-8")) > MAX_RESPONSE_BYTES:
        data = json.dumps({
            "jsonrpc": "2.0",
            "id": obj.get("id"),
            "error": {"code": -32603, "message": "response too large: %.1f MB, the limit is %d MB. A print or a model this "
                      "large: make it smaller (size, scale, a coarser detail) or write it with the command line "
                      "(construct print / construct export), which has no limit" % (
                          len(data.encode("utf-8")) / 1048576.0, MAX_RESPONSE_BYTES // 1048576)},
        }, separators=(",", ":"))
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    state = {"initialized": False}
    while True:
        line = stdin.readline(MAX_REQUEST_BYTES + 2)
        if not line:
            break
        if len(line) > MAX_REQUEST_BYTES + 1 and not line.endswith("\n"):
            # consume remainder of overlong line
            while True:
                chunk = stdin.readline(MAX_REQUEST_BYTES + 2)
                if not chunk or chunk.endswith("\n"):
                    break
            _emit({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32600, "message": "request too large"}})
            continue
        if len(line.encode("utf-8")) > MAX_REQUEST_BYTES:
            _emit({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "request too large"}})
            continue
        stripped = line.strip()
        if not stripped:
            continue
        try:
            msg = json.loads(stripped, object_pairs_hook=hologram._reject_duplicate_keys, parse_constant=hologram._reject_constant)
        except (ValueError, hologram.SheetError, RecursionError):
            _emit({"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": "parse error"}})
            continue
        is_notification = isinstance(msg, dict) and "id" not in msg
        try:
            result = _handle(msg, state)
        except _RpcError as exc:
            if is_notification:
                continue
            _emit({"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) and _valid_id(msg.get("id")) else None,
                   "error": {"code": exc.code, "message": exc.message}})
            continue
        except Exception:
            if is_notification:
                continue
            _emit({"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) and _valid_id(msg.get("id")) else None,
                   "error": {"code": -32603, "message": "internal error"}})
            continue
        if is_notification:
            continue
        _emit({"jsonrpc": "2.0", "id": msg.get("id"), "result": result})


def main():
    serve()


if __name__ == "__main__":
    main()
