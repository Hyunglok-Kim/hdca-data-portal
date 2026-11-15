/* HDCA data portal — single-page app, no build step.

   How the map gets its data
     The grid is SMAP's 36 km EASE-Grid 2.0 (406 x 964 cells), so a whole day is one 8-bit PNG of about
     100 KB: pixel = value in whole steps (DN x step), DN 255 = no retrieval. catalog.json says which days,
     months and climatology layers exist and where they live (PMTiles archives used as range-readable
     key-value stores). The browser fetches the one field it needs, keeps the numbers, and projects them
     onto Web Mercator tiles itself through the "hdca://" protocol — so the cursor readout is exact and
     no tile server is involved. A click reads the cell's whole 2015–2025 record for all three variables
     from the series store with one range request. */
(() => {
"use strict";

/* ───────────────────────────── configuration ───────────────────────────── */
const CFG = Object.assign({ dataBase: "./data/", seriesBase: "", ncBase: "", contactEmail: "", dataContact: "", nasPath: "" }, window.PORTAL_CONFIG || {});
const Q = new URLSearchParams(location.search);
{
  const d = Q.get("data");                       // same-origin absolute path only
  if (d && /^\/(?!\/)[\w\-./]*\/$/.test(d)) CFG.dataBase = d;
  const nas = Q.get("nas");                      // lab storage path, shown on the internal copy
  if (nas && /^\/[\w\-./]+$/.test(nas)) CFG.nasPath = nas;
}
const EMBED = Q.get("embed") === "1";
if (EMBED) document.documentElement.classList.add("embed");
if (Q.get("hidefooter") === "1") document.body.classList.add("hide-footer");   // as on the Hampyeong portal
const DATA = new URL(CFG.dataBase, location.href).href;
/* The series store may live apart from the fields (public copy: a second GitHub Pages repository on the same
   origin, because one site holds at most 1 GB). A ?data= override (the lab copy) keeps everything together. */
const SERIES = Q.get("data") || !CFG.seriesBase ? DATA : new URL(CFG.seriesBase, location.href).href;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const TILE = 256, W = 964, H = 406, Y0 = 2015;
const NODATA = 255;
const GLOBE = { center: [12, 18], zoom: 1.55 };
const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
/* Sequential ramps, lightness falling monotonically, one per variable so the layers are told apart at a glance. */
const RAMPS = {
  SM: ["#ffffd9", "#edf8b1", "#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#253494", "#081d58"].map(hex),   // dry → wet
  VOD: ["#ffffe5", "#f7fcb9", "#d9f0a3", "#addd8e", "#78c679", "#41ab5d", "#238443", "#006837", "#004529"].map(hex),
  OMEGA: ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026", "#800026"].map(hex),
  N: ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"].map(hex),
};
const VARS = {
  SM: { name: "Soil moisture", short: "SM", units: "m³/m³", digits: 3, fixed: [0.02, 0.5], tick: 0.05, series: 0 },
  VOD: { name: "Vegetation optical depth", short: "VOD", units: "", digits: 2, fixed: [0, 1.2], tick: 0.1, series: 1 },
  OMEGA: { name: "Effective scattering albedo", short: "ω̄", units: "", digits: 3, fixed: [0, 0.15], tick: 0.01, series: 2 },
  N: { name: "Days observed", short: "days", units: "days", digits: 0, fixed: null, tick: 1, series: null },
};
const COVER_STEPS = ["#D9E8F1", "#A9CBDF", "#74A9C9", "#2E7BA8", "#1F5F85"];   // one hue, light → dark
/* Validation sites of the paper, then regions worth a look. */
const SITES = [["Tambopata, Peru (Amazon)", -69.27, -12.83], ["Millbrook, New York", -73.615, 41.855],
  ["Harvard Forest, Massachusetts", -72.12, 42.515], ["Carman, Manitoba", -98.0, 49.5], ["South Fork, Iowa", -93.4, 42.4]];
const REGIONS = [["Korean Peninsula", 127.5, 37.0], ["Congo Basin", 22, 0.5], ["Borneo", 114, 0.5], ["Sahel", 5, 14],
  ["Indian subcontinent", 78, 22], ["Australia", 134, -25], ["Southern Africa", 25, -22], ["Western Europe", 8, 48]];

/* EASE-Grid 2.0 global 36 km (EPSG:6933): x is linear in longitude, y is linear in the authalic q(φ). */
const EASE = { a: 6378137.0, e2: 0.00669437999014, cell: 36032.220840584, y0: 7314540.830638 };
EASE.e = Math.sqrt(EASE.e2);
{ const s = Math.sin(30 * Math.PI / 180); EASE.k0 = Math.cos(30 * Math.PI / 180) / Math.sqrt(1 - EASE.e2 * s * s); }
function latToRow(lat) {
  const s = Math.sin(lat * Math.PI / 180), e = EASE.e;
  const q = (1 - EASE.e2) * (s / (1 - EASE.e2 * s * s) - Math.log((1 - e * s) / (1 + e * s)) / (2 * e));
  const r = Math.floor((EASE.y0 - EASE.a * q / (2 * EASE.k0)) / EASE.cell);
  return r >= 0 && r < H ? r : -1;
}
const lonToCol = (lon) => { const c = Math.floor((lon + 180) / 360 * W); return ((c % W) + W) % W; };
const tileLat = (yf) => Math.atan(Math.sinh(Math.PI * (1 - 2 * yf))) * 180 / Math.PI;

/* ───────────────────────────── small helpers ───────────────────────────── */
const $ = (s) => document.querySelector(s);
function el(tag, attrs, kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of [].concat(kids == null ? [] : kids)) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}
const svgEl = (tag, attrs) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
  return n;
};
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const fmt = (v, d = 0) => (v == null || Number.isNaN(v) ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const pad2 = (n) => String(n).padStart(2, "0");
const ymLabel = (ym) => `${MONL[+ym.slice(5, 7) - 1]} ${ym.slice(0, 4)}`;
const dLabel = (d) => `${+d.slice(8, 10)} ${MON[+d.slice(5, 7) - 1]} ${d.slice(0, 4)}`;
function fmtBytes(b) { return b >= 1e9 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(1) + " MB"; }
const isoOf = (date) => `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`;
const dateOf = (iso) => new Date(iso + "T00:00:00Z");
const dayIndex = (iso) => Math.round((dateOf(iso) - dateOf(CAT.record.first)) / 86400e3);
const isoAt = (i) => isoOf(new Date(dateOf(CAT.record.first).getTime() + i * 86400e3));
const doy = (iso) => Math.round((dateOf(iso) - dateOf(iso.slice(0, 4) + "-01-01")) / 86400e3) + 1;
const daysIn = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();
function rampRGB(ramp, t) {
  const x = clamp(t, 0, 1) * (ramp.length - 1), i = Math.min(ramp.length - 2, Math.floor(x)), f = x - i;
  return [0, 1, 2].map((c) => Math.round(ramp[i][c] + (ramp[i + 1][c] - ramp[i][c]) * f));
}
function niceCeil(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v || 1))), n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}
function download(name, text, type) {
  const a = el("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function copyText(text, btn) {
  try { await navigator.clipboard.writeText(text); } catch {
    const t = el("textarea", { style: "position:fixed;opacity:0" }, text); document.body.append(t); t.select();
    document.execCommand("copy"); t.remove();
  }
  if (btn) { const old = btn.textContent; btn.textContent = "Copied"; setTimeout(() => { btn.textContent = old; }, 1400); }
}
const tip = $("#tip");
function showTip(nodes, x, y) {
  tip.replaceChildren(...nodes); tip.hidden = false;
  const r = tip.getBoundingClientRect();
  tip.style.left = clamp(x + 14, 6, innerWidth - r.width - 6) + "px";
  tip.style.top = clamp(y - r.height - 12 < 6 ? y + 16 : y - r.height - 12, 6, innerHeight - r.height - 6) + "px";
}
const hideTip = () => { tip.hidden = true; };

/* ───────────────────────────── state ───────────────────────────── */
let CAT = null, map = null, landGeo = null, pickMarker = null;
let dayByDate = new Map(), dayList = [], monthByYm = new Map();
const state = { var: "SM", mode: "all", climMonth: 7, ym: null, day: null, scale: "fixed", pick: null, seriesYear: null, playing: null };
let chartModel = null, recordModel = null;

/* ───────────────────────────── catalog ───────────────────────────── */
async function loadCatalog() {
  const r = await fetch(DATA + "catalog.json", { cache: "no-cache" });
  if (r.status === 401 || r.status === 403) {
    if (window.parent !== window) window.parent.postMessage({ type: "portalAuth" }, "*");
    throw new Error("Sign-in required — open this page from the lab dashboard.");
  }
  if (!r.ok) throw new Error(`Could not load the catalog (HTTP ${r.status}).`);
  CAT = await r.json();
  dayList = CAT.days; dayByDate = new Map(CAT.days.map((d) => [d.d, d]));
  monthByYm = new Map(CAT.months.map((m) => [m.ym, m]));
  const julys = CAT.months.filter((m) => m.ym.endsWith("-07") && m.with_data >= 25);
  state.ym = (julys[julys.length - 1] || CAT.months[CAT.months.length - 1]).ym;
  state.seriesYear = state.ym.slice(0, 4);
  const mid = dayList.filter((d) => d.d.startsWith(state.ym) && d.d.slice(8) === "15")[0] || dayList.find((d) => d.d.startsWith(state.ym));
  state.day = mid ? mid.d : dayList[dayList.length - 1].d;
  const vq = Q.get("var"); if (vq && VARS[vq]) state.var = vq;
  const dq = Q.get("date"); if (dq && dayByDate.has(dq)) { state.mode = "day"; state.day = dq; state.ym = dq.slice(0, 7); state.seriesYear = dq.slice(0, 4); }
  const bad = CAT.grid.lats.map((la, i) => [i, latToRow(la)]).filter(([i, r]) => i !== r);
  if (bad.length) console.warn("[grid] analytic row differs from the catalogue's row centres for", bad.length, "rows", bad.slice(0, 5));
}
const V = () => VARS[state.var];
const YEARS = () => CAT.source.years.map((y) => String(y.year));
const RECORD_YEARS = () => `${CAT.record.first.slice(0, 4)}–${CAT.record.last.slice(0, 4)}`;

/* What is on the map: which archive, which entry, how to read the numbers. */
function layerSpec() {
  const v = state.var, isN = v === "N";
  const spec = { var: v, mode: state.mode, step: isN ? 1 : CAT.variables[v].step, units: V().units, digits: V().digits, mean: null, cover: null };
  if (state.mode === "all") {
    spec.archive = `clim/HDCA_${v}_clim.pmtiles`; spec.x = 0;
    if (isN) { spec.step = 16; spec.label = `Days with a retrieval, ${RECORD_YEARS()}`; spec.sub = `How many of the ${fmt(CAT.record.with_tiles)} days in the record had a retrieval at the cell. The sum of all months, in steps of 16 days.`; }
    else { const s = CAT.variables[v].all; spec.mean = s.mean; spec.cover = s.cover; spec.label = `${V().name}, record mean ${RECORD_YEARS()}`; spec.sub = `Mean of every daily retrieval at the cell; on average a cell has ${fmt(s.days_per_cell_mean)} days.`; }
  } else if (state.mode === "clim") {
    const m = state.climMonth;
    spec.archive = `clim/HDCA_${v}_clim.pmtiles`; spec.x = m;
    if (isN) { spec.label = `Days with a retrieval in ${MONL[m - 1]}, mean over years`; spec.sub = "Average number of days in that calendar month with a retrieval at the cell. Frozen months are empty in the north."; }
    else { const s = CAT.variables[v].clim[m - 1]; spec.mean = s.mean; spec.cover = s.cover; spec.label = `${V().name}, ${MONL[m - 1]} mean ${RECORD_YEARS()}`; spec.sub = `Mean of all ${MONL[m - 1]} retrievals over ${s.years} years, using the days the cell was retrieved.`; }
  } else if (state.mode === "month") {
    const ym = state.ym, rec = monthByYm.get(ym), y = +ym.slice(0, 4), m = +ym.slice(5, 7);
    spec.archive = `monthly/HDCA_${v}_monthly.pmtiles`; spec.x = (y - Y0) * 12 + m - 1; spec.rec = rec;
    if (isN) { spec.label = `Days with a retrieval, ${ymLabel(ym)}`; spec.sub = `${rec.with_data} of ${rec.days} days of the month have a SMAP file.`; }
    else { spec.mean = rec[v]; spec.cover = rec.cover; spec.label = `${V().name}, ${ymLabel(ym)} mean`; spec.sub = `Mean over the days of the month with a retrieval · ${rec.with_data} of ${rec.days} days have data.`; }
  } else {
    const d = state.day, rec = dayByDate.get(d);
    spec.archive = `daily/HDCA_${v}_${d.slice(0, 4)}.pmtiles`; spec.x = doy(d); spec.rec = rec;
    spec.label = `${V().name}, ${dLabel(d)}`;
    spec.sub = rec ? `One day of 6 a.m. overpasses · ${fmtBytes(rec.bytes)} NetCDF` : "No SMAP file for this day.";
    if (rec) { spec.mean = rec[v]; spec.cover = rec.n / CAT.land_px; }
  }
  spec.key = `${v}|${state.mode}|${state.mode === "all" ? "" : state.mode === "clim" ? pad2(state.climMonth) : state.mode === "month" ? state.ym : state.day}`;
  return spec;
}
function currentRange(spec, st) {
  const v = V();
  if (state.scale === "fixed") {
    if (spec.var !== "N") return v.fixed;
    return spec.mode === "all" ? [0, 4000] : [0, 31];
  }
  const t = spec.var === "N" ? (spec.mode === "all" ? 100 : 1) : v.tick;
  const lo = Math.floor((st ? st.p02 : 0) / t) * t, hi = Math.ceil((st ? st.p98 : t) / t) * t;
  return [lo, Math.max(hi, lo + t)];
}

/* ───────────────────────────── fields (one PNG per layer) ───────────────────────────── */
const archives = new Map(), fields = new Map(), pendingF = new Map();
const FIELD_MAX = 80;
function archive(rel) {
  let a = archives.get(rel);
  if (!a) { a = new pmtiles.PMTiles(new pmtiles.FetchSource(DATA + rel)); archives.set(rel, a); }
  return a;
}
/* Fields carry numbers, so they are decoded byte for byte and not through a canvas: Safari colour-manages canvas
   pixels and hands back values that are off by one. An 8-bit grayscale PNG is a zlib stream of filtered rows. */
async function decodePNG8(buf, w, h) {
  const b = new Uint8Array(buf), dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  if (b.length < 45 || dv.getUint32(0) !== 0x89504e47 || dv.getUint32(4) !== 0x0d0a1a0a) throw new Error("not a PNG");
  let p = 8, pw = 0, ph = 0;
  const idat = [];
  while (p + 12 <= b.length) {
    const len = dv.getUint32(p), type = dv.getUint32(p + 4);
    if (type === 0x49484452) {                                    // IHDR: 8-bit, grayscale, not interlaced
      pw = dv.getUint32(p + 8); ph = dv.getUint32(p + 12);
      if (pw !== w || ph !== h || b[p + 16] !== 8 || b[p + 17] !== 0 || b[p + 20] !== 0) throw new Error("unexpected PNG layout");
    } else if (type === 0x49444154) idat.push(b.subarray(p + 8, p + 8 + len));
    else if (type === 0x49454e44) break;
    p += 12 + len;
  }
  const raw = new Uint8Array(await new Response(new Blob(idat).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());
  if (!pw || raw.length !== ph * (pw + 1)) throw new Error("unexpected PNG size");
  const out = new Uint8Array(pw * ph);
  for (let y = 0; y < ph; y++) {
    const f = raw[y * (pw + 1)], src = y * (pw + 1) + 1, dst = y * pw, up = dst - pw;
    for (let x = 0; x < pw; x++) {
      const a = x ? out[dst + x - 1] : 0, u = y ? out[up + x] : 0, c = x && y ? out[up + x - 1] : 0;
      let v = raw[src + x];
      if (f === 1) v += a;
      else if (f === 2) v += u;
      else if (f === 3) v += (a + u) >> 1;
      else if (f === 4) { const q = a + u - c, pa = Math.abs(q - a), pu = Math.abs(q - u), pc = Math.abs(q - c); v += pa <= pu && pa <= pc ? a : pu <= pc ? u : c; }
      else if (f !== 0) throw new Error("unexpected PNG filter");
      out[dst + x] = v;
    }
  }
  return out;
}
const cv = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(W, H) : Object.assign(document.createElement("canvas"), { width: W, height: H });
const cx = cv.getContext("2d", { willReadFrequently: true });
async function decodeViaCanvas(buf) {
  const bmp = await createImageBitmap(new Blob([buf], { type: "image/png" }), { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  cx.clearRect(0, 0, W, H); cx.drawImage(bmp, 0, 0); bmp.close();
  const d = cx.getImageData(0, 0, W, H).data, out = new Uint8Array(W * H);
  for (let i = 0, j = 0; i < out.length; i++, j += 4) out[i] = d[j];
  return out;
}
let exactDecode = typeof DecompressionStream !== "undefined";
async function decodeDN(buf) {
  if (exactDecode) {
    try { return await decodePNG8(buf, W, H); }
    catch (e) { console.warn("[fields] exact PNG decode failed, falling back to canvas:", e.message); exactDecode = false; }
  }
  return decodeViaCanvas(buf);
}
/* The field of a layer: Uint8Array(W*H) or null when the archive has no entry (a day without a SMAP file). */
function getField(spec) {
  const key = spec.key;
  if (fields.has(key)) { const v = fields.get(key); fields.delete(key); fields.set(key, v); return Promise.resolve(v); }
  if (pendingF.has(key)) return pendingF.get(key);
  const p = (async () => {
    const res = await archive(spec.archive).getZxy(9, spec.x, 0);
    const dn = res && res.data && res.data.byteLength ? await decodeDN(res.data) : null;
    fields.set(key, dn);
    if (fields.size > FIELD_MAX) fields.delete(fields.keys().next().value);
    return dn;
  })().finally(() => pendingF.delete(key));
  pendingF.set(key, p);
  return p;
}
/* Statistics of a field, computed here: the grid is equal-area, so a plain mean over cells is an area mean. */
const statCache = new Map();
function fieldStats(spec, dn) {
  if (statCache.has(spec.key)) return statCache.get(spec.key);
  const hist = new Float64Array(255);
  let n = 0, sum = 0;
  if (dn) for (let i = 0; i < dn.length; i++) { const d = dn[i]; if (d !== NODATA) { hist[d]++; n++; sum += d; } }
  const pct = (p) => { let c = 0; for (let d = 0; d < 255; d++) { c += hist[d]; if (c >= n * p) return d * spec.step; } return 254 * spec.step; };
  const st = { n, mean: n ? sum / n * spec.step : null, cover: n / CAT.land_px, p02: n ? pct(0.02) : 0, p98: n ? pct(0.98) : spec.step, hist };
  statCache.set(spec.key, st);
  return st;
}

/* ───────────────────────────── colouring and the tile protocol ───────────────────────────── */
const luts = new Map();
function lutFor(spec, lo, hi) {
  const key = `${spec.var}_${spec.step}_${lo}_${hi}`;
  let lut = luts.get(key);
  if (!lut) {
    lut = new Uint32Array(256);
    const ramp = RAMPS[spec.var];
    for (let d = 0; d < 255; d++) {
      const [r, g, b] = rampRGB(ramp, (d * spec.step - lo) / (hi - lo));
      lut[d] = (255 << 24 | b << 16 | g << 8 | r) >>> 0;       // little-endian RGBA
    }
    lut[NODATA] = 0;
    luts.set(key, lut);
  }
  return { key, lut };
}
let current = null;                                            // { spec, lut, lutKey, stats, field }
const specsByKey = new Map();
function registerProtocol() {
  maplibregl.addProtocol("hdca", async (params) => {
    const m = /^hdca:\/\/([^/]+)\/(\d+)\/(\d+)\/(\d+)\?k=(.+)$/.exec(params.url);
    const spec = m && specsByKey.get(decodeURIComponent(m[1]));
    const lut = m && luts.get(decodeURIComponent(m[5]));
    const dn = spec && lut ? await getField(spec) : null;
    if (!dn) return { data: await createImageBitmap(new ImageData(1, 1)) };
    const z = +m[2], tx = +m[3], ty = +m[4], n = 2 ** z;
    const rows = new Int16Array(TILE), cols = new Int16Array(TILE);
    for (let i = 0; i < TILE; i++) {
      rows[i] = latToRow(tileLat((ty + (i + 0.5) / TILE) / n));
      cols[i] = lonToCol(((tx + (i + 0.5) / TILE) / n) * 360 - 180);
    }
    const img = new ImageData(TILE, TILE), px = new Uint32Array(img.data.buffer);
    for (let j = 0; j < TILE; j++) {
      const r = rows[j];
      if (r < 0) continue;
      const base = r * W, o = j * TILE;
      for (let i = 0; i < TILE; i++) px[o + i] = lut[dn[base + cols[i]]];
    }
    return { data: await createImageBitmap(img) };
  });
}
const tileURL = () => `hdca://${encodeURIComponent(current.spec.key)}/{z}/{x}/{y}?k=${encodeURIComponent(current.lutKey)}`;

/* Switch the map to the layer the controls describe. Fetches the field first so the stats, legend and card agree. */
let applySeq = 0;
async function applyLayer() {
  const seq = ++applySeq, spec = layerSpec();
  specsByKey.set(spec.key, spec);
  renderWhen(); renderCalendar();
  let dn = null;
  try { dn = await getField(spec); } catch (e) { console.warn("[field]", e.message); }
  if (seq !== applySeq) return;
  const st = fieldStats(spec, dn);
  const [lo, hi] = currentRange(spec, st);
  const { key: lutKey, lut } = lutFor(spec, lo, hi);
  current = { spec, lut, lutKey, stats: st, field: dn, lo, hi };
  const src = map && map.getSource("data");
  if (src) src.setTiles([tileURL()]);
  renderLayerCard(); renderLegend();
  if (!state.pick) renderGlobalSeries(); else renderPickCharts();
}

/* ───────────────────────────── map ───────────────────────────── */
function initMap() {
  registerProtocol();
  map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      projection: { type: "globe" },
      sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 4.5, 1, 6.5, 0] },
      sources: {
        sat: { type: "raster", tileSize: 256, maxzoom: 18,
               tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
               attribution: "Imagery © Esri, Maxar, Earthstar Geographics" },
        data: { type: "raster", tileSize: 256, minzoom: 0, maxzoom: 7, tiles: [tileURL()],
                attribution: "HDCA: Lee et al., HydroAI Lab (GIST) · SMAP L3 (NASA)" },
      },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#0F1318" } },
        { id: "sat", type: "raster", source: "sat", paint: { "raster-saturation": -0.45, "raster-brightness-max": 0.8 } },
        { id: "data", type: "raster", source: "data", paint: { "raster-opacity": 1, "raster-fade-duration": 120, "raster-resampling": "nearest" } },
      ],
    },
    center: REDUCED || Q.get("intro") === "0" ? GLOBE.center : [-30, 18], zoom: REDUCED || Q.get("intro") === "0" ? GLOBE.zoom : 1.25,
    minZoom: 0.9, maxZoom: 9,
    attributionControl: { compact: true }, dragRotate: false, pitchWithRotate: false, touchPitch: false,
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 110 }), "bottom-left");
  window.__portal = { map, state, getField, fields, exact: () => exactDecode, latToRow, lonToCol, current: () => current, layerSpec };

  map.on("error", (e) => console.warn("[map]", e && e.error ? e.error.message : e));
  map.on("load", () => {
    $("#boot").classList.add("out");
    setTimeout(() => $("#boot").remove(), 500);
    addMarkers();
    loadLand();
    if (!(REDUCED || Q.get("intro") === "0")) setTimeout(() => map.easeTo({ ...GLOBE, duration: 2600 }), 700);
  });
  map.on("zoom", onZoom);
  map.on("mousemove", onHover);
  map.on("mouseout", () => { $("#roVal").textContent = ""; });
  map.on("click", onClick);
}
async function loadLand() {
  /* Natural Earth 1:110m land (public domain), cut at the antimeridian — a stitched outline draws rings around the pole. */
  try {
    landGeo = await (await fetch(new URL("assets/land-110m.json", location.href))).json();
    map.addSource("land", { type: "geojson", data: landGeo });
    map.addLayer({ id: "land-line", type: "line", source: "land", paint: { "line-color": "#F0EEE6", "line-width": 0.6,
      "line-opacity": ["interpolate", ["linear"], ["zoom"], 1, 0.45, 5, 0.25, 7, 0] } });
  } catch (e) { console.warn("[land outline]", e.message); }
}
let siteMarkers = [];
function addMarkers() {
  siteMarkers = SITES.map(([name, lng, lat]) =>
    new maplibregl.Marker({ element: el("div", {}, el("span", { class: "city" }, "● " + name.split(",")[0])), anchor: "left" }).setLngLat([lng, lat]).addTo(map));
  onZoom();
}
function onZoom() {
  if (!map) return;
  const z = map.getZoom();
  for (const m of siteMarkers) m.getElement().firstChild.style.opacity = z >= 3.2 ? "1" : "0";
  if (map.getLayer("data")) map.setPaintProperty("data", "raster-resampling", z > 2.5 ? "nearest" : "linear");
}
function cellAt(lng, lat) {
  const row = latToRow(lat);
  if (row < 0) return null;
  const col = lonToCol(lng);
  return { row, col, lat: CAT.grid.lats[row], lng: CAT.grid.lons[col] };
}
function valueAt(dn, row, col) {
  if (!dn) return null;
  const d = dn[row * W + col];
  return d === NODATA ? null : d * current.spec.step;
}
let hoverRAF = 0;
function onHover(e) {
  cancelAnimationFrame(hoverRAF);
  hoverRAF = requestAnimationFrame(() => {
    const out = $("#roVal"), c = cellAt(e.lngLat.lng, e.lngLat.lat);
    if (!c || !current) { out.textContent = ""; return; }
    const v = valueAt(current.field, c.row, c.col);
    out.textContent = v == null ? "no retrieval" : `${fmt(v, current.spec.digits)} ${current.spec.units}`.trim();
  });
}
function onClick(e) {
  const { lng, lat } = e.lngLat, c = cellAt(lng, lat);
  if (!c) return;
  if (map.getZoom() < 3.4) map.flyTo({ center: [lng, lat], zoom: 4.4, duration: 1400 });
  pickLocation(c);
}

