// ---------------------------------------------------------------------------
// Tiny isometric engine: orthographic camera, flat 3-tone shading, ink lines,
// boxes, prisms, cylinders, spheres, wires, planes for printed detail.
// World: centimetres, x forward, z up. The camera draws it mirrored (VR below), so on screen +y
// reads as the RIGHT of +x: name sides by what the viewer sees (movimiento.js: +y = 'der').
// ---------------------------------------------------------------------------
const INK = '#1d2033';
const AZ = Math.PI / 4, EL = Math.PI / 6;
const VR = [Math.sin(AZ), -Math.cos(AZ), 0];
const VU = [-Math.sin(EL) * Math.cos(AZ), -Math.sin(EL) * Math.sin(AZ), Math.cos(EL)];
const VC = [Math.cos(EL) * Math.cos(AZ), Math.cos(EL) * Math.sin(AZ), Math.sin(EL)];
const LT = (() => { const v = [-0.7, 0.15, 1.0]; const l = Math.hypot(...v); return v.map(a => a / l); })();
const SH = [0.62, -0.13];
let LWS = 1; // ink weight scale (set per frame from zoom) // floor shadow offset per cm of height (light travels +x, slight -y)

const dot3 = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const add3 = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub3 = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul3 = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
const easeOut = (t) => 1 - Math.pow(1 - clamp(t), 3);
const easeInOut = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const backOut = (t) => { t = clamp(t); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const depthOf = (p) => dot3(p, VC);

// ---- colour -------------------------------------------------------------
const _rgbCache = {};
function hexRgb(h) {
  if (_rgbCache[h]) return _rgbCache[h];
  const n = parseInt(h.slice(1), 16);
  return (_rgbCache[h] = [(n >> 16) & 255, (n >> 8) & 255, n & 255]);
}
function mixRgb(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function rgbCss(c, a = 1) { return a >= 1 ? `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})` : `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`; }
// shade value: 0.5 + 0.5 n.L ; top ~0.905, +y ~0.561, +x ~0.215
function toneRgb(m, s, steps) {
  const d = hexRgb(m.dark), md = hexRgb(m.mid), l = hexRgb(m.light);
  if (steps) s = Math.round(s * steps) / steps;
  if (s <= 0.215) return mixRgb(mixRgb(d, [10, 10, 25], 0.12), d, clamp((s - 0.0) / 0.215));
  if (s <= 0.561) return mixRgb(d, md, (s - 0.215) / 0.346);
  if (s <= 0.905) return mixRgb(md, l, (s - 0.561) / 0.344);
  return l;
}
function shadeOf(n) { return 0.5 + 0.5 * dot3(n, LT); }
function tone(m, n, alpha = 1, steps) { return rgbCss(toneRgb(m, shadeOf(n), steps), alpha); }

// ---- camera ---------------------------------------------------------------
class Cam {
  constructor(zoom, target, cx, cy) {
    this.z = zoom;
    this.ox = cx - zoom * dot3(target, VR);
    this.oy = cy + zoom * dot3(target, VU);
  }
  p(q) { return [this.ox + this.z * (q[0] * VR[0] + q[1] * VR[1]), this.oy - this.z * (q[0] * VU[0] + q[1] * VU[1] + q[2] * VU[2])]; }
}

// ---- transforms (yaw about z + translation) --------------------------------
class Xf {
  constructor(x = 0, y = 0, z = 0, yaw = 0) { this.x = x; this.y = y; this.z = z; this.c = Math.cos(yaw); this.s = Math.sin(yaw); this.yaw = yaw; }
  p(q) { return [this.c * q[0] - this.s * q[1] + this.x, this.s * q[0] + this.c * q[1] + this.y, q[2] + this.z]; }
  n(v) { return [this.c * v[0] - this.s * v[1], this.s * v[0] + this.c * v[1], v[2]]; }
  lift(dz) { const o = new Xf(this.x, this.y, this.z + dz, this.yaw); return o; }
}

// ---- drawing context ---------------------------------------------------------
// G = { ctx, cam, k (backing scale), alpha }
function pathPts(ctx, pts) { ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.closePath(); }
function inkW(G, w) { return w; }
function fillStroke(G, pts, fill, lw = 1.7, ink = INK) {
  const c = G.ctx; pathPts(c, pts);
  if (fill) { c.fillStyle = fill; c.fill(); }
  if (lw > 0) { c.lineWidth = lw * LWS; c.strokeStyle = ink; c.lineJoin = 'round'; c.stroke(); }
}
function hull(pts) {
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (p.length < 3) return p;
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const q of p) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (let i = p.length - 1; i >= 0; i--) { const q = p[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  up.pop(); lo.pop(); return lo.concat(up);
}

// Plane: draw 2D detail in local (u,v) cm coordinates mapped onto a 3D plane.
function onPlane(G, origin, u, v, fn) {
  const c = G.ctx, cam = G.cam, k = G.k;
  const O = cam.p(origin), A = cam.p(add3(origin, u)), B = cam.p(add3(origin, v));
  c.save();
  c.setTransform(k * (A[0] - O[0]), k * (A[1] - O[1]), k * (B[0] - O[0]), k * (B[1] - O[1]), k * O[0], k * O[1]);
  fn(c, (w, color = INK) => { c.save(); c.setTransform(k, 0, 0, k, 0, 0); c.lineWidth = w * LWS; c.strokeStyle = color; c.lineJoin = 'round'; c.lineCap = 'round'; c.stroke(); c.restore(); });
  c.restore();
}

// ---- primitives --------------------------------------------------------------
// Box in local coords [a,b], transformed by xf. opts: top(c,sp), px(c,sp), py(c,sp), ny, nx, lw, alpha
function drawBox(G, xf, a, b, m, o = {}) {
  const P = (x, y, z) => G.cam.p(xf.p([x, y, z]));
  const [x0, y0, z0] = a, [x1, y1, z1] = b;
  const alpha = o.alpha ?? 1, lw = o.lw ?? 1.7;
  const faces = [
    { n: [1, 0, 0], q: [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]], d: 'px' },
    { n: [-1, 0, 0], q: [[x0, y1, z0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1]], d: 'nx' },
    { n: [0, 1, 0], q: [[x1, y1, z0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1]], d: 'py' },
    { n: [0, -1, 0], q: [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]], d: 'ny' },
  ];
  for (const f of faces) {
    const nw = xf.n(f.n);
    if (dot3(nw, VC) <= 0.001) continue;
    const pts = f.q.map(q => P(...q));
    fillStroke(G, pts, tone(o.side || m, nw, alpha), lw);
    if (o[f.d]) facePlane(G, xf, f.d, a, b, o[f.d]);
  }
  if (o.noTop) return;
  const top = [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]].map(q => P(...q));
  fillStroke(G, top, tone(o.topM || m, [0, 0, 1], alpha), lw);
  if (o.top) onPlane(G, xf.p([x0, y0, z1]), xf.n([1, 0, 0]), xf.n([0, 1, 0]), o.top);
}
// face planes oriented so text reads left-to-right on screen, v going down
function facePlane(G, xf, which, a, b, fn) {
  const [x0, y0, z0] = a, [x1, y1, z1] = b;
  if (which === 'px') onPlane(G, xf.p([x1, y1, z1]), xf.n([0, -1, 0]), [0, 0, -1], fn);
  else if (which === 'py') onPlane(G, xf.p([x0, y1, z1]), xf.n([1, 0, 0]), [0, 0, -1], fn);
  else if (which === 'nx') onPlane(G, xf.p([x0, y0, z1]), xf.n([0, 1, 0]), [0, 0, -1], fn);
  else if (which === 'ny') onPlane(G, xf.p([x1, y0, z1]), xf.n([-1, 0, 0]), [0, 0, -1], fn);
}

