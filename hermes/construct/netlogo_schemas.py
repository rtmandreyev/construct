"""The NetLogo tools' JSON schemas (see netlogo_tools.py)."""

VIEWS = ["auto", "space-time", "network-time", "phase", "field", "pulse"]


def _tool(name, description, properties, required=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}


# how a run is drawn: Construct's `netlogo` options, for one run or for runs compared
_DRAW = {
    "view": {"type": "string", "enum": VIEWS,
             "description": "How the run is drawn (time is height): auto (default; the view the data suits), space-time "
                            "(moving agents' tracks), network-time (spreading on a network: each turtle rises to the "
                            "tick its state turned true), phase (two counts in a cycle), field (change spreading over "
                            "patches), pulse (turtles switching a state on and off)."},
    "title": {"type": "string", "maxLength": 120, "description": "The construct's title (default: the model's name)."},
    "options": {
        "type": "object", "additionalProperties": False,
        "description": "Construct's drawing options; leave out what you do not need.",
        "properties": {
            "state": {"type": "string", "description": "network-time: the turtle variable whose turning true lifts a "
                                                       "node; pulse: the true/false variable that switches (hidden? too)."},
            "x": {"type": "string", "description": "phase: the reporter across the floor (default the first recorded)."},
            "z": {"type": "string", "description": "phase: the reporter front to back (default the second)."},
            "smooth": {"type": "integer", "minimum": 2, "maximum": 500,
                       "description": "phase: a centred moving average over this many records."},
            "window": {"type": "string", "description": "space-time and pulse: auto (default: where the order formed), "
                                                        "whole, or the tick to end at (e.g. \"800\")."},
            "time": {"type": "string", "enum": ["linear", "sqrt"],
                     "description": "Height from ticks: linear (default) or sqrt, for a run whose changes come early."},
            "change": {"type": "string", "enum": ["first", "last"],
                       "description": "field: lift each patch to its first (default) or last change."},
            "levels": {"type": "integer", "minimum": 2, "maximum": 128, "description": "field: fronts drawn (default 32)."},
            "resolution": {"type": "integer", "minimum": 8, "maximum": 256,
                           "description": "field: blocks across the world (default 64)."},
            "max_agents": {"type": "integer", "minimum": 1, "maximum": 1000,
                           "description": "space-time: at most this many turtles (default 150)."},
            "landmarks": {"type": "string", "enum": ["on", "off"],
                          "description": "Mark the moments worth marking from the first count (default on)."},
            "colors": {"type": "string", "enum": ["run", "house"],
                       "description": "run (default): the run's own NetLogo colours; house: Construct's tones."},
        },
    },
    "model_3d": {"type": "boolean",
                 "description": "Also solids and a 3D model of the run (.glb in the run's colours, with the build as an "
                                "animation; a material map beside the scene for construct_export). One run only."},
}

