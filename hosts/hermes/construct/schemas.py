"""The tools' JSON schemas, as the model sees them."""

from .netlogo_schemas import TOOLS as NETLOGO_TOOLS

WAIT_MAX = 380   # seconds a call may wait: Hermes stops a tool call at 420 s
ARCHETYPES = ["book", "case", "object", "vehicle", "vessel"]
CATEGORIES = ["architecture", "book", "cd", "machine", "object", "organism"]
PALETTES = ["violet", "cyan", "amber", "green", "ice", "rose"]
IDENTITIES = ["none", "warm-wood", "stone", "steel", "brass", "bio", "ember", "ice", "paper"]
SHEETS = ["assembly", "views", "life", "motion", "provenance"]
REVIEW_IMAGES = ["hero", "sheet-views", "sheet-assembly", "sheet-life", "sheet-motion", "sheet-provenance", "view-open",
                 "solid", "still-reduced-motion"]

_TARGET = {
    "project": {"type": "string", "description": "The project id construct_start returned (its scene is used)."},
    "scene": {"type": "string", "description": "Instead of (or with) a project: a scene or parameter document by path. "
                                               "Relative paths are inside the project; an absolute path may be anywhere "
                                               "the user named. Outputs always go to the project folder."},
}
_LOOK = {
    "palette": {"type": "string", "enum": PALETTES, "description": "Only when the user chose a colour; the default is "
                                                                   "the house palette."},
    "identity": {"type": "string", "enum": IDENTITIES, "description": "Only when the user chose an identity tint."},
}


def _tool(name, description, properties, required=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}


START = _tool(
    "construct_start",
    "Start a construct project: a new folder holding scene.json, from ONE of: a finished construct the plugin ships "
    "(example: a car, a bus, a scooter, a chair, a radio and its knob, a tape recorder, a piano, a clock, a shed before "
    "and after a planned change, a chapel, a cathedral, a castle, an invented spaceship; to show what Construct makes, "
    "or to start from the nearest one), an archetype's parameter document (the simple path for a CD case, book, guitar, "
    "bass, synth, car, bottle, can or glass), a category starter scene (the full loop for anything else), or an "
    "existing scene the user named (copied with its artwork). Then change the scene with construct_edit (or your file "
    "tools for a large rewrite) and run construct_check. Called with no source, it lists the shipped constructs (name, "
    "title, parts, one line each), the archetypes and their variants, the categories, and which outside programs "
    "(browser, ffmpeg, FreeCAD, Blender) are available.",
    {
        "title": {"type": "string", "maxLength": 120, "description": "The construct's title; also names the project."},
        "for_world": {"type": "string", "maxLength": 120, "description": "Building a piece of a world: the world's name or "
                                                                          "id, so the piece is kept with that world."},
        "archetype": {"type": "string", "enum": ARCHETYPES,
                      "description": "Parameter document for an archetype (with variant): case (jewel, slim, digipak, box), "
                                     "book (hardcover, paperback), object (electric-guitar, acoustic-guitar, bass-guitar, "
                                     "synth), vehicle (wedge, coupe, sedan), vessel (bottle, can, glass)."},
        "variant": {"type": "string", "description": "The archetype's variant, e.g. jewel or electric-guitar."},
        "seed": {"type": "integer", "description": "With an archetype: a seeded variant with sizes drawn near the standard."},
        "category": {"type": "string", "enum": CATEGORIES, "description": "A valid starter scene of this category to "
                                                                          "rewrite with the real thing."},
        "example": {"type": "string", "description": "A finished construct the plugin ships, by name (call with no source "
                                                     "to list them with their titles), e.g. volkswagen-t1-samba, "
                                                     "braun-sk4-knob, garden-shed, sainte-chapelle, kestrel-v2."},
        "from_path": {"type": "string", "description": "An existing scene or parameter document (absolute path) the user "
                                                       "gave you; it is copied into the new project."},
    })

