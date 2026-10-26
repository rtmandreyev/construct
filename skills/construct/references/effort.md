# Research and effort

Aim for genuinely good, and always stop within the mode's limits. Both rules hold together.

## Research: optional, decided by the request

| request | research | record |
|---|---|---|
| a generic subject: "a watch", "a desk lamp", "a fictional moss snail" | none: a typical, well-proportioned example from general knowledge; `subject.accuracy: generic`, facts `inferred` or `decorative` | `"research": "not_needed"` |
| a concrete, named subject: a brand and model, a named place or building, a species, a specific artwork or vehicle | **preferred whenever you are unsure** of its identity-defining shape or specs (below) | `"done"`, with the sources used |
| the same, and you are confident without looking | skip it; then nothing is `verified` (no cited source): facts `inferred`, accuracy `approximate` at most | `"skipped"` |
| no web tool in the host | proceed without it; mark accuracy honestly; say in `next` what research would improve | `"unavailable"` |
| the user says "research: on" or "research: off" | the user wins, either way | `"done"` / `"off"` |

Research, when it applies, comes **before** any part is written:

1. **Look up the exact subject:** the official or maker's pages, manuals, specifications,
   plans and drawings, and reference photos (front, side, three-quarter).
2. **Look at the references** with vision (any model that can see images: Claude, GPT,
   Gemini, DeepSeek; in Hermes through the vision toolset) and measure the silhouette and the
   proportions. Trace the identity shape when text cannot give it ([tracing](tracing.md)).
3. **Record what each value is:** documented (`verified`, citing the page), traced
   (`inferred`, citing the reference image) or invented (`inferred` with a note, or
   `decorative`).
4. **Only then author.**

Record it in the scene: `"authoring": {"tier": "standard", "research": "done", "sources":
["maker-specs", "ref-front"]}`, every id also in the scene's `sources`.

## Modes: fast, masterpiece, unbounded

The user picks a mode by saying its name, or says nothing and you pick one (below).

| mode | what it does | stops at | costs | for |
|---|---|---|---|---|
| **fast** | one pass with self-review, no rounds loop (the standard tier; showcase for a richer subject) | the tier's limits: 10 min and 2 reviews, or 30 min and 4 | 10 minutes (30 for a richer subject); cents with a DeepSeek-class model (tested: DeepSeek V4.1 Flash) | generic subjects ("a watch", "a car"), simple mechanical objects, quick asks; DeepSeek-class models do these well |
| **masterpiece** | the rounds loop: a defect ledger and one independent critic a round, each version judged pairwise against the best so far ([rounds](rounds.md)) | 2 rounds in a row without a pairwise win, every criterion 3, **12 rounds**, or **2 hours of active work** | up to 12 rounds and 2 hours of active work, plus the critic's time; the most tokens of a normal run, so use a frontier model (tested: GPT-6.1 Sol, Claude Opus 5.5) | a specific named subject whose likeness matters: a car model, a landmark, a named building |
| **unbounded** | the same loop with **only** its stop rules: no round cap, no time ceiling | 2 rounds in a row without a pairwise win (or every criterion 3), or the user | no cap: many rounds and hours, at a high token cost; stop it at any round | only when the user asks for it by name |

**Unbounded, plainly:** the critic finds a win almost every round, so an unbounded run can go
on for many rounds and hours, at a high token cost. The per-round report lets the user stop it
at any time. In the author's own blind comparisons, on two subjects, there was no visible gain
after about 12 rounds, which is why masterpiece stops there. Offer unbounded only when asked; never choose it yourself.

The old tier names still work: quick, standard and showcase are fast; masterpiece is
masterpiece. `tier: showcase` or `mode: masterpiece` in a request is honoured.

### Choosing when the user says nothing

Pick the mode yourself and **announce it before any work**, in two or three lines: the mode,
why, the rough time and cost, and how to switch. For example:

> Mode: **masterpiece**, because a Porsche 911 is a specific named car whose likeness matters.
> About 12 rounds and up to 2 hours of active work, at frontier-model token cost. Say "fast"
> for a single 10-minute pass instead (or "unbounded" to keep going past 12 rounds).

- **fast:** a generic subject, a simple mechanical object, a quick request.
- **masterpiece:** a specific named subject whose likeness matters (a car model, a landmark, a
  named building).
- **unbounded:** never chosen automatically.

**Say which model fits.** If you are a smaller or cheaper model and the subject is a hard named
one, say so in the announcement and recommend GPT-6.1 Sol or Claude Opus 5.5 (or a model of that class) for masterpiece (the
evaluation runs: small models made scale errors and often failed to save a scene);
offer fast mode as the alternative on the current model.

## The tiers behind the modes

| mode | tier | use | wall clock | review/improve rounds | check rounds | research, when it applies |
|---|---|---|---|---|---|---|
| fast | quick | fast mode: bulk imports and simple archetypes (the parameter path) | 2 min | 0 (audit only) | 3 | none beyond the source data |
| fast | standard | fast mode: one entry, a generic subject or a simple object | 10 min | 2 | 6 | ≤5 searches, ≤3 sources read, ≤3 reference images |
| fast | showcase | fast mode for a richer subject: more references, more review rounds | 30 min | 4 | 10 | ≤10 searches, ≤6 sources read, ≤6 reference images |
| masterpiece | masterpiece | a named subject whose likeness matters: rounds judged pairwise against the best, until two rounds without a win, every criterion 3, 12 rounds or the 2-hour ceiling | 120 min active | 12 (default cap) | 8 per round | ≤20 searches, ≤12 sources read, ≤12 reference images |
| unbounded | unbounded | only on explicit request: the same rounds with only the stop rules (two rounds without a win, or every criterion 3); no round cap, no time ceiling; many rounds and hours at a high token cost | none | until the stop rules | 8 per round | ≤20 searches, ≤12 sources read, ≤12 reference images |