/* ───────────────────────────── layer controls ───────────────────────────── */
function renderWhen() {
  const box = $("#when"); box.replaceChildren();
  document.querySelectorAll("#varSeg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.var === state.var);
    b.disabled = b.dataset.var === "N" && state.mode === "day";
  });
  document.querySelectorAll("#modeSeg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.mode === state.mode);
    b.disabled = b.dataset.mode === "day" && state.var === "N";
  });
  if (state.mode === "all") { box.append(el("span", { class: "sub" }, `Every day of ${RECORD_YEARS()}`)); return; }
  if (state.mode === "clim") {
    box.append(el("div", { class: "mon", role: "group", "aria-label": "Month" }, MON.map((name, i) =>
      el("button", { class: state.climMonth === i + 1 ? "on" : "", title: MONL[i], onclick: () => { stopPlay(); state.climMonth = i + 1; applyLayer(); } }, name))));
    box.append(playBtn());
    return;
  }
  const y = state.mode === "month" ? state.ym.slice(0, 4) : state.day.slice(0, 4);
  box.append(el("select", { "aria-label": "Year", onchange: (e) => { stopPlay(); setYear(e.target.value); } },
    YEARS().map((yy) => el("option", { value: yy, selected: yy === y }, yy))));
  const curM = state.mode === "month" ? +state.ym.slice(5, 7) : +state.day.slice(5, 7);
  const have = new Set(CAT.months.filter((m) => m.ym.startsWith(y) && m.with_data > 0).map((m) => +m.ym.slice(5, 7)));
  box.append(el("div", { class: "mon", role: "group", "aria-label": "Month" }, MON.map((name, i) =>
    el("button", { class: curM === i + 1 ? "on" : "", disabled: !have.has(i + 1), title: MONL[i], onclick: () => { stopPlay(); setMonth(i + 1); } }, name))));
  if (state.mode === "day") {
    const inp = el("input", { type: "date", class: "daypick", value: state.day, min: CAT.record.first, max: CAT.record.last, "aria-label": "Day",
      onchange: (e) => { if (/^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) { stopPlay(); setDay(e.target.value, +1); } } });
    box.append(el("div", { class: "daynav" }, [
      el("button", { class: "mbtn", title: "Previous day with data", onclick: () => { stopPlay(); stepDay(-1); } }, "◀"),
      inp,
      el("button", { class: "mbtn", title: "Next day with data", onclick: () => { stopPlay(); stepDay(+1); } }, "▶"),
    ]));
  }
  box.append(playBtn());
}
function playBtn() {
  return el("button", { class: "play", onclick: togglePlay, "aria-pressed": state.playing ? "true" : "false" }, state.playing ? "Pause" : "Play");
}
function setYear(y) {
  state.seriesYear = y;
  if (state.mode === "month") {
    const have = CAT.months.filter((m) => m.ym.startsWith(y) && m.with_data > 0);
    state.ym = (have.find((m) => m.ym.slice(5) === state.ym.slice(5)) || have[0]).ym;
  } else {
    const want = `${y}-${state.day.slice(5)}`;
    state.day = dayByDate.has(want) ? want : nearestDay(want, +1);
    state.ym = state.day.slice(0, 7);
  }
  applyLayer(); if (state.pick) renderPickCharts();
}
function setMonth(m) {
  const y = state.mode === "month" ? state.ym.slice(0, 4) : state.day.slice(0, 4);
  if (state.mode === "month") state.ym = `${y}-${pad2(m)}`;
  else { const want = `${y}-${pad2(m)}-${Math.min(+state.day.slice(8), daysIn(+y, m)).toString().padStart(2, "0")}`; state.day = dayByDate.has(want) ? want : nearestDay(want, +1); state.ym = state.day.slice(0, 7); }
  applyLayer();
}
/* The next day with a file in the given direction (SMAP outages span weeks); the other direction only as a last resort. */
function nearestDay(iso, dir) {
  const i = dayIndex(iso);
  for (const d of [dir, -dir]) for (let k = 1; k < 400; k++) { const j = i + k * d; if (j >= 0 && j < CAT.record.n && dayByDate.has(isoAt(j))) return isoAt(j); }
  return dayList[0].d;
}
function setDay(iso, dir) {
  iso = iso < CAT.record.first ? CAT.record.first : iso > CAT.record.last ? CAT.record.last : iso;
  const missing = !dayByDate.has(iso);
  state.day = missing ? nearestDay(iso, dir) : iso;
  state.ym = state.day.slice(0, 7);
  if (state.seriesYear !== state.day.slice(0, 4)) { state.seriesYear = state.day.slice(0, 4); if (state.pick) renderPickCharts(); }
  if (missing) flagText = `${dLabel(iso)} has no SMAP file — showing ${dLabel(state.day)}, the next day with one.`;   // applyLayer's card render shows it
  applyLayer();
}
function stepDay(dir) {
  const k = dayList.findIndex((d) => d.d === state.day), nxt = dayList[clamp(k + dir, 0, dayList.length - 1)];
  if (nxt && nxt.d !== state.day) setDay(nxt.d, dir);
}
let flagText = "";
function stopPlay() { if (state.playing) { clearInterval(state.playing); state.playing = null; } }
function togglePlay() {
  if (state.playing) { stopPlay(); renderWhen(); return; }
  if (state.mode === "day") state.playing = setInterval(() => stepDay(+1), 700);
  else if (state.mode === "month") state.playing = setInterval(() => {
    const months = CAT.months.filter((m) => m.ym.startsWith(state.ym.slice(0, 4)) && m.with_data > 0).map((m) => +m.ym.slice(5, 7));
    setMonth(months[(months.indexOf(+state.ym.slice(5, 7)) + 1) % months.length]);
  }, 1300);
  else state.playing = setInterval(() => { state.climMonth = state.climMonth % 12 + 1; applyLayer(); }, 1300);
  renderWhen();
}

