// Hip roofs for the surveyed buildings: the straight skeleton of each footprint (CGAL, via the `straight-skeleton` 2.0.1
// Wasm build, which only runs in a browser, so this drives headless Chromium with Playwright). The DBT heights stop at
// the eaves; the page lifts each skeleton vertex by its distance from the eaves line (capped) to make a pitched roof, for
// the buildings it gives a tiled roof. Stored as data.roofs[index of b] = [interior vertices (x dm, y dm, t dm), faces].
// Faces index the footprint's vertices first (outer ring CCW, then holes CW, as rewritten into b here), then the interior.
// usage (after landmarks.py): npm i straight-skeleton@2.0.1 @playwright/test; node roofs.mjs milan.json
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('@playwright/test');

const file = process.argv[2];
const d = JSON.parse(readFileSync(file));
const SKIP = new Set(['Duomo di Milano', 'Galleria Vittorio Emanuele Secondo', 'Ottagono', 'Arco della Galleria', 'Castello Sforzesco',
  'Torre del Filarete', 'Torre Falconiera', 'Monumento a Vittorio Emanuele II', 'Palazzo della Ragione', 'Torre Velasca']);
const signed = (f) => { let s = 0; for (let i = 0; i < f.length; i += 2) { const j = (i + 2) % f.length; s += f[i] * f[j + 1] - f[j] * f[i + 1]; } return s / 200; }; // m², >0 = CCW
const flip = (f) => { const r = []; for (let i = f.length - 2; i >= 0; i -= 2) r.push(f[i], f[i + 1]); return r; };

const jobs = [];
d.b.forEach((b, i) => {
  const name = b[2] >= 0 ? d.names[b[2]] : '';
  if (b[3] !== 3 || SKIP.has(name) || b[0] > 45 || b[0] - b[1] < 3 || Math.abs(signed(b[4])) < 40) return;
  if (signed(b[4]) < 0) b[4] = flip(b[4]);                                    // outer ring counter-clockwise
  if (b[5]) b[5] = b[5].map((h) => (signed(h) > 0 ? flip(h) : h));           // holes clockwise
  jobs.push([i, [b[4], ...(b[5] || [])]]);
});

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent('<html><body></body></html>');
await page.addScriptTag({ path: require.resolve('straight-skeleton') });
const res = await page.evaluate(async (jobs) => {
  await SkeletonBuilder.init();
  const out = {};
  for (const [i, rings] of jobs) {
    const rr = rings.map((f) => { const r = []; for (let k = 0; k < f.length; k += 2) r.push([f[k] / 10, f[k + 1] / 10]); return [...r, r[0]]; });
    const n = rings.reduce((s, f) => s + f.length / 2, 0);
    let s = null; try { s = SkeletonBuilder.buildFromPolygon(rr); } catch (e) { s = null; }
    if (!s) continue;
    const flat = rr.flatMap((r) => r.slice(0, -1));
    if (s.vertices.length < n || flat.some((p, k) => Math.abs(p[0] - s.vertices[k][0]) > 1e-3 || Math.abs(p[1] - s.vertices[k][1]) > 1e-3)) continue; // contour first, in order (Wasm returns 32-bit floats)
    out[i] = [s.vertices.slice(n).flatMap((v) => [Math.round(v[0] * 10), Math.round(v[1] * 10), Math.round(v[2] * 10)]), s.polygons];
  }
  return out;
}, jobs);
await browser.close();

d.roofs = res;
writeFileSync(file, JSON.stringify(d));
const ok = Object.keys(res).length;
console.log('roofs', ok, 'of', jobs.length, 'footprints', `(${((jobs.length - ok) / jobs.length * 100).toFixed(1)}% left flat)`);
console.assert(ok > jobs.length * 0.95, 'too many skeletons failed');
