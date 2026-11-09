---
title: See flocks form in time
summary: Run NetLogo's Flocking and see each bird's track rise with time, random near the floor, flowing in streams higher up.
group: Simulations
needs: netlogo, browser
time: about 15 minutes
status: ready
---

## Prompt

Teach me to run NetLogo's Flocking model with Construct and see flocks form in time, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/13-netlogo-flocking.md"). Start by checking that my NetLogo is ready.

## Steps

1. **NetLogo first.** Ask whether desktop NetLogo 7 is installed; the model comes from the user's own Models Library.
   If NetLogo isn't found, ask where it is installed and have the user set it in Settings → Plugins → Construct →
   NetLogo folder; Construct never installs it.
2. **The model in one line.** Each bird follows three rules (keep apart, align with neighbours, stay close), and
   nobody leads. Flocking never stops on its own, so a run needs a length.
3. **One run.** `construct_netlogo_run` for the library model "Flocking", one run, seed 7, about 1000 ticks. Put the
   MEDIA line in the reply (or `construct_build` the scene it wrote). The view is space-time: the floor is the world,
   height is ticks, and each bird's track rises with time (up to 150 birds, chosen evenly).
4. **How to read it.** Near the floor the tracks wander every way; higher up they lean together into parallel
   streams: flocks. Ask the user to drag the replay bar and press **H** and **L**.
5. **The window.** Order forms early and then holds, so the construct is drawn from tick 0 to just after the flock
   aligned, and its title says which ticks. `construct_inspect`: the `window` fact gives the alignment (0 every way,
   1 all one way) at the start and at the window's end. Read the numbers to the user.
6. **The whole run.** `construct_netlogo_draw` on the same `run.jsonl` with the window `whole`, no NetLogo needed.
   Show both MEDIA lines and ask which reads better, and why the window was chosen.
7. **Try another.** Another seed, or a setting such as vision moved, compared side by side: `15-netlogo-compare-runs.md`.

**What next:** `14-netlogo-fireflies.md`, `16-netlogo-film-and-plates.md` (the flock as a film in Blender).

## Notes

- Needs the user's own desktop NetLogo 7 (with the Java runtime it runs on).
- A long run of many birds is sampled to stay light (about 18,000 line segments at most); the `sampling` fact says how.
- Library models are © Uri Wilensky and co-authors, under CC BY-NC-SA 3.0. A construct drawn from one carries the
  model's credit (as its Info tab asks) and that licence note: non-commercial, share-alike. Never bundle, copy into a
  shared folder or redistribute the library model itself; the user runs it from their own NetLogo.
