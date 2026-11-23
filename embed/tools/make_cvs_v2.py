#!/usr/bin/env python3
"""make_cvs_v2.py HAMPYEONG_REPO OUTDIR [test] — frames for the Core Validation Site card (cvs-v3; cvs-v2 with CVS_NOTICE=0).

The first loop showed the 1 km cell from the drone in true colour, flight after flight. This one shows the three ways the
site is measured, in the order of the card's own facts, from what the Hampyeong portal itself publishes:

  1. the drone   one flight day (25 May 2026) through four sensors: true colour, NDVI, thermal infrared, LiDAR surface
                 height, each wiped over the last;
  2. the ground  the picture moves south to the paddies, where most stations stand, and the season runs from that flight
                 to 28 October 2026, one day a frame: the picture is the nearest clean true-colour flight, every
                 station's dot takes the colour of its soil moisture on that day (the portal's own dry-to-wet scale),
                 and a chart draws every station's daily series, their mean, and the daily rain above them;
  3. satellites  the camera pulls back to the whole cell and two kilometres round it: HLS NDVI at 30 m, Sentinel-1 radar
                 at 10 m, then NISAR's soil moisture (beta) as its 200 m cells over the drone picture, all 47 stations marked.

Inputs, all under HAMPYEONG_REPO/data: uav/ (catalog.csv and the layers' PNGs), satellites/ (the same), models/GPM_IMERG.csv,
in_situ/stations.csv and in_situ/daily_sm.json. It draws whatever the checkout holds, so see first that it is what the portal
publishes (embed/tools/README.md gives the two git commands). CVS_INSITU=<folder> reads the two in-situ files from another
folder (a refreshed copy that is not in the repository yet). CVS_SCALE=<k> draws k times larger frames (1: 960 x 540, encoded 768 wide
for the card; 1.3333333: 1280 x 720 for the home page's reel; the drone mosaic is about 1 m, so no larger). CVS_PANEL=bottom
puts the chart at the foot of the picture instead of the top (the top keeps it clear of the caption at every card size).
CVS_RANGE=<from>:<to> draws a part of the frames, so that several processes can share the work.

The Sentinel-1 scene is modified Copernicus Sentinel data, and the Copernicus licence asks for the notice "Contains modified
Copernicus Sentinel data <year>" wherever it is shown to the public. The lab head chose (2026-11-23) to have it in the
picture, small, at the top right while the scene shows (from its wipe to the end of the loop): that is cvs-v3.
CVS_NOTICE=0 leaves it out and draws the loop as published on 2026-11-22 (cvs-v2).

The picture is drawn to scale (metres east and south of the mosaic's north-west corner). The layers' PNGs are regular in
degrees, about 0.91 m east-west by 1.11 m north-south a pixel here; the first loop used the pixels as they are, which
drew the site a fifth too wide.

The chart reaches from edge to edge, so the card must show the whole picture (no `hd-fill` on its media box: in the
page's row layout that class crops a picture to the box).

Writes f_0000.png ... and timeline.json (frame rate, frame count, the caption times). With `test`, a handful of frames."""
import sys, os, csv, json, math, datetime as D
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection

repo, out = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser(); test = "test" in sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
K = float(os.environ.get("CVS_SCALE", "1"))
W, H, FPS = int(round(960 * K)), int(round(540 * K)), 24
INSITU = Path(os.environ.get("CVS_INSITU", repo / "data/in_situ")).expanduser()
PANEL_AT = os.environ.get("CVS_PANEL", "top")
BG = (15, 19, 24)
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ── what is shown ──────────────────────────────────────────────────────────────────────────────────────────────────
DAY1 = "20260525"                                   # the flight day seen through four sensors (the one with a midday thermal map)
FLIGHTS = ["20260525", "20260724", "20260817", "20260829", "20260915", "20260922", "20261009", "20261016"]   # clean true-colour flights of the season
D0, D1 = D.date(2026, 5, 25), D.date(2026, 10, 28)  # the season's clock: every station's record reaches 28 October (45 to 47 a day)
HLS = "HP_SAT_NDVI_20261015_0205.png"               # satellites/: scenes near the last flight, without gaps
S1 = os.environ.get("CVS_S1", "HP_SAT_S1_VV_20261012_2132.png")
NISAR = "HP_SAT_SM_20260118_1026.png"               # NISAR's soil moisture (beta): the latest scene the portal has
DAYS = [D0 + D.timedelta(n) for n in range((D1 - D0).days + 1)]; ND = len(DAYS)
SEG = [("open", 16), ("w_ndvi", 12), ("h_ndvi", 17), ("w_tir", 12), ("h_tir", 17), ("w_lidar", 12), ("h_lidar", 17), ("w_back", 12),
       ("rise", 14), ("clock", ND), ("hold", 10), ("out", 22), ("h_hls", 20), ("w_s1", 12), ("h_s1", 20),
       ("w_nisar", 12), ("h_nisar", 32), ("close", 12)]
