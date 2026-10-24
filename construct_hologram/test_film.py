"""Film mode: audio features, long assemblies, the viewer's audio-driven build and its parity without audio."""

import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from . import diagnose, film_audio, render, scene, studio

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE / "examples" / "v2"
FPS = 24
RATE = film_audio.RATE
CAPTURE = render.find_browser() and os.environ.get("HOLOGRAM_SKIP_CAPTURE") != "1"


def tone(seconds, amp, freq=440.0, sr=RATE):
    return [int(32767 * amp * math.sin(2 * math.pi * freq * i / sr)) for i in range(int(seconds * sr))]


def write_wav(path, samples, sr=RATE):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def scene_with_assembly(seconds):
    s = json.loads((EXAMPLES / "lighthouse.json").read_text())
    s.setdefault("animation", {}).setdefault("assembly", {})["seconds"] = seconds
    return s


class Features(unittest.TestCase):
    """`construct audio`: energy, high and voice per video frame, 0..1."""

    def test_silence_is_zero_and_a_loud_tone_is_full(self):
        doc = film_audio.analyse([0] * (2 * RATE) + tone(3, 0.6), FPS)
        e = doc["energy"]
        self.assertEqual((doc["format"], doc["fps"], doc["frames"]), ("construct-audio", FPS, len(e)))
        self.assertEqual(len(e), 5 * FPS)
        self.assertEqual(max(e[:2 * FPS]), 0.0)
        self.assertGreater(e[-1], 0.95)
        self.assertTrue(all(0.0 <= x <= 1.0 for x in e + doc["high"] + doc["voice"]))
        self.assertEqual(set(doc["voice"]), {0.0})  # no voice stem: no voice

    def test_a_silent_track_is_all_zero(self):
        doc = film_audio.analyse([0] * (2 * RATE), FPS)
        self.assertEqual(set(doc["energy"]) | set(doc["high"]), {0.0})
        self.assertNotIn("range_db", doc)

    def test_each_track_is_mapped_to_its_own_range(self):
        # a loud master: it alternates between -12 and -5 dBFS, every three seconds (the meter falls slowly)
        samples = []
        for k in range(8):
            samples += tone(3, 0.35 if k % 2 else 0.8)
        track = film_audio.analyse(samples, FPS, scale="track")
        fixed = film_audio.analyse(samples, FPS, scale="fixed")
        self.assertEqual(fixed["range_db"], [-40.0, -10.0])

        def spread(e):  # the end of each quiet stretch against the end of each loud one
            quiet = [e[(k + 1) * 3 * FPS - 1] for k in range(1, 8, 2)]
            loud = [e[(k + 1) * 3 * FPS - 1] for k in range(2, 8, 2)]
            return min(loud) - max(quiet)
        self.assertGreater(spread(track["energy"]), 0.25)  # the track moves between quiet and loud
        self.assertLess(spread(fixed["energy"]), 0.1)  # the fixed window saturates: both read about 1
        def saturated(e):
            return sum(1 for x in e if x >= 0.99) / len(e)
        self.assertGreater(saturated(fixed["energy"]), 0.3)
        self.assertLess(saturated(track["energy"]), saturated(fixed["energy"]) / 2)

    def test_high_follows_brightness(self):
        low_loud, low_high = film_audio.levels(tone(1, 0.5, 100.0), FPS)
        hi_loud, hi_high = film_audio.levels(tone(1, 0.5, 4000.0), FPS)
        self.assertAlmostEqual(low_loud[10], hi_loud[10], delta=1.0)  # the same loudness
        self.assertGreater(hi_high[10] - low_high[10], 20.0)  # far brighter
        doc = film_audio.analyse([0] * RATE + tone(1, 0.5, 4000.0), FPS)
        self.assertEqual(doc["high"][FPS // 2], 0.0)
        self.assertGreater(doc["high"][FPS + 3], 0.8)  # an attack shows within a few frames

    def test_a_voice_stem_drives_the_voice_channel(self):
        doc = film_audio.analyse(tone(2, 0.5), FPS, voice_samples=[0] * RATE + tone(1, 0.5, 220.0))
        self.assertEqual(doc["voice"][FPS // 2], 0.0)
        self.assertGreater(doc["voice"][2 * FPS - 1], 0.7)

    def test_onsets_mark_attacks_and_nothing_else(self):
        plucks = []
        for k in range(6):  # a pluck every 0.75 s: a sharp start, then a fade
            plucks += [int(x * math.exp(-6 * i / RATE)) for i, x in enumerate(tone(0.75, 0.7, 330.0))]
        doc = film_audio.analyse([0] * RATE + plucks, FPS)
        hits = [i / FPS for i, v in enumerate(doc["onset"]) if v > 0]
        expected = [1 + 0.75 * k for k in range(6)]
        self.assertEqual(len(doc["onset"]), doc["frames"])
        self.assertTrue(all(any(abs(h - e) <= 2 / FPS for h in hits) for e in expected), hits)  # every pluck
        self.assertTrue(all(any(abs(h - e) <= 2 / FPS for e in expected) for h in hits), hits)  # and only plucks
        self.assertEqual(set(film_audio.analyse(tone(4, 0.5), FPS)["onset"][FPS:]), {0.0})  # a held tone has none
        self.assertEqual(set(film_audio.analyse([0] * (2 * RATE), FPS)["onset"]), {0.0})
        gaps = [b - a for a, b in zip(hits, hits[1:])]
        self.assertGreaterEqual(min(gaps), film_audio.ONSET_GAP_S)

    def test_sections_are_where_the_music_changes(self):
        quiet, loud = tone(25, 0.08, 150.0), tone(25, 0.6, 2500.0)
        doc = film_audio.analyse(quiet + loud + quiet, FPS)
        self.assertEqual(doc["version"], 2)
        found = [x["t"] for x in doc["sections"]]
        self.assertEqual(len(found), 2, doc["sections"])
        self.assertAlmostEqual(found[0], 25, delta=1.5)
        self.assertAlmostEqual(found[1], 50, delta=1.5)
        self.assertEqual(film_audio.analyse(tone(60, 0.3), FPS)["sections"], [])  # one long tone: no sections

    def test_scale_is_checked(self):
        with self.assertRaises(ValueError):
            film_audio.analyse([0] * RATE, FPS, scale="loud")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
    def test_the_audio_command_reads_a_wav(self):
        with tempfile.TemporaryDirectory() as d:
            write_wav(Path(d, "t.wav"), [0] * RATE + tone(3, 0.6))
            r = subprocess.run([sys.executable, str(HERE / "cli.py"), "audio", str(Path(d, "t.wav")), "--out",
                                str(Path(d, "a.json")), "--fps", "12"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(Path(d, "a.json").read_text())
            self.assertEqual((doc["fps"], doc["frames"], doc["scale"]), (12, 48, "track"))
            self.assertEqual(doc["energy"][0], 0.0)
            self.assertGreater(doc["energy"][-1], 0.9)


class LongAssembly(unittest.TestCase):
    """A construct assembles in at most 20 s; film mode allows up to 1200 s, with a warning."""

    def codes(self, seconds):
        return {d["code"]: d["severity"] for d in diagnose.diagnose(scene_with_assembly(seconds))["diagnostics"]}

    def test_up_to_20_seconds_is_a_construct(self):
        self.assertNotIn("long-assembly", self.codes(20))

    def test_longer_assemblies_are_allowed_with_a_warning(self):
        report = diagnose.diagnose(scene_with_assembly(240))
        self.assertTrue(report["ok"], report["repair_text"])
        self.assertEqual(self.codes(240).get("long-assembly"), "warning")

    def test_the_cap_is_1200_seconds(self):
        self.assertFalse(diagnose.diagnose(scene_with_assembly(1201))["ok"])
        self.assertTrue(diagnose.diagnose(scene_with_assembly(1200))["ok"])


class Cli(unittest.TestCase):
    def test_the_film_flags(self):
        for command, flags in (("video", ("--audio", "--assembly", "--sound", "--camera", "--reactivity")),
                               ("audio", ("--out", "--voice", "--scale")), ("build", ("--film",))):
            r = subprocess.run([sys.executable, str(HERE / "cli.py"), command, "--help"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for flag in flags:
                self.assertIn(flag, r.stdout, (command, flag))

    def video_page(self, *flags):
        """What `video` hands the browser: the URL parameters, and whether the page carries film mode."""
        from . import __main__ as cli
        seen = {}

        def frames(page, *args, **kwargs):
            seen["film"] = "Construct film mode" in Path(page).read_text(encoding="utf-8")
            seen["extra"] = kwargs["extra"]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(render, "frames", side_effect=frames), \
                mock.patch.object(render, "encode_video"), mock.patch("sys.stdout"):
            features = Path(d, "a.json")
            features.write_text("{}")
            argv = ["video", str(EXAMPLES / "cd.json"), "--out", str(Path(d, "x.mp4"))]
            self.assertEqual(cli.main(argv + [str(features) if f == "AUDIO" else f for f in flags]), 0)
        return seen

    def test_a_plain_video_is_the_stock_page(self):
        self.assertEqual(self.video_page(), {"film": False, "extra": {}})
        self.assertEqual(self.video_page("--camera", "still"), {"film": False, "extra": {"camera": "still"}})

    def test_film_options_reach_the_page(self):
        self.assertEqual(self.video_page("--camera", "steady"), {"film": True, "extra": {"camera": "steady"}})
        self.assertEqual(self.video_page("--camera", "tour", "--assembly", "30"), {"film": True, "extra": {"assembly": "30.000"}})
        seen = self.video_page("--audio", "AUDIO", "--reactivity", "1.5")
        self.assertEqual(seen, {"film": True, "extra": {"audio": "audio.json", "reactivity": "1.5"}})

    def test_the_skill_knows_the_film_workflow(self):
        text = (HERE / "skill" / "SKILL.md").read_text(encoding="utf-8")
        section = text[text.index("## A construct that assembles across a track"):text.index("## Rules that keep it")]
        for step in ("TOOLS audio", "--assembly", "--audio", "--sound", "--camera", "frames"):
            self.assertIn(step, section)

    def test_the_loader_is_shipped_and_neutral(self):
        text = (HERE / "film" / "construct-three.js").read_text(encoding="utf-8")
        self.assertIn("export const HOUSE_TONES", text)
        self.assertIn("export const ALBUM_TONES", text)
        self.assertIn("opt.palette || HOUSE_TONES", text)  # the house palette by default; the album one is optional
        self.assertNotIn("Math.random", text)  # re-renders match
        for word in (" he ", " she ", " his ", " her "):
            self.assertNotIn(word, text.lower())


class Stock(unittest.TestCase):
    """Film mode is strictly optional: without it, Construct writes what 0.2.1 wrote."""

    def test_the_viewer_is_the_0_2_1_viewer(self):
        self.assertEqual((HERE / "viewer" / "hologram.js").read_bytes(), (HERE / "testdata" / "hologram-0.2.1.js").read_bytes())

    def test_a_page_carries_film_mode_only_when_asked(self):
        geometry = scene.compile_scene(studio.load(str(EXAMPLES / "cd.json")))
        stock, _ = render.build_html(geometry, str(EXAMPLES))
        film, _ = render.build_html(geometry, str(EXAMPLES), film=True)
        self.assertNotIn("film mode", stock)
        self.assertNotIn("HOLO_AUDIO_READY", stock)
        code = (HERE / "viewer" / "film.js").read_text(encoding="utf-8")
        self.assertEqual(film.replace("<script>\n" + code + "\n</script>\n", "", 1), stock)  # film adds one script, nothing else


STATE_PROBE = """JSON.stringify((() => {
  const h = HOLO.hologram, out = {at: h.assemblyTimes(), timeline: HOLO.timeline(), s: []};
  for (let t = 0; t <= 40; t += 0.25) out.s.push(h.state(t));
  return out; })())"""
# the camera over time, from the hero view: the tour's flights, the drift and the breathing
CAMERA_PROBE = """JSON.stringify((() => { const h = HOLO.hologram, base = h.cameraFor("hero"), out = [];
  for (let t = 0; t <= 60; t += 0.5) out.push(h.cameraAt(t, base));
  return out; })())"""
PIXELS = """(() => { const out = []; for (const t of [1.5, 4, 9, 30]) { HOLO.renderAt(t);
  out.push(document.querySelector('canvas').toDataURL()); } return JSON.stringify(out); })()"""
TOUR = [{"view": "top", "at": 0.5, "fly": 0.6}, {"view": "side", "at": 3.5, "fly": 2}, {"view": "front", "at": 8, "fly": 2}]


def features(path, seconds, energy=1.0, onset=(), sections=(), voice_from=None, version=2):
    """A features file: energy (a number, or a function of track time), onsets and sections at given times."""
    n = int(seconds * FPS)
    e = [energy(i / FPS) if callable(energy) else energy for i in range(n)]
    doc = {"fps": FPS, "energy": e, "high": [0.0] * n,
           "voice": [0.0 if voice_from is None or i < voice_from * FPS else 1.0 for i in range(n)]}
    if version == 2:
        doc["onset"] = [0.0] * n
        for t in onset:
            doc["onset"][int(round(t * FPS))] = 1.0
        doc["sections"] = [{"t": t, "strength": 1.0} for t in sections]
    Path(path).write_text(json.dumps(doc), encoding="utf-8")


@unittest.skipUnless(CAPTURE, "no Chromium-family browser (or HOLOGRAM_SKIP_CAPTURE=1)")
class Viewer(unittest.TestCase):
    """The viewer: a page with film mode behaves exactly as the stock page without film options; with them,
    the music paces, lights, accents and stages the build. cd.json: four stages; the build runs from 1.25 s
    (after the ghost and the collapse)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        cd = studio.load(str(EXAMPLES / "cd.json"))
        toured = json.loads(json.dumps(cd))
        toured["animation"]["camera"]["tour"] = TOUR  # a camera tour authored against the scene's own assembly
        for name, doc in (("", cd), ("tour-", toured)):
            geometry = scene.compile_scene(doc)
            for kind, film in (("stock", False), ("film", True)):
                html, _ = render.build_html(geometry, str(EXAMPLES), film=film)
                Path(cls.d, name + kind + ".html").write_text(html, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def probe(self, page, expression, **query):
        b = render.open_browser(render._url(str(Path(self.d, page)), ui=0, capture=1, **query), 640, 400, 1.0)
        try:
            if query.get("audio"):
                b.evaluate("window.HOLO_AUDIO_READY.then(() => true)")
            return json.loads(b.evaluate(expression))
        finally:
            b.close()

    def test_without_film_options_film_mode_changes_nothing(self):
        # reactivity alone is not a film option: it only shapes what ?audio= brings
        for query in ({}, {"motion": "reduced"}, {"reactivity": "2"}, {"camera": "still"}):
            for page in ("", "tour-"):
                for probe in (STATE_PROBE, CAMERA_PROBE):
                    self.assertEqual(self.probe(page + "film.html", probe, **query),
                                     self.probe(page + "stock.html", probe, **query), (page, query))
        self.assertEqual(self.probe("film.html", PIXELS), self.probe("stock.html", PIXELS))

    def test_without_audio_reactivity_accents_and_sections_are_inert(self):
        for page in ("film.html", "tour-film.html"):
            plain = self.probe(page, STATE_PROBE, assembly="30")
            self.assertEqual(self.probe(page, STATE_PROBE, assembly="30", reactivity="2"), plain)
            self.assertEqual(self.probe(page, CAMERA_PROBE, assembly="30", reactivity="2"),
                             self.probe(page, CAMERA_PROBE, assembly="30"))
        # and an assembly alone only lengthens the build: the build is linear, the light the scene's own
        k = [s["build"] for s in plain["s"]]
        self.assertAlmostEqual(k[41], (10.25 - 1.25) / 30, places=6)  # t = 10.25 s
        self.assertEqual({s["globalAlpha"] for s in plain["s"][6:100]}, {1})

    def test_reactivity_0_is_an_even_build(self):
        features(Path(self.d, "r0.json"), 40, energy=lambda t: 0.0 if t < 15 else 1.0, onset=[5, 9], sections=[12])
        r0 = self.probe("film.html", STATE_PROBE, assembly="30", audio="r0.json", reactivity="0")
        self.assertEqual(r0, self.probe("film.html", STATE_PROBE, assembly="30"))

    def test_assembly_sets_the_length(self):
        at = self.probe("film.html", "JSON.stringify(HOLO.hologram.assemblyTimes())", assembly="30")
        self.assertAlmostEqual(at["build"], 30.0)

    def test_the_music_paces_the_build_and_the_light(self):
        # silence for 5 s, then full energy; a voice from 12 s. Version 1 features: no onsets, no sections
        features(Path(self.d, "audio.json"), 14, energy=lambda t: 0.0 if t < 5 else 1.0, voice_from=12, version=1)
        probe = """JSON.stringify((() => { const h = HOLO.hologram, at = h.assemblyTimes(), t0 = at.ghost + at.collapse;
          const lit = h.state(at.end + 0.6), a = h.audio; h.audio = null; const dark = h.state(at.end + 0.6); h.audio = a;
          return {quiet: h.state(4.9).build, linear: (4.9 - t0) / at.build, late: h.state(t0 + at.build - 0.05).build,
                  ratio: lit.globalAlpha / dark.globalAlpha, silent: h.state(3).globalAlpha, voice: h.state(12.5).event[0]}; })())"""
        r = self.probe("film.html", probe, assembly="10", audio="audio.json")
        self.assertLess(r["quiet"], r["linear"] / 4)  # the silent stretch nearly pauses
        self.assertGreater(r["late"], 0.97)  # and the build still ends on time
        self.assertAlmostEqual(r["ratio"], 1.4, places=2)  # full energy: the light at 1 + 0.4
        self.assertAlmostEqual(r["silent"], 0.6, places=2)  # silence: 1 - 0.4
        self.assertEqual(r["voice"], 4)  # the voice shimmer
        stronger = self.probe("film.html", probe, assembly="10", audio="audio.json", reactivity="2")
        self.assertLess(stronger["quiet"], r["quiet"])  # more reactivity, a deeper pause
        self.assertAlmostEqual(stronger["ratio"], 1.8, places=2)

    def test_an_attack_flares_and_fades(self):
        features(Path(self.d, "attack.json"), 40, energy=0.5, onset=[8])
        probe = """JSON.stringify((() => { const h = HOLO.hologram;
          return [7.9, 8, 8.2, 8.5, 9].map((t) => { const s = h.state(t); return {accent: h.accentAt(t), event: s.event,
                  stabilise: s.stabilise, alpha: s.globalAlpha, build: s.build}; }); })())"""
        before, at, later, gone, after = self.probe("film.html", probe, assembly="30", audio="attack.json")
        self.assertEqual((before["accent"], before["event"][0], before["stabilise"]), (0, 0, 0))
        self.assertEqual(at["accent"], 1)
        self.assertEqual(at["event"][0], 1)  # a scan band at the build front
        self.assertGreater(at["stabilise"], 0.7)  # and a glow pulse on what is built
        self.assertGreater(at["alpha"], before["alpha"])
        self.assertAlmostEqual(later["accent"], math.exp(-1), delta=0.03)  # about 0.2 s to fade by e
        self.assertLess(gone["accent"], 0.1)
        self.assertEqual(after["event"][0], 0)
        # the band sits where the build is drawing: within the construct's height, rising with the build
        self.assertTrue(0 <= at["event"][1] * 1.25 - 0.12 <= 1)
        self.assertEqual(self.probe("film.html", probe, assembly="30", audio="attack.json", reactivity="0")[1]["event"][0], 0)

    def test_a_new_section_starts_a_new_stage(self):
        # steady music, and a section boundary 8 s into a 20 s build: an even build would be at 0.4 there;
        # instead the third of the four stages begins (0.5), and the build still ends on time
        features(Path(self.d, "sections.json"), 30, energy=0.5, sections=[9.25])
        features(Path(self.d, "none.json"), 30, energy=0.5)
        probe = """JSON.stringify((() => { const h = HOLO.hologram;
          return {at: h.state(9.25).build, before: h.state(9.2).build, end: h.state(21.2).build}; })())"""
        staged = self.probe("film.html", probe, assembly="20", audio="sections.json")
        self.assertAlmostEqual(staged["at"], 0.5, places=6)
        self.assertLess(staged["before"], 0.5)
        self.assertGreater(staged["end"], 0.99)
        plain = self.probe("film.html", probe, assembly="20", audio="none.json")  # no sections: the paced build
        self.assertAlmostEqual(plain["at"], 0.4, delta=0.01)

    def tour(self, page="tour-film.html", **query):
        probe = """JSON.stringify((() => { const h = HOLO.hologram, base = h.cameraFor("hero");
          return {at: h.assemblyTimes(), stops: h.tourStops ? h.tourStops() : h.geo.animation.camera.tour,
                  pitch: Object.fromEntries([1.2, 5.5, 10, 10.1, 22.25, 35.6].map((t) => [t, h.cameraAt(t, base).pitch]))}; })())"""
        return self.probe(page, probe, **query)

    def test_the_tour_keeps_its_place_in_a_longer_assembly(self):
        # the tour has one stop before the build (0.5 s), one halfway through it (3.5 s) and one after it (8 s)
        own, film = self.tour("tour-stock.html"), self.tour(assembly="30")
        self.assertEqual(own["stops"], TOUR)
        before, during, after = film["stops"]
        self.assertEqual(before, TOUR[0])  # before the build: where it was
        self.assertAlmostEqual(during["at"], 1.25 + 0.5 * 30)  # halfway through the film's build
        self.assertAlmostEqual(during["fly"], 2 * 3)  # the flight scaled with the build, at most 3x
        self.assertAlmostEqual(after["at"], 8 + (30 - 4.5))  # after the build: moved by as much as the end
        self.assertEqual(after["fly"], 2)
        # the pitch is the tour's alone (drift turns the yaw, breathing the distance). Mid-build the film's
        # camera has finished the first flight and not begun the second, as the scene's own camera at 1.2 s
        self.assertAlmostEqual(film["pitch"]["10"], own["pitch"]["1.2"], places=6)
        self.assertAlmostEqual(film["pitch"]["22.25"], own["pitch"]["5.5"], places=6)  # the second flight landed
        self.assertAlmostEqual(film["pitch"]["35.6"], own["pitch"]["10.1"], places=6)  # and the third

    def test_with_music_a_tour_stop_follows_the_build(self):
        # silence until 15 s of track time, then full energy: the build is slow first, then fast
        features(Path(self.d, "tour-audio.json"), 40, energy=lambda t: 0.0 if t < 15 else 1.0)
        probe = """JSON.stringify((() => { const h = HOLO.hologram, s = h.tourStops()[1];
          return {stop: s, there: h.state(s.at).build, frame: h.state(s.at - 1 / 24).build}; })())"""
        plain = self.tour(assembly="30")
        for query in ({"assembly": "30"}, {}):  # a film's length, or the scene's own
            film = self.tour(audio="tour-audio.json", **query)
            before, during, after = film["stops"]
            self.assertEqual(before, TOUR[0])
            self.assertAlmostEqual(after["at"], 8 + (film["at"]["build"] - 4.5))
            r = self.probe("tour-film.html", probe, audio="tour-audio.json", **query)
            self.assertGreaterEqual(r["there"], 0.5)  # the stop comes as the build reaches halfway
            self.assertLess(r["frame"], 0.5)  # and not a frame later
        # the long silence builds slowly, so halfway comes much later than in the even build
        film = self.tour(audio="tour-audio.json", assembly="30")
        self.assertGreater(film["stops"][1]["at"], plain["stops"][1]["at"] + 5)
        self.assertEqual(film["stops"][1]["fly"], plain["stops"][1]["fly"])

    def test_a_steady_camera_flies_no_tour_but_keeps_drifting(self):
        probe = """JSON.stringify((() => { const h = HOLO.hologram, base = h.cameraFor("hero");
          return {base, cams: [0, 5.5, 12, 40].map((t) => h.cameraAt(t, base))}; })())"""
        for query in ({}, {"assembly": "30"}):
            steady = self.probe("tour-film.html", probe, camera="steady", **query)
            still = self.probe("tour-film.html", probe, camera="still", **query)
            toured = self.probe("tour-film.html", probe, **query)
            base = steady["base"]
            for cam in steady["cams"]:  # no flight: the view's own target and pitch, all the way
                self.assertEqual((cam["target"], cam["pitch"]), (base["target"], base["pitch"]), query)
            self.assertGreater(steady["cams"][3]["yaw"], steady["cams"][0]["yaw"] + 1)  # but it drifts
            self.assertNotEqual(steady["cams"][3]["dist"], base["dist"])  # and breathes
            self.assertEqual(still["cams"], [base] * 4)  # still: nothing moves
            self.assertTrue(any(c["pitch"] != base["pitch"] for c in toured["cams"]))  # the tour flies

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is not installed")
    def test_a_film_with_its_sound(self):
        d = self.d
        write_wav(Path(d, "t.wav"), tone(3, 0.5))
        cli = [sys.executable, str(HERE / "cli.py")]
        r = subprocess.run(cli + ["audio", str(Path(d, "t.wav")), "--out", str(Path(d, "f.json")), "--fps", "12"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(cli + ["video", str(EXAMPLES / "cd.json"), "--out", str(Path(d, "f.mp4")), "--size", "320x200",
                                  "--fps", "12", "--assembly", "2", "--audio", str(Path(d, "f.json")), "--sound",
                                  str(Path(d, "t.wav"))], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                                  str(Path(d, "f.mp4"))], capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(streams), ["audio", "video"])


if __name__ == "__main__":
    unittest.main()
