#!/usr/bin/env python3
"""cap_hdca.py BASE OUTDIR [test] — frames for the HDCA card: the globe turns once while the layer goes from soil moisture to
vegetation optical depth to the scattering albedo (record means). Drawn in software, one settled frame at a time."""
import sys, json, math
from pathlib import Path
from playwright.sync_api import sync_playwright
base, out = sys.argv[1], Path(sys.argv[2]); test = "test" in sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
W, H, FPS, N, FADE = 960, 540, 24, 288, 12
LAT, LNG0 = 15.0, -20.0          # soil moisture over Africa and Eurasia, optical depth over East Asia and Australia, the albedo over the Americas
ZOOM = math.log2(0.9 * H * math.cos(math.radians(LAT)) / 133)
CSS = """html, body { background: #0F1318 !important; overflow: hidden !important; }
.mapwrap { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; z-index: 99999 !important; border: 0 !important; border-radius: 0 !important; }
.map-ui, .nomap-msg, #boot, .maplibregl-control-container, .logos-footer, .maplibregl-marker { display: none !important; }"""
VARS = [("SM", 0), ("VOD", N // 3), ("OMEGA", 2 * N // 3)]
SET = """async (lng) => { const m = window.__portal.map; m.jumpTo({center: [lng, %s], zoom: %s});
  await new Promise((res) => { let done = false; const fin = () => { if (!done) { done = true; res(); } }; m.once('idle', fin); setTimeout(fin, 9000); });
  return m.areTilesLoaded(); }""" % (LAT, ZOOM)
with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"])
    page = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1).new_page()
    page.goto(base, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_function("window.__portal && window.__portal.map && window.__portal.map.loaded()", timeout=90000)
    page.add_style_tag(content=CSS)
    page.evaluate("""() => { const m = window.__portal.map; m.setMinZoom(0); m.resize(); for (const id of ['data', 'sat']) if (m.getLayer(id)) m.setPaintProperty(id, 'raster-fade-duration', 0); }""")
    titles = {}
    for k, (var, start) in enumerate(VARS):
        page.evaluate("v => document.querySelector(`#varSeg button[data-var=${v}]`).click()", var)      # the layer bar lies under the full-window map
        page.wait_for_function("v => window.__portal.current().spec.key.startsWith(v + '|')", arg=var, timeout=60000)
        page.wait_for_timeout(600)
        titles[var] = page.inner_text("#lyTitle")
        idx = list(range(start - FADE // 2, start + N // 3 + FADE // 2))
        if test: idx = [start, start + 48]
        bad = 0
        for i in idx:
            j = i % N
            ok = page.evaluate(SET, LNG0 + 360.0 * j / N)
            bad += 0 if ok else 1
            page.screenshot(path=str(out / (f"test_{var}_{j:04d}.png" if test else f"{var}_{j:04d}.png")))
        print(var, "|", titles[var], "| frames", len(idx), "| not settled:", bad, flush=True)
    (out / "timeline.json").write_text(json.dumps({"fps": FPS, "frames": N, "fade": FADE, "vars": VARS, "titles": titles, "zoom": ZOOM, "lat": LAT}))
    br.close()
