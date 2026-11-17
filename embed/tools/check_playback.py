#!/usr/bin/env python3
"""check_playback.py [URL] [ENGINE] — do the pictures on the Data page's hub behave?

  1. every card's loop plays, and its time moves on;
  2. every caption in a card's data-caps is shown at some point of its loop (a caption timed past the end never is);
  3. opening a dataset hides the hub and stops the loops; coming back starts them again;
  4. the page throws no script error;
  5. a visitor who asked for reduced motion gets the still pictures: no video is fetched, and each picture carries
     the first caption.

Run it on the live page after a loop is re-made or a card is changed (the default URL), or on a local copy of the page
(a server that cannot answer range requests is fine: nothing here seeks). ENGINE is chromium (the default, drawn in
software), firefox or webkit; webkit uses the graphics card, so not while training jobs hold it. Needs Python with
playwright and that engine. The window is 2048 px wide because a loop plays only while its card is on screen and all
cards must be: if the hub grows, widen it. Exit code 1 if anything fails."""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://hydroai.net/data"
ENGINE = sys.argv[2] if len(sys.argv) > 2 else "chromium"
VIEW = {"width": 2048, "height": 1100}
STATE = """() => [...document.querySelectorAll('a.hd-card')].map((card) => { const m = card.querySelector('.hd-media'), v = m.querySelector('video'), cap = m.querySelector('.hd-cap');
    const dec = (t) => { const e = document.createElement('span'); e.innerHTML = t; return e.textContent; };
    let list = []; try { list = JSON.parse(cap.getAttribute('data-caps')).map((x) => dec(x[1])); } catch (e) {}
    const r = m.getBoundingClientRect();
    return {card: card.getAttribute('href'), video: !!v, t: v ? +v.currentTime.toFixed(2) : null, dur: v && isFinite(v.duration) ? v.duration : null,
            paused: v ? v.paused : null, ready: v ? v.readyState : null, err: v && v.error ? v.error.code : null,
            file: v ? (v.currentSrc || '').split('/').pop().split('?')[0] : '', sources: v ? v.querySelectorAll('source').length : 0,
            cap: cap ? cap.textContent : '', expected: [...new Set(list)], first: list[0] || '',
            onScreen: r.top < innerHeight && r.bottom > 0 && r.left < innerWidth && r.right > 0,
            still: getComputedStyle(m).backgroundImage.startsWith('url(')}; })"""

with sync_playwright() as pw:
    if ENGINE == "chromium":
        br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    else:
        br = getattr(pw, ENGINE).launch()
    fails = []
    def check(ok, msg):
        print(("ok   " if ok else "FAIL ") + f"{ENGINE}: {msg}")
        if not ok: fails.append(msg)

    ctx = br.new_context(viewport=VIEW); page = ctx.new_page(); thrown, console = [], []
    page.on("pageerror", lambda e: thrown.append(str(e)[:160]))
    page.on("console", lambda m: console.append(m.text[:160]) if m.type == "error" else None)
    page.goto(URL, wait_until="load"); page.wait_for_timeout(5000)
    a = [x for x in page.evaluate(STATE) if x["video"]]
    check(bool(a) and all(x["onScreen"] for x in a), f"all {len(a)} cards with a loop are on screen in a {VIEW['width']} x {VIEW['height']} window")
    page.wait_for_timeout(4500)
    b = [x for x in page.evaluate(STATE) if x["video"]]
    check(bool(a) and all(not x["paused"] and x["ready"] >= 2 and x["err"] is None for x in b) and all(y["t"] != x["t"] for x, y in zip(a, b)),
          f"the loops play ({[x['file'] for x in b]}; seconds {[x['t'] for x in a]} then {[y['t'] for y in b]})")

    seen = {x["card"]: set() for x in b}
    longest = max([x["dur"] or 16 for x in b] or [16])
    for _ in range(int((longest + 2.5) / 0.4) + 1):
        for x in page.evaluate(STATE):
            if x["video"]: seen[x["card"]].add(x["cap"])
        page.wait_for_timeout(400)
    missing = {x["card"]: [c for c in x["expected"] if c not in seen[x["card"]]] for x in b}
    check(all(not v for v in missing.values()) and all(x["expected"] for x in b),
          f"every caption is shown during its loop ({ {x['card']: len(x['expected']) for x in b} } captions; never shown: { {k: v for k, v in missing.items() if v} })")

    first = page.evaluate("document.querySelector('a.hd-card').getAttribute('href')"); key = first.lstrip("#")
    page.click(f'a.hd-card[href="{first}"]'); page.wait_for_timeout(1500)
    c = [x for x in page.evaluate(STATE) if x["video"]]
    check(page.evaluate(f"document.getElementById('hd-hub').hidden && !document.getElementById('hd-panel-{key}').hidden") and all(x["paused"] for x in c),
          f"opening a dataset ({first}) hides the hub and stops the loops")
    page.click(f"#hd-panel-{key} a.hd-back"); page.wait_for_timeout(2500)
    d = [x for x in page.evaluate(STATE) if x["video"]]
    check(page.evaluate("!document.getElementById('hd-hub').hidden") and all(not x["paused"] for x in d), "back on the hub they play again")
    check(not thrown, f"no script error ({thrown[:3]})")
    if console: print(f"note {ENGINE}: console errors, not counted: {console[:3]}")
    ctx.close()

    ctx = br.new_context(viewport=VIEW, reduced_motion="reduce"); page = ctx.new_page(); fetched = []
    page.on("request", lambda r: fetched.append(r.url.split("?")[0].split("/")[-1]) if r.url.split("?")[0].endswith((".mp4", ".webm")) else None)
    page.goto(URL, wait_until="load"); page.wait_for_timeout(3500)
    e = [x for x in page.evaluate(STATE) if x["video"]]
    check(bool(e) and all(x["paused"] and x["sources"] == 0 and x["still"] for x in e) and not fetched and all(x["cap"] == x["first"] and x["cap"] for x in e),
          f"with reduced motion the pictures stay still, no video is fetched ({fetched[:2]}), and each carries its first caption ({[x['cap'] for x in e]})")
    ctx.close(); br.close()
    print(f"{len(fails)} failed"); sys.exit(1 if fails else 0)