EDIT = _tool(
    "construct_edit",
    "Change a scene safely, by part id, without writing scripts: a list of operations applied in order, each validated "
    "with Construct's own scene validation; the scene is replaced only when the edits add no new error (otherwise "
    "nothing is written and the result names the operation that broke it). Returns the diff (each change: part, field, "
    "before, after), the problems each step introduced or fixed, and a check summary (as construct_check). Use it for "
    "every scene change you can express this way instead of editing JSON in the terminal. Operations (op + fields): "
    "move {part, by|to: [x,y,z] m}; rotate {part, by|to: [rx,ry,rz] degrees}; resize {part, size: [w,h,d] | factor: "
    "k or [kx,ky,kz] | shape: {radius: ..}}; set {part, field: \"look.weight\", value} or {path: \"subject.accuracy\", "
    "value}; unset {part, field} or {path}; certainty {part, certainty: word or {size, shape}, basis?: [fact keys], "
    "source?}; add_part {part: {...}, after?}; remove_part {part} (also leaves its joints and identity features); "
    "add_fact {fact: {key, value, unit, certainty, source}}; set_fact {key, value?, unit?, certainty?, source?, note?}; "
    "remove_fact {key}; add_source {source: {id, kind, title, ref}}. part may be a pattern (door-*) or parts a list. "
    "Paths that leave the project, URLs and scripts are refused.",
    dict(_TARGET,
         operations={"type": "array", "minItems": 1, "maxItems": 100,
                     "items": {"type": "object", "properties": {"op": {"type": "string", "enum": [
                         "move", "rotate", "resize", "set", "unset", "certainty", "add_part", "remove_part", "add_fact",
                         "set_fact", "remove_fact", "add_source"]}}, "required": ["op"]},
                     "description": "The edits, in order, e.g. [{\"op\": \"move\", \"part\": \"lid\", \"by\": [0, 0.004, 0]}, "
                                    "{\"op\": \"certainty\", \"parts\": [\"wheel-*\"], \"certainty\": \"verified\", "
                                    "\"basis\": [\"wheel-diameter\"]}]."},
         dry_run={"type": "boolean", "description": "Validate and show the diff without writing (default false)."}),
    required=("operations",))

CHECK = _tool(
    "construct_check",
    "Validate, compile and audit a scene (construct check --json): ok, needs_repair, counts, and every diagnostic with "
    "its JSON path, code, message and fix hint, plus repair_text. While needs_repair is true, fix each diagnostic in the "
    "scene file and check again. fit=true also checks how the solids fit (slower: seconds to a minute): each finding "
    "names its parts (pokes: one part comes out through another; buried: a part hidden inside another) with where and a "
    "fix; fix the ones that show, then check again.",
    dict(_TARGET, fit={"type": "boolean", "description": "Also check the solids' fit (for export, print, kit)."},
         cells={"type": "integer", "minimum": 40, "maximum": 600,
                "description": "Fit resolution: voxels along the longest side (default 160)."}))

INSPECT = _tool(
    "construct_inspect",
    "What the construct's own record says is known, read deterministically from the scene (no model): title, subject "
    "and accuracy; parts grouped by certainty (verified, size_verified, shape_verified, supplied, traced, inferred, "
    "designed, decorative) with counts and key part names; the dimensions that are verified, supplied or inferred; "
    "every fact with its value, unit, certainty and source id; the sources (kind, title, reference); the articulations "
    "(type and travel); and the authoring record (mode, outcome, critic verdict, rounds, silhouette comparisons, what "
    "comes next). Use it to answer 'what is actually known about this?'.",
    dict(_TARGET))

BUILD = _tool(
    "construct_build",
    "Build the construct: the self-contained animated WebGL page (construct.html), its geometry and its audit, shown "
    "live in the chat. Returns the audit, the counts, the page's path, and media: put its MEDIA: line in your reply on "
    "a line of its own (Hermes Desktop shows the construct live from it; elsewhere it opens the page). A build that "
    "takes longer than about four minutes returns a job_id: follow it with construct_job.",
    dict(_TARGET, thumbnail={"type": "boolean", "description": "Also take a small still for the gallery when a "
                                                               "browser is available (default true)."}, **_LOOK))

