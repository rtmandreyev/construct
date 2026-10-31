# Construct for film and motion

A construct can assemble across a piece of music: the build pauses, surges and flares with the track, and you get a
video with the music in it. A NetLogo run can be filmed too, every agent as moving light.

<p align="center">
  <a href="https://rtmandreyev.github.io/construct/films/james-webb-space-telescope/"><img src="../media/film-james-webb-space-telescope.gif" width="32%" alt="The James Webb Space Telescope assembling across a piece of music"></a>
  <a href="https://rtmandreyev.github.io/construct/films/voyager-1/"><img src="../media/film-voyager-1.gif" width="32%" alt="Voyager 1 assembling across a piece of music"></a>
  <a href="https://rtmandreyev.github.io/construct/films/arecibo-observatory/"><img src="../media/film-arecibo-observatory.gif" width="32%" alt="The Arecibo Observatory assembling across a piece of music"></a>
</p>
<p align="center"><sub>Three films, each with its video and its live construct. Open one to choose.</sub></p>

## What you can do

- **A film from a construct:** measure a track, then render the construct building across it, at any size and frame rate.
- **It follows the music:** the build nearly pauses in quiet passages and surges in loud ones; give a separate
  vocal stem (`--voice vocals.wav`) and it shimmers while the voice is present.
- **A run as a film:** a NetLogo recording rendered in Blender, every agent with a trail, in its own colours.

## Try it

```sh
construct audio track.wav --out track-audio.json
construct video scene.json --out film.mp4 --assembly 245 --audio track-audio.json --sound track.wav \
    --camera steady --size 1920x1080 --fps 24
```

## Go deeper

- [Film mode](../FILM.md)
- [Runs as films](../NETLOGO.md) and [the Blender add-on](../../hosts/blender/README.md)
