"""Edit a scene by its part ids, one operation at a time (construct_edit). Pure Python on the scene's JSON: no
Construct import, so the tool and its tests can use it as well as the child, which validates each step with
Construct's own validator (child.py `edit`).

An operation is an object with `op` and its fields:

    move         part, by: [x, y, z] | to: [x, y, z]            metres, the part's `at`
    rotate       part, by: [rx, ry, rz] | to: [rx, ry, rz]      degrees, the part's `rotate`
    resize       part, size: [w, h, d]                          the shape's own `size`
                 part, factor: k | [kx, ky, kz]                 multiplies the part's `scale`
                 part, shape: {radius: .., height: ..}          sets the shape's own fields
    set          part, field: "look.weight", value              a field of the part (a dotted path inside it)
                 path: "subject.accuracy", value                a field of the scene (a dotted path; list indexes as numbers)
    unset        part, field | path                             removes it
    certainty    part, certainty: "inferred" | {size, shape}, basis?: [fact keys], source?: source id
    add_part     part: {id, role, shape, certainty, stage, ...}, after?: part id
    remove_part  part                                           and its id from joints and identity features
    add_fact     fact: {key, value, unit?, certainty, source?}
    set_fact     key, and any of value, unit, certainty, source, note
    remove_fact  key                                            and from the parts' basis lists
    add_source   source: {id, kind, title, ...}

`part` is a part id or a pattern (`door-*`, `wheel-?`), or `parts` a list of them; a pattern must match at least one
part. Each operation returns its changes as {"part", "field", "before", "after"}.
"""

import copy
import fnmatch
import json
import re

OPS = ("move", "rotate", "resize", "set", "unset", "certainty", "add_part", "remove_part", "add_fact", "set_fact",
       "remove_fact", "add_source")
MAX_OPS = 100
SEGMENT = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]{0,63}|[0-9]{1,5})$")
PART_CERTAINTIES = ("verified", "user_supplied", "traced", "inferred", "decorative")
FACT_FIELDS = ("value", "unit", "certainty", "source", "note")


class EditError(Exception):
    """An operation that cannot be applied; the message says why, for the model."""


def _vec(v, name, n=3):
    if not isinstance(v, list) or len(v) != n or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in v):
        raise EditError("%s must be a list of %d numbers" % (name, n))
    return [float(x) for x in v]


def _round(v):
    return [round(x, 6) for x in v]


def _parts(doc):
    parts = doc.get("parts")
    if not isinstance(parts, list):
        raise EditError("this document has no parts (a parameter document: use set with a path instead)")
    return parts


def _match(doc, op):
    """The parts an operation names: `part` (an id or a pattern) or `parts` (a list of them)."""
    names = op.get("parts") if op.get("parts") is not None else [op.get("part")]
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n or len(n) > 120 for n in names):
        raise EditError("name the part by id (part) or several (parts: a list of ids or patterns such as door-*)")
    parts, out = _parts(doc), []
    for name in names:
        hit = [p for p in parts if isinstance(p, dict) and (p.get("id") == name or (
            any(c in name for c in "*?[") and fnmatch.fnmatchcase(str(p.get("id")), name)))]
        if not hit:
            near = sorted(str(p.get("id")) for p in parts if isinstance(p, dict) and str(p.get("id", "")).startswith(name[:3]))[:8]
            raise EditError("no part %r%s" % (name, (" (near: %s)" % ", ".join(near)) if near else ""))
        out += [p for p in hit if p not in out]
    return out


def _segments(path):
    if not isinstance(path, str) or not path or len(path) > 200:
        raise EditError("a path is dotted names, e.g. subject.accuracy or look.weight")
    segs = path.split(".")
    if any(not SEGMENT.match(s) for s in segs):
        raise EditError("path %r: each step is a name (letters, digits, _) or a list index" % path)
    return segs


def _walk(root, segs, create):
    """The container holding the last segment, creating dicts on the way when `create`."""
    cur = root
    for s in segs[:-1]:
        if isinstance(cur, list):
            if not s.isdigit() or int(s) >= len(cur):
                raise EditError("no item %s in a list of %d" % (s, len(cur)))
            cur = cur[int(s)]
        elif isinstance(cur, dict):
            if s not in cur:
                if not create:
                    raise EditError("nothing at %s" % s)
                cur[s] = {}
            cur = cur[s]
        else:
            raise EditError("%s is not an object or a list" % s)
    return cur


