"""A song as a construct: a tower of sound, each moment of the track a ring whose radius at each angle is
how loud that band of frequencies is, rising with time. Python standard library + ffmpeg.

    construct song track.mp3 --out scene.json [--rings 160] [--title "Title"]

The track is decoded to 16 kHz mono (ffmpeg) and cut into `rings` equal slices; each slice's spectrum is
the mean of a few Hann-windowed 2048-point FFTs in it, gathered into 24 bands spaced evenly in pitch from
60 Hz to 7 kHz. Each band is mapped to the track's own range (its 5th to 97th percentile over the
slices, at least 12 dB), so a ring shows where that moment is loud or quiet for this track, not which
band is loudest in general. Around a ring the bands run from the lowest at the front to the highest at
the back and mirror on the other side, so each ring is closed and symmetric; further from the axis is
louder. Height is time: the first slice on the floor, the last at the top. Meridians join the rings at
each angle, a time axis stands beside them with a mark each minute, and the rings where the track
changes section (`construct audio`) are drawn again in the accent.

The scene carries the track's name, SHA-256 and length, and its features for film mode, so its page
builds in time with the track and its replay bar plays it (the track beside the page). Everything drawn
comes from the analysis, under a data lock (source `track`). It is line art: the 3D export makes the
lines tubes, for Blender.
"""

import cmath
import hashlib
import json
import math
from pathlib import Path

from . import film_audio, netlogo, product

RATE = film_audio.RATE
N_FFT = 2048
BANDS = 24
LOW_HZ, HIGH_HZ = 60.0, 7000.0
POINTS = 64            # around each ring
HEIGHT = 10.0          # metres, the first slice to the last
R0, RISE = 0.8, 2.8    # a ring's radius in silence, and how much further the loudest band reaches
FPS = 30               # the features for the page


class SongError(ValueError):
    pass


