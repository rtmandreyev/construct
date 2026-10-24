# Film mode

Film mode lets a construct assemble across a piece of music. Instead of building itself in a few
seconds, it builds for as long as the track lasts: slowly through the quiet passages and quickly
through the loud ones, with its light breathing with the music and a shimmer whenever a voice is
present. You get a video with the music in it, ready for a music video, a visualiser or a scene
in a longer film.

```
your track (.wav)  ──►  construct audio  ──►  features (energy, brightness, voice per frame)
your scene         ──►  construct video --audio --assembly <track length> --sound <track>  ──►  film.mp4
```

Nothing about the construct itself changes. The scene is the same scene, and without the film
options the construct opens exactly as it always does.

## Make a construct assemble across a track

You need a construct (a scene that passes `check`), the track as an audio file, and ffmpeg, which
film mode uses to read the audio and write the video. Any format ffmpeg reads works; a `.wav` is
the safest.

**1. Measure the track.** Construct listens to the track and writes down, for every frame of the
video, how loud it is, how bright, and whether a voice is present:

```sh
python3 construct_hologram/cli.py audio track.wav --out track-audio.json
```

Each track is measured against its own range, from its quieter moments to its louder ones, so a
loudly mastered song still moves between calm and intense instead of sitting at full volume.
If you prefer one fixed scale for every track, add `--scale fixed`. If you have the vocals as a
separate stem, add `--voice vocals.wav`, and the construct will shimmer while the voice is present.

**2. Render the film.** Tell Construct how long the assembly should last, usually the length of
the track in seconds, and give it the measurements and the track itself:

```sh
python3 construct_hologram/cli.py video scene.json --out film.mp4 \
    --assembly 245 --audio track-audio.json --sound track.wav --size 1920x1080 --fps 24
```

The construct builds for 245 seconds, its pace following the music, and the finished video has
the track in it. A construct with a ceremony assembly first shows a short opening, a ghost of
itself collapsing into place, of about a second (1.25 s); its build starts after that, so for a
build that ends with the track, give `--assembly` the track's length minus 1.25. The video runs
three seconds past the assembly so it can settle; set `--seconds` for a different length. A scene
whose assembly style is `cut` appears at once, so film mode has nothing to pace there.

If the scene has a camera tour, each flight keeps its place in the story. A flight the scene
starts halfway through its build starts when the film's build is halfway, so the camera arrives
as the parts it looks at are built, and it flies a little slower, as the build does (at most
three times slower, and no longer than 12 seconds unless the scene's own flight is). A flight
after the build starts as long after the film's build as the scene set it, and a flight before
the build stays where it was.

### Choose the camera

`--camera` decides how the camera moves:

| Camera | What it does | Pick it when |
| --- | --- | --- |
| `tour` (the default) | plays the scene's own camera choreography: flights to its close-ups and views | the scene's tour tells the story you want, part by part |
| `steady` | no flights; one long shot from the view, slowly drifting and breathing | a single long shot, or a film that should end on the whole construct |
| `still` | the view held exactly, nothing moves but the construct | a locked-off shot, or one you will move in your editor |

A tour that flies to close-ups during the build ends wherever it was going when the build ends,
which may be a detail rather than the whole construct; `steady` keeps the whole construct in view
from start to end. Choose the view with `--view` (`hero` by default).

Rendering takes a while: every frame is drawn in a browser, about a frame or two a second on a
laptop, so a four-minute film at 24 frames a second takes roughly an hour.

**3. Watch it.** Open `film.mp4`. The quiet opening of a track builds only a little; the louder it
gets, the faster the construct grows, and it completes exactly when its build time is up.

### Why the build follows the music

Every frame, the build moves forward by a small fixed amount plus an amount that grows with the
square of the music's loudness. Quiet frames still move it a little, so nothing stalls; loud
frames move it up to eight times faster. The steps are then scaled so that the whole build ends
on the second you asked for. The light does the same in a gentler way: it dims to 82% in silence
and rises to 118% at full volume.

### Preview it in a browser

You can watch the same thing live. Build the construct, put the features file next to the page,
and open it with the film options:

```sh
python3 construct_hologram/cli.py build scene.json --out out
cp track-audio.json out/
# then open out/construct.html?assembly=245&audio=track-audio.json, and play the track alongside
# (add &camera=steady or &camera=still for the other cameras)
```

The page doesn't play the audio itself; it follows the measurements in time.

## Long assemblies in a scene

A normal construct assembles in at most 20 seconds, and that is what the check expects. For a
film it is better to keep the scene as it is and set the length when you render, with
`--assembly`. If you do write a long assembly into the scene, up to 1200 seconds is accepted, and
the check warns `long-assembly` to remind you that it is meant for film.

## For filmmakers: the three.js loader

If you are making a film in a 3-D engine built on [three.js](https://threejs.org/), you can place
a construct inside your own scene, with your own camera, lighting and post-processing, instead of
rendering Construct's page. `construct_hologram/film/construct-three.js` is an optional loader for
that. Construct itself doesn't need it, and it needs three.js, which you bring.

```js
import { loadConstruct, makeBuildCurve, ALBUM_TONES } from "./construct-three.js";

const c = await loadConstruct("geometry.json", { scale: 1 });   // written by `construct build`
scene.add(c.group);

const audio = await (await fetch("track-audio.json")).json();
const build = makeBuildCurve(audio.energy, audio.fps, 0, 245);  // a build that follows the music, done at 245 s

// every frame, at track time t:
const i = Math.round(t * audio.fps);
c.update({ build: build(t), time: t, energy: audio.energy[i], high: audio.high[i], voice: audio.voice[i] });
```

The loader draws the construct's lines as glowing screen-space strokes and its solid parts as
dark glass, with the faint x-ray of hidden lines, as the Construct viewer does. It uses the house
palette by default. `ALBUM_TONES` is an optional warmer palette made for an album film; pass any
eight colours as `palette` to use your own. Line glow breathes with `energy`, a fine shimmer
follows `high`, and the growing edge of the build flares while `voice` is present.

## Film examples

Examples of constructs assembling across music will be added here.