START, _n = {}, 0
for _name, _len in SEG: START[_name] = _n; _n += _len
N, LEN = _n, dict(SEG)

# ── the ground: metres from the north-west corner of the flights' common grid ───────────────────────────────────────
GRID = dict(n=35.020053, s=35.010096, e=126.556309, w=126.545354)       # uav/catalog.csv, the full-coverage flights
PHI = math.radians((GRID["n"] + GRID["s"]) / 2)
MY = 111132.92 - 559.82 * math.cos(2 * PHI) + 1.175 * math.cos(4 * PHI)  # metres in a degree of latitude here
MX = 111412.84 * math.cos(PHI) - 93.5 * math.cos(3 * PHI) + 0.118 * math.cos(5 * PHI)
wx = lambda lon: (lon - GRID["w"]) * MX
wy = lambda lat: (GRID["n"] - lat) * MY
def view(cx, cy, w): h = w * H / W; return (cx - w / 2, cy - h / 2, w, h)
VA = view(500.0, 553.0, 940.0)             # the drone's stage: the village, the hill, the fields between
VC = view(500.0, float(os.environ.get("CVS_CY", "768")), 940.0)   # the stations' stage: the paddies south of the road (27 stations in
                                           # the window: 5 behind the chart and 1 just beside it are hidden while the chart is up, so
                                           # none is cut by its edge; every flight covers it)
VB = view(500.0, 552.3, 2000.0)            # the satellites' stage: the whole mosaic in the middle, HLS and Sentinel-1 fill the rest
CELL = dict(n=35.01984406, s=35.01030731, e=126.55601501, w=126.54563904)      # the 1 km EASE-Grid 2.0 cell (grid/nested_grids.json)
smooth = lambda t: t * t * (3 - 2 * t)
def between(va, vb, t):
    w = va[2] * (vb[2] / va[2]) ** t; cx = (va[0] + va[2] / 2) * (1 - t) + (vb[0] + vb[2] / 2) * t; cy = (va[1] + va[3] / 2) * (1 - t) + (vb[1] + vb[3] / 2) * t
    return view(cx, cy, w)

# ── layers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
UAV = {(r["product"], r["date"].replace("-", "")): r for r in csv.DictReader(open(repo / "data/uav/catalog.csv"))}
SAT = {r["file"]: r for r in csv.DictReader(open(repo / "data/satellites/catalog.csv"))}
box = lambda r: (wx(float(r["w"])), wy(float(r["n"])), wx(float(r["e"])), wy(float(r["s"])))
def day(iso): d = D.date.fromisoformat(iso[:10]); return f"{d.day} {MON[d.month - 1]} {d.year}"
_lay = {}
def layer(kind, key):
    """(premultiplied RGBA image, its box on the ground). The layers are published a little transparent for the portal's
    map (alpha 220 or 200 of 255); here a layer is the picture itself, so it is drawn opaque wherever it has a value."""
    if (kind, key) not in _lay:
        r = UAV[key] if kind == "uav" else SAT[key]
        a = np.asarray(Image.open(repo / "data" / ("uav" if kind == "uav" else "satellites") / r["file"]).convert("RGBA")).copy()
        has = a[..., 3] > 0
        if kind == "sat": has &= a[..., :3].sum(-1) > 0                  # a cell without a value is black in the NISAR files
        a[..., 3] = np.where(has, 255, 0); a[~has, :3] = 0
        _lay[(kind, key)] = (Image.fromarray(a).convert("RGBa"), box(r))
    return _lay[(kind, key)]
