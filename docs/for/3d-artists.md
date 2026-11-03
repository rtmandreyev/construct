# Construct for 3D artists

A construct comes into Blender with its build, its joints and its finish on sliders: from lines of light to a plain
model of named parts to the finished model, ready to light, render or model over. Its OBJ is quads where it can be, so
it subdivides cleanly.

<p align="center">
  <a href="https://rtmandreyev.github.io/construct/examples/light-to-metal/"><img src="../media/pipeline-revox.gif" width="45%" alt="The Revox A77 in Blender: from lines of light to a plain model, then finished in brushed metal"></a>
  <a href="https://rtmandreyev.github.io/construct/examples/light-to-metal/"><img src="../media/pipeline-minifreak.gif" width="45%" alt="The Arturia MiniFreak in Blender: from lines of light to a plain model, then finished with its keys"></a>
</p>
<p align="center"><sub>The Revox A77 and the Arturia MiniFreak in Blender, revealed by the add-on. <a href="https://rtmandreyev.github.io/construct/examples/light-to-metal/">See them in 3D</a>.</sub></p>

## What you can do

- **Import with the add-on:** File > Import > Construct; the build, the opening and the finish are sliders.
- **Finish it:** a material map (part names to colour and finish) turns the plain model into paint, chrome and glass.
- **Model over it:** the OBJ shares its positions and turns strips back into quads; `--quality` shows where its
  triangles are thin, so you know what to remesh.
- **Check the solid first:** press **S** in the construct page, or run `construct check --fit` for parts that poke
  through others.

## Try it

```sh
python3 scripts/build_blender_extension.py         # dist/construct-blender-<version>.zip
construct export scene.json --out model.glb --materials finish.json --wire seams
```

In Blender: **Edit > Preferences > Get Extensions > Install from Disk**, then File > Import > Construct.

## Go deeper

- [New things from real ones](invent-from-what-exists.md): design a ship, a vehicle, a creature or an artefact from real ones, with a brief to copy
- [The Blender add-on](../../hosts/blender/README.md)
- [3D export](../EXPORT.md): materials, quality, OBJ for artists
