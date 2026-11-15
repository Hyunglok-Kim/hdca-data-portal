#!/usr/bin/env python3
"""Browser smoke test for the HDCA portal (headless, Playwright).

    python tests/smoke.py --base http://127.0.0.1:8791/ --shots /tmp/shots --ref tests/field_ref.json
    python tests/smoke.py --browser webkit ...        # Safari's engine; also firefox

Checks that the page boots without console errors, that fields decode to the exact numbers the pipeline
wrote (--ref, see tests/make_field_ref.py), that the analytic EASE-Grid row/column mapping matches the
catalogue, that hover, click, the cell series, the full record and its CSV, the day/month/climatology
modes, the tabs and the narrow layout work, and saves screenshots to look at. Exit code 1 on any failure.

Against the lab dashboard the portal needs a session cookie: put "hydroai_rd=<token>" in the SMOKE_COOKIE
environment variable and use the /rd/hdca/ address as --base.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8791/")
ap.add_argument("--shots", required=True)
ap.add_argument("--ref", default="")
ap.add_argument("--query", default="intro=0")
ap.add_argument("--browser", default="chromium", choices=["chromium", "webkit", "firefox"])
ap.add_argument("--cookie", default="", help="name=value to send with every request (internal copy); or set SMOKE_COOKIE")
a = ap.parse_args()
a.cookie = a.cookie or os.environ.get("SMOKE_COOKIE", "")
shots = Path(a.shots)
shots.mkdir(parents=True, exist_ok=True)
fails, notes = [], []


def check(ok, msg):
    (notes if ok else fails).append(("ok   " if ok else "FAIL ") + msg)


def settle(page, ms=900):
    page.wait_for_timeout(ms)
    page.wait_for_function("window.__portal.map.areTilesLoaded()", timeout=60000)


with sync_playwright() as pw:
    gl = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"]
    br = getattr(pw, a.browser).launch(args=gl if a.browser == "chromium" else [])
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    if a.cookie:
        from urllib.parse import urlparse
        name, _, value = a.cookie.partition("=")
        ctx.add_cookies([{"name": name, "value": value, "domain": urlparse(a.base).hostname, "path": "/"}])
    page = ctx.new_page()
    console, bad = [], []
    page.on("console", lambda m: console.append((m.type, m.text)))
    page.on("pageerror", lambda e: console.append(("pageerror", str(e))))
    aborted = ("ERR_ABORTED", "cancelled", "NS_BINDING_ABORTED")
    page.on("requestfailed", lambda r: bad.append((r.url, r.failure)) if not any(x in str(r.failure) for x in aborted) else None)
    page.on("response", lambda r: bad.append((r.url, r.status)) if r.status >= 400 else None)

    sep = "&" if "?" in a.base else "?"
    page.goto(a.base + (sep + a.query if a.query else ""), wait_until="domcontentloaded")
    page.wait_for_function("window.__portal && window.__portal.map && window.__portal.map.loaded()", timeout=60000)
    page.wait_for_function("document.querySelector('#boot') === null", timeout=15000)
    settle(page, 2500)
    page.screenshot(path=str(shots / "01_record_mean.png"))

    info = page.evaluate("""() => { const p = window.__portal, c = p.current();
        return {zoom: p.map.getZoom(), fields: p.fields.size, key: c.spec.key, n: c.stats.n, mean: c.stats.mean, cover: c.stats.cover,
                title: document.querySelector('#lyTitle').textContent, card: document.querySelector('#lyMean').textContent}; }""")
    notes.append(f"info {info}")
    check(info["fields"] >= 1 and info["n"] > 100000, f"record-mean field decoded: {info['n']} land cells, mean {info['mean']:.4f}")
    check(page.evaluate("window.__portal.exact()"), "fields are decoded byte for byte (no canvas round trip)")
    check(abs(info["cover"] - 1) < 0.01, f"record mean covers every land cell ({info['cover']:.4f})")
    # the analytic row mapping against the catalogue's cell-centre latitudes
    rows_ok = page.evaluate("""async () => { const data = new URLSearchParams(location.search).get('data') || './data/';
        const cat = await (await fetch(new URL(data, location.href).href + 'catalog.json')).json();
        let bad = 0; cat.grid.lats.forEach((la, i) => { if (window.__portal.latToRow(la) !== i) bad++; });
        let badc = 0; cat.grid.lons.forEach((lo, i) => { if (window.__portal.lonToCol(lo) !== i) badc++; });
        return [bad, badc, cat.grid.lats.length, cat.grid.lons.length]; }""")
    check(rows_ok[0] == 0 and rows_ok[1] == 0, f"analytic EASE-Grid mapping puts every catalogue centre in its own row/column ({rows_ok})")

    if a.ref:
        ref = json.loads(Path(a.ref).read_text())
        for key, exp in ref.items():
            var, mode, when = key.split("|")
            got = page.evaluate("""async ([v, mode, when]) => { const p = window.__portal, s = p.state;
                const keep = {...s}; s.var = v; s.mode = mode;
                if (mode === 'day') s.day = when; if (mode === 'month') s.ym = when; if (mode === 'clim') s.climMonth = +when;
                const spec = p.layerSpec(); Object.assign(s, keep);
                const dn = await p.getField(spec); if (!dn) return null;
                let sum = 0, n255 = 0; for (const x of dn) { sum += x; if (x === 255) n255++; }
                return {sum, n255, px: [dn[248 * 964 + 296], dn[67 * 964 + 284], dn[201 * 964 + 540], dn[82 * 964 + 823]]}; }""", [var, mode, when])
            check(got is not None and got["sum"] == exp["sum"] and got["n255"] == exp["n255"] and got["px"] == exp["px"],
                  f"field {key} decodes to the pipeline's numbers (sum {got and got['sum']} vs {exp['sum']})")

    # hover readout over the Amazon
    box = page.locator("#map").bounding_box()
    page.evaluate("window.__portal.map.jumpTo({center: [-62, -8], zoom: 4.2})")
    settle(page, 1200)
    pt = page.evaluate("(() => { const p = window.__portal.map.project([-62, -8]); return [p.x, p.y]; })()")
    cx, cy = box["x"] + pt[0], box["y"] + pt[1]
    page.mouse.move(cx, cy)
    page.wait_for_timeout(400)
    ro = page.inner_text("#roVal")
    check("m³/m³" in ro, f"hover readout over the Amazon: '{ro}'")
    page.screenshot(path=str(shots / "02_amazon.png"))

    # click: the cell series (daily for the year) and the full record
    page.mouse.click(cx, cy)
    page.wait_for_function("!document.querySelector('#srSub').textContent.startsWith('Reading')", timeout=60000)
    check(page.locator("#chart svg path").count() >= 1, "cell series chart drawn: " + page.inner_text("#srTitle") + " | " + page.inner_text("#srSub")[:90])
    check(page.locator("#chartRecord svg path").count() >= 1 and "have a retrieval here" in page.inner_text("#rcSub"), "full record: " + page.inner_text("#rcSub")[:100])
    with page.expect_download() as dl:
        page.click("#rcCsv")
    csv_text = Path(dl.value.path()).read_text()
    rows = [r for r in csv_text.splitlines() if r and not r.startswith("#")]
    check(rows[0] == "date,SM_m3m3,VOD,OMEGA" and len(rows) == 3928 + 1 and all(len(r.split(",")) == 4 for r in rows),
          f"record CSV: {len(rows) - 1} rows, first {rows[1]!r}, last {rows[-1]!r}")
    filled = sum(1 for r in rows[1:] if r.split(",")[1])
    check(filled > 200, f"record CSV has {filled} days with a value at this cell")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    page.screenshot(path=str(shots / "03_after_click.png"))

    # tooltip on the chart and its table
    sv = page.locator("#chart svg").bounding_box()
    if sv:
        page.mouse.move(sv["x"] + sv["width"] * 0.6, sv["y"] + sv["height"] * 0.5)
        page.wait_for_timeout(200)
        check(page.locator("#tip").is_visible(), "chart tooltip: " + page.inner_text("#tip").replace("\n", " / ")[:80])
    page.click("#srTableBtn")
    check(page.locator("#srTable table tbody tr").count() > 30, f"series table has {page.locator('#srTable table tbody tr').count()} rows")
    page.click("#srTableBtn")

    # day mode: a single day, then step to the next day with data, then a day without a file
    page.click("#modeSeg button[data-mode=day]")
    settle(page, 1200)
    key = page.evaluate("window.__portal.current().spec.key")
    check(key.startswith("SM|day|"), f"day layer: {key} — {page.inner_text('#lyTitle')}")
    cov = page.evaluate("window.__portal.current().stats.cover")
    check(0.2 < cov < 0.8, f"a single day shows the swath pattern ({cov * 100:.0f}% of land)")
    page.screenshot(path=str(shots / "04_day.png"))
    page.fill("#when input[type=date]", "2019-06-25")                   # SMAP safe mode: no file
    page.dispatch_event("#when input[type=date]", "change")
    settle(page, 1200)
    key2 = page.evaluate("window.__portal.current().spec.key")
    check(key2.endswith("2019-07-24"), f"a missing day falls through to the next day with a file ({key2}); flag: {page.inner_text('#lyFlag')[:70]}")

    # variable switch + month mode + climatology + days observed
    page.click("#varSeg button[data-var=OMEGA]")
    settle(page, 1000)
    check("ω̄" in page.inner_text("#lgTitle") or "albedo" in page.inner_text("#lyTitle"), "omega layer: " + page.inner_text("#lyTitle"))
    page.click("#modeSeg button[data-mode=month]")
    settle(page, 1000)
    check("mean" in page.inner_text("#lyTitle"), "month layer: " + page.inner_text("#lyTitle"))
    page.click("#varSeg button[data-var=N]")
    settle(page, 1000)
    check("Days" in page.inner_text("#lyTitle"), "days-observed layer: " + page.inner_text("#lyTitle") + " · " + page.inner_text("#lyMean") + " days")
    check(page.evaluate("document.querySelector('#modeSeg button[data-mode=day]').disabled"), "day mode is disabled for the days-observed variable")
    page.click("#modeSeg button[data-mode=clim]")
    settle(page, 1000)
    check("mean over years" in page.inner_text("#lyTitle"), "climatology of days observed: " + page.inner_text("#lyTitle"))
    page.click("#varSeg button[data-var=VOD]")
    settle(page, 1000)
    check("VOD" in page.inner_text("#lgTitle"), "VOD climatology: " + page.inner_text("#lyTitle"))
    page.screenshot(path=str(shots / "05_vod_clim.png"))

    # stretch scale + calendar click + globe
    page.click("#scaleSeg button[data-scale=auto]")
    settle(page, 800)
    ticks = page.inner_text("#lgTicks")
    check("≥" in ticks, f"stretched legend: {ticks.replace(chr(10), ' ')}")
    page.click("#cal button.cal-c.built >> nth=40")
    settle(page, 1000)
    check(page.evaluate("window.__portal.state.mode") == "month", "calendar click selects a month: " + page.inner_text("#lyTitle"))
    page.click("#btnGlobe")
    page.wait_for_timeout(2200)
    page.screenshot(path=str(shots / "06_globe.png"))
    page.select_option("#jump", label="Korean Peninsula")
    page.wait_for_timeout(2200)
    c = page.evaluate("(() => { const m = window.__portal.map, c = m.getCenter(); return [c.lng, c.lat, m.getZoom()]; })()")
    check(abs(c[0] - 127.5) < 0.05 and abs(c[1] - 37.0) < 0.05 and page.input_value("#jump") == "", f"jump to Korea: {c[0]:.2f}, {c[1]:.2f}, zoom {c[2]:.2f}")
    page.screenshot(path=str(shots / "07_korea.png"))

    for tab, shot in (("download", "08_download.png"), ("code", "09_code.png"), ("about", "10_about.png")):
        page.click(f".tab[data-tab={tab}]")
        page.wait_for_timeout(250)
        page.screenshot(path=str(shots / shot), full_page=True)
    page.click(".tab[data-tab=download]")
    check(page.locator("#dlTable tbody tr").count() == 11, "download table lists 11 years: " + page.inner_text("#dlTotal"))

    # narrow screen
    page.set_viewport_size({"width": 430, "height": 860})
    page.click(".tab[data-tab=explore]")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(shots / "11_phone.png"), full_page=True)
    over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(over <= 1, f"no horizontal overflow at 430 px (overflow {over}px)")

    errs = [c for c in console if c[0] in ("error", "pageerror")]
    check(not errs, f"no console errors ({len(errs)})")
    for c in errs[:12]:
        notes.append(f"   console {c}")
    warn = [c for c in console if c[0] == "warning"]
    for c in warn[:8]:
        notes.append(f"   warning {c[1][:200]}")
    check(not bad, f"no failed or 4xx/5xx requests ({len(bad)})")
    for b in bad[:12]:
        notes.append(f"   request {b}")
    br.close()

print("\n".join(notes))
print("\n".join(fails))
print(f"\n{len(fails)} failed")
sys.exit(1 if fails else 0)