/* ───────────────────────────── legend + layer card ───────────────────────────── */
function renderLegend() {
  const { spec, lo, hi, stats } = current, ramp = RAMPS[spec.var];
  $("#lgTitle").textContent = spec.var === "N" ? "Days with a retrieval" : `${V().short}${spec.units ? ", " + spec.units : ""}`;
  $("#lgBar").style.background = `linear-gradient(90deg, ${ramp.map((c) => `rgb(${c.join(",")})`).join(",")})`;
  const d = spec.var === "N" ? 0 : spec.digits;
  $("#lgTicks").replaceChildren(el("span", {}, lo > 0 ? `≤ ${fmt(lo, d)}` : fmt(lo, d)), el("span", {}, fmt((lo + hi) / 2, d)), el("span", {}, `≥ ${fmt(hi, d)}`));
  $("#lgNodata").textContent = spec.var === "N" ? "Not a land cell" : spec.mode === "day" ? "No retrieval — no overpass, frozen, MPDI ≤ 0.002 or water" : "No retrieval in any day — frozen all season, or water";
  document.querySelectorAll("#scaleSeg button").forEach((b) => b.classList.toggle("on", b.dataset.scale === state.scale));
  const c = $("#lgHist"), LW = 240, LH = 34, dpr = Math.min(2, devicePixelRatio || 1);
  c.width = LW * dpr; c.height = LH * dpr;
  const g = c.getContext("2d"); g.scale(dpr, dpr); g.clearRect(0, 0, LW, LH);
  if (!stats.n) return;
  const cols = new Float64Array(LW);
  stats.hist.forEach((n, dn) => { cols[clamp(Math.round((dn * spec.step - lo) / (hi - lo) * (LW - 1)), 0, LW - 1)] += n; });
  const top = Math.max(...cols.slice(1, LW - 1), 1);
  g.fillStyle = "#8C8A80";
  for (let x = 0; x < LW; x++) { const h = Math.min(LH, cols[x] / top * (LH - 2)); if (h > 0.3) g.fillRect(x, LH - h, 1, h); }
}
function renderLayerCard() {
  if (!current) return;
  const { spec, stats } = current, isN = spec.var === "N";
  $("#lyTitle").textContent = spec.label;
  $("#lySub").textContent = spec.sub;
  const mean = spec.mean != null ? spec.mean : stats.mean;
  $("#lyMeanL").textContent = isN ? "Mean over land cells" : "Mean over observed land";
  $("#lyMean").textContent = isN ? fmt(mean) : fmt(mean, spec.digits);
  $("#lyUnit").textContent = isN ? "days" : spec.units;
  const cov = Math.min(100, (spec.cover != null ? spec.cover : stats.cover) * 100);
  $("#lyCoverL").textContent = isN ? "Land cells" : spec.mode === "day" ? "Land cells observed today" : "Land cells with a retrieval";
  $("#lyCover").textContent = fmt(cov, cov < 99.5 ? 1 : 0);
  $("#lyCoverBar").style.width = cov + "%";
  const flag = $("#lyFlag");
  let f = flagText; flagText = "";
  if (!f && !current.field) f = spec.mode === "day" ? "No SMAP file for this day — SMAP was in safe mode or the file was not produced." : "This layer has no field.";
  else if (!f && spec.mode === "day" && !isN) f = "A single day shows SMAP's swath pattern: about half of the land has a 6 a.m. overpass on any given day.";
  else if (!f && spec.var === "OMEGA") f = "ω̄ is a parameter of the inversion. Values at or above 1 occur and are drawn as ≥ 0.25 here; the files keep the full value.";
  flag.hidden = !f; flag.textContent = f || "";
}

