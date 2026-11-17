#!/usr/bin/env python3
"""check_captions.py [URL] — does every caption and credit line fit its picture, at each layout of the Data page's hub?

A card's caption chip is one line (at most the picture's width minus 24 px) and cuts longer text off with an ellipsis; the
credit line may wrap but must stay inside the picture. For each card, every text in its data-caps is put into the chip in
turn and the chip is measured, at eight window widths from 2048 px down to a 360 px phone. About 47 characters fit everywhere.

Run it on the live page after any change to a caption, a credit line or the hub's columns (the default URL), or on a local
copy of the page. Needs Python with playwright and its chromium; it draws in software, so no graphics card is needed.
Exit code 1 if anything is cut off."""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://hydroai.net/data"
WIDTHS = ((2048, 1050), (1720, 1000), (1440, 900), (1200, 800), (1024, 768), (768, 1000), (390, 844), (360, 740))
JS = """() => { const dec = (t) => { const e = document.createElement('span'); e.innerHTML = t; return e.textContent; };
  return [...document.querySelectorAll('a.hd-card')].map((card) => {
    const m = card.querySelector('.hd-media'), cap = m.querySelector('.hd-cap'), cr = m.querySelector('.hd-credit');
    const was = cap.textContent, cut = [];
    let list = []; try { list = JSON.parse(cap.getAttribute('data-caps')).map((x) => dec(x[1])); } catch (e) {}
    if (!list.length && was) list = [was];                                  // a card with a still picture and fixed words
    for (const t of new Set(list)) { cap.textContent = t; if (cap.scrollWidth > cap.clientWidth + 1) cut.push(t); }
    cap.textContent = was;
    const mr = m.getBoundingClientRect(), rr = cr ? cr.getBoundingClientRect() : null;
    return {card: card.getAttribute('href'), w: Math.round(mr.width), captions: new Set(list).size, cut,
            credit: rr ? {w: Math.round(rr.width), h: Math.round(rr.height),
                          inside: rr.left >= mr.left - 0.5 && rr.right <= mr.right + 0.5 && rr.bottom <= mr.bottom + 0.5} : null}; }); }"""

with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    bad = 0
    for W, H in WIDTHS:
        ctx = br.new_context(viewport={"width": W, "height": H}, reduced_motion="reduce")       # reduced motion: nothing is fetched or played
        page = ctx.new_page()
        page.goto(URL, wait_until="load"); page.wait_for_timeout(1500)
        for r in page.evaluate(JS):
            ok = not r["cut"] and (r["credit"] is None or r["credit"]["inside"]); bad += 0 if ok else 1
            print(f"{'ok  ' if ok else 'FAIL'} {W:5d} px {r['card']:6s} picture {r['w']:4d} px | {r['captions']} captions, cut off: {r['cut']} | credit: {r['credit']}")
        ctx.close()
    br.close()
    print(f"{bad} failed"); sys.exit(1 if bad else 0)
