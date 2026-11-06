/* Construct film mode: a construct that assembles across a track of music. An optional extra to the viewer
 * (hologram.js), embedded only in pages built for film (`construct build --film`, or `construct video` with a
 * film option); a page built without it is the stock viewer, byte for byte.
 *
 * URL parameters: assembly (seconds: the assembly lasts this long, e.g. a whole track), audio (a features file
 * written by `construct audio`, fetched beside the page), reactivity (0..2, default 1: how strongly the music
 * shows; 0 is an even build with no light or accents), camera=steady (no tour; the view drifts and breathes).
 * Without any of them this script changes nothing.
 *
 * With audio, at reactivity r:
 *   pace      each frame's speed is exp(4r·(rank − 0.5)), rank being the frame's loudness among the build's
 *             frames (0 the quietest, 1 the loudest), slowed further where the music is near silence (energy
 *             below 0.15: down to 0.15^r), smoothed over 2 s: quiet passages nearly pause, loud ones surge, and
 *             the whole is normalised so the build still ends exactly on time
 *   sections  at each section boundary the features file names, a new stage of the scene begins
 *   light     the hologram's light scales by 1 + 0.4r·(2·energy − 1): 0.6..1.4 at r = 1
 *   accents   each strong onset (and each section boundary) flares the build front and what was just drawn,
 *             and pulses the glow of what is built; it decays in about 0.2 s (gone by 0.5 s). Onsets are at
 *             least 0.2 s apart; only those above 0.75 − 0.2r of the track's strong ones flare, the
 *             strongest most, so a busy track still reads as accents rather than flicker
 *   voice     while a voice stem is present the hologram shimmers
 * It fetches the one features file named by ?audio and nothing else.
 */
