#!/usr/bin/env python3
"""Repack the per-cell series store for publishing: gzip every entry and split it into row bands.

Input  series/HDCA_series.pmtiles         (uncompressed, 2.5 GB, written by build_layers.py)
Output series/HDCA_series_r<r0>-<r1>.pmtiles   one archive per row band, each under --max-mb,
                                            tile_compression = gzip (pmtiles.js inflates on read),
                                            entries unchanged: uint16 LE [T][SM, VOD, OMEGA], 65535 = no data
       work/series_parts.json              which rows live in which file (make_catalog.py copies it)

Why: the whole store gzips to about 0.5 GB and GitHub Pages serves files under 100 MB, so the public
copy can live in a repository of its own on the same origin as the portal. The lab copy uses the same files.
"""
import argparse
import gzip
import json
import os
import time

from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--src", default="/data/personal_data/project_hdca_portal/out/series/HDCA_series.pmtiles")
ap.add_argument("--out-dir", default="/data/personal_data/project_hdca_portal/out/series")
ap.add_argument("--work", default="/data/personal_data/project_hdca_portal/work")
ap.add_argument("--max-mb", type=float, default=90)
ap.add_argument("--days", type=int, default=3928)
a = ap.parse_args()
t0 = time.time()

by_row = {}                                   # row -> list of (tileid, gzipped bytes)
n = raw = 0
with open(a.src, "rb") as f:
    for (z, x, y), data in all_tiles(MmapSource(f)):
        assert z == 10 and len(data) == a.days * 6, (z, len(data))
        by_row.setdefault(y, []).append((zxy_to_tileid(z, x, y), gzip.compress(data, 6, mtime=0)))
        n += 1; raw += len(data)
print(f"{n} cells read and gzipped in {time.time() - t0:.0f}s: {raw / 1e9:.2f} GB -> "
      f"{sum(len(d) for v in by_row.values() for _, d in v) / 1e9:.2f} GB", flush=True)

rows = sorted(by_row)
bands, cur, size = [], [], 0
for r in rows:
    s = sum(len(d) for _, d in by_row[r])
    if cur and size + s > a.max_mb * 1e6:
        bands.append(cur); cur, size = [], 0
    cur.append(r); size += s
if cur:
    bands.append(cur)

parts = []
for band in bands:
    r0, r1 = band[0], band[-1]
    name = f"HDCA_series_r{r0:03d}-{r1:03d}.pmtiles"
    tiles = sorted((t for r in band for t in by_row[r]), key=lambda t: t[0])
    tmp = os.path.join(a.out_dir, name + ".part")
    with open(tmp, "wb") as fh:
        w = Writer(fh)
        for tid, d in tiles:
            w.write_tile(tid, d)
        w.finalize({"tile_type": TileType.UNKNOWN, "tile_compression": Compression.GZIP,
                    "min_lon_e7": -1800000000, "min_lat_e7": -850445000, "max_lon_e7": 1800000000, "max_lat_e7": 850445000,
                    "center_zoom": 0, "center_lon_e7": 0, "center_lat_e7": 0},
                   {"name": f"HDCA pixel series rows {r0}-{r1}", "type": "series", "addressing": "z=10, x=column, y=row",
                    "layout": f"gzip of uint16 little-endian [{a.days} days][SM, VOD, OMEGA]; 65535 = no data",
                    "scale": {"SM": 1e-4, "VOD": 1e-4, "OMEGA": 2e-4}, "rows": [r0, r1]})
    os.replace(tmp, os.path.join(a.out_dir, name))
    parts.append({"file": f"series/{name}", "rows": [r0, r1], "cells": len(tiles), "bytes": os.path.getsize(os.path.join(a.out_dir, name))})
    print(f"  {name}: rows {r0}-{r1}, {len(tiles)} cells, {parts[-1]['bytes'] / 1e6:.1f} MB", flush=True)

json.dump({"dtype": "uint16le", "layout": "interleaved", "order": ["SM", "VOD", "OMEGA"], "nodata": 65535,
           "compression": "gzip", "days": a.days, "parts": parts}, open(os.path.join(a.work, "series_parts.json"), "w"), indent=1)
print(f"done: {len(parts)} parts, {sum(p['bytes'] for p in parts) / 1e9:.2f} GB in {time.time() - t0:.0f}s")
