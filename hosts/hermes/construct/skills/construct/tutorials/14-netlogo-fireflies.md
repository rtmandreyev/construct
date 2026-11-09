---
title: Fireflies falling into step
summary: Run NetLogo's Fireflies and watch a thin, ragged column open into wide plates as the swarm starts flashing together.
group: Simulations
needs: netlogo, browser
time: about 15 minutes
status: ready
---

## Prompt

Teach me to run NetLogo's Fireflies model with Construct and see the fireflies fall into step, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/14-netlogo-fireflies.md"). Start by checking that my NetLogo is ready.

## Steps

1. **NetLogo first.** Ask whether desktop NetLogo 7 is installed; the model comes from the user's own Models Library.
   If NetLogo isn't found, ask where it is installed and have the user set it in Settings → Plugins → Construct →
   NetLogo folder; Construct never installs it.
2. **The model in one line.** Each firefly flashes on its own clock and resets it when it sees a neighbour flash.
   Nobody conducts, yet the swarm can end up flashing together. It never stops on its own, so a run needs a length.
3. **One run.** `construct_netlogo_run` for the library model "Fireflies", one run, seed 5, 2000 ticks. Put the MEDIA
   line in the reply (or `construct_build` the scene it wrote).
4. **The pulse view.** One ring per tick, its area the share of fireflies flashing then. While they flash on their
   own the rings make a thin, ragged column; once they flash together, wide plates with nothing between. If the view
   chosen was not pulse, redraw with `construct_netlogo_draw` on the `run.jsonl`, view `pulse`, state `hidden?`.
5. **The landmarks.** The dashed frames mark the first tick half the swarm flashed at once, then all of it. Ask the
   user to drag the replay bar to each and press **H**. `construct_inspect` gives the ticks and the synchrony (0 each
   on its own rhythm, 1 all in step). With seed 5 in NetLogo 7.0.4 they were ticks 315 and 456; another version or
   seed may differ.
6. **The window.** The construct is drawn up to just after the swarm fell into step; the title says which ticks.
   `construct_netlogo_draw` with the window `whole` draws all 2000 ticks: the plates then go on to the top.
7. **Try another.** Another seed: does it always fall into step, and how soon? `15-netlogo-compare-runs.md`.

**What next:** `15-netlogo-compare-runs.md`, `16-netlogo-film-and-plates.md` (the swarm as a film, or printed plates).

## Notes

- Needs the user's own desktop NetLogo 7 (with the Java runtime it runs on).
- A colour that changes shows a state, not a rhythm: the pulse view reads a true/false variable (`hidden?` here).
- Library models are © Uri Wilensky and co-authors, under CC BY-NC-SA 3.0. A construct drawn from one carries the
  model's credit (as its Info tab asks) and that licence note: non-commercial, share-alike. Never bundle, copy into a
  shared folder or redistribute the library model itself; the user runs it from their own NetLogo.
