/* Construct viewer — a dependency-free WebGL2 renderer for compiled construct
 * geometry (format "construct-geometry" version 2).
 *
 * Everything is a pure function of the geometry, the seed and a time t, so any frame
 * can be reproduced exactly (?t=3.2) for review captures. The renderer only draws what
 * the compiler produced: it runs no scene-supplied code and fetches nothing.
 *
 * URL parameters: t (freeze time, seconds), view (hero|front|side|back|top|three-quarter|<scene view>),
 * motion (full|reduced), mode (light|provenance), ui (1|0), labels (1|0), caption (1|0),
 * rounds (1|0: show or never show the round timeline a `construct rounds` run recorded),
 * sheet (assembly|views|motion|life|provenance|all), fps (15|20|30|60|0), capture (1),
 * open (0..1: hold the articulations at this opening instead of playing them),
 * shift (x,y: move the framed object across the screen, in fractions of the half-viewport),
 * zoom (>1 pulls the camera back to leave room around the object).
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------------- palettes
  const hex = (h) => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255];
  // tones: accent, bright, hairline, structure, dust, identity(base), data, faint; then base and haze tints
  const PALETTES = {
    violet: { tones: ["#d16bd0", "#f6eaff", "#eadcf3", "#b7a4c8", "#9682d7", "#eadcf3", "#8fd3ff", "#6f6080"], base: "#070207", haze: "#d16bd0", haze2: "#9682d7" },
    cyan:   { tones: ["#44d6ff", "#e9fbff", "#d6f1f9", "#9dbcca", "#6c9cff", "#d6f1f9", "#9cffe0", "#4f6873"], base: "#01060a", haze: "#2fb6e0", haze2: "#6c7cff" },
    amber:  { tones: ["#ffb14a", "#fff4e0", "#f5e2c6", "#c8ae8d", "#ff8a5c", "#f5e2c6", "#ffd56b", "#6f5e49"], base: "#090502", haze: "#ff9a3a", haze2: "#ff6a4a" },
    green:  { tones: ["#57ff9a", "#ecfff4", "#d5f5e2", "#9cc4ad", "#62d4ff", "#d5f5e2", "#c6ff6b", "#4a6b58"], base: "#010804", haze: "#36d47e", haze2: "#3aa8d8" },
    ice:    { tones: ["#9fd8ff", "#f2faff", "#e0eef7", "#a9bfcf", "#b7a6ff", "#e0eef7", "#7ff0ff", "#56687a"], base: "#02050a", haze: "#7fb8e8", haze2: "#a090ff" },
    rose:   { tones: ["#ff6f9b", "#fff0f5", "#f6dce6", "#c9a6b6", "#ff9d6f", "#f6dce6", "#ffd1e3", "#735362"], base: "#0a0206", haze: "#ff4f86", haze2: "#ff8a5c" },
  };
  // identity light: a low-chroma tint over the structure tone (the place's own material)
  const IDENTITY = { "warm-wood": [0.88, 0.6, 0.34], stone: [0.8, 0.77, 0.7], steel: [0.62, 0.75, 0.88],
    brass: [0.96, 0.78, 0.4], bio: [0.45, 0.96, 0.72], ember: [1.0, 0.48, 0.26], ice: [0.7, 0.92, 1.0], paper: [0.96, 0.92, 0.82] };
  const CERT_CODE = { verified: 0, user_supplied: 1, inferred: 2, decorative: 3 };
  const ROLE_CODE = { mass: 0, structure: 1, detail: 2, identity: 3, data: 4, ornament: 5, ground: 6, artwork: 7 };
  const EVENT_CODE = { scan: 1, sweep: 2, wave: 3, shimmer: 4, glitch: 5, brownout: 6, propagate: 7, tear: 8, burst: 9 };
  const EVENT_SECONDS = { scan: 2.6, sweep: 2.2, wave: 3.2, shimmer: 2.4, glitch: 0.7, brownout: 1.1, propagate: 2.4, tear: 0.9, burst: 2.0 };

  // ------------------------------------------------------------------------- shaders
  const COMMON = `#version 300 es
precision highp float;
precision highp int;
uniform mat4 uVP;
uniform vec3 uEye;
uniform vec2 uViewport;      // device pixels of this viewport
uniform float uDpr;
uniform highp sampler2D uStyles;
uniform vec3 uPalette[8];
uniform vec3 uCertColor[4];
uniform float uMode;         // 0 light, 1 provenance
uniform float uBuild;        // build progress 0..1 (beyond 1: complete)
uniform float uTime;
uniform vec4 uEvent;         // kind, progress 0..1, strength, seed
uniform vec4 uEventP;        // kind-specific: origin/axis data
uniform vec4 uBounds;        // centre xyz, radius
uniform vec2 uYRange;        // ground y, top y
uniform mat4 uMotion[32];
uniform float uMotionGain[32];
uniform mat4 uJoint[16];     // articulation chains, posed by the opening
uniform float uGhost;        // pre-build ghost image 0..1
uniform float uStabilise;    // glow surplus after the build
uniform float uGlobalAlpha;
uniform float uFogDensity;
uniform float uLife;         // ambient life 0..1

float h1(float n) { return fract(sin(n * 12.9898 + uEvent.w * 78.233) * 43758.5453); }
float band(float x, float front, float w) { float d = (x - front) / w; return exp(-d * d); }
float strike(float t) { return smoothstep(0.0, 0.08, t) * (1.0 - smoothstep(0.7, 1.0, t)) * (0.75 + 0.25 * step(0.5, fract(t * 5.0))); }

vec4 styleA(float s) { return texelFetch(uStyles, ivec2(0, int(s + 0.5)), 0); }  // tone, alpha, width, glow
vec4 styleB(float s) { return texelFetch(uStyles, ivec2(1, int(s + 0.5)), 0); }  // dash, fade, part, slot
vec4 styleC(float s) { return texelFetch(uStyles, ivec2(2, int(s + 0.5)), 0); }  // occluder, certainty, role, drift
vec4 styleD(float s) { return texelFetch(uStyles, ivec2(3, int(s + 0.5)), 0); }  // joint

// periodic motion about the rest pose, then the articulation chain carries it
vec3 moved(vec3 p, float slot, float joint, inout float gain) {
  if (slot >= -0.5) { int i = int(slot + 0.5); p = (uMotion[i] * vec4(p, 1.0)).xyz; gain *= uMotionGain[i]; }
  if (joint >= -0.5) p = (uJoint[int(joint + 0.5)] * vec4(p, 1.0)).xyz;
  return p;
}
// what an event does to where a point is drawn
vec3 displaced(vec3 p, float id) {
  int k = int(uEvent.x + 0.5);
  float t = uEvent.y, s = uEvent.z, R = uBounds.w;
  float hy = (p.y - uYRange.x) / max(uYRange.y - uYRange.x, 1e-4);
  if (k == 3) { // wave: a breath rises through it, pushing outward a little
    vec2 d = p.xz - uBounds.xz; float l = length(d);
    p.xz += (l > 1e-4 ? d / l : vec2(0.0)) * 0.025 * R * s * band(hy, t * 1.3 - 0.15, 0.12);
  } else if (k == 5) { // glitch: a slice loses registration, stepped
    float lo = uEventP.x, hi = uEventP.y;
    if (hy > lo && hy < hi) p.x += (h1(floor(t * 9.0)) - 0.5) * 0.09 * R * s * strike(t);
  } else if (k == 8) { // tear: a height band jitters along x
    if (hy > uEventP.x && hy < uEventP.y) p.x += sin(p.y * 40.0 + t * 60.0) * 0.012 * R * s * strike(t);
  } else if (k == 9) { // burst: thrown outward, then gathered back
    vec3 d = p - uBounds.xyz; p += d * 0.12 * s * sin(3.14159 * t) * (0.5 + h1(id));
  }
  if (uGhost > 0.0) p.x += (h1(floor(uTime * 14.0) + p.y * 3.0) - 0.5) * 0.03 * R * uGhost * step(0.6, h1(floor(p.y * 6.0 / R) + floor(uTime * 8.0)));
  return p;
}
// how bright an event makes a point (1 = unchanged)
float eventGain(vec3 p, float id) {
  int k = int(uEvent.x + 0.5);
  if (k == 0) return 1.0;
  float t = uEvent.y, s = uEvent.z;
  float hy = (p.y - uYRange.x) / max(uYRange.y - uYRange.x, 1e-4);
  if (k == 1) return 1.0 + 1.8 * s * band(hy, t * 1.25 - 0.12, 0.05);                     // scan
  if (k == 2) { float a = dot(p - uBounds.xyz, uEventP.xyz) / uBounds.w;                  // sweep
                return 1.0 + 1.4 * s * band(a, mix(-1.2, 1.2, t), 0.22); }
  if (k == 3) return 1.0 + 0.9 * s * band(hy, t * 1.3 - 0.15, 0.12);                      // wave
  if (k == 4) return 1.0 + 1.6 * s * step(0.86, h1(id + floor(uTime * 10.0))) * sin(3.14159 * t); // shimmer
  if (k == 5) return (hy > uEventP.x && hy < uEventP.y) ? 1.0 + 1.3 * s * strike(t) : 1.0;  // glitch
  if (k == 6) return (dot(p - uBounds.xyz, uEventP.xyz) > 0.0) ? 1.0 - 0.85 * min(s, 1.0) * strike(t) : 1.0; // brownout
  if (k == 7) { float d = length(p - uEventP.xyz) / uBounds.w;                             // propagate
                return 1.0 + 1.7 * s * band(d, t * 2.2, 0.16); }
  if (k == 8) return (hy > uEventP.x && hy < uEventP.y) ? 1.0 + 1.1 * s * strike(t) : 1.0;  // tear
  if (k == 9) return 1.0 + 1.2 * s * sin(3.14159 * t);                                      // burst
  return 1.0;
}
vec3 toneColor(float tone, float cert) {
  if (uMode > 0.5) return uCertColor[int(cert + 0.5)];
  return uPalette[int(tone + 0.5)];
}
float fogOf(vec3 p, float fade) {
  float beyond = max(distance(p, uEye) - (distance(uBounds.xyz, uEye) - 0.3 * uBounds.w), 0.0) / uBounds.w;
  return exp(-uFogDensity * beyond * (1.0 + 0.7 * fade));
}
`;

  const LINE_VS = COMMON + `
layout(location=0) in vec2 corner;
layout(location=1) in vec3 aA;
layout(location=2) in vec3 aB;
layout(location=3) in float aStyle;
layout(location=4) in vec2 aPhase;
uniform float uInk;     // under-stroke pass
uniform float uHidden;  // 1 front, <1 behind glass
out vec4 vColor; out float vAcross; out float vHalf; out float vGlow; out float vDash; out float vPhase; out float vDashKind; out float vTip;
void main() {
  vec4 sa = styleA(aStyle), sb = styleB(aStyle), sc = styleC(aStyle), sd = styleD(aStyle);
  float gain = 1.0;
  float id = float(gl_InstanceID);
  vec3 a = displaced(moved(aA, sb.w, sd.x, gain), id), b = displaced(moved(aB, sb.w, sd.x, gain), id + 0.5);
  vec4 ca = uVP * vec4(a, 1.0), cb = uVP * vec4(b, 1.0);
  float near = 0.02;
  if (ca.w < near && cb.w < near) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vColor = vec4(0.0); return; }
  if (ca.w < near) ca = mix(ca, cb, (near - ca.w) / (cb.w - ca.w));
  if (cb.w < near) cb = mix(cb, ca, (near - cb.w) / (ca.w - cb.w));
  vec2 hv = 0.5 * uViewport;
  vec2 pa = ca.xy / ca.w * hv, pb = cb.xy / cb.w * hv, d = pb - pa;
  float len = length(d);
  vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0), nrm = vec2(-dir.y, dir.x);
  vec3 mid = mix(a, b, corner.x);
  float ev = eventGain(mid, id);
  float half_ = 0.5 * sa.z * uDpr * (uInk > 0.5 ? 1.0 : 1.0);
  float glow = sa.w * uDpr * (1.0 + 0.6 * uStabilise) + (ev > 1.05 ? 2.5 * uDpr * min(ev - 1.0, 1.5) : 0.0);
  if (uInk > 0.5) { half_ += 1.4 * uDpr; glow = 0.0; }
  float ext = half_ + glow + 1.0;
  vec4 c = corner.x < 0.5 ? ca : cb;
  // across: the full width with its glow; along: only the anti-aliased edge, so joints do not bead
  float along = min(half_ + 1.0, 1.0);
  vec2 off = nrm * corner.y * ext + dir * (corner.x < 0.5 ? -along : along);
  c.xy += off / hv * c.w;
  gl_Position = c;
  vAcross = corner.y * ext; vHalf = half_; vGlow = glow;
  vDash = corner.x * distance(aA, aB) / max(uBounds.w, 1e-4);
  vDashKind = sb.x;
  vPhase = mix(aPhase.x, aPhase.y, corner.x);
  float fog = fogOf(mid, sb.y);
  float alpha = sa.y * fog * gain * uGlobalAlpha * uHidden;
  vTip = 0.0;
  if (uInk > 0.5) { vColor = vec4(0.0, 0.0, 0.0, min(0.62, alpha * 0.8)); return; }
  vec3 col = toneColor(sa.x, sc.y) * ev * (1.0 + 0.35 * uStabilise);
  float a2 = clamp(alpha * min(ev, 1.6), 0.0, 1.0);
  vColor = vec4(col * a2, a2);
}`;

  const LINE_FS = `#version 300 es
precision highp float;
in vec4 vColor; in float vAcross; in float vHalf; in float vGlow; in float vDash; in float vPhase; in float vDashKind; in float vTip;
uniform float uBuild; uniform float uDashScale;
out vec4 o;
void main() {
  if (vPhase > uBuild + 0.0005) discard;
  float reveal = smoothstep(vPhase - 0.0005, vPhase + 0.035, uBuild);
  float tip = uBuild < 1.0 ? exp(-pow((uBuild - vPhase) / 0.02, 2.0)) : 0.0;
  if (vDashKind > 0.5) {
    float u = fract(vDash * uDashScale);
    if (vDashKind < 1.5 ? u > 0.56 : (u > 0.22)) discard;
  }
  float d = abs(vAcross);
  float w = max(vHalf, 0.5);
  float core = (1.0 - smoothstep(w - 0.5, w + 0.5, d)) * min(1.0, vHalf * 2.0);
  float halo = 0.0;
  if (vGlow > 0.0) { float t = max(d - vHalf, 0.0) / vGlow; halo = 0.42 * exp(-4.0 * t * t); }
  float cov = clamp(core + halo * (1.0 - core), 0.0, 1.0) * reveal;
  if (cov < 0.004) discard;
  vec4 c = vColor * (1.0 + 2.2 * tip);
  o = vec4(c.rgb * cov, min(1.0, c.a) * mix(cov, cov * 0.7, 1.0 - core));
}`;

  const FILL_VS = COMMON + `
layout(location=0) in vec3 aPos;
layout(location=1) in float aStyle;
layout(location=2) in float aPhase;
out vec3 vWorld; out vec4 vTint; out float vPhase; out float vOcc;
void main() {
  vec4 sa = styleA(aStyle), sb = styleB(aStyle), sc = styleC(aStyle), sd = styleD(aStyle);
  float gain = 1.0;
  vec3 p = displaced(moved(aPos, sb.w, sd.x, gain), float(gl_VertexID / 3));
  vWorld = p; vPhase = aPhase; vOcc = sc.x;
  float ev = eventGain(p, float(gl_VertexID / 3));
  vTint = vec4(toneColor(sa.x, sc.y) * ev, sa.y * gain * fogOf(p, sb.y) * uGlobalAlpha);
  gl_Position = uVP * vec4(p, 1.0);
}`;
  const FILL_FS = `#version 300 es
precision highp float;
in vec3 vWorld; in vec4 vTint; in float vPhase; in float vOcc;
uniform vec3 uEye; uniform float uBuild; uniform vec3 uBase;
out vec4 o;
void main() {
  if (vPhase > uBuild + 0.0005) discard;
  float reveal = smoothstep(vPhase, vPhase + 0.06, uBuild);
  vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
  float facing = abs(dot(n, normalize(uEye - vWorld)));
  float fres = pow(1.0 - facing, 2.0);
  if (vOcc > 0.5) { float a = 0.55 * reveal * vTint.a / max(vTint.a, 1e-4) * 0.9; o = vec4(uBase * a, a); return; }
  float a = vTint.a * (0.35 + 1.6 * fres) * reveal;
  o = vec4(mix(uBase, vTint.rgb, 0.55) * a, a);
}`;

  const POINT_VS = COMMON + `
layout(location=0) in vec2 corner;
layout(location=1) in vec3 aPos;
layout(location=2) in float aSize;
layout(location=3) in float aStyle;
layout(location=4) in float aShape;
layout(location=5) in float aPhase;
out vec4 vColor; out vec2 vUv; out float vShape; out float vPhase;
void main() {
  vec4 sa = styleA(aStyle), sb = styleB(aStyle), sc = styleC(aStyle), sd = styleD(aStyle);
  float gain = 1.0; float id = float(gl_InstanceID);
  vec3 p = moved(aPos, sb.w, sd.x, gain);
  float drift = sc.w;
  float life = 1.0;
  if (drift > 0.5) { // rising motes (the projector's): wrap within a column, fade at both ends
    float hgt = uBounds.w * 1.6;
    float k = fract(h1(id * 3.1) + uTime * (0.03 + 0.03 * h1(id)));
    p.y += k * hgt; life = sin(3.14159 * k);
  } else if (uLife > 0.0 && int(sc.z + 0.5) == 5) { // decorative dust breathes
    p += vec3(sin(uTime * 0.5 + id), sin(uTime * 0.37 + id * 1.7), cos(uTime * 0.43 + id)) * 0.012 * uBounds.w * uLife;
  }
  p = displaced(p, id);
  float ev = eventGain(p, id);
  vec4 c = uVP * vec4(p, 1.0);
  float size = aSize * uDpr * (1.0 + 0.4 * (ev - 1.0));
  c.xy += corner * size / uViewport * c.w;
  gl_Position = c;
  vUv = corner; vShape = aShape; vPhase = aPhase;
  float a = sa.y * gain * life * fogOf(p, sb.y) * uGlobalAlpha * min(ev, 1.8);
  vColor = vec4(toneColor(sa.x, sc.y) * min(ev, 2.0) * a, a);
}`;
  const POINT_FS = `#version 300 es
precision highp float;
in vec4 vColor; in vec2 vUv; in float vShape; in float vPhase;
uniform float uBuild;
out vec4 o;
void main() {
  if (vPhase > uBuild + 0.0005) discard;
  float r = length(vUv), cov;
  if (vShape < 0.5) cov = smoothstep(0.42, 0.32, r) + 0.5 * exp(-r * r * 7.0);
  else if (vShape < 1.5) cov = smoothstep(0.1, 0.0, abs(r - 0.8)) + 0.12 * exp(-r * r * 3.0);
  else if (vShape < 2.5) { float m = max(abs(vUv.x), abs(vUv.y)); cov = smoothstep(0.5, 0.4, m) + 0.3 * exp(-r * r * 5.0); }
  else cov = exp(-r * r * 5.5);
  cov = clamp(cov, 0.0, 1.0) * (1.0 - smoothstep(0.92, 1.0, r)) * smoothstep(vPhase, vPhase + 0.05, uBuild);
  if (cov < 0.004) discard;
  o = vColor * cov;
}`;

  const QUAD_VS = `#version 300 es
layout(location=0) in vec2 p;
out vec2 uv;
void main() { uv = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }`;

  const HAZE_FS = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform float uTime; uniform float uAspect; uniform float uPresence; uniform vec2 uCore;
uniform vec3 uBase; uniform vec3 uTint; uniform vec3 uTint2; uniform vec2 uScan; uniform float uSeed;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7)) + uSeed) * 43758.5453); }
float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p) { float s = 0.0, k = 0.5; for (int i = 0; i < 4; i++) { s += k * noise(p); p = p * 2.03 + 17.1; k *= 0.5; } return s; }
void main() {
  vec2 q = vec2((uv.x - 0.5) * uAspect, uv.y - 0.5), c = vec2((uCore.x - 0.5) * uAspect, uCore.y - 0.5);
  float rc = length(q - c);
  float a = fbm(q * 2.1 + vec2(uTime * 0.011, uTime * 0.006));
  float b = fbm(q * 4.4 - vec2(uTime * 0.019, -uTime * 0.009) + 5.0);
  float haze = smoothstep(0.34, 0.95, a * 0.7 + b * 0.45) * (0.5 + 0.5 * exp(-rc * rc * 2.6));
  vec3 col = uBase * 1.5 + uTint * haze * 0.11 + uTint2 * haze * b * 0.07 + uTint * 0.07 * exp(-rc * rc * 5.0);
  col += uTint * 0.14 * uScan.y * exp(-pow((uv.y - uScan.x) / 0.04, 2.0)) * (0.5 + 0.5 * b);
  o = vec4(col * uPresence, 1.0);
}`;

  const DRESS_FS = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform vec2 uSize; uniform float uDpr; uniform float uScanlines; uniform float uVignette; uniform float uVeil;
void main() {
  vec2 px = uv * uSize / uDpr;
  float line = uScanlines * (mod(floor(uv.y * uSize.y / uDpr), 3.0) >= 2.0 ? 0.1 : 0.0);
  vec2 d = (uv - vec2(0.5, 0.47)) * vec2(1.0, 1.08);
  float vig = uVignette * 0.6 * smoothstep(0.38, 0.86, length(d) * 1.25);
  float veil = uVeil * 0.7 * smoothstep(0.2, 0.75, length(uv - 0.5));
  float a = 1.0 - (1.0 - line) * (1.0 - vig) * (1.0 - veil);
  o = vec4(0.0, 0.0, 0.0, a);
}`;

  const ART_VS = COMMON + `
layout(location=0) in vec3 aPos;
layout(location=1) in vec2 aUv;
uniform float uSlot; uniform float uJointArt; uniform float uPhaseArt;
out vec2 vUv; out float vA;
void main() {
  float gain = 1.0;
  vec3 p = moved(aPos, uSlot, uJointArt, gain);
  vUv = aUv; vA = uGlobalAlpha * smoothstep(uPhaseArt, uPhaseArt + 0.1, uBuild);
  gl_Position = uVP * vec4(p, 1.0);
}`;
  const ART_FS = `#version 300 es
precision highp float;
in vec2 vUv; in float vA; out vec4 o;
uniform sampler2D uTex; uniform float uTime; uniform vec2 uViewport;
uniform vec2 uMask;   // x: 0 rectangle, 1 circle; y: the hole as a fraction of the radius
uniform vec4 uText;   // rgb: the light the renderer sets text in; a: 1 for text
void main() {
  vec4 c = texture(uTex, vUv);
  float edge;
  if (uMask.x > 0.5) {
    float r = length(vUv - 0.5) * 2.0;
    if (r > 1.0 || r < uMask.y) discard;
    edge = smoothstep(1.0, 0.96, r) * smoothstep(uMask.y, uMask.y + 0.03, r);
  } else {
    vec2 e = min(vUv, 1.0 - vUv);
    edge = smoothstep(0.0, 0.025, min(e.x, e.y));
  }
  // the image as projected light: faint scan texture, a little transparency, edges that fade
  float scan = 0.86 + 0.14 * step(1.0, mod(gl_FragCoord.y, 3.0));
  if (uText.a > 0.5) { float t = vA * c.a; if (t < 0.003) discard; o = vec4(uText.rgb * scan * t, t); return; }
  float a = vA * 0.82 * (0.7 + 0.3 * edge);
  o = vec4(c.rgb * scan * a, a);
}`;

  // ------------------------------------------------------------------------- GL helpers
  function compile(gl, type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + "\n" + src.split("\n").map((l, i) => (i + 1) + " " + l).join("\n"));
    return s;
  }
  function program(gl, vs, fs) {
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const u = {};
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) {
      const info = gl.getActiveUniform(p, i);
      const name = info.name.replace(/\[0\]$/, "");
      u[name] = gl.getUniformLocation(p, info.name);
    }
    return { p, u };
  }

  // ------------------------------------------------------------------------- math
  const V = {
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
    lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
  };
  function lookAt(eye, target, up) {
    const z = V.norm(V.sub(eye, target)), x = V.norm(V.cross(up, z)), y = V.cross(z, x);
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -V.dot(x, eye), -V.dot(y, eye), -V.dot(z, eye), 1];
  }
  function perspective(fovDeg, aspect, near, far) {
    const f = 1 / Math.tan(fovDeg * Math.PI / 360), nf = 1 / (near - far);
    return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
  }
  function mat4mul(a, b) {
    const o = new Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
      o[c * 4 + r] = s;
    }
    return o;
  }
  function project(m, p) {
    const x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
    const w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15];
    return w > 1e-6 ? [x / w, y / w, w] : null;
  }
  function axisMatrix(axis, angle, pivot, offset) {
    const [x, y, z] = V.norm(axis), c = Math.cos(angle), s = Math.sin(angle), t = 1 - c;
    const r = [t * x * x + c, t * x * y + s * z, t * x * z - s * y, 0,
               t * x * y - s * z, t * y * y + c, t * y * z + s * x, 0,
               t * x * z + s * y, t * y * z - s * x, t * z * z + c, 0, 0, 0, 0, 1];
    // translate(pivot + offset) * R * translate(-pivot)
    const rp = [r[0] * pivot[0] + r[4] * pivot[1] + r[8] * pivot[2], r[1] * pivot[0] + r[5] * pivot[1] + r[9] * pivot[2],
                r[2] * pivot[0] + r[6] * pivot[1] + r[10] * pivot[2]];
    r[12] = pivot[0] - rp[0] + offset[0]; r[13] = pivot[1] - rp[1] + offset[1]; r[14] = pivot[2] - rp[2] + offset[2];
    return r;
  }
  const ease = (k) => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  function rng(seed) { let s = (seed >>> 0) || 1; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

  // ------------------------------------------------------------------------- the hologram
  function Hologram(canvas, geo, options) {
    this.canvas = canvas; this.geo = geo; this.opt = options;
    const gl = canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: true, alpha: true, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 is not available in this browser.");
    this.gl = gl;
    this.programs = {
      line: program(gl, LINE_VS, LINE_FS), fill: program(gl, FILL_VS, FILL_FS), point: program(gl, POINT_VS, POINT_FS),
      haze: program(gl, QUAD_VS, HAZE_FS), dress: program(gl, QUAD_VS, DRESS_FS), art: program(gl, ART_VS, ART_FS),
    };
    this.R = Math.max(geo.bounds.radius, 1e-3);
    this.C = geo.bounds.center;
    this.ground = geo.bounds.min[1];
    this.top = geo.bounds.max[1];
    this.seed = (geo.provenance && geo.scene_sha256) ? parseInt(geo.scene_sha256.slice(0, 8), 16) : 7;
    this.buildEnvironment();
    this.upload();
    this.schedule = this.buildSchedule();
    this.camera = this.cameraFor(options.view || "hero");
  }

  Hologram.prototype.buildEnvironment = function () {
    // the survey grid and the optional projector: geometry of the presentation, not the object
    const g = this.geo, at = g.presentation.atmosphere, styles = g.styles.map((s) => s.slice());
    const parts = g.parts;
    const extra = [], extraPts = [];
    const lines = g.lines.slice(), points = g.points.slice();
    const add = (style) => { styles.push(style); return styles.length - 1; };
    // a hovering subject keeps its survey ground below it (presentation.float)
    const R = this.R, cx = this.C[0], cz = this.C[2], y = this.ground - (g.presentation.float || 0) - 0.0005;
    if (at.grid) {
      const span = Math.max(g.bounds.max[0] - g.bounds.min[0], g.bounds.max[2] - g.bounds.min[2], R) * 2.6;
      const raw = span / 14, p10 = Math.pow(10, Math.floor(Math.log10(raw)));
      const step = [1, 2, 5, 10].map((m) => m * p10).find((s) => s >= raw) || raw;
      const n = Math.min(40, Math.ceil(span / step / 2));
      const sMinor = add([7, 0.16, 0.7, 0, 0, 3, -1, -1, 0]), sMajor = add([7, 0.3, 0.8, 0, 0, 2, -1, -1, 0]);
      for (let i = -n; i <= n; i++) {
        const s = i % 5 === 0 ? sMajor : sMinor;
        lines.push(cx + i * step, y, cz - n * step, cx + i * step, y, cz + n * step, s, 0, 0);
        lines.push(cx - n * step, y, cz + i * step, cx + n * step, y, cz + i * step, s, 0, 0);
      }
    }
    if (at.projector) {
      // an emitter below the object: rings, a light cone to its footprint, rising motes
      const base = y - 0.06 * R, ring = add([0, 0.85, 1.4, 2.4, 0, 0, -1, -1, 0]), ray = add([4, 0.22, 0.7, 0.6, 0, 1, -1, -1, 0]);
      const rr = [0.12, 0.2, 0.3].map((k) => k * R), N = 48;
      for (const r of rr) for (let i = 0; i < N; i++) {
        const a0 = 2 * Math.PI * i / N, a1 = 2 * Math.PI * (i + 1) / N;
        lines.push(cx + r * Math.cos(a0), base, cz + r * Math.sin(a0), cx + r * Math.cos(a1), base, cz + r * Math.sin(a1), ring, 0, 0);
      }
      const fw = (g.bounds.max[0] - g.bounds.min[0]) / 2, fd = (g.bounds.max[2] - g.bounds.min[2]) / 2;
      for (let i = 0; i < 18; i++) {
        const a = 2 * Math.PI * i / 18;
        lines.push(cx + 0.1 * R * Math.cos(a), base, cz + 0.1 * R * Math.sin(a), cx + fw * Math.cos(a), y, cz + fd * Math.sin(a), ray, 0, 0);
      }
      const mote = add([4, 0.7, 0, 0, 0, 0, -1, -1, 0]);
      const r = rng(this.seed);
      for (let i = 0; i < 90; i++) {
        const a = 2 * Math.PI * r(), d = Math.sqrt(r()) * Math.max(fw, fd) * 0.9;
        points.push(cx + d * Math.cos(a), y, cz + d * Math.sin(a), 2.6 + 2 * r(), mote, 3, 0);
      }
      this.moteStyle = mote;
    }
    this.styles = styles; this.allLines = new Float32Array(lines); this.allPoints = new Float32Array(points);
    this.objectLines = g.lines.length / 9; this.envLines = lines.length / 9 - this.objectLines;
  };

  Hologram.prototype.upload = function () {
    const gl = this.gl, g = this.geo;
    // styles texture: 4 texels per style
    const st = new Float32Array(this.styles.length * 16);
    this.styles.forEach((s, i) => {
      const part = s[6] >= 0 ? g.parts[s[6]] : null;
      st.set([s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8],
              part ? CERT_CODE[part.certainty] : 2, part ? ROLE_CODE[part.role] : 6,
              (this.moteStyle === i) ? 1 : 0, s.length > 9 ? s[9] : -1, 0, 0, 0], i * 16);
    });
    this.styleTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.styleTex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, 4, this.styles.length, 0, gl.RGBA, gl.FLOAT, st);

    const corner = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, corner);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, -1, 0, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const sprite = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, sprite);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);

    this.lineVao = gl.createVertexArray();
    gl.bindVertexArray(this.lineVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, corner);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const lb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, lb);
    gl.bufferData(gl.ARRAY_BUFFER, this.allLines, gl.STATIC_DRAW);
    [[1, 3, 0], [2, 3, 12], [3, 1, 24], [4, 2, 28]].forEach(([loc, n, off]) => {
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 36, off); gl.vertexAttribDivisor(loc, 1);
    });

    this.fillVao = gl.createVertexArray();
    gl.bindVertexArray(this.fillVao);
    const fb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, fb);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(g.fills), gl.STATIC_DRAW);
    [[0, 3, 0], [1, 1, 12], [2, 1, 16]].forEach(([loc, n, off]) => { gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 20, off); });
    this.fillCount = g.fills.length / 5;

    this.pointVao = gl.createVertexArray();
    gl.bindVertexArray(this.pointVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, sprite);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const pb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, pb);
    gl.bufferData(gl.ARRAY_BUFFER, this.allPoints, gl.STATIC_DRAW);
    [[1, 3, 0], [2, 1, 12], [3, 1, 16], [4, 1, 20], [5, 1, 24]].forEach(([loc, n, off]) => {
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 28, off); gl.vertexAttribDivisor(loc, 1);
    });
    this.pointCount = this.allPoints.length / 7;

    this.quadVao = gl.createVertexArray();
    gl.bindVertexArray(this.quadVao);
    const qb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, qb);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    // artwork: only supplied, hash-checked bytes the build embedded; otherwise an empty slot.
    // Labels: text the renderer sets itself from the facts, in its own font, as light.
    this.art = [];
    const assets = (window.HOLOGRAM_ASSETS || {});
    const quad = (c, uv) => {
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      const b = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      const d = [];
      for (const i of [0, 1, 2, 0, 2, 3]) d.push(c[i][0], c[i][1], c[i][2], uv[i][0], uv[i][1]);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(d), gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 20, 0);
      gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 20, 12);
      return vao;
    };
    const UV = [[0, 0], [1, 0], [1, 1], [0, 1]];
    for (const lb of g.labels || []) {
      const c = lb.corners, wm = Math.hypot(...V.sub(c[1], c[0])), hm = Math.hypot(...V.sub(c[3], c[0]));
      if (!(wm > 0 && hm > 0)) continue;
      const W = 1024, H = Math.max(16, Math.min(1024, Math.round(W * hm / wm)));
      const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
      const x = cv.getContext("2d");
      const weight = lb.role === "title" ? "600 " : lb.role === "creator" ? "500 " : "400 ";
      let size = H * 0.7;
      const font = (sz) => weight + sz.toFixed(1) + "px ui-sans-serif, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif";
      x.font = font(size);
      const tw = x.measureText(lb.text).width;
      if (tw > W * 0.94) { size *= W * 0.94 / tw; x.font = font(size); }
      x.fillStyle = "#ffffff"; x.textBaseline = "middle";
      x.textAlign = lb.align === "left" ? "left" : lb.align === "right" ? "right" : "center";
      x.fillText(lb.text, lb.align === "left" ? W * 0.03 : lb.align === "right" ? W * 0.97 : W / 2, H * 0.54);
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, cv);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      this.art.push({ vao: quad(c, UV), phase: lb.phase, part: lb.part, tex, ready: true, text: true,
                      certainty: lb.certainty, slot: lb.motion_slot, joint: lb.joint, mask: [0, 0] });
    }
    for (const a of g.artwork || []) {
      const vao = quad(a.corners, a.uv);
      const entry = { vao, phase: a.phase, part: a.part, tex: null, ready: false,
                      slot: a.motion_slot !== undefined ? a.motion_slot : -1, joint: a.joint !== undefined ? a.joint : -1,
                      mask: [a.mask === "circle" ? 1 : 0, a.inner_ratio || 0] };
      if (assets[a.asset_id]) {
        const img = new Image();
        let done;
        entry.loading = new Promise((res) => { done = res; });
        img.onerror = () => done();
        img.onload = () => {
          entry.tex = gl.createTexture();
          gl.bindTexture(gl.TEXTURE_2D, entry.tex);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
          gl.generateMipmap(gl.TEXTURE_2D);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
          entry.ready = true;
          done();
        };
        img.src = assets[a.asset_id];
      }
      this.art.unshift(entry);
    }
    gl.bindVertexArray(null);
  };

  // ------------------------------------------------------------------------- time
  Hologram.prototype.assemblyTimes = function () {
    const asm = this.geo.animation.assembly;
    if (this.opt.reduced || asm.style === "cut") return { ghost: 0, collapse: 0, build: 0, settle: 0, end: 0 };
    const ghost = asm.interference && asm.style === "ceremony" ? 0.9 : 0, collapse = ghost ? 0.35 : 0;
    const build = Math.max(0.2, asm.seconds), settle = asm.style === "ceremony" ? 1.1 : 0.4;
    return { ghost, collapse, build, settle, end: ghost + collapse + build + settle };
  };

  Hologram.prototype.buildSchedule = function () {
    // the idle life: a deterministic sequence of events after assembly
    const idle = this.geo.animation.idle, out = [];
    if (this.opt.reduced || idle.life === "off" || !idle.events.length) return out;
    const r = rng(this.seed ^ 0x9e3779b9);
    const calm = idle.life === "calm";
    let t = this.openTimes().end + 1.2;
    let last = "";
    for (let i = 0; i < 400 && t < 3600; i++) {
      let kind = idle.events[Math.floor(r() * idle.events.length)];
      if (kind === last && idle.events.length > 1) kind = idle.events[(idle.events.indexOf(kind) + 1) % idle.events.length];
      last = kind;
      const dur = EVENT_SECONDS[kind];
      const lo = r();
      const band = [0.15 + 0.6 * r(), 0];
      band[1] = Math.min(1, band[0] + 0.08 + 0.15 * r());
      const axis = r() < 0.5 ? [1, 0, 0] : [0, 0, 1];
      out.push({ kind, t0: t, dur, strength: idle.strength * (calm ? 0.6 : 1) * (0.75 + 0.25 * lo), band, axis, seed: r() * 100 });
      const gap = idle.cadence[0] + (idle.cadence[1] - idle.cadence[0]) * r();
      t += dur + gap * (calm ? 2 : 1);
    }
    return out;
  };

  Hologram.prototype.state = function (t) {
    const g = this.geo, at = this.assemblyTimes(), s = { build: 2, ghost: 0, stabilise: 0, globalAlpha: 1, event: [0, 0, 0, 0], eventP: [0, 0, 0, 0], scan: [0, 0] };
    if (t < at.end) {
      if (t < at.ghost) { s.ghost = 1; s.build = 2; s.globalAlpha = 0.18 + 0.1 * Math.sin(t * 40) * Math.sin(t * 7); }
      else if (t < at.ghost + at.collapse) { const k = (t - at.ghost) / at.collapse; s.ghost = 1 - k; s.build = 2; s.globalAlpha = 0.2 * (1 - k); }
      else if (t < at.ghost + at.collapse + at.build) { const k = (t - at.ghost - at.collapse) / at.build; s.build = k; s.scan = [k * 1.05, 0.6]; }
      else { const k = (t - at.ghost - at.collapse - at.build) / at.settle; s.build = 2; s.stabilise = Math.exp(-3.5 * k) * (1 - k); }
    }
    for (const e of this.schedule) {
      if (t >= e.t0 && t < e.t0 + e.dur) {
        const p = (t - e.t0) / e.dur;
        s.event = [EVENT_CODE[e.kind], p, e.strength, e.seed];
        if (e.kind === "glitch" || e.kind === "tear") s.eventP = [e.band[0], e.band[1], 0, 0];
        else if (e.kind === "sweep" || e.kind === "brownout") s.eventP = [e.axis[0], e.axis[1], e.axis[2], 0];
        else if (e.kind === "propagate") { const c = this.identityCentre(); s.eventP = [c[0], c[1], c[2], 0]; }
        if (e.kind === "scan") s.scan = [p * 1.25 - 0.12, 0.5 * e.strength];
        break;
      }
      if (e.t0 > t) break;
    }
    s.life = this.opt.reduced || g.animation.idle.life === "off" ? 0 : 1;
    return s;
  };

  // articulations: after assembly the object opens, one order group after another, and holds
  Hologram.prototype.openTimes = function () {
    const arts = this.geo.articulations || [];
    const orders = [...new Set(arts.map((a) => a.order))].sort((a, b) => a - b);
    const start = this.assemblyTimes().end + (orders.length ? 0.6 : 0), per = 1.5;
    return { orders, start, end: start + orders.length * per };
  };
  Hologram.prototype.openAt = function (t) {
    if (this.opt.open !== null && this.opt.open !== undefined) return this.opt.open;
    if (this.opt.reduced) return this.geo.presentation.still_pose === "closed" ? 0 : 1;
    const o = this.openTimes();
    return o.end > o.start ? Math.max(0, Math.min(1, (t - o.start) / (o.end - o.start))) : 0;
  };
  Hologram.prototype.jointUniforms = function (u) {
    const arts = this.geo.articulations || [], joints = this.geo.joints || [];
    const I = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    const mats = new Float32Array(16 * 16);
    for (let i = 0; i < 16; i++) mats.set(I, i * 16);
    const orders = [...new Set(arts.map((a) => a.order))].sort((a, b) => a - b), G = orders.length;
    const A = arts.map((a) => {
      const v = ease(Math.max(0, Math.min(1, (u * G - orders.indexOf(a.order)) / 0.85)));
      if (a.type === "hinge" || a.type === "turn") return axisMatrix(a.axis, a.amount * v * Math.PI / 180, a.pivot, [0, 0, 0]);
      const d = a.amount * v;
      return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, a.axis[0] * d, a.axis[1] * d, a.axis[2] * d, 1];
    });
    // a later articulation rides on the earlier ones: the first in the chain is outermost
    joints.forEach((chain, j) => { if (j < 16) mats.set(chain.reduce((M, i) => mat4mul(M, A[i]), I), j * 16); });
    return mats;
  };

  Hologram.prototype.identityCentre = function () {
    if (this._idc) return this._idc;
    const p = this.geo.parts.find((q) => q.role === "identity") || this.geo.parts[0];
    const b = p.instances[0];
    this._idc = [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2];
    return this._idc;
  };

  Hologram.prototype.motionUniforms = function (t) {
    const mats = new Float32Array(32 * 16), gains = new Float32Array(32).fill(1);
    for (let i = 0; i < 32; i++) mats.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], i * 16);
    const still = this.opt.reduced;
    (this.geo.motions || []).forEach((m, i) => {
      if (i >= 32 || still) return;
      const ph = 2 * Math.PI * (t / m.period + m.phase);
      let ang = 0, off = [0, 0, 0];
      if (m.type === "spin") ang = m.rpm * 2 * Math.PI / 60 * t + 2 * Math.PI * m.phase;
      else if (m.type === "swing") ang = m.degrees * Math.PI / 180 * Math.sin(ph);
      else if (m.type === "bob") off = V.mul(V.norm(m.axis), m.distance * Math.sin(ph));
      else if (m.type === "pulse") gains[i] = 1 + m.amount * 0.5 * (1 + Math.sin(ph));
      if (m.type !== "pulse") mats.set(axisMatrix(m.axis, ang, m.pivot, off), i * 16);
    });
    return { mats, gains };
  };

  // ------------------------------------------------------------------------- camera
  Hologram.prototype.viewSpec = function (id) {
    const g = this.geo, fr = g.presentation.framing;
    const builtin = { hero: { yaw: fr.yaw, pitch: fr.pitch, distance: 1 }, front: { yaw: 0, pitch: 6, distance: 1 },
      side: { yaw: 90, pitch: 6, distance: 1 }, back: { yaw: 180, pitch: 6, distance: 1 },
      top: { yaw: 0, pitch: 82, distance: 1 }, "three-quarter": { yaw: 38, pitch: 26, distance: 1 } };
    const custom = (g.presentation.views || []).find((v) => v.id === id);
    return custom ? Object.assign({ distance: 1 }, custom) : (builtin[id] || builtin.hero);
  };
  Hologram.prototype.targetOf = function (partId) {
    if (!partId) return this.C.slice();
    const p = this.geo.parts.find((q) => q.id === partId);
    if (!p) return this.C.slice();
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const b of p.instances) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], b.min[k]); hi[k] = Math.max(hi[k], b.max[k]); }
    return { c: [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2], r: 0.5 * Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) };
  };
  Hologram.prototype.framingBoxes = function (partId) {
    // what a view must contain: every part's boxes, except decorative clouds of points
    if (!this._boxes) {
      this._boxes = {};
      const all = [];
      for (const p of this.geo.parts) {
        const boxes = p.instances.map((b) => [b.min, b.max]).concat(p.instances.filter((b) => b.open_min).map((b) => [b.open_min, b.open_max]));
        this._boxes[p.id] = boxes;
        if (!(p.shape === "points" && (p.role === "ornament" || p.certainty === "decorative"))) all.push(...boxes);
      }
      this._boxes["*"] = all.length ? all : [[this.geo.bounds.min, this.geo.bounds.max]];
    }
    return this._boxes[partId || "*"] || this._boxes["*"];
  };
  Hologram.prototype.cameraFor = function (id) {
    // fit the silhouette as seen from this direction: project every box corner onto the camera's
    // axes and solve the distance that keeps all of them inside both fields of view, with margin
    const v = this.viewSpec(id), fr = this.geo.presentation.framing, fov = 34;
    const tid = v.target || (id === "hero" ? fr.target : null);
    const boxes = this.framingBoxes(tid);
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const [a, b] of boxes) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], a[k]); hi[k] = Math.max(hi[k], b[k]); }
    const target = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    const y = v.yaw * Math.PI / 180, p = v.pitch * Math.PI / 180;
    const back = [Math.sin(y) * Math.cos(p), Math.sin(p), Math.cos(y) * Math.cos(p)];
    const right = V.norm(V.cross(Math.abs(v.pitch) > 88 ? [0, 0, -1] : [0, 1, 0], back)), up = V.cross(back, right);
    const aspect = this.aspect || 1.6, tanV = Math.tan(fov * Math.PI / 360), tanH = tanV * aspect, margin = 0.86;
    let dist = 1e-3;
    for (const [a, b] of boxes) for (let i = 0; i < 8; i++) {
      const c = [i & 1 ? b[0] : a[0], i & 2 ? b[1] : a[1], i & 4 ? b[2] : a[2]], d = V.sub(c, target);
      const x = Math.abs(V.dot(d, right)), yy = Math.abs(V.dot(d, up)), z = V.dot(d, back);
      dist = Math.max(dist, z + x / (tanH * margin), z + yy / (tanV * margin));
    }
    dist *= (fr.fit || 1) * (v.distance || 1) * (this.opt.zoom || 1);
    return { target, yaw: v.yaw, pitch: v.pitch, dist, fov };
  };
  Hologram.prototype.cameraAt = function (t, base) {
    // the base camera, then the scene's tour (flights between views), then drift and breathing
    const anim = this.geo.animation.camera, reduced = this.opt.reduced;
    let cam = Object.assign({}, base);
    // without a tour of its own, an object that opens turns to its "open" view while it opens
    let tour = anim.tour;
    if (!tour.length && (this.geo.articulations || []).length && (this.geo.presentation.views || []).some((v) => v.id === "open")) {
      const op = this.openTimes();
      tour = [{ view: "open", at: op.start, fly: Math.max(1.5, op.end - op.start) }];
    }
    if (!reduced && !this.opt.freezeCamera) {
      for (let i = 0; i < tour.length; i++) {
        const s = tour[i];
        if (t < s.at) break;
        const prev = i === 0 ? base : this.cameraFor(tour[i - 1].view);
        const next = this.cameraFor(s.view), fly = s.fly || 2.2;
        const k = Math.min(1, (t - s.at) / fly), e = ease(k);
        let dy = next.yaw - prev.yaw; while (dy > 180) dy -= 360; while (dy < -180) dy += 360;
        cam = { target: V.lerp(prev.target, next.target, e), yaw: prev.yaw + dy * e,
                pitch: prev.pitch + (next.pitch - prev.pitch) * e + 8 * Math.sin(Math.PI * e),
                dist: prev.dist * Math.pow(next.dist / prev.dist, e) * (1 + 0.12 * Math.sin(Math.PI * e)), fov: base.fov };
      }
      const start = this.assemblyTimes().end * 0.5;
      const tt = Math.max(0, t - start);
      cam.yaw += anim.drift / 60 * tt;
      cam.dist *= 1 + anim.breathe * Math.sin(2 * Math.PI * tt / 37);
    }
    return cam;
  };
  Hologram.prototype.matrices = function (cam, aspect) {
    const y = cam.yaw * Math.PI / 180, p = cam.pitch * Math.PI / 180;
    const eye = V.add(cam.target, [cam.dist * Math.sin(y) * Math.cos(p), cam.dist * Math.sin(p), cam.dist * Math.cos(y) * Math.cos(p)]);
    const view = lookAt(eye, cam.target, Math.abs(cam.pitch) > 88 ? [0, 0, -1] : [0, 1, 0]);
    const near = Math.max(cam.dist * 0.01, 0.001), far = cam.dist + this.R * 10;
    // an optional screen-space offset: the object framed off-centre (room for type, a layout)
    const sh = this.opt.shift || [0, 0];
    const post = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, sh[0], sh[1], 0, 1];
    return { vp: mat4mul(post, mat4mul(perspective(cam.fov, aspect, near, far), view)), eye };
  };

  // ------------------------------------------------------------------------- drawing
  Hologram.prototype.palette = function () {
    // the compiled palette (the house one unless a person chose another), or ?palette= / ?identity=
    const hint = Object.assign({}, this.geo.presentation.style_hint || {},
                               this.opt.palette ? { palette: this.opt.palette } : {}, this.opt.identity ? { identity: this.opt.identity } : {});
    const pal = PALETTES[hint.palette] || PALETTES.violet;
    const tones = pal.tones.map(hex);
    const id = IDENTITY[hint.identity];
    if (id) tones[5] = [tones[3][0] * 0.58 + id[0] * 0.42 * 1.05, tones[3][1] * 0.58 + id[1] * 0.42 * 1.05, tones[3][2] * 0.58 + id[2] * 0.42 * 1.05];
    else tones[5] = tones[1];
    return { tones, base: hex(pal.base), haze: hex(pal.haze), haze2: hex(pal.haze2) };
  };

  Hologram.prototype.draw = function (t, rect, viewId, opts) {
    const gl = this.gl, g = this.geo, pr = g.presentation, dpr = this.dpr;
    opts = opts || {};
    const reducedWas = this.opt.reduced;
    if (opts.reduced !== undefined) { this.opt.reduced = opts.reduced; this.schedule = this.buildSchedule(); }
    const mode = opts.mode !== undefined ? opts.mode : this.opt.mode;
    const [x, y, w, h] = rect;
    gl.viewport(x, y, w, h);
    gl.scissor(x, y, w, h);
    gl.enable(gl.SCISSOR_TEST);
    const pal = this.palette();
    const transparent = pr.background === "transparent";
    gl.clearColor(transparent ? 0 : pal.base[0], transparent ? 0 : pal.base[1], transparent ? 0 : pal.base[2], transparent ? 0 : 1);
    gl.clearDepth(1);
    gl.depthMask(true);  // a masked depth buffer would not clear, and a sheet's next cell would inherit it
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    this.aspect = w / h;
    const base = opts.camera || (this.userCamera && !opts.view ? this.userCamera : this.cameraFor(viewId || this.opt.view || "hero"));
    const cam = (this.userCamera && !opts.view && !opts.camera) ? base : this.cameraAt(t, base);
    this.lastCamera = cam;
    const { vp, eye } = this.matrices(cam, w / h);
    this.lastVP = vp; this.lastRect = rect;
    const s = this.state(t);
    const mot = this.motionUniforms(t);
    const joints = this.jointUniforms(opts.open !== undefined ? opts.open : this.openAt(t));
    this.lastJoints = joints;

    // atmosphere
    if (!transparent && pr.atmosphere.haze > 0) {
      const core = project(vp, this.C);
      const hz = this.programs.haze;
      gl.useProgram(hz.p);
      gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
      gl.uniform1f(hz.u.uTime, this.opt.reduced ? 0 : t);
      gl.uniform1f(hz.u.uAspect, w / h);
      gl.uniform1f(hz.u.uPresence, 0.55 + 0.45 * pr.atmosphere.haze);
      gl.uniform2f(hz.u.uCore, core ? core[0] * 0.5 + 0.5 : 0.5, core ? core[1] * 0.5 + 0.5 : 0.5);
      gl.uniform3fv(hz.u.uBase, pal.base); gl.uniform3fv(hz.u.uTint, V.mul(pal.haze, pr.atmosphere.haze));
      gl.uniform3fv(hz.u.uTint2, V.mul(pal.haze2, pr.atmosphere.haze));
      const sy = (s.scan[0] * (this.top - this.ground) + this.ground);
      const sc = project(vp, [this.C[0], sy, this.C[2]]);
      gl.uniform2f(hz.u.uScan, sc ? sc[1] * 0.5 + 0.5 : -1, s.scan[1] * pr.atmosphere.haze);
      gl.uniform1f(hz.u.uSeed, this.seed % 1000);
      gl.bindVertexArray(this.quadVao);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    const common = (pg) => {
      const u = pg.u;
      gl.useProgram(pg.p);
      gl.uniformMatrix4fv(u.uVP, false, vp);
      if (u.uEye) gl.uniform3fv(u.uEye, eye);
      if (u.uViewport) gl.uniform2f(u.uViewport, w, h);
      if (u.uDpr) gl.uniform1f(u.uDpr, dpr);
      if (u.uStyles) { gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.styleTex); gl.uniform1i(u.uStyles, 0); }
      if (u.uPalette) gl.uniform3fv(u.uPalette, pal.tones.flat());
      if (u.uCertColor) gl.uniform3fv(u.uCertColor, [0.85, 0.97, 1.0, 0.45, 1.0, 0.62, 1.0, 0.72, 0.3, 0.95, 0.42, 0.95]);
      if (u.uMode) gl.uniform1f(u.uMode, mode === "provenance" ? 1 : 0);
      if (u.uBuild) gl.uniform1f(u.uBuild, s.build);
      if (u.uTime) gl.uniform1f(u.uTime, this.opt.reduced ? 0 : t);
      if (u.uEvent) gl.uniform4fv(u.uEvent, s.event);
      if (u.uEventP) gl.uniform4fv(u.uEventP, s.eventP);
      if (u.uBounds) gl.uniform4f(u.uBounds, this.C[0], this.C[1], this.C[2], this.R);
      if (u.uYRange) gl.uniform2f(u.uYRange, this.ground, this.top);
      if (u.uMotion) gl.uniformMatrix4fv(u.uMotion, false, mot.mats);
      if (u.uMotionGain) gl.uniform1fv(u.uMotionGain, mot.gains);
      if (u.uJoint) gl.uniformMatrix4fv(u.uJoint, false, joints);
      if (u.uGhost) gl.uniform1f(u.uGhost, s.ghost);
      if (u.uStabilise) gl.uniform1f(u.uStabilise, s.stabilise);
      if (u.uGlobalAlpha) gl.uniform1f(u.uGlobalAlpha, s.globalAlpha);
      if (u.uFogDensity) gl.uniform1f(u.uFogDensity, 0.55);
      if (u.uLife) gl.uniform1f(u.uLife, s.life);
      if (u.uBase) gl.uniform3fv(u.uBase, pal.base);
      if (u.uDashScale) gl.uniform1f(u.uDashScale, 34.0);
      return u;
    };

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    const xray = pr.occlusion === "xray";

    // fills: glass (and dark occluders) write depth, pushed back so edges on them stay in front
    if (this.fillCount) {
      common(this.programs.fill);
      gl.depthMask(xray);
      gl.depthFunc(gl.LEQUAL);
      gl.enable(gl.POLYGON_OFFSET_FILL);
      gl.polygonOffset(1.5, 2.0);
      gl.bindVertexArray(this.fillVao);
      gl.drawArrays(gl.TRIANGLES, 0, this.fillCount);
      gl.disable(gl.POLYGON_OFFSET_FILL);
      gl.depthMask(false);
    }

    // artwork faces (supplied bytes only), then the labels' text
    if (this.art.length) {
      const u = common(this.programs.art);
      const certLight = { verified: 1.0, user_supplied: 0.95, inferred: 0.78, decorative: 0.6 };
      const certColor = { verified: [0.85, 0.97, 1.0], user_supplied: [0.45, 1.0, 0.62], inferred: [1.0, 0.72, 0.3], decorative: [0.95, 0.42, 0.95] };
      // images and text sit a hair in front of their surface (and of a clear lid over them)
      gl.enable(gl.POLYGON_OFFSET_FILL);
      gl.polygonOffset(-2.0, -4.0);
      for (const a of this.art) {
        if (!a.ready) continue;
        gl.uniform1f(u.uSlot, a.slot);
        gl.uniform1f(u.uJointArt, a.joint);
        gl.uniform1f(u.uPhaseArt, a.phase);
        gl.uniform2f(u.uMask, a.mask[0], a.mask[1]);
        const k = certLight[a.certainty] || 0.8, tint = mode === "provenance" ? certColor[a.certainty] || pal.tones[1] : pal.tones[1];
        gl.uniform4f(u.uText, tint[0] * k, tint[1] * k, tint[2] * k, a.text ? 1 : 0);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, a.tex); gl.uniform1i(u.uTex, 1);
        gl.depthFunc(gl.LEQUAL);
        gl.bindVertexArray(a.vao);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
      }
      gl.disable(gl.POLYGON_OFFSET_FILL);
    }

    // lines: the under-stroke ink, then light — in front of the glass, then (xray) faintly behind it
    const lu = common(this.programs.line);
    gl.bindVertexArray(this.lineVao);
    const total = this.allLines.length / 9;
    const passes = xray ? [[gl.LEQUAL, 1.0], [gl.GREATER, 0.24]] : [[gl.ALWAYS, 1.0]];
    for (const [fn, hidden] of passes) {
      gl.depthFunc(fn);
      gl.uniform1f(lu.uHidden, hidden);
      gl.uniform1f(lu.uInk, 1);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, total);
      gl.uniform1f(lu.uInk, 0);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, total);
    }

    // sprites
    if (this.pointCount && pr.atmosphere.motes > 0) {
      common(this.programs.point);
      gl.depthFunc(xray ? gl.LEQUAL : gl.ALWAYS);
      gl.bindVertexArray(this.pointVao);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.pointCount);
    }

    // dressing: scanlines and vignette over this viewport
    gl.disable(gl.DEPTH_TEST);
    if (!transparent) {
      const dr = this.programs.dress;
      gl.useProgram(dr.p);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.uniform2f(dr.u.uSize, w, h);
      gl.uniform1f(dr.u.uDpr, dpr);
      gl.uniform1f(dr.u.uScanlines, pr.atmosphere.scanlines ? 1 : 0);
      gl.uniform1f(dr.u.uVignette, pr.atmosphere.vignette ? 1 : 0);
      gl.uniform1f(dr.u.uVeil, 0);
      gl.bindVertexArray(this.quadVao);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    gl.bindVertexArray(null);
    gl.disable(gl.SCISSOR_TEST);
    if (opts.reduced !== undefined) { this.opt.reduced = reducedWas; this.schedule = this.buildSchedule(); }
    return { vp, rect, state: s };
  };

  // ------------------------------------------------------------------------- page
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  function boot() {
    const geo = window.HOLOGRAM_GEOMETRY;
    const q = new URLSearchParams(location.search);
    const prefersReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const opt = {
      t: q.has("t") ? parseFloat(q.get("t")) : null,
      view: q.get("view") || "hero",
      reduced: q.get("motion") === "reduced" || (prefersReduced && q.get("motion") !== "full"),
      mode: q.get("mode") === "provenance" ? "provenance" : "light",
      ui: q.get("ui") !== "0", labels: q.get("labels") === "1", caption: q.get("caption") !== "0",
      sheet: q.get("sheet"), fps: q.has("fps") ? parseInt(q.get("fps"), 10) : 30, capture: q.get("capture") === "1",
      open: q.has("open") ? Math.max(0, Math.min(1, parseFloat(q.get("open")) || 0)) : null,
      shift: q.has("shift") ? q.get("shift").split(",").map((x) => Math.max(-0.9, Math.min(0.9, parseFloat(x) || 0))).concat([0]).slice(0, 2) : null,
      zoom: q.has("zoom") ? Math.max(0.3, Math.min(4, parseFloat(q.get("zoom")) || 1)) : 1,
      palette: q.get("palette"), identity: q.get("identity"),
      // camera=still: the view's own fitted framing, no tour, drift or breathing (the review's hero)
      freezeCamera: q.get("camera") === "still",
    };
    const stage = document.getElementById("stage");
    const canvas = document.getElementById("holo");
    const overlay = document.getElementById("overlay");
    let holo;
    try { holo = new Hologram(canvas, geo, opt); }
    catch (err) { document.body.setAttribute("data-error", String(err.message || err)); overlay.appendChild(el("pre", "error", String(err.message || err))); window.HOLO = { ready: Promise.reject(err) }; return; }
    holo.dpr = Math.min(2, window.devicePixelRatio || 1);
    const resize = () => {
      const r = stage.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(r.width * holo.dpr)); canvas.height = Math.max(1, Math.round(r.height * holo.dpr));
    };
    resize();

    // caption: what this is and how much of it is evidence (never implies exact accuracy)
    const subj = geo.subject;
    const accuracy = { generic: "GENERIC RECONSTRUCTION", approximate: "APPROXIMATE RECONSTRUCTION", documented: "DOCUMENTED RECONSTRUCTION" }[subj.accuracy];
    const caption = el("div", "caption");
    caption.appendChild(el("div", "title", geo.title));
    caption.appendChild(el("div", "meta", [accuracy, subj.synthetic ? "SYNTHETIC EXAMPLE" : null, geo.counts.lines + " LINES"].filter(Boolean).join(" · ")));
    if ((geo.provenance.assets || []).some((a) => a.provenance === "generated-decorative")) caption.appendChild(el("div", "meta warn", "ARTWORK: GENERATED DECORATION, NOT AUTHENTIC"));
    // terrain says how its relief is known, at what scale, and whose data it is
    const relief = geo.parts.find((p) => p.shape === "terrain");
    if (relief) {
      const measured = relief.certainty === "verified" || relief.certainty === "user_supplied";
      const fact = (k) => ((geo.provenance.facts || []).find((f) => f.key === k) || {}).value;
      const ex = fact("terrain.vertical_exaggeration");
      caption.appendChild(el("div", "meta", [measured ? "MEASURED TERRAIN" : "SKETCHED TERRAIN", fact("terrain.scale"),
        ex && ex !== 1 ? "HEIGHTS ×" + ex : null].filter(Boolean).join(" · ")));
      (geo.provenance.sources || []).filter((s) => s.kind === "dataset").forEach((s) => caption.appendChild(el("div", "meta", "DATA: " + s.title)));
    }
    // a globe says the same of its coastlines
    const coast = !relief && geo.parts.find((p) => p.shape === "globe" && p.role === "identity");
    if (coast) {
      const measured = coast.certainty === "verified" || coast.certainty === "user_supplied";
      const scale = ((geo.provenance.facts || []).find((f) => f.key === "globe.scale") || {}).value;
      caption.appendChild(el("div", "meta", [measured ? "MEASURED COASTLINES" : "SKETCHED COASTLINES", scale].filter(Boolean).join(" · ")));
      (geo.provenance.sources || []).filter((s) => s.kind === "dataset").forEach((s) => caption.appendChild(el("div", "meta", "DATA: " + s.title)));
    }
    if (!opt.caption || opt.sheet) caption.style.display = "none";
    overlay.appendChild(caption);
    const legend = el("div", "legend");
    [["verified", "VERIFIED"], ["user_supplied", "USER-SUPPLIED"], ["inferred", "INFERRED"], ["decorative", "DECORATIVE"]].forEach(([k, label]) => {
      const row = el("div", "row " + k); row.appendChild(el("span", "swatch")); row.appendChild(el("span", "", label)); legend.appendChild(row);
    });
    overlay.appendChild(legend);
    const help = el("div", "help", "drag orbit · wheel zoom · 1–6 views · R replay · M motion · P provenance · L labels · space pause");
    overlay.appendChild(help);
    const labels = el("div", "labels"); overlay.appendChild(labels);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("class", "leaders"); overlay.appendChild(svg);
    const sheetCaps = el("div", "sheetcaps"); overlay.appendChild(sheetCaps);
    const setUi = () => {
      document.body.classList.toggle("noui", !opt.ui);
      legend.style.display = opt.mode === "provenance" ? "block" : "none";
      help.style.display = opt.ui && !opt.capture ? "block" : "none";
    };
    setUi();

    let clock0 = performance.now(), paused = false, pausedAt = 0, frozen = opt.t;
    const now = () => frozen !== null ? frozen : paused ? pausedAt : (performance.now() - clock0) / 1000;

    function placeLabels(vp, rect) {
      labels.textContent = ""; svg.textContent = "";
      if (!opt.labels || opt.sheet) return;
      const cw = canvas.width / holo.dpr, ch = canvas.height / holo.dpr;
      svg.setAttribute("viewBox", "0 0 " + cw + " " + ch);
      const placed = [];
      const free = (x, y, w) => !placed.some((r) => x < r[0] + r[2] + 8 && x + w + 8 > r[0] && Math.abs(y - r[1]) < 22);
      (geo.annotations || []).forEach((a, i) => {
        let anchor = a.anchor;
        if (a.joint >= 0 && holo.lastJoints) {  // follow the part as it opens
          const m = holo.lastJoints.subarray(a.joint * 16, a.joint * 16 + 16), q = anchor;
          anchor = [0, 1, 2].map((r) => m[r] * q[0] + m[4 + r] * q[1] + m[8 + r] * q[2] + m[12 + r]);
        }
        const p = project(vp, anchor);
        if (!p || p[2] <= 0) return;
        const sx = (p[0] * 0.5 + 0.5) * cw, sy = (1 - (p[1] * 0.5 + 0.5)) * ch;
        // to the side away from the object's centre, lifted, then nudged until it overlaps no other label
        const c = project(vp, holo.C), right = !c || sx >= (c[0] * 0.5 + 0.5) * cw;
        const w = 9 + 6.6 * a.text.length;
        let lx = sx + (right ? 70 : -70), ly = sy - 40;
        for (let k = 0; k < 12 && !free(right ? lx : lx - w, ly, w); k++) ly -= 24;
        placed.push([right ? lx : lx - w, ly, w]);
        const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
        line.setAttribute("points", sx + "," + sy + " " + lx + "," + ly);
        svg.appendChild(line);
        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("cx", sx); dot.setAttribute("cy", sy); dot.setAttribute("r", 2.2); svg.appendChild(dot);
        const tag = el("div", "label " + a.certainty, a.text);
        tag.style.left = lx + "px"; tag.style.top = ly + "px";
        if (!right) tag.classList.add("left");
        labels.appendChild(tag);
      });
    }

    function sheetCells(kind) {
      const at = holo.assemblyTimes(), first = holo.schedule[0];
      const end = at.end;
      if (kind === "views") return ["hero", "front", "side", "back", "top", "three-quarter"].map((v) => ({ label: v.toUpperCase(), t: end + 0.01, view: v, reduced: true }));
      if (kind === "assembly") {
        const ts = end > 0 ? [0.05, 0.4, 0.75].map((k) => k * at.ghost).concat([0.1, 0.25, 0.45, 0.65, 0.85].map((k) => at.ghost + at.collapse + k * at.build)).concat([at.ghost + at.collapse + at.build + 0.2, end + 0.3]) : [0];
        return ts.slice(at.ghost ? 0 : 3).map((t) => ({ label: "T " + t.toFixed(2) + " S", t, view: "hero", freezeCamera: true }));
      }
      if (kind === "life") {
        const evs = holo.schedule.slice(0, 6);
        return evs.length ? evs.map((e) => ({ label: e.kind.toUpperCase() + " " + (e.t0 + e.dur * 0.45).toFixed(1) + " S", t: e.t0 + e.dur * 0.45, view: "hero", freezeCamera: true }))
                          : [{ label: "LIFE OFF", t: end + 1, view: "hero" }];
      }
      if (kind === "motion") { const op = holo.openTimes(), span = Math.max(7.5, op.end - end + 1.5);
        return [0, 0.2, 0.4, 0.6, 0.8, 1].map((k) => ({ label: "MOTION " + (end + k * span).toFixed(1) + " S", t: end + k * span, view: "hero" })); }
      if (kind === "provenance") return ["hero", "front", "side"].map((v) => ({ label: "PROVENANCE " + v.toUpperCase(), t: end + 0.01, view: v, reduced: true, mode: "provenance" }));
      if (kind === "tour") return (geo.animation.camera.tour || []).map((s) => ({ label: "TOUR " + s.view.toUpperCase() + " " + (s.at + (s.fly || 2.2)).toFixed(1) + " S", t: s.at + (s.fly || 2.2) + 0.05, view: "hero" }));
      return [];
    }

    function renderSheet(kind) {
      const cells = kind === "all" ? [].concat(sheetCells("assembly").slice(0, 4), sheetCells("views").slice(0, 4), sheetCells("life").slice(0, 2), sheetCells("provenance").slice(0, 2)) : sheetCells(kind);
      const n = cells.length, cols = n <= 4 ? 2 : 3, rows = Math.ceil(n / cols);
      const W = canvas.width, H = canvas.height, cw = Math.floor(W / cols), chh = Math.floor(H / rows);
      sheetCaps.textContent = "";
      const held = holo.opt.freezeCamera;
      cells.forEach((c, i) => {
        const col = i % cols, row = Math.floor(i / cols);
        holo.opt.freezeCamera = !!c.freezeCamera;
        holo.draw(c.t, [col * cw + 1, H - (row + 1) * chh + 1, cw - 2, chh - 2], c.view, { view: c.view, reduced: c.reduced, mode: c.mode });
        const cap = el("div", "cell", c.label);
        cap.style.left = (col * cw / holo.dpr + 10) + "px"; cap.style.top = (row * chh / holo.dpr + 8) + "px";
        sheetCaps.appendChild(cap);
      });
      holo.opt.freezeCamera = held;
      const head = el("div", "sheethead", geo.title + " — " + kind.toUpperCase() + " · " + accuracy + (subj.synthetic ? " · SYNTHETIC" : ""));
      sheetCaps.appendChild(head);
    }

    function frame() {
      const t = now();
      if (opt.sheet) { renderSheet(opt.sheet); return; }
      const out = holo.draw(t, [0, 0, canvas.width, canvas.height], opt.view, {});
      placeLabels(out.vp, out.rect);
    }

    // interaction
    let drag = null, lastInput = -1e9;
    canvas.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId);
      if (!holo.userCamera) holo.userCamera = holo.cameraAt(now(), holo.cameraFor(opt.view)); });
    canvas.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const c = holo.userCamera;
      c.yaw -= (e.clientX - drag.x) * 0.35; c.pitch = Math.max(-80, Math.min(85, c.pitch + (e.clientY - drag.y) * 0.3));
      drag = { x: e.clientX, y: e.clientY }; lastInput = performance.now(); kick();
    });
    canvas.addEventListener("pointerup", () => { drag = null; });
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (!holo.userCamera) holo.userCamera = holo.cameraAt(now(), holo.cameraFor(opt.view));
      holo.userCamera.dist *= Math.exp(e.deltaY * 0.0012); lastInput = performance.now(); kick();
    }, { passive: false });
    window.addEventListener("keydown", (e) => {
      const views = ["hero", "front", "side", "back", "top", "three-quarter"];
      if (e.key >= "1" && e.key <= "6") { opt.view = views[+e.key - 1]; holo.userCamera = null; }
      else if (e.key === "r" || e.key === "R") { clock0 = performance.now(); frozen = null; paused = false; holo.userCamera = null; }
      else if (e.key === "m" || e.key === "M") { opt.reduced = !opt.reduced; holo.opt.reduced = opt.reduced; holo.schedule = holo.buildSchedule(); }
      else if (e.key === "p" || e.key === "P") { opt.mode = opt.mode === "provenance" ? "light" : "provenance"; holo.opt.mode = opt.mode; setUi(); }
      else if (e.key === "l" || e.key === "L") { opt.labels = !opt.labels; }
      else if (e.key === " ") { if (paused) { clock0 += performance.now() - pausedStamp; paused = false; } else { pausedAt = now(); pausedStamp = performance.now(); paused = true; } e.preventDefault(); }
      else return;
      kick();
    });
    let pausedStamp = 0;
    // after a while untouched the presentation returns to its own camera
    setInterval(() => { if (holo.userCamera && performance.now() - lastInput > 25000) { holo.userCamera = null; kick(); } }, 2000);

    let raf = 0, lastFrame = 0, running = false;
    function loop(ts) {
      raf = 0;
      const interval = opt.fps > 0 ? 1000 / opt.fps : 0;
      if (ts - lastFrame >= interval - 1) { lastFrame = ts; frame(); }
      const still = frozen !== null || paused || (opt.reduced && !holo.userCamera);
      if (!still && !document.hidden) raf = requestAnimationFrame(loop); else running = false;
    }
    function kick() { if (!raf) { running = true; raf = requestAnimationFrame(loop); } }
    window.addEventListener("resize", () => { resize(); kick(); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });

    const artLoads = holo.art.map((a) => a.loading).filter(Boolean);
    const ready = Promise.all(artLoads).then(() => { frame(); kick(); document.body.setAttribute("data-ready", "1"); });
    window.HOLO = {
      ready, hologram: holo,
      renderAt(t, o) { o = o || {}; frozen = t; if (o.view) { opt.view = o.view; holo.userCamera = null; } if (o.mode) { opt.mode = o.mode; holo.opt.mode = o.mode; setUi(); }
        if (o.reduced !== undefined) { opt.reduced = o.reduced; holo.opt.reduced = o.reduced; holo.schedule = holo.buildSchedule(); }
        if (o.sheet !== undefined) opt.sheet = o.sheet;
        if (o.open !== undefined) { opt.open = o.open; holo.opt.open = o.open; }
        frame(); return true; },
      camera() { const c = holo.lastCamera; return c ? { target: c.target, yaw: c.yaw, pitch: c.pitch, dist: c.dist } : null; },
      fitted(view) { const c = holo.cameraFor(view || "hero"); return { target: c.target, yaw: c.yaw, pitch: c.pitch, dist: c.dist }; },
      timeline() { const op = holo.openTimes(); return { assembly: holo.assemblyTimes(), open: op, settled: Math.max(holo.assemblyTimes().end, op.end), events: holo.schedule.slice(0, 24) }; },
    };
  }

  window.HologramViewer = { Hologram, boot, PALETTES };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
