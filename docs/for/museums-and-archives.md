# Construct for museums and archives

A reconstruction in which every part says how it is known: measured and published, traced from a drawing, read from
a photograph, described in a document, or designed, and whether a design was made to a stated requirement. A part's
size and its shape are judged apart. The sources are cited by URL, the labels come only from recorded facts, and the
critic's verdict and what it still found stay in the record. Press **P** and a visitor sees the evidence and the
guesses in different colours.

<p align="center"><a href="https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/construct.html?mode=provenance"><img src="../media/tompion-provenance.jpg" width="60%" alt="Tompion's clock in the provenance view: the case's outline in cyan, size verified; the rest in shades of amber; the legend counts each kind and the caption names what is known and from where"></a></p>
<p align="center"><sub>Tompion's year-going clock in the provenance view: the case carries the Royal Collection's dimensions
(cyan); the rest is read from photographs or designed, in shades of amber. <a href="https://rtmandreyev.github.io/construct/examples/tompion-year-going-clock/construct.html?mode=provenance">Open it</a>.</sub></p>

## A collection object: Tompion's year-going clock

The request asked for Thomas Tompion's year-going longcase clock made for William III, now in the Royal Collection,
with "its real dimensions, materials and features, each recorded as a fact with its source", and every part's size
and shape known apart. DeepSeek V4.1 Flash built it in masterpiece mode through Hermes.

**What it read:** the Royal Collection's record of the clock (RCIN 57800) and two of its photographs, the record of a
sister equation clock (RCIN 2754), a Britannica entry on Tompion and a Christie's lot essay on another of his clocks.

**What the record says,** in 23 facts, each with its source:

| Fact | Value | How it is known |
| --- | --- | --- |
| height, width, depth | 2.23 × 0.455 × 0.236 m | verified · Royal Collection, RCIN 57800 |
| case | burr walnut veneer | verified · RCIN 57800 |
| hands | blued steel | verified · RCIN 57800 |
| duration | one year on a single winding | verified · RCIN 57800 |
| dial plate | 0.305 m (12 in) square | inferred · Christie's essay on a sister clock |
| movement plates | three brass plates, the year-going train between them | inferred · the sister clock, RCIN 2754 |

The overall size and the materials are documented; the case's mouldings were read from the photographs; the
movement's wheels behind the dial were designed from Tompion's practice, and they say so. Twelve rounds, each judged
by a critic that never saw the authoring; its last verdict is *improve*, with its reasons kept in the scene: the arch
above the hood is a thin hoop, and the movement does not read as one. [The clock, end to end →](../END-TO-END.md)

## A place, house by house: Stortorget

[Stortorget](../../examples/worlds/stortorget/), Stockholm's old square at its Christmas market, was made in Hermes from
one photograph as a world of 13 constructs: eight houses researched one by one, the square, one market stall placed
41 times, the spruce, a lamp and a granite block. Its page keeps the documented and the inferred apart:

- **Documented,** each cited by URL in the scenes: Schantzska huset (No. 20) and Seyfridtzska huset (No. 18) are the
  pair; the city's heritage record gives No. 20's front as of 1650, its portal by Johan Wendelstam, and No. 18's
  medieval masonry with its present front from the early eighteenth century; Börshuset, by Erik Palmstedt, was
  inaugurated in 1776; a 2022 report counted 41 stalls.
- **Inferred:** no reliable published heights of the houses were found, so every height, footprint, roof behind the
  front and the stalls' layout is read from the photograph, and each part says so. Two addresses are marked
  uncertain. The stall's name, *Stortorgets Julbod*, is invented in real Swedish and said to be.

<p align="center"><img src="../../examples/worlds/stortorget/gables.jpg" width="80%" alt="The red and orange gables of Stortorget 20 and 18 from below in the solid view: their scrolls, white trim, windows and wall anchors"></p>
<p align="center"><sub>Nos. 20 and 18 from below, in the solid view. Their fronts are documented; their heights, which no
source gives, are read from the photograph.</sub></p>

## Asked, and answered

