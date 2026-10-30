# Provenance, certainty and rights

The construct's look tells the truth about what is known; the scene records why.

## Certainty

| certainty | means | needs | looks |
|---|---|---|---|
| `verified` | checked against a cited source | a `source` id, or a verified basis fact | crisp light |
| `user_supplied` | the user said or gave it | ideally a `user_request`/`user_supplied` source | crisp |
| `traced` | fitted to an orthographic drawing, plan or elevation that a verified size scales | that reference as `source` (`drawing` or `reference_image`) | as inferred; blue in the provenance view |
| `inferred` | your reasoning: typical sizes, proportions, designed from a description | a `note` saying why helps | a step back |
| `decorative` | chosen for presentation, not evidence | nothing | dotted, faint |

- Facts carry certainty; parts carry certainty and cite the facts they rest on (`basis`).
  A part never claims more than its basis (the audit flags overclaims).
- `subject.accuracy`: `generic` unless you are modelling *this particular* thing from
  evidence; `documented` only when its key parts are evidence-backed (audit-enforced).
- `subject.synthetic: true` for examples and demonstrations only; a real request is
  `false` with its request source `user_private`.
- **Dimensions are not shapes: say each.** A spec page verifies a length or a height, not an
  outline, so give a part both answers when they differ:
  `"certainty": {"size": "verified", "shape": "traced"}` with the length in `basis` and the
  blueprint as `source`. Link every part whose own dimension is a verified fact to it in `basis`
  (a body to its length and width, a tower to its height, a tyre to its size code). A count or a
  description does not verify a size, and neither does a measured thing a part only sits on or is
  computed from: a crater on a moon of known radius, a fret placed by the scale length.
- A shape is `verified` only when a source of kind `drawing`, `measurement` or `dataset` gives its
  coordinates (the audit warns: `shape-overclaim`); `traced` when you fitted it to an orthographic
  reference (a blueprint, a plan, a patent elevation, a square-on overhead); `inferred` when it was
  read off a perspective photograph or designed. Looking for orthographic drawings is the fastest
  way to make a real object's construct more than a guess.
- **Guesses come in shades.** The provenance view deepens an inferred part from designed (cites
  nothing) through described (a document, a basis fact) and seen (read from a picture of it, cited as
  its `source`) to seen and checked (also resting on a verified fact, or passing a silhouette
  comparison, `construct compare --record`); a traced part deepens once its reference's comparison
  passes. So cite on every part the picture or page you read it from: a part modelled from a photo
  that does not cite it shows as designed.
- **Unknown stays unknown.** A fact you do not know is not written at all (never `null`, a
  placeholder or a plausible guess), and nothing is labelled with it.

## Sources

`{"id", "kind", "title", "rights", "ref"}`. Cite what you actually used: the request, a
measurement the user gave, a document they supplied, a page you read. `ref` is citation
text; the tools never fetch it. Rights: `synthetic`, `user_private`, `permitted`,
`public_domain`, `reference_only` (you may describe it, not reproduce it).

## Artwork

- **Authentic** artwork (the real cover, label, poster) only from bytes the user supplied
  or explicitly permitted: declare `provenance: "authentic"`, its rights and source, and
  its SHA-256. Never download covers on your own initiative, never recreate a real cover
  from memory, never present an approximation as the real thing.
- **Generated decoration** is allowed and must be declared `generated-decorative`; the
  viewer captions it "GENERATED DECORATION, NOT AUTHENTIC". Say so in your delivery note.
- No bytes or a hash mismatch: the slot stays empty and labelled. That is a correct result.

## Privacy

Keep private collections, titles, notes and personal photos out of examples, logs and
anything published. Use synthetic stand-ins when demonstrating.
