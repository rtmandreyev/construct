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
        for command, flags in (("video", ("--audio", "--assembly", "--sound")), ("audio", ("--out", "--voice", "--scale"))):
            r = subprocess.run([sys.executable, str(HERE / "cli.py"), command, "--help"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for flag in flags:
                self.assertIn(flag, r.stdout, (command, flag))

    def test_the_loader_is_shipped_and_neutral(self):
        text = (HERE / "film" / "construct-three.js").read_text(encoding="utf-8")
        self.assertIn("export const HOUSE_TONES", text)
        self.assertIn("export const ALBUM_TONES", text)
        self.assertIn("opt.palette || HOUSE_TONES", text)  # the house palette by default; the album one is optional
        self.assertNotIn("Math.random", text)  # re-renders match
        for word in (" he ", " she ", " his ", " her "):
            self.assertNotIn(word, text.lower())


STATE_PROBE = """JSON.stringify((() => {
  const h = HOLO.hologram, out = {at: h.assemblyTimes(), timeline: HOLO.timeline(), s: []};
  for (let t = 0; t <= 40; t += 0.25) out.s.push(h.state(t));
  return out; })())"""
# the camera over time, from the hero view: the tour's flights, the drift and the breathing
CAMERA_PROBE = """JSON.stringify((() => { const h = HOLO.hologram, base = h.cameraFor("hero"), out = [];
  for (let t = 0; t <= 60; t += 0.5) out.push(h.cameraAt(t, base));
  return out; })())"""
TOUR = [{"view": "top", "at": 8, "fly": 2}, {"view": "side", "at": 14, "fly": 3}]


@unittest.skipUnless(CAPTURE, "no Chromium-family browser (or HOLOGRAM_SKIP_CAPTURE=1)")
class Viewer(unittest.TestCase):
    """The viewer: identical to the viewer before film mode without ?audio, and audio-driven with it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        new = (HERE / "viewer" / "hologram.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        old = (HERE / "testdata" / "hologram-0.2.1.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        cd = studio.load(str(EXAMPLES / "cd.json"))
        toured = json.loads(json.dumps(cd))
        toured["animation"]["camera"]["tour"] = TOUR  # a camera tour authored against the scene's own assembly
        for name, doc in (("", cd), ("tour-", toured)):
            html, _ = render.build_html(scene.compile_scene(doc), str(EXAMPLES))
            assert html.count(new) == 1
            Path(cls.d, name + "new.html").write_text(html, encoding="utf-8")
            Path(cls.d, name + "old.html").write_text(html.replace(new, old), encoding="utf-8")

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

    def test_without_audio_the_viewer_is_unchanged(self):
        for query in ({}, {"motion": "reduced"}):
            self.assertEqual(self.probe("new.html", STATE_PROBE, **query), self.probe("old.html", STATE_PROBE, **query),
                             query)
        pixels = "(() => { const out = []; for (const t of [1.5, 4, 9, 30]) { HOLO.renderAt(t); " \
                 "out.push(document.querySelector('canvas').toDataURL()); } return JSON.stringify(out); })()"
        self.assertEqual(self.probe("new.html", pixels), self.probe("old.html", pixels))
        for probe in (STATE_PROBE, CAMERA_PROBE):  # a scene with a camera tour, too
            self.assertEqual(self.probe("tour-new.html", probe), self.probe("tour-old.html", probe))

    def test_a_longer_assembly_moves_the_tour_after_it(self):
        probe = """JSON.stringify((() => { const h = HOLO.hologram, base = h.cameraFor("hero");
          return {delta: h.assemblyTimes().end - h.assemblyTimes(true).end, stops: h.tourStops().map((s) => s.at),
                  pitch: [0, 9.9, 12, 37.5].map((t) => h.cameraAt(t, base).pitch)}; })())"""
        film = self.probe("tour-new.html", probe, assembly="30")
        scene_own = self.probe("tour-new.html", probe)
        self.assertAlmostEqual(film["delta"], 30 - 4.5)  # the build is 25.5 s longer; the ghost and the settle are not
        self.assertEqual(scene_own["delta"], 0)
        self.assertEqual(scene_own["stops"], [s["at"] for s in TOUR])
        for got, stop in zip(film["stops"], TOUR):
            self.assertAlmostEqual(got, stop["at"] + film["delta"])
        # the pitch is the tour's alone (drift turns the yaw, breathing the distance): mid-build, where the
        # scene's own tour has already flown to the top view, the film's camera holds the hero's pitch
        self.assertEqual(film["pitch"][1], film["pitch"][0])
        self.assertGreater(scene_own["pitch"][1], scene_own["pitch"][0] + 20)
        # and after the build it is where the scene's own was, delta seconds earlier
        self.assertAlmostEqual(film["pitch"][3], scene_own["pitch"][2], places=6)

    def test_assembly_sets_the_length(self):
        at = self.probe("new.html", "JSON.stringify(HOLO.hologram.assemblyTimes())", assembly="30")
        self.assertAlmostEqual(at["build"], 30.0)

    def test_the_music_paces_the_build_and_the_light(self):
        n = 14 * FPS  # silence for 5 s, then full energy; a voice from 12 s
        energy = [0.0] * (5 * FPS) + [1.0] * (n - 5 * FPS)
        voice = [0.0] * (12 * FPS) + [1.0] * (n - 12 * FPS)
        Path(self.d, "audio.json").write_text(json.dumps({"fps": FPS, "energy": energy, "high": [0.0] * n,
                                                          "voice": voice}), encoding="utf-8")
        # the features follow track time: the build starts after the ghost and the collapse (t0)
        probe = """JSON.stringify((() => { const h = HOLO.hologram, at = h.assemblyTimes(), t0 = at.ghost + at.collapse;
          const k = (t) => h.state(t0 + t).build;
          const lit = h.state(at.end + 0.6), a = h.audio; h.audio = null; const dark = h.state(at.end + 0.6); h.audio = a;
          return {quiet: h.state(4.9).build, linear: (4.9 - t0) / at.build, late: k(at.build - 0.05),
                  ratio: lit.globalAlpha / dark.globalAlpha, voice: h.state(12.5).event[0]}; })())"""
        r = self.probe("new.html", probe, assembly="10", audio="audio.json")
        self.assertLess(r["quiet"], r["linear"] / 3)  # the silent stretch builds slowly, far behind a linear build
        self.assertGreater(r["late"], 0.97)  # and it still ends on time
        self.assertAlmostEqual(r["ratio"], 1.18, places=2)  # full energy: the light at 0.82 + 0.36
        self.assertEqual(r["voice"], 4)  # the voice shimmer

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
