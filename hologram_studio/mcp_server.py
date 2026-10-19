"""Minimal MCP stdio server exposing hologram tools.

Newline-delimited JSON-RPC 2.0 over stdin/stdout. Standard library only.
Never reads or writes files, never spawns processes, never fetches or renders.

Tools: the v0.1 construction sheets (hologram_template, hologram_validate, hologram_compile)
and the v2 scenes of contract tessera.hologram/0.2 (hologram_diagnose,
hologram_params_template, hologram_expand_params, hologram_compile_scene). Every tool works
only on the JSON in the request.
"""

import json
import sys

from . import diagnose, hologram, params, product, scene, __version__

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
_DOC = {"type": "object", "description": "a tessera-hologram scene (version 2) or a tessera-hologram-params document"}
TOOLS += [
    {"name": "hologram_diagnose",
     "description": "Check a v2 scene or parameter document (contract tessera.hologram/0.2): every problem with a "
                    "JSON path, a code and a fix hint, plus repair_text to send back to the model that wrote it. "
                    "Give `text` (the model's raw answer) or `document` (parsed JSON).",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "maxLength": MAX_REQUEST_BYTES},
                                                      "document": _DOC},
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "hologram_params_template",
     "description": "A parameter document to fill in for an archetype (case, book, object, vessel) and variant: the "
                    "simple path for models that struggle with full scenes. Without arguments: every archetype.",
     "inputSchema": {"type": "object", "properties": {"archetype": {"type": "string", "enum": sorted(params.VARIANTS)},
                                                      "variant": {"type": "string"}},
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "hologram_expand_params",
     "description": "The full v2 scene a valid parameter document builds (or its diagnostics when it is not valid).",
     "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}}, "required": ["params"],
                     "additionalProperties": False},
     "annotations": _READ_ONLY},
    {"name": "hologram_compile_scene",
     "description": "Compile a valid v2 scene or parameter document into tessera-hologram-geometry v2 (or return "
                    "its diagnostics). Artwork bytes are never read: slots carry asset ids and hashes only.",
     "inputSchema": {"type": "object", "properties": {"document": _DOC}, "required": ["document"],
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
    if name in V2_TOOLS:
        return _call_v2(name, args)
    raise _RpcError(-32602, "unknown tool")


V2_TOOLS = {"hologram_diagnose": ({"text", "document"}, set()), "hologram_params_template": ({"archetype", "variant"}, set()),
            "hologram_expand_params": ({"params"}, {"params"}), "hologram_compile_scene": ({"document"}, {"document"})}


def _call_v2(name, args):
    allowed, required = V2_TOOLS[name]
    if set(args) - allowed:
        raise _RpcError(-32602, "unknown arguments")
    if required - set(args):
        raise _RpcError(-32602, "missing " + ", ".join(sorted(required - set(args))))
    if name == "hologram_diagnose":
        if ("text" in args) == ("document" in args):
            raise _RpcError(-32602, "give exactly one of text or document")
        if "text" in args:
            if not isinstance(args["text"], str):
                raise _RpcError(-32602, "text must be a string")
            return _tool_result(diagnose.diagnose_text(args["text"]))
        return _tool_result(diagnose.diagnose_text(json.dumps(args["document"])))
    if name == "hologram_params_template":
        if "archetype" not in args:
            return _tool_result({"archetypes": {a: sorted(v) for a, v in params.VARIANTS.items()},
                                 "describe": params.describe()})
        try:
            return _tool_result(params.template(args["archetype"], args.get("variant")))
        except scene.SceneError as exc:
            return _tool_result({"error": str(exc)}, is_error=True)
    doc = args["params"] if name == "hologram_expand_params" else args["document"]
    if not isinstance(doc, dict):
        raise _RpcError(-32602, "the document must be an object")
    report = diagnose.diagnose_text(json.dumps(doc))
    if not report["ok"]:
        return _tool_result(report, is_error=True)
    built = params.expand(doc) if doc.get("format") == params.FORMAT else doc
    if name == "hologram_expand_params":
        if doc.get("format") != params.FORMAT:
            raise _RpcError(-32602, "not a tessera-hologram-params document")
        return _tool_result(built)
    return _tool_result(scene.compile_scene(built))


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
            "error": {"code": -32603, "message": "response too large"},
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
