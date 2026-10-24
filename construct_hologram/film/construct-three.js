// construct-three: draws a compiled Construct geometry (format "construct-geometry" v2) inside a three.js scene,
// so a construct lives in a film's 3D space with real depth, the film's camera, motion blur and light. An optional
// extra for filmmakers: Construct itself does not need it, and it needs three.js (an ES module import of "three").
//
//   const c = await loadConstruct(url, { palette, scale, gain, fillAlpha });
//   scene.add(c.group);
//   c.update({ build, time, energy, high, voice });   // every sub-frame
//
// url    a geometry.json written by `construct build` (beside construct.html).
// palette  eight colours for the tone slots; the default is the house palette (HOUSE_TONES, Measured Light).
//        ALBUM_TONES is an optional, warmer alternative; any eight colours work.
// build  0..1 assembly progress (beyond 1: complete). The host decides how long it takes and how it moves with the
//        music; makeBuildCurve() below gives a curve whose speed follows the music's energy and ends at a chosen time.
// time   seconds, for the construct's own part motion (spin, swing, bob, pulse).
// energy, high, voice  0..1 audio features from `construct audio`: line glow breathes with energy, a fine
//        shimmer follows high, and the build front flares while the voice is present.
// Lines are screen-space quads (true width in pixels, soft glow), depth-tested against the construct's own dark
// fills; what the fills hide is drawn again faintly ("x-ray"), as the Construct viewer does.
import * as THREE from "three";

// the eight tone slots: accent, bright, hairline, structure, dust, identity, data, faint (sRGB; converted to linear)
// the house palette, as the Construct viewer draws it
export const HOUSE_TONES = ["#d16bd0", "#f6eaff", "#eadcf3", "#b7a4c8", "#9682d7", "#eadcf3", "#8fd3ff", "#6f6080"];
// an optional, warmer palette (made for an album film); pass it as { palette: ALBUM_TONES }
export const ALBUM_TONES = ["#E1AAB0", "#F4ECE6", "#D9C9D6", "#B9A7C9", "#9C86B8", "#F0DCDF", "#F6E7C8", "#6F6489"];