RUN = _tool(
    "construct_netlogo_run",
    "Run a NetLogo model headless on this machine and draw the run as a construct, shown live in the chat. Use it when "
    "the user wants to run, simulate or see a NetLogo model (their own .nlogox, or one from their installed NetLogo "
    "Models Library by name, e.g. Flocking, Fireflies, Virus on a Network, Wolf Sheep Predation). It instruments a copy "
    "of the model, runs setup and go (the model's own buttons unless you name the commands) until the model stops or "
    "the tick limit, records what is worth recording (or what you name), then draws it (view auto by default) into a "
    "construct project: scene.json, the recording run.jsonl and counts.csv, so construct_check, construct_inspect, "
    "construct_review, construct_export and construct_command (netlogo-plates, netlogo-film) work on it as on any "
    "project. runs > 1 repeats the model with seeds seed, seed+1, ... (BehaviorSpace style) and draws up to eight of "
    "them side by side, with a summary of every recorded count's final value across all runs (min, median, max). "
    "It is a background job: a short run answers with the construct; a longer one answers with a live preview that "
    "grows as the run goes and a job_id (construct_job gives the final construct). Call it with only `search` to find "
    "models in the installed library. Library models are CC BY-NC-SA: the project carries their credit and licence; "
    "say so when you show it.",
    dict({
        "model": {"type": "string", "description": "The model: an absolute path to a .nlogox file, or a model's name in "
                                                   "the installed NetLogo Models Library (e.g. \"Flocking\")."},
        "search": {"type": "string", "maxLength": 80,
                   "description": "Instead of running: list the installed library's models whose name or folder matches "
                                  "these words (empty string: where NetLogo and its library are)."},
        "runs": {"type": "integer", "minimum": 1, "maximum": 100,
                 "description": "How many runs, each with its own seed (default 1). More than one: a comparison and a "
                                "summary across runs."},
        "seed": {"type": "integer", "minimum": 0, "maximum": 2000000000,
                 "description": "The random seed (of the first run); default a fresh one, recorded with the run."},
        "ticks": {"type": "integer", "minimum": 1, "maximum": 100000,
                  "description": "Tick limit (default 1000); a model that stops by itself ends sooner."},
        "setup": {"type": "string", "maxLength": 400,
                  "description": "The setup command, when not the model's own (e.g. \"setup-random\" or \"setup 4\")."},
        "go": {"type": "string", "maxLength": 400, "description": "The go command, when not the model's own forever "
                                                                  "button (e.g. \"go-once\")."},
        "constants": {"type": "object",
                      "description": "The model's settings for the run(s), by its sliders', switches' and choosers' "
                                     "variable names, e.g. {\"number\": 300, \"strategy\": \"phase advance\"}. The result "
                                     "lists the model's settings."},
        "turtles": {"type": "array", "items": {"type": "string"}, "maxItems": 12,
                    "description": "Turtle variables or reporters to record per turtle (e.g. [\"infected?\"]). Leave "
                                   "turtles, reporters and patches out for Construct's own choice."},
        "reporters": {"type": "array", "items": {"type": "string"}, "maxItems": 12,
                      "description": "Observer reporters to record each tick (e.g. [\"count sheep\", \"count wolves\"])."},
        "patches": {"type": "string", "maxLength": 200,
                    "description": "A patch reporter and how often, as REPORTER:EVERY (e.g. \"pcolor:4\")."},
        "no_turtles": {"type": "boolean", "description": "Record no turtles (counts or patches only: much smaller)."},
        "every": {"type": "integer", "minimum": 1, "maximum": 1000, "description": "Record every N ticks (default 1)."},
        "live": {"type": "boolean", "description": "A single run: show its construct growing while it runs (default "
                                                   "true; previews only for small runs)."},
    }, **_DRAW))

DRAW = _tool(
    "construct_netlogo_draw",
    "Draw NetLogo runs that are already recorded (run.jsonl files written by Construct's recorder or its NetLogo "
    "extension) as a construct, shown live in the chat; no NetLogo needed. One recording: a construct of the run. Two "
    "to eight: the runs side by side on one time scale under one data lock (a slider moved, other seeds). Or give a "
    "project made by construct_netlogo_run to draw its recording(s) again with another view or options. Makes a "
    "project (scene.json and the recordings) that every other construct_* tool works on. For printed plates of a run "
    "use construct_command [\"netlogo-plates\", \"run.jsonl\", \"--out\", \"plates\"]; for a Blender film "
    "[\"netlogo-film\", \"run.jsonl\", \"--out\", \"film.mp4\"] (in the run's project).",
    dict({
        "recordings": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8,
                       "description": "Absolute paths of the recordings (.jsonl), left to right."},
        "project": {"type": "string", "description": "Instead of recordings: a project construct_netlogo_run made; its "
                                                     "recording(s) are drawn again into it."},
        "labels": {"type": "array", "items": {"type": "string", "maxLength": 40}, "maxItems": 8,
                   "description": "Runs compared: their names, left to right (default A, B, C... or their seeds)."},
        "art": {"type": "string", "description": "One recording: an art-direction layer (art.json, absolute path or in "
                                                 "the project) applied on top of the data (docs/NETLOGO.md)."},
    }, **_DRAW))

TOOLS = [RUN, DRAW]
