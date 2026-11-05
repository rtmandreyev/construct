"""Construct for Hermes: build constructs (animated, audited holographic models of real or invented things,
every part saying how it is known) with tools, and see them live in the chat.

The agent half registers the `construct_*` tools, the `construct` skill that teaches the craft, an optional
approval gate for the outside programs Construct runs (a headless browser, ffmpeg, FreeCAD, Blender), and
stops its background jobs when the plugin unloads. It also registers the /construct slash command. The Desktop half
(desktop/plugin.js) shows each built construct live in the chat (and glTF, STEP and kits in their own viewers), keeps
the Constructs page and the Learn page; its backend is dashboard/plugin_api.py.
"""

from pathlib import Path

from . import commands, jobs, netlogo_tools, runtime, schemas, stock, tools

HERE = Path(__file__).resolve().parent
SKILL = HERE / "skills" / "construct" / "SKILL.md"
SKILL_DESCRIPTION = ("Construct: research a thing and write one exact, checked description of it (named parts at real "
                     "sizes, how they fit, open and move, how each is known), then build from it with the construct_* "
                     "tools: a live hologram, glTF with joints, print, kit, CAD/STEP, films; edit by part id; NetLogo runs; "
                     "tutorials.")

# what each call runs outside Python, for the approval gate
BROWSER, FFMPEG, FREECAD, BLENDER, NETLOGO = "a headless browser", "ffmpeg", "FreeCAD", "Blender", "NetLogo (Java)"
COMMAND_PROGRAMS = {"review": [BROWSER], "video": [BROWSER, FFMPEG], "audio": [FFMPEG], "critique": [BROWSER],
                    "rounds": [BROWSER], "freecad": [FREECAD], "netlogo-film": [BLENDER]}


def programs_for(tool_name, args):
    """The outside programs a call would run (empty: none)."""
    args = args if isinstance(args, dict) else {}
    if tool_name == "construct_build":
        return [BROWSER] if args.get("thumbnail", True) is not False else []
    if tool_name == "construct_review":
        return [BROWSER]
    if tool_name == "construct_film":
        return [BROWSER, FFMPEG]
    if tool_name == "construct_export" and args.get("format") in ("fcstd", "step"):
        return [FREECAD]
    if tool_name == "construct_netlogo_run":
        return [NETLOGO, BROWSER] if args.get("model") is not None else []
    if tool_name == "construct_netlogo_draw":
        return [BROWSER]
    if tool_name == "construct_command":
        argv = args.get("argv") if isinstance(args.get("argv"), list) else []
        return list(COMMAND_PROGRAMS.get(argv[0], [])) if argv and isinstance(argv[0], str) else []
    return []


def make_gate(ctx):
    """A pre_tool_call hook: with `confirm_runs` on, a call that runs an outside program asks the user first.
    In an unattended run (cron) nobody can answer, so the call is refused with a reason instead."""
    def gate(tool_name=None, args=None, **kwargs):
        if not str(tool_name or "").startswith("construct_"):
            return None
        if not runtime.setting("confirm_runs", False):
            return None
        progs = programs_for(tool_name, args)
        if not progs:
            return None
        what = " and ".join(progs)
        try:
            unattended = ctx.current_cron_execution() is not None
        except Exception:
            unattended = False
        if unattended:
            return {"action": "block",
                    "message": "Construct asks before running %s (the plugin's 'Ask before running programs' setting), and "
                               "nobody can answer in a scheduled run. Turn that setting off to allow it." % what}
        return {"action": "approve", "message": "Construct wants to run %s on this machine (no network) for %s." % (
            what, tool_name), "rule_key": "construct:%s" % "+".join(p.split()[0 if p == NETLOGO else -1].lower() for p in progs)}
    return gate


def _event(name, payload):
    from hermes_cli.plugin_events import broadcast_plugin_event
    broadcast_plugin_event("construct", name, payload)


def register(ctx):
    runtime.configure(config=ctx.get_config)
    jobs.set_reporters(post=ctx.post_message, event=_event)
    tools.set_surface(ctx.session_surface)
    handlers = dict(tools.HANDLERS, **netlogo_tools.HANDLERS)
    checks = dict(netlogo_tools.CHECKS)
    for schema in schemas.TOOLS:
        ctx.register_tool(name=schema["name"], toolset="construct", schema=schema, handler=handlers[schema["name"]],
                          check_fn=checks.get(schema["name"], _runtime_present),
                          description=schema["description"].split(". ")[0])
    ctx.register_hook("pre_tool_call", make_gate(ctx))
    ctx.register_skill("construct", SKILL, description=SKILL_DESCRIPTION,
                       frontmatter={"metadata": {"hermes": {"requires_tools": ["construct_start", "construct_build"]}}})
    ctx.register_command("construct", _slash, description="Your constructs, the examples to start from, the tutorials, "
                         "background jobs; open one on the Constructs page",
                         args_hint="[open <project> | examples | learn [n] | jobs]")
    ctx.on_unload(jobs.stop_all)


def _slash(raw_args="", **kwargs):
    return commands.handle(raw_args, event=_event)


def _runtime_present():
    try:
        runtime.vendor_root()
        return True
    except runtime.ConstructError:
        return False