/* ───────────────────────────── charts (SVG) ─────────────────────────────
   One line chart for everything: n equally spaced slots, series as values[n] with nulls for gaps, ticks on
   chosen slots. spanGaps draws a series through its gaps (used for the monthly-mean overlay on daily data). */
function drawLine(box, model) {
  box.replaceChildren();
  const all = model.series.flatMap((s) => s.values).filter((v) => v != null);
  if (!all.length) { box.append(el("p", { class: "chart-empty" }, model.empty || "No data at this location.")); return; }
  box.append(el("div", { class: "chart-legend" }, model.series.map((s) => el("span", {}, [el("i", { class: "key", style: `border-color:${s.color}` }), s.name]))));
  const CW = 360, CH = model.height || 200, m = { l: 38, r: model.rightPad == null ? 12 : model.rightPad, t: 8, b: 22 }, pw = CW - m.l - m.r, ph = CH - m.t - m.b;
  const n = model.n, yMin = model.yMin == null ? 0 : model.yMin;
  const yMax = model.yMax != null ? model.yMax : niceCeil(Math.max(...all) * 1.04) || 1;
  const X = (i) => m.l + (n === 1 ? pw / 2 : pw * i / (n - 1)), Y = (v) => m.t + ph * (1 - (v - yMin) / (yMax - yMin));
  const svg = svgEl("svg", { viewBox: `0 0 ${CW} ${CH}`, role: "img", tabindex: "0", "aria-label": `${model.title}. Use the table below for values.` });
  const nY = model.yLines || 4, stepY = (yMax - yMin) / nY;
  const yDigits = model.yDigits != null ? model.yDigits : stepY >= 1 ? 0 : stepY >= 0.1 ? 1 : stepY >= 0.01 ? 2 : 3;   // ticks must not repeat
  for (let k = 0; k <= nY; k++) {
    const v = yMin + stepY * k, y = Y(v);
    svg.append(svgEl("line", { class: k ? "gridline" : "axisline", x1: m.l, x2: CW - m.r, y1: y, y2: y }));
    const t = svgEl("text", { x: m.l - 6, y: y + 3.5, "text-anchor": "end" }); t.textContent = fmt(v, yDigits); svg.append(t);
  }
  for (const [i, lb] of model.ticks) {
    if (model.tickMarks) svg.append(svgEl("line", { class: "axisline", x1: X(i), x2: X(i), y1: m.t + ph, y2: m.t + ph + 3 }));
    const t = svgEl("text", { x: X(i), y: CH - 6, "text-anchor": "middle" }); t.textContent = lb; svg.append(t);
  }
  for (const b of model.bands || []) svg.append(svgEl("rect", { class: "band", x: X(b[0]), y: m.t, width: X(b[1]) - X(b[0]), height: ph }));
  const ends = [];
  for (const s of model.series) {
    let d = "", pen = false, last = -1, lone = [];
    s.values.forEach((v, i) => {
      if (v == null) { if (!s.spanGaps) pen = false; return; }
      d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; last = i;
      if (!s.spanGaps && s.values[i - 1] == null && s.values[i + 1] == null) lone.push(i);
    });
    svg.append(svgEl("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": s.dash || "" }));
    for (const i of lone) svg.append(svgEl("circle", { cx: X(i), cy: Y(s.values[i]), r: n > 60 ? 1.4 : 2.5, fill: s.color }));
    if (s.dots) s.values.forEach((v, i) => { if (v != null) svg.append(svgEl("circle", { cx: X(i), cy: Y(v), r: 2.6, fill: s.color })); });
    if (last >= 0 && model.endLabels) ends.push({ s, i: last, y: Y(s.values[last]) });
  }
  ends.sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 12) { const mid = (ends[k].y + ends[k - 1].y) / 2; ends[k - 1].ly = mid - 6; ends[k].ly = mid + 6; }
  for (const e of ends) {
    svg.append(svgEl("circle", { cx: X(e.i), cy: e.y, r: 4, fill: e.s.color, stroke: "#fff", "stroke-width": 2 }));
    const t = svgEl("text", { class: "lbl", x: X(e.i) + 8, y: (e.ly ?? e.y) + 3.5 }); t.textContent = e.s.short || e.s.name; svg.append(t);
  }
  const cross = svgEl("line", { class: "cross", y1: m.t, y2: m.t + ph, visibility: "hidden" });
  const dots = model.series.map((s) => svgEl("circle", { r: 4, fill: s.color, stroke: "#fff", "stroke-width": 2, visibility: "hidden" }));
  svg.append(cross, ...dots);
  let cur = -1;
  const show = (i, cxp, cyp) => {
    cur = i;
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
    model.series.forEach((s, k) => {
      const v = s.values[i];
      dots[k].setAttribute("visibility", v == null ? "hidden" : "visible");
      if (v != null) { dots[k].setAttribute("cx", X(i)); dots[k].setAttribute("cy", Y(v)); }
    });
    showTip([el("div", { class: "t-h" }, model.tipHead(i)),
      ...model.series.filter((s) => !(s.spanGaps && s.values[i] == null)).map((s) => el("div", { class: "t-r" }, [el("i", { class: "key", style: `border-color:${s.color}` }),
        el("b", {}, s.values[i] == null ? (model.noneText || "no retrieval") : `${fmt(s.values[i], model.digits || 0)} ${model.units}`.trim()), el("span", { class: "n" }, s.name)])),
      ...(model.tipFoot ? [model.tipFoot(i)].filter(Boolean) : [])], cxp, cyp);
  };
  const hide = () => { cur = -1; cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden")); hideTip(); };
  svg.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * CW;
    show(clamp(Math.round((x - m.l) / pw * (n - 1)), 0, n - 1), e.clientX, e.clientY);
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const i = clamp((cur < 0 ? 0 : cur) + (cur < 0 ? 0 : e.key === "ArrowRight" ? 1 : -1), 0, n - 1), r = svg.getBoundingClientRect();
    show(i, r.left + X(i) / CW * r.width, r.top + r.height * 0.35);
  });
  box.append(svg);
}
function tableOf(model) {
  return el("table", { class: "grid" }, [
    el("thead", {}, el("tr", {}, [el("th", {}, model.rowLabel || "When"), ...model.series.map((s) => el("th", { class: "num" }, `${s.name}${model.units ? ` (${model.units})` : ""}`))])),
    el("tbody", {}, Array.from({ length: model.n }, (_, i) => i).filter((i) => model.series.some((s) => s.values[i] != null) || !model.skipEmptyRows)
      .map((i) => el("tr", {}, [el("td", {}, model.rowName(i)), ...model.series.map((s) => el("td", { class: "num" }, s.values[i] == null ? (model.noneText || "no retrieval") : fmt(s.values[i], model.digits || 0)))]))),
  ]);
}
function csvOf(model) {
  const rows = [[model.csvKey || "when", ...model.series.map((s) => s.csvName || s.name)].join(",")];
  for (let i = 0; i < model.n; i++) if (!model.skipEmptyRows || model.series.some((s) => s.values[i] != null)) rows.push([model.rowName(i), ...model.series.map((s) => s.values[i] == null ? "" : s.values[i])].join(","));
  return `# ${model.title}\n# ${model.note || ""}\n` + rows.join("\n") + "\n";
}
const monthTicks = () => MON.map((mn, i) => [i, mn[0]]);

