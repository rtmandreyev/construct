# Review

Two gates, both required:

1. **Geometric validity** — `check` reports `audit: PASS`. It proves the object stands up
   (every part rests on the ground, on another part or on a declared floating part, its
   surface meeting that part's surface: a box that only overlaps is not enough),
   that nothing claims more certainty than its evidence, and that accuracy claims are
   backed. It cannot judge beauty or likeness.
2. **Art direction** — your eyes on the captures. Read the images; do not infer them from
   the JSON. The bar is not "recognisable": it is **genuinely good**, accurate and
   beautiful, something you would put in a launch video.

## The art-direction rubric

Score each criterion 0–3 from the captures, against the references:

- **3 outstanding**: someone who knows the subject names it exactly at a glance; silhouette
  and proportions match the reference within a few percent; finished, polished, exhibition
  quality. Rare.
- **2 good**: clearly right; deviations show only beside the reference.
- **1 weak**: the right kind of thing, wrong where an owner notices at once (boxy where it is
  curved, towers missing, a rectangle where the nose tapers).
- **0** missing or wrong.

| criterion | good means | look at |
|---|---|---|
| silhouette | reads instantly as this thing, from the hero and every side | `hero.png`, `sheet-views.png` |
| proportions | right against the facts and the references: heights, widths, spacing | `sheet-views.png` front and side, beside the reference |
| identity | the two or three identity features are rendered with care, in proportion, bright | `hero.png`, their own `view-<id>.png` |
| depth | masses, structure, detail and ornament layer clearly; nothing equally loud | `hero.png` |
| composition | strong hero framing with margin; nothing cut off; the best side | `hero.png`, each view |
| assembly | the build order tells the object's story: foundations first, the reveal last | `sheet-assembly.png` |
| motion | articulations and idle life bring it alive without noise, about real pivots | `sheet-motion.png`, `sheet-life.png` |
| density | one clear object at hero scale; up close every region has something true (a bare face or empty corner is unfinished); never clutter: no hairlines, nothing hovering or poking through | every sheet, `solid.png` |
| honesty | labels only from facts; inferred and decorative parts look it; the caption says GENERIC or APPROXIMATE when it is, ORIGINAL DESIGN for a new design | `sheet-provenance.png`, `hero.png` |

It is **good** when every criterion scores 2 or more and you would show it as it is.
Otherwise **iterate**: improve the weakest criterion first, `check`, `review`, score again.
Stop when it is good or when the tier's review rounds or time run out ([effort](effort.md)),
and record the remaining ideas in `authoring.next`.

A model that can see reviews its own captures (`prompts/vision-review.md` asks for exactly
these scores). That self-review records `"outcome": "self-reviewed"`: an author grading its own
work is lenient (seen in live runs: unfinished castles graded "good"). Only the independent
critic can record "good" or "outstanding".

## The independent critic

Fresh eyes, the method the original places were finished with. The critic is not the author: a
subagent, a delegated task or a second model call with a fresh context, which sees only the
packet:

```bash
python3 TOOLS critique scene.json --reference side=side.jpg --reference top=top.jpg \
    --reference three-quarter=hero.jpg --request "a Lamborghini Countach LP400"
```

That writes `critique/packet.md` (the critic's instructions, the request, your identity
checklist, the scene's hash) and renders from the views of your references beside them. Then:

- **Claude Code**: start a subagent with only this: "Read critique/packet.md and every image
  it lists; answer with the critique JSON it asks for; save it as critique/critique.json".
  Do not give it your conversation.
- **Hermes**: delegate the same task (the delegation toolset)<!--network-->, or run the critic as a
  second model call: add `--base-url`, `--model` and `--key-env` to the command above<!--/network-->.
<!--network-->- **`construct author --critic`** (or `--tier masterpiece`) runs it for you every round.
<!--/network-->- **Masterpiece rounds** (`rounds packet` / `rounds record`, [rounds](rounds.md)) use one critic
  per round in three parts: this version blind, then against the best so far (A/B), then the
  defect ledger. The pairwise pick decides; scores are recorded, and every score below 3 must
  cite a defect of its criterion.

Record the answer: `python3 TOOLS critique scene.json --record critique/critique.json`. It
checks the critique, binds it to the scene's hash (a later edit makes it stale), recomputes
the verdict from the scores (outstanding: every score 3, nothing critical or major, every
checklist feature present at quality 3; good: every score at least 2, nothing critical), and
writes `critique/defects.md`: the ranked defects. Fix them most severe first, then critique
again.

## The capture set (`review --out out/`)

| file | what to look for |
|---|---|
| `review/hero.png` | the main impression with labels: is it instantly *this* object? |
| `sheet-views.png` | hero, front, side, back, top, three-quarter: silhouette from every side, proportions, nothing missing or poking through |
| `sheet-assembly.png` | ghost → collapse → staged build → settle: order makes sense, nothing hovers before its support, the tip of construction reads |
| `sheet-life.png` | idle events at their peak: visible but not chaotic, suited to the subject |
| `sheet-provenance.png` | certainty colours (verified ice-white, size verified cyan, shape verified violet, traced blue, user-supplied green, inferred amber, decorative magenta): is the honest story visible, and is anything amber that a cited dimension or drawing could vouch for? Pale amber (designed) on a part you read from a reference means it does not cite it. |
| `still-reduced-motion.png` | the still state alone |
| `solid.png` | the surfaces as a solid, as a print or a modelling program shows them (S in the page): panels that meet, glass inside its frames, nothing crumpled, faceted or poking through. The light forgives these; a print does not. |
| `sheet-motion.png` | opening and part motion across seconds |
| `view-<id>.png` | each of your scene's own views, still: is the target framed with context? |

## Checklist (what each criterion hides)

- **Recognisable at thumbnail size?** Squint at a single view cell. If not, the silhouette
  or proportions are wrong — fix masses before anything else.
- **Identity features visible** in hero and in their own view?
- **Hierarchy**: masses and identity carry the image; detail and ornament recede. If
  everything is equally bright it is clutter (audit warns above 55 % detail). Main surfaces
  keep their faint contour wire: that is form, not clutter.
- **Framing**: the object fills the frame with margin in every view; nothing cut off.
- **Proportions** against the facts; no part obviously too thick, thin, high or low.
- **Contact**: legs on the ground, roofs on walls, arms on pivots, a shade on its arm. The
  audit's `detached` warning compares real surfaces and names the nearest part; fix it, do
  not explain it away. `unsupported` (an error) is a part whose box reaches its support but
  whose surface does not; `thin-support` is a part held up only by a strut or a wire far
  thinner than itself, with the sturdy part it should rest on named. `tips` is a part that
  stands on something with its weight off it, on one edge or a point (a back board standing on
  a rail and leaning back with nothing behind it): give it a second hold on the side it leans to.
  `thin` flags a structural part too fine to render.
- **Honesty**: inferred and decorative parts look it; generated art is labelled; the caption
  says GENERIC or APPROXIMATE when it is, ORIGINAL DESIGN for a new design.
- **Motion**: ambient, never frantic; parts move about their real pivots.
- **Opening**: lids and boards swing about their real hinge and nothing passes through
  anything; the open pose shows what opening is for (the disc, the title page). Choose the
  `open` view's yaw and pitch from `view-open.png` (try a few: the board or lid must not
  hide what it reveals) and keep the hero for the closed object's best side.
- **Text**: labels sit on their face, read the right way up, and only name facts you have.
- **Still**: the reduced-motion frame is a complete, good picture.

## Common defects and fixes

| defect | fix |
|---|---|
| reads as a generic box/cylinder | stronger identity parts; real profile changes in lathe/extrude; better hero yaw |
| mush of lines | fewer meridians/rings/ribs; `fill: none` on thin parts; move clutter to `detail` |
| part floats or sinks | correct `at`/`anchor`; heights from the support's top; or `floating: true` if real |
| dotted, broken-looking main body | it is `decorative`: designed parts of a requested object are `inferred` |
| too dark/faint | role `mass`/`identity` instead of `structure`; `look.glow`; fewer competing parts |
| wrong rotation axis in motion | axis and pivot are world values for the first copy |
| labels collide | fewer annotations, `offset` them apart |
| a part pokes through another in `solid.png` (a fender edge up through a bonnet, a pillar over the roof) | `check --fit` names it and where: trim it to end at the other's face |
| a part through a pane (`check --fit`: crosses-glass) | stop it at the glass, or split the pane around it |
| an open shell (`check --fit`: open): a tube end or a lathe's top you can see into | `"caps": true`, or start and end the lathe's profile on its axis |
| a part buried in another (`check --fit`) | usually the other is far too thick (a fender that swallows the strut tower): thin it; or the buried part is not needed |

Fix, `check`, `review` again, within the tier's review rounds.

## Refining the solid

The light forgives what a solid, a print or a kit does not. When a construct will be printed, made a kit or
exported for an engine, refine its solid: open the page and press **S**, run `construct check scene.json --fit`
(the parts that poke through others where it shows, and the parts buried in others, the most visible first;
some are meant, a part set through another by design), fix the scene so parts meet at faces, and `review`
again: `solid.png` shows the result, and the critic sees it too. Proportions are checked as before, against the
references with `compare`.
