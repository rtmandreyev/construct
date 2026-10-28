/* Construct kiosk: a construct as an exhibit, for a museum screen or a classroom wall. An optional extra to the
 * viewer, embedded only in pages built with `construct build --kiosk`; every other page is the stock viewer.
 *
 * The page fills the screen with no help line or legend, a label in the corner (the construct's title and the
 * first sentence of its summary) and a "touch to explore" hint. It loops by itself: once the construct has
 * assembled and settled, it holds for `hold` seconds (default 20) and plays again. A touch or a drag explores
 * it as anywhere else; after `idle` seconds untouched (default 45) the loop takes over again. The first touch
 * asks for full screen and, on a run recorded to music, lets the run play with its track from then on (a
 * browser plays sound only after a touch, unless the kiosk browser is started to allow it). The screen is kept
 * awake where the browser allows it, and the cursor hides when it is still.
 *
 * In a show (`construct kiosk`), it tells the show when it is touched, so the show waits while someone explores.
 *
 * URL parameters: hold, idle (seconds); kiosk=0 turns it off.
 */
(function () {
  "use strict";
  const q = new URLSearchParams(location.search);
  if (q.get("kiosk") === "0") return;
  const num = (k, d) => (q.has(k) && isFinite(parseFloat(q.get(k))) ? Math.max(0, parseFloat(q.get(k))) : d);
  const HOLD = num("hold", 20), IDLE = num("idle", 45);
  const geo = window.HOLOGRAM_GEOMETRY || {};
  const css = `
  body.kiosk .help, body.kiosk .legend { display: none !important; }
  body.kiosk.still, body.kiosk.still * { cursor: none !important; }
  .kiosk-label { position: absolute; left: 4vmin; bottom: 4vmin; max-width: min(46vw, 760px); pointer-events: none;
    font: 400 clamp(13px, 1.5vmin, 20px)/1.45 "IBM Plex Mono", ui-monospace, monospace; color: rgba(241,233,247,0.72); }
  .kiosk-label b { display: block; font: 400 clamp(26px, 4.4vmin, 64px)/1.05 "Instrument Serif", Georgia, serif;
    color: #f1e9f7; margin-bottom: 0.4em; }
  .kiosk-hint { position: absolute; right: 4vmin; bottom: 4vmin; pointer-events: none; letter-spacing: 0.16em;
    font: 500 clamp(11px, 1.2vmin, 15px) "IBM Plex Mono", ui-monospace, monospace; color: #d16bd0; text-transform: uppercase;
    transition: opacity 0.8s; }
  body.kiosk.touched .kiosk-hint { opacity: 0; }`;

  function sentence(s) {
    const m = String(s || "").match(/^.*?[.!?](\s|$)/);
    return (m ? m[0] : String(s || "")).trim();
  }

  function start() {
    const H = window.HOLO;
    if (!H || !H.hologram) return;
    document.head.appendChild(Object.assign(document.createElement("style"), { textContent: css }));
    document.body.classList.add("kiosk");
    const overlay = document.getElementById("overlay") || document.body;
    const label = document.createElement("div");
    label.className = "kiosk-label";
    const b = document.createElement("b");
    b.textContent = geo.title || "";
    label.append(b, sentence((geo.subject || {}).summary));
    const hint = document.createElement("div");
    hint.className = "kiosk-hint";
    hint.textContent = "Touch to explore";
    overlay.append(label, hint);

    let cycle = performance.now(), touched = -1e9, moved = performance.now(), sound = false;
    const replay = () => {
      cycle = performance.now();
      const play = document.querySelector(".rd-bar button");
      if (sound && play && (window.HOLOGRAM_GEOMETRY.reading || {}).music) {   // a run with music: replay it with its track
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "r" }));
        if (play.textContent !== "❚❚") play.click();
      } else {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "r" }));
      }
    };
    const touch = () => {
      touched = moved = performance.now();
      if (window.parent !== window) window.parent.postMessage({ construct: "touch" }, "*");   // a show waits
      document.body.classList.add("touched");
      document.body.classList.remove("still");
      if (!sound) {
        sound = true;   // a touch lets the page play sound from now on
        const el = document.documentElement;
        if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(() => {});
      }
    };
    window.addEventListener("pointerdown", touch, true);
    window.addEventListener("wheel", touch, { passive: true, capture: true });
    window.addEventListener("keydown", (e) => { if (e.isTrusted) touch(); }, true);
    window.addEventListener("pointermove", () => { moved = performance.now(); document.body.classList.remove("still"); }, true);

    setInterval(() => {
      const t = performance.now();
      if (t - moved > 3000) document.body.classList.add("still");
      if (t - touched < IDLE * 1000) return;   // someone is exploring
      document.body.classList.remove("touched");
      const settled = (H.timeline().settled || 0) * 1000;
      const play = document.querySelector(".rd-bar button");
      const playing = play && play.textContent === "❚❚";
      if (!playing && t - cycle > settled + HOLD * 1000) replay();
    }, 1000);

    // keep the screen awake, and again whenever the page comes back
    const awake = () => { if (navigator.wakeLock && document.visibilityState === "visible") navigator.wakeLock.request("screen").catch(() => {}); };
    document.addEventListener("visibilitychange", awake);
    awake();
  }

  const go = () => (window.HOLO && window.HOLO.ready ? window.HOLO.ready.then(start, () => {}) : null);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => setTimeout(go, 0));
  else setTimeout(go, 0);
})();
