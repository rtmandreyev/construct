# Worlds: constructs placed together

A world places whole constructs in one scene: your chair, clock and piano in your house, your cars under it, a ship
overhead, a planet in the sky. It's a room, a street, a city, or a game map. Each placed construct stays whole: its
parts, its sources, how each part is known, its critic's verdict and its joints are its own, under its placement's
id (`eames/seat-shell`, `vespa/photo-front`). A world is not a bigger construct. A construct keeps a construct's
budgets and checks, and a world has its own, for many constructs at once.

```json
{"format": "construct-world", "version": 1, "id": "my-villa", "title": "My Villa Savoye",
 "placements": [
   {"id": "villa", "construct": "villa-savoye"},
   {"id": "eames", "construct": "eames-lounge-chair", "on": "villa/living-floor-east", "at": [3.2, 0, -1.5], "yaw": 30},
   {"id": "fj62", "construct": "toyota-land-cruiser-fj62", "on": "villa", "at": [4, 0, 6], "yaw": 90},
   {"id": "saturn", "construct": "saturn", "sky": {"diameter_m": 1.20536e8, "of": "globe", "distance_m": 3.844e8,
                                                   "azimuth": 120, "elevation": 25}}],
 "presentation": {"views": [{"id": "salon", "label": "Salon", "target": "villa/living-floor-east", "pitch": 30}]}}
```

Build and export it as you would a construct:

```sh
python3 construct_hologram/cli.py check my-villa.json                           # what overlaps, collides or floats
python3 construct_hologram/cli.py build my-villa.json --out out/my-villa        # the page, live, every placement whole
python3 construct_hologram/cli.py export my-villa.json --out my-villa.glb --pieces glued   # one file for Godot or Blender
```

## Examples

Four worlds ship in [examples/worlds](../examples/worlds/), made of the constructs the plugin ships. In Hermes,
`construct_world` with `op: new` and `example` makes one the user's own.

| World | What it holds |
|---|---|
| [The shed, the Samba and the Vespa](../examples/worlds/the-shed/world.json) | The garden shed with its planned deck and log store, a VW T1 Samba by the log store, a Vespa GS 150 by the door, State Bench inside and Rietveld's Red-Blue Chair on the deck |
| [The Villa Savoye, lived in](../examples/worlds/villa-savoye-lived-in/world.json) | The salon with an Eames chair, a Tompion clock and two tables (designed for this world) carrying a Braun SK 4, a Revox A77, a Leica M3 and SERUM 2 / 61; a Jackson by the studio table; a Land Cruiser and an Aston Martin DB5 under the pilotis; KESTREL far off over the roof |
| [A street of landmarks](../examples/worlds/a-street-of-landmarks/world.json) | The Duomo di Milano, the Sainte-Chapelle and the Sagrada Família on one street at their real sizes, Neuschwanstein across it |
| [KESTREL at Saturn](../examples/worlds/kestrel-at-saturn/world.json) | KESTREL at work by Saturn's rings, the planet at its real size from about 350,000 km |

## Placements

| Key | What it does |
|---|---|
| `construct` | A scene's path (relative to the world's file), another world's path (a district in a city), or a name a resolver knows: the gallery's constructs, or the Hermes plugin's projects and stock constructs |
| `at` | metres. With `on`, x and z are on the host and y is a lift above its top |
| `yaw`, `rotate` | degrees: about up, then about x, y, z |
| `on` | an earlier placement (it stands on that placement's ground) or `placement/part-id` (on that part's top: a floor, a deck, a table) |
| `scale` | 1 is real size. Anything else is disclosed by the world's audit and wherever it is shown |
| `floating` | it's meant to hover: a ship, a hanging lamp |
| `sky` | `{diameter_m, distance_m, of, azimuth, elevation}`: far away, at its real angular size (a planet, a moon). `of` names the part `diameter_m` belongs to (Saturn's `globe`), so its rings and moons come at the same scale; without it, `diameter_m` is the whole construct's size. Never what a view fits |
| `note` | why it is there |

A world's `presentation.views` name its own views (`{id, label, target, yaw, pitch, distance, cutaway}`; `target` is a
placement or `placement/part-id`, such as a room's floor). The page shows them as buttons, after one for the whole
world and before one for each placement.

The solid view cuts away what stands between the eye and a view's target only when the view looks into something:
its target stands under another placement's part (a bench in a shed, a car under the pilotis), or its camera does
(a camera saved in a room). A view from outside, down a street or across a market, keeps its foreground: the
façades are what it shows. A view says otherwise with `"cutaway": true` or `false`.

The same construct placed many times is compiled once. A world can place worlds, up to eight levels deep: a city
holds districts, a district holds buildings, a building holds rooms. Ids join with `/` at each level. Coordinates
reach 1,000 km from the origin, and an optional `origin: {lat, lon}` ties the world to a place on Earth.

## What reads a world

- **The page** draws it like a construct.
  - The caption says how many constructs it holds.
  - Provenance (P) shows every part's evidence across the world, and the solid view (S) works too, and cuts away what stands between you and the room a view looks into.
  - A view frames each placement.
  - Every joint opens: the viewer keeps joint and motion poses in a texture, so a world's dozens of doors, lids
    and hinges are not limited to a construct's sixteen.
- **The world's audit** (and `construct check`) says:
  - when placements overlap;
  - when one runs into the construct it stands in: each of its parts is checked against the host's, all but the
    part it stands on, so a car parked under a house must clear the columns;
  - when a placement stands where another's door, lid or cowl opens (each joint's open pose is checked too);
  - when one stands on nothing, and when one isn't at real size.

  Each placed construct's own audit stays its own.