/* ───────────────────────────── global series (no cell picked) ───────────────────────────── */
function renderGlobalSeries() {
  const v = state.var, y = state.seriesYear, vv = V();
  $("#srKicker").textContent = "Seasonal cycle"; $("#srTitle").textContent = v === "N" ? "Days with a SMAP file" : "Mean over observed land"; $("#srReset").hidden = true;
  $("#recordBox").hidden = true; recordModel = null;
  const yr = MON.map((_, i) => { const r = monthByYm.get(`${y}-${pad2(i + 1)}`); return r ? (v === "N" ? r.with_data : r[v]) : null; });
  const clim = MON.map((_, i) => {
    if (v !== "N") { const c = CAT.variables[v].clim[i]; return c ? c.mean : null; }
    const ms = CAT.months.filter((m) => +m.ym.slice(5, 7) === i + 1); return ms.length ? ms.reduce((a, m) => a + m.with_data, 0) / ms.length : null;
  });
  $("#srSub").textContent = v === "N" ? `Days of each month of ${y} that have a SMAP file, against the ${RECORD_YEARS()} average. The 2019 and 2022 gaps are SMAP outages.`
    : `${vv.name} averaged over every land cell with a retrieval in each month of ${y}, against the ${RECORD_YEARS()} mean of the same months. Frozen cells drop out in winter, so the set of cells changes with the season.`;
  chartModel = { title: v === "N" ? `Days with a SMAP file per month` : `Global mean monthly ${vv.name.toLowerCase()}`, n: 12, ticks: monthTicks(), units: v === "N" ? "days" : vv.units,
    digits: v === "N" ? 0 : vv.digits, rowLabel: "Month", rowName: (i) => `${y}-${pad2(i + 1)}`, csvKey: "month", tipHead: (i) => MONL[i], endLabels: true, rightPad: 44,
    note: v === "N" ? "days per month with a SMAP L3 file" : "mean over land cells with a retrieval; the set of cells changes with the season", noneText: "no data",
    series: [{ name: y, short: y, color: "#2E7BA8", values: yr, csvName: `${v}_${y}` }, { name: `${RECORD_YEARS()} mean`, short: "mean", color: "#8C8A80", values: clim, csvName: `${v}_mean` }] };
  drawLine($("#chart"), chartModel); renderSeriesTable();
}
function renderSeriesTable() { const w = $("#srTable"); w.replaceChildren(); if (chartModel) w.append(tableOf(chartModel)); }