// rounded-rect plan
function rrPlan(x0, y0, x1, y1, r, seg = 5) {
  const pts = [];
  const rr = Array.isArray(r) ? r : [r, r, r, r]; // order: (x1,y0),(x1,y1),(x0,y1),(x0,y0)
  const cs = [[x1 - rr[0], y0 + rr[0], -Math.PI / 2, rr[0]], [x1 - rr[1], y1 - rr[1], 0, rr[1]], [x0 + rr[2], y1 - rr[2], Math.PI / 2, rr[2]], [x0 + rr[3], y0 + rr[3], Math.PI, rr[3]]];
  for (const [cx, cy, a0, R] of cs) for (let i = 0; i <= seg; i++) { const a = a0 + (i / seg) * Math.PI / 2; pts.push([cx + R * Math.cos(a), cy + R * Math.sin(a)]); }
  return pts;
}
// Extruded convex plan (CCW). opts: top(c, strokePx), alpha, lw
function drawPrism(G, xf, plan, z0, z1, m, o = {}) {
  const alpha = o.alpha ?? 1, lw = o.lw ?? 1.7;
  const n = plan.length, facets = [];
  const bot = plan.map(([x, y]) => G.cam.p(xf.p([x, y, z0])));
  const top = plan.map(([x, y]) => G.cam.p(xf.p([x, y, z1])));
  for (let i = 0; i < n; i++) {
    const a = plan[i], b = plan[(i + 1) % n];
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    const nw = xf.n([dy / L, -dx / L, 0]);
    if (dot3(nw, VC) <= 0) continue;
    facets.push({ pts: [bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]], nw });
  }
  const c = G.ctx;
  for (const f of facets) { const col = tone(o.side || m, f.nw, alpha); pathPts(c, f.pts); c.fillStyle = col; c.fill(); c.lineWidth = 0.6; c.strokeStyle = col; c.stroke(); }
  // silhouette
  const h = hull(bot.concat(top));
  if (lw > 0) { pathPts(c, h); c.lineWidth = lw * LWS * 1.3; c.strokeStyle = INK; c.lineJoin = 'round'; c.stroke(); }
  fillStroke(G, top, tone(o.topM || m, [0, 0, 1], alpha), lw);
  if (o.top) onPlane(G, xf.p([0, 0, z1]), xf.n([1, 0, 0]), xf.n([0, 1, 0]), o.top);
}