REVIEW = _tool(
    "construct_review",
    "Build, then capture the review set in a headless browser: hero, contact sheets (assembly, views, life, motion, "
    "provenance), each of the scene's views (the open view opened), the solid and the reduced-motion still. Returns "
    "every image's path, and media: MEDIA: lines for the images to show (put them in your reply). Look at the images "
    "(vision) and judge them as an art director before improving the scene. Needs a Chromium-family browser.",
    dict(_TARGET,
         sheets={"type": "array", "items": {"type": "string", "enum": SHEETS},
                 "description": "Contact sheets to capture (default all five)."},
         size={"type": "string", "pattern": "^[0-9]{3,4}x[0-9]{3,4}$",
               "description": "Capture size WxH (default 1280x800; keep it modest, the images go into the conversation)."},
         show={"type": "array", "items": {"type": "string", "enum": REVIEW_IMAGES},
               "description": "Which images come back as MEDIA lines (default hero, sheet-views, sheet-assembly, view-open)."},
         **_LOOK))

EXPORT = _tool(
    "construct_export",
    "Export the construct as a file: glb or obj (a 3D model for Blender, game engines and the web: named parts, joints "
    "as the open animation, idle motion), fbx or usd/usdz (the same model carried over by Blender, when it is installed: "
    "FBX for Unity, Unreal, Maya; USD for Omniverse, Houdini, Apple's tools), stl or 3mf (one watertight solid to 3D print, checked), fcstd or step (named "
    "solids and joints in FreeCAD, and STEP; needs FreeCAD installed). Returns the file, Construct's report and a MEDIA: "
    "line to put in your reply. Long exports return a job_id: follow it with construct_job.",
    dict(_TARGET,
         format={"type": "string", "enum": ["glb", "obj", "fbx", "usd", "usdz", "stl", "3mf", "fcstd", "step"]},
         pieces={"type": "string", "enum": ["none", "glued", "loose"],
                 "description": "glb/obj physics: glued = what stays put is one body, each door or lid one more on its "
                                "hinge; loose = pieces that break apart and settle."},
         colliders={"type": "boolean", "description": "glb/obj: a box collider per part."},
         wire={"type": "string", "enum": ["edges", "tubes", "seams", "none"],
               "description": "glb/obj line art: edges (default), tubes (thin geometry), seams (design lines as dark "
                              "seams; with merge for a game prop) or none."},
         pose={"type": "string", "enum": ["closed", "open"], "description": "glb/obj: the pose it rests in."},
         merge={"type": "boolean", "description": "glb/obj: merge static parts per material (game engines)."},
         frame={"type": "string", "enum": ["y-up", "z-up"], "description": "obj only."},
         materials={"type": "object",
                    "description": "A material map: {\"materials\": [{\"parts\": [\"body\", \"door-*\"], \"color\": "
                                   "\"#2b4a6f\", \"finish\": \"paint\"}]} (finishes: paint, brushed, chrome, wood, rubber, "
                                   "plastic, glass, light). Only the user's choices; default: <scene>.materials.json beside "
                                   "the scene when there is one."},
         materials_path={"type": "string", "description": "Instead of materials: a material map file by path."},
         size_mm={"type": "number", "description": "stl/3mf: the longest side in mm (default 100)."},
         scale={"type": "number", "description": "stl/3mf: print at 1:N of the real size instead, e.g. 43."},
         printer={"type": "string", "enum": ["small", "desktop", "cube", "large", "resin"],
                  "description": "stl/3mf: a printer class (its bed, finest detail and thinnest wall)."},
         fit={"type": "boolean", "description": "stl/3mf: the largest print that stands on the printer's bed."},
         exact={"type": "boolean", "description": "3mf: keep the construct's own solids (finer than voxels)."},
         lines={"type": "string", "enum": ["none", "engrave", "raised"],
                "description": "stl/3mf: parts drawn only in lines: left out (none), cut in, or raised."},
         step={"type": "boolean", "description": "fcstd: also write STEP beside it."}),
    required=("format",))

