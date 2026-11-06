# Villa Savoye · final reconstruction record

> **Historical pre-repair record.** The current geometry was subsequently repaired and rechecked as solids. See `SOLID_FIT_REPAIR.md` for the current fit results; the scene described below is preserved as `before-solid-fit-repair.json` and in the judged checkpoint.

## Delivered result

The selected version is round 12 of the masterpiece run. The independent critic rated it **good**, preferred it to round 11 for smoother solarium curves, and did not rate it outstanding. The run stopped at the 12-round cap: 59.8 active authoring minutes plus 76.2 critic minutes. No further geometry was edited after the final selection; only `authoring.next` was updated to describe the remaining work.

405 named scene entries compile to 563 instances, with 9,632 lines and 11,264 triangles. The page provides the complete building, assembly replay and named entry, garden, promenade, roof-garden, court and stair views. Use Solid to inspect the architectural volumes.

## Evidence and uncertainty

Published secondary-source overall figures are 19.00 m wide × 21.50 m long × 9.40 m high. They are not an as-built survey. The published structural module is 4.75 m. The Fondation Le Corbusier plans reproduced by ArchEyes supplied the plan outlines; sections were cross-checked for the four-flight ramp route. World Heritage documentation supplies the automobile-turning-arc principle for the ground enclosure and the ramp/solarium relationship.

The main building footprint follows 19 × 21.5 m; the broader 21 × 23 m scene bounds include the presentation ground. Overall compiled vertical span is 9.5191 m because geometry extends below the nominal ground datum; do not confuse that span with the published 9.40 m ground-to-top figure.

Plan curves are manually traced/interpolated, not archival CAD. Storey levels, thicknesses, pilotis diameter, glazing construction, stair treads, rail offsets and furniture dimensions remain inferred. The entrance curve is a plan-based approximation, not a recovered automobile kinematic sweep. Plant silhouettes are based on restored-building photographs, not authenticated 1931 planting. The scene contains no embedded reference photographs and makes no claim to original paint or furnishing authentication.

### Sources

- Plans, section and restored-building photographs: https://archeyes.com/the-villa-savoye-le-corbusier/
- Official World Heritage architectural description: https://lecorbusier-worldheritage.org/villa-savoye-et-loge-du-jardinier
- Published overall dimensions, secondary source: https://fr.wikipedia.org/wiki/Villa_Savoye#Plan_de_la_villa
- Structural-module discussion, Riccardo Bianchini: https://inexhibit.com/case-studies/le-corbusier-villa-savoye-part-2-architecture

## Actual final checks

**Validation / compilation:** PASS, 0 errors, 9 `tiny` warnings. The warnings concern the hob ring and eight rail standoffs being small at whole-building framing; their dimensions were not inflated to silence a visibility warning.

**Numerical geometry:** `verify_promenade.py` passed on the delivered scene and wrote `numerical-verification.json`. It checks four ramp-flight endpoint levels, duplicate-slab removal, 18 stair tread/parapet footprint bounds against the cut deck notch, and both stair landing elevations. Maximum ramp-endpoint level deviation is 0.001628 m. The footprint test excludes tubular handrails and does not certify headroom, swept human passage, structural feasibility or building-code compliance.

Final scene file SHA-256, including delivery metadata:
`59b310e84d834be0511a6f84eaf206adf2888ecbbadb151a93c47c3ead68f5de`

**Solid fit:** the 200-cell check examined 380 solid parts and returned **23 findings**, not a clean fit. It ran on the selected geometry before the metadata-only `authoring.next` update. There are 7 `pokes` and 16 `buried` pair findings, listed below. Some are frame/partition joins or thin geometry affected by voxel resolution, but they have **not all been individually cleared by coordinate-level proof**. In particular, buried sash bottoms and salon tracks remain unresolved detailing rather than verified visible construction.

| Type | Part | Other part |
|---|---|---|
| pokes | back-continuous-head-reveal | kitchen-east |
| pokes | back-continuous-head-reveal | bedroom-east |
| pokes | left-ribbon-rail-5.45 | bedroom-partition-west |
| pokes | back-casement-transom-east | kitchen-access-west |
| pokes | salon-sliding-track-outer-channel | salon-terrace-stile-4 |
| pokes | salon-sliding-track-outer-channel | salon-terrace-stile-1 |
| pokes | left-ribbon-rail-4.23 | bedroom-partition-west |
| buried | front-ribbon-rail-4.23 | front-continuous-sill-reveal |
| buried | front-opening-sash-a-bottom | front-continuous-sill-reveal |
| buried | front-opening-sash-c-bottom | front-continuous-sill-reveal |
| buried | back-ribbon-rail-4.23 | back-continuous-sill-reveal |
| buried | right-ribbon-rail-5.45 | right-continuous-head-reveal |
| buried | rail-standoff-upper-left-back | bath-wc-jamb |
| buried | left-ribbon-rail-5.45 | left-continuous-head-reveal |
| buried | front-ribbon-rail-5.45 | front-continuous-head-reveal |
| buried | back-ribbon-rail-5.45 | back-continuous-head-reveal |
| buried | salon-sliding-track-inner-channel | salon-recessed-threshold |
| buried | salon-sliding-track-outer-channel | salon-recessed-threshold |
| buried | salon-sliding-head-inner-channel | salon-recessed-head-reveal |
| buried | front-end-pier--9.32 | front-frame-group-a |
| buried | front-end-pier--9.32 | front-jamb-reveal-left |
| buried | right-ribbon-rail-4.23 | right-continuous-sill-reveal |
| buried | left-ribbon-rail-4.23 | left-continuous-sill-reveal |

## Remaining visual limits

The critic still identifies simplified planting and salon furnishings, approximate close-range joinery, some stair-rail terminal shaping and photograph-dependent proportion/framing discrepancies. The run's ledger and sealed judgments are preserved in `rounds.md` and `checkpoints/`. Interior layering and glazing-edge detailing reached the workflow's skill-gap limit after three kept attempts.

Construct's holographic view deliberately retains faint hidden lines, and its house palette does not reproduce tinted glazing. These are presentation limits, not evidence of historical material colours. This is a researched architectural reconstruction, not construction documentation, an engineering clearance model, or a printable/exported deliverable.
