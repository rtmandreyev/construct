"""Preview build and capture for compiled constructs.

build_html()  — one self-contained HTML file (the viewer, the geometry and any supplied,
                hash-checked artwork) that runs in any WebGL2 browser, offline.
Capture       — a headless Chromium driven over the DevTools protocol with a minimal
                standard-library WebSocket client: fixed frames, review contact sheets
                and video frames. ffmpeg (optional) turns frames into MP4/GIF.

Nothing here fetches from the network. The browser is launched with a throwaway profile,
loads a local file and is closed afterwards.
"""

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWER = HERE / "viewer"
ART_RIGHTS = ("synthetic", "user_private", "permitted")


class CaptureError(Exception):
    pass


# ---------------------------------------------------------------------------- HTML

def _script_json(obj):
    # no "<" at all inside an inline script: scene text can never open or close an element
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")


def embed_assets(geometry, asset_root):
    """Data URIs for artwork whose bytes exist under asset_root and match the declared
    SHA-256. Anything else stays an empty slot; returns (assets, notes)."""
    out, notes = {}, []
    declared = {a["id"]: a for a in geometry.get("provenance", {}).get("assets", [])}
    for art in geometry.get("artwork", []):
        a = declared.get(art["asset_id"])
        if a is None:
            continue
        if asset_root is None:
            notes.append("artwork %s: no asset folder given; the slot stays empty" % a["id"])
            continue
        root = Path(asset_root).resolve()
        path = (root / a["path"]).resolve()
        if root not in path.parents:
            notes.append("artwork %s: path escapes the asset folder; skipped" % a["id"])
            continue
        if not path.is_file():
            notes.append("artwork %s: %s not found; the slot stays empty" % (a["id"], a["path"]))
            continue
        data = path.read_bytes()
        if len(data) > 20 * 1024 * 1024:
            notes.append("artwork %s: larger than 20 MiB; skipped" % a["id"])
            continue
        if hashlib.sha256(data).hexdigest() != a["sha256"]:
            notes.append("artwork %s: bytes do not match the declared sha256; skipped" % a["id"])
            continue
        if a["rights"] not in ART_RIGHTS:
            notes.append("artwork %s: rights %r do not permit display; skipped" % (a["id"], a["rights"]))
            continue
        out[a["id"]] = "data:%s;base64,%s" % (a["media_type"], base64.b64encode(data).decode("ascii"))
    return out, notes