FILM = _tool(
    "construct_film",
    "Render a film (MP4) of the construct assembling, in the background: it returns a job_id at once; follow it with "
    "construct_job (a film takes minutes; about an hour for four minutes of music, so say so first). With a music "
    "track, the build spans the track and moves with it (film mode). Needs a Chromium-family browser and ffmpeg.",
    dict(_TARGET,
         track={"type": "string", "description": "A music file (any format ffmpeg reads): measured, and laid under the film."},
         voice={"type": "string", "description": "With track: a vocal stem whose level drives the voice shimmer."},
         audio_features={"type": "string", "description": "Instead of track: features JSON from `construct audio`."},
         seconds={"type": "number", "minimum": 1, "maximum": 1800,
                  "description": "Length (default: the track's, else 12, or the assembly plus 3 s)."},
         assembly={"type": "number", "minimum": 1, "maximum": 1200,
                   "description": "The assembly lasts this long (default with a track: its length less 1.25 s)."},
         camera={"type": "string", "enum": ["tour", "steady", "still"],
                 "description": "steady keeps the whole construct in view (default with a track); tour plays the scene's "
                                "camera flights."},
         reactivity={"type": "number", "minimum": 0, "maximum": 2,
                     "description": "How strongly the music shows (calmer 0.5, stronger 1.5); only when asked."},
         size={"type": "string", "pattern": "^[0-9]{3,4}x[0-9]{3,4}$", "description": "WxH (default 1280x720)."},
         fps={"type": "integer", "minimum": 12, "maximum": 60, "description": "Frames per second (default 24)."},
         view={"type": "string", "description": "A view to film from (front, side, hero, or one of the scene's)."},
         **_LOOK))

JOB = _tool(
    "construct_job",
    "Status of a background Construct job (a film, a NetLogo run, or a build, review, export or command that outlasted "
    "its call): running with progress, or finished with its result and MEDIA: lines (put them in your reply), or failed "
    "with Construct's own message. wait_seconds waits for it here (returning as soon as it ends): use it instead of "
    "sleeping in a terminal. cancel=true stops it. Without job_id: the recent jobs.",
    {"job_id": {"type": "string", "description": "The job_id a construct tool returned."},
     "wait_seconds": {"type": "integer", "minimum": 1, "maximum": WAIT_MAX,
                      "description": "Wait up to this long for the job to end (at most %d s, under Hermes's tool "
                                     "deadline); it answers at once when the job ends sooner." % WAIT_MAX},
     "cancel": {"type": "boolean", "description": "Stop the job."}})

COMMAND = _tool(
    "construct_command",
    "Run one of Construct's other subcommands, for the long tail the other tools do not cover: loft-from-traces, "
    "compare, trace, terrain, globe, critique, rounds, kit, audio, params --list, expand, print --printers, netlogo, "
    "netlogo-instrument, netlogo-compare, netlogo-plates, netlogo-film, prompts. argv is the command line after "
    "`construct` (a list, no shell), run in the project folder, so relative paths are the project's; it may write only "
    "inside the project or the plugin's data folder. Commands that call a model over the network (author, trace-image, "
    "--base-url, rounds run) are not run here: delegate the critic to a fresh subagent instead. Returns the exit code, "
    "the output and the files written; a command that outlasts wait_seconds returns a job_id for construct_job.",
    {"argv": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 64,
              "description": "e.g. [\"compare\", \"scene.json\", \"--trace\", \"side.json\", \"--view\", \"side\", \"--record\"]"},
     "project": {"type": "string", "description": "The project to run in (its folder is the working folder)."},
     "wait_seconds": {"type": "integer", "minimum": 1, "maximum": 380,
                      "description": "How long to wait before handing over a job_id (default 300)."}},
    required=("argv",))

