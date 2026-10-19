# The check-and-repair loop (for hosts and runners)

1. Send `system.md`, then `params.md` (small models) or `scene.md` (capable models), then
   the user's request with any facts and supplied images.
2. Check the answer: `python3 cli.py check draft.json --json` (or `diagnose.diagnose_text`).
   The report: `ok`, `errors`, `warnings`, `diagnostics[]` (`severity, code, path, message,
   hint`) and `repair_text`.
3. If `ok` is false, send `repair_text` back as the next user message and check again.
   Stop after 4 rounds; if a full scene still fails, ask the same model for the parameter
   document instead (`params.md`), which almost always validates.
4. When `ok` is true: `build` (geometry, preview, audit) and, if a browser is available,
   `review` for images a person or a vision model can judge. Warnings are allowed; pass them
   on with the proposal.

Codes a model will meet: json, duplicate-key, unknown-key, missing-key, type, range,
choice, id, reference, certainty, unknown-fact, style, path, budget, floating,
stage-order, overclaim, accuracy, decorative-identity, no-mass, no-identity, clutter,
duplicates, tiny, invisible.

A host that supports constrained output can hold a small model to `params.schema.json`.
No step needs an API key from this toolkit; the model and its key live in the host.