def solid_payload(scene, geometry, phase_of=None):
    """The construct's surfaces for the page's solid view (S): what a modelling program shows, from the same
    solid compile as the 3D export, packed small. Each vertex carries its part's style in `geometry` (so the
    opening, the stages and provenance colours move it as they move the lines), its build phase and a smooth
    normal; glass comes last, drawn see-through. None when the scene has no surfaces. `phase_of` (part id ->
    phase, or a function of a triangle's middle: a part made into several pieces) builds the parts in another
    order (a kit's steps: each piece whole, at once); a part it leaves out is never built."""
    from . import export as export_mod, scene as scene_mod
    solid = scene_mod.compile_scene(scene, solid=True)
    styles, parts = geometry["styles"], geometry["parts"]
    style_of = {}
    for i, st in enumerate(styles):   # a part's first style in the page: the one its lines are drawn with
        style_of.setdefault(int(st[6]), i)
    by_part = {}
    f = solid["fills"]
    for i in range(0, len(f), 15):
        pi = int(solid["styles"][int(f[i + 3])][6])
        if pi in style_of:
            by_part.setdefault(pi, []).append(tuple((f[i + 5 * j], f[i + 5 * j + 1], f[i + 5 * j + 2], f[i + 5 * j + 4])
                                                     for j in range(3)))
    if not by_part:
        return None
    # glass by its name (a window, a windscreen): `look.fill` "glass" is how the light draws a part, not its material
    glassy = {pi for pi in by_part if export_mod.is_glass_name(parts[pi]["id"])}
    corners = [c for tris in by_part.values() for t in tris for c in t]
    lo = [min(c[a] for c in corners) for a in range(3)]
    hi = [max(c[a] for c in corners) for a in range(3)]
    span = [max(hi[a] - lo[a], 1e-9) for a in range(3)]
    index, verts, opaque, clear = {}, [], [], []
    for pi in sorted(by_part, key=lambda p: p in glassy):
        tris = by_part[pi]
        normals = export_mod.smooth_normals([tuple(c[:3] for c in t) for t in tris])
        out = clear if pi in glassy else opaque
        own = phase_of.get(parts[pi]["id"], 1.0) if phase_of is not None else None
        for ti, t in enumerate(tris):
            ph = own(tuple(sum(c[a] for c in t) / 3 for a in range(3))) if callable(own) else own
            for j, c in enumerate(t):
                n = normals[3 * ti + j]
                key = (tuple(int(round((c[a] - lo[a]) / span[a] * 65535)) for a in range(3)),
                       tuple(max(-127, min(127, int(round(n[a] * 127)))) for a in range(3)),
                       style_of[pi], int(round(max(0.0, min(1.0, c[3] if ph is None else ph)) * 65535)))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(key)
                out.append(index[key])
    pos = struct.pack("<%dH" % (3 * len(verts)), *(q for v in verts for q in v[0]))
    nrm = struct.pack("<%db" % (4 * len(verts)), *(q for v in verts for q in v[1] + (0,)))
    sty = struct.pack("<%dH" % len(verts), *(v[2] for v in verts))
    pha = struct.pack("<%dH" % len(verts), *(v[3] for v in verts))
    wide = len(verts) > 65535
    idx = struct.pack("<%d%s" % (len(opaque) + len(clear), "I" if wide else "H"), *(opaque + clear))
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"lo": [round(x, 6) for x in lo], "hi": [round(x, 6) for x in hi], "vertices": len(verts),
            "opaque": len(opaque), "clear": len(clear), "wide": wide,
            "pos": b64(pos), "nrm": b64(nrm), "sty": b64(sty), "pha": b64(pha), "idx": b64(idx)}


