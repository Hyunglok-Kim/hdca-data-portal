#!/usr/bin/env python3
"""cap_hdca_amazon.py BASE OUTDIR [test] — raw frames for the HDCA card (v2): the globe turns with the record-mean soil
moisture, zooms into the Amazon basin, and the basin's soil moisture then plays month by month (the chart over it is
drawn afterwards by compose_hdca_amazon.py). Drawn in software, one settled frame at a time."""
import sys, json, math
from pathlib import Path
from playwright.sync_api import sync_playwright
base, out = sys.argv[1], Path(sys.argv[2]); test = "test" in sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
W, H, FPS = 960, 540, 24
NA, NB, NC0, NHOLD = 84, 60, 12, 18          # globe turn | zoom in | box + panel come in | hold on the last month
BOX = [-74.0, -13.0, -50.0, 3.0]              # the averaging box of amazon_series.py
LAT_A, LNG_A0, LNG_A1 = 15.0, 15.0, -40.0     # the turn: from Africa under the eye to the Atlantic, the Amazon coming round
ZG = math.log2(0.9 * H * math.cos(math.radians(LAT_A)) / 133)   # the globe at 90 % of the frame height, as the first card
ZT = 3.4                                      # the Amazon stage: the continent still recognisable, 36 km cells ~3 px
BOX_AT = (480, 162)                           # where the box's centre sits in the frame, above the chart panel
CSS = """html, body { background: #0F1318 !important; overflow: hidden !important; }
.mapwrap { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; z-index: 99999 !important; border: 0 !important; border-radius: 0 !important; }
.map-ui, .nomap-msg, #boot, .maplibregl-control-container, .logos-footer, .maplibregl-marker { display: none !important; }"""
SETTLE = """async ([lng, lat, z]) => { const m = window.__portal.map; m.jumpTo({center: [lng, lat], zoom: z});
  await new Promise((res) => { let done = false; const fin = () => { if (!done) { done = true; res(); } }; m.once('idle', fin); setTimeout(fin, 9000); });
  return m.areTilesLoaded(); }"""
smooth = lambda t: t * t * (3 - 2 * t)
def shot(page, view, name):
    ok = page.evaluate(SETTLE, view); page.screenshot(path=str(out / name)); return ok
with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"])
    page = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1).new_page()
    page.goto(base, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_function("window.__portal && window.__portal.map && window.__portal.map.loaded()", timeout=90000)
    page.add_style_tag(content=CSS)
    page.evaluate("""(b) => { const m = window.__portal.map; m.setMinZoom(0); m.resize();
      for (const id of ['data', 'sat']) if (m.getLayer(id)) m.setPaintProperty(id, 'raster-fade-duration', 0);
      m.addSource('amz', {type: 'geojson', data: {type: 'Feature', properties: {}, geometry: {type: 'Polygon', coordinates: [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]]}}});
      m.addLayer({id: 'amz-line', type: 'line', source: 'amz', paint: {'line-color': '#FFFFFF', 'line-width': 2, 'line-opacity': 0}}); }""", BOX)
    assert page.evaluate("() => window.__portal.current().spec.key") == "SM|all|", "the page must open on the record-mean soil moisture"
    # the stage view: the box's centre at BOX_AT; found by projecting with the map itself (the globe is not a flat map)
    page.evaluate(SETTLE, [(BOX[0] + BOX[2]) / 2, (BOX[1] + BOX[3]) / 2, ZT])
    for _ in range(3):
        c = page.evaluate("""([b, at]) => { const m = window.__portal.map; const p = m.project([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]);
          const c = m.getCenter(); const q = m.unproject([p.x - at[0] + m.getContainer().clientWidth / 2, p.y - at[1] + m.getContainer().clientHeight / 2]);
          m.jumpTo({center: q}); return [q.lng, q.lat]; }""", [BOX, BOX_AT])
    T = [c[0], c[1], ZT]
    corners = page.evaluate("(b) => { const m = window.__portal.map; return [m.project([b[0], b[1]]), m.project([b[2], b[3]])]; }", BOX)
    print("stage view", [round(v, 3) for v in T], "| box on screen", {k: round(v) for k, v in corners[0].items()}, {k: round(v) for k, v in corners[1].items()}, flush=True)
    months = [m["ym"] for m in json.loads((Path(__file__).resolve().parents[2] / "data" / "catalog.json").read_text())["months"]]   # the record, month by month
    A = [(LNG_A0 + (LNG_A1 - LNG_A0) * i / (NA - 1), LAT_A, ZG) for i in range(NA)]
    B = []
    for i in range(NB):
        t = smooth((i + 1) / NB); B.append((A[-1][0] + (T[0] - A[-1][0]) * t, A[-1][1] + (T[1] - A[-1][1]) * t, A[-1][2] + (T[2] - A[-1][2]) * t))
    want_A = [0, NA // 2] if test else range(NA)
    want_B = [NB // 3, NB - 1] if test else range(NB)
    want_M = [0, len(months) // 2, len(months) - 1] if test else range(len(months))
    bad = 0
    for i in want_A: bad += 0 if shot(page, list(A[i]), f"A_{i:04d}.png") else 1
    for i in want_B: bad += 0 if shot(page, list(B[i]), f"B_{i:04d}.png") else 1
    print("turn + zoom: not settled", bad, flush=True)
    # the stage: the record mean once (the frame the box fades in over), then every month
    page.evaluate("() => window.__portal.map.setPaintProperty('amz-line', 'line-opacity', 0)")
    shot(page, T, "C_all.png")
    page.evaluate("() => window.__portal.map.setPaintProperty('amz-line', 'line-opacity', 0.92)")
    shot(page, T, "C_all_box.png")
    bad = 0
    for k in want_M:
        ym = months[k]
        page.evaluate("(ym) => { window.__portal.state.ym = ym; document.querySelector('#modeSeg button[data-mode=month]').click(); }", ym)
        page.wait_for_function("ym => window.__portal.current().spec.key === 'SM|month|' + ym", arg=ym, timeout=60000)
        bad += 0 if shot(page, T, f"M_{k:03d}.png") else 1
    print("months", len(want_M), "| not settled:", bad, flush=True)
    (out / "timeline.json").write_text(json.dumps({"fps": FPS, "W": W, "H": H, "NA": NA, "NB": NB, "NC0": NC0, "NHOLD": NHOLD, "months": months, "box": BOX, "stage": T, "box_px": corners, "zg": ZG}))
    br.close()
