---
title: A run as a film or printed plates
summary: A NetLogo run as a film in Blender, every agent as moving light, or as a stack of printed plates that replays it in your hands.
group: Simulations
needs: netlogo, blender
time: about 20 minutes, then the render
status: ready
---

## Prompt

Teach me to turn a NetLogo run into a film or into printed plates with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/16-netlogo-film-and-plates.md"). Start by asking me which run to use.

## Steps

1. **A recording.** Ask which run: one from `12`, `13` or `14` (its `run.jsonl` path is in that run's result), or a
   new one with `construct_netlogo_run` (if NetLogo isn't found, ask where it is installed and have the user set it
   in Settings → Plugins → Construct → NetLogo folder; Construct never installs it). Flocking and Fireflies make good
   films; Simple Viral Marketing and Virus on a Network make good plates.
2. **Is Blender here?** `construct_start()` with no arguments lists the programs it finds. The film needs Blender;
   the plates do not. Construct never installs either.
3. **The film's scene first.** `construct_command(argv=["netlogo-film", "<run.jsonl>", "--blend", "run.blend"],
   project=<id>)`: ready in under a minute. Every agent at every tick as moving light with a trail, in its own NetLogo
   colours, each link while it lasts, the patches as a floor, 30 ticks a second, without sound. Nothing is sampled.
   The user opens it in Blender (with the Construct add-on) and presses play.
4. **The film.** `construct_command(argv=["netlogo-film", "<run.jsonl>", "--out", "film.mp4", "--size", "1920x1080"],
   project=<id>)`. Warn first: about a second a frame on a laptop GPU. `--from` and `--seconds` take a part of the run;
   `--trail 0` for no trails (Fireflies). It returns a `job_id`: follow it with `construct_job`, then put the MEDIA
   line in the reply.
5. **Plates you can hold.** `construct_command(argv=["netlogo-plates", "<run.jsonl>", "--out", "plates", "--plates",
   "6"], project=<id>)`, or `"--at", "0,20,40,68,120,300"` for chosen ticks. For Fireflies put the plates `--at` the
   landmark ticks and a few ticks after each (`construct_inspect` gives them): plates spaced evenly miss the flashes.
   Each plate is one moment, keyed with pins so they stack in order: building the stack replays the run. For
   Fireflies add `"--state", "hidden?", "--tall", "false"` so the flashing ones stand tall. `--size` sets the world's
   longer side in mm (default 100).
6. **What they get.** In `plates/`: the plates, the pins and sleeves, and `KEY.md`, a key card naming each plate, the
   model and its data lock. Tell them to open the plates in their slicer and print one first.
7. **A 3D model too.** `construct_netlogo_draw` on the recording with `model_3d: true` (solids and a glb): the run as
   named parts in its own colours, and the Blender add-on's Build slider replays it (see `05-blender.md`).

**What next:** `08-film-to-music.md` (a construct to music), `15-netlogo-compare-runs.md`.

## Notes

- Needs the user's own desktop NetLogo 7 (with the Java runtime it runs on) for a new run, and Blender for the film.
- Print one plate and a pin before the rest: how tightly pins fit is a matter of the printer and the slicer.
- Library models are © Uri Wilensky and co-authors, under CC BY-NC-SA 3.0. A film, plates or model from one carries
  the model's credit (as its Info tab asks) and that licence note: non-commercial, share-alike. Never bundle, copy
  into a shared folder or redistribute the library model itself; the user runs it from their own NetLogo.