WORLD = _tool(
    "construct_world",
    "Place whole constructs together in one world and see it live in the chat: a chair, a clock and a piano in the "
    "user's house, their cars under it, a castle on a hill, a ship overhead, a planet in the sky; at city scale, "
    "worlds inside worlds. Each placed construct stays whole (its own parts, sources, provenance and joints, under "
    "its placement's id: eames/seat-shell), at its real size unless scaled. Ops: new {title, construct (what holds "
    "the rest: the user's project, a construct the plugin ships, a gallery construct, or a scene path)}; place "
    "{world, construct, id?, on?, at?, yaw?, rotate?, scale?, floating?, sky?, note?}; move {world, id, ...the same "
    "fields}; remove {world, id}; list {world, id?} (with id: the surfaces on that placement things can stand on). "
    "on: an earlier placement (it stands on that placement's ground) or placement/part-id (on that part's top: a "
    "floor, a deck, a table); at: metres (with on: x and z, and a lift above the top); yaw: degrees about up. sky: "
    "{diameter_m, distance_m, azimuth, elevation}: far away at its real angular size (a planet, the moon). Every "
    "change is checked, rebuilt and shown (a MEDIA line, as construct_build), with the placements' sizes, what each "
    "stands on and warnings (overlaps, a thing running into the house it is in, things standing on nothing). place "
    "several at once with placements: [{construct, id?, on?, at?, yaw?, ...}, ...] (one check, one rebuild). view {world, "
    "id, label?, target?, yaw?, pitch?, distance?, remove?}: a named view of the world (a room: target a floor part; "
    "one placement: its id), shown as a button on the page beside one for each placement. tidy {world, projects}: archive the "
    "scratch projects made on the way (nothing is deleted). construct_check checks a "
    "world; construct_export exports it whole (one glTF for Blender or a game engine, joints working).",
    {"op": {"type": "string", "enum": ["new", "place", "move", "remove", "list", "view", "tidy"]},
     "projects": {"type": "array", "items": {"type": "string"},
                  "description": "tidy: project ids of scratch work for this world (trial copies, superseded builds) to "
                                 "archive: kept, out of the Constructs page's way."},
     "world": {"type": "string", "description": "The world's project id (from op new)."},
     "title": {"type": "string", "description": "new: the world's name."},
     "example": {"type": "string", "description": "new: start from a world that ships with the plugin "
                                                  "(construct_start lists them under worlds)."},
     "summary": {"type": "string", "description": "new: what the world is, in a sentence."},
     "construct": {"type": "string", "description": "What to place: the user's project id (a construct or another "
                                                    "world), a construct the plugin ships (construct_start lists them), "
                                                    "a gallery construct by name, or a scene's absolute path."},
     "id": {"type": "string", "description": "The placement's id (default: from the construct's name)."},
     "on": {"type": "string", "description": "An earlier placement's id, or placement/part-id to stand on that part."},
     "at": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] metres."},
     "yaw": {"type": "number", "description": "Degrees about up (+Y)."},
     "rotate": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] degrees, after yaw."},
     "scale": {"type": "number", "description": "1 is real size (the default); anything else is shown as such."},
     "floating": {"type": "boolean", "description": "It is meant to hover (a ship, a hanging lamp)."},
     "sky": {"type": "object", "description": "{diameter_m, distance_m, of?, azimuth?, elevation?}: a planet or moon "
                                              "far away, drawn at its real angular size. of: the part diameter_m is "
                                              "the real diameter of (a planet's globe), else the whole construct's "
                                              "size; its rings and moons come at the same scale."},
     "placements": {"type": "array", "items": {"type": "object"},
                    "description": "place: several placements at once, each {construct, id?, on?, at?, yaw?, rotate?, "
                                   "scale?, floating?, sky?, note?, label?}."},
     "label": {"type": "string", "description": "A display name for the placement, or view: the view's button."},
     "target": {"type": "string", "description": "view: what it frames, a placement id or placement/part-id."},
     "pitch": {"type": "number", "description": "view: degrees above the horizon."},
     "distance": {"type": "number", "description": "view: 1 frames the target; less is closer."},
     "remove": {"type": "boolean", "description": "view: remove the named view."},
     "note": {"type": "string", "description": "Why it is there (kept with the placement)."},
     "wait_seconds": {"type": "integer", "minimum": 1, "maximum": 380}},
    required=("op",))

TOOLS = [START, EDIT, CHECK, INSPECT, BUILD, REVIEW, EXPORT, FILM, JOB, COMMAND, WORLD] + NETLOGO_TOOLS
NAMES = [t["name"] for t in TOOLS]


def by_name(name):
    return next(t for t in TOOLS if t["name"] == name)
