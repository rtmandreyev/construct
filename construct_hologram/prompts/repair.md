# The check-and-repair loop (for hosts and runners)

1. Send `system.md`, then `params.md` (small models) or `scene.md` (capable models), then
   the user's request with any facts and supplied images.
2. Check the answer: `python3 cli.py check draft.json --json` (or `diagnose.diagnose_text`).
   The report: `ok`, `errors`, `warnings`, `diagnostics[]` (`severity, code, path, message,
   hint`) and `repair_text`.
3. While `needs_repair` is true (errors, or a part that is detached or a hairline), send
   `repair_text` back as the next user message and check again.
   Stop at the tier's check rounds; if a full scene still fails, ask the same model for the parameter
   document instead (`params.md`), which almost always validates.
4. When `ok` is true: `build` (geometry, preview, audit) and, if a browser is available,
   `review` for images a person or a vision model can judge. Other warnings are allowed;
   pass them on with the proposal.
5. For models that can see images: send `vision-review.md` with `review/hero.png`,
   `sheet-views.png`, `sheet-assembly.png` (and `view-open.png` when it opens) and the
   original request. While the verdict is "improve", ask for the fix to the weakest point,
   check it again, and review again.
6. Every loop is bounded by the effort tier (`system.md`): check rounds, review rounds and
   wall clock, plus any token or cost ceiling the host sets. Stop at whichever comes first,
   the verdict "good" or a limit, and deliver the best draft so far with its `authoring`
   record (`tier`, `outcome`, `next`). `construct author --tier ... --vision` runs exactly this.

Codes a model will meet: json, duplicate-key, unknown-key, missing-key, type, range,
choice, id, reference, certainty, unknown-fact, style, path, budget, floating,
stage-order, overclaim, accuracy, decorative-identity, no-mass, no-identity, clutter,
duplicates, tiny, invisible, no-open-view, detached, thin, shape-overclaim, research,
tier-budget, authoring.

A host that supports constrained output can hold a small model to `params.schema.json`.
No step needs an API key from this toolkit; the model and its key live in the host.
