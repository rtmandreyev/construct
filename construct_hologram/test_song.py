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


class Rings(unittest.TestCase):
    def test_a_closed_surface_through_rings(self):
        from collections import Counter
        from . import shapes
        rings = [[[math.cos(2 * math.pi * j / 8) * (1 + 0.3 * i), i * 0.5, math.sin(2 * math.pi * j / 8) * (1 + 0.3 * i)]
                  for j in range(8)] for i in range(5)]
        for order in (rings, [list(reversed(r)) for r in rings]):   # either winding: faces point outward
            m = shapes.rings_surface(order)
            key = lambda p: tuple(round(v, 6) for v in p)
            edges = Counter(tuple(sorted((key(u), key(v)))) for a, b, c in m.tris for u, v in ((a, b), (b, c), (c, a)))
            self.assertEqual(set(edges.values()), {2})   # watertight: every edge between two faces
            vol = sum(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
                      for a, b, c in m.tris)
            self.assertGreater(vol, 0)
        self.assertEqual(len(shapes.rings_surface(rings).tris), 4 * 8 * 2 + 2 * 8)
        good = {"id": "x", "label": "x", "role": "mass", "certainty": "verified", "source": "s", "shape": {"type": "rings",
                "rings": rings}}
        for bad in ({"rings": rings[:1]}, {"rings": [rings[0], rings[1][:5]]}, {"rings": rings, "caps": "yes"}):
            sc = json.loads((HERE / "examples" / "v2" / "cd.json").read_text())
            sc["parts"].append(dict(good, shape=dict(good["shape"], **bad)))
            self.assertTrue(any("rings" in e or "caps" in e for e in scene.validate(sc)), bad)


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
            solid = song.scene_from_track(Path(d, "t.wav"), "Test", rings=16, solid=True)   # a body to print
            body = next(p for p in solid["parts"] if p["id"] == "body")
            self.assertEqual((body["shape"]["type"], len(body["shape"]["rings"])), ("rings", 16))
            gs = scene.compile_scene(solid)
            self.assertEqual(audit.audit(solid, gs)["errors"], [])
            self.assertGreater(sum(len(p.get("tris", [])) for p in gs["parts"]) if gs["parts"] and "tris" in gs["parts"][0]
                               else 1, 0)


def _vl(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _track(events, name=None):
    data, last = (_vl(0) + b"\xff\x03" + _vl(len(name)) + name.encode()) if name else b"", 0
    for t, ev in sorted(events, key=lambda e: e[0]):
        data += _vl(t - last) + ev
        last = t
    data += _vl(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + data


def midi_file(path):
    """A small piece: a tempo track (120 bpm, 4/4), a scale of 8 notes and a C major chord held for a bar."""
    div = 480
    meta = [(0, b"\xff\x51\x03" + (500000).to_bytes(3, "big")), (0, b"\xff\x58\x04\x04\x02\x18\x08")]
    mel = [e for i, p in enumerate([60, 62, 64, 65, 67, 69, 71, 72])
           for e in ((i * div, bytes([0x90, p, 90])), (i * div + div // 2, bytes([0x90, p, 0])))]   # note-on 0: off
    chord = [e for p in (48, 52, 55) for e in ((0, bytes([0x91, p, 70])), (4 * div, bytes([0x81, p, 0])))]
    Path(path).write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, 3, div) + _track(meta) + _track(mel, "Melody")
                           + _track(chord, "Chords"))


class Score(unittest.TestCase):
    def test_a_midi_file_read_and_drawn(self):
        from . import score
        with tempfile.TemporaryDirectory() as d:
            midi_file(Path(d, "p.mid"))
            m = score.read_midi(Path(d, "p.mid"))
            self.assertEqual((len(m["notes"]), m["length"], m["meter"], m["tempo"], m["names"]),
                             (11, 3.75, "4/4", 120.0, {1: "Melody", 2: "Chords"}))
            first = m["notes"][0]
            self.assertEqual((first[0], first[1]), (0.0, 0.25))     # half a beat at 120 bpm
            self.assertEqual(len(m["bars"]), 2)                       # bars at 0 and 2 s
            sc = score.scene_from_midi(Path(d, "p.mid"), "Piece")
            self.assertEqual([e for e in scene.validate(sc)], [])
            self.assertEqual(audit.audit(sc, scene.compile_scene(sc))["errors"], [])
            self.assertIsNone(netlogo.lock_problem(sc))
            labels = sorted(p["label"].split(":")[0] for p in sc["parts"] if p["id"].startswith("notes"))
            self.assertEqual(labels, ["Chords", "Melody"])
            c, g = score._place(60, 4), score._place(67, 4)        # C at the front, G one step round the circle of fifths
            self.assertAlmostEqual(c[0], 0.0, places=6)
            self.assertAlmostEqual(math.atan2(g[0], g[1]), math.pi / 6, places=6)
            moved = json.loads(json.dumps(sc))
            next(p for p in moved["parts"] if p["id"].startswith("notes"))["shape"]["paths"][0][1][1] += 1
            self.assertIn("score", netlogo.lock_problem(moved))
            Path(d, "bad.mid").write_bytes(b"RIFF")
            with self.assertRaises(score.ScoreError):
                score.read_midi(Path(d, "bad.mid"))
            Path(d, "cut.mid").write_bytes(Path(d, "p.mid").read_bytes()[:60])   # cut short: a clear error
            with self.assertRaises(score.ScoreError):
                score.read_midi(Path(d, "cut.mid"))

    def test_a_meter_change_and_the_clock(self):
        from . import score
        div = 480
        meta = [(0, b"\xff\x51\x03" + (500000).to_bytes(3, "big")), (0, b"\xff\x58\x04\x03\x02\x18\x08"),
                (4 * 3 * div, b"\xff\x58\x04\x04\x02\x18\x08")]   # a waltz, then 4/4 after four bars
        mel = [e for i in range(24) for e in ((i * div, bytes([0x90, 60, 80])), (i * div + 200, bytes([0x80, 60, 0])))]
        with tempfile.TemporaryDirectory() as d:
            Path(d, "w.mid").write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, 2, div) + _track(meta) + _track(mel))
            m = score.read_midi(Path(d, "w.mid"))
        self.assertEqual((m["meter"], [round(x, 2) for x in m["bars"]]), ("3/4", [0.0, 1.5, 3.0, 4.5, 6.0, 8.0, 10.0]))
        self.assertEqual((song._clock(119.6), song._clock(59.7), song._clock(12.4)), ("2:00", "1:00", "12 s"))


if __name__ == "__main__":
    unittest.main()
