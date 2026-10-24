"""Film mode: per-frame audio features for a construct's long assembly (Python standard library + ffmpeg).

    construct audio track.wav --out audio.json [--voice stem.wav] [--fps 24] [--scale track|fixed]

writes {"format": "construct-audio", "version": 1, "fps", "energy": [...], "high": [...], "voice": [...], ...},
one value per video frame, each 0..1:

energy[f]  the music's short-term loudness at frame f, smoothed like a meter (fast up, slow down). By default
           each track is mapped to its own range, its 5th to 95th percentile of loudness, so a loud master
           still moves between quiet and loud; `scale="fixed"` keeps the older fixed -40..-10 dBFS window.
high[f]    brightness and attacks: the level of the first difference of the signal (a simple high-pass),
           mapped to the track's own range the same way and smoothed quickly.
voice[f]   a voice stem's level (-60..-10 dBFS), or zeros without a stem.

ffmpeg decodes any format it reads to 16 kHz mono; everything after that is the standard library.
"""

import json
import math
import struct
import subprocess

RATE = 16000
SILENT_DB = -60.0  # quieter than this, a frame counts as silence: energy and high are 0 there
MIN_SPAN_DB = 12.0  # a track's range is at least this wide, so a steady tone does not flicker between 0 and 1
FIXED = (-40.0, -10.0)  # the older window, for `scale="fixed"`


def _decode(path, sr=RATE):
    """The audio as 16-bit mono samples at sr, decoded by ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    n = len(raw) // 2
    return struct.unpack("<%dh" % n, raw[:n * 2])


def _db(ms):
    return 10 * math.log10(ms / 32768.0 ** 2 + 1e-12)


def levels(samples, fps, sr=RATE):
    """Per frame: (loudness, high) in dBFS. Loudness is the frame's RMS level; high is the RMS level of the
    first difference x[n] - x[n-1], which weights the upper frequencies and the attacks."""
    hop = sr // fps
    loud, high = [], []
    prev = 0
    for i in range(0, len(samples) - hop + 1, hop):
        seg = samples[i:i + hop]
        ms = sum(x * x for x in seg) / hop
        dms = 0
        for x in seg:
            d = x - prev
            dms += d * d
            prev = x
        loud.append(_db(ms))
        high.append(_db(dms / hop / 4.0))  # a first difference can be twice the signal's swing
    return loud, high


def _percentile(values, q):
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def track_range(dbs, lo_q=0.05, hi_q=0.95):
    """The window a track is mapped to: its 5th to 95th percentile of loudness over the frames that are not
    silent, at least MIN_SPAN_DB wide (extended downwards). None for a silent track."""
    heard = [x for x in dbs if x > SILENT_DB]
    if not heard:
        return None
    lo, hi = _percentile(heard, lo_q), _percentile(heard, hi_q)
    return (min(lo, hi - MIN_SPAN_DB), hi)


def _scaled(dbs, window, attack, release):
    """0..1 per frame, mapped through the window, smoothed like a meter (attack and release per frame)."""
    out, s = [], 0.0
    for db in dbs:
        if window is None or db <= SILENT_DB:
            x = 0.0
        else:
            lo, hi = window
            x = min(1.0, max(0.0, (db - lo) / (hi - lo)))
        s += (x - s) * (attack if x > s else release)
        out.append(round(s, 3))
    return out


def analyse(samples, fps=24, scale="track", voice_samples=None, sr=RATE):
    """The features document for decoded samples (see the module docstring)."""
    if scale not in ("track", "fixed"):
        raise ValueError("scale is 'track' or 'fixed'")
    loud, high = levels(samples, fps, sr)
    window = track_range(loud) if scale == "track" else FIXED
    high_window = track_range(high) if scale == "track" else (FIXED[0] - 10, FIXED[1] - 10)
    energy = _scaled(loud, window, 0.08, 0.02)
    brightness = _scaled(high, high_window, 0.6, 0.25)
    voice = [0.0] * len(energy)
    if voice_samples is not None:
        vl, _ = levels(voice_samples, fps, sr)
        s = 0.0
        for i in range(min(len(voice), len(vl))):
            x = min(1.0, max(0.0, (vl[i] + 60) / 50))
            s += (x - s) * (0.5 if x > s else 0.15)
            voice[i] = round(s, 3)
    doc = {"format": "construct-audio", "version": 1, "fps": fps, "frames": len(energy), "scale": scale,
           "energy": energy, "high": brightness, "voice": voice}
    if window is not None:
        doc["range_db"] = [round(window[0], 1), round(window[1], 1)]
    return doc


def features(music, voice=None, fps=24, out="audio.json", scale="track"):
    """Decode the music (and an optional voice stem) with ffmpeg and write the features JSON; returns the
    number of frames."""
    doc = analyse(_decode(music), fps, scale, _decode(voice) if voice else None)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    return doc["frames"]
