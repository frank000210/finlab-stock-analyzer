// ---------------------------------------------------------------------------
// Materials (3 tones each: light top, mid left face, dark right face), wire colours,
// and helpers for printed detail on faces (text, circles, rects in face cm units).
// ---------------------------------------------------------------------------
const FONT_MONO = 'JetBrains Mono, monospace';
const M = {
  mat: { light: '#fbf8f1', mid: '#ece4d4', dark: '#d6ccb7' },
  acr: { light: '#ffa457', mid: '#f3832f', dark: '#c9611c' },      // orange acrylic
  yel: { light: '#ffdb5c', mid: '#f2bd2c', dark: '#c48d16' },      // TT gearbox
  can: { light: '#f6f7f9', mid: '#d7dbe1', dark: '#a7aebb' },
  tire: { light: '#535663', mid: '#33353f', dark: '#1d1e25' },
  hub: { light: '#ffe36b', mid: '#f6c62f', dark: '#cf9a18' },
  brass: { light: '#f6d77f', mid: '#dcb04a', dark: '#a8812a' },
  steel: { light: '#f1f3f6', mid: '#cdd2da', dark: '#959caa' },
  pcbB: { light: '#3f86ea', mid: '#2b68c9', dark: '#1d4b97' },     // UNO blue
  pcbR: { light: '#f0605f', mid: '#d24448', dark: '#a02f33' },     // L298N red
  pcbS: { light: '#3a9af2', mid: '#257bd6', dark: '#1a5aa2' },     // HC-SR04 blue
  pcbK: { light: '#3d4250', mid: '#2a2e38', dark: '#1b1e25' },     // black PCB (ESP32)
  pcbG: { light: '#3fbf7f', mid: '#2a9c63', dark: '#1d7448' },     // green PCB
  blk: { light: '#50535f', mid: '#363841', dark: '#23242b' },
  hs: { light: '#62677a', mid: '#3d4150', dark: '#272a35' },
  term: { light: '#55a0ff', mid: '#3a7fe0', dark: '#285db0' },
  bb: { light: '#fdfdf9', mid: '#e8e8e0', dark: '#c9c9bf' },
  cellA: { light: '#66dccd', mid: '#2fb8a7', dark: '#1e8c7f' },
  cellB: { light: '#a487ff', mid: '#7f5ff2', dark: '#5a3fc4' },
  red: { light: '#ff7070', mid: '#e5484d', dark: '#b3343a' },
  inner: { light: '#3b3d47', mid: '#2b2d35', dark: '#1d1e25' },
  box: { light: '#e9b77f', mid: '#d39b5d', dark: '#ad7841' },
  gold: { light: '#ffe58f', mid: '#e8bf4c', dark: '#b58c2a' },
  servo: { light: '#5aa2ff', mid: '#3a84ea', dark: '#2763bd' },    // SG90 blue
  white: { light: '#ffffff', mid: '#eceef2', dark: '#c9cdd6' },
  beige: { light: '#f3dfb5', mid: '#e2c894', dark: '#b99c64' },    // resistor body
  ledR: { light: '#ff8a8a', mid: '#ef4b4f', dark: '#b8272c' },
  ledG: { light: '#8af0a6', mid: '#33cc66', dark: '#1f9a49' },
  ledB: { light: '#8ab8ff', mid: '#3f7fff', dark: '#2a58c4' },
  ledY: { light: '#fff08a', mid: '#ffd23f', dark: '#c9a01d' },
  ledW: { light: '#ffffff', mid: '#e9edf5', dark: '#b8bfcc' },
};
const WIRE = { red: '#ef4b50', blk: '#2b2c33', yel: '#ffc928', grn: '#2fbf71', org: '#ff8a3d', pur: '#9b6be0', gry: '#aab0bb', wht: '#f5f5f2', brn: '#b06a3f', blu: '#3d84e6' };
// Spanish aliases used in demos
const ROJO = WIRE.red, NEGRO = WIRE.blk, AMARILLO = WIRE.yel, VERDE = WIRE.grn, NARANJA = WIRE.org, MORADO = WIRE.pur, GRIS = WIRE.gry, BLANCO = WIRE.wht, CAFE = WIRE.brn, AZUL = WIRE.blu;

function ptxt(c, s, x, y, size, color, weight = 700, align = 'left', rot = 0) {
  c.save(); c.translate(x, y); if (rot) c.rotate(rot);
  c.font = `${weight} ${size}px ${FONT_MONO}`; c.fillStyle = color; c.textAlign = align; c.textBaseline = 'middle';
  c.fillText(s, 0, 0); c.restore();
}
function pcirc(c, x, y, r) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); }
function prect(c, x, y, w, h, r = 0) { c.beginPath(); if (r) c.roundRect(x, y, w, h, r); else c.rect(x, y, w, h); }
function glowAt(c, x, y, r, rgba) { c.save(); c.globalCompositeOperation = 'lighter'; const g = c.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, rgba); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g; pcirc(c, x, y, r); c.fill(); c.restore(); }
function shadeHex(hex, k) { const c = mixRgb(hexRgb(hex), [10, 10, 25], k); return '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join(''); }
