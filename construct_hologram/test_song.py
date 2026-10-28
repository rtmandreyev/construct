"""A song as a construct: the spectrum per slice, the rings' shape, the scene, its lock and its page."""

import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from . import audit, netlogo, render, scene, song

HERE = Path(__file__).resolve().parent
RATE = song.RATE


def tone(seconds, amp, freq):
    return [int(32767 * amp * math.sin(2 * math.pi * freq * i / RATE)) for i in range(int(seconds * RATE))]


class Spectrum(unittest.TestCase):
    def test_a_low_tone_bulges_the_front_and_a_high_one_the_back(self):
        low = song.spectra(tone(2, 0.5, 90.0), 4)[1]
        high = song.spectra(tone(2, 0.5, 4000.0), 4)[1]
        self.assertLess(low.index(max(low)), 4)                 # the lowest bands
        self.assertGreater(high.index(max(high)), song.BANDS - 6)   # the highest
        ring_low = song._ring([1.0] * 4 + [0.0] * (song.BANDS - 4), 1.0)
        front, back = ring_low[0], ring_low[song.POINTS // 2]
        self.assertGreater(math.hypot(front[0], front[2]), math.hypot(back[0], back[2]) + 1.0)
        self.assertEqual(ring_low[0], ring_low[-1])   # closed

    def test_a_loud_moment_is_a_big_ring(self):
        quiet = [v * 0.05 for v in tone(1, 1.0, 300.0)]
        loud = tone(1, 0.8, 300.0)
        lv = song.normalised(song.spectra([int(x) for x in quiet] + loud, 4), smooth=0)
        self.assertLess(sum(lv[0]), sum(lv[3]))


class Scene(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
    def test_a_track_is_a_locked_tower_that_plays_with_its_track(self):
        with tempfile.TemporaryDirectory() as d:
            sig = tone(3, 0.2, 110.0) + tone(3, 0.7, 2000.0)
            with wave.open(str(Path(d, "t.wav")), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(struct.pack("<%dh" % len(sig), *sig))
            sc = song.scene_from_track(Path(d, "t.wav"), "Test", rings=16)
            self.assertEqual([e for e in scene.validate(sc)], [])
            g = scene.compile_scene(sc)
            self.assertEqual(audit.audit(sc, g)["errors"], [])
            self.assertIsNone(netlogo.lock_problem(sc))
            self.assertEqual(sc["reading"]["clock"]["to"], 6.0)
            self.assertEqual((sc["reading"]["music"]["track"], sc["reading"]["music"]["ticks_per_second"]), ("t.wav", 1))
            moved = json.loads(json.dumps(sc))
            moved["parts"][2]["shape"]["paths"][0][0][0] += 1.0   # a ring changed: the lock sees it
            self.assertIn("construct song", netlogo.lock_problem(moved))
            page, _ = render.build_html(g)
            self.assertIn("runCurve", page)   # it builds in time with the track, which the replay bar plays
            r = subprocess.run([sys.executable, str(HERE / "cli.py"), "song", str(Path(d, "t.wav")), "--out",
                                str(Path(d, "out", "scene.json")), "--rings", "16"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(d, "out", "t.wav").is_file())
            with self.assertRaises(song.SongError):
                song.scene_from_track(Path(d, "t.wav"), rings=4)


if __name__ == "__main__":
    unittest.main()
