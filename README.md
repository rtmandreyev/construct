# hologram-studio

Audited, animated holograms of objects, buildings, machines and creatures — authored by any
AI agent. An agent (or a person) describes *what* a thing is: its parts, real sizes, facts and
how certain each one is. The toolkit validates and audits that description, compiles it
deterministically, and renders it as an animated WebGL2 hologram in one house style: staged
construction, a calm idle life, an opening sequence, honest certainty, a reduced-motion still.

- **Any model, any host.** No API key, no model and no network service inside. Small models
  fill a ten-line parameter document; capable models write full scenes; every draft comes
  back with JSON paths, codes and fix hints until it is valid.
- **Honest by construction.** Every fact is `verified` (with a source), `user_supplied`,
  `inferred` or `decorative`; unknown facts are left out, never guessed; text on an object
  comes only from facts; artwork only from hashed bytes the user supplied.
- **The renderer owns the look.** Agents never pick colours, so entries from a cheap model
  and a frontier model sit side by side on the same shelf.
- Python 3.10+, standard library only. MIT licensed.

Status: 0.2.0, contract `tessera.hologram/0.2`. The product name is provisional (see
[Renaming](#renaming)).

## Quick start (from any agent)

**Command line** (the toolkit runs by path from any folder; nothing to install):

```sh
python3 hologram_studio/cli.py params --list                        # the simple path's archetypes
python3 hologram_studio/cli.py params case --variant jewel --output cd.json
python3 hologram_studio/cli.py check cd.json --json                 # paths, codes, hints, repair_text
python3 hologram_studio/cli.py build cd.json --out out/             # out/hologram.html, geometry.json
python3 hologram_studio/cli.py review cd.json --out out/            # + review/*.png (needs a local Chromium)
python3 hologram_studio/cli.py video cd.json --out out/cd.mp4       # needs ffmpeg
python3 hologram_studio/cli.py new organism --output scene.json    # a full scene starter
```

**MCP** (stdio, read-only tools; no file access, rendering or network). Point any MCP host at
`server.py`:

```json
{"mcpServers": {"hologram-studio": {"command": "python3", "args": ["/absolute/path/to/hologram_studio/server.py"]}}}
```

Tools: `hologram_diagnose` (raw model output or a document → diagnostics and `repair_text`),
`hologram_params_template`, `hologram_expand_params`, `hologram_compile_scene`, plus the
legacy v0.1 `hologram_template` / `hologram_validate` / `hologram_compile`.

**Python:**

```python
from hologram_studio import diagnose, params, scene, render

report = diagnose.diagnose_text(model_output)    # {"ok", "diagnostics", "repair_text", ...}
if report["ok"]:
    doc, _ = diagnose.parse_text(model_output)
    if doc["format"] == params.FORMAT:            # the simple path
        doc = params.expand(doc)
    geometry = scene.compile_scene(doc)
    html, notes = render.build_html(geometry, asset_root="path/to/assets")
else:
    send_back_to_the_model(report["repair_text"])
```

**Agent skills.** `python3 hologram_studio/package.py --out dist/` builds two self-contained
skill packages (runtime, prompts, examples, contract, schemas, LICENSE, NOTICE, a hashed
manifest):

- **Hermes**: copy `dist/hermes/hologram-studio/` into `~/.hermes/skills/`, or into a project's
  `.hermes/skills/` and run `hermes skills trust` there.
- **Claude Code**: `claude --plugin-dir dist/claude-code/hologram-studio` for one session, or
  copy `dist/claude-code/hologram-studio/skills/hologram-studio` into `.claude/skills/`.

**Any other model or runner** (an OpenAI-compatible endpoint, a local model): send
`prompts/system.md`, then `prompts/params.md` (small models) or `prompts/scene.md`, then the
user's request; check the answer and send back `repair_text` until `ok` (`prompts/repair.md`).
`prompts/params.schema.json` constrains output where the host supports it.

## How it works

**request and evidence → facts → construction (scene or parameters) → deterministic compile →
geometric audit → fixed-view and animation captures → visual review → correction.**

| | |
|---|---|
| Scene format | facts with certainty and sources; parts from a closed shape vocabulary (box, cylinder, cone, sphere, torus, lathe, extrude, tube, curve, plane, grid, points, marker; repeat, radial repeat, mirror); roles; stages; periodic motion; one-shot articulations (hinge, slide, lift, turn); labels from facts; artwork slots; anchors; views |
| The simple path | `tessera-hologram-params` documents for `case` (jewel, slim, digipak, box set), `book` (hardcover, paperback), `object` (electric, acoustic and bass guitar, synth), `vessel` (bottle, can, glass) |
| Audit | support (nothing floats), assembly order, certainty overclaims, documented-accuracy backing, clutter, duplicates, tiny and invisible parts, a missing `open` view |
| Output | packed geometry (`geometry.schema.json`) and one self-contained HTML page; review contact sheets; MP4/GIF |
| Viewer | drag/wheel to orbit, 1–6 views, L labels, P provenance, M reduced motion, R replay, space pause; URL `t`, `view`, `motion`, `mode`, `labels`, `sheet`, `open` reproduce any frame |

The consumer contract is [CONTRACT.md](CONTRACT.md). The authoring skill and its references
are in `hologram_studio/skill/`; the any-model prompts in `hologram_studio/prompts/`.

## Repository

| | |
|---|---|
| `hologram_studio/` | the package: `scene.py` (validation, compiler), `shapes.py`, `audit.py`, `diagnose.py`, `params.py`, `render.py` and `viewer/`, `studio.py` + `cli.py` (command line), `mcp_server.py` + `server.py`, `prompts.py` + `prompts/`, `package.py`, `product.py` (the name) |
| `hologram_studio/examples/v2/` | synthetic examples: lighthouse, turntable, a fictional lantern jellyfish, CD, book, and 15 parameter documents |
| `hologram_studio/evaluation/` | synthetic cross-model tasks, `score.py` (needs no model or key) and the results |
| `hologram_studio/skill/` | the agent skill: `SKILL.md` and references (vocabulary, composition, animation, review, provenance, method) |
| `CONTRACT.md`, `hologram_studio/geometry.schema.json`, `hologram_studio/prompts/params.schema.json` | the contract and its schemas |

Tests: `python3 -m unittest discover -s hologram_studio -t . -p 'test_*.py'` (the capture
smoke test is skipped without a browser).

## Evaluation

Five synthetic tasks (three parameter documents with deliberately unknown facts, a desk lamp,
a fictional creature), prompts only, scored by `score.py` and reviewed visually: Claude Haiku
13/15 then 15/15 after prompt fixes, Sonnet 15/15, Opus 15/15; no tier invented a fact the
user did not know. Parameter entries look identical across tiers; free scenes scale with the
model. Details: [evaluation/RESULTS.md](hologram_studio/evaluation/RESULTS.md). Score any
provider's answers with `python3 -m hologram_studio.evaluation.score <folders>`.

## Requirements, licence, notices

Python 3.10+. Captures need a Chromium-family browser already installed (Chrome, Chromium,
Edge, Brave, or `HOLOGRAM_CHROME=/path`); video needs ffmpeg. Nothing is downloaded or
installed. MIT licence ([LICENSE](LICENSE)); see [NOTICE](NOTICE). Tested on macOS (Apple
Silicon); Linux and Windows capture paths are untested.

## Limitations

- One periodic motion per part (a fan's head cannot oscillate while its blades spin);
  articulations do nest.
- A closed procedural vocabulary: no imported meshes, CAD, photogrammetry or booleans.
- Artwork is a flat image on a face; liquids in glasses read faintly.
- The audit proves validity and honesty, not likeness: free-form subjects need a visual
  review by a person or a model that can see the captures.
- Terrain and routes (scale ladder, measured vs sketched relief) are planned for contract 0.3.

## Integrations: Tessera

Tessera (a collection app) consumes this toolkit as a pinned dependency: its
atlas renders compiled geometry natively (Y-up, front +Z, metres), re-validates it, maps tone
slots to its own palette, drives the articulations and turns to the `open` view, and sets
labels in its own type from the item's live facts. Its agent pipeline (`tessera-agent`, the
inbox) wraps `diagnose`, `params.expand` and `compile_scene`. The contract and format ids
(`tessera.hologram/0.2`, `tessera-hologram*`) come from that integration and stay until a new
contract version decides otherwise.

## Renaming

The name lives in `hologram_studio/product.py` (`NAME`, `TITLE`) and `pyproject.toml`; the
package folder is the import name, and code finds it from the folder. Apply a final name
with `python3 scripts/rename.py <new-name> ["New Title"]` (rewrites those, the README,
CHANGELOG, LICENSE and NOTICE, and `git mv`s the folder), then run the tests.

## Legacy: v0.1 construction sheets

`hologram.py` and `schema.json` keep the earlier construction-sheet compiler (`template`,
`validate`, `compile` commands and MCP tools) for existing consumers. New work uses scenes.