def place(lay, v, resample=Image.LANCZOS):
    """The layer as seen in the view v, an RGBA frame (clear where the layer is not). The frame's pixels are whole; the
    part of the layer under them is taken exactly, so nothing trembles while the view moves."""
    im, b = lay; vx0, vy0, vw, vh = v
    fx0, fy0, fx1, fy1 = (b[0] - vx0) / vw * W, (b[1] - vy0) / vh * H, (b[2] - vx0) / vw * W, (b[3] - vy0) / vh * H
    dx0, dy0 = max(0, math.ceil(fx0 - 1e-6)), max(0, math.ceil(fy0 - 1e-6)); dx1, dy1 = min(W, math.floor(fx1 + 1e-6)), min(H, math.floor(fy1 + 1e-6))
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if dx1 <= dx0 or dy1 <= dy0: return frame
    u = lambda d: (d - fx0) / (fx1 - fx0) * im.width
    w_ = lambda d: (d - fy0) / (fy1 - fy0) * im.height
    frame.paste(im.resize((dx1 - dx0, dy1 - dy0), resample, box=(u(dx0), w_(dy0), u(dx1), w_(dy1))).convert("RGBA"), (dx0, dy0))
    return frame
def over(*layers, dim=1.0):
    """Layers laid on the dark ground in turn; RGB as a float array."""
    im = Image.new("RGBA", (W, H), BG + (255,))
    for l in layers: im.alpha_composite(l)
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    return a * dim if dim != 1.0 else a
_pic = {}
def pic(product, date, v):
    """A drone layer in one of the two settled windows (kept; the layer must cover the window completely)."""
    if (product, date, v) not in _pic:
        lay = place(layer("uav", (product, date)), v)
        assert lay.getchannel("A").getextrema()[0] == 255, f"the {product} layer of {date} does not cover the window {v}"
        _pic[(product, date, v)] = over(lay)
    return _pic[(product, date, v)]
moving = lambda product, date, v: over(place(layer("uav", (product, date)), v))
img = lambda a: Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
def wipe(a, b, t):
    """b comes in over a from the left, behind a bright edge."""
    m = 40 * K; x = (W + 2 * m) * smooth(t) - m; xs = np.arange(W, dtype=np.float32) + 0.5
    mask = np.clip((x - xs) / (1.5 * K) + 0.5, 0, 1)[None, :, None]
    o = a * (1 - mask) + b * mask
    d = (xs - x) / K; glow = (0.85 * np.exp(-(d / 1.3) ** 2) + 0.20 * np.exp(-(d / 9.0) ** 2))[None, :, None]
    return o + (255 - o) * np.clip(glow, 0, 1)

# ── stations and their soil moisture ───────────────────────────────────────────────────────────────────────────────
ST = [(r["station_id"], wx(float(r["lon"])), wy(float(r["lat"]))) for r in csv.DictReader(open(INSITU / "stations.csv")) if r.get("station_id")]
_daily = json.load(open(INSITU / "daily_sm.json"))["byDate"]
SM = np.full((len(ST), ND), np.nan)
for j, d in enumerate(DAYS):
    row = _daily.get(d.isoformat(), {})
    for i, (sid, _, _) in enumerate(ST):
        if isinstance(row.get(sid), (int, float)): SM[i, j] = row[sid]
NREP = np.isfinite(SM).sum(0)
MEAN = np.array([np.nanmean(SM[:, j]) if NREP[j] else np.nan for j in range(ND)])
_rain = {r["date"]: float(r["precip_mm"]) for r in csv.DictReader(open(repo / "data/models/GPM_IMERG.csv")) if r["precip_mm"] not in ("", None)}
RAIN = np.array([_rain.get(d.isoformat(), np.nan) for d in DAYS])
print(f"stations {len(ST)} | days {ND} ({D0} to {D1}) | stations reporting a day: {NREP.min()} to {NREP.max()} | values {np.nanmin(SM):.3f} to {np.nanmax(SM):.3f} | "
      f"mean {np.nanmin(MEAN):.3f} to {np.nanmax(MEAN):.3f} | rain: {np.nansum(RAIN):.0f} mm, wettest day {np.nanmax(RAIN):.1f} mm, days without a value {int(np.isnan(RAIN).sum())}")
