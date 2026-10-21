# Rounds: how a Masterpiece (or Showcase) gets better, and when it stops

A long run improves only if each round is judged fairly and nothing good is thrown away. In live
runs a construct gained about one rubric point per round, up to about 20 of 27 by 45–50 active
minutes. What wasted rounds there:
- comparing every round with the luckiest score so far (single scores wobble by about ±1);
- reverting a whole round over one local regression;
- bundling 5–10 edits, so nobody could tell which one hurt;
- retiring defects as "known limits" while they were still being fixed.

`construct rounds` keeps the run on disk, so it can be read, steered and resumed. Use it for
Masterpiece, and for Showcase when you run review rounds.

## Start

In the run's own folder, named after nothing (`run-3f9a/`, not the subject's name), with the
first draft saved and passing `check`:

```bash
python3 TOOLS rounds start scene.json --tier masterpiece
```

The run's memory is these files. Every command saves them, so an interruption loses at most one
step:

| file | holds |
|---|---|
| `state.json` | `round`, `step`, `active_seconds`, `best_round`, `status` (running / stopped) |
| `ledger.json` | every defect ever raised: `id`, `title`, `criterion`, `severity`, `first_round`, `status` (open / fixed / regressed / known-limit), `rounds_attempted`, `history` |
| `rounds.md` | one section per round, appended: what changed, the critic's requests, won or lost |
| `checkpoints/round-NN/` | that round's scene, its renders, the critic's answer, the A/B key (never shown to the critic) |

## One round

1. **Work on at most 4 ledger items.** Regressions come first, then the rest from most severe
   down. Never work on a known limit. Tag every edit with its ledger id:
   `python3 TOOLS rounds change D3 "lowered the bonnet 40 mm at the axle"`. In round 1 the tag
   is `draft`. A fifth item is refused: check the round in and let the critic judge first.
   Small batches tell you which edit did what.
2. **`check` until clean,** then `python3 TOOLS rounds packet --reference side=side.jpg
   --reference top=top.jpg ...`. That checks the scene in to `checkpoints/round-NN/` and
   writes one packet, in a neutral folder, for **one** fresh critic:
   - **part 1:** this version alone, the standard critique;
   - **part 2:** this version and the best so far, from the same views, unlabelled and in a
     random A/B order, beside the references;
   - **part 3:** the ledger.

   The critic writes part 1 before it opens part 2. Its blind judgement never sees the history.
3. **The critic.** Give a fresh critic the packet folder and nothing else: a subagent, one
   delegated task (in Hermes, one child a round fits its two-child budget), or direct model
   calls: `python3 TOOLS rounds run --base-url URL --model M --key-env VAR` (one conversation,
   part 1 answered before parts 2 and 3 are shown). Save its answer outside the packet folder.
4. **`python3 TOOLS rounds record answer.json`.** It un-blinds the pair and decides:
   - **Won overall: keep it.** Its regressions go to the top of the ledger. Repair, don't
     revert.
   - **Lost overall: revert.** The working scene becomes the best round again. Next round, try
     a different fix.

   Absolute scores are recorded but decide nothing.
5. **Report the round in chat** (Masterpiece: every round; Showcase: one summary at the end).
   `record` prints it: the critic's top requests, what changed (with ledger ids), won or lost
   against the best, and the minutes. Copy it as it is. Then go to step 1, unless it says STOP.

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
- every criterion at 3;
- 2 rounds in a row that don't beat the best;
- the 2-hour safety stop on active time (time lost to a usage limit or a pause doesn't count);
- the user says so.

Then `python3 TOOLS rounds report` appends the final report to `rounds.md`: the best round, the
curve, the minutes, the open defects and the known limits. Deliver the best round: it is the
working scene, with its round history in `authoring.rounds`. `construct.html` shows the
timeline, and `review` writes it as `rounds.png`.

## Resume (usage limits are expected)

After any interruption, `python3 TOOLS rounds status` says where the run is and what the next
step is. Redo only the step it names, never a finished round.
