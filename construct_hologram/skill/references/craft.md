# Drawing craft: what makes a construct read

A clean audit says a construct stands up; it does not say it reads. The strongest constructs
made with this skill were not the ones with the most code or the most effort. They were drawn
with a few habits that every model can follow. Measured on the same skill, the same prompts and
the same time, the strongest runs against the rest:

| | strongest runs | the rest |
|---|---|---|
| distinct line weights | 8–19 | 0 (the defaults) |
| parts with a dark, depth-writing fill | 9–128 | 0–7 |
| identity parts | 22–125 | 10–29 |
| independent critic | every round, each answered by a refine pass | some runs never |

Five rules follow, in the words of the scripts that drew them. Read them with the examples that
ship with this skill (its `examples/` folder): `leica-m3.json`, `open-reel.json`,
`sea-cliff.json`, `juggernaut-et7.json`, `porsche-911-964.json` and `sagrada-familia.json`.

## 1. A line-weight hierarchy

Three weights, and the eye reads the object in that order:

| layer | `look.weight` | also |
|---|---|---|
| identity: the lines that name it | 1.1–1.5 (a signature line up to 2.6) | `glow` 0.3–0.7 |
| structure: the form | 0.8–0.9 | |
| detail: seams, lenses, slats | 0.55–0.65 | `alpha` 0.25–0.6: faded |

```python
curve('side-window-frame', window, 'identity', 'x', look={'weight': 1.5})
curve('door-seam', seam, 'detail', 'x', look={'weight': .8})
curve('rear-demister-' + str(k), [[-w, y, z], [0, y + .008, z], [w, y, z]], look={'alpha': .25, 'weight': .4})
curve('rear-lightbar', bar, 'identity', look={'weight': 2.6})
```

Without weights every line is the same line, and nothing is first.

## 2. A dark fill under a faint contour; feature lines on top

Every visible main surface (a body, a roof, a hood, a bumper, a glasshouse, a tower's mass)
keeps a **faint contour wire** over its dark, depth-writing fill: `look` weight about 0.4–0.5,
alpha about 0.5–0.6. That fine wire following the surface is what makes it read as sculpted;
without it the surface is a flat dark shape and the construct looks like a cardboard mockup.
Then draw the feature lines yourself, heavier: roof rails, lower edges, bumper faces, window
frames.

```python
# The cabin keeps its faint surface wire over a depth-writing shell; its contours are authored on top.
by['glasshouse']['look'] = {'fill': 'dark', 'weight': .45, 'alpha': .55}
for sg in [-1, 1]:
    cv('roof-rail-' + str(sg), rail(sg), 'identity', look={'weight': 1.2})
by['front-bumper']['look'] = {'fill': 'dark', 'weight': .45, 'alpha': .55}
cv('front-lower-edge', lower_edge, 'identity', look={'weight': 1.1})
```

Hide only true construction scaffolding: helper volumes, guides, a section stack that is not a
surface. `line: "none"` is for occluders and backings (a dark panel behind a grille, a plate
that hides the far side), never for a visible main surface; `check` warns `bare-surface` when
one is. A critic that calls a surface's faint contour "construction lines" is wrong: it is the
surface.

The dark fill also hides what is behind it, so the far side stops showing through.

```python
# Main masses recede; foreground architecture and silhouettes dominate.
for x in parts:
    if x['role'] == 'mass':
        x['look'] = {'fill': 'dark', 'alpha': .42, 'glow': .08, 'weight': .65}
```

## 3. Sub-volumes per feature, each conforming to its neighbours

Not one body: a volume for each feature, shaped to the ones it meets. Wings that rise above the
bonnet and seat the lamps; a bowl behind each lamp; arches that follow the tyre, with the
body's sections lowered around them.

```python
# Smooth, substantial front wings seat the lenses and sit higher than the bonnet.
add('front-fender-' + str(sg), 'mass', {'type': 'loft', 'sections': secs, 'round': 1}, [sg * .615, 0, 0], 2,
    look={'fill': 'dark', 'weight': .65, 'alpha': .75})
# Complete lamp bowls behind the lens.
add('headlamp-bowl-' + str(sg), 'mass', {'type': 'sphere', 'radii': [.157, .165, .16]}, [sg * .62, .735, 1.83], 2,
    look={'fill': 'dark', 'weight': .5, 'alpha': .7})
# Conform the lower body's arches to the tyres without deleting structure through the car.
for s in body_sections:
    if abs(s[0] - zc) < R * 1.10:
        s[2] = max(.205, R + math.sqrt((R * 1.10) ** 2 - (s[0] - zc) ** 2))
```

A building works the same way: a foot under each tower, a deck under each lantern, the gables
standing on the walls.

## 4. Density where identity lives, and detail everywhere

Two looks, and a construct needs both:
- **at hero scale, one clear object:** the silhouette and the identity features read first;
- **up close (4×), every region still has something true to find:** seams, panel lines,
  louvres, fixings, tracery, coursing. A bare face or an empty corner is unfinished work.

Spend parts on what names the subject, three to five times more than on the rest: lamp rims
and lenses, louvres and slats, window rows, spires, tracery. Keep the masses simple in shape,
not empty: they carry their faint contour and their true seams. Clutter is detail that is not
true to the subject or that drowns the silhouette; it is not detail as such.

```python
for r in [.132, .146]:          # two concentric rims on each round lamp
    curve('lamp-rim-' + suffix + '-' + str(r), rim(r), 'identity', look={'weight': 1.2})
for dy in [-.07, 0, .07]:       # and the refractor lines inside, faint
    curve('lens-' + suffix + '-' + str(dy), lens(dy), stage=4, look={'alpha': .35, 'weight': .5})
for k in range(12):             # twelve slats on the engine-lid grille
    curve('grille-slat-' + str(k), slat(k), 'detail', stage=4, look={'weight': .75})
```

## 5. Checkpoint, critic, then a refine pass that answers the defects in order

Every round: save a checkpoint of the scene, run the independent critic
(`python3 TOOLS critique scene.json --reference side=photo.jpg ...`), then write a refine
pass that takes the ranked defects one by one, most severe first, and says which one each change
answers. Re-measure positions from the photos rather than nudging by eye.

```python
"""Second geometry pass responding to independent critic's ranked defects."""
d = json.loads(Path('checkpoints/round-01/scene.json').read_text())
# Re-seat headlights at measured wing-end height.
for p in parts:
    if p['id'].startswith('headlamp-'):
        p['at'][1] -= .057; p['at'][2] += .055
# Spatial 12-point star: three interlocking axes, no flat gear-like rosette.
...
d['authoring']['review_rounds'] = 2
```

Keep each round's reasoning in the comments: the next round, and the next reader, can see what
was answered. A changed scene makes the critic's record stale; critique the version you deliver.

## What does not help

- More code. The strongest generators were 160–420 lines; the rest were longer.
- One body with everything on it. Sub-volumes read; one skin reads as a blob.
- Every line at the default weight, every wire showing.
- Main surfaces with no contour at all (`line: "none"`): a dark cardboard mockup.
- Bare faces and empty corners left for "later": up close they are the unfinished work.
- Calling a construct finished because the audit passes. A clean audit is not a good picture.
