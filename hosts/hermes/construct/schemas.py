"""The tools' JSON schemas, as the model sees them."""

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
    "Start a construct project: a new folder holding scene.json, from ONE of: an archetype's parameter document "
    "(the simple path for a CD case, book, guitar, bass, synth, car, bottle, can or glass), a category starter scene "
    "(the full loop for anything else), a bundled example scene, or an existing scene the user named (copied with its "
    "artwork). Then edit the scene file with your file tools and run construct_check. Called with no source, it "
    "lists the archetypes and their variants, the categories and the bundled examples, and which outside programs "
    "(browser, ffmpeg, FreeCAD, Blender) are available.",
    {
        "title": {"type": "string", "maxLength": 120, "description": "The construct's title; also names the project."},
        "archetype": {"type": "string", "enum": ARCHETYPES,
                      "description": "Parameter document for an archetype (with variant): case (jewel, slim, digipak, box), "
                                     "book (hardcover, paperback), object (electric-guitar, acoustic-guitar, bass-guitar, "
                                     "synth), vehicle (wedge, coupe, sedan), vessel (bottle, can, glass)."},
        "variant": {"type": "string", "description": "The archetype's variant, e.g. jewel or electric-guitar."},
        "seed": {"type": "integer", "description": "With an archetype: a seeded variant with sizes drawn near the standard."},
        "category": {"type": "string", "enum": CATEGORIES, "description": "A valid starter scene of this category to "
                                                                          "rewrite with the real thing."},
        "example": {"type": "string", "description": "A bundled example scene by name (call with no source to list them), "
                                                     "e.g. lighthouse, leica-m3, castle."},
        "from_path": {"type": "string", "description": "An existing scene or parameter document (absolute path) the user "
                                                       "gave you; it is copied into the new project."},
    })

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
    "as the open animation, idle motion), stl or 3mf (one watertight solid to 3D print, checked), fcstd or step (named "
    "solids and joints in FreeCAD, and STEP; needs FreeCAD installed). Returns the file, Construct's report and a MEDIA: "
    "line to put in your reply. Long exports return a job_id: follow it with construct_job.",
    dict(_TARGET,
         format={"type": "string", "enum": ["glb", "obj", "stl", "3mf", "fcstd", "step"]},
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
    "Status of a background Construct job (a film, or a build, review, export or command that outlasted its call): "
    "running with progress, or finished with its result and MEDIA: lines (put them in your reply), or failed with "
    "Construct's own message. cancel=true stops it. Without job_id: the recent jobs.",
    {"job_id": {"type": "string", "description": "The job_id a construct tool returned."},
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

TOOLS = [START, CHECK, INSPECT, BUILD, REVIEW, EXPORT, FILM, JOB, COMMAND]
NAMES = [t["name"] for t in TOOLS]