// Cylinder: centre c (local), axis 'x'|'y'|'z', radius r, length L.
function cylBasis(ax) {
  if (Array.isArray(ax)) { // any direction: A = axis, E1/E2 = perpendicular pair
    const A = mul3(ax, 1 / Math.hypot(...ax)), t = Math.abs(A[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
    const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    let E1 = cr(A, t); E1 = mul3(E1, 1 / Math.hypot(...E1));
    return [A, E1, cr(A, E1)];
  }
  if (ax === 'x') return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  if (ax === 'y') return [[0, 1, 0], [0, 0, 1], [1, 0, 0]];
  return [[0, 0, 1], [1, 0, 0], [0, 1, 0]];
}
function drawCyl(G, xf, c, ax, r, L, m, o = {}) {
  const [A, E1, E2] = cylBasis(ax);
  const seg = o.seg || 36, alpha = o.alpha ?? 1, lw = o.lw ?? 1.7, h = L / 2;
  const ring = (s) => { const out = []; for (let i = 0; i < seg; i++) { const ph = (i / seg) * Math.PI * 2; const q = add3(add3(c, mul3(A, s)), add3(mul3(E1, r * Math.cos(ph)), mul3(E2, r * Math.sin(ph)))); out.push(G.cam.p(xf.p(q))); } return out; };
  const r0 = ring(-h), r1 = ring(h);
  const cx = G.ctx;
  // side facets
  for (let i = 0; i < seg; i++) {
    const ph = ((i + 0.5) / seg) * Math.PI * 2;
    const nl = add3(mul3(E1, Math.cos(ph)), mul3(E2, Math.sin(ph)));
    const nw = xf.n(nl);
    if (dot3(nw, VC) <= -0.02) continue;
    const j = (i + 1) % seg;
    const col = tone(o.side || m, nw, alpha, o.steps ?? 7);
    pathPts(cx, [r0[i], r0[j], r1[j], r1[i]]); cx.fillStyle = col; cx.fill(); cx.lineWidth = 0.7; cx.strokeStyle = col; cx.stroke();
  }
  if (o.sideFx) o.sideFx(G, r0, r1, seg);
  const Aw = xf.n(A);
  const capVis = dot3(Aw, VC) >= 0 ? 1 : -1;
  const capPts = capVis > 0 ? r1 : r0;
  const hh = hull(r0.concat(r1));
  if (lw > 0) { pathPts(cx, hh); cx.lineWidth = lw * LWS * 1.3; cx.strokeStyle = INK; cx.lineJoin = 'round'; cx.stroke(); }
  if (Math.abs(dot3(Aw, VC)) > 0.02 && !o.noCap) {
    fillStroke(G, capPts, tone(o.cap || m, mul3(Aw, capVis), alpha), lw);
    if (o.capFx) {
      const origin = add3(c, mul3(A, h * capVis));
      // u along E1, v along E2 (flip for the back cap so the drawing is not mirrored)
      onPlane(G, xf.p(origin), xf.n(capVis > 0 ? E1 : mul3(E1, -1)), xf.n(E2), (cc, sp) => o.capFx(cc, sp, capVis));
    }
  }
  return { hull: hh, capVis };
}
function drawSphere(G, xf, c, r, m, o = {}) {
  const P = G.cam.p(xf.p(c)), R = r * G.cam.z, cx = G.ctx;
  cx.beginPath(); cx.arc(P[0], P[1], R, 0, Math.PI * 2); cx.fillStyle = rgbCss(hexRgb(m.mid)); cx.fill();
  cx.save(); cx.clip();
  cx.beginPath(); cx.arc(P[0] + R * 0.35, P[1] + R * 0.35, R * 1.05, 0, Math.PI * 2); cx.fillStyle = rgbCss(hexRgb(m.dark)); cx.fill();
  cx.beginPath(); cx.arc(P[0] - R * 0.18, P[1] - R * 0.18, R * 0.72, 0, Math.PI * 2); cx.fillStyle = rgbCss(hexRgb(m.mid)); cx.fill();
  cx.beginPath(); cx.arc(P[0] - R * 0.38, P[1] - R * 0.4, R * 0.22, 0, Math.PI * 2); cx.fillStyle = rgbCss(hexRgb(m.light)); cx.fill();
  cx.restore();
  cx.beginPath(); cx.arc(P[0], P[1], R, 0, Math.PI * 2); cx.lineWidth = (o.lw ?? 1.6) * LWS; cx.strokeStyle = INK; cx.stroke();
}

// Catmull-Rom through control points (local), returns world points
function splinePts(xf, cps, n = 10) {
  const out = [];
  const P = cps;
  for (let i = 0; i < P.length - 1; i++) {
    const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      const q = [0, 1, 2].map(j => 0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3));
      out.push(xf.p(q));
    }
  }
  out.push(xf.p(P[P.length - 1]));
  return out;
}
function drawWire(G, xf, cps, color, o = {}) {
  const pts = splinePts(xf, cps, o.n || 12);
  let k = pts.length;
  const prog = o.prog ?? 1;
  if (prog <= 0) return;
  if (prog < 1) k = Math.max(2, Math.ceil(pts.length * prog));
  const sp = pts.slice(0, k).map(q => G.cam.p(q));
  const c = G.ctx, w = Math.max(2.0, (o.w || 0.24) * G.cam.z);
  c.lineCap = 'round'; c.lineJoin = 'round';
  c.beginPath(); c.moveTo(sp[0][0], sp[0][1]); for (let i = 1; i < sp.length; i++) c.lineTo(sp[i][0], sp[i][1]);
  c.lineWidth = w + 2.8 * LWS; c.strokeStyle = INK; c.stroke();
  c.lineWidth = w; c.strokeStyle = color; c.stroke();
  if (w > 3) {
    c.save(); c.translate(-w * 0.18, -w * 0.22);
    c.lineWidth = Math.max(1, w * 0.28); c.strokeStyle = 'rgba(255,255,255,0.45)'; c.stroke(); c.restore();
  }
  if (o.glow) { c.lineWidth = w + 6; c.strokeStyle = o.glow; c.globalCompositeOperation = 'lighter'; c.stroke(); c.globalCompositeOperation = 'source-over'; }
  return sp;
}