(function () {
  "use strict";
  const HV = window.HologramViewer;
  if (!HV) return;
  const q = new URLSearchParams(location.search);
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const FILM = {
    assembly: q.has("assembly") ? clamp(parseFloat(q.get("assembly")) || 0, 0.2, 3600) : null,
    audio: q.get("audio"),
    steady: q.get("camera") === "steady",
    reactivity: q.has("reactivity") ? clamp(parseFloat(q.get("reactivity")) || 0, 0, 2) : 1,
  };
  if (!FILM.assembly && !FILM.audio && !FILM.steady) return;  // no film option: the stock viewer, untouched
  const P = HV.Hologram.prototype;
  const SCAN = 1, SHIMMER = 4;  // the viewer's event codes
  const SMOOTH_S = 2.0, ACCENT_S = 0.2, PACE = 4;
  window.HOLO_FILM = FILM;

  // ------------------------------------------------------------------ the assembly's length
  const ownTimes = P.assemblyTimes;
  P.assemblyTimes = function (authored) {
    // authored: the scene's own assembly, ignoring ?assembly=
    const at = ownTimes.call(this);
    if (authored || !FILM.assembly || !at.build) return at;
    const build = Math.max(0.2, FILM.assembly);
    return Object.assign({}, at, { build, end: at.ghost + at.collapse + build + at.settle });
  };

  // ------------------------------------------------------------------ the music
  P.audioAt = function (t) {
    const a = this.audio, i = clamp(Math.round(t * a.fps), 0, a.energy.length - 1);
    return { energy: a.energy[i] || 0, high: (a.high && a.high[i]) || 0, voice: (a.voice && a.voice[i]) || 0 };
  };
  P.filmCurve = function () {
    // the build's progress per frame of the build (0 at its start, 1 at its end), paced and staged by the music
    const at = this.assemblyTimes(), a = this.audio, r = FILM.reactivity, key = at.build + "/" + r;
    if (this._film && this._film.key === key) return this._film;
    const fps = a.fps, t0 = at.ghost + at.collapse, n = Math.max(2, Math.ceil(at.build * fps) + 1), i0 = Math.round(t0 * fps);
    const E = new Float64Array(n);
    for (let i = 0; i < n; i++) E[i] = a.energy[clamp(i0 + i, 0, a.energy.length - 1)] || 0;
    // rank: where each frame's loudness stands among the build's frames (ties share their mean rank)
    const ord = Array.from({ length: n }, (_, i) => i).sort((x, y) => E[x] - E[y]), rank = new Float64Array(n);
    for (let i = 0; i < n;) {
      let j = i; while (j + 1 < n && E[ord[j + 1]] === E[ord[i]]) j++;
      for (let k = i; k <= j; k++) rank[ord[k]] = (i + j) / 2 / (n - 1);
      i = j + 1;
    }
    // speed: exp(4r(rank - 0.5)), slower still near silence, then smoothed so the pace swells and settles rather than flickers
    const raw = new Float64Array(n), w = Math.max(1, Math.round(SMOOTH_S * fps / 2));
    for (let i = 0; i < n; i++) raw[i] = Math.exp(PACE * r * (rank[i] - 0.5)) * Math.pow(0.15 + 0.85 * clamp(E[i] / 0.15, 0, 1), r);
    const pre = new Float64Array(n + 1);
    for (let i = 0; i < n; i++) pre[i + 1] = pre[i] + raw[i];
    const acc = new Float64Array(n);
    for (let i = 1; i < n; i++) { const lo = Math.max(0, i - w), hi = Math.min(n, i + w + 1); acc[i] = acc[i - 1] + (pre[hi] - pre[lo]) / (hi - lo); }
    // sections: each boundary inside the build starts a new stage; the strongest first if there are more
    // boundaries than stages, and never two on one stage
    const N = (this.geo.stages || []).length, anchors = [[0, 0]];
    if (N > 1 && r > 0 && Array.isArray(a.sections)) {
      const inside = a.sections.map((s) => ({ j: Math.round((s.t - t0) * fps), strength: s.strength || 0 }))
        .filter((s) => s.j > 0.04 * n && s.j < 0.96 * n)
        .sort((x, y) => y.strength - x.strength).slice(0, N - 1).sort((x, y) => x.j - y.j);
      let last = 0;
      for (const s of inside) {
        const stage = clamp(Math.round(acc[s.j] / acc[n - 1] * N), 1, N - 1);
        if (stage <= last) continue;
        anchors.push([s.j, stage / N]); last = stage;
      }
    }
    anchors.push([n - 1, 1]);
    const p = new Float64Array(n);
    for (let k = 0; k + 1 < anchors.length; k++) {
      const [ja, pa] = anchors[k], [jb, pb] = anchors[k + 1], span = acc[jb] - acc[ja] || 1;
      for (let i = ja; i <= jb; i++) p[i] = pa + (pb - pa) * (acc[i] - acc[ja]) / span;
    }
    // accents: each onset (and each section boundary) flares at once and decays over about 0.2 s
    const m = a.energy.length, env = new Float64Array(m), decay = Math.exp(-1 / (ACCENT_S * fps)), hit = new Float64Array(m);
    const floor = clamp(0.75 - 0.2 * r, 0.2, 0.75);
    (a.onset || []).forEach((v, i) => { if (i < m && v > floor) hit[i] = Math.pow((v - floor) / (1 - floor), 1.5); });
    (a.sections || []).forEach((s) => { const i = Math.round(s.t * fps); if (i >= 0 && i < m) hit[i] = 1; });
    for (let i = 0; i < m; i++) env[i] = Math.max(hit[i], i ? env[i - 1] * decay : 0);
    this._film = { key, fps, n, p, env, sections: anchors.slice(1, -1).map(([j, pr]) => ({ t: t0 + j / fps, progress: pr })) };
    return this._film;
  };
  P.filmBuild = function (tb) {
    const c = this.filmCurve();
    return c.p[clamp(Math.round(tb * c.fps), 0, c.n - 1)];
  };
  P.filmBuildTime = function (progress) {
    // the inverse: the first moment (seconds into the build) the build reaches this progress
    const c = this.filmCurve(); let lo = 0, hi = c.n - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (c.p[mid] >= progress) hi = mid; else lo = mid + 1; }
    return Math.min(this.assemblyTimes().build, lo / c.fps);
  };
  P.accentAt = function (t) {
    const c = this.filmCurve(), i = Math.round(t * c.fps);
    return i >= 0 && i < c.env.length ? c.env[i] : 0;
  };
  P.frontHeight = function (k) {
    // where the build front is, as a fraction of the construct's height: a stage builds bottom-up
    if (!this._stageY) {
      const index = {}, ys = {};
      (this.geo.stages || []).forEach((s) => { index[s.stage] = s.index; });
      (this.geo.parts || []).forEach((part) => (part.instances || []).forEach((ins) => {
        const s = index[part.stage], y = ys[s] || [Infinity, -Infinity];
        ys[s] = [Math.min(y[0], ins.min[1]), Math.max(y[1], ins.max[1])];
      }));
      this._stageY = ys;
    }
    const N = Math.max(1, (this.geo.stages || []).length), si = clamp(Math.floor(k * N), 0, N - 1);
    const f = clamp((k * N - si) / 0.82, 0, 1), y = this._stageY[si] || [this.ground, this.top];
    return clamp((y[0] + f * (y[1] - y[0]) - this.ground) / Math.max(this.top - this.ground, 1e-4), 0, 1);
  };

  // ------------------------------------------------------------------ what the music does to each frame
  const ownState = P.state;
  P.state = function (t) {
    const s = ownState.call(this, t), a = this.audio, r = FILM.reactivity;
    if (!a || r <= 0) return s;
    const at = this.assemblyTimes(), t0 = at.ghost + at.collapse, building = at.build > 0 && t >= t0 && t < t0 + at.build;
    if (building) { const k = this.filmBuild(t - t0); s.build = k; s.scan = [k * 1.05, 0.6]; }
    const f = this.audioAt(t), accent = Math.min(1, r) * this.accentAt(t);
    s.globalAlpha *= clamp(1 + 0.4 * r * (2 * f.energy - 1), 0.15, 1.8) * (1 + 0.1 * accent);
    s.stabilise = Math.max(s.stabilise, 0.8 * accent);  // a glow pulse on what is built
    if (building && accent > 0.03) {
      // the front flares: a bright band at the height being drawn, and the haze's scan line with it
      const hy = this.frontHeight(s.build);
      s.event = [SCAN, (hy + 0.12) / 1.25, 0.9 * accent, 3]; s.eventP = [0, 0, 0, 0];
      s.scan = [s.scan[0], 0.6 + 0.8 * accent];
    } else if (s.event[0] === 0 && f.voice > 0.25) {
      s.event = [SHIMMER, (t * 0.35) % 1, (0.35 + 0.6 * f.voice) * Math.min(1, r), 7];
    }
    return s;
  };

  // ------------------------------------------------------------------ the camera
  P.tourStops = function () {
    // the scene's tour is authored in seconds against its own assembly; each stop keeps its place in it.
    // Before the build it stays; during the build it comes when the film's build reaches the same progress,
    // its flight scaled with the build (at most 3x, and 12 s unless the scene's own is longer); after the
    // build it moves by as much as the assembly's end. A flight never runs into the next stop.
    const tour = this.geo.animation.camera.tour || [], at = this.assemblyTimes(), own = this.assemblyTimes(true);
    const start = at.ghost + at.collapse, d = at.end - own.end, paced = this.audio && FILM.reactivity > 0;
    if ((!d && !paced) || !at.build) return tour;
    const ratio = at.build / own.build;
    const out = tour.map((s) => {
      const fly = s.fly || 2.2;
      if (s.at < start) return Object.assign({}, s);
      if (s.at >= start + own.build) return Object.assign({}, s, { at: s.at + d });
      const progress = (s.at - start) / own.build;
      return Object.assign({}, s, { at: start + (paced ? this.filmBuildTime(progress) : progress * at.build),
                                    fly: Math.max(0.2, Math.min(fly * Math.min(ratio, 3), Math.max(fly, 12))) });
    });
    for (let i = 0; i + 1 < out.length; i++) out[i].fly = Math.max(0.05, Math.min(out[i].fly || 2.2, out[i + 1].at - out[i].at));
    return out;
  };
  const ownCamera = P.cameraAt;
  P.cameraAt = function (t, base) {
    // the viewer flies the scene's tour; for the length of this call it flies the film's instead
    // (camera=steady: a stop that never comes, so no tour and no automatic turn to the open view)
    const cam = this.geo.animation.camera, own = cam.tour;
    cam.tour = FILM.steady ? [{ view: "hero", at: Infinity }] : this.tourStops();
    try { return ownCamera.call(this, t, base); } finally { cam.tour = own; }
  };

  // ------------------------------------------------------------------ after the viewer has started
  function start() {
    const holo = window.HOLO && window.HOLO.hologram;
    if (!holo) return;
    holo.schedule = holo.buildSchedule();  // the idle life begins after the film's assembly
    if (FILM.audio) {
      window.HOLO_AUDIO_READY = fetch(FILM.audio).then((res) => res.json())
        .then((a) => { holo.audio = a; holo._film = null; holo.schedule = holo.buildSchedule(); })
        .catch((e) => console.error("audio features:", e));
    }
  }
  if (window.HOLO) start(); else document.addEventListener("DOMContentLoaded", start);
})();