assert len(ST) == 47 and NREP.min() >= 40, "the caption and the chart say 47 stations: read the in-situ files again"
SM_STOPS = [(0.00, (120, 60, 20)), (0.33, (220, 160, 60)), (0.66, (80, 170, 220)), (1.00, (20, 60, 160))]     # the portal's smToColor, 0.05 to 0.55 m3/m3
def sm_rgb(v, vmin=0.05, vmax=0.55):
    if v is None or not np.isfinite(v): return (136, 136, 136)
    t = min(1.0, max(0.0, (v - vmin) / (vmax - vmin)))
    for (t0, c0), (t1, c1) in zip(SM_STOPS, SM_STOPS[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0); return tuple(int(round(c0[i] + (c1[i] - c0[i]) * u)) for i in range(3))
    return SM_STOPS[-1][1]
def dots(v, k, vals=None, c=0.0, r=3.6, ring=1.0, rim=1.0, hide=0.0):
    """The stations in the view v at frame k: a white disc in a dark rim, inside it the colour of the station's soil
    moisture (c = 0: none, all white; 1: full), round it a ring that breathes (ring = 0: none). hide is how far the
    chart has come in (0 to 1): the stations behind it go out as it does, so that none shows through it."""
    S = 3; ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov); vx0, vy0, vw, vh = v; q = K * S
    for n, (sid, X, Y) in enumerate(ST):
        px, py = (X - vx0) / vw * W * S, (Y - vy0) / vh * H * S
        if not (-20 * q < px < W * S + 20 * q and -20 * q < py < H * S + 20 * q): continue
        o = 1.0
        if hide > 0 and (PX0 - 9 * K) * S < px < (PX1 + 9 * K) * S and (PY0 - 9 * K) * S < py < (PY1 + 9 * K) * S:
            o = 1 - hide
            if o < 0.02: continue
        if ring > 0:
            ph = 0.5 + 0.5 * math.sin(2 * math.pi * (5 * k / N) + n * 0.61); rr = (7.5 + 3.5 * ph) * q
            dr.ellipse([px - rr, py - rr, px + rr, py + rr], outline=(255, 255, 255, int((70 + 60 * (1 - ph)) * ring * o)), width=max(1, int(round(1.2 * q))))
        r0 = r * q
        dr.ellipse([px - r0 - rim * q, py - r0 - rim * q, px + r0 + rim * q, py + r0 + rim * q], fill=(20, 24, 30, int(200 * o)))
        dr.ellipse([px - r0, py - r0, px + r0, py + r0], fill=(255, 255, 255, int(255 * o)))
        if c > 0 and vals is not None:
            col = sm_rgb(vals[n]); r1 = r0 - 1.3 * q
            dr.ellipse([px - r1, py - r1, px + r1, py + r1], fill=tuple(int(round(255 + (col[i] - 255) * c)) for i in range(3)) + (int(255 * o),))
    return ov.resize((W, H), Image.LANCZOS)

