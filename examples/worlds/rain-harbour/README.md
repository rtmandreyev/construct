# Rain Harbour, a night street

A game level made in Hermes from one concept picture: 60 m of a rain-soaked night street in an invented harbour
district, its towers, its bilingual neon signs and one drivable hero car. 21 constructs, placed 50 times. The
constructs were made in rounds, each judged by a fresh critic. Then the whole world ran 12 rounds of its own
against the picture. Built by GPT-6.1 Sol in Hermes Desktop with the Construct plugin, 8–9 November 2026.

<p align="center">
  <img src="hero.jpg" width="95%" alt="Rain Harbour in lines of light: a long wet street between stacked towers, cyan and magenta neon signs in English and Chinese on both sides, the yellow hero car at the front left, the skyline behind">
</p>
<p align="center"><sub>The picture's own shot, low down the street. Open the world in Hermes (<b>Worlds</b> on the
Constructs page) or with <code>construct build examples/worlds/rain-harbour/world.json</code>.</sub></p>

## The ask

One message, with the concept picture attached (an AI-generated picture, the requester's own; it is not published
here):

> Make a Construct world from this concept picture: a game level, a rain-soaked cyberpunk street at night.
> Masterpiece quality: it should be usable in a game as it comes out, and good enough to show in a video.
>
> What to build: one street block, about 60 m of street with its pavements, kerbs and drains, the buildings on both
> sides and the skyline behind them. Real sizes throughout, built as separate pieces a level designer can reuse: a
> building used twice is one construct placed twice. […] The neon signs carry the picture's look, its colours and
> placement, but every sign must say something real and readable, never the AI letter-noise in the picture. Invent a
> coherent district and write the signs for it […] in English and real Chinese characters that mean what they say.
> ONE car only: the yellow car in the front left, the hero car. Design it as a real drivable game vehicle, the size
> of a real sports car, with doors that open, wheels, and its own tail lights. […]
>
> How to make it: plan the pieces first and tell me the plan […], then go straight on and build everything. Build
> each missing construct in masterpiece mode in its own subagent, with a critic each round. Then judge the whole
> world against the picture and fix what it finds.

## What it made

| | |
| --- | --- |
| Constructs | 21, placed 50 times: a building used five times is one construct |
| The street | 60 m of road, pavements, kerbs, drains, wet patches and the ground under it all |
| Buildings | Service Tower ×5, Offset Balcony Hotel ×5, Tide Relay Tower, Terrace Exchange, Service Loft, Far Signal Tower ×2 |
| Signs | RAIN HARBOUR / 雨港, NIGHT VOYAGE NOODLES / 夜航面馆, HARBOUR HOTEL / 港湾旅馆, BLUE LINE ELECTRONICS / 蓝线电器, PEACE OF MIND PHARMACY / 安心药房, NIGHT MARKET / 夜市, a convenience store, RAIN HARBOUR ROAD 08 / 雨港路 08 |
| The car | AURIC, a two-door coupé at a real sports car's size: doors that swing 65°, four wheels, tail lights |
| Street props | bollards ×6, street lamps ×2, bins ×2, a water vending machine, cable spans ×3 |
| Size | 3,250 parts placed; 93,868 lines and 116,246 triangles on the page; 4.7 MB with its pictures |

The district is invented, so every sign was written for it: the hotel, the noodle bar and the pharmacy are named in
English and in Chinese that says the same thing. The sign artwork was drawn for this world (marked
`generated-decorative`). Only the 60 m length was given; every other size is designed, not surveyed, and each part
says so (press **P**).

<p align="center">
  <img src="car.jpg" width="49%" alt="AURIC, the yellow hero car, close: its long bonnet, the doors' shut lines, the wheels and the tail lights">
  <img src="signs.jpg" width="49%" alt="Under the signs: the RAIN HARBOUR district fascia and the hotel blades overhead, looking up between the towers">
</p>
<p align="center">
  <img src="solid.jpg" width="49%" alt="The same street in the solid view: grey towers, the coloured sign faces and the yellow car">
  <img src="car-solid.jpg" width="49%" alt="AURIC in the solid view: yellow body, magenta tail lights, its wheels and rear wing">
</p>
<p align="center"><sub>Its own views: the car close, under the signs, and the street and the car in the solid view (S),
where the car is yellow. The light view keeps Construct's house palette.</sub></p>

## How it was made