In Hermes the record can be questioned in plain words. After the [Villa Savoye](../../examples/villa-savoye/) was built
from its published plans, the request was *"What do we actually know about this house, and what did you have to
design? Show me."* The answer was the provenance view (blue for what was traced from the plans, amber for what was
inferred) and a table of every choice: the pilotis' 320 mm diameter, the floor and roof levels, a 6.35 m curve for
the entrance that is *not* a recovered turning circle. Its own summary: "a plan-led, source-linked architectural
reconstruction, not an exact 1931 digital twin". [The walkthrough →](hermes-walkthrough.md#4-what-do-we-actually-know)

<p align="center"><img src="../media/hermes-villa-known.jpg" width="90%" alt="The agent's table, What I had to choose or approximate: for the pilotis, ribbon windows, ramp, solarium, curved entrance, stair and interiors, and planting, the evidence and the reconstruction choice"></p>

## What the colours say

| Colour | Meaning |
| --- | --- |
| white | verified, size and shape |
| cyan | size verified (a published dimension), shape traced or inferred |
| violet | shape verified (a drawing, a measurement, a dataset) |
| blue | traced from an orthographic drawing; strong blue once a silhouette comparison with it passed |
| amber, pale to deep | inferred: designed, described in a document, seen in a picture, or seen and checked against a verified fact |
| green | supplied by the person who asked |
| magenta, dotted | decorative, not a claim |

The legend counts the parts of each kind, names the sources behind the verified ones, and counts designed parts made
*to a requirement* (a function a document gives, a feature the request asked for) apart from free design. The
caption says what kind of thing it is: DOCUMENTED RECONSTRUCTION, APPROXIMATE RECONSTRUCTION, GENERIC
RECONSTRUCTION, ORIGINAL DESIGN, or RECORDED RUN for a NetLogo model's run. [Saturn](https://rtmandreyev.github.io/construct/examples/saturn/construct.html?mode=provenance)
is a short lesson: 54 of its 127 parts, the globe and the rings among them, come from published measurements and show
white; its cloud belts are designed and show amber.

## The record behind it

- **Facts and sources** live in the scene, a JSON file you can read, cite and keep; labels are made only from facts,
  so a construct never labels what it does not know.
- **The audit** (`construct check`) refuses broken scenes and warns when a number in the text contradicts the fact it
  names (`stale-number`), when a scene changed after its critic judged it (`critic-stale`), and when a part stands on
  nothing or leans off what holds it.
- **The critic stands apart.** In masterpiece rounds a fresh critic judges renders, reference pictures and the request,
  never the author's reasoning; each packet is sealed, and a recorded blind verdict is not rewritten.
- **A note on its evidence** (`authoring.provenance_note`) appears under the caption in the provenance view, for what
  the colours alone would understate.

## Try it

Open any construct in the [gallery](https://rtmandreyev.github.io/construct/) and press **P**, or add `?mode=provenance`
to its address. In Hermes, ask *"what is known about it, and from where?"*: `construct_inspect` reads the parts by
certainty, the facts and sources, the joints and the critic's verdict from the construct's own record. For an exhibit,
a construct's page is a single file that needs no network: copy it to the exhibit's computer and open it.

## Good to know

- **A reconstruction, not a survey.** Where no source gives a size, it is read from a photograph or designed, and the
  part says so. Before using a construct as a measurement, check what **P** shows.
- **Credit travels with the record.** Each source is cited with its credit. Stortorget's photograph is included
  unchanged as its `reference.jpg` under its own licence, CC BY-SA 4.0, credited to its photographer on the world's
  page.
- **Not yet:** pages for a museum screen that loop by themselves and open to a touch come in a later release.

## Go deeper

- [The Measured Light style](../STYLE.md#how-each-part-is-known): the provenance view and its colours
- [The scene contract](../../CONTRACT.md): how certainty, sources and facts are written
- [How it is made](../HOW-IT-IS-MADE.md): masterpiece rounds and the critic
- [In a classroom and a museum](../CLASSROOM.md): a NetLogo run as an exhibit