export async function loadConstruct(url, opt = {}) {
  const g = await (await fetch(url)).json();
  const tones = (opt.palette || HOUSE_TONES).map((h) => new THREE.Color(h).convertSRGBToLinear());
  const S = g.styles, nMot = Math.min(32, g.motions.length);
  const group = new THREE.Group(); group.name = g.id;
  const mats = [];
  const common = {
    uBuild: { value: 0 }, uTones: { value: tones.map((c) => new THREE.Vector3(c.r, c.g, c.b)) }, uRes: { value: new THREE.Vector2(1920, 1080) },
    uEnergy: { value: 0 }, uHigh: { value: 0 }, uVoice: { value: 0 }, uTime: { value: 0 }, uGain: { value: opt.gain ?? 1 },
    uFillA: { value: opt.fillAlpha ?? .55 },   // 1: the fills are opaque, so the object blocks the stars behind it
    uM: { value: Array.from({ length: 32 }, () => new THREE.Matrix4()) }, uPulse: { value: new Float32Array(32).fill(1) },
  };
  const MOTION_GLSL = `
    uniform mat4 uM[32]; uniform float uPulse[32];
    vec3 moved(vec3 p, float slot){ int s = int(slot); return s < 0 ? p : (uM[s] * vec4(p, 1.)).xyz; }
    float pulse(float slot){ int s = int(slot); return s < 0 ? 1. : uPulse[s]; }`;
  const TONE_GLSL = `uniform vec3 uTones[8]; vec3 tone(float t){ int i = int(t); return uTones[i]; }`;

  // ---------------------------------------------------------------- fills: dark glass that hides what is behind it
  if (g.fills.length) {
    const n = g.fills.length / 5, pos = new Float32Array(n * 3), aux = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { const o = i * 5, st = S[g.fills[o + 3]];
      pos.set([g.fills[o], g.fills[o + 1], g.fills[o + 2]], i * 3); aux.set([st[0], st[1], g.fills[o + 4], st[7]], i * 4); }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3)); geo.setAttribute("aux", new THREE.BufferAttribute(aux, 4));
    const m = new THREE.ShaderMaterial({ uniforms: common, transparent: true, depthWrite: true, side: THREE.DoubleSide, blending: THREE.NormalBlending,
      vertexShader: `attribute vec4 aux; varying float vPh, vA; varying vec3 vW; ${MOTION_GLSL}
        void main(){ vPh = aux.z; vA = aux.y; vec3 p = moved(position, aux.w); vW = (modelMatrix * vec4(p, 1.)).xyz; gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.); }`,
      fragmentShader: `uniform float uBuild, uGain, uFillA; varying float vPh, vA; varying vec3 vW;
        void main(){ if (vPh > uBuild + .0005) discard; float r = smoothstep(vPh, vPh + .06, uBuild);
          gl_FragColor = vec4(vec3(.010, .008, .03) * uGain * (1. - uFillA * .9), uFillA * r); }` });
    const mesh = new THREE.Mesh(geo, m); mesh.renderOrder = 1; mesh.frustumCulled = false; group.add(mesh); mats.push(m);
  }

  // ---------------------------------------------------------------- lines: instanced screen-space quads
  const nl = g.lines.length / 9;
  const quad = new THREE.InstancedBufferGeometry();
  quad.setAttribute("position", new THREE.BufferAttribute(new Float32Array([0, -1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0]), 3)); quad.setIndex([0, 1, 2, 0, 2, 3]);
  const A = new Float32Array(nl * 3), B = new Float32Array(nl * 3), P = new Float32Array(nl * 2), ST = new Float32Array(nl * 4), EX = new Float32Array(nl * 4);
  for (let i = 0; i < nl; i++) { const o = i * 9, st = S[g.lines[o + 6]];
    A.set([g.lines[o], g.lines[o + 1], g.lines[o + 2]], i * 3); B.set([g.lines[o + 3], g.lines[o + 4], g.lines[o + 5]], i * 3);
    P.set([g.lines[o + 7], g.lines[o + 8]], i * 2); ST.set([st[0], st[1], st[2], st[3]], i * 4); EX.set([st[4], st[5], st[7], ((i * 2654435761) % 4294967296) / 4294967296], i * 4); }  // a fixed seed per line: re-renders match
  quad.setAttribute("aA", new THREE.InstancedBufferAttribute(A, 3)); quad.setAttribute("aB", new THREE.InstancedBufferAttribute(B, 3));
  quad.setAttribute("aP", new THREE.InstancedBufferAttribute(P, 2)); quad.setAttribute("aS", new THREE.InstancedBufferAttribute(ST, 4)); quad.setAttribute("aX", new THREE.InstancedBufferAttribute(EX, 4));
  quad.instanceCount = nl;
  const lineMat = (xray) => new THREE.ShaderMaterial({ uniforms: Object.assign({ uX: { value: xray ? 1 : 0 } }, common), transparent: true, depthWrite: false,
    depthFunc: xray ? THREE.GreaterDepth : THREE.LessEqualDepth, blending: THREE.AdditiveBlending,
    vertexShader: `attribute vec3 aA, aB; attribute vec2 aP; attribute vec4 aS, aX; uniform vec2 uRes; uniform float uBuild;
      varying float vPh, vAcross, vW, vGlow; varying vec4 vS; varying float vDash, vAlong, vSeed; ${MOTION_GLSL}
      void main(){
        vec3 a = moved(aA, aX.z), b = moved(aB, aX.z);
        // a partly built line grows from its earlier end
        float k = aP.x == aP.y ? 1. : clamp((uBuild - aP.x) / (aP.y - aP.x), 0., 1.); b = mix(a, b, k);
        vec4 ca = projectionMatrix * modelViewMatrix * vec4(a, 1.), cb = projectionMatrix * modelViewMatrix * vec4(b, 1.);
        vec2 sa = ca.xy / ca.w * uRes * .5, sb = cb.xy / cb.w * uRes * .5, d = normalize(sb - sa + 1e-6), nrm = vec2(-d.y, d.x);
        float w = aS.z * 1.15 + aS.w * .9 + 1.6;                                    // core width plus room for the glow
        vec4 c = mix(ca, cb, position.x); c.xy += nrm * position.y * w / uRes * 2. * c.w;
        gl_Position = c; vAcross = position.y; vW = w; vGlow = aS.w / max(w, 1.); vS = aS; vPh = mix(aP.x, aP.y, position.x);
        vDash = aX.x; vAlong = length(sb - sa) * position.x; vSeed = aX.w;
      }`,
    fragmentShader: `uniform float uBuild, uEnergy, uHigh, uVoice, uTime, uGain, uX; varying float vPh, vAcross, vW, vGlow, vDash, vAlong, vSeed; varying vec4 vS; ${TONE_GLSL}
      void main(){
        if (vPh > uBuild + .0005) discard;
        if (vDash > .5 && mod(vAlong, vDash > 1.5 ? 6. : 11.) > (vDash > 1.5 ? 2. : 7.)) discard;
        float r = abs(vAcross) * vW, core = 1. - smoothstep(vS.z * .5, vS.z * .5 + 1., r), glow = exp(-r * r / max(1., vS.w * vS.w * .5)) * .35;
        float reveal = smoothstep(vPh - .0005, vPh + .035, uBuild);
        float tip = uBuild < 1. ? exp(-pow((uBuild - vPh) / .02, 2.)) * (1.2 + 2.5 * uVoice) : 0.;
        float shimmer = 1. + uHigh * .35 * sin(uTime * (6. + vSeed * 9.) + vSeed * 40.);
        float br = vS.y * (core + glow * (1. + 1.5 * uEnergy)) * reveal * shimmer * (.85 + .5 * uEnergy) + tip * core;
        vec3 col = mix(tone(vS.x), vec3(1., .96, .94), clamp(tip, 0., 1.));
        gl_FragColor = vec4(col * br * uGain * (uX > .5 ? .16 : 1.), 1.);
      }` });
  for (const x of [false, true]) { const m = lineMat(x); mats.push(m); const mesh = new THREE.Mesh(quad, m); mesh.frustumCulled = false; mesh.renderOrder = 2; group.add(mesh); }

  // ---------------------------------------------------------------- points
  if (g.points.length) {
    const n = g.points.length / 7, pos = new Float32Array(n * 3), aux = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { const o = i * 7, st = S[g.points[o + 4]]; pos.set([g.points[o], g.points[o + 1], g.points[o + 2]], i * 3);
      aux.set([g.points[o + 3], st[0], g.points[o + 6], st[7]], i * 4); }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3)); geo.setAttribute("aux", new THREE.BufferAttribute(aux, 4));
    const m = new THREE.ShaderMaterial({ uniforms: common, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `attribute vec4 aux; varying float vPh, vT, vP; ${MOTION_GLSL}
        void main(){ vPh = aux.z; vT = aux.y; vP = pulse(aux.w); vec3 p = moved(position, aux.w); gl_PointSize = aux.x * 2. + 4.; gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.); }`,
      fragmentShader: `uniform float uBuild, uEnergy, uGain; varying float vPh, vT, vP; ${TONE_GLSL}
        void main(){ if (vPh > uBuild + .0005) discard; float r = length(gl_PointCoord - .5) * 2.; float a = exp(-r * r * 5.) * (1. - smoothstep(.8, 1., r));
          gl_FragColor = vec4(tone(vT) * a * vP * (.7 + .5 * uEnergy) * uGain * smoothstep(vPh, vPh + .05, uBuild), 1.); }` });
    const pts = new THREE.Points(geo, m); pts.frustumCulled = false; pts.renderOrder = 3; group.add(pts); mats.push(m);
  }
  group.scale.setScalar(opt.scale || 1);

  // ---------------------------------------------------------------- part motion (the contract's periodic motions)
  const M = new THREE.Matrix4(), T1 = new THREE.Matrix4(), T2 = new THREE.Matrix4(), R = new THREE.Matrix4();
  function motions(t) {
    for (let i = 0; i < nMot; i++) { const m = g.motions[i], piv = new THREE.Vector3(...m.pivot), ax = new THREE.Vector3(...m.axis).normalize();
      const ph = 2 * Math.PI * (t / Math.max(.001, m.period || 1) + (m.phase || 0)); M.identity(); let p = 1;
      if (m.type === "spin") { R.makeRotationAxis(ax, m.rpm * 2 * Math.PI / 60 * t + 2 * Math.PI * (m.phase || 0)); M.multiplyMatrices(T1.makeTranslation(piv.x, piv.y, piv.z), R).multiply(T2.makeTranslation(-piv.x, -piv.y, -piv.z)); }
      else if (m.type === "swing") { R.makeRotationAxis(ax, THREE.MathUtils.degToRad(m.degrees) * Math.sin(ph)); M.multiplyMatrices(T1.makeTranslation(piv.x, piv.y, piv.z), R).multiply(T2.makeTranslation(-piv.x, -piv.y, -piv.z)); }
      else if (m.type === "bob") { const d = m.distance * Math.sin(ph); M.makeTranslation(ax.x * d, ax.y * d, ax.z * d); }
      else if (m.type === "pulse") p = 1 + m.amount * (1 + Math.sin(ph)) / 2;
      common.uM.value[i].copy(M); common.uPulse.value[i] = p; }
  }
  return {
    group, geometry: g, bounds: g.bounds,
    update({ build = 2, time = 0, energy = 0, high = 0, voice = 0, gain } = {}) {
      common.uBuild.value = build; common.uTime.value = time; common.uEnergy.value = energy; common.uHigh.value = high; common.uVoice.value = voice;
      if (gain !== undefined) common.uGain.value = gain; motions(time);
    },
    setResolution(w, h) { common.uRes.value.set(w, h); },
  };
}

// A long assembly whose speed follows the music: progress advances by (base + k·energy²) per frame and is normalised so
// it starts at t0 and completes exactly at t1 (seconds, track time). energy is the per-frame feature array at fps.
export function makeBuildCurve(energy, fps, t0, t1, k = 2.5, base = .35) {
  const i0 = Math.max(0, Math.round(t0 * fps)), i1 = Math.min(energy.length - 1, Math.round(t1 * fps)), acc = new Float32Array(energy.length);
  let s = 0; for (let i = 0; i < energy.length; i++) { if (i > i0 && i <= i1) s += base + k * energy[i] * energy[i]; acc[i] = s; }
  const total = acc[i1] || 1;
  return (t) => { const i = Math.round(t * fps); if (i <= i0) return 0; if (i >= i1) return 1.001; return acc[i] / total; };
}
