---
title: Compare two runs
summary: The same model with another seed or a slider moved, side by side on one time scale, then many seeded runs and what held.
group: Simulations
needs: netlogo, browser
time: about 20 minutes
status: ready
---

## Prompt

Teach me to compare NetLogo runs with Construct, two side by side and then many seeded runs, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/15-netlogo-compare-runs.md"). Start by asking me which model to use.

## Steps

1. **Choose a model.** From the user's own installed Models Library: one from `12`, `13` or `14`, or Virus on a
   Network. Ask what they want to learn: does chance alone change the outcome (another seed), or does a setting (a
   slider moved)? If NetLogo isn't found, ask where it is installed and have the user set it in Settings → Plugins →
   Construct → NetLogo folder; Construct never installs it. Recordings they already have can be compared without it
   (step 3).
2. **Two runs.** `construct_netlogo_run` twice with two seeds (say 7 and 8), or once per setting if the user moved
   one. Keep each recording's path.
3. **Side by side.** `construct_netlogo_draw` with both recordings and labels ("seed 7, seed 8" or "2.5%, 6%"): A on
   the left, B on the right, one time scale (the longer run's), every label and count marked with its run, one data
   lock over both. Up to eight recordings stand left to right. MEDIA line in the reply. For a sense of scale: in
   Virus on a Network with seed 7, a spread chance of 2.5% dies out by tick 10 and 6% runs to tick 972.
4. **Read the difference.** Ask the user what differs and what is the same. Answer from `construct_inspect` (each
   run's seed, ticks and counts). Runs side by side have no landmarks and are drawn whole.
5. **Many runs.** `construct_netlogo_run` with N seeded runs (start with 10) and its comparison. Name the counts to
   record in `reporters`, or the summary has only the number of turtles: for Virus on a Network, `["count turtles
   with [infected?]", "count turtles with [resistant?]"]`. Read the outcome summary it returns to the user in plain
   words: what held across the seeds, what varied, and how far apart the runs ended. Do not round away a wide spread:
   that spread is the finding.
6. **For a lesson.** Printed (Cmd/Ctrl+P), the side-by-side page is a one-page worksheet with three questions;
   *Cite this run* gives the model, NetLogo's version, the seeds and the ticks.

**What next:** `16-netlogo-film-and-plates.md`, `12-netlogo-viral-marketing.md`.

## Notes

- Needs the user's own desktop NetLogo 7 (with the Java runtime it runs on) to make new runs; drawing and comparing
  recordings the user already has needs no NetLogo.
- A seed makes a run repeatable in the same NetLogo version; it is not a measure of the model's typical behaviour.
  Many seeds are.
- Library models are © Uri Wilensky and co-authors, under CC BY-NC-SA 3.0. A construct drawn from one carries the
  model's credit (as its Info tab asks) and that licence note: non-commercial, share-alike. Never bundle, copy into a
  shared folder or redistribute the library model itself; the user runs it from their own NetLogo.
