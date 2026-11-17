#!/usr/bin/env python3
"""cap_et.py BASE OUTDIR [test] — frames for the ET card: the globe with ET over all land, then down to the Korean Peninsula and into
a 30 m sample area (Pyeongchang), and back. Drawn in software, one settled frame at a time (camera set, tiles in, then a screenshot),
from the public copy of the tiles, as the portal itself draws it.

The lab head asked (2026-11-17) for the loop to open on the globe with ET laid over the whole Earth, and for the 30 m part to be
Pyeongchang. Outside the Korean Peninsula those colours are the portal's background layer, another product (MOD16A2GF): the card
must name it on the picture for as long as it shows (its first caption and its credit line do)."""
import sys, json, math
from pathlib import Path
from playwright.sync_api import sync_playwright
base, out = sys.argv[1], Path(sys.argv[2]); test = "test" in sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
W, H, FPS = 960, 540, 24
CSS = """html, body { background: #0F1318 !important; overflow: hidden !important; }
.mapwrap { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; z-index: 99999 !important; border: 0 !important; border-radius: 0 !important; }
.map-ui, .steps, .nomap-msg, #boot, .maplibregl-control-container, .logos-footer, .page-notice, .fine-tag, .pulse-label { display: none !important; }
.pulse { animation: none !important; }"""

def merc(lng, lat): return ((lng + 180) / 360, (1 - math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi) / 2)
def unmerc(x, y): return (x * 360 - 180, math.degrees(2 * math.atan(math.exp((1 - 2 * y) * math.pi)) - math.pi / 2))
def ease(u): return u * u * (3 - 2 * u)
def ease3(u): return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
def globe_zoom(lat, D): return math.log2(D * math.cos(math.radians(lat)) / 133)          # zoom at which the globe is D px across when centred on lat
def about(P, Cfar, zfar, znear, u):
    """Zoom about the point P: at u = 0 the far view (Cfar, zfar), at u = 1 P in the middle at znear; P glides to the middle of the frame."""
    z = zfar + (znear - zfar) * ease3(u)
    px, py = merc(*P); cx, cy = merc(*Cfar); k = 2 ** (zfar - z) * (1 - ease(u))
    return unmerc(px - (px - cx) * k, py - (py - cy) * k) + (z,)

D0 = 0.9 * H
K0 = (80.0, 18.0); K1 = (127.7, 34.5); PEN = (127.6, 38.0); CH = (128.51588, 37.48177)     # CH: the Pyeongchang sample area (deciduous forest, valleys)
zK0, zK1, zPEN, zCH = globe_zoom(K0[1], D0), globe_zoom(K1[1], D0), 4.95, 12.25              # zPEN: the whole peninsula; zCH: the 6.7 km sample square just inside the frame
def segA(u):                                  # the globe turns to the region with maps, the same size throughout
    e = ease(u); lng = K0[0] + (K1[0] - K0[0]) * e; lat = K0[1] + (K1[1] - K0[1]) * e
    return (lng, lat, globe_zoom(lat, D0))
segB = lambda u: about(PEN, K1, zK1, zPEN, u)                               # down to the peninsula
segC = lambda u: (PEN[0], PEN[1], zPEN + 0.1 * u)                           # a breath
segD = lambda u: about(CH, PEN, zPEN + 0.1, zCH, u)                         # in to the sample square
segE = lambda u: (CH[0], CH[1], zCH + 0.8 * ease(u))                        # and on into its 30 m pixels
segF = lambda u: about(CH, K0, zK0, zCH + 0.8, 1 - u)                       # back out to the globe
SEGS = [("globe", segA, 3.0), ("down", segB, 2.2), ("peninsula", segC, 0.9), ("in", segD, 3.0), ("30 m", segE, 2.0), ("out", segF, 2.6)]
frames, marks, t = [], [], 0.0
for name, f, dur in SEGS:
    n = round(dur * FPS); marks.append((name, round(t, 2), len(frames)))
    for i in range(n): frames.append(f(i / n))
    t += dur
print("frames:", len(frames), "| seconds:", round(len(frames) / FPS, 2), "| segments start at:", marks)
(out / "timeline.json").write_text(json.dumps({"fps": FPS, "frames": len(frames), "segments": marks}))
SET = """async (cam) => { const m = window.__portal.map; m.jumpTo({center: [cam[0], cam[1]], zoom: cam[2]});
  await new Promise((res) => { let done = false; const fin = () => { if (!done) { done = true; res(); } }; m.once('idle', fin); setTimeout(fin, 9000); });
  return m.areTilesLoaded(); }"""
with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"])
    page = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1).new_page()
    page.goto(base, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_function("window.__portal && window.__portal.map && window.__portal.map.loaded()", timeout=90000)
    page.add_style_tag(content=CSS)
    bgv = page.evaluate("""() => { const m = window.__portal.map; m.setPadding({top: 0, bottom: 0, left: 0, right: 0}); m.setMinZoom(0); m.resize();
        for (const id of ['et', 'sat', 'ctx']) if (m.getLayer(id)) m.setPaintProperty(id, 'raster-fade-duration', 0);
        return m.getLayer('ctx') ? m.getLayoutProperty('ctx', 'visibility') : 'no background layer'; }""")
    print("background layer:", bgv, flush=True)
    assert bgv == "visible", "the loop must show the portal's background layer on the globe"
    page.wait_for_timeout(800)
    todo = [(i, frames[i]) for i in ([m[2] for m in marks] + [marks[0][2] + 36, marks[1][2] + 28, marks[3][2] + 30, marks[3][2] + 55, marks[4][2] + 20, marks[5][2] + 30] if test else range(len(frames)))]
    bad = 0
    for i, cam in todo:
        ok = page.evaluate(SET, list(cam))
        if not ok: bad += 1
        page.screenshot(path=str(out / (f"test_{i:04d}.png" if test else f"f_{i:04d}.png")))
        if test or i % 40 == 0: print(i, [round(v, 4) for v in cam], "tiles in:", ok, flush=True)
    print("done; frames whose tiles were not all in:", bad)
    br.close()