/* ───────────────────────────── a cell's series ─────────────────────────────
   The series store holds one entry per land cell: uint16 [T][SM, VOD, OMEGA]. One range request gives the whole record. */
const seriesCache = new Map(), seriesArchives = new Map();
function seriesArchive(row) {
  const parts = (CAT.series && CAT.series.parts) || [];
  const part = parts.find((p) => row >= p.rows[0] && row <= p.rows[1]);
  if (!part) return null;                                       // rows with no land cell have no archive
  let a = seriesArchives.get(part.file);
  if (!a) { a = new pmtiles.PMTiles(new pmtiles.FetchSource(SERIES + part.file)); seriesArchives.set(part.file, a); }
  return a;
}
async function getSeries(row, col) {
  const key = `${row}/${col}`;
  if (seriesCache.has(key)) return seriesCache.get(key);
  const arch = seriesArchive(row);
  const res = arch ? await arch.getZxy(10, col, row) : null;    // pmtiles.js inflates gzip-compressed entries itself
  if (!res || !res.data || !res.data.byteLength) { seriesCache.set(key, null); return null; }
  const T = CAT.record.n, dv = new DataView(res.data), out = {};
  if (res.data.byteLength !== T * 6) throw new Error(`series entry has ${res.data.byteLength} bytes, expected ${T * 6}`);
  for (const v of ["SM", "VOD", "OMEGA"]) {
    const k = VARS[v].series, sc = CAT.variables[v].series_scale, arr = new Float32Array(T);
    for (let t = 0; t < T; t++) { const raw = dv.getUint16((t * 3 + k) * 2, true); arr[t] = raw === 65535 ? NaN : raw * sc; }
    out[v] = arr;
  }
  if (seriesCache.size > 40) seriesCache.delete(seriesCache.keys().next().value);
  seriesCache.set(key, out);
  return out;
}
function pickLocation(c) {
  state.pick = c;
  if (!pickMarker) pickMarker = new maplibregl.Marker({ color: "#B85434", scale: 0.75 });
  pickMarker.setLngLat([c.lng, c.lat]).addTo(map);
  renderPickCharts();
}
let pickSeq = 0;
async function renderPickCharts() {
  const c = state.pick, seq = ++pickSeq;
  if (!c) return;
  const where = `${Math.abs(c.lat).toFixed(3)}°${c.lat >= 0 ? "N" : "S"}, ${Math.abs(c.lng).toFixed(3)}°${c.lng >= 0 ? "E" : "W"}`;
  $("#srKicker").textContent = `36 km cell · row ${c.row}, column ${c.col}`; $("#srTitle").textContent = where; $("#srReset").hidden = false;
  $("#srSub").textContent = "Reading the cell's record…";
  let S;
  try { S = await getSeries(c.row, c.col); } catch (e) { $("#srSub").textContent = "Could not read the series store: " + e.message; return; }
  if (seq !== pickSeq) return;
  if (!S) {
    $("#srSub").textContent = "No retrieval at this cell in any day — it is water, ice, or never thawed under a 6 a.m. overpass.";
    chartModel = null; $("#chart").replaceChildren(el("p", { class: "chart-empty" }, "No data at this cell.")); renderSeriesTable();
    $("#recordBox").hidden = true; recordModel = null;
    return;
  }
  const v = state.var, y = state.seriesYear, T = CAT.record.n, vv = V();
  const nDays = S.SM.reduce((a, x) => a + (Number.isNaN(x) ? 0 : 1), 0);
  // per calendar month at this cell: mean (over all years) and the mean number of retrieval days
  const calSum = new Float64Array(12), calN = new Float64Array(12), calDays = new Float64Array(12), yearsPerMonth = Array.from({ length: 12 }, () => new Set());
  for (let t = 0; t < T; t++) {
    const iso = isoAt(t), mo = +iso.slice(5, 7) - 1;
    yearsPerMonth[mo].add(iso.slice(0, 4));
    if (v !== "N") { const x = S[v][t]; if (!Number.isNaN(x)) { calSum[mo] += x; calN[mo]++; } }
    if (!Number.isNaN(S.SM[t])) calDays[mo]++;
  }
  const clim = MON.map((_, i) => (v === "N" ? (yearsPerMonth[i].size ? calDays[i] / yearsPerMonth[i].size : null) : (calN[i] ? calSum[i] / calN[i] : null)));
  if (v === "N") {
    const yr = MON.map((_, i) => { let k = 0; const i0 = dayIndex(`${y}-${pad2(i + 1)}-01`), nd = daysIn(+y, i + 1); for (let t = i0; t < Math.min(T, i0 + nd); t++) if (t >= 0 && !Number.isNaN(S.SM[t])) k++; return i0 + nd <= 0 || i0 >= T ? null : k; });
    $("#srSub").textContent = `${fmt(nDays)} of the record's ${fmt(CAT.record.with_tiles)} days have a retrieval here. Bars: days per month in ${y}; grey: the ${RECORD_YEARS()} average.`;
    chartModel = { title: `Days with a retrieval at ${where}`, n: 12, ticks: monthTicks(), units: "days", digits: 0, rowLabel: "Month", rowName: (i) => `${y}-${pad2(i + 1)}`, csvKey: "month",
      tipHead: (i) => MONL[i], endLabels: true, rightPad: 44, yMax: 31, noneText: "—", note: `cell row ${c.row} column ${c.col}, centre ${where}`,
      series: [{ name: y, short: y, color: "#2E7BA8", values: yr, csvName: `days_${y}` }, { name: `${RECORD_YEARS()} mean`, short: "mean", color: "#8C8A80", values: clim, csvName: "days_mean" }] };
  } else {
    const i0 = dayIndex(`${y}-01-01`), nd = daysIn(+y, 12) === 31 && doy(`${y}-12-31`) === 366 ? 366 : 365;
    const yr = Array.from({ length: nd }, (_, k) => { const t = i0 + k; if (t < 0 || t >= T) return null; const x = S[v][t]; return Number.isNaN(x) ? null : x; });
    const climDaily = new Array(nd).fill(null);
    MON.forEach((_, i) => { const mid = doy(`${y}-${pad2(i + 1)}-15`) - 1; if (mid < nd) climDaily[mid] = clim[i]; });
    const nObs = yr.filter((x) => x != null).length;
    const dayTicks = MON.map((mn, i) => [doy(`${y}-${pad2(i + 1)}-01`) - 1, mn[0]]);
    $("#srSub").textContent = `${nObs} days of ${y} have a retrieval here (${fmt(nDays)} in the whole record). The grey line is this cell's own ${RECORD_YEARS()} mean by calendar month.`;
    chartModel = { title: `Daily ${vv.name.toLowerCase()} at ${where}, ${y}`, n: nd, ticks: dayTicks, units: vv.units, digits: vv.digits, rowLabel: "Day", rowName: (i) => isoAt(i0 + i), csvKey: "date",
      tipHead: (i) => dLabel(isoAt(i0 + i)), skipEmptyRows: true, note: `cell row ${c.row} column ${c.col}, centre ${where}; series-store values (precision ${CAT.variables[v].series_scale})`,
      series: [{ name: y, color: "#2E7BA8", values: yr, width: 1.5, csvName: `${v}_${y}` }, { name: `${RECORD_YEARS()} mean by month`, color: "#8C8A80", values: climDaily, spanGaps: true, dots: true, width: 1.5, dash: "4 3", csvName: `${v}_monthly_mean` }] };
  }
  drawLine($("#chart"), chartModel); renderSeriesTable();
  // the full record
  $("#recordBox").hidden = false;
  if (v === "N") {
    const n = CAT.months.length, vals = CAT.months.map((m) => { let k = 0; const i0 = dayIndex(m.ym + "-01"); for (let t = i0; t < Math.min(T, i0 + m.days); t++) if (!Number.isNaN(S.SM[t])) k++; return k; });
    recordModel = { pick: c, where, S, title: `Days with a retrieval per month at ${where}`, n, units: "days", digits: 0, yMax: 31, yLines: 3, height: 150, rowLabel: "Month", rowName: (i) => CAT.months[i].ym, csvKey: "month",
      ticks: CAT.months.map((m, i) => [i, m.ym.slice(0, 4)]).filter(([i]) => CAT.months[i].ym.endsWith("-01")).map(([i, yy]) => [i, yy.slice(2)]), tickMarks: true,
      tipHead: (i) => ymLabel(CAT.months[i].ym), noneText: "—", series: [{ name: "days", color: "#2E7BA8", values: vals, width: 1.5, csvName: "days" }] };
    $("#rcSub").textContent = `Retrieval days per month over the whole record.`;
  } else {
    const vals = Array.from(S[v], (x) => (Number.isNaN(x) ? null : x));
    const ticks = []; for (let yy = +CAT.record.first.slice(0, 4) + 1; yy <= +CAT.record.last.slice(0, 4); yy++) ticks.push([dayIndex(`${yy}-01-01`), String(yy).slice(2)]);
    recordModel = { pick: c, where, S, title: `Daily ${vv.name.toLowerCase()} at ${where}, ${RECORD_YEARS()}`, n: T, units: vv.units, digits: vv.digits, yLines: 2, height: 150, rowLabel: "Date", rowName: (i) => isoAt(i), csvKey: "date",
      ticks, tickMarks: true, tipHead: (i) => dLabel(isoAt(i)), skipEmptyRows: true, series: [{ name: vv.short, color: "#2E7BA8", values: vals, width: 1, csvName: v }] };
    $("#rcSub").textContent = `${fmt(nDays)} of ${fmt(CAT.record.n)} days have a retrieval here. Gaps are days without a 6 a.m. overpass, frozen soil, MPDI ≤ 0.002, or SMAP outages.`;
  }
  drawLine($("#chartRecord"), recordModel);
  $("#rcTable").replaceChildren(tableOf(recordModel));
}
function recordCSV() {
  const R = recordModel; if (!R) return "";
  const c = R.pick, T = CAT.record.n, S = R.S;
  const rows = [];
  for (let t = 0; t < T; t++) {
    const a = S.SM[t], b = S.VOD[t], o = S.OMEGA[t];
    rows.push([isoAt(t), Number.isNaN(a) ? "" : a.toFixed(4), Number.isNaN(b) ? "" : b.toFixed(4), Number.isNaN(o) ? "" : o.toFixed(4)].join(","));
  }
  return [`# HDCA second-stage retrieval at EASE-Grid 2.0 36 km cell row ${c.row}, column ${c.col} (centre ${c.lat.toFixed(4)}N ${c.lng.toFixed(4)}E), data version ${CAT.version}`,
    "# Values from the portal's series store (precision 0.0001 for SM and VOD, 0.0002 for OMEGA). Use the NetCDF files for analysis.",
    "# Empty = no retrieval that day (no 6 a.m. overpass, Teff <= 273.15 K, MPDI <= 0.002, or no SMAP file). OMEGA above 1 is kept as retrieved.",
    "date,SM_m3m3,VOD,OMEGA", ...rows].join("\n") + "\n";
}

