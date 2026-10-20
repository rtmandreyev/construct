# Research and effort

Aim for genuinely good, and always stop within the tier's limits. Both rules hold together.

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

## Effort tiers

| tier | use | wall clock | review/improve rounds | check rounds | research, when it applies |
|---|---|---|---|---|---|
| quick | bulk imports and simple archetypes (the parameter path) | 2 min | 0 (audit only) | 3 | none beyond the source data |
| standard | one entry (the default) | 10 min | 2 | 6 | ≤5 searches, ≤3 sources read, ≤3 reference images |
| showcase | only on explicit request: more references, more review rounds | 30 min | 4 | 10 | ≤10 searches, ≤6 sources read, ≤6 reference images |

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

## When to stop

At whichever comes first:

- **The review judges it genuinely good**: accurate and beautiful, something you would put in
  a launch video. Judge it with the art-direction rubric in [review](review.md) on the rendered
  captures, not only the audit. Review, improve the weakest point, review again.
- **Any limit of the tier is reached** (wall clock, check rounds, review rounds, research
  counts, or a host's token or cost ceiling).

Then deliver the best version so far, and record how it ended:

```json
"authoring": {"tier": "standard", "research": "done", "sources": ["maker-specs", "ref-front"],
              "review_rounds": 2, "outcome": "limit",
              "next": ["trace the headstock from a side photo", "finer fret markers"]}
```

`outcome` is `good`, `limit` or `unreviewed` (nobody could look at the captures). `next`
lists, most valuable first, what the next improvement would be, so the construct can be
regenerated at a higher tier later. Say the same in the hand-over.

## Who enforces the limits

- **The agent** (any host) follows the table above; the tier is the user's or host's choice,
  standard by default, showcase only when asked.
- **`construct author`** enforces them itself: `--tier`, a wall-clock timeout, check and
  review round counters (no review round starts after 80% of the time), saving every new best
  valid draft to `--out` at once, a cap on web reference images (`--max-images`; the user's own
  photos are source data, not research), and optional `--max-total-tokens` or `--max-cost`
  (with `--price-in`/`--price-out`, USD per million tokens). `--vision` turns on the
  review rounds for a model that can see. Single limits can be raised, never removed.
- **MCP hosts** ask `construct_limits` for a tier's limits (with overrides, or the `tier:` and
  `research:` words found in a request) and enforce them in their own loop.
- **Hosts add hard limits on top**: a Hermes run budget (its turn and time limits), an agent
  harness's timeout and cost ceiling (for example tessera-agent's), a provider's spend cap.
  Whichever limit is tightest wins; Construct never runs unbounded.