def build_html(geometry, asset_root=None, film=False, solid=None, extra=None):
    """The construct page. `film` also embeds film mode (viewer/film.js) after the viewer; without it the page
    is the stock viewer, unchanged. `solid` (solid_payload) gives the page its solid view (S)."""
    template = (VIEWER / "template.html").read_text(encoding="utf-8")
    viewer = (VIEWER / "hologram.js").read_text(encoding="utf-8")
    assets, notes = embed_assets(geometry, asset_root)
    title = geometry["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    # one pass over the template: what is put in is never searched again (a title that says "__VIEWER__" stays text)
    import re
    fill = {"__TITLE__": title, "__GEOMETRY__": _script_json(geometry), "__ASSETS__": _script_json(assets),
            "__SOLID__": _script_json(solid), "__VIEWER__": viewer.replace("</script", "<\\/script")}
    html = re.sub("__(?:TITLE|GEOMETRY|ASSETS|SOLID|VIEWER)__", lambda m: fill[m.group(0)], template)
    if film:  # a script of its own, right after the viewer's, so it runs before the viewer starts
        code = (VIEWER / "film.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        mark = "\n</script>\n<script>\n  // the improvement rounds"
        assert html.count(mark) == 1
        html = html.replace(mark, "\n</script>\n<script>\n" + code + "\n</script>\n<script>\n  // the improvement rounds")
    if extra:   # a page of its own made from the viewer (a kit's step-by-step build): its script, after the viewer's
        mark = "\n</script>\n<script>\n  // the improvement rounds"
        assert html.count(mark) == 1
        html = html.replace(mark, "\n</script>\n<script>\n" + extra.replace("</script", "<\\/script")
                            + "\n</script>\n<script>\n  // the improvement rounds")
    if geometry.get("reading") or geometry.get("presentation", {}).get("labels"):
        # how to read it, the run's replay and labels as their parts are drawn (viewer/reading.js): only for a scene
        # that asks; every other page is the stock viewer, unchanged
        code = (VIEWER / "reading.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        mark = "\n</script>\n<script>\n  // the improvement rounds"
        assert html.count(mark) == 1
        html = html.replace(mark, "\n</script>\n<script>\n" + code + "\n</script>\n<script>\n  // the improvement rounds")
    return html, notes


# ---------------------------------------------------------------------------- browser

def find_browser():
    env = os.environ.get("HOLOGRAM_CHROME")
    if env and Path(env).exists():
        return env
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for cache in (Path.home() / "Library/Caches/ms-playwright", Path.home() / ".cache/ms-playwright"):
        for exe in sorted(cache.glob("chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"), reverse=True) + \
                   sorted(cache.glob("chromium-*/chrome-linux*/chrome"), reverse=True):
            return str(exe)
    return None


class _WebSocket:
    """Just enough RFC 6455 for one local DevTools connection (text frames, masking,
    fragmentation, ping/pong)."""

    def __init__(self, url, timeout=60):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (u.path, u.hostname, u.port, key))
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CaptureError("DevTools closed the connection during the handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise CaptureError("DevTools refused the WebSocket: %r" % head[:120])
        self.buf = head.split(b"\r\n\r\n", 1)[1]

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise CaptureError("DevTools connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        data = text.encode()
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        parts = []
        while True:
            b0, b1 = self._read(2)
            op, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x9:  # ping
                self.sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + b"\0\0\0\0" + payload)
                continue
            if op == 0x8:
                raise CaptureError("DevTools closed the connection")
            parts.append(payload)
            if b0 & 0x80:
                return b"".join(parts).decode()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Browser:
    """A throwaway headless Chromium with one page."""

    def __init__(self, width=1280, height=800, scale=1.0, browser=None, gpu=True):
        exe = browser or find_browser()
        if not exe:
            raise CaptureError("No Chromium-family browser found. Install Chrome/Chromium/Edge or set HOLOGRAM_CHROME. "
                               "The HTML preview itself works in any WebGL2 browser without this.")
        self.profile = tempfile.mkdtemp(prefix="hologram-chrome-")
        args = [exe, "--headless=new", "--remote-debugging-port=0", "--user-data-dir=" + self.profile,
                "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--mute-audio", "--hide-scrollbars",
                "--allow-file-access-from-files", "--enable-webgl", "--ignore-gpu-blocklist",
                "--window-size=%d,%d" % (width, height), "about:blank"]
        if not gpu:  # software WebGL: slower, but works without a GPU (CI, servers)
            args[-2:-2] = ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = Path(self.profile) / "DevToolsActivePort"
        deadline = time.time() + 30
        while not port_file.exists() or not port_file.read_text().strip():
            if time.time() > deadline or self.proc.poll() is not None:
                self.close()
                raise CaptureError("the browser did not start its DevTools endpoint")
            time.sleep(0.05)
        port = int(port_file.read_text().split()[0])
        page = None
        while page is None:   # a busy machine (a render beside it) can take a while to answer: wait, within the deadline
            try:
                targets = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=10).read())
                page = next((t for t in targets if t.get("type") == "page"), None)
            except (OSError, ValueError):
                pass
            if page is None:
                if time.time() > deadline + 60 or self.proc.poll() is not None:
                    self.close()
                    raise CaptureError("the browser started but did not answer on its DevTools endpoint")
                time.sleep(0.5)
        # software WebGL draws a large construct's contact sheet in minutes, not seconds: wait for it
        self.patience = 60 if gpu else 900
        self.ws = _WebSocket(page["webSocketDebuggerUrl"], timeout=self.patience)
        self.next_id = 0
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=False)
        self.size = (width, height)

    def call(self, method, **params):
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CaptureError("%s: %s" % (method, msg["error"].get("message")))
                return msg.get("result", {})

    def evaluate(self, expression, timeout=None):
        timeout = timeout or getattr(self, "patience", 60)
        res = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True,
                        timeout=int(timeout * 1000))
        if res.get("exceptionDetails"):
            detail = res["exceptionDetails"]
            text = detail.get("exception", {}).get("description") or detail.get("text")
            raise CaptureError("page script failed: %s" % text)
        return res.get("result", {}).get("value")

    def open(self, url):
        self.call("Page.navigate", url=url)
        deadline = time.time() + 60
        while time.time() < deadline:
            state = self.evaluate("document.readyState + '|' + (document.body ? (document.body.getAttribute('data-error') || document.body.getAttribute('data-ready') || '') : '')")
            if state and state.startswith("complete"):
                flag = state.split("|", 1)[1]
                if flag == "1":
                    return
                if flag:
                    raise CaptureError("the viewer failed: " + flag)
            time.sleep(0.05)
        raise CaptureError("the viewer did not become ready")

    def shot(self, path):
        self.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"]
        Path(path).write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)