/* ───────────────────────────── calendar of the record ───────────────────────────── */
function renderCalendar() {
  const box = $("#cal"); box.replaceChildren(el("span"));
  MON.forEach((mn) => box.append(el("span", { class: "cal-h" }, mn[0])));
  const y0 = +CAT.record.first.slice(0, 4), y1 = +CAT.record.last.slice(0, 4);
  const cls = (c) => COVER_STEPS[clamp(Math.floor(c * 5), 0, 4)];
  const selYm = state.mode === "month" ? state.ym : state.mode === "day" ? state.day.slice(0, 7) : null;
  for (let y = y0; y <= y1; y++) {
    box.append(el("span", { class: "cal-y train" }, String(y)));
    for (let mo = 1; mo <= 12; mo++) {
      const ym = `${y}-${pad2(mo)}`, r = monthByYm.get(ym);
      let node, lines;
      if (!r) {
        node = el("span", { class: "cal-c none" });
        lines = [ymLabel(ym), "before the record begins"];
      } else if (r.with_data === 0) {
        node = el("span", { class: "cal-c pending", tabindex: "0" });
        lines = [ymLabel(ym), "no SMAP files this month"];
      } else {
        node = el("button", { class: "cal-c built" + (selYm === ym ? " sel" : ""), style: `background:${cls(r.with_data / r.days)}`,
          "aria-label": `${ymLabel(ym)}, ${r.with_data} of ${r.days} days`,
          onclick: () => { stopPlay(); state.mode = "month"; state.ym = ym; state.seriesYear = ym.slice(0, 4); applyLayer(); if (state.pick) renderPickCharts(); } });
        const sv = state.var === "N" ? "SM" : state.var;
        lines = [ymLabel(ym), `${r.with_data} of ${r.days} days have a SMAP file`, `${fmt(r.cover * 100, 1)}% of land cells retrieved · mean ${VARS[sv].short} ${fmt(r[sv], VARS[sv].digits)}`];
      }
      const tipNodes = () => [el("div", { class: "t-h" }, lines[0]), ...lines.slice(1).map((s) => el("div", {}, s))];
      node.addEventListener("pointerenter", (e) => showTip(tipNodes(), e.clientX, e.clientY));
      node.addEventListener("pointerleave", hideTip);
      node.addEventListener("focus", () => { const b = node.getBoundingClientRect(); showTip(tipNodes(), b.left, b.top); });
      node.addEventListener("blur", hideTip);
      box.append(node);
    }
  }
  $("#calSub").textContent = `${fmt(CAT.record.with_tiles)} daily files from ${dLabel(CAT.record.first)} to ${dLabel(CAT.record.last)}; ${CAT.record.missing.length} days have none. Click a month to show its mean.`;
  $("#calLegend").replaceChildren(
    el("span", {}, ["Days with a file: ", ...COVER_STEPS.map((c) => el("i", { style: `background:${c}` })), " few → all"]),
    el("span", {}, [el("i", { style: "box-shadow:inset 0 0 0 1px #D9D5C7;background:#FAF9F5" }), "no files"]),
    el("span", {}, [el("i", { style: "background:radial-gradient(circle,#D9D5C7 1.5px,transparent 2px)" }), "before the record"]));
}

/* ───────────────────────────── download + code ───────────────────────────── */
const nasRoot = () => (CFG.nasPath ? CFG.nasPath.replace(/\/$/, "") : "");
const fileAddress = (rel) => (CFG.ncBase ? CFG.ncBase.replace(/\/$/, "") + "/" + rel : nasRoot() ? nasRoot() + "/" + rel : rel);
const dayPath = (d) => `Retrieved_2nd/${d.slice(0, 4)}/${d.slice(0, 4)}.${d.slice(5, 7)}.${d.slice(8, 10)}/HDCA_2nd_${d.replace(/-/g, "")}.nc`;
function renderDownload() {
  const notice = $("#dlNotice"); notice.replaceChildren();
  if (CFG.ncBase) notice.append("Files download directly from the links below.");
  else {
    notice.append(el("b", {}, "The NetCDF files are not in a public repository yet. "),
      "A DOI link will be added here when they are deposited; until then write to ", el("a", { href: "mailto:" + CFG.contactEmail }, CFG.contactEmail), " for access.");
    if (nasRoot()) notice.append(el("br"), "Lab members: the files are on the lab storage under ", el("code", {}, nasRoot() + "/"), " (CPU server).");
  }
  const src = CAT.source;
  $("#dlMerged tbody").replaceChildren(el("tr", {}, [
    el("td", { class: "mono" }, CFG.ncBase ? el("a", { href: fileAddress(src.merged_file) }, src.merged_file.split("/").pop()) : fileAddress(src.merged_file)),
    el("td", { class: "num" }, fmtBytes(src.merged_bytes)),
    el("td", {}, `time ${fmt(CAT.record.n)} × y 406 × x 964`),
    el("td", {}, "SM, VOD, OMEGA, TBv, TBh, Teff, latitude, longitude")]));
  const sel = $("#dlYear");
  sel.replaceChildren(el("option", { value: "" }, "All years"), ...src.years.map((y) => el("option", { value: String(y.year) }, String(y.year))));
  const body = $("#dlTable tbody");
  const draw = () => {
    const rows = src.years.filter((y) => !sel.value || String(y.year) === sel.value);
    body.replaceChildren(...rows.map((y) => el("tr", {}, [el("td", {}, String(y.year)), el("td", { class: "num" }, String(y.files)),
      el("td", { class: "num", title: y.missing.join(", ") }, String(y.missing.length)), el("td", { class: "num" }, fmtBytes(y.bytes)),
      el("td", { class: "mono" }, fileAddress(`Retrieved_2nd/${y.year}/`))])));
    const files = rows.reduce((a, y) => a + y.files, 0), bytes = rows.reduce((a, y) => a + y.bytes, 0);
    $("#dlTotal").textContent = `${fmt(files)} files · ${fmtBytes(bytes)}`;
    const miss = rows.flatMap((y) => y.missing);
    $("#dlMissing").textContent = miss.length ? `Days without a file (${miss.length}): ${spans(miss)}.` : "Every day in this range has a file.";
  };
  sel.onchange = draw; draw();
  $("#dlCopy").onclick = (e) => copyText(dayList.filter((d) => !sel.value || d.d.startsWith(sel.value)).map((d) => fileAddress(dayPath(d.d))).join("\n"), e.currentTarget);
}
/* "2019-06-20 – 2019-07-23, 2022-08-06 – 2022-09-21, 2015-05-13" */
function spans(days) {
  const out = []; let s = null, p = null;
  for (const d of [...days].sort()) {
    if (s && dayIndex(d) === dayIndex(p) + 1) { p = d; continue; }
    if (s) out.push(s === p ? dLabel(s) : `${dLabel(s)} – ${dLabel(p)}`);
    s = p = d;
  }
  if (s) out.push(s === p ? dLabel(s) : `${dLabel(s)} – ${dLabel(p)}`);
  return out.join(", ");
}
function renderCode() {
  const base = CFG.ncBase ? CFG.ncBase.replace(/\/$/, "") : nasRoot() || "/path/to/HDCA";
  $("#codePt").textContent =
`import numpy as np
import xarray as xr

ds = xr.open_dataset("${base}/${CAT.source.merged_file}")       # 2015-04-01 … ${CAT.record.last}, daily
lon, lat = -69.27, -12.83                                        # Tambopata, Amazon

# the grid is EASE-Grid 2.0 (equal-area), so pick the cell whose centre is nearest
d2 = (ds.latitude - lat) ** 2 + (ds.longitude - lon) ** 2
iy, ix = np.unravel_index(int(d2.fillna(np.inf).argmin()), d2.shape)
cell = ds.isel(y=iy, x=ix)

sm = cell["SM"]                                                 # m3/m3, NaN where no retrieval
print(float(cell.latitude), float(cell.longitude), int(sm.notnull().sum()), "days with data")
monthly = sm.resample(time="1MS").mean()                         # monthly mean of the retrieved days`;
  $("#codeMap").textContent =
`import glob
import xarray as xr

files = sorted(glob.glob("${base}/Retrieved_2nd/2020/2020.07.*/HDCA_2nd_*.nc"))
ds = xr.open_mfdataset(files, combine="nested", concat_dim="time")

sm_july = ds["SM"].mean("time")                                 # mean over the days each cell was retrieved
n_days = ds["SM"].notnull().sum("time")                         # how many days went into each cell
sm_july = sm_july.where(n_days >= 5)                            # drop cells with fewer than five days

# a quick look: cell centres are 2-D coordinates
sm_july.plot(x="longitude", y="latitude", vmin=0.02, vmax=0.5, cmap="YlGnBu")`;
  $("#codeQc").textContent =
`# Screen before analysis
ok = (ds["SM"] > 0.02) & (ds["SM"] < 0.6)                        # 0.02 is the lower bound of the search
ok &= ds["VOD"] < 1.5                                            # 1.5 is the upper bound of the search
ok &= ds["OMEGA"] <= 1.0                                         # omega above 1 is not physical (about 4 % of retrievals)
sm = ds["SM"].where(ok)

# the input brightness temperatures and soil temperature travel with the retrieval
mpdi = (ds["TBv"] - ds["TBh"]) / (ds["TBv"] + ds["TBh"])        # cells with MPDI <= 0.002 were not retrieved`;
  document.querySelectorAll(".copy").forEach((b) => { b.onclick = () => copyText($("#" + b.dataset.copy).textContent, b); });
}