// shadows: project world points to plane z=h, convex hull
function shadowPts(G, worldPts, h) {
  return hull(worldPts.map(q => { const d = q[2] - h; return G.cam.p([q[0] + SH[0] * d, q[1] + SH[1] * d, h]); }));
}
function boxCorners(xf, a, b) { const o = []; for (const x of [a[0], b[0]]) for (const y of [a[1], b[1]]) for (const z of [a[2], b[2]]) o.push(xf.p([x, y, z])); return o; }
function cylCorners(xf, c, ax, r, L, seg = 16) {
  const [A, E1, E2] = cylBasis(ax); const o = [];
  for (const s of [-L / 2, L / 2]) for (let i = 0; i < seg; i++) { const ph = (i / seg) * Math.PI * 2; o.push(xf.p(add3(add3(c, mul3(A, s)), add3(mul3(E1, r * Math.cos(ph)), mul3(E2, r * Math.sin(ph)))))); }
  return o;
}

// ellipse on a horizontal plane (world centre), radius rx along local x, ry along y
function floorEllipse(G, xf, c, rx, ry, seg = 48) {
  const out = []; for (let i = 0; i < seg; i++) { const a = (i / seg) * Math.PI * 2; out.push(G.cam.p(xf.p([c[0] + rx * Math.cos(a), c[1] + ry * Math.sin(a), c[2]]))); } return out;
}

