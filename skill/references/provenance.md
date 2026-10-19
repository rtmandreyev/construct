# Provenance, certainty and rights

The hologram's look tells the truth about what is known; the scene records why.

## Certainty

| certainty | means | needs | looks |
|---|---|---|---|
| `verified` | checked against a cited source | a `source` id, or a verified basis fact | crisp light |
| `user_supplied` | the user said or gave it | ideally a `user_request`/`user_supplied` source | crisp |
| `inferred` | your reasoning: typical sizes, proportions, designed from a description | a `note` saying why helps | a step back |
| `decorative` | chosen for presentation, not evidence | nothing | dotted, faint |

- Facts carry certainty; parts carry certainty and cite the facts they rest on (`basis`).
  A part never claims more than its basis (the audit flags overclaims).
- `subject.accuracy`: `generic` unless you are modelling *this particular* thing from
  evidence; `documented` only when its key parts are evidence-backed (audit-enforced).
- `subject.synthetic: true` for examples and anything not about a real item.

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
