#!/usr/bin/env python3
"""cap_et_v3.py BASE OUTDIR [test] — frames for the ET card (et-v3): the globe with ET over all land, down to France, across to the Korean
Peninsula and into a 30 m sample area (Pyeongchang), and back. Drawn in software, one settled frame at a time (camera set, tiles
in, then a screenshot), from the public copy of the tiles, as the portal itself draws it.

The lab head asked (2026-11-17) for the loop to open on the globe with ET laid over the whole Earth, and for the 30 m part to be
Pyeongchang; France was added when its maps went up (2026-11-21). Outside the regions with maps those colours are the portal's
background layer, another product (MOD16A2GF): the card must name it on the picture while the globe shows (its first caption does,
and it comes back when the globe does)."""
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
G0 = (62.0, 24.0)                                    # where the loop opens: Eurasia, both regions on the near side of the globe
F1 = (2.6, 40.0); FR = (2.6, 46.4)                   # the globe turned to France; the middle of France
K1 = (127.7, 34.5); PEN = (127.6, 38.0); CH = (128.51588, 37.48177)     # the same for the Korean Peninsula; CH: the Pyeongchang sample area (deciduous forest, valleys)
zG0, zF1, zK1 = globe_zoom(G0[1], D0), globe_zoom(F1[1], D0), globe_zoom(K1[1], D0)
zFR, zPEN, zCH = 4.5, 4.95, 12.25                    # the whole of France; the whole peninsula; the 6.7 km sample square just inside the frame
def turn(A, B):                                      # the globe turns from A to B, the same size throughout
    def f(u):
        e = ease(u); lng = A[0] + (B[0] - A[0]) * e; lat = A[1] + (B[1] - A[1]) * e
        return (lng, lat, globe_zoom(lat, D0))
    return f
def across(u):                                       # out of France to the globe, and round to the Korean Peninsula
    e = ease(u); lng = FR[0] + (K1[0] - FR[0]) * e; lat = FR[1] + (K1[1] - FR[1]) * e
    zg = globe_zoom(lat, D0); k = min(1.0, u / 0.36)
    return (lng, lat, zFR + 0.12 + (zg - zFR - 0.12) * ease(k))
SEGS = [("globe", turn(G0, F1), 1.8),
        ("to France", lambda u: about(FR, F1, zF1, zFR, u), 1.9),
        ("France", lambda u: (FR[0], FR[1], zFR + 0.12 * u), 1.1),
        ("across", across, 2.8),
        ("down", lambda u: about(PEN, K1, zK1, zPEN, u), 2.0),
        ("peninsula", lambda u: (PEN[0], PEN[1], zPEN + 0.1 * u), 0.8),
        ("in", lambda u: about(CH, PEN, zPEN + 0.1, zCH, u), 2.9),
        ("30 m", lambda u: (CH[0], CH[1], zCH + 0.8 * ease(u)), 1.9),
        ("out", lambda u: about(CH, G0, zG0, zCH + 0.8, 1 - u), 2.5)]
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
        return {bg: m.getLayer('ctx') ? m.getLayoutProperty('ctx', 'visibility') : 'no background layer', regions: window.__portal.regions.map((r) => r.id + ' zoom ' + r.zoom.max)}; }""")
    print("background layer:", bgv["bg"], "| regions:", bgv["regions"], flush=True)
    assert bgv["bg"] == "visible", "the loop must show the portal's background layer on the globe"
    assert all(r.endswith("zoom 10") for r in bgv["regions"]) and len(bgv["regions"]) == 2, "the loop is drawn from the public copy of the tiles, with both regions"
    page.wait_for_timeout(800)
    pick = [m[2] for m in marks] + [marks[0][2] + 22, marks[1][2] + 24, marks[3][2] + 12, marks[3][2] + 34, marks[3][2] + 56, marks[4][2] + 26, marks[6][2] + 30, marks[6][2] + 54, marks[7][2] + 20, marks[8][2] + 30]
    todo = [(i, frames[i]) for i in (sorted(set(pick)) if test else range(len(frames)))]
    bad = 0
    for i, cam in todo:
        ok = page.evaluate(SET, list(cam))
        if not ok: bad += 1
        page.screenshot(path=str(out / (f"test_{i:04d}.png" if test else f"f_{i:04d}.png")))
        if test or i % 40 == 0: print(i, [round(v, 4) for v in cam], "tiles in:", ok, flush=True)
    print("done; frames whose tiles were not all in:", bad)
    br.close()
