"""Render a NetLogo run as a film with Blender: every recorded turtle as light that moves, with its track.

    blender -b --factory-startup --python scripts/run_film.py -- RUN.jsonl --out film.mp4
            [--size 1920x1080] [--from SECONDS] [--seconds SECONDS] [--samples 16] [--trail 0.5] [--blend out.blend]

RUN.jsonl is a recording from construct:run or construct.nls; a run recorded with construct:music plays
with its track (its features file and the track beside the recording), in time: tick t at second
t / ticks-per-second. The film draws the recording itself (hosts/blender/construct/runfilm.py), so a run
of any length and any number of turtles loses nothing. EEVEE; the length is the run's unless --seconds.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(prog="run_film.py", description=__doc__.splitlines()[0])
ap.add_argument("run")
ap.add_argument("--out", required=True, help="the film (.mp4)")
ap.add_argument("--size", default="1920x1080")
ap.add_argument("--from", dest="start", type=float, default=0.0, help="seconds into the run to start at")
ap.add_argument("--seconds", type=float, help="how long (default: to the end of the run)")
ap.add_argument("--samples", type=int, default=16, help="EEVEE samples per frame")
ap.add_argument("--trail", type=float, default=0.5, help="seconds of trail behind each turtle")
ap.add_argument("--blend", help="also save the scene as a .blend")
a = ap.parse_args(argv)

spec = importlib.util.spec_from_file_location("construct_runfilm", ROOT / "hosts" / "blender" / "construct" / "runfilm.py")
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
rf.register()

sc = bpy.context.scene
for obj in list(sc.objects):   # the factory scene's cube, light and camera
    bpy.data.objects.remove(obj, do_unlink=True)
rf.build(a.run, sc, trail_seconds=a.trail)
w, h = (int(x) for x in a.size.lower().split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
first = 1 + int(round(a.start * sc.render.fps))
sc.frame_start = first
if a.seconds:
    sc.frame_end = first + int(round(a.seconds * sc.render.fps)) - 1
sc.eevee.taa_render_samples = a.samples
s = sc.render.image_settings
if hasattr(s, "media_type"):
    s.media_type = "VIDEO"
s.file_format = "FFMPEG"
sc.render.ffmpeg.format = "MPEG4"
sc.render.ffmpeg.codec = "H264"
sc.render.ffmpeg.constant_rate_factor = "HIGH"
sc.render.ffmpeg.audio_codec = "AAC" if sc.sequence_editor else "NONE"
sc.render.ffmpeg.audio_bitrate = 192
sc.render.filepath = os.path.abspath(a.out)
if a.blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
bpy.ops.render.render(animation=True)
print("wrote %s (frames %d to %d)" % (a.out, sc.frame_start, sc.frame_end))
