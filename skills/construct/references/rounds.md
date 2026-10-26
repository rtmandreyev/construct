# Rounds: how a masterpiece (or unbounded) run gets better, and when it stops

A long run improves only if each round is judged fairly and nothing good is thrown away. In live
runs a construct gained about one rubric point per round, up to about 20 of 27 by 45–50 active
minutes. What wasted rounds there:
- comparing every round with the luckiest score so far (single scores wobble by about ±1);
- reverting a whole round over one local regression;
- bundling 5–10 edits, so nobody could tell which one hurt;
- retiring defects as "known limits" while they were still being fixed.

`construct rounds` keeps the run on disk, so it can be read, steered and resumed. It is the
masterpiece and unbounded modes; fast mode is one pass without it.

## Start

In the run's own folder, named after nothing (`run-3f9a/`, not the subject's name), with the
first draft saved and passing `check`:

```bash
python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds start scene.json --mode masterpiece      # or --mode unbounded, only when asked
```

The run's memory is these files. Every command saves them, so an interruption loses at most one
step:

| file | holds |
|---|---|
| `state.json` | `round`, `step`, `active_seconds`, `critic_seconds`, `best_round`, `status` (running / stopped) |
| `ledger.json` | every defect ever raised: `id`, `title`, `criterion`, `severity`, `first_round`, `status` (open / fixed / regressed / known-limit), `rounds_attempted`, `history` |
| `rounds.md` | one section per round, appended: what changed, the critic's requests, won or lost |
| `checkpoints/round-NN/` | that round's scene, its renders, the critic's answer, the A/B key (never shown to the critic) |

## One round

1. **Work on at most 4 ledger items.** Regressions come first, then the rest from most severe
   down. Never work on a known limit. Tag every edit with its ledger id:
   `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds change D3 "lowered the bonnet 40 mm at the axle"`. In round 1 the tag
   is `draft`. A fifth item is refused: check the round in and let the critic judge first.
   Small batches tell you which edit did what.
2. **`check` until clean,** then `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds packet --reference side=side.jpg
   --reference top=top.jpg ...`. That checks the scene in to `checkpoints/round-NN/` and
   writes one packet, in a neutral folder, with the references copied in, for **one** fresh
   critic:
   - **part 1:** this version alone, the standard critique;
   - **part 2:** this version and the best so far, from the same views, unlabelled and in a
     random A/B order, beside the references. The pictures are re-encoded and named at random,
     so no file comparison tells them apart;
   - **part 3:** the ledger.

   The critic writes part 1 before it opens part 2. Its blind judgement never sees the history.
3. **The critic.** Give a fresh critic the packet folder and nothing else: a subagent, one
   delegated task (in Hermes, one child a round fits its two-child budget), or direct model
   calls: `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds run --base-url URL --model M --key-env VAR` (one conversation,
   part 1 answered before parts 2 and 3 are shown). Save its answer outside the packet folder.
4. **`python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds record answer.json`.** It un-blinds the pair and decides:
   - **Won overall: keep it.** Its regressions go to the top of the ledger. Repair, don't
     revert.
   - **Lost overall: revert.** The working scene becomes the best round again. Next round, try
     a different fix.

   Absolute scores are recorded but decide nothing.
5. **Report the round in chat,** every round.
   `record` prints it: the critic's top requests, what changed (with ledger ids), won or lost
   against the best, and the minutes. Copy it as it is. Then go to step 1, unless it says STOP.

Each round's section in `rounds.md` also answers "would a 4-round finish cap stop here?". Finish
starts at the first round with no critical or major silhouette, proportions or identity item
open. This is logged only, to compare stop rules; it never stops the run.

## The medium

The renderer cannot do three things, and `start` seeds them as known limits (L1–L3):
- hidden lines show faintly through solid parts (the x-ray style);
- glass cannot be tinted;
- stills show the closed still pose.

An ask the critic itself files under one of them (its `limits` answer in part 3) never enters the
ledger. Don't try to change the renderer from a scene.

## Scores need evidence

Every score below 3 cites a defect of its criterion, or the critique is refused. In the log, a
score that moves with no defect added or fixed for its criterion is marked as noise. The pairwise
gate, not the scores, decides which version is the best.

## The ledger

`record` reconciles every open item (fixed, open, regressed) and adds the genuinely new
defects. An item becomes a **known limit** in either case:
- 3 kept rounds attempted it without progress (rounds that were reverted don't count);
- the critic says the construct's tools cannot draw it (`inexpressible`).

Known limits are not worked on again. The final report lists them as **skill gaps**: what the
skill could not express.

## Stop

At the first of:
- 2 rounds in a row that don't beat the best (any pairwise win resets the count);
- every criterion at 3;
- **masterpiece only:** 12 rounds (a default cap: in the author's own blind comparisons, on two
  subjects, no visible gain showed after about 12 rounds);
- **masterpiece only:** 2 hours of **active time**: the author's time from `start` or `record` to the
  next `packet`, measured from the run folder's own activity (edits, a generator writing the
  scene, builds). Time after the last write counts only if the next command comes within 10
  minutes; a silence of over 45 minutes between writes (a usage limit) is an interruption; and
  `rounds pause` marks one explicitly. The critic's time, from `packet` to `record`, is measured
  the same way, the packet's folder included, and logged separately;
- the user says so.

**Unbounded** keeps only the first two: no round cap and no time ceiling. The critic finds a
win almost every round, so it can run for many rounds and hours at a high token cost. Report
every round, so the user can stop it at any time.

Then `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds report` appends the final report to `rounds.md`: the best round, the
curve, the minutes, the open defects and the known limits. Deliver the best round: it is the
working scene, with its round history in `authoring.rounds`. `construct.html` shows the
timeline, and `review` writes it as `rounds.png`.

## Resume (usage limits are expected)

Before stepping away, `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds pause`. After any interruption, `python3 ${HERMES_SKILL_DIR}/scripts/cli.py rounds
status` says where the run is and what the next step is. Redo only the step it names, never a finished round.
