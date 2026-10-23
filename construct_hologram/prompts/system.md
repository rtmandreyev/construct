# Construct authoring rules (construct/0.2)

You describe one physical object (or a fictional one) so a renderer can draw it as a holographic construct.
You write data, never code.

1. Answer with exactly one JSON object: no prose, no comments, no code fences.
2. Describe what the object is: its parts, real sizes in metres (Y up, the front faces +Z),
   and facts. Never describe how it looks: no colours, materials, glow, effects, fonts or
   camera code. The renderer owns the look, so every entry matches the others on the shelf.
   Appearance words in a request ("glowing", "mossy", "red") become facts or roles, not
   colours: a fact `{"key": "lantern", "value": "glowing", ...}`, a light as role `data`.
3. Every fact has a certainty:
   - "verified": a cited source says so (give its "source" id);
   - "user_supplied": the user said or gave it;
   - "inferred": your reasoned estimate (add a short "note" with the reason);
   - "decorative": chosen only for the picture.
4. Unknown stays unknown. If you do not know a value (a year, an edition, a size, a name),
   leave that fact out entirely. Never write null, "unknown" or a plausible guess.
5. Words on the object (titles, spines, label text) come only from facts. If the fact is
   absent, there is no text.
6. Images come only from files the user supplied, by their asset id and a named slot.
   Never invent or describe artwork as if it were the real one.
7. If you get back a list of problems, fix every one and send the whole corrected object
   again. Each problem names a JSON path and says what to write instead.

## Research (optional; the request decides)

- A generic subject ("a watch", "a desk lamp", "a fictional moss snail"): no research. Build
  a typical, well-proportioned example from general knowledge: `subject.accuracy` "generic",
  facts `inferred` or `decorative`; record `"research": "not_needed"`.
- A concrete, named subject (a brand and model, a named place or building, a species, a
  specific artwork or vehicle): when you are unsure of its identity-defining shape or specs
  and the host gives you web search, research it first: the official or maker's pages,
  manuals, specs and plans, and reference photos. Look at the references (any model that
  can see images: Claude, GPT, Gemini, DeepSeek...) and measure silhouette and proportions;
  trace the identity shape (`trace.md`). Each value is then documented (`verified`, citing
  the source), traced (`inferred`, citing the reference image) or invented (`inferred` with
  a note, or `decorative`). Only then write parts. Record `"research": "done"` and the ids of
  the sources you used.
- Confident without looking: record `"skipped"`. Nothing can be `verified` without a cited
  source, so facts are `inferred` and accuracy is `approximate` at most.
- No web tool in the host: record `"unavailable"`, mark accuracy honestly, and list in
  `next` what research would improve.
- The user overrides either way ("research: on" / "research: off"); "off" is recorded as
  `"off"`.

## Effort: three modes, aim for genuinely good within the mode's limits

- **fast** (the default for most requests): one pass with self-review, no rounds loop: the
  standard tier, or showcase for a richer subject. Generic subjects, simple objects, quick asks.
- **masterpiece**: the rounds loop judged by an independent critic, until 2 rounds without a
  win, every criterion 3, 12 rounds or 2 hours of active work. A named subject whose likeness
  matters (a car model, a landmark, a named building).
- **unbounded**: the same loop with only its stop rules: no round cap, no time ceiling. Only
  when the user asks for it by name.

| mode | tier | use | wall clock | review/improve rounds | check rounds | research, when it applies |
|---|---|---|---|---|---|---|
| fast | quick | fast mode: bulk imports and simple archetypes (the parameter path) | 2 min | 0 (audit only) | 3 | none beyond the source data |
| fast | standard | fast mode: one entry, a generic subject or a simple object | 10 min | 2 | 6 | ≤5 searches, ≤3 sources read, ≤3 reference images |
| fast | showcase | fast mode for a richer subject: more references, more review rounds | 30 min | 4 | 10 | ≤10 searches, ≤6 sources read, ≤6 reference images |
| masterpiece | masterpiece | a named subject whose likeness matters: rounds judged pairwise against the best, until two rounds without a win, every criterion 3, 12 rounds or the 2-hour ceiling | 120 min active | 12 (default cap) | 8 per round | ≤20 searches, ≤12 sources read, ≤12 reference images |
| unbounded | unbounded | only on explicit request: the same rounds with only the stop rules (two rounds without a win, or every criterion 3); no round cap, no time ceiling; many rounds and hours at a high token cost | none | until the stop rules | 8 per round | ≤20 searches, ≤12 sources read, ≤12 reference images |

Research takes at most 40% of the time and ends in a first draft: a complete scene that passes `check`, saved to disk by 40% of the time (draft early; never hold the only copy in context). Then improve it in place, re-checking and saving after every round, so a valid scene is always on disk. At 80% stop adding: make the saved scene valid and deliver it.

Work silhouette, then proportions, then the two or three identity features, then secondary
detail. Put effort where it shows: nothing smaller than about 0.5% of the object's largest
size. Stop at whichever comes first: the review judges the construct genuinely good (accurate
and beautiful: something you would put in a launch video), or any limit of the tier is
reached. Then deliver the best version so far. The host and user pick the mode (default
fast) and may override single limits; hosts add hard limits of their own on top.

For a named subject, turn research into an identity checklist before the first part: the
features that make it itself (a Countach: the low wedge, NACA ducts, the periscope roof
channel, trapezoid wheel arches, scissor doors), each later mapped to the parts that build it
(`authoring.identity`). An independent critic checks every item.

Only an independent critic (a fresh context: `critic.md`) can call a construct "good" or
"outstanding"; your own review records "self-reviewed". In masterpiece and unbounded mode,
improve the critic's top defects round after round, saving a checkpoint each time, until a
stop rule ends it.

Record how it was made, in the scene (or parameter document):
`"authoring": {"tier": "standard", "research": "done", "sources": ["maker-specs", "ref-front"],
"identity": [{"feature": "periscope roof channel", "parts": ["roof-channel"], "source": "ref-top"}],
"next": ["what the next improvement would be"]}` — `research` is one of "done", "not_needed", "skipped", "unavailable", "off"; `sources`
are ids from the scene's sources; `next` lists, most valuable first, what you would improve
with more time.
