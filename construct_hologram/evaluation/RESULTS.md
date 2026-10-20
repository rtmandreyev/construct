# Cross-model evaluation, 2026-10-19

Synthetic objects only (every name invented; no private data, no NODE source, no keys).

## Method

- **Tasks** (`TASKS.md`, `tasks.json`): three parameter documents — a jewel-case CD, a
  paperback whose author and year the user does not know, a 440 ml can whose brewery the
  user does not know — and two free scenes: a desk lamp (~45 cm) and a fictional
  three-legged moss snail carrying a lantern.
- **Models**: three Claude tiers run as isolated agents (Haiku, Sonnet, Opus). Each got only
  the packaged prompts (`prompts/`) and the CLI, was told not to read the runtime source,
  examples or references, and could run `check --json` at most 4 times per task.
- **Scoring** (`score.py`, re-checks every answer itself; nothing self-reported is trusted):
  one point each for valid (the toolkit's own diagnostics), factual (the user's facts present
  with the user's values and certainty, nothing the user did not know invented, `verified`
  only with a source, unknowns left out rather than written as "unknown") and plausible
  (archetype, category, size).
- **Visual review**: a person-style look at every hero capture (`review`), recorded below.

## Results

Round 1 used the first prompts; round 2 re-ran the weakest tier after fixing what round 1
found.

| run | t1-cd | t2-paperback | t3-can | t4-lamp | t5-snail | total |
|---|---|---|---|---|---|---|
| Haiku | 3/3 (1 check) | 3/3 (1) | 1/3 (1) | 3/3 (2) | 3/3 (3) | 13/15 |
| Sonnet | 3/3 (1) | 3/3 (1) | 3/3 (1) | 3/3 (1) | 3/3 (3) | 15/15 |
| Opus | 3/3 (1) | 3/3 (1) | 3/3 (1) | 3/3 (1) | 3/3 (3) | 15/15 |
| Haiku, round 2 | 3/3 (1) | 3/3 (1) | 3/3 (1) | 3/3 (2) | 3/3 (1) | 15/15 |

- **Validity**: every answer of every tier became valid within the check budget; the repair
  loop (paths, codes, hints) was enough for all three.
- **Factuality**: no tier invented an author, year, publisher, label or brewery the user did
  not know, or claimed `verified` without a source. Haiku's round-1 can wrote ABV as the
  string "5.6%" and kept the 330 ml height for a 440 ml can; the round-2 prompts (fact units,
  common can sizes, how to state a size) fixed both.
- **Inferred extras**: Sonnet and Opus added `style: "Porter"` to the can as `inferred` —
  honest, labelled, and shown on the can's label; acceptable under the rules.

## Visual review

- Parameter entries (CD, paperback, can) render identically in style across all tiers; only
  the facts differ. This is the consistency the pipeline needs: a small model's entry sits on
  the shelf next to a large model's.
- Desk lamp: recognisable from every tier (base, jointed arm, down-pointing shade); Sonnet's
  elbow reads best; Haiku round 2 is clean.
- Moss snail (fictional, no archetype): quality scales with the model. Round 1: Haiku's read
  as a saucer on legs; Sonnet's as a creature with a lantern on a pole; Opus's best (eye
  stalks, a caged lantern on the back). Round 2 Haiku: head with eye stalks, body, three legs
  and a lantern on a post — a creature, if a plain one.
- Conclusion: free-form subjects still need the visual gate (a person, or a model that can
  see the captures); the validator guarantees validity and honesty, not likeness.

## What the evaluation changed

Prompts: the allowed `category`/`accuracy` values, stage order for bodies on legs, default
shape orientations, certainty of requested parts with chosen sizes and of fictional designs,
`user_private` for real requests, an empty `params` template and how to state a size,
conventional fact keys and units (`abv` with "%", `volume` with "ml"), common container
sizes, appearance words as facts not colours, an example without host-owned blocks.
Validator: synonyms in hints ("creature" → organism or fictional, not "architecture"), and
an `open`-view warning that says when to ignore it.

## Limits

- Only Anthropic tiers were available in this session. DeepSeek, OpenRouter models and local
  models (Ollama, llama.cpp, LM Studio) were not run: the scorer needs no model, so main's
  runner can produce their answers and `python3 -m construct_hologram.evaluation.score <folders>` (from the repository root)
  scores them the same way.
- Agents ran the loop themselves with a CLI; a host runner adds transport (JSON mode, tool
  calls) that was not exercised here.
- Five tasks are a smoke test, not a benchmark; renders were judged by one reviewer.

Renders of every answer are in `.local/construct/` when generated locally (not
committed).
