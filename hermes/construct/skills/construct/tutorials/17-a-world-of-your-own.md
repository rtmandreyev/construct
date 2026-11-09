---
title: A world of your own
summary: Your things together in one place at their real sizes, a house with its furniture and cars, a street, a game map, arranged by Hermes and by your own hand.
group: Worlds
example: the-shed
needs: browser
time: about 15 minutes
status: ready
---

## Prompt

Teach me to make a world with Construct, step by step, one step at a time and waiting for me between steps. Follow the Construct tutorial: skill_view("construct:construct", file_path="tutorials/17-a-world-of-your-own.md"). Start by showing me the shed and the things around it.

## Steps

1. **A world to start from.** `construct_world(op="new", example="the-shed")`; the MEDIA line in the reply. Say: five
   whole constructs (the shed with its planned deck, a VW T1 Samba, a Vespa GS 150, State Bench and Rietveld's
   Red-Blue Chair), each with its own record and joints, placed at real size; the buttons on the page are the world's views. Ask the user to press **P**: every part's evidence, across
   the world.
2. **Placed by asking.** Ask what of theirs should join it (one of their projects, or a shipped construct:
   `construct_start` lists them). `construct_world(op="list", world=..., id="shed")` gives the surfaces to stand on;
   place it with `op="place"` (`on`, `at`, `yaw`), then read the warnings aloud and fix each with `op="move"`.
3. **Arranged by hand.** In Hermes Desktop: **Arrange** on the world's card. Click a construct and drag it onto
   anything, a floor, a table, a roof; Shift-drag or Q and E turn it; the arrows nudge it; what stands on it goes with it. **Save**: the world is
   checked with the moves, saved and rebuilt, with no model turn. Wait while they try it, then
   `construct_world(op="list")` and say what moved (the world's `edits/log.jsonl` marks the user's moves as theirs).
   Outside Desktop the page does the same with A, and `/construct undo <world>` steps back.
4. **Name the views.** Ask which views they want ("by the door", "from the yard"): `op="view"` with a target (a
   placement, or a floor part). They become buttons.
5. **Take it elsewhere.** `construct_export(project=..., format="glb")` for Blender or a game engine, each placement a
   group; with `pieces="glued"` a Godot game map whose doors swing. Point at the other worlds:
   `construct_start` lists them (the Villa Savoye lived in; a street of landmarks; KESTREL at Saturn; Rain Harbour and Stortorget, each made
   from one picture), and **Worlds**
   on the Constructs page.