def _get(root, segs):
    try:
        box = _walk(root, segs, False)
    except EditError:
        return None
    last = segs[-1]
    if isinstance(box, list):
        return box[int(last)] if last.isdigit() and int(last) < len(box) else None
    return box.get(last) if isinstance(box, dict) else None


def _set(root, segs, value):
    box = _walk(root, segs, True)
    last = segs[-1]
    if isinstance(box, list):
        if not last.isdigit() or int(last) > len(box):
            raise EditError("list index %s out of range (%d items)" % (last, len(box)))
        if int(last) == len(box):
            box.append(value)
        else:
            box[int(last)] = value
    elif isinstance(box, dict):
        box[last] = value
    else:
        raise EditError("cannot set %s inside a value" % last)


def _unset(root, segs):
    box = _walk(root, segs, False)
    last = segs[-1]
    if isinstance(box, list) and last.isdigit() and int(last) < len(box):
        del box[int(last)]
    elif isinstance(box, dict) and last in box:
        del box[last]
    else:
        raise EditError("nothing to remove at %s" % ".".join(segs))


def unsafe(value, key=""):
    """Why a value may not go into a scene (a path that leaves the project, a URL to fetch, a script), or None."""
    if isinstance(value, dict):
        for k, v in value.items():
            why = unsafe(v, k)
            if why:
                return why
        return None
    if isinstance(value, list):
        for v in value:
            why = unsafe(v, key)
            if why:
                return why
        return None
    if isinstance(value, str):
        low = value.strip().lower()
        if re.search(r"<\s*script|javascript:", low):
            return "a script in a text field"
        if key in ("path", "file", "src", "href", "image", "sprite_path"):
            if "://" in low or low.startswith(("/", "~", "\\")) or re.match(r"^[a-z]:[\\/]", low) or \
                    ".." in re.split(r"[\\/]", value):
                return "the path %r leaves the project folder (give a path relative to the scene, inside it)" % value
    return None


def _clean(value, key=""):
    why = unsafe(value, key)
    if why:
        raise EditError("refused: %s" % why)
    try:
        text = json.dumps(value)
    except (TypeError, ValueError):
        raise EditError("the value is not JSON")
    if len(text) > 200000:
        raise EditError("the value is too large (%d characters)" % len(text))
    return copy.deepcopy(value)


def brief(value, n=240):
    """A value as the diff shows it: whole when short, else its size."""
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= n:
        return value
    return "<%s, %d characters>" % (type(value).__name__, len(text))


def _change(part, field, before, after):
    return {"part": part, "field": field, "before": brief(before), "after": brief(after)}


