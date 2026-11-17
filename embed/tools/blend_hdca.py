#!/usr/bin/env python3
"""blend_hdca.py FRAMES_DIR OUT_DIR — join the three variables' frames from cap_hdca.py into one loop.

Each variable was captured for its third of the turn plus half a cross-fade on either side; here the overlaps are
blended, and the loop is started a few frames late so that it begins on a clean soil-moisture frame (the first frame
is also the still picture shown before the loop plays, and to visitors who asked for reduced motion)."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
src, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
tl = json.loads((src / "timeline.json").read_text()); N, FADE, VARS = tl["frames"], tl["fade"], tl["vars"]
SHIFT = FADE // 2 + 2
def load(v, j): return np.asarray(Image.open(src / f"{v}_{j:04d}.png").convert("RGB"), dtype=np.float32)
frames = []
for i in range(N):
    k = max(n for n, (v, s) in enumerate(VARS) if i >= s)
    v, s = VARS[k]; nxt, s2 = VARS[(k + 1) % len(VARS)][0], (VARS[(k + 1) % len(VARS)][1] or N); prev = VARS[(k - 1) % len(VARS)][0]
    a = None
    if i >= s2 - FADE // 2: a, other = (i - (s2 - FADE // 2) + 0.5) / FADE, nxt
    elif i < s + FADE // 2: a, other = 1 - (i - (s - FADE // 2) + 0.5) / FADE, prev
    if a is None: img = load(v, i)
    else:
        a = a * a * (3 - 2 * a); img = load(v, i) * (1 - a) + load(other, i) * a
    frames.append(img.astype(np.uint8))
for i in range(N): Image.fromarray(frames[(i + SHIFT) % N]).save(out / f"f_{i:04d}.png")
fps = tl["fps"]
print("frames:", N, "| the captions change at", [round(((s or N) - SHIFT) / fps, 2) for v, s in VARS[1:]] + [round((N - SHIFT) / fps, 2)], "s")
