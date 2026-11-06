---
title: Watch adoption rise
summary: Run NetLogo's Simple Viral Marketing from your own Models Library and watch adoption rise through the network, tick by tick.
group: Simulations
needs: netlogo, browser
time: about 15 minutes
status: ready
---

## Prompt

Teach me to run NetLogo's Simple Viral Marketing model with Construct and watch adoption rise, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/12-netlogo-viral-marketing.md"). Start by checking that my NetLogo is ready.

## Steps

1. **NetLogo first.** Ask whether desktop NetLogo 7 is installed. The model comes from the user's own installed
   Models Library; nothing is downloaded or bundled. If `construct_netlogo_run` cannot find NetLogo, say so and stop:
   Construct never installs it (NetLogo Web cannot run it).
2. **The model in one line.** People on a social network and one product: some adopt from advertising, others
   because their neighbours have. The question: how fast does it spread, and how far?
3. **One run.** `construct_netlogo_run` for the library model "Simple Viral Marketing", one run with a fixed seed
   (say 2026) so it can be repeated. Put the MEDIA line it returns in the reply (if it returns only a scene,
   `construct_build` it). Nothing in the model is changed: the run is recorded as it is.
4. **How to read it.** The network is on the floor; each person rises to the tick they adopted, and each link climbs
   from the earlier adopter to the later (a steep link joins two people who adopted far apart in time). Ask the user
   to drag the replay bar, press **H** (How to read it), **L** (the legend) and **P**: every data part is verified
   against the recording. The dashed frames mark where adoption was half way and 90% of the way, from the run itself.
5. **Ask what they see.** Where does it start, where does it stall, who adopts last? Answer from
   `construct_inspect` (the model, NetLogo's version, the seed, the ticks, the counts), never from memory.
6. **Stretch the start.** Most of a cascade happens early. Redraw the same recording, without running NetLogo again:
   `construct_netlogo_draw` on its `run.jsonl` with the view `network-time`, the state `adopted?` and time `sqrt`.
7. **Keep it.** The How to read it panel offers the counts as CSV and *Cite this run*. Printed (Cmd/Ctrl+P), the page
   is a one-page worksheet with three questions.

**What next:** `15-netlogo-compare-runs.md` (another seed, or many), `16-netlogo-film-and-plates.md`.

## Notes

- Needs the user's own desktop NetLogo 7 (with the Java runtime it runs on).
- Library models are © Uri Wilensky and co-authors, under CC BY-NC-SA 3.0. A construct drawn from one carries the
  model's credit (as its Info tab asks) and that licence note: non-commercial, share-alike. Never bundle, copy into a
  shared folder or redistribute the library model itself; the user runs it from their own NetLogo.
- The data is locked: an art pass may relabel or restyle, never move a point (`construct_check` refuses it).
