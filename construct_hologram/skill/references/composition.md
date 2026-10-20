# Recognition and composition

A construct is recognised by its **silhouette**, its **proportions** and **two or three
identity features**, in that order. Neon on a wrong silhouette is still wrong.

## Before you write a part

1. **Proportions from facts.** Write the overall size and the ratios that matter (a
   lighthouse ~4× taller than its base is wide; a jewel case 142 × 125 × 10 mm; an LP
   0.30 m on a 0.46 m plinth). Inferred is fine; unstated is not.
2. **Silhouette.** Which outline would a child draw? Build that first as `mass` parts.
3. **Primary structure.** What holds it up, how it is divided (floors, bays, segments,
   joints). `structure` parts, few and clean.
4. **Identity features.** The two or three things that make it *this* thing: tonearm and
   grooves; banded tower and lantern; scalloped bell and trailing tentacles. Give them
   `role: identity`, real geometry and a camera view.
5. **Detail, deliberately.** Only detail that reads at the hero framing and helps
   recognition. Repeats (railing posts, windows, ribs) read as texture; keep them `detail`.
6. **Leave out** what does not help: interiors nobody sees, every bolt, decorative
   clutter. Simplify before adding.

## Choosing shapes

- Turned or round things → `lathe` (profile through the real changes of radius).
- Footprints, floor plans, gabled fronts, letterforms → `extrude`.
- Anything that bends: limbs, arms, cables, branches, tentacles → `tube` with a tapering
  `radius` list.
- Many identical things → `repeat` (radial for rings of things), symmetric creatures and
  vehicles → `mirror`.
- Bodies whose width and height both change along their length (car bodies, glasshouses,
  hulls, fuselages) → `loft`: one section per real change, back to front.
- Curved surfaces read through their rings and meridians: 8–16 meridians, rings at real
  profile changes; more lines are not more legible.

## Recipes by kind (adapt, do not copy)

- **Architecture**: footprint/elevation extrude or lathe for the main volume; roof shape;
  openings as planes or thin boxes in rhythm (`repeat`); one landmark (tower, dome,
  portal) as identity; a ground (rock, plinth, plan grid). Stage: ground → mass → roof and
  landmark → openings → light/annotations.
- **Manufactured object**: the housing as mass; working parts (platter, arm, blade, lid)
  as identity, each a separate part so it can move; small controls as detail. Show it in
  use (record on the platter, lid open) when that is recognisable.
- **Vehicle**: never a box body. Trace the side silhouette and the plan (top) outline first
  — from references when the car is a named model ([tracing](tracing.md)) — and loft the
  lower body through them: half-widths from the plan, sill and shoulder heights from the
  side, the sides leaning in (`half_width_top` about 0.9 of the bottom). Round the plan at
  the nose and tail with extra sections; the nose of most cars is far narrower than the
  cabin. The glasshouse is a second loft, narrower at the roof, from the windscreen base
  raked back. Wheels stand on the ground in arches on the body's side; lights at nose and
  tail as detail. The `vehicle` archetype (`params vehicle --variant wedge|coupe|sedan`)
  builds exactly this and is the quickest start.
- **Machine**: the frame, the moving assembly (with `spin`/`swing` at its real pivot), the
  power or light source as `data`.
- **Organism**: body volumes as ellipsoids/lathe; limbs as tapered tubes from real joints;
  `mirror` for bilateral animals, radial repeats for radial ones; gentle motion with
  `phase_step` ripples; never a perfectly rigid creature.
- **Fictional entity**: take the described features as `user_supplied` facts and design
  everything else as `inferred` (designed from the request); use `decorative` only for
  atmosphere. Label it fictional in the title.
- **CD / book / artwork carrier**: standard generic dimensions (inferred). A jewel case is
  a tray (inlay slot on its back, spine labels on its left face), a hinged lid carrying the
  booklet (`cover-front`), and a disc in the tray (`disc` slot, circle mask with the hole)
  that lifts and turns once. A book is boards, a rounded spine (`extrude`) with a flat
  spine face for its labels, a ribbed page block whose front carries the title-page labels,
  and a front board hinged on the spine. Name `anchors.front` and `anchors.spine`. Text
  comes from facts through labels; images through slots. Start from
  `examples/cd.json` and `examples/book.json`.

## Framing

The camera fits every part's boxes (decorative point clouds excluded). Choose `framing`
yaw/pitch that shows the identity features and the depth (≈25–40° yaw, 10–30° pitch);
add a view that targets the main identity feature and tour to it. A tall thin object wants
a lower pitch; a flat object (turntable, board game) a higher one.
