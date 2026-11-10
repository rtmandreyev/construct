# Construct for developers

Construct is a Python toolkit (3.10 or newer, standard library only, Apache-2.0) around one idea: a thing is
described as data, a **scene**, and everything else is built from it. A model writes the scene. Construct checks it,
hands back each problem with its JSON path and a fix, and builds from it: a self-contained page, a glTF, a print, a
kit, a CAD file, a film. The same scene always builds into the same page and the same model. You can drive it from a command line, an MCP server,
the agent skills or the Hermes plugin, or read its outputs from your own code.

## What you build on

**The scene contract** ([CONTRACT.md](../../CONTRACT.md), `construct/0.2`). A scene is JSON, never code: facts with
their sources, named parts in metres made from a small vocabulary of shapes (boxes, lathes, lofts, tubes,
extrusions…), each part's certainty (its size and its shape apart), joints, motions and the assembly order. Construct
decides how it looks. A **world** (`construct-world`, [WORLDS.md](../WORLDS.md)) places whole scenes together at real
size, each kept whole under its placement's id.

**A check an agent can act on.** `construct check scene.json --json` returns `ok`, `needs_repair`, `diagnostics[]`
(each with `severity`, `code`, `path`, `message` and `hint`) and `repair_text` to send straight back to the model.
Every audit code carries a hint, and a test keeps a new code from arriving without one. `--fit` adds how the solids meet:
parts that poke through, cross a pane, are buried, or are left open where they show.

```json
{"ok": true, "contract": "construct/0.2", "errors": 0, "warnings": 0, "diagnostics": [],
 "stats": {"lines": 68, "triangles": 36, "articulations": 1, "labels": 6, "size_m": [0.1299, 0.198, 0.0251]},
 "needs_repair": false, "repair_text": "The scene is valid and the audit is clean."}
```

**The same scene, the same bytes.** Built twice, the Villa Savoye's page, its `geometry.json` and its glTF came out
byte-identical. The scene's hash travels in the compiled geometry and in the glTF's `extras`, so an output can be
traced to the scene that made it.

**Outputs with a stable shape.** `geometry.json` (its schema:
[geometry.schema.json](../../construct_hologram/geometry.schema.json)); glTF with each part a named node, its role,
certainty and sources in `extras.construct`, the joints as an `open` animation and each vertex's build phase as
`_PHASE`; OBJ, STL, 3MF, FreeCAD and STEP; FBX and USD through Blender. [ADAPTERS.md](../ADAPTERS.md) says where an
adapter reads each thing, with a tested template that writes a parts sheet and an STL per part.

## Ways in

| | What it is |
| --- | --- |
| **Command line** | `python3 construct_hologram/cli.py <command>`: `new`, `params`, `check`, `build`, `review`, `export`, `print`, `kit`, `freecad`, `video`, `audio`, `critique`, `rounds`, `trace`, `compare`, `terrain`, `globe`, the `netlogo` commands and more ([the list](../DEVELOPMENT.md#the-command-line)) |
| **MCP server** | `construct_hologram/server.py`, over stdio: `construct_diagnose`, `construct_params_template`, `construct_expand_params`, `construct_compile`, `construct_limits`, `construct_export`, `construct_print`, `construct_netlogo_instrument`, `construct_netlogo_draw`. They read the JSON they are given; no file access, no network |
| **Agent skills** | the Claude Code skill and the Hermes skill (`python3 construct_hologram/package.py --out dist`), and the same rules as prompts for other models (`construct_hologram/prompts/`) |
| **Any OpenAI-compatible model** | `construct author "request" --base-url … --model … --key-env …` runs the whole loop: write, check, repair, build |
| **Hermes plugin** | thirteen tools, a `/construct` command and a skill with tutorials ([what it does and touches](../../hosts/hermes/construct/README.md)) |

The Hermes plugin's tools, for building an agent workflow on:

| Tool | Does |
| --- | --- |
| `construct_start` | a project from a construct the plugin ships, an archetype, a starter or a scene you name |
| `construct_edit` | changes a scene by part id, dotted path, `[n]` or JSON pointer; each step validated, written only when nothing breaks, with the diff |
| `construct_check`, `construct_inspect` | the audit with fix hints; what the construct's own record says is known |
| `construct_build`, `construct_review` | the live page in the chat; review stills in a headless browser |
| `construct_export`, `construct_film` | glTF, FBX, USD, OBJ, STL, 3MF, FreeCAD, STEP, each read back and summarised; a film, as a background job |
| `construct_world` | makes a world, places constructs (several at once), moves, removes, names views, refreshes improved constructs; checked and shown live |
| `construct_command` | the rest of the command line (rounds, kits, tracing, terrain…), parsed as Construct parses it before it runs, guarded |
| `construct_job`, `construct_netlogo_run`, `construct_netlogo_draw` | background work; NetLogo runs and drawings |

The plugin gives every program it starts a minimal environment (provider keys never reach them), refuses options
that would call a model over the network, writes only inside its data and projects folders, and fetches nothing but a
gallery construct a world names, from this release's tag, after the user approves it.

## Try it

```sh
git clone https://github.com/rtmandreyev/construct.git && cd construct
python3 construct_hologram/cli.py params book --variant paperback --output book.json
python3 construct_hologram/cli.py check book.json --json            # the report above
python3 construct_hologram/cli.py build book.json --out out          # out/construct.html, out/geometry.json
python3 construct_hologram/cli.py check examples/worlds/rain-harbour/world.json   # a world's audit
python3 -m unittest discover -s construct_hologram -t . -p 'test_*.py'
```

As an MCP server:

```json
{"mcpServers": {"construct": {"command": "python3", "args": ["/path/to/construct/construct_hologram/server.py"]}}}
```

## Tests

Over 500 tests, standard library only, no network and no model, run in CI on macOS, Linux and Windows. They compile
every example, replay exported animations in a small glTF evaluator to a fraction of a millimetre, build the host
packages and the gallery, and check its links. When an environment variable names one, they also drive the real
program: Blender's importer (`CONSTRUCT_BLENDER`), Godot's physics (`CONSTRUCT_GODOT`), FreeCAD (`CONSTRUCT_FREECAD`),
PrusaSlicer (`CONSTRUCT_PRUSASLICER`) and NetLogo (`CONSTRUCT_NETLOGO`).

## Good to know

- **Budgets** are part of the contract: a construct up to 1,024 parts, 48,000 lines and 48,000 triangles on its page,
  200,000 solid triangles for exports, 16 joints; a world up to 4,096 placements, 400,000 lines and triangles, 2,000,000
  solid triangles. `construct_limits` gives a mode's limits for a host to enforce.
- **Construct never downloads or installs anything.** A browser (stills, films), ffmpeg, Blender, FreeCAD and NetLogo
  are used when present.
- **The contract grows by additions** within `construct/0.2`; what is planned and not yet in it is listed at the end
  of [CONTRACT.md](../../CONTRACT.md#planned-not-yet-in-the-contract).

## Go deeper

- [Development](../DEVELOPMENT.md): the repository, the command line, the check report, the MCP tools, the tests
- [Using Construct](../USING.md): every way to run it, in Claude Code, Hermes and through MCP
- [The scene contract](../../CONTRACT.md) and [worlds](../WORLDS.md)
- [Adapters](../ADAPTERS.md): write your own, from a template
- [Evaluation](../EVALUATION.md): how models compare, and how to score your own
