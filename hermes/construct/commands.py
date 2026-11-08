"""The /construct slash command: what is there to open, start from and learn, in a few lines, on every surface.

    /construct                    the projects (newest first) and how to go on
    /construct open <project>     one project: its newest build, kits and files (Hermes Desktop opens it on the
                                  Constructs page)
    /construct examples           the constructs the plugin ships, to start from
    /construct learn [n]          the tutorials; with a number or name, the message that starts one
    /construct jobs               background work: films, NetLogo runs, long exports
    /construct worlds             your worlds and the worlds the plugin ships
    /construct arrange <world> <changes>   moves and turns made by hand on a world's page (the Desktop half sends
                                  these: a JSON list of {id, move, turn, pivot}); checked, saved and rebuilt
    /construct undo <world>       the world as it was before its last change
    /construct job <id>           one background job's state (an ended build is published here)
"""

from pathlib import Path

import json
import re

from . import jobs, runtime, world_tools

HELP = ("/construct: your constructs · /construct open <project> · /construct examples · /construct learn [n] · "
        "/construct jobs · /construct worlds · /construct undo <world>")


def _plugin_api():
    import importlib.util
    spec = importlib.util.spec_from_file_location("construct_plugin_api_for_command",
                                                  Path(__file__).resolve().parent / "dashboard" / "plugin_api.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _when(iso):
    return str(iso or "")[:16].replace("T", " ")


def handle(raw_args="", event=None, **kwargs):
    words = str(raw_args or "").split()
    verb = words[0].lower() if words else ""
    try:
        api = _plugin_api()
        root = runtime.data_dir()
        if verb in ("", "list", "projects"):
            rows = api.projects(root)
            if not rows:
                return "No constructs yet. Ask for one (\"make a construct of a lighthouse\"), or start from an example: " \
                       "/construct examples\n" + HELP
            lines = ["Constructs (%d), newest first:" % len(rows)]
            for r in rows[:20]:
                n = r.get("newest") or {}
                bits = [r["project"], "\"%s\"" % r["title"], _when(r.get("updated"))]
                if n.get("parts"):
                    bits.append("%d parts" % n["parts"])
                more = ["%d build%s" % (len(r["builds"]), "" if len(r["builds"]) == 1 else "s")] if r["builds"] else []
                more += ["%d kit%s" % (len(r["kits"]), "" if len(r["kits"]) == 1 else "s")] if r["kits"] else []
                more += ["%d file%s" % (len(r["items"]), "" if len(r["items"]) == 1 else "s")] if r["items"] else []
                if r.get("changed_since"):
                    more.append("scene changed since the last build")
                lines.append("  " + " · ".join(bits) + ("  (" + ", ".join(more) + ")" if more else ""))
            lines.append(HELP)
            return "\n".join(lines)
        if verb == "open":
            if len(words) < 2:
                return "Which one? /construct open <project> (the names /construct lists)"
            name = words[1].lower()
            try:
                r = api.project(root, name)
            except api.NotFound:
                near = [p["project"] for p in api.projects(root) if name in p["project"]][:6]
                return "No project %r.%s" % (name, (" Did you mean: " + ", ".join(near)) if near else "")
            if event is not None:
                try:
                    event("open", {"project": name})
                except Exception:   # no Desktop listening: the text below still answers
                    pass
            lines = ["%s (\"%s\"), last changed %s%s" % (name, r["title"], _when(r.get("updated")),
                                                        "; the scene changed since its newest build" if r.get("changed_since") else "")]
            n = r.get("newest")
            if n:
                lines.append("  newest build %s: %s parts; page: %s" % (n["build"], n.get("parts"), n.get("page")))
            for k in r["kits"][:3]:
                lines.append("  kit %s: %s pieces on %s plates, booklet: %s" % (k["kit"], k.get("pieces"), k.get("plates"),
                                                                              k.get("booklet")))
            for i in r["items"][:10]:
                lines.append("  %s %s: %s%s" % (i["kind"], i["name"], i.get("path"), (" (" + i["summary"] + ")") if i.get("summary") else ""))
            lines.append("In Hermes Desktop it opens on the Constructs page; ask \"show the construct %s\" to see it in the chat." % name)
            return "\n".join(lines)
        if verb in ("examples", "start"):
            lines = ["Constructs to start from (ask \"start from <name>\" or \"show me <name>\"):"]
            for e in runtime.catalog():
                lines.append("  %s · %s · %d parts%s" % (e["name"], e["title"], e["parts"],
                                                         (" · " + e["use"]) if e.get("use") else ""))
            return "\n".join(lines)
        if verb in ("learn", "tutorials", "tutorial"):
            rows = api.tutorials(Path(__file__).resolve().parent)
            if len(words) > 1:
                key = words[1].lower()
                pick = next((t for t in rows if key == str(t["order"]) or key == "%02d" % t["order"] or key == t["id"]), None)
                if not pick:
                    return "No tutorial %r: /construct learn lists them" % key
                return "%s\nSend this to start it:\n\n%s" % (pick["title"], pick["prompt"])
            lines = ["Tutorials (/construct learn <number> gives the message that starts one):"]
            group = None
            for t in rows:
                if t["group"] != group:
                    group = t["group"]
                    lines.append(group + ":")
                lines.append("  %2d  %s: %s%s" % (t["order"], t["title"], t["summary"],
                                                  " (placeholder)" if t["status"] == "placeholder" else ""))
            return "\n".join(lines)
        if verb == "worlds":
            mine = [r for r in api.projects(root) if r.get("world")]
            lines = ["Your worlds (%d):" % len(mine) if mine else "No worlds yet: ask for one, or start from an example."]
            for r in mine[:20]:
                n = r.get("newest") or {}
                lines.append("  %s \"%s\"%s" % (r["project"], r["title"], " · %d constructs" % n["placements"] if n.get("placements") else ""))
            lines.append("Worlds to start from (ask \"start the world <name>\"):")
            for name, w in sorted(runtime.example_worlds().items()):
                lines.append("  %s · %s" % (name, w["title"]))
            return "\n".join(lines)
        if verb == "arrange":
            parts = str(raw_args or "").strip().split(None, 2)
            if len(parts) < 3:
                return "Usage: /construct arrange <world> <changes: a JSON list of {id, move, turn, pivot}>"
            try:
                changes = json.loads(parts[2])
            except ValueError:
                return "Construct could not read those changes (a JSON list of {id, move, turn, pivot})."
            r = world_tools.arrange_by_hand(parts[1].lower(), changes)
            warn = r.get("warnings") or []
            return ("Arranged %s by hand: %s. Rebuilding (build %s, job %s)%s" % (r["world"], ", ".join(r["moved"]), r["build"], r["job_id"],
                    (". The check says: " + "; ".join(warn[:4])) if warn else "; the check found nothing in the way."))
        if verb == "undo":
            if len(words) < 2:
                return "Which world? /construct undo <world>"
            r = world_tools.undo(words[1].lower())
            return "Undid the last change to %s (%s %s). Rebuilding (build %s, job %s)." % (r["world"], r["undid"], r["placement"], r["build"], r["job_id"])
        if verb == "job":   # one job's state; an ended job's result is made here (a build is published)
            jid = words[1] if len(words) > 1 else ""
            if not re.match(r"^[0-9a-f]{12}$", jid):
                return "Which job? /construct job <id> (/construct jobs lists them)"
            st = jobs.status(jid)
            if st.get("state") == "running":
                prog = st.get("progress") or {}
                return "Job %s is running%s." % (jid, " (%s%%)" % prog["percent"] if prog.get("percent") is not None else "")
            return "Job %s %s%s." % (jid, {"done": "finished", "warned": "finished, with problems to fix"}.get(st.get("state"), "failed"),
                                     " (build %s)" % st["build"] if st.get("build") else (": " + str(st.get("error"))[:300] if st.get("error") else ""))
        if verb == "jobs":
            rows = jobs.recent()
            if not rows:
                return "No background work."
            return "\n".join(["Background work, newest first:"] + ["  %s %s: %s" % (j["job_id"], j["label"], j["state"])
                                                                   for j in rows])
        return HELP
    except Exception as exc:   # a command must answer, never raise into the gateway
        return "Construct could not answer that: %s: %s" % (type(exc).__name__, exc)