def apply(doc, op):
    """Apply one operation to `doc` in place; its changes. Raises EditError when it cannot be applied."""
    if not isinstance(op, dict) or op.get("op") not in OPS:
        raise EditError("each operation is an object with op: one of %s" % ", ".join(OPS))
    kind = op["op"]
    changes = []
    if kind in ("move", "rotate"):
        key = "at" if kind == "move" else "rotate"
        if ("by" in op) == ("to" in op):
            raise EditError("%s takes by or to (a list of three numbers)" % kind)
        for p in _match(doc, op):
            before = p.get(key)
            base = _vec(before, key) if before is not None else [0.0, 0.0, 0.0]
            new = [a + b for a, b in zip(base, _vec(op["by"], "by"))] if "by" in op else _vec(op["to"], "to")
            p[key] = _round(new)
            changes.append(_change(p.get("id"), key, before, p[key]))
    elif kind == "resize":
        given = [k for k in ("size", "factor", "shape") if k in op]
        if len(given) != 1:
            raise EditError("resize takes one of size (the shape's size), factor (multiplies the part's scale) or shape "
                            "(the shape's own fields)")
        for p in _match(doc, op):
            shape = p.get("shape") if isinstance(p.get("shape"), dict) else {}
            if "size" in op:
                if not isinstance(shape.get("size"), list):
                    raise EditError("%s is a %s without a size list: use shape (its own fields, e.g. radius) or factor"
                                    % (p.get("id"), shape.get("type")))
                new = _round(_vec(op["size"], "size", len(shape["size"])))
                changes.append(_change(p.get("id"), "shape.size", shape["size"], new))
                shape["size"] = new
            elif "factor" in op:
                f = op["factor"]
                f = [float(f)] * 3 if isinstance(f, (int, float)) and not isinstance(f, bool) else _vec(f, "factor")
                if any(x <= 0 for x in f):
                    raise EditError("factor must be positive")
                before = p.get("scale")
                old = [float(before)] * 3 if isinstance(before, (int, float)) else (_vec(before, "scale") if before else [1.0] * 3)
                new = _round([a * b for a, b in zip(old, f)])
                p["scale"] = new[0] if len(set(new)) == 1 else new
                changes.append(_change(p.get("id"), "scale", before, p["scale"]))
            else:
                fields = op["shape"]
                if not isinstance(fields, dict) or not fields or "type" in fields:
                    raise EditError("shape is an object of the shape's own fields (not its type), e.g. {\"radius\": 0.02}")
                for k, v in fields.items():
                    _segments(k)
                    changes.append(_change(p.get("id"), "shape." + k, shape.get(k), v))
                    shape[k] = _clean(v, k)
    elif kind in ("set", "unset"):
        if "part" in op or "parts" in op:
            segs = _segments(op.get("field"))
            if segs[0] == "id":
                raise EditError("a part's id is how everything else finds it: add a new part and remove the old one")
            targets = [(p, p.get("id")) for p in _match(doc, op)]
        elif "path" in op:
            segs = _segments(op["path"])
            if segs[0] in ("parts",):
                raise EditError("change parts by id: set with part and field")
            if segs[0] in ("format", "version"):
                raise EditError("the document's format and version are Construct's, not edited")
            targets = [(doc, None)]
        else:
            raise EditError("%s takes part + field, or path" % kind)
        if kind == "set" and "value" not in op:
            raise EditError("set needs a value")
        for root, pid in targets:
            name = ".".join(segs)
            before = _get(root, segs)
            if kind == "set":
                _set(root, segs, _clean(op["value"], segs[-1]))
                changes.append(_change(pid, name if pid else "/" + name, before, op["value"]))
            else:
                _unset(root, segs)
                changes.append(_change(pid, name if pid else "/" + name, before, None))
    elif kind == "certainty":
        cert = op.get("certainty")
        if isinstance(cert, dict):
            if set(cert) != {"size", "shape"} or any(v not in PART_CERTAINTIES for v in cert.values()):
                raise EditError("certainty as an object is {\"size\": .., \"shape\": ..}, each one of %s" %
                                ", ".join(PART_CERTAINTIES))
        elif cert not in PART_CERTAINTIES:
            raise EditError("certainty is one of %s, or {\"size\": .., \"shape\": ..}" % ", ".join(PART_CERTAINTIES))
        basis = op.get("basis")
        if basis is not None and (not isinstance(basis, list) or any(not isinstance(b, str) for b in basis)):
            raise EditError("basis is a list of fact keys")
        for p in _match(doc, op):
            changes.append(_change(p.get("id"), "certainty", p.get("certainty"), cert))
            p["certainty"] = copy.deepcopy(cert)
            if basis is not None:
                changes.append(_change(p.get("id"), "basis", p.get("basis"), basis))
                p["basis"] = list(basis)
            if "source" in op:
                changes.append(_change(p.get("id"), "source", p.get("source"), op["source"]))
                if op["source"] is None:
                    p.pop("source", None)
                else:
                    p["source"] = _clean(op["source"])
    elif kind == "add_part":
        part = op.get("part")
        if not isinstance(part, dict) or not isinstance(part.get("id"), str):
            raise EditError("add_part takes part: the new part as an object with its id, role, shape, certainty, stage")
        parts = _parts(doc)
        if any(isinstance(p, dict) and p.get("id") == part["id"] for p in parts):
            raise EditError("a part %r exists already: change it, or give the new one another id" % part["id"])
        at = len(parts)
        if op.get("after") is not None:
            ids = [p.get("id") if isinstance(p, dict) else None for p in parts]
            if op["after"] not in ids:
                raise EditError("no part %r to add after" % op["after"])
            at = ids.index(op["after"]) + 1
        parts.insert(at, _clean(part))
        changes.append(_change(part["id"], "", None, part))
    elif kind == "remove_part":
        gone = [p.get("id") for p in _match(doc, op)]
        doc["parts"] = [p for p in _parts(doc) if not (isinstance(p, dict) and p.get("id") in gone)]
        for pid in gone:
            changes.append(_change(pid, "", "part", None))
        for a in doc.get("articulations") or []:
            if isinstance(a, dict) and isinstance(a.get("parts"), list) and set(a["parts"]) & set(gone):
                before = list(a["parts"])
                a["parts"] = [x for x in a["parts"] if x not in gone]
                changes.append(_change(None, "articulations[%s].parts" % a.get("id"), before, a["parts"]))
        ident = (doc.get("authoring") or {}).get("identity") if isinstance(doc.get("authoring"), dict) else None
        for f in ident or []:
            if isinstance(f, dict) and isinstance(f.get("parts"), list) and set(f["parts"]) & set(gone):
                before = list(f["parts"])
                f["parts"] = [x for x in f["parts"] if x not in gone]
                changes.append(_change(None, "authoring.identity[%s].parts" % f.get("feature", "")[:40], before, f["parts"]))
    elif kind == "add_fact":
        fact = op.get("fact")
        if not isinstance(fact, dict) or not isinstance(fact.get("key"), str):
            raise EditError("add_fact takes fact: {key, value, unit?, certainty, source?}")
        facts = doc.setdefault("facts", [])
        if any(isinstance(f, dict) and f.get("key") == fact["key"] for f in facts):
            raise EditError("a fact %r exists already: use set_fact" % fact["key"])
        facts.append(_clean(fact))
        changes.append(_change(None, "facts[%s]" % fact["key"], None, fact))
    elif kind in ("set_fact", "remove_fact"):
        key = op.get("key")
        facts = doc.get("facts") or []
        hit = [f for f in facts if isinstance(f, dict) and f.get("key") == key]
        if not hit:
            raise EditError("no fact %r (facts: %s)" % (key, ", ".join(str(f.get("key")) for f in facts[:30]
                                                                         if isinstance(f, dict))))
        if kind == "set_fact":
            given = [k for k in FACT_FIELDS if k in op]
            if not given:
                raise EditError("set_fact takes any of %s" % ", ".join(FACT_FIELDS))
            for k in given:
                changes.append(_change(None, "facts[%s].%s" % (key, k), hit[0].get(k), op[k]))
                if op[k] is None:
                    hit[0].pop(k, None)
                else:
                    hit[0][k] = _clean(op[k], k)
        else:
            doc["facts"] = [f for f in facts if f not in hit]
            changes.append(_change(None, "facts[%s]" % key, hit[0], None))
            for p in doc.get("parts") or []:
                if isinstance(p, dict) and isinstance(p.get("basis"), list) and key in p["basis"]:
                    before = list(p["basis"])
                    p["basis"] = [b for b in p["basis"] if b != key]
                    changes.append(_change(p.get("id"), "basis", before, p["basis"]))
    elif kind == "add_source":
        src = op.get("source")
        if not isinstance(src, dict) or not isinstance(src.get("id"), str):
            raise EditError("add_source takes source: {id, kind, title, ref?, rights?}")
        sources = doc.setdefault("sources", [])
        if any(isinstance(s, dict) and s.get("id") == src["id"] for s in sources):
            raise EditError("a source %r exists already" % src["id"])
        sources.append(_clean(src))
        changes.append(_change(None, "sources[%s]" % src["id"], None, src))
    return changes


def check_ops(ops):
    if not isinstance(ops, list) or not ops:
        raise EditError("operations is a list of edits, e.g. [{\"op\": \"move\", \"part\": \"lid\", \"by\": [0, 0.01, 0]}]")
    if len(ops) > MAX_OPS:
        raise EditError("at most %d operations at a time" % MAX_OPS)
    for i, op in enumerate(ops):
        if not isinstance(op, dict) or op.get("op") not in OPS:
            raise EditError("operation %d: op must be one of %s" % (i + 1, ", ".join(OPS)))
    return ops
