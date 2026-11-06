# Villa Savoye reconstruction evidence

## Published sources inspected
- Fondation Le Corbusier ground, first-floor and roof plans, reproduced by ArchEyes: https://archeyes.com/the-villa-savoye-le-corbusier/ . Reference-only images saved in references/, not embedded as artwork.
- Official World Heritage description: https://lecorbusier-worldheritage.org/villa-savoye-et-loge-du-jardinier . Documents the recessed ground floor, pilotis, minimum automobile turning arc, ramp promenade and rooftop solarium.
- Published overall dimensions: https://fr.wikipedia.org/wiki/Villa_Savoye#Plan_de_la_villa : 21.50 m long, 19.00 m wide, 9.40 m high. These are published secondary-source figures, not a measured survey.
- Riccardo Bianchini, Inexhibit: https://inexhibit.com/case-studies/le-corbusier-villa-savoye-part-2-architecture : structural module reduced from 5.00 to 4.75 m in 1928.
- Restored-building exterior and interior photos, original elevation and section drawing reproduced by ArchEyes; originals and third-party redrawing are distinguished in image titles.

## Modelling interpretation
The first-floor and roof plan coordinate frames were aligned by their outer prism; a plan width of 19 m and depth of 21.5 m set the scale. Plan boundaries are manually fitted, not extracted archival CAD. Their certainty is traced only where an actual polygon was read from the drawing. Intermediate levels, structural thicknesses, mullions, column diameter and most details are inferred. A verified grid dimension does not verify every actual column location.

The rooftop solarium is two unequal curved screens with a framed landscape opening, not a generic round pavilion. The first-floor courtyard remains open through its east ribbon aperture and through the roof.

## Reconstruction refinement
The section cross-check led to four ramp flights: two ground-to-first-floor and two first-floor-to-roof. The paired upper flights now return towards the solarium. The first draft's single upper flight was superseded and retained only in the judged history.

The first-floor level remains an inferred 3.10 m. The roof level was revised from an inferred 6.70 m to an inferred 7.15 m after section/photo proportion comparison; the roof-screen rises were shortened correspondingly, retaining the published 9.40 m maximum. Ribbon heights and band proportions were photo-adjusted and remain reconstruction choices, not published joinery dimensions. These are reconstruction choices, not a measured survey.

The staircase was replaced with an elongated returning footprint, straight runs, semicircular winders, solid rising parapets and independent tubular rails, based on the plans and the restored-stair photograph. Tread counts, rises and railing offsets remain inferred.

The reference publication's image called `rear-facade.jpg` depicts the model's terrace-facing right side, not its model-space back. Later review packets map it to `side`; the initial mapping was corrected rather than moving correct geometry to satisfy the wrong view.

## Numerical and fit verification
`verify_promenade.py` writes `numerical-verification.json`, bound to the scene file by SHA-256. It checks four ramp endpoint levels, removal of duplicate slabs, returning-stair footprints within the deck notches and landing elevations. Ramp walking faces differ from their target levels by less than 2 mm because nominal slab thickness is rotated; this is a modelling tolerance, not a statement about the building. It does not certify walkability, headroom, structure or code compliance.

The initial 180-cell fit check reported central support/parapet and stair/deck conflicts plus buried duplicate landings. The decks were cut, duplicate pieces removed and the stair rebuilt. A later bath/chaise clash was also repaired; the moved partition was explicitly downgraded to photo-inferred provenance. The subsequent 200-cell check returned three frame/partition or voxel-resolution findings, not a clean zero-finding fit. Any delivered fit summary must be regenerated on the selected final scene.

Frame rails are joined to internal partition ends; small rails and jambs are close to or below the fit grid cell size. Such findings require coordinate-level interpretation rather than enlarging historic details merely to silence the voxel checker.

## Post-run solid-fit repair
A later user-requested, self-reviewed fit repair consolidated redundant frame profiles, trimmed partition ends to the glazing plane, seated salon tracks and matched pane/stile heights, and repaired terminal jamb/support interfaces. The revised scene passes 63 compiled-coordinate checks and the circulation checks. At 600-cell resolution the fit check reports two intentional guardrail/support joints rather than a raw zero. Coarser-grid touching-face flags are individually checked. See `SOLID_FIT_REPAIR.md`; the earlier three-finding and final 23-finding reports above are historical, not current acceptance evidence. Published facts and principal envelope/circulation geometry were retained.

## Limits
No claim to exact 1931 paint, furnishing, hidden reinforcement or measured as-built detailing. Photographs depict the restored building. No reference image is embedded in the final page, no invented landscape or authentic artwork. Holographic presentation uses Construct's house palette.
