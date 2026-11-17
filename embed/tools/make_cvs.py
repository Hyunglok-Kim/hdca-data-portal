#!/usr/bin/env python3
"""make_cvs.py HAMPYEONG_REPO OUTDIR [test] — frames for the Core Validation Site card: the 1 km cell from the drone, true colour,
flight after flight through the 2026 growing season, with the ground stations marked. Made from the portal's own published layers."""
import sys, csv, json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
repo, out = Path(sys.argv[1]), Path(sys.argv[2]); test = "test" in sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
import os
W, H, FPS = 960, 540, int(os.environ.get('CVS_FPS', 24))
DATES = ["20260507", "20260525", "20260724", "20260817", "20260829", "20260915", "20260922", "20261009", "20261016", "20261109"]      # ten clean flights, bare fields to harvest; flights with colour artefacts over the forest are left out
HOLD, FADE = int(os.environ.get('CVS_HOLD', 9)), int(os.environ.get('CVS_FADE', 12))      # frames a flight is held, frames of the cross-fade to the next
PULSE = os.environ.get('CVS_PULSE', '1') == '1'
N = len(DATES) * (HOLD + FADE)
BOUNDS = dict(n=35.020053, s=35.010096, e=126.556309, w=126.545354)       # the flights' common grid (catalog.csv), 1098 x 998 px at 1 m
SW, SH = 1098, 998
BG = (15, 19, 24)
imgs = []
for d in DATES:
    im = Image.open(repo / f"data/uav/HP_UAV_RGB_{d}_1m.png").convert("RGBA")
    assert im.size == (SW, SH), (d, im.size)
    base = Image.new("RGBA", im.size, BG + (255,)); base.alpha_composite(im)
    imgs.append(np.asarray(base.convert("RGB"), dtype=np.float32))
stations = []
for r in csv.DictReader(open(repo / "data/stations.csv")):
    try: lat, lon = float(r["lat"]), float(r["lon"])
    except (ValueError, TypeError, KeyError): continue
    if r.get("station_id"): stations.append(((lon - BOUNDS["w"]) / (BOUNDS["e"] - BOUNDS["w"]) * SW, (BOUNDS["n"] - lat) / (BOUNDS["n"] - BOUNDS["s"]) * SH))
print("flights:", len(DATES), "| stations:", len(stations), "| frames:", N, "| seconds:", N / FPS)
CX, CY, CW, CH = SW / 2, 500.0, 1040.0, 585.0        # the 16:9 window on the mosaic, before the slow drift
def view(k):
    # The window stands still: a drifting view of imagery this detailed tripled the size of the file, and the
    # seasons changing and the stations' rings are movement enough.
    return CX - CW / 2, CY - CH / 2, CW, CH
def frame(k):
    i, r = divmod(k, HOLD + FADE)
    a = 0.0 if r < HOLD else (r - HOLD + 1) / (FADE + 1)
    a = a * a * (3 - 2 * a)
    arr = imgs[i] if a == 0 else imgs[i] * (1 - a) + imgs[(i + 1) % len(DATES)] * a
    x0, y0, w, h = view(k)
    im = Image.fromarray(arr.astype(np.uint8)).resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))
    S = 3                                              # stations drawn three times as large, then reduced: smooth edges
    ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    for n, (sx, sy) in enumerate(stations):
        px, py = (sx - x0) / w * W * S, (sy - y0) / h * H * S
        ph = 0.5 + 0.5 * math.sin(2 * math.pi * (3 * k / N) + n * 0.61) if PULSE else 0.5          # each station's ring breathes, out of step with the others
        rr = (7.5 + 3.5 * ph) * S
        dr.ellipse([px - rr, py - rr, px + rr, py + rr], outline=(255, 255, 255, int(70 + 60 * (1 - ph))), width=int(1.2 * S))
        r0 = 3.6 * S
        dr.ellipse([px - r0 - S, py - r0 - S, px + r0 + S, py + r0 + S], fill=(20, 24, 30, 200))
        dr.ellipse([px - r0, py - r0, px + r0, py + r0], fill=(255, 255, 255, 255))
    im = im.convert("RGBA"); im.alpha_composite(ov.resize((W, H), Image.LANCZOS))
    return im.convert("RGB")
caps = []
for i, d in enumerate(DATES): caps.append([round(i * (HOLD + FADE) / FPS, 2), d])
(out / "timeline.json").write_text(json.dumps({"fps": FPS, "frames": N, "dates": caps}))
for k in ([0, 30, 60, 150, 200, 280] if test else range(N)):
    frame(k).save(out / (f"test_{k:04d}.png" if test else f"f_{k:04d}.png"))
print("done")