# ── the chart ──────────────────────────────────────────────────────────────────────────────────────────────────────
PH = 208                                                  # the panel's height in a 960 x 540 frame
PX0, PX1 = int(round(24 * K)), int(round(936 * K))
PY0 = int(round(18 * K)) if PANEL_AT == "top" else int(round((480 - PH) * K)); PY1 = PY0 + int(round(PH * K))
INK, DIM, SKY = "#F3F6FA", "#9AA4B2", "#8BD3F7"
YLO, YHI, YT = 0.06, 0.46, [0.1, 0.2, 0.3, 0.4]
RMAX = 48.0                                               # millimetres at the foot of the rain strip (the bars hang from its top)
fam = next((f for f in ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"] if any(ff.name == f for ff in font_manager.fontManager.ttflist)), "DejaVu Sans")
plt.rcParams.update({"font.family": fam, "text.color": INK, "axes.edgecolor": "none", "axes.facecolor": "none", "figure.facecolor": "none"})
_seg = []                                                 # each station's series as coloured pieces, made once
for i in range(len(ST)):
    y = SM[i]; x = np.arange(ND) + 0.5
    p = np.stack([np.stack([x[:-1], y[:-1]], 1), np.stack([x[1:], y[1:]], 1)], 1); ok = np.isfinite(p).all((1, 2))
    _seg.append((p, ok, [tuple(c / 255 for c in sm_rgb((a + b) / 2)) if o else (0, 0, 0) for a, b, o in zip(y[:-1], y[1:], ok)]))
_bg = None
def panel_bg():
    global _bg
    if _bg is None:
        s = 3; im = Image.new("RGBA", ((PX1 - PX0) * s, (PY1 - PY0) * s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=int(14 * K * s), fill=(15, 19, 24, 230), outline=(255, 255, 255, 34), width=max(1, int(round(s * K))))
        _bg = im.resize((PX1 - PX0, PY1 - PY0), Image.LANCZOS)
    return _bg
def chart(j):
    """The panel's drawing with the season up to day j (j = -1: the axes only), RGBA, the panel's size. Rain hangs from
    the top of its own strip, the stations' series and their mean run beneath it."""
    pw, ph = PX1 - PX0, PY1 - PY0; k = K; L, Rm = 62 * k, 62 * k
    fig = plt.figure(figsize=(pw / (100 * k), ph / (100 * k)), dpi=100 * k)
    axes = lambda top, height: fig.add_axes([L / pw, 1 - (top + height) * k / ph, (pw - L - Rm) / pw, height * k / ph])
    rx, ax = axes(47, 22), axes(75, 100); perday = (pw - L - Rm) / ND
    firsts = [n for n, d in enumerate(DAYS) if d.day == 1]
    rx.set_xlim(0, ND); rx.set_ylim(RMAX, 0); rx.set_xticks([]); rx.yaxis.tick_right(); rx.set_yticks([40]); rx.set_yticklabels(["40 mm"], fontsize=10.5, color=DIM)
    rx.tick_params(axis="y", length=0, pad=7)
    rx.axhline(0, color="#FFFFFF", alpha=0.20, lw=1, clip_on=False); rx.axhline(40, color="#FFFFFF", alpha=0.10, lw=1)
    rx.text(-13 * k / (pw - L - Rm), 0.5, "rain", transform=rx.transAxes, ha="right", va="center", fontsize=11.5, color=DIM)
    ax.set_xlim(0, ND); ax.set_ylim(YLO, YHI)
    for y in YT: ax.axhline(y, color="#FFFFFF", alpha=0.10, lw=1)
    ax.set_yticks(YT); ax.set_yticklabels([f"{y:.1f}" for y in YT], fontsize=12.5, color=DIM); ax.tick_params(axis="y", length=0, pad=13)
    ax.set_xticks([n + 15 for n in firsts]); ax.set_xticklabels([MON[DAYS[n].month - 1] for n in firsts], fontsize=14, color=DIM); ax.tick_params(axis="x", length=0, pad=5)
    for a_ in (ax, rx):
        for n in firsts: a_.axvline(n, color="#FFFFFF", alpha=0.07, lw=1)
    grad = np.array([[sm_rgb(v) for _ in range(2)] for v in np.linspace(YHI, YLO, 160)], dtype=np.uint8)     # the scale of the dots, beside the axis it belongs to
    ax.imshow(grad, extent=(-8.5 * k / perday, -3 * k / perday, YLO, YHI), aspect="auto", clip_on=False, zorder=1, interpolation="bilinear")
    ax.set_xlim(0, ND); ax.set_ylim(YLO, YHI)
    if j >= 0:
        rx.bar(np.arange(j + 1) + 0.5, np.nan_to_num(RAIN[: j + 1]), width=0.8, color=SKY, alpha=0.9, linewidth=0, zorder=2)
        for a_ in (ax, rx): a_.axvline(j + 0.5, color="#FFFFFF", alpha=0.22, lw=1, zorder=1)
        for p, ok, cols in _seg:
            sel = ok.copy(); sel[j:] = False
            if sel.any(): ax.add_collection(LineCollection(p[sel], colors=[c for c, s in zip(cols, sel) if s], linewidths=1.0, alpha=0.66, capstyle="round", zorder=3))
        x = np.arange(j + 1) + 0.5
        ax.plot(x, MEAN[: j + 1], color="#0F1318", lw=5.4, alpha=0.6, solid_capstyle="round", zorder=4)
        ax.plot(x, MEAN[: j + 1], color=INK, lw=2.8, solid_capstyle="round", solid_joinstyle="round", zorder=5)
        ax.scatter([j + 0.5], [MEAN[j]], s=260, color=INK, alpha=0.22, linewidths=0, zorder=6)
        ax.scatter([j + 0.5], [MEAN[j]], s=52, color="#FFFFFF", edgecolors="#0F1318", linewidths=1.6, zorder=7)
        d = DAYS[j]; fig.text(1 - 22 * k / pw, 1 - 11 * k / ph, f"{d.day} {MON[d.month - 1]} {d.year}   mean {MEAN[j]:.3f}", ha="right", va="top", fontsize=18.5, color=INK, fontweight="medium")
    fig.text(22 * k / pw, 1 - 14 * k / ph, f"{len(ST)} ground stations: daily soil moisture (m³/m³)", ha="left", va="top", fontsize=15.5, color=INK, fontweight="medium")
    fig.canvas.draw(); rgba = np.asarray(fig.canvas.buffer_rgba()).copy(); plt.close(fig)
    return Image.fromarray(rgba)
def panel(j, a=1.0):
    """The panel as a frame-sized layer, at opacity a; below full opacity it stands a little off its place."""
    off = int(round((1 - a) * 24 * K)) * (-1 if PANEL_AT == "top" else 1)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); lay.alpha_composite(panel_bg(), (PX0, PY0 + off)); lay.alpha_composite(chart(j), (PX0, PY0 + off))
    if a < 1: lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    return lay

# ── the season's picture: the nearest clean flight, dissolving into the next half-way between two flights ───────────
FDAY = [(D.date(int(f[:4]), int(f[4:6]), int(f[6:])) - D0).days for f in FLIGHTS]
HALF = 3.0                                                # days each side of the half-way point
def season(j):
    for n in range(len(FLIGHTS) - 1):
        mid = (FDAY[n] + FDAY[n + 1]) / 2
        if j < mid - HALF: return pic("rgb", FLIGHTS[n], VC)
        if j <= mid + HALF:
            t = smooth((j - (mid - HALF)) / (2 * HALF)); return pic("rgb", FLIGHTS[n], VC) * (1 - t) + pic("rgb", FLIGHTS[n + 1], VC) * t
    return pic("rgb", FLIGHTS[-1], VC)

# ── the satellites' stage ──────────────────────────────────────────────────────────────────────────────────────────
def cell_px(v, s=1):
    vx0, vy0, vw, vh = v
    return ((wx(CELL["w"]) - vx0) / vw * W * s, (wy(CELL["n"]) - vy0) / vh * H * s, (wx(CELL["e"]) - vx0) / vw * W * s, (wy(CELL["s"]) - vy0) / vh * H * s)
def outline(v, a=1.0, grid=False):
    """The 1 km cell's edge in the view v (and, with grid, NISAR's 200 m lines inside it)."""
    S = 3; ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov); x0, y0, x1, y1 = cell_px(v, S); q = K * S
    if grid:
        for n in range(1, 5):
            xx = x0 + (x1 - x0) * n / 5; yy = y0 + (y1 - y0) * n / 5
            dr.line([xx, y0, xx, y1], fill=(255, 255, 255, int(120 * a)), width=max(1, int(round(1.0 * q))))
            dr.line([x0, yy, x1, yy], fill=(255, 255, 255, int(120 * a)), width=max(1, int(round(1.0 * q))))
    dr.rectangle([x0 - 2 * q, y0 - 2 * q, x1 + 2 * q, y1 + 2 * q], outline=(15, 19, 24, int(150 * a)), width=max(1, int(round(4.4 * q))))
    dr.rectangle([x0 - q, y0 - q, x1 + q, y1 + q], outline=(255, 255, 255, int(245 * a)), width=max(1, int(round(2.0 * q))))
    return ov.resize((W, H), Image.LANCZOS)
def inside(v):
    """1 inside the 1 km cell, 0 outside (a soft pixel at its edge)."""
    x0, y0, x1, y1 = cell_px(v); xs = np.arange(W) + 0.5; ys = np.arange(H) + 0.5
    mx = np.clip(np.minimum(xs - x0, x1 - xs) + 0.5, 0, 1); my = np.clip(np.minimum(ys - y0, y1 - ys) + 0.5, 0, 1)
    return (my[:, None] * mx[None, :])[..., None].astype(np.float32)
def faded(lay, a):
    if a >= 1: return lay
    lay = lay.copy(); lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a))); return lay