def _fft(x):
    """An iterative radix-2 FFT of a list of complex numbers (its length a power of two)."""
    n = len(x)
    j = 0
    a = list(x)
    for i in range(1, n):   # bit reversal
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        w = cmath.exp(-2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            wk = 1
            for k in range(start, start + half):
                u, v = a[k], a[k + half] * wk
                a[k], a[k + half] = u + v, u - v
                wk *= w
        size *= 2
    return a


def band_edges(bands=BANDS):
    """FFT bin ranges for `bands` bands spaced evenly in pitch from LOW_HZ to HIGH_HZ."""
    hz = [LOW_HZ * (HIGH_HZ / LOW_HZ) ** (i / bands) for i in range(bands + 1)]
    bins = [max(1, int(round(f * N_FFT / RATE))) for f in hz]
    return [(bins[i], max(bins[i] + 1, bins[i + 1])) for i in range(bands)]


def spectra(samples, rings, per=4):
    """Per slice: the level of each band in dB (the mean power of a few windows in the slice)."""
    n = len(samples)
    if n < N_FFT * 2:
        raise SongError("the track is too short to draw (under a quarter of a second)")
    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / (N_FFT - 1)) for i in range(N_FFT)]
    edges = band_edges()
    out = []
    for r in range(rings):
        a, b = int(n * r / rings), int(n * (r + 1) / rings)
        power = [0.0] * BANDS
        starts = [a + (b - a - N_FFT) * k // max(1, per - 1) for k in range(per)] if b - a > N_FFT else [max(0, a)]
        for s in starts:
            s = max(0, min(n - N_FFT, s))
            spec = _fft([samples[s + i] * hann[i] / 32768.0 for i in range(N_FFT)])
            for k, (lo, hi) in enumerate(edges):
                power[k] += sum(abs(spec[i]) ** 2 for i in range(lo, hi)) / (hi - lo)
        out.append([10 * math.log10(p / len(starts) + 1e-12) for p in power])
    return out


TILT_DB = 4.5          # per octave up, so a typical mix's bands sit level (music falls about this much)


def normalised(levels, smooth=1):
    """The levels tilted by +4.5 dB an octave, each slice averaged with `smooth` on each side and each band
    with its neighbours (1-2-1), then mapped to the track's own range (its 5th to 98th percentile over every
    band and slice, at least 18 dB): a ring's shape is the moment's balance of frequencies, and a loud moment
    is a big ring."""
    octaves = math.log2(HIGH_HZ / LOW_HZ) / BANDS   # each band's width
    tilted = [[db + TILT_DB * k * octaves for k, db in enumerate(row)] for row in levels]
    n = len(tilted)
    avg = [[sum(tilted[j][k] for j in range(max(0, r - smooth), min(n, r + smooth + 1))) /
            (min(n, r + smooth + 1) - max(0, r - smooth)) for k in range(BANDS)] for r in range(n)]
    avg = [[(row[max(0, k - 1)] + 2 * row[k] + row[min(BANDS - 1, k + 1)]) / 4 for k in range(BANDS)] for row in avg]
    flat = sorted(v for row in avg for v in row)
    lo, hi = flat[int(0.05 * (len(flat) - 1))], flat[int(0.98 * (len(flat) - 1))]
    lo = min(lo, hi - 18.0)
    return [[max(0.0, min(1.0, (v - lo) / (hi - lo))) ** 1.4 for v in row] for row in avg]


def _ring(level, y):
    """One ring: POINTS points around the axis at height y, the bands from the front (lowest) to the back
    (highest) and mirrored, each a Catmull-Rom curve through the band values, closed."""
    def at(u):   # u in [0, 1]: the band position, smoothly between bands
        p = u * (BANDS - 1)
        i = int(min(BANDS - 2, math.floor(p)))
        t = p - i
        g = lambda k: level[max(0, min(BANDS - 1, k))]
        p0, p1, p2, p3 = g(i - 1), g(i), g(i + 1), g(i + 2)
        v = 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
        return max(0.0, min(1.0, v))
    pts = []
    for j in range(POINTS):
        th = 2 * math.pi * j / POINTS
        u = th / math.pi if th <= math.pi else (2 * math.pi - th) / math.pi
        r = R0 + RISE * at(u)
        pts.append([round(r * math.sin(th), 4), round(y, 4), round(r * math.cos(th), 4)])
    return pts + [pts[0]]


def _part(pid, label, role, paths, tone=None, weight=None, alpha=None):
    p = {"id": pid, "label": label, "role": role, "shape": {"type": "paths", "paths": paths}, "certainty": "verified",
         "stage": 0, "source": "track"}
    look = {k: v for k, v in (("tone", tone), ("weight", weight), ("alpha", alpha)) if v is not None}
    if look:
        p["look"] = look
    return p


def _by_loudness(ring_paths, levels):
    """The rings in three parts by how loud each moment is (its mean level): the quietest third faint, the
    loudest third bright, so the loud passages glow and the quiet ones recede."""
    loud = [sum(row) / len(row) for row in levels]
    order = sorted(range(len(loud)), key=lambda r: loud[r])
    third = max(1, len(order) // 3)
    groups = [sorted(order[:third]), sorted(order[third:-third] if len(order) > 2 * third else []), sorted(order[-third:])]
    looks = [("rings-quiet", "The quietest third of the moments", "detail", dict(tone="dust", weight=0.6, alpha=0.5)),
             ("rings", "Each ring a moment of the track: further out, louder", "identity", dict(weight=0.8)),
             ("rings-loud", "The loudest third of the moments", "identity", dict(tone="bright", weight=1.0))]
    return [_part(pid, label, role, [ring_paths[r] for r in g], **look)
            for (pid, label, role, look), g in zip(looks, groups) if g]


def _clock(seconds):
    s = int(round(seconds))
    return "%d:%02d" % divmod(s, 60) if s >= 60 else "%d s" % s


def scene_from_track(path, title=None, rings=56, solid=False):
    """A construct-scene v2 of the track (see the module docstring)."""
    path = Path(path)
    if not 16 <= rings <= 240:
        raise SongError("rings: 16 to 240 (each ring is 64 lines, and a construct holds 24,000)")
    if solid and rings > 180:
        raise SongError("--solid takes at most 180 rings (each adds 128 triangles; a construct holds 24,000)")
    samples = film_audio._decode(path)
    seconds = len(samples) / RATE
    levels = normalised(spectra(samples, rings))
    feats = film_audio.analyse(samples, FPS)
    name = path.name
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    title = title or path.stem

    ys = [HEIGHT * (r + 0.5) / rings for r in range(rings)]
    ring_paths = [_ring(levels[r], ys[r]) for r in range(rings)]
    meridians = [[ring_paths[r][j] for r in range(rings)] for j in range(0, POINTS, 8)]
    reach = R0 + RISE + 0.5
    axis = [[[0, 0, -reach], [0, HEIGHT, -reach]]]
    for m in range(1, int(seconds // 60) + 1):
        y = HEIGHT * m * 60 / seconds
        axis.append([[-0.25, y, -reach], [0.25, y, -reach]])
    floor = [[[round(reach * math.sin(2 * math.pi * j / 48), 4), 0, round(reach * math.cos(2 * math.pi * j / 48), 4)]
              for j in range(49)]]
    sections = [s for s in feats.get("sections", []) if 0 < s["t"] < seconds]
    section_rings = [ring_paths[min(rings - 1, int(s["t"] / seconds * rings))] for s in sections]

    parts = [_part("floor", "The floor: the start of the track", "ground", floor, alpha=0.5, weight=0.6),
             _part("time-axis", "Time, 0 to %s, a mark each minute" % _clock(seconds), "ground", axis),
             *_by_loudness(ring_paths, levels),
             _part("meridians", "The same band through time", "detail", meridians, tone="dust", weight=0.4, alpha=0.35)]
    if section_rings:
        parts.append(_part("sections", "Where the track changes section", "data", section_rings, tone="accent", weight=1.4))
    if solid:   # the tower as a closed body, through every ring, capped: for Blender, or to print
        body = _part("body", "The tower as a solid, through every ring", "mass", [], alpha=0.25, weight=0.5)
        body["shape"] = {"type": "rings", "rings": [r[:-1] for r in ring_paths], "caps": True}
        parts.insert(2, body)
    for p in parts:   # each ring hangs at its own moment, above the floor
        if p["id"] in ("rings", "rings-quiet", "rings-loud", "meridians", "sections", "body"):
            p["floating"] = True
    how = ["Height is time: the track starts on the floor and ends at the top, %s in all." % _clock(seconds),
           "Each ring is one moment (%.1f s): around it, the frequencies, the lowest at the front and the highest "
           "at the back, mirrored; further from the middle is louder, for this track." % (seconds / rings),
           "A ring that swells all round is a loud moment; one that bulges at the front, bass; at the back, highs.",
           "The accent rings mark where the track changes section.",
           "Press play to hear the track as the tower builds."]
    facts = [{"key": "track", "value": name, "certainty": "verified", "source": "track"},
             {"key": "sha256", "value": sha, "certainty": "verified", "source": "track"},
             {"key": "seconds", "value": round(seconds, 2), "certainty": "verified", "source": "track"},
             {"key": "view", "value": "song", "certainty": "user_supplied", "source": "request"},
             {"key": "coordinates", "value": "Y is up. Height is time, %g m from the start to the end; a ring's radius "
                                             "is %g m in silence and up to %g m where a band is at its loudest."
                                             % (HEIGHT, R0, R0 + RISE), "certainty": "user_supplied", "source": "request"},
             {"key": "analysis", "value": "%d slices of %.2f s; per slice the mean of up to 4 Hann-windowed %d-point FFTs "
                                          "at %d Hz, in %d bands from %d Hz to %d Hz spaced evenly in pitch, tilted +4.5 dB "
                                          "an octave, averaged with each neighbouring slice and band, mapped to the track's own "
                                          "5th-98th percentile (at least 18 dB) and raised to the power 1.4"
                                          % (rings, seconds / rings, N_FFT, RATE, BANDS, LOW_HZ, HIGH_HZ),
              "certainty": "verified", "source": "track"}]
    slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-")[:48] or "song"
    annotations = []
    for i, p in enumerate(q for q in parts if q["id"] in ("time-axis", "rings-loud", "sections")):   # each label on a real point
        pts = [v for path in p["shape"]["paths"] for v in path]
        lo = [min(v[k] for v in pts) for k in range(3)]
        hi = [max(v[k] for v in pts) for k in range(3)]
        anchor = [(lo[0] + hi[0]) / 2, hi[1], (lo[2] + hi[2]) / 2]
        d = netlogo.LEGEND_DIRS[i % len(netlogo.LEGEND_DIRS)]
        best = max(pts, key=lambda v: v[0] * d[0] + v[1] * d[1] + v[2] * d[2])
        annotations.append({"id": "legend-" + p["id"], "part": p["id"], "text": p["label"][:80],
                            "offset": [round(best[k] - anchor[k], 3) for k in range(3)]})
    sc = {
        "format": product.SCENE_FORMAT, "version": 2, "id": "song-%s" % slug, "title": title,
        "subject": {"category": "other", "accuracy": "documented", "synthetic": False,
                    "summary": "%s as a tower of sound: each moment a ring whose shape is how loud each band of "
                               "frequencies is, rising with time." % title},
        "units": "m", "seed": 7,
        "sources": [{"id": "request", "kind": "user_request", "title": "A construct of a track", "rights": "user_private"},
                    {"id": "track", "kind": "dataset", "title": "%s, analysed by construct song" % name,
                     "rights": "permitted"}],
        "facts": facts, "parts": parts, "annotations": annotations,
        "presentation": {"framing": {"yaw": 28, "pitch": 32}, "atmosphere": {"haze": 0.6, "grid": False, "projector": False,
                                                                           "motes": 0}, "labels": True},
        "animation": {"assembly": {"style": "build", "seconds": 12.0},
                      "idle": {"life": "calm", "events": ["scan"], "cadence": [8, 14], "strength": 0.4},
                      "camera": {"drift": 4, "breathe": 0.02}},
        "reading": {"how": how, "clock": {"label": "second", "from": 0, "to": round(seconds, 3), "top": HEIGHT, "scale": "linear"},
                    "music": {"track": name, "sha256": sha, "ticks_per_second": 1, "seconds": round(seconds, 2),
                              "audio": {"fps": FPS, **{k: feats[k] for k in ("energy", "high", "kick", "onset")}}}},
    }
    sc["facts"].append({"key": netlogo.LOCK, "value": netlogo.data_lock(sc, "track"), "certainty": "verified",
                        "source": "track", "note": "The data as `construct song` drew it from the track: the rings, the "
                                                   "meridians, the sections, the time axis and the track's facts. The "
                                                   "audit refuses the scene if any of it changes."})
    return sc