// deterministic noise
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---- composition: place an asset (native origin O) at `at`, rotated `rot`, inside `parent`
function compose(parent, at = [0, 0, 0], rot = 0, O = [0, 0, 0]) {
  const c = Math.cos(rot), s = Math.sin(rot);
  const loc = [at[0] - (c * O[0] - s * O[1]), at[1] - (s * O[0] + c * O[1]), at[2] - O[2]];
  const w = parent.p(loc);
  return new Xf(w[0], w[1], w[2], parent.yaw + rot);
}

// ---- cones and surfaces of revolution (from Lab 03) -----------------------------------------
// Frustum along any axis: centre c (local), radius r0 at -L/2 and r1 at +L/2. opts like drawCyl (seg, lw, alpha, cap, noCap)
function drawFrustum(G, xf, c, ax, r0, r1, L, m, o = {}) {
  const [A, E1, E2] = cylBasis(ax), seg = o.seg || 32, alpha = o.alpha ?? 1, lw = o.lw ?? 1.7, h = L / 2, k = (r0 - r1) / L;
  const ring = (s, r) => { const out = []; for (let i = 0; i < seg; i++) { const ph = (i / seg) * Math.PI * 2; out.push(G.cam.p(xf.p(add3(add3(c, mul3(A, s)), add3(mul3(E1, r * Math.cos(ph)), mul3(E2, r * Math.sin(ph))))))); } return out; };
  const R0 = ring(-h, r0), R1 = ring(h, r1), cx = G.ctx;
  for (let i = 0; i < seg; i++) {
    const ph = ((i + 0.5) / seg) * Math.PI * 2, nr = add3(mul3(E1, Math.cos(ph)), mul3(E2, Math.sin(ph)));
    const nl = add3(nr, mul3(A, k)), nw = xf.n(mul3(nl, 1 / Math.hypot(...nl)));
    if (dot3(nw, VC) <= -0.02) continue;
    const j = (i + 1) % seg, col = tone(o.side || m, nw, alpha, o.steps ?? 7);
    pathPts(cx, [R0[i], R0[j], R1[j], R1[i]]); cx.fillStyle = col; cx.fill(); cx.lineWidth = 0.7; cx.strokeStyle = col; cx.stroke();
  }
  const hh = hull(R0.concat(R1));
  if (lw > 0) { pathPts(cx, hh); cx.lineWidth = lw * LWS * 1.3; cx.strokeStyle = INK; cx.lineJoin = 'round'; cx.stroke(); }
  const Aw = xf.n(A), d = dot3(Aw, VC);
  if (!o.noCap) {
    if (d > 0.02 && r1 > 0.002) fillStroke(G, R1, tone(o.cap || m, Aw, alpha), lw);
    else if (d < -0.02 && r0 > 0.002) fillStroke(G, R0, tone(o.cap || m, mul3(Aw, -1), alpha), lw);
  }
  return { hull: hh };
}
// Surface of revolution about a vertical axis through c (local): prof = [[dz, r], ...] with dz increasing.
// Lit from the left like everything else. o: {shine 0..1 (specular streak), glint (phase), lw, alpha, cap (draw the top disc)}
function drawRevol(G, xf, c, prof, m, o = {}) {
  const C = xf.p(c), cx = G.ctx, n = prof.length, Rn = [Math.SQRT1_2, -Math.SQRT1_2];
  const at = (z, r, ph) => G.cam.p([C[0] + r * Math.cos(ph), C[1] + r * Math.sin(ph), C[2] + z]);
  const PL = (3 * Math.PI) / 4, PR = -Math.PI / 4;                // screen-left and screen-right extremes of each ring
  const out = [];
  const [z0, r0] = prof[0], [zn, rn] = prof[n - 1];
  for (let i = 0; i <= 18; i++) out.push(at(z0, r0, PL + (PR - PL) * (i / 18)));            // bottom, front half
  for (let i = 1; i < n; i++) out.push(at(prof[i][0], prof[i][1], PR));                     // right side up
  for (let i = 1; i <= 18; i++) out.push(at(zn, rn, PR - Math.PI * (i / 18)));              // top, back half
  for (let i = n - 2; i > 0; i--) out.push(at(prof[i][0], prof[i][1], PL));                 // left side down
  const rmax = Math.max(...prof.map(p => p[1])), xl = G.cam.p([C[0] - Rn[0] * rmax, C[1] - Rn[1] * rmax, C[2]])[0], xr = 2 * G.cam.p(C)[0] - xl;
  const g = cx.createLinearGradient(xl, 0, xr, 0), a = o.alpha ?? 1;
  g.addColorStop(0, rgbCss(hexRgb(m.light), a)); g.addColorStop(0.45, rgbCss(hexRgb(m.mid), a)); g.addColorStop(1, rgbCss(hexRgb(m.dark), a));
  pathPts(cx, out); cx.fillStyle = g; cx.fill();
  if (o.cap && rn > 0.001) { const cap = []; for (let i = 0; i < 28; i++) cap.push(at(zn, rn, (i / 28) * Math.PI * 2)); pathPts(cx, cap); cx.fillStyle = rgbCss(hexRgb(m.light), a); cx.fill(); }
  const sh = o.shine ?? 0;
  if (sh > 0.01) {                                                  // specular streak, a little left of the front
    const ph = 1.75 + 0.18 * Math.sin(o.glint || 0);
    cx.save(); cx.lineCap = 'round'; cx.strokeStyle = `rgba(255,255,255,${0.85 * sh})`;
    cx.lineWidth = Math.max(1.2, 0.18 * rmax * G.cam.z);
    cx.beginPath(); prof.forEach(([z, r], i) => { const p = at(z, r * 0.92, ph); i ? cx.lineTo(p[0], p[1]) : cx.moveTo(p[0], p[1]); }); cx.stroke(); cx.restore();
  }
  if ((o.lw ?? 1.5) > 0) { pathPts(cx, out); cx.lineWidth = (o.lw ?? 1.5) * LWS; cx.strokeStyle = INK; cx.lineJoin = 'round'; cx.stroke(); }
  return out;
}
