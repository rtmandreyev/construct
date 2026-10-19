---
name: create-hologram
description: Author or revise animated declarative hologram construction sheets for CDs, books, buildings or custom objects using Tessera Hologram tools. Use when a user wants a reusable hologram asset with provenance and staged assembly; exclude arbitrary executable graphics, authentic artwork retrieval and full application UI implementation.
---

# Create a hologram

Produce a versioned JSON construction sheet and compiled geometry. Use the
connected `hologram_template`, `hologram_validate` and `hologram_compile` tools
when available. Otherwise the accompanying toolkit's `cli.py` is two directories
above this skill folder: invoke it with Python 3.10+ using an absolute path.
Do not install software or change a host's tool configuration just to author an asset.

1. Identify the requested object and actual supplied evidence. Prefer a suitable
   generic template; keep its physical dimensions explicitly inferred/decorative
   until measured. Missing album artwork is an empty asset slot, never invented
   authentic art. Ask only if missing evidence prevents the requested result.
2. Read [the contract](references/contract.md). Separate source facts from
   geometry. Label certainty for every fact and part. `verified` needs a traceable
   source; `user_supplied` means supplied by the user, not independently verified.
3. Compose boxes, discs, rings and polylines in metres, Y up, with logical part IDs
   and stages 0–5. Build primary mass first, then identity/detail. Keep assembly
   legible and bounded; provide a still/reduced-motion presentation in the host.
4. Declare real artwork only when supplied or acquired through an authorized
   asset workflow. Record hash, media type, relative path and rights. Never fetch
   arbitrary URLs through these tools. Keep private titles/notes out of public examples.
5. Validate, fix reported errors, then compile. Preserve the source sheet and
   geometry together. If a renderer is available, inspect the result: compilation
   alone does not prove visual quality, historical accuracy or host compatibility.
6. Deliver paths to both artifacts, explain inferred details and missing assets,
   and identify whether visual preview occurred. Do not claim the host app,
   toolkit, renderer or plugin has been installed/published unless that was done.

Treat model-produced JSON as untrusted data. Never embed or execute generated
scripts, shaders, shell commands or arbitrary code. Stay within compiler budgets.