/* ───────────────────────────── tabs, embed, wiring ───────────────────────────── */
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => { const on = t.dataset.tab === name; t.classList.toggle("on", on); t.setAttribute("aria-selected", on); });
  document.querySelectorAll(".tabpane").forEach((p) => { const on = p.id === "tab-" + name; p.hidden = !on; p.classList.toggle("on", on); });
  if (name === "explore" && map) map.resize();
  hideTip(); sendHeight();
}
function sendHeight() {
  if (window.parent === window) return;
  const h = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  window.parent.postMessage({ type: "portalHeight", height: h }, "*");
}
function wire() {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  document.querySelectorAll("#varSeg button").forEach((b) => b.addEventListener("click", () => {
    if (b.disabled) return; stopPlay(); state.var = b.dataset.var;
    if (state.var === "N" && state.mode === "day") { state.mode = "month"; state.ym = state.day.slice(0, 7); }
    applyLayer();
  }));
  document.querySelectorAll("#modeSeg button").forEach((b) => b.addEventListener("click", () => { if (b.disabled) return; stopPlay(); state.mode = b.dataset.mode; applyLayer(); }));
  document.querySelectorAll("#scaleSeg button").forEach((b) => b.addEventListener("click", () => { state.scale = b.dataset.scale; applyLayer(); }));
  $("#opacity").addEventListener("input", (e) => map.setPaintProperty("data", "raster-opacity", e.target.value / 100));
  const places = [...SITES.map((s) => [...s, "site"]), ...REGIONS.map((r) => [...r, "region"])];
  const og1 = el("optgroup", { label: "Validation sites in the paper" }), og2 = el("optgroup", { label: "Regions" });
  places.forEach(([name, , , kind], i) => (kind === "site" ? og1 : og2).append(el("option", { value: i }, name)));
  $("#jump").append(og1, og2);
  $("#jump").onchange = (e) => {
    const p = places[+e.target.value];
    if (e.target.value !== "" && p) map.flyTo({ center: [p[1], p[2]], zoom: p[3] === "site" ? 5.2 : 3.6, duration: 1700 });
    e.target.value = "";
  };
  $("#btnGlobe").onclick = () => map.flyTo({ ...GLOBE, duration: 1800 });
  $("#srReset").onclick = () => { state.pick = null; recordModel = null; $("#recordBox").hidden = true; if (pickMarker) pickMarker.remove(); renderGlobalSeries(); };
  $("#rcTableBtn").onclick = (e) => { const t = $("#rcTable"); t.hidden = !t.hidden; e.currentTarget.textContent = t.hidden ? "Show table" : "Hide table"; e.currentTarget.setAttribute("aria-expanded", String(!t.hidden)); sendHeight(); };
  $("#rcCsv").onclick = () => download(`hdca_cell_r${state.pick ? state.pick.row : 0}_c${state.pick ? state.pick.col : 0}.csv`, recordCSV(), "text/csv");
  $("#srTableBtn").onclick = (e) => { const t = $("#srTable"); t.hidden = !t.hidden; e.currentTarget.textContent = t.hidden ? "Show table" : "Hide table"; e.currentTarget.setAttribute("aria-expanded", String(!t.hidden)); sendHeight(); };
  $("#srCsv").onclick = () => { if (chartModel) download("hdca_series.csv", csvOf(chartModel), "text/csv"); };
  /* In-page links of the About tab: inside an auto-height frame the frame itself never scrolls, so
     ask the browser to bring the heading into view (it scrolls whichever ancestor can). */
  document.querySelectorAll(".toc a").forEach((lnk) => lnk.addEventListener("click", (e) => {
    const target = document.getElementById(lnk.getAttribute("href").slice(1));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" });
  }));
  addEventListener("resize", sendHeight);
  if (window.ResizeObserver) new ResizeObserver(sendHeight).observe(document.body);
}
async function main() {
  try {
    await loadCatalog();
  } catch (e) {
    $("#bootMsg").textContent = e.message; document.querySelector(".boot-mark").style.display = "none";
    return;
  }
  const f = CAT.record.first, l = CAT.record.last;
  $("#factRecord").textContent = `${MON[+f.slice(5, 7) - 1]} ${f.slice(0, 4)} – ${MON[+l.slice(5, 7) - 1]} ${l.slice(0, 4)}`;
  $("#abRecord").textContent = `${dLabel(f)} to ${dLabel(l)}`;
  const om = CAT.stats && CAT.stats.OMEGA; if (om && om.n) $("#abOmega").textContent = `${(om.above_1 / om.n * 100).toFixed(1)} %`;
  const outages = spans(CAT.record.missing.filter((d) => (d >= "2019-06-20" && d <= "2019-07-23") || (d >= "2022-08-07" && d <= "2022-09-21")));
  $("#abMissing").textContent = `${CAT.record.missing.length} of the ${fmt(CAT.record.n)} days in the record have no SMAP file, almost all in two SMAP outages (${outages}); the Download tab lists every missing day. On other days about half of the land has a 6 a.m. overpass.`;
  $("#glRecord").textContent = `${dLabel(f)} – ${dLabel(l)} · ${fmt(CAT.record.with_tiles)} days with data`;
  $("#abContact").textContent = CFG.dataContact || "";
  $("#abMail").textContent = CFG.contactEmail; $("#abMail").href = "mailto:" + CFG.contactEmail;
  $("#footVer").textContent = `Data version ${CAT.version}`;
  wire(); renderDownload(); renderCode();
  const spec = layerSpec(); specsByKey.set(spec.key, spec);
  const st = { n: 0, mean: null, cover: 0, p02: 0, p98: spec.step, hist: new Float64Array(255) };
  const [lo, hi] = currentRange(spec, st), { key, lut } = lutFor(spec, lo, hi);
  current = { spec, lut, lutKey: key, stats: st, field: null, lo, hi };
  initMap();
  await applyLayer();
  const tab = Q.get("tab"); if (tab && document.getElementById("tab-" + tab)) showTab(tab);
  sendHeight();
}
main();
})();