_st = {}
def stage(name):
    """The three settled pictures of the satellites' stage (without stations), kept."""
    if name not in _st:
        if name == "hls": a = over(place(layer("sat", HLS), VB, Image.NEAREST))
        elif name == "s1": a = over(place(layer("sat", S1), VB, Image.NEAREST))
        else:                                              # NISAR's cells over the drone picture of the cell, the radar scene dark round it
            drone = place(layer("uav", ("rgb", FLIGHTS[-1])), VB); cover = np.asarray(drone.getchannel("A"), dtype=np.float32)[..., None] / 255 * inside(VB)
            a = over(place(layer("sat", S1), VB, Image.NEAREST), dim=0.24) * (1 - cover) + over(drone, dim=0.78) * cover
            cells = place(layer("sat", NISAR), VB, Image.NEAREST); ca = np.asarray(cells.getchannel("A"), dtype=np.float32)[..., None] / 255 * 0.86
            a = a * (1 - ca) + np.asarray(cells.convert("RGB"), dtype=np.float32) * ca
        _st[name] = a
    return _st[name]
def finish(a, *layers):
    im = img(a).convert("RGBA")
    for l in layers: im.alpha_composite(l)
    return im.convert("RGB")

NOTICE = os.environ.get("CVS_NOTICE", "1") != "0"         # the Copernicus notice over the Sentinel-1 part (see the header)
_NFONT = ImageFont.truetype(font_manager.findfont(font_manager.FontProperties(family=fam)), int(round(22 * K)))
def notice(a=1.0):
    """The notice in a small dark box at the top right, beside the 1 km cell (clear of the cell, its stations and the caption
    chip at the foot), at opacity a."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not NOTICE or a <= 0: return lay
    lines = ["Contains modified", "Copernicus Sentinel", f"data {SAT[S1]['date'][:4]}"]
    d = ImageDraw.Draw(lay); asc, desc = _NFONT.getmetrics(); lh = asc + desc
    pad, gap, m = int(round(8 * K)), int(round(2 * K)), int(round(14 * K))
    tw = int(round(max(d.textlength(t, font=_NFONT) for t in lines)))
    x1, y0 = W - m, m; y1 = y0 + 2 * pad + len(lines) * lh + (len(lines) - 1) * gap
    d.rounded_rectangle([x1 - tw - 2 * pad, y0, x1, y1], radius=int(round(7 * K)), fill=(15, 19, 24, int(round(150 * a))))
    for j, t in enumerate(lines):
        d.text((int(round(x1 - pad - d.textlength(t, font=_NFONT))), y0 + pad + j * (lh + gap)), t, font=_NFONT, fill=(232, 237, 243, int(round(240 * a))))
    return lay

# ── the sequence ───────────────────────────────────────────────────────────────────────────────────────────────────
R1, R2 = 6.2, 3.3                                          # the stations' discs: in the season (they carry a colour), from space
far = lambda k: dots(VB, k, r=R2, ring=0, rim=1.5)
def frame(k):
    name = next(n for n, _ in reversed(SEG) if k >= START[n]); i = k - START[name]; L = LEN[name]
    if name == "open": return finish(pic("rgb", DAY1, VA), dots(VA, k))
    if name in ("w_ndvi", "w_tir", "w_lidar", "w_back"):
        a, b = {"w_ndvi": ("rgb", "ndvi"), "w_tir": ("ndvi", "tir"), "w_lidar": ("tir", "lidar"), "w_back": ("lidar", "rgb")}[name]
        return finish(wipe(pic(a, DAY1, VA), pic(b, DAY1, VA), (i + 1) / (L + 1)), dots(VA, k))
    if name in ("h_ndvi", "h_tir", "h_lidar"): return finish(pic(name[2:], DAY1, VA), dots(VA, k))
    if name == "rise":                                     # the picture moves south, the chart comes in, the stations take their colours
        t = smooth((i + 1) / L); v = between(VA, VC, t)
        return finish(moving("rgb", DAY1, v), dots(v, k, SM[:, 0], c=t, r=3.6 + (R1 - 3.6) * t, ring=1 - t, hide=t), panel(-1 if t < 0.5 else 0, t))
    if name == "clock": return finish(season(i), dots(VC, k, SM[:, i], c=1, r=R1, ring=0, hide=1), panel(i))
    if name == "hold": return finish(season(ND - 1), dots(VC, k, SM[:, -1], c=1, r=R1, ring=0, hide=1), panel(ND - 1))
    if name == "out":                                      # the chart leaves, the camera pulls back, the drone picture gives way to the satellite's
        t = smooth((i + 1) / L); v = between(VC, VB, t); gone = min(1.0, t / 0.3); up = smooth(min(1.0, max(0.0, (t - 0.30) / 0.62)))
        a = over(place(layer("sat", HLS), v, Image.NEAREST), faded(place(layer("uav", ("rgb", FLIGHTS[-1])), v), 1 - up))
        layers = [outline(v, min(1.0, t / 0.6)), dots(v, k, SM[:, -1], c=1 - gone, r=R1 + (R2 - R1) * t, ring=0, rim=1 + 0.5 * t, hide=1 - gone)]
        if gone < 1: layers.append(panel(ND - 1, 1 - gone))
        return finish(a, *layers)
    if name == "h_hls": return finish(stage("hls"), outline(VB), far(k))
    if name == "w_s1": return finish(wipe(stage("hls"), stage("s1"), (i + 1) / (L + 1)), outline(VB), far(k), notice(smooth((i + 1) / (L + 1))))
    if name == "h_s1": return finish(stage("s1"), outline(VB), far(k), notice())
    if name == "w_nisar":
        t = (i + 1) / (L + 1); return finish(wipe(stage("s1"), stage("nisar"), t), outline(VB), outline(VB, smooth(t), grid=True), far(k), notice())
    if name == "h_nisar": return finish(stage("nisar"), outline(VB, grid=True), far(k), notice())
    last = np.asarray(frame(START["close"] - 1), dtype=np.float32); first = np.asarray(frame(0), dtype=np.float32); t = smooth((i + 1) / L)
    return img(last * (1 - t) + first * t)

# ── captions: who, when: what ──────────────────────────────────────────────────────────────────────────────────────
_d1 = day(f"{DAY1[:4]}-{DAY1[4:6]}-{DAY1[6:]}")
CAPTIONS = {
    "open": f"Drone, {_d1}: true colour",
    "ndvi": f"Drone, {_d1}: vegetation index (NDVI)",
    "tir": f"Drone, {_d1}: thermal infrared",
    "lidar": f"Drone, {_d1}: LiDAR surface height",
    "ground": f"{len(ST)} stations, {D0.day} {MON[D0.month - 1]}–{day(D1.isoformat())}: soil moisture",
    "hls": f"HLS, {day(SAT[HLS]['date'])}: NDVI at 30 m",
    "s1": f"Sentinel-1, {day(SAT[S1]['date'])}: radar at 10 m",
    "nisar": f"NISAR, {day(SAT[NISAR]['date'])}: soil moisture (beta), 200 m",
}
half = lambda n: START[n] + LEN[n] // 2                    # a caption changes when the wipe is half-way
marks = [(0, "open"), (half("w_ndvi"), "ndvi"), (half("w_tir"), "tir"), (half("w_lidar"), "lidar"), (half("w_back"), "ground"),
         (START["out"] + int(LEN["out"] * 0.55), "hls"), (half("w_s1"), "s1"), (half("w_nisar"), "nisar"), (half("close"), "open")]
caps = [[round(f / FPS, 2), CAPTIONS[c]] for f, c in marks]
(out / "timeline.json").write_text(json.dumps({"fps": FPS, "frames": N, "seconds": round(N / FPS, 2), "W": W, "H": H, "segments": START, "caps": caps}, ensure_ascii=False, indent=1))
print(f"frames {N} | {N / FPS:.2f} s at {FPS} a second | {W} x {H} | chart at the {PANEL_AT}")
for t, c in caps: print(f"  {t:6.2f} s  {c}  ({len(c)} characters)")
if test:
    picks = [0, half("w_ndvi"), START["h_ndvi"] + 3, START["h_tir"] + 3, START["h_lidar"] + 3, START["rise"] + 7, START["clock"] + 20, START["clock"] + 75,
             START["clock"] + 120, START["hold"] + 3, START["out"] + 7, START["out"] + 14, START["h_hls"] + 5, half("w_s1"), START["h_s1"] + 5, half("w_nisar"), START["h_nisar"] + 10, START["close"] + 5]
    for k in picks: frame(k).save(out / f"test_{k:04d}.png")
else:
    lo, hi = (int(a) for a in os.environ.get("CVS_RANGE", f"0:{N}").split(":"))
    for k in range(lo, min(hi, N)): frame(k).save(out / f"f_{k:04d}.png")
print("done")
