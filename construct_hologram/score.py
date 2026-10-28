"""A score as a construct: a MIDI file's notes standing in a cylinder of time. Python standard library only.

    construct song piece.mid --out scene.json [--track piece.mp3] [--title "Title"]

Each note is a line of light that rises from its start to its end (height is time), standing at its
pitch's place on the circle of fifths (keys and chords close together, all around the axis), further
out for a higher octave. Each MIDI track is a tone of its own; faint rings mark each bar, from the file's
tempo and time signature. With --track (the piece as audio), the page builds in time with it and plays
it, as a song's does; without, it builds over the piece's own length. Everything drawn comes from the
file, under a data lock (source `score`).
"""

import hashlib
import json
import math
import struct
from pathlib import Path

from . import film_audio, netlogo, product

HEIGHT = 10.0
R0, OCTAVE = 1.0, 0.42        # a note's radius: the lowest octave, then this much further out for each one up
MAX_NOTES = 9000              # each note is one line; a construct holds 24,000
TONES = ("identity", "accent", "data", "bright", "structure", "dust")


class ScoreError(ValueError):
    pass


def _varlen(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def read_midi(path):
    """The notes of a Standard MIDI File, as (start_s, end_s, pitch, velocity, track), its tempo changes and its
    time signature, and its length in seconds."""
    data = Path(path).read_bytes()
    if data[:4] != b"MThd":
        raise ScoreError("%s is not a MIDI file (no MThd header)" % Path(path).name)
    hlen, fmt, ntrk, div = struct.unpack(">IHHH", data[4:14])
    if div & 0x8000:
        raise ScoreError("SMPTE-timed MIDI files are not read; save it with a tempo (ticks per beat)")
    try:
        return _read(data, hlen, fmt, ntrk, div, Path(path).name)
    except (IndexError, struct.error, ValueError) as exc:
        if isinstance(exc, ScoreError):
            raise
        raise ScoreError("%s is damaged or cut short" % Path(path).name)


def _read(data, hlen, fmt, ntrk, div, name):
    i = 8 + hlen
    events, tempos, meters, names = [], [(0, 500000)], [], {}
    for trk in range(ntrk):
        if data[i:i + 4] != b"MTrk":
            raise ScoreError("track %d of %s is damaged" % (trk, name))
        n = struct.unpack(">I", data[i + 4:i + 8])[0]
        j, end, t, status = i + 8, i + 8 + n, 0, 0
        while j < end:
            dt, j = _varlen(data, j)
            t += dt
            b = data[j]
            if b == 0xFF:   # meta
                kind = data[j + 1]
                ln, j = _varlen(data, j + 2)
                body = data[j:j + ln]
                if kind == 0x51 and ln == 3:
                    tempos.append((t, int.from_bytes(body, "big")))
                elif kind == 0x58 and ln >= 2:
                    meters.append((t, body[0], 2 ** body[1]))
                elif kind == 0x03 and trk not in names:   # the track's name
                    names[trk] = body.decode("latin-1").strip()[:40]
                j += ln
                continue
            if b in (0xF0, 0xF7):   # sysex
                ln, j = _varlen(data, j + 1)
                j += ln
                continue
            if b & 0x80:
                status, j = b, j + 1
            kind = status & 0xF0
            if kind in (0x80, 0x90):
                pitch, vel = data[j], data[j + 1]
                events.append((t, trk, status & 0x0F, pitch, vel if kind == 0x90 else 0))
                j += 2
            elif kind in (0xA0, 0xB0, 0xE0):
                j += 2
            elif kind in (0xC0, 0xD0):
                j += 1
            else:
                raise ScoreError("an unknown MIDI event in track %d" % trk)
        i = end
    tempos = sorted(dict(tempos).items())

    def seconds(tick):   # the tempo map, piece by piece
        s, last_t, last_us = 0.0, 0, tempos[0][1]
        for tt, us in tempos:
            if tt >= tick:
                break
            s += (tt - last_t) * last_us / div / 1e6
            last_t, last_us = tt, us
        return s + (tick - last_t) * last_us / div / 1e6

    notes, held = [], {}
    for t, trk, ch, pitch, vel in sorted(events, key=lambda e: (e[0], e[4] == 0)):
        key = (trk, ch, pitch)
        if vel > 0:
            held.setdefault(key, []).append((t, vel))
        elif held.get(key):
            t0, v = held[key].pop(0)
            notes.append((seconds(t0), seconds(t), pitch, v, trk))
    if not notes:
        raise ScoreError("%s has no notes" % name)
    length = max(n[1] for n in notes)
    # the bars, meter by meter (4/4 until the file says otherwise), never a bar shorter than a tick
    meters = sorted({t: (t, n, d) for t, n, d in ([(0, 4, 4)] + sorted(meters))}.values())
    bars = []
    for k, (t0, num, den) in enumerate(meters):
        t1 = meters[k + 1][0] if k + 1 < len(meters) else None
        step = max(1, div * max(1, num) * 4 // max(1, den))
        tk = t0
        while (t1 is None or tk < t1) and seconds(tk) <= length:
            bars.append(seconds(tk))
            tk += step
    return {"notes": sorted(notes), "length": length, "bars": bars, "division": div, "format": fmt, "tracks": ntrk,
            "names": names,
            "meter": "%d/%d" % (meters[0][1], meters[0][2]), "tempo": round(60e6 / tempos[0][1], 2)}


def _part(pid, label, role, paths, tone=None, weight=None, alpha=None):
    p = {"id": pid, "label": label, "role": role, "shape": {"type": "paths", "paths": paths}, "certainty": "verified",
         "stage": 0, "source": "score", "floating": True}
    look = {k: v for k, v in (("tone", tone), ("weight", weight), ("alpha", alpha)) if v is not None}
    if look:
        p["look"] = look
    return p


def _place(pitch, lo_oct):
    """A pitch's place: its angle on the circle of fifths, its radius by octave."""
    th = 2 * math.pi * ((pitch * 7) % 12) / 12
    r = R0 + OCTAVE * (pitch // 12 - lo_oct)
    return r * math.sin(th), r * math.cos(th)


def scene_from_midi(path, title=None, track=None):
    """A construct-scene v2 of a MIDI file (see the module docstring); `track`: the piece as audio, to play with."""
    path = Path(path)
    m = read_midi(path)
    notes = m["notes"]
    if len(notes) > MAX_NOTES:
        raise ScoreError("%d notes: at most %d fit a construct (each is a line)" % (len(notes), MAX_NOTES))
    T = m["length"]
    lo_oct = min(n[2] for n in notes) // 12
    y = lambda s: round(HEIGHT * s / T, 4)
    by_track = {}
    for s0, s1, pitch, vel, trk in notes:
        x, z = _place(pitch, lo_oct)
        by_track.setdefault(trk, []).append([[round(x, 4), y(s0), round(z, 4)], [round(x, 4), max(y(s1), y(s0) + 0.02), round(z, 4)]])
    reach = R0 + OCTAVE * (max(n[2] for n in notes) // 12 - lo_oct) + 0.35
    bar_rings = [[[round(reach * math.sin(2 * math.pi * k / 48), 4), y(b), round(reach * math.cos(2 * math.pi * k / 48), 4)]
                  for k in range(49)] for b in m["bars"][::max(1, len(m["bars"]) // 120)]]
    wheel = []   # the circle of fifths on the floor: a spoke for each pitch class
    names = ["C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#", "F"]
    for k in range(12):
        th = 2 * math.pi * k / 12
        wheel.append([[round(R0 * 0.6 * math.sin(th), 4), 0, round(R0 * 0.6 * math.cos(th), 4)],
                      [round(reach * math.sin(th), 4), 0, round(reach * math.cos(th), 4)]])
    parts = [_part("wheel", "The circle of fifths on the floor (C at the front)", "ground", wheel, alpha=0.5, weight=0.6),
             _part("bars", "A ring at each bar (%s)" % m["meter"], "detail", bar_rings, tone="dust", alpha=0.3, weight=0.4)]
    parts[0]["floating"] = False
    for k, (trk, paths) in enumerate(sorted(by_track.items(), key=lambda kv: -len(kv[1]))):
        name = m["names"].get(trk) or "Track %d" % (sorted(by_track).index(trk) + 1)
        for c in range(0, len(paths), 4000):   # a shape holds 4,000 lines: a long part in pieces
            parts.append(_part("notes-track-%d%s" % (trk, "-%d" % (c // 4000 + 1) if c else ""),
                               "%s: %d notes, each rising from its start to its end" % (name, len(paths)),
                               "identity" if k == 0 else "data", paths[c:c + 4000],
                               tone=TONES[k % len(TONES)], weight=1.0 if k == 0 else 0.8))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    title = title or path.stem
    clock = lambda s: "%d:%02d" % divmod(int(round(s)), 60)
    facts = [{"key": "score", "value": path.name, "certainty": "verified", "source": "score"},
             {"key": "sha256", "value": sha, "certainty": "verified", "source": "score"},
             {"key": "notes", "value": len(notes), "certainty": "verified", "source": "score"},
             {"key": "seconds", "value": round(T, 2), "certainty": "verified", "source": "score"},
             {"key": "tempo", "value": "%g bpm at the start, %s" % (m["tempo"], m["meter"]), "certainty": "verified",
              "source": "score"},
             {"key": "view", "value": "score", "certainty": "user_supplied", "source": "request"},
             {"key": "coordinates", "value": "Y is up. Height is time, %g m from the first note to the end; around the "
                                             "axis, the circle of fifths (C at the front, G to its right); out from it, "
                                             "the octave, %g m each." % (HEIGHT, OCTAVE),
              "certainty": "user_supplied", "source": "request"}]
    slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-")[:48] or "score"
    how = ["Height is time: the piece starts on the floor and ends at the top, %s in all." % clock(T),
           "Each line is one note, rising from where it starts to where it ends; a long note is a tall line.",
           "Around the axis, the circle of fifths (C at the front): notes of one key stand together, and a chord is a "
           "cluster.",
           "Further out is higher: each octave a ring further from the middle.",
           "Each MIDI track has its own colour; the faint rings are the bars."]
    sc = {
        "format": product.SCENE_FORMAT, "version": 2, "id": "score-%s" % slug, "title": title,
        "subject": {"category": "other", "accuracy": "documented", "synthetic": False,
                    "summary": "%s as a sculpture of its score: every note a line of light rising through time, around "
                               "the circle of fifths." % title},
        "units": "m", "seed": 7,
        "sources": [{"id": "request", "kind": "user_request", "title": "A construct of a score", "rights": "user_private"},
                    {"id": "score", "kind": "dataset", "title": "%s, read by construct song" % path.name,
                     "rights": "permitted"}],
        "facts": facts, "parts": parts, "annotations": [],
        "presentation": {"framing": {"yaw": 28, "pitch": 30}, "atmosphere": {"haze": 0.6, "grid": False, "projector": False,
                                                                           "motes": 0}, "labels": True},
        "animation": {"assembly": {"style": "build", "seconds": 12.0},
                      "idle": {"life": "calm", "events": ["scan"], "cadence": [8, 14], "strength": 0.4},
                      "camera": {"drift": 4, "breathe": 0.02}},
        "reading": {"how": how, "clock": {"label": "second", "from": 0, "to": round(T, 3), "top": HEIGHT, "scale": "linear"}},
    }
    for i, p in enumerate(q for q in parts if q["id"].startswith("notes") or q["id"] == "wheel"):   # labels on real points
        pts = [v for path_ in p["shape"]["paths"] for v in path_]
        lo = [min(v[k] for v in pts) for k in range(3)]
        hi = [max(v[k] for v in pts) for k in range(3)]
        anchor = [(lo[0] + hi[0]) / 2, hi[1], (lo[2] + hi[2]) / 2]
        d = netlogo.LEGEND_DIRS[i % len(netlogo.LEGEND_DIRS)]
        best = max(pts, key=lambda v: v[0] * d[0] + v[1] * d[1] + v[2] * d[2])
        sc["annotations"].append({"id": "legend-" + p["id"], "part": p["id"], "text": p["label"][:80],
                                  "offset": [round(best[k] - anchor[k], 3) for k in range(3)]})
    if track:   # the piece as audio: the page builds in time with it and plays it
        tp = Path(track)
        feats = film_audio.analyse(film_audio._decode(tp), 30)
        sc["reading"]["music"] = {"track": tp.name, "sha256": hashlib.sha256(tp.read_bytes()).hexdigest(),
                                  "ticks_per_second": 1, "seconds": round(T, 2),
                                  "audio": {"fps": 30, **{k: feats[k] for k in ("energy", "high", "kick", "onset")}}}
        sc["reading"]["how"].append("Press play to hear the piece as the score builds.")
    else:
        sc["animation"]["assembly"]["seconds"] = round(min(1200.0, max(12.0, T)), 2)
    sc["facts"].append({"key": netlogo.LOCK, "value": netlogo.data_lock(sc, "score"), "certainty": "verified",
                        "source": "score", "note": "The notes, bars and wheel as `construct song` drew them from the MIDI "
                                                   "file, and its facts. The audit refuses the scene if any of it changes."})
    return sc
