# Documentation

Start with the first two pages if you are new to Construct; the rest are there when you need them.

| If you want to… | read |
| --- | --- |
| see how a construct is made, step by step | [HOW-IT-IS-MADE.md](HOW-IT-IS-MADE.md) |
| understand what you see in a construct | [STYLE.md](STYLE.md) |
| run Construct in Claude Code, Hermes, another agent or by hand | [USING.md](USING.md) |
| fix something that went wrong | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| fill in a ready-made template (a book, a CD, a guitar, a bottle, a car) | [ARCHETYPES.md](ARCHETYPES.md) |
| build a mountain, a route or a planet from real elevation data | [TERRAIN.md](TERRAIN.md) |
| know where Construct's method comes from | [ABOUT.md](ABOUT.md) |
| compare models, or score your own | [EVALUATION.md](EVALUATION.md) |
| contribute, or build Construct into your own tools | [DEVELOPMENT.md](DEVELOPMENT.md) |
| read the scene and geometry format, for apps | [CONTRACT.md](../CONTRACT.md) |
| read what changed in each version | [CHANGELOG.md](../CHANGELOG.md) and the [v0.2.1 release notes](releases/v0.2.1.md) |
| publish the examples gallery yourself | [PUBLISHING.md](../PUBLISHING.md) |

## Glossary

**Construct.** An animated holographic model of one thing, built by Construct: a single
`construct.html` page that opens in any browser. Also the name of the project.

**Scene.** The short text file an agent writes to describe a construct: the facts, each marked
with how well it is known, and the parts, built from simple shapes, with how they assemble and
open. Construct turns a scene into a construct.

**Archetype.** A ready-made template for a common thing, like a book or a CD case. You fill in
the facts you know, and Construct draws the rest.

**Mode.** How much effort goes into a construct: **fast** (one careful pass), **masterpiece**
(rounds judged by a critic) or **unbounded** (masterpiece without the round and time limits).

**Critic.** A second, independent model that never saw the authoring. In masterpiece mode it
looks at each new version, compares it with the best one so far without knowing which is which,
and says what to improve.

**Round.** One cycle of a masterpiece run: a few improvements, then the critic's judgement. Only
a version the critic prefers is kept.

**Provenance.** How each fact and part is known: verified, user-supplied, inferred or decorative.
Press **P** in a construct to see it.

**Measured Light.** The name of the house style: line light over smoked glass. See
[STYLE.md](STYLE.md).