**1. The plan.** Sol listed what the picture holds and what was worth making: each distinct building, sign and prop
once, placed as many times as the street needs. It said the plan and its cost and went straight on.

**2. The constructs, each in its own builder.** Each missing construct was built by its own subagent, in masterpiece
mode: a scene, a build, a packet of review pictures, a fresh critic, a recorded verdict, the fixes, round after round
until the stop rules (12 rounds; two in a row that do not beat the best; two hours of the builder's own time). Small
repeated props ran fewer rounds, since they are seen small. Several builders ran at once.

| Construct | Rounds | Last verdict |
| --- | ---: | --- |
| AURIC, the hero car | 12 | improve |
| Offset Balcony Hotel | 12 | good |
| Service Loft | 12 | good |
| Far Signal Tower | 12 | (stopped by its own ceiling) |
| NIGHT MARKET / 夜市 | 12 | improve |
| HARBOUR HOTEL / 港湾旅馆 | 11 | good |
| Convenience store, PEACE OF MIND PHARMACY, BLUE LINE ELECTRONICS, water vending | 9–10 | good |
| RAIN HARBOUR ROAD 08, RAIN HARBOUR / 雨港 | 6–8 | outstanding |
| The street, the bin, the noodle bar, the Tide Relay Tower, the Terrace Exchange | 6–8 | good, the street improve |
| Service Tower (placed five times) | one critic's pass, repaired in the world's rounds | good |
| Bollard, cable span, street lamp | 3–4 | good, the bollard improve |

**3. Placed at real size.** `construct_world` stood the bollards, lamps, bins and the vending machine on the
pavements, and set the buildings, the signs against their façades and the car on the road by their coordinates, all at
scale 1.

**4. The world's own rounds.** Then the whole world ran masterpiece rounds against the concept picture, one fresh
critic a round judging the world's packet (its named views beside the picture): composition, scale, what is missing,
depth, honesty. A round that lost put the world and its constructs back. The first eight rounds stopped at the
two-hour ceiling, still improving; on request the run was given 90 more minutes (`rounds extend 90`) and went on to
the 12-round cap.

| World round | Kept? | What changed |
| --- | --- | --- |
| 1–8 | 2, 4, 5, 7, 8 kept; 3 and 6 lost and put back | the wet foreground, a skyline that opens at the vanishing point as the picture's does, the distant tower group, the signs' hierarchy, the car's yellow, the stepped tower on its legs |
| 9 | kept | the car's yellow paint on its body (judged in the solid view), the hotel's double-sided blade signs |
| 10 | lost, put back | a façade-depth change that flattened the towers |
| 11 | kept | a 24-second assembly order, a tighter car view |
| 12 | kept | shop fittings in the lower floors, the bins' hinges and plinths, small things on the pavement |

Final verdict: **good**, 21 of 27 (silhouette, proportions, identity, depth, composition and density 2 of 3;
assembly, motion and honesty 3 of 3). 204 minutes of authoring, 59 of critics, for the world's rounds alone.

## Still open

What the last critic wrote, kept as it is, so the next person knows where to start:

- the matched street view still lacks a layered, overlapping cluster of distant towers;
- the near buildings keep regular parallel walls and repeated balconies where the picture has asymmetric masses;
- the cyan and magenta reflections on the road read as rectangles, not a wet road (no wet surface in Construct yet);
- the distant tower faces are sparse;
- the car's raised wing and narrow cabin read more like a track car than the picture's closed coupé;
- the three hotel blades repeat.

Six contact warnings remain where the cables meet the façades: Construct has no wall mount yet, so a cable fixed to
a wall touches it.

## Use it

- **In Hermes:** Worlds → Rain Harbour. Arrange it by hand, add your own constructs, save views, export it.
- **In a game engine:** `construct export examples/worlds/rain-harbour/world.json --out level.glb --pieces glued` gives
  a Godot map: the street and buildings fixed, the car's doors on their hinges. Every placement is a named group.
- **In Blender:** import `world.json` with the Construct add-on, or the exported `.glb`.
- **As a starting point:** every construct is its own folder under `constructs/`, with its own record. Place the
  hotel or the car in a world of your own.

## Credits

Made by GPT-6.1 Sol in Hermes Agent with the Construct plugin, from a concept picture supplied by the requester.
The district, its names and its signs are invented; the sign artwork was drawn for it. Apache-2.0, as the rest of
Construct.
