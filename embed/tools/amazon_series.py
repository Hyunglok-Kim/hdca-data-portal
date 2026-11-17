#!/usr/bin/env python3
"""amazon_series.py DATA_DIR OUT_JSON — area-mean soil moisture of the Amazon-basin box from the portal's own fields:
monthly means (monthly archive) and daily means (daily archives). The grid is equal-area, so a plain mean over cells is an area mean."""
import sys, json, io, gzip, math
from pathlib import Path
import numpy as np
from PIL import Image
from pmtiles.reader import Reader, MmapSource
data, outp = Path(sys.argv[1]), Path(sys.argv[2])
cat = json.loads((data / "catalog.json").read_text())
BOX = [-74.0, -13.0, -50.0, 3.0]            # lon0, lat0, lon1, lat1
W, Hh = cat["grid"]["cols"], cat["grid"]["rows"]
step = cat["variables"]["SM"]["step"]
lats = np.array(cat["grid"]["lats"])
rows = np.where((lats >= BOX[1]) & (lats <= BOX[3]))[0]
c0, c1 = int(math.floor((BOX[0] + 180) / 360 * W)), int(math.floor((BOX[2] + 180) / 360 * W))
print("rows", rows.min(), rows.max(), "cols", c0, c1, "cells", len(rows) * (c1 - c0 + 1))
readers = {}
def tile(rel, x):
    r = readers.get(rel)
    if r is None:
        f = open(data / rel, "rb"); r = Reader(MmapSource(f)); readers[rel] = r
    b = r.get(9, x, 0)
    if not b: return None
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    a = np.asarray(Image.open(io.BytesIO(b)))
    assert a.shape == (Hh, W), a.shape
    return a
def boxmean(a):
    sub = a[rows.min():rows.max() + 1, c0:c1 + 1]
    ok = sub != 255
    return (float(sub[ok].mean() * step) if ok.any() else None), int(ok.sum())
out = {"box": BOX, "rows": [int(rows.min()), int(rows.max())], "cols": [c0, c1], "step": step, "months": [], "days": []}
a = tile("clim/HDCA_SM_clim.pmtiles", 0); m, n = boxmean(a); out["record_mean"] = m; out["record_cells"] = n
print("record mean", m, "cells with data", n)
for rec in cat["months"]:
    y, mo = int(rec["ym"][:4]), int(rec["ym"][5:7])
    a = tile("monthly/HDCA_SM_monthly.pmtiles", (y - 2015) * 12 + mo - 1)
    m, n = boxmean(a) if a is not None else (None, 0)
    out["months"].append({"ym": rec["ym"], "mean": m, "n": n})
for rec in cat["days"]:
    d = rec["d"]; y = int(d[:4])
    doy = (np.datetime64(d) - np.datetime64(f"{y}-01-01")).astype(int) + 1
    try: a = tile(f"daily/HDCA_SM_{y}.pmtiles", int(doy))
    except FileNotFoundError: a = None
    m, n = boxmean(a) if a is not None else (None, 0)
    out["days"].append({"d": d, "mean": m, "n": n})
outp.write_text(json.dumps(out))
mm = [x["mean"] for x in out["months"] if x["mean"] is not None]
print("months", len(out["months"]), "with data", len(mm), "min %.3f max %.3f" % (min(mm), max(mm)))
dd = [x["mean"] for x in out["days"] if x["mean"] is not None]
print("days", len(out["days"]), "with data", len(dd), "min %.3f max %.3f" % (min(dd), max(dd)))
for x in out["months"][::12]: print(x["ym"], x["mean"], x["n"])