def open_browser(html_probe, width, height, scale, browser=None):
    """A browser whose WebGL2 works: the GPU first, then software rendering."""
    last = None
    for gpu in (True, False):
        b = Browser(width, height, scale, browser, gpu=gpu)
        try:
            b.open(html_probe)
            return b
        except CaptureError as err:
            last = err
            b.close()
    raise last


def _url(html_path, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return Path(html_path).resolve().as_uri() + ("?" + q if q else "")


# ---------------------------------------------------------------------------- review

SHEETS = ("assembly", "views", "life", "motion", "provenance")


def review(html_path, out_dir, width=1440, height=900, scale=1.0, sheets=SHEETS, browser=None):
    """Capture the review set: contact sheets (assembly, views, life, motion, provenance),
    a still of the reduced-motion state, a still of each of the scene's own views, the solid
    view and a labelled hero once assembled and opened. Returns the written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    b = open_browser(_url(html_path, ui=0, capture=1, t="0"), width, height, scale, browser)
    try:
        timeline = b.evaluate("JSON.stringify(HOLO.timeline())")
        tl = json.loads(timeline)
        end = max(tl["assembly"]["end"], tl.get("settled", 0.0))
        views = json.loads(b.evaluate("JSON.stringify((HOLOGRAM_GEOMETRY.presentation.views || []).map((v) => v.id))"))
        for kind in sheets:
            b.open(_url(html_path, sheet=kind, ui=0, capture=1))
            p = out / ("sheet-%s.png" % kind)
            b.shot(p)
            written.append(str(p))
        b.open(_url(html_path, motion="reduced", ui=0, capture=1, labels=1))
        p = out / "still-reduced-motion.png"
        b.shot(p)
        written.append(str(p))
        for vid in views:
            # each of the scene's own views, still, so its framing can be judged
            # the "open" view is what opening reveals: shown opened, whatever the still pose
            b.open(_url(html_path, view=vid, motion="reduced", ui=0, capture=1, open=1 if vid == "open" else None))
            p = out / ("view-%s.png" % vid)
            b.shot(p)
            written.append(str(p))
        if b.evaluate("window.HOLOGRAM_SOLID ? 1 : 0"):
            # the surfaces as a solid, as a print or a modelling program shows them: what the light forgives
            # (panels that do not meet, glass outside its frame, a crumpled corner) shows here
            b.open(_url(html_path, view="hero", motion="reduced", camera="still", ui=0, capture=1, solid=1))
            p = out / "solid.png"
            b.shot(p)
            written.append(str(p))
        if b.evaluate("JSON.stringify(((HOLOGRAM_GEOMETRY.provenance || {}).authoring || {}).rounds || [])") != "[]":
            # the improvement rounds' timeline, over the still (`construct rounds` recorded them)
            b.open(_url(html_path, motion="reduced", ui=0, capture=1, rounds=1))
            p = out / "rounds.png"
            b.shot(p)
            written.append(str(p))
        # the hero is the whole object in its fitted hero framing, assembled and opened: the
        # camera held still, so a tour or drift never decides what the hero shows
        b.open(_url(html_path, t="%.3f" % (end + 2.0), view="hero", camera="still", ui=0, capture=1, labels=1))
        p = out / "hero.png"
        b.shot(p)
        written.append(str(p))
        tl["hero_camera"] = json.loads(b.evaluate("JSON.stringify(HOLO.camera())"))
        tl["hero_fitted"] = json.loads(b.evaluate("JSON.stringify(HOLO.fitted('hero'))"))
        (out / "timeline.json").write_text(json.dumps(tl) + "\n", encoding="utf-8")
    finally:
        b.close()
    return written


def stills(html_path, out_dir, views, width=1280, height=800, scale=1.0, browser=None):
    """A still (reduced motion, no labels) from each named view: front, side, back, top,
    three-quarter, hero or one of the scene's own views. Written as still-<view>.png."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    if not views:
        return written
    b = open_browser(_url(html_path, ui=0, capture=1, motion="reduced"), width, height, scale, browser)
    try:
        for v in views:
            b.open(_url(html_path, view=v, motion="reduced", camera="still", ui=0, capture=1, open=1 if v == "open" else None))
            p = out / ("still-%s.png" % v)
            b.shot(p)
            written.append(str(p))
    finally:
        b.close()
    return written


def frames(html_path, out_dir, seconds, fps=24, start=0.0, width=1280, height=720, scale=1.0, view=None, browser=None,
           extra=None):
    """Frames of the animation from `start`, `seconds` long. `extra` adds URL parameters, for film mode:
    {"assembly": seconds, "audio": "features.json"} (the features file beside the page), "camera": "steady",
    "reactivity": 0..2 (a page built with film mode)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    b = open_browser(_url(html_path, t="%.3f" % start, ui=0, capture=1, view=view, **(extra or {})), width, height, scale,
                     browser)
    paths = []
    try:
        if extra and extra.get("audio"):  # film mode: wait until the features are loaded, and refuse to go without them
            b.evaluate("window.HOLO_AUDIO_READY && window.HOLO_AUDIO_READY.then(() => true)")
            if not b.evaluate("!!(window.HOLO && HOLO.hologram && HOLO.hologram.audio)"):
                raise CaptureError("the audio features did not load (%s): see the page's console" % extra["audio"])
        n = int(round(seconds * fps))
        for i in range(n):
            t = start + i / fps
            b.evaluate("HOLO.renderAt(%.4f)" % t)
            p = out / ("frame-%05d.png" % i)
            b.shot(p)
            paths.append(str(p))
    finally:
        b.close()
    return paths


def encode_video(frame_dir, out_path, fps=24, sound=None, sound_start=0.0):
    """MP4 (H.264) or GIF from captured frames with ffmpeg, when it is installed. With `sound` (any audio file
    ffmpeg reads), an MP4 carries that audio from `sound_start` seconds, cut or padded to the video's length."""
    from . import film_audio
    try:
        ffmpeg = film_audio.find_ffmpeg()
    except FileNotFoundError:
        ffmpeg = None
    if not ffmpeg:
        raise CaptureError("ffmpeg is not installed: the frames are in %s" % frame_dir)
    pattern = str(Path(frame_dir) / "frame-%05d.png")
    out_path = str(out_path)
    if out_path.endswith(".gif"):
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern, "-vf",
               "fps=%d,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" % min(fps, 15),
               out_path]
    else:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern]
        if sound:
            # the audio is padded with silence if it is shorter, then cut at the last frame: the video keeps every frame
            cmd += ["-ss", "%.3f" % sound_start, "-i", str(sound), "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:a", "aac",
                    "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)
    return out_path
