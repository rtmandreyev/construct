# Construct for anyone with an AI agent

You describe a thing in plain words, and your agent builds it as a construct: an animated model drawn in lines of
light. It comes as one web page that works anywhere, and it is honest about what is known about it. You don't need to
know 3D, code or graphics.

<p align="center"><a href="https://rtmandreyev.github.io/construct/examples/sainte-chapelle/"><img src="../media/assembly-sainte-chapelle.gif" width="60%" alt="The Sainte-Chapelle construct assembling itself"></a></p>
<p align="center"><sub>The Sainte-Chapelle, made by Claude Opus 5.5 in masterpiece mode. <a href="https://rtmandreyev.github.io/construct/examples/sainte-chapelle/">Open it</a> and drag to turn it around.</sub></p>

## What you can do

- **Ask for anything real or imagined:** a car, a cathedral, a camera, a guitar, a planet, a lamp from your
  grandmother's house. For a named subject the agent looks up the real facts first.
- **See how it is known:** press **P** and every part is coloured by how it is known, from measured to guessed.
- **See it as a solid:** press **S** and the same construct is shown as a modelling program shows it.
- **Take it further:** the same construct exports as a 3D model, prints on a 3D printer, becomes a model kit
  ([four to open](https://rtmandreyev.github.io/construct/#kits)), plays in a game engine or assembles across a piece of music in a film.
- **Give it colour:** every new construct comes with its own colours and materials, so its 3D model arrives finished.
  In Hermes you can click any part and repaint it yourself.
- **Make a whole place:** put your constructs together into a **world**, ask for one in plain words, or give your
  agent a single photo or picture of a place. Every construct in a world stays its own, so you can move it, take it
  out, or open it on its own.

## A whole place, from one picture

<p align="center"><a href="../../examples/worlds/stortorget/"><img src="../media/world-stortorget.gif" width="49%" alt="Stortorget, Stockholm's old square, assembling as a world"></a>
<a href="../../examples/worlds/rain-harbour/"><img src="../media/world-rain-harbour.gif" width="49%" alt="Rain Harbour, a night street with neon signs, assembling as a world"></a></p>
<p align="center"><sub>Left: <a href="../../examples/worlds/stortorget/">Stortorget</a>, Stockholm's old square, made from one photograph.
Right: <a href="../../examples/worlds/rain-harbour/">Rain Harbour</a>, a game level made from one concept picture.</sub></p>

Both were made by GPT-6.1 Sol in Hermes, zero-shot: one picture and one request each. A world
this size takes time (Stortorget about 20 hours, Rain Harbour about 17), because every house, sign and car is built
and checked as its own construct. Putting constructs you already have together, in a room or a yard, takes minutes.
[Worlds, step by step](worlds-walkthrough.md).

## Try it

1. Install it for your agent (two minutes, nothing system-wide; see [Install](../../README.md#install)). In Hermes it
   is one line: `hermes plugins install rtmandreyev/construct#hermes/construct`, and constructs then appear live in
   the chat ([step by step](hermes-walkthrough.md)). With no terminal at all, use the
   [Claude or ChatGPT app](in-the-apps.md).
2. Ask: *"make a construct of a 1970s desk fan"*, or *"a masterpiece of the Sydney Opera House"*.
3. Open the `construct.html` it gives you. Drag to orbit, scroll to zoom, **R** replays the build.

Before it starts, the agent tells you which mode it will use and why:

| Mode | For | Time |
| --- | --- | --- |
| **fast** | simple objects and generic subjects | about 10 minutes |
| **masterpiece** | a named car, landmark or instrument whose likeness matters | up to 2 hours |
| a **world** from one picture | a whole street, square or game level | many hours: every piece is its own construct |

## Go deeper

- [How a construct is made](../HOW-IT-IS-MADE.md): the process, step by step
- [The Measured Light style](../STYLE.md): what you are looking at, and the keys
- [Using Construct](../USING.md): every way to run it
- [The gallery](https://rtmandreyev.github.io/construct/): every example, to open and explore
