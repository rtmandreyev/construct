# About Construct

**Construct is an agent skill and toolkit that turns a description of a real or fictional
thing into an honest, animated hologram any agent can build.**

## What it does

1. **A model describes the thing.** It writes a declarative *scene* — facts with their
   certainty and sources, and parts built from a closed set of shapes (box, cylinder, lathe,
   extrusion, tube and so on), each with a role, a stage and the facts it rests on — or, for
   common things, it fills an *archetype's* few parameters (a CD case, a book, a guitar, a
   synth, a bottle).
2. **Construct checks it.** Validation and a geometric audit report every problem with a JSON
   path, a code and a fix hint: a `verified` claim without a source, an unknown fact written
   as `null` or "unknown", a part that floats or barely renders, an assembly order that builds
   a roof before its walls. The model repairs the draft until it is clean.
3. **Construct compiles it deterministically** — the same scene gives the same geometry, byte
   for byte — and **renders it in one holographic style**: line light over smoked glass,
   staged assembly (a ghost, a collapse, a build that grows bottom-up with a bright tip, a
   settle), one-shot articulations (a lid opens, a disc lifts and turns), calm idle life, and
   a visible certainty for every fact and part. The renderer chooses every colour; agents never do.
4. **Outputs:** a self-contained HTML hologram that runs in any browser, review stills and
   contact sheets, video, and compiled geometry (`construct-geometry`, see
   [CONTRACT.md](../CONTRACT.md)) that apps such as Tessera render natively.

## Where the method comes from

### Anatomy's truth-first construction method

Construct is inspired by [Anatomy](https://github.com/wheresryan22/anatomy) by Ryan
(`wheresryan22/anatomy`, MIT licence), an agent skill that builds detailed isometric SVG
illustrations of machines and systems. Construct uses **its method, not its code**: no code,
assets or text from Anatomy are included. From Anatomy's `SKILL.md` and README:

| Anatomy's practice | In Construct |
|---|---|
| Collect the real numbers before drawing ("truth first") | `facts`, each with a certainty and a source; parts cite the facts they rest on |
| Write the parts list before any geometry | the scene's grouped parts with roles, written before shapes are tuned |
| Rebuild byte for byte (deterministic builds) | the compiler: same scene, same geometry |
| Run the audit to zero ("every line ends on something") | `check`: support and real contact, assembly order, overclaims, accuracy; errors must reach zero |
| Read every rendered image | `review`: contact sheets, views, the opened pose, a reduced-motion still |
| Never copy a reference image | artwork only from bytes the user supplied, hashed; never recreated from memory |

### What Construct adds

- **3-D animated holograms** rather than flat SVG figures: assembly, articulations, idle life,
  a camera that turns to what opening reveals, a reduced-motion still.
- **Certainty as material:** verified, user-supplied, inferred and decorative parts look
  different, and a provenance view colours them.
- **Artwork with hashes and rights:** named slots (cover, inlay, disc print, label) filled
  only from supplied, hash-checked bytes; generated art is labelled as decoration.
- **Articulations** that ride on each other, for objects that open.
- **A versioned geometry contract** for apps, with a JSON Schema.
- **Any-model authoring:** a repair loop with machine-readable fixes, parameter archetypes
  for small models, prompts for any host, MCP tools, and an OpenAI-compatible runner.
- **A cross-model evaluation** with a scorer that needs no model ([EVALUATION.md](EVALUATION.md)).

### NODE

Construct's holographic look and construction method grew out of NODE's Measured Light
holograms, by the same author. Construct is an independent re-creation: it contains no NODE
code, fonts, shaders or assets.

## How to talk about it

Say:

- "Inspired by Anatomy's truth-first construction method."
- "A hologram any agent can build."
- "Honest about what is known."
- "Works with any model, through Hermes, Claude Code, MCP, a CLI, Python or an
  OpenAI-compatible endpoint."

Don't say:

- "Anatomy for 3-D" — Construct shares a method, not a product or code.
- "Photoreal", "exact replica" or "digital twin" — it is a stylised hologram; generic
  reconstructions say so on screen.
- That it identifies real editions, pressings or printings, or that it reproduces real
  artwork — it shows a real cover only from bytes the user supplied, and never recreates one.
- That every model produces a good likeness — the audit guarantees validity and honesty;
  likeness of free-form subjects depends on the model and on looking at the result.
  Parameter archetypes look the same whichever model fills them.

## Licence

MIT. Anatomy is MIT-licensed too; no part of it is included. Third-party software: none is
bundled (Python standard library; an optional local browser and ffmpeg are used if present).
