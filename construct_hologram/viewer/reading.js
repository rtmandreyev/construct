// Construct reading: for a page whose scene carries a reading (how to read it and, for a run, its clock and
// counts) or asks for its labels. Labels show as their parts are drawn (unless ?labels=0) and stay inside the window;
// "How to read it" is a panel (H); a run gets a replay bar that scrubs it tick by tick with its counts.
// A run's panel also offers its counts as CSV and a citation of the run (model, NetLogo, seed, ticks, the data
// lock), for a spreadsheet or a report. Printed (Cmd/Ctrl+P), the page is a worksheet: the construct as it is
// on screen, how to read it, the counts at that tick, the citation and three questions with room to answer.
// The viewer itself is unchanged: this drives it through window.HOLO, after it starts.
(() => {
  const geo = window.HOLOGRAM_GEOMETRY, reading = geo.reading || {}, q = new URLSearchParams(location.search);
  const quiet = q.get("ui") === "0" || q.has("sheet") || q.get("capture") === "1";   // stills: no controls
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const css = `
  .rd-box { position: absolute; pointer-events: auto; background: rgba(10,4,12,.72); border: 1px solid rgba(255,255,255,.12);
    border-radius: 6px; color: var(--ink); text-shadow: none; }
  .rd-how { right: 20px; top: 38px; width: min(360px, calc(100% - 40px)); font-size: 11px; line-height: 1.45; }
  .rd-how button { all: unset; cursor: pointer; display: flex; justify-content: space-between; width: 100%; box-sizing: border-box;
    padding: 7px 10px; font-size: 10px; letter-spacing: .14em; color: #cbbcd8; }
  .rd-how button:focus-visible, .rd-bar button:focus-visible { outline: 1px solid var(--accent); }
  .rd-how ol { margin: 0; padding: 0 12px 9px 28px; } .rd-how li { margin-top: 4px; }
  .rd-how.closed ol, .rd-how.closed .rd-tools { display: none; }
  .rd-tools { padding: 0 12px 9px 12px; font-size: 10px; letter-spacing: .1em; }
  .rd-tools a { color: #d16bd0; cursor: pointer; text-decoration: none; margin-right: 14px; }
  .rd-tools a:hover { text-decoration: underline; }
  .rd-cite { margin-top: 6px; padding: 6px 8px; border: 1px solid rgba(255,255,255,.12); border-radius: 4px; letter-spacing: 0;
    color: #d9c9e6; user-select: all; white-space: normal; overflow-wrap: anywhere; }
  .rd-bar { right: 20px; bottom: 20px; width: min(440px, calc(100% - 40px)); padding: 8px 10px; display: grid;
    grid-template-columns: auto 1fr; gap: 6px 10px; align-items: center; font-size: 10px; letter-spacing: .08em; }
  .rd-bar button { all: unset; cursor: pointer; width: 22px; height: 22px; display: grid; place-items: center; border-radius: 50%;
    border: 1px solid rgba(255,255,255,.25); font-size: 10px; }
  .rd-bar input { width: 100%; accent-color: var(--accent); margin: 0; }
  .rd-bar .rd-read { grid-column: 1 / -1; color: #d9c9e6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rd-bar .rd-read b { color: var(--ink); font-weight: 600; }
  .rd-sheet { display: none; }
  @media print {
    #stage, .rd-box, .help, .legend { display: none !important; }
    html, body { background: #fff !important; height: auto !important; overflow: visible !important; }
    .rd-sheet { display: block; color: #111; font: 11pt/1.45 Georgia, "Times New Roman", serif; padding: 0 4mm; }
    .rd-sheet h1 { font-size: 20pt; font-weight: normal; margin: 0 0 4mm; }
    .rd-sheet h2 { font: 600 8.5pt/1 "IBM Plex Mono", ui-monospace, monospace; letter-spacing: .12em; text-transform: uppercase;
      margin: 6mm 0 2mm; color: #555; }
    .rd-sheet img { display: block; width: 100%; max-height: 92mm; object-fit: contain; background: #050205; border-radius: 2mm; }
    .rd-sheet .rd-now { font: 9pt/1.4 "IBM Plex Mono", ui-monospace, monospace; color: #333; margin: 2mm 0 0; }
    .rd-sheet ol { margin: 0; padding-left: 5mm; } .rd-sheet li { margin: 1mm 0; }
    .rd-sheet .rd-small { font-size: 8.5pt; color: #555; overflow-wrap: anywhere; }
    .rd-sheet .rd-q { margin: 4mm 0 1mm; page-break-inside: avoid; }
    .rd-sheet .rd-lines { height: 15mm; background: repeating-linear-gradient(transparent 0, transparent 7mm, #bbb 7mm, #bbb 7.3mm); }
  }
  @media (max-width: 700px) { .rd-bar { left: 16px; right: 16px; width: auto; bottom: 96px; } .rd-how { right: 16px; top: 60px; width: calc(100% - 32px); }
    #overlay .labels .label { white-space: normal; width: max-content; max-width: calc(100vw - 28px); } }`;

  function keepInside(obstacles) {   // after the viewer places its labels, nudge any that leave the window
    const box = document.querySelector("#overlay .labels"), svg = document.querySelector("#overlay svg.leaders");
    if (!box || !svg) return;
    const fix = () => {
      const tags = box.children, lines = svg.querySelectorAll("polyline"), W = window.innerWidth, Hh = window.innerHeight, M = 10;
      const blocks = obstacles().map((o) => o.getBoundingClientRect()).filter((r) => r.width);
      for (let i = 0; i < tags.length; i++) {
        const t = tags[i];
        let r = t.getBoundingClientRect(), dx = 0, dy = 0;
        if (r.right > W - M) dx = W - M - r.right; else if (r.left < M) dx = M - r.left;
        if (r.top < M) dy = M - r.top; else if (r.bottom > Hh - M) dy = Hh - M - r.bottom;
        for (const b of blocks) {   // off the panel and the replay bar
          const L = r.left + dx, R = r.right + dx, T = r.top + dy, B = r.bottom + dy;
          if (L < b.right && R > b.left && T < b.bottom && B > b.top) dy += (b.top > Hh / 2 ? b.top - B - 6 : b.bottom - T + 6);
        }
        const clear = (d) => {   // this label moved by d stays in the window, off the panel, the bar and the others
          const L = r.left + dx, R = r.right + dx, T = r.top + d, B = r.bottom + d;
          if (T < M || B > Hh - M) return false;
          const hits = (o) => L < o.right && R > o.left && T < o.bottom && B > o.top;
          return !blocks.some(hits) && ![...tags].slice(0, i).some((x) => hits(x.getBoundingClientRect()));
        };
        if (!clear(dy)) {   // the nearest place, up or down, where it is clear
          for (let step = 6; step < Hh; step += 6) {
            if (clear(dy - step)) { dy -= step; break; }
            if (clear(dy + step)) { dy += step; break; }
          }
        }
        if (!dx && !dy) continue;
        t.style.left = (parseFloat(t.style.left) + dx) + "px"; t.style.top = (parseFloat(t.style.top) + dy) + "px";
        const ln = lines[i];
        if (ln) { const p = ln.getAttribute("points").split(" "), e = p[1].split(",").map(Number); p[1] = (e[0] + dx) + "," + (e[1] + dy); ln.setAttribute("points", p.join(" ")); }
      }
    };
    new MutationObserver(fix).observe(box, { childList: true });
  }

  // a run's counts as CSV (as the replay shows them) and a citation of the run, from its own facts
  function runTools() {
    const c = reading.clock, series = reading.series || [];
    if (!c) return null;
    const facts = {};
    ((geo.provenance || {}).facts || []).forEach((f) => { facts[f.key] = f.value; });
    if (!facts.model) return null;
    const box = el("div", "rd-tools");
    if (series.length) {
      const csv = el("a", null, "DATA (CSV)");
      csv.addEventListener("click", () => {
        const ticks = [...new Set(series.flatMap((s) => s.values.map((v) => v[0])))].sort((a, b) => a - b);
        const cell = (x) => (/[",\n]/.test(String(x)) ? '"' + String(x).replace(/"/g, '""') + '"' : String(x));
        const rows = [[c.label].concat(series.map((s) => s.name)).map(cell).join(",")];
        ticks.forEach((t) => rows.push([t].concat(series.map((s) => { const v = s.values.find((p) => p[0] === t); return v ? v[1] : ""; })).join(",")));
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([rows.join("\n") + "\n"], { type: "text/csv" }));
        a.download = (geo.id || "run") + "-counts.csv";
        document.body.appendChild(a); a.click(); a.remove();
      });
      box.append(csv);
    }
    const cite = el("a", null, "CITE THIS RUN"), text = el("div", "rd-cite");
    text.textContent = facts.model + " (NetLogo " + (facts.netlogo || "?") + "), one run" +
      (facts.seed != null ? ", random-seed " + facts.seed : "") + ", " + facts.ticks + " " + c.label + "s" +
      ". Drawn with " + (geo.generator || "Construct").replace(/^construct/, "Construct") +
      " (github.com/rtmandreyev/construct)" + (facts.data_lock ? "; data lock " + facts.data_lock : "") + ".";
    text.hidden = true;
    cite.addEventListener("click", () => {
      text.hidden = !text.hidden;
      if (!text.hidden && navigator.clipboard) navigator.clipboard.writeText(text.textContent).catch(() => {});
    });
    box.append(cite, text);
    return box;
  }

  function howPanel(overlay) {
    const how = reading.how || [];
    if (!how.length) return null;
    const box = el("div", "rd-box rd-how"), head = el("button");
    head.append(el("span", null, "HOW TO READ IT"), el("span", null, "H"));
    head.setAttribute("aria-expanded", "true");
    const list = el("ol");
    how.forEach((line) => list.appendChild(el("li", null, line)));
    box.append(head, list);
    const tools = runTools();
    if (tools) box.append(tools);
    const set = (open) => { box.classList.toggle("closed", !open); head.setAttribute("aria-expanded", String(open)); };
    set(window.innerWidth > 700);
    head.addEventListener("click", () => set(box.classList.contains("closed")));
    window.addEventListener("keydown", (e) => { if ((e.key === "h" || e.key === "H") && !e.metaKey && !e.ctrlKey) set(box.classList.contains("closed")); });
    overlay.appendChild(box);
    return box;
  }

  function replayBar(overlay, H) {
    const c = reading.clock;
    if (!c || !c.phase) return null;
    const holo = H.hologram, series = reading.series || [], span = c.to - c.from;
    const times = () => holo.assemblyTimes();
    const yOf = (tick) => { const f = Math.max(0, Math.min(1, (tick - c.from) / span)); return c.top * (c.scale === "sqrt" ? Math.sqrt(f) : f); };
    const tOf = (tick) => { const a = times();
      const ph = c.phase[0] * yOf(tick) + c.phase[1]; return a.ghost + a.collapse + Math.max(0, Math.min(1, ph)) * a.build; };
    const tickOf = (t) => {   // the inverse, for the viewer's own replay
      const a = times(); if (!a.build) return c.to;
      const ph = Math.max(0, Math.min(1, (t - a.ghost - a.collapse) / a.build)), f = Math.max(0, Math.min(1, ((ph - c.phase[1]) / c.phase[0]) / c.top));
      return c.from + span * (c.scale === "sqrt" ? f * f : f);
    };
    const at = (s, tick) => { let lo = 0, hi = s.values.length - 1;   // the last sample at or before the tick
      if (tick < s.values[0][0]) return null;
      while (lo < hi) { const m = (lo + hi + 1) >> 1; if (s.values[m][0] <= tick) lo = m; else hi = m - 1; }
      return s.values[lo][1]; };
    const fmt = (v) => v == null ? "–" : Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 10 ? 2 : 1);

    const bar = el("div", "rd-box rd-bar"), play = el("button", null, "▶"), range = el("input"), read = el("div", "rd-read");
    play.setAttribute("aria-label", "Play the run");
    Object.assign(range, { type: "range", min: c.from, max: c.to, step: "any", value: c.to });
    range.setAttribute("aria-label", "The run's " + c.label);
    bar.append(play, range, read);
    overlay.appendChild(bar);

    let mode = "viewer", tick = c.to, t0 = performance.now(), paused = false, pausedAt = 0, last = 0;
    let shown = "";
    const show = () => {
      const key = mode + Math.round(tick * 100);
      if (key === shown) return;   // the DOM only when the tick moves
      shown = key;
      range.value = tick;
      read.replaceChildren(el("b", null, c.label.toUpperCase() + " " + Math.round(tick) + " / " + Math.round(c.to)));
      series.forEach((s) => read.append(" · " + s.name + " " + fmt(at(s, tick))));
    };
    const take = (k) => {   // the bar holds the time now: the viewer shows the run up to this tick
      tick = Math.max(c.from, Math.min(c.to, k));
      if (holo.opt.reduced) H.renderAt(tOf(tick), { reduced: false }); else H.renderAt(tOf(tick));
      show();
    };
    range.addEventListener("input", () => { mode = "scrub"; play.textContent = "▶"; take(parseFloat(range.value)); });
    play.addEventListener("click", () => {
      if (mode === "play") { mode = "scrub"; play.textContent = "▶"; return; }
      if (tick >= c.to - 1e-9) take(c.from);
      mode = "play"; play.textContent = "❚❚"; last = performance.now();
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "r" || e.key === "R") { mode = "viewer"; t0 = performance.now(); paused = false; play.textContent = "▶"; }   // the viewer's replay
      else if (e.key === " " && mode === "viewer") { if (paused) { t0 += performance.now() - pausedAt; paused = false; } else { pausedAt = performance.now(); paused = true; } }
    });
    const loop = (now) => {
      if (mode === "viewer" && !paused) { tick = tickOf((now - t0) / 1000); show(); }
      else if (mode === "play") {
        const k = tick + span * (now - last) / 1000 / Math.max(6, times().build || 12);
        last = now;
        take(k);
        if (tick >= c.to) { mode = "scrub"; play.textContent = "▶"; }
      }
      requestAnimationFrame(loop);
    };
    show();
    requestAnimationFrame(loop);
    return bar;
  }

  // printed, the page is a worksheet, filled the moment it is printed: the construct as it is on screen
  function worksheet() {
    const sheet = el("div", "rd-sheet");
    document.body.appendChild(sheet);
    const fill = () => {
      sheet.replaceChildren(el("h1", null, geo.title || ""));
      const canvas = document.getElementById("holo");
      try { const img = new Image(); img.src = canvas.toDataURL("image/png"); img.alt = geo.title || ""; sheet.append(img); } catch (e) { /* no picture */ }
      const now = document.querySelector(".rd-bar .rd-read");
      if (now) sheet.append(el("p", "rd-now", now.textContent));
      const list = el("ol");
      (reading.how || []).forEach((line) => list.append(el("li", null, line)));
      sheet.append(el("h2", null, "How to read it"), list);
      const cite = document.querySelector(".rd-cite");
      if (cite) sheet.append(el("p", "rd-small", cite.textContent));
      sheet.append(el("h2", null, "Questions"));
      ["What do you notice first in its shape?", "Where does it change fastest, and what in the model makes it do that?",
       "What would you change in the model to give it another shape? Predict it, then try it."].forEach((qn) => {
        sheet.append(el("p", "rd-q", qn), el("div", "rd-lines"));
      });
    };
    window.addEventListener("beforeprint", fill);
    window.HOLO_WORKSHEET = fill;   // for a printing tool that fires no beforeprint
  }

  const on = () => {
    const H = window.HOLO;
    if (!H || !H.hologram) return;
    if (geo.presentation && geo.presentation.labels && !q.has("labels")) H.hologram.opt.labels = true;
    const overlay = document.getElementById("overlay"), parts = [];
    if (!quiet && overlay) {
      document.head.appendChild(el("style", null, css));
      const how = howPanel(overlay), bar = replayBar(overlay, H);
      if (how) parts.push(how);
      if (bar) parts.push(bar);
      if (how) worksheet();
    }
    keepInside(() => parts);
    window.dispatchEvent(new Event("resize"));   // the viewer redraws, labels and all
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", on); else on();
})();