- **Exports:**
  - **glTF:** one file. Each placement is a group named after it. Each construct's own material map is merged in
    under its id. Every joint is in the `open` animation.
  - **Godot:** with `--pieces glued`, the world is a game map. Its fixed body stays put; doors, lids and wheels
    swing on their joints through `construct_joints.gd`.
  - **Blender:** the add-on imports a world (`.json`) with the usual build, open, metal and finish sliders.

## In Hermes

`construct_world` places, moves and removes constructs in a world from the chat, and shows each change live:

- `op: new` with a title and the construct that holds the rest;
- `op: place` with `construct`, plus `on`, `at`, `yaw`, `scale`, `floating`, `sky` or `note`; or `placements`, a
  list of these, placed together with one check and one rebuild;
- `op: move` and `op: remove` by placement id;
- `op: list`, with an id to list the surfaces things can stand on;
- `op: view` with an id, a label and a target: a named view, a button on the page (`remove: true` drops it).

In Hermes Desktop a world's card has **Arrange**: click a construct and drag it: it rides on whatever is under the
pointer (a floor, a table, a roof; a wall stops it; Alt keeps its level). Shift-drag or Q/E turns it, the arrows
nudge it, Page Up/Down lift it, Backspace puts it back; Duplicate and Remove are on its bar. What stands on it (on it, or on one of
its parts) goes with it, as a table carries what is on it. **Save** runs `/construct arrange <world> <changes>`
in the gateway, with no model turn: the world is checked with the moves, written back as each placement was
placed (absolute, or on its host), logged as the user's in `edits/log.jsonl` and rebuilt. `/construct undo <world>`
steps back one saved change, the agent's or the user's. Any world page does the same with A; outside Hermes,
`HOLO.arrange.changes()` gives the moves.

**Quality.** A world asked for from a picture or a description is made to a masterpiece's standard: each missing
construct in its own subagent, in masterpiece rounds with a fresh critic each round, and the whole world judged
against the picture at the end. In Hermes this takes an orchestrator subagent per construct, so it needs
`delegation.max_spawn_depth: 2` in Hermes's config. Say "fast" for one pass each, much quicker and cheaper.

What a world places comes from three sources:
- the user's own projects;
- the constructs the plugin ships;
- the whole gallery, fetched by name from this release on GitHub.

Each placed construct is copied into the world's folder, so a world travels whole and can be shared.
`construct_check` checks a world, and `construct_export` exports it, as they do a construct.

## Limits

| Budget | A construct | A world |
|---|---|---|
| Lines (page) | 48,000 | 400,000 |
| Triangles (page) | 48,000 | 400,000 |
| Triangles (solid, exports) | 200,000 | 2,000,000 |
| Joints | 16 | none (the viewer's texture holds them) |
| Placements | — | 4,096 |
| Extent | 500 m | 1,000 km |

A world's page grows with what it holds. The fifteen constructs of the Villa Savoye example come to about
140,000 lines and 150,000 triangles. Larger worlds (a city) will need what a construct page never needed:
- drawing each repeated construct once, instanced;
- leaving out what is off screen;
- far placements as outlines;
- loading in chunks.

The format already carries what these need: repeated placements of one construct, and placements that are
themselves worlds.
