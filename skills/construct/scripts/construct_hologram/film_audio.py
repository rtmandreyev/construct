"""Film mode: per-frame audio features for a construct's long assembly (Python standard library + ffmpeg).

    construct audio track.wav --out audio.json [--voice stem.wav] [--fps 24] [--scale track|fixed]

writes {"format": "construct-audio", "version": 2, "fps", "energy": [...], "high": [...], "onset": [...],
"voice": [...], "sections": [...], ...}, one value per video frame, each 0..1, and the sections:

energy[f]  the music's short-term loudness at frame f, smoothed like a meter (fast up, slow down). By default
           each track is mapped to its own range, its 5th to 95th percentile of loudness, so a loud master
           still moves between quiet and loud; `scale="fixed"` keeps the older fixed -40..-10 dBFS window.
high[f]    brightness and attacks: the level of the first difference of the signal (a simple high-pass),
           mapped to the track's own range the same way and smoothed quickly.
onset[f]   the strongest attack in frame f, 0 for none: a peak in the rise of the level in three bands (low,
           whole, high), at least 0.2 s from the next, relative to the track's own strong attacks.
voice[f]   a voice stem's level (-60..-10 dBFS), or zeros without a stem.
sections   [{"t": seconds, "strength": 0..1}]: where the track changes section, found as peaks in the novelty
           of its smoothed loudness and brightness (how different the next 8 s are from the last 8 s), at
           least 10 s apart (more for a long track); [] when nothing stands out.

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
ONSET_GAP_S = 0.2  # attacks closer than this are one attack: no flicker faster than 5 a second
SECTION_WINDOW_S = 8.0  # sections: how much music each side of a moment is compared


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


def band_levels(samples, hop, sr=RATE):
    """Per hop: the level in dBFS of the low band (below about 250 Hz, a one-pole low-pass), the whole signal,
    and the high band (the first difference)."""
    a = math.exp(-2 * math.pi * 250.0 / sr)
    lp, prev, out = 0.0, 0, []
    for i in range(0, len(samples) - hop + 1, hop):
        el = ef = eh = 0.0
        for x in samples[i:i + hop]:
            lp = a * lp + (1 - a) * x
            d = x - prev
            prev = x
            el += lp * lp
            ef += x * x
            eh += d * d
        out.append((_db(el / hop), _db(ef / hop), _db(eh / hop / 4.0)))
    return out


def onsets(samples, fps, sr=RATE, sub=4):
    """Per video frame, the strongest attack in it (0..1, 0 for none); see the module docstring."""
    hop = max(1, sr // (fps * sub))
    bands = band_levels(samples, hop, sr)
    n = len(bands)
    flux = [0.0] * n
    for h in range(4, n):
        rise = 0.0
        for b in range(3):
            now = bands[h][b]
            if now > SILENT_DB:
                rise += max(0.0, now - sum(bands[k][b] for k in range(h - 4, h)) / 4)
        flux[h] = rise
    pre = [0.0]
    for x in flux:
        pre.append(pre[-1] + x)
    w = max(1, int(0.75 * fps * sub))
    peaks = []
    for h in range(n):
        lo, hi = max(0, h - 3), min(n, h + 4)
        if flux[h] <= 0 or flux[h] < max(flux[lo:hi]):
            continue
        a, b = max(0, h - w), min(n, h + w + 1)
        if flux[h] > 1.4 * (pre[b] - pre[a]) / (b - a) + 1.0:  # well above the music around it
            peaks.append((flux[h], h))
    gap = ONSET_GAP_S * fps * sub
    kept = []
    for f, h in sorted(peaks, reverse=True):
        if all(abs(h - k) >= gap for _, k in kept):
            kept.append((f, h))
    frames = len(samples) // (sr // fps) if fps else 0
    out = [0.0] * frames
    if kept:
        ref = _percentile([f for f, _ in kept], 0.9) or 1.0
        for f, h in kept:
            v = min(1.0, f / ref)
            i = h // sub
            if v >= 0.2 and i < frames:
                out[i] = max(out[i], round(v, 3))
    return out


def sections(loud, high, fps, window_s=SECTION_WINDOW_S):
    """Where the track changes section (see the module docstring), from per-frame loudness and high levels."""
    block = max(1, fps // 2)
    feats = []
    for i in range(0, len(loud) - block + 1, block):
        lo = sum(max(x, SILENT_DB) for x in loud[i:i + block]) / block
        hi = sum(max(x, SILENT_DB) for x in high[i:i + block]) / block
        feats.append((lo, hi, hi - lo))
    nb, w = len(feats), max(2, int(window_s * fps / block))
    duration = len(loud) / fps
    min_len = max(10.0, duration / 24.0)
    if nb < 2 * w + 1:
        return []
    cols = []
    for k in range(3):
        v = [f[k] for f in feats]
        m = sum(v) / nb
        sd = max(1.5, math.sqrt(sum((x - m) ** 2 for x in v) / nb))  # a steady track is not made to look restless
        cols.append([(x - m) / sd for x in v])
    nov = [0.0] * nb
    for b in range(w, nb - w):
        nov[b] = math.sqrt(sum((sum(c[b:b + w]) / w - sum(c[b - w:b]) / w) ** 2 for c in cols))
    inner = nov[w:nb - w]
    mean = sum(inner) / len(inner)
    sd = math.sqrt(sum((x - mean) ** 2 for x in inner) / len(inner))
    floor = max(1.0, mean + 0.5 * sd)
    reach = max(1, int(min_len * fps / block / 2))
    # a true peak inside the range where both windows fit (not the edge of it, where an intro would win)
    cands = [(nov[b], b) for b in range(w + 1, nb - w - 1)
             if nov[b] > floor and nov[b] > nov[b - 1] and nov[b] >= max(nov[max(w, b - reach):b + reach + 1])
             and 6.0 <= b * block / fps <= duration - 6.0]
    kept = []
    for v, b in sorted(cands, reverse=True):
        if all(abs(b - k) * block / fps >= min_len for _, k in kept):
            kept.append((v, b))
    top = max((v for v, _ in kept), default=1.0)
    return [{"t": round(b * block / fps, 2), "strength": round(v / top, 3)} for v, b in sorted(kept, key=lambda x: x[1])]


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
    onset = onsets(samples, fps, sr)[:len(energy)]
    onset += [0.0] * (len(energy) - len(onset))
    doc = {"format": "construct-audio", "version": 2, "fps": fps, "frames": len(energy), "scale": scale,
           "energy": energy, "high": brightness, "onset": onset, "voice": voice, "sections": sections(loud, high, fps)}
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