Effort goes where it is visible: silhouette, then proportions, then the two or three identity
features, then secondary detail. Model nothing smaller than about 0.5% of the object's largest
size: that is efficiency guidance, not a reason to stop.

## Watch the clock: draft early

A run that researches well and then writes one large scene at the end can lose everything to
the time limit (seen in a live run: ten minutes of excellent research, no scene saved). So:

| share of the tier's time | what is true |
|---|---|
| ≤ 40% | research is over (within its counts) and a **complete scene that passes `check` is saved** in your folder |
| 40–80% | improve the saved scene in place: one change, `check`, save, `review`; a valid scene is always on disk |
| 80% | stop adding (in Hermes: the run budget's wrap-up notice); make the saved scene valid, `build`, deliver with `next` |

Start the first draft from what you have (the silhouette, the masses, the identity features
roughly placed) rather than from a perfect plan; size and detail come in the rounds after.

## Masterpiece and unbounded: the rounds

For a subject that must be recognisable exactly (a named car, a landmark building).
Masterpiece runs judged rounds ([rounds](rounds.md)) and stops at the first of: two rounds in a
row that do not beat the best, every criterion at 3, 12 rounds, 2 hours of active time (an
interruption does not count), or the user. Unbounded drops the round cap and the time ceiling.
Every round:

1. Work on at most 4 ledger items, regressions first, and tag each edit with its ledger id.
2. `check` until clean; `rounds packet` checks the round in and writes the critic's packet.
3. One fresh critic judges it blind, then against the best so far (A/B, unlabelled), then
   reconciles the ledger; `rounds record` keeps the version if it wins overall (its
   regressions lead the next round) and reverts it only if it loses.
4. Report the round in chat: the critic's top requests, what changed (ledger ids), won or
   lost, the minutes. Everything else is in `rounds.md` and `checkpoints/round-NN/`.

Start it with the same research, identity checklist and draft-early rule as any tier: a
complete, valid scene first, then the rounds. A run can be resumed at any time
(`rounds status`): usage limits are expected.

## When to stop

At whichever comes first:

- **The review judges it genuinely good**: accurate and beautiful, something you would put in
  a launch video. Only an independent critic can record "good" or "outstanding"; your own
  review records "self-reviewed". Judge it with the art-direction rubric in [review](review.md) on the rendered
  captures, not only the audit. Review, improve the weakest point, review again.
- **Any limit of the tier is reached** (wall clock, check rounds, review rounds, research
  counts, or a host's token or cost ceiling).

Then deliver the best version so far, and record how it ended:

```json
"authoring": {"tier": "standard", "research": "done", "sources": ["maker-specs", "ref-front"],
              "review_rounds": 2, "outcome": "limit",
              "next": ["trace the headstock from a side photo", "finer fret markers"]}
```

`outcome` is `outstanding` or `good` (an independent critic's verdict, recorded by
`construct critique`), `self-reviewed` (your own review), `limit` or `unreviewed` (nobody could
look at the captures). `next`
lists, most valuable first, what the next improvement would be, so the construct can be
regenerated at a higher tier later. Say the same in the hand-over.

## Count the rounds

Before each review round, add one to `authoring.review_rounds` in the saved scene and save
it. `check` warns `tier-rounds` once the count is past the tier's cap: stop reviewing then,
deliver, and put what you would still improve in `next`.

## Who enforces the limits

- **The agent** (any host) follows the tables above; the mode is the user's choice, or yours
  when they name none (announced first, never unbounded).
- **`construct author`** enforces them itself: `--mode` (or `--tier`), a wall-clock timeout, check and
  review round counters (no review round starts after 80% of the time), saving every new best
  valid draft to `--out` at once, a cap on web reference images (`--max-images`; the user's own
  photos are source data, not research), and optional `--max-total-tokens` or `--max-cost`
  (with `--price-in`/`--price-out`, USD per million tokens). `--vision` turns on the
  review rounds for a model that can see. Single limits can be raised, never removed.
- **MCP hosts** ask `construct_limits` for a tier's limits (with overrides, or the `tier:` and
  `research:` words found in a request) and enforce them in their own loop.
- **Claude Code**: a command hook (`hosts/claude-code/construct_budget.py` in the
  repository, with its settings recipe) refuses review commands past the tier's rounds and,
  past the wall clock, every tool but reading, `check` and `build`.
- **Hermes**: `hermes chat --run-budget 600 --max-turns 120` (per run; the owner's
  `config.yaml` stays as it is) gives the 80% wrap-up notice and a hard ceiling.
- **Hosts add hard limits on top**: a Hermes run budget (its turn and time limits), an agent
  harness's timeout and cost ceiling (for example tessera-agent's), a provider's spend cap.
  Whichever limit is tightest wins. Only the unbounded mode, on the user's explicit request,
  runs without Construct's own round cap and time ceiling.
