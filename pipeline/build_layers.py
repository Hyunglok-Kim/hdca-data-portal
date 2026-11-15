#!/usr/bin/env python3
"""Browse fields and the pixel-series store for the HDCA portal, from the merged NetCDF.

The grid is small (406 x 964 cells of 36 km, EASE-Grid 2.0 global), so a whole day is one
8-bit PNG of ~100 KB and the browser projects it onto the map itself. Nothing is warped here.

Field contract (every PNG): 964 x 406, 8-bit grayscale, value = DN x step, DN 255 = no data.
    SM     step 0.0035 m3/m3   (DN 254 = 0.889; the record's maximum is 0.884)
    VOD    step 0.006          (DN 254 = 1.524; the inversion's upper bound is 1.5)
    OMEGA  step 0.001          (DN 254 = 0.254; values above are shown as >= 0.254)
    N      step 1 day          (days with a retrieval; DN 255 = not a land cell)

Archives (PMTiles used as a range-readable key-value store; the key is a z/x/y address):
    daily/HDCA_<VAR>_<YYYY>.pmtiles      z 9, x = day of year (1..366), y = 0   -> PNG of that day
    monthly/HDCA_<VAR>_monthly.pmtiles   z 9, x = (year-2015)*12 + month-1,  y = 0 -> PNG, mean of the month's days
    clim/HDCA_<VAR>_clim.pmtiles         z 9, x = 0 -> record mean; x = 1..12 -> calendar-month mean
    series/HDCA_series.pmtiles           z 10, x = column, y = row -> uint16 LE [T][SM, VOD, OMEGA], 65535 = no data
                                         SM x 1e-4, VOD x 1e-4, OMEGA x 2e-4 (one entry per land cell)
Statistics for the catalog go to work/layers.json; make_catalog.py assembles catalog.json.
Memory: one variable at a time (~6 GB) plus the 2.5 GB series store as a memmap.
"""
import argparse
import io
import json
import os
import time
from datetime import date, timedelta
from multiprocessing import Pool

import netCDF4 as nc
import numpy as np
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

VARS = {"SM": {"step": 0.0035, "scale": 1e-4, "units": "m3 m-3", "k": 0},
        "VOD": {"step": 0.006, "scale": 1e-4, "units": "1", "k": 1},
        "OMEGA": {"step": 0.001, "scale": 2e-4, "units": "1", "k": 2}}
NODATA_DN = 255
SER_NODATA = 65535
Y0 = 2015
G = {}                      # shared with forked workers: the current array and its step


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def png_bytes(q):
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(q), "L").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def quantize(v, step, land=None):
    """float field -> DN. NaN -> 255. With `land`, cells off land are 255 and land cells without a value keep DN 0."""
    ok = np.isfinite(v)
    q = np.full(v.shape, NODATA_DN, np.uint8)
    q[ok] = np.minimum(np.rint(v[ok] / step), NODATA_DN - 1)
    return q


def enc_day(t):
    v = G["A"][t]
    ok = np.isfinite(v)
    n = int(ok.sum())
    if n == 0:
        return t, None, None, 0
    return t, png_bytes(quantize(v, G["step"])), float(v[ok].mean()), n


def write_archive(path, tiles, tile_type, meta, bounds=(-180, -85.0445, 180, 85.0445)):
    """tiles: list of (tileid, bytes). Writes atomically."""
    tiles.sort(key=lambda t: t[0])
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        w = Writer(fh)
        for tid, data in tiles:
            w.write_tile(tid, data)
        w.finalize({"tile_type": tile_type, "tile_compression": Compression.NONE,
                    "min_lon_e7": int(bounds[0] * 1e7), "min_lat_e7": int(bounds[1] * 1e7),
                    "max_lon_e7": int(bounds[2] * 1e7), "max_lat_e7": int(bounds[3] * 1e7),
                    "center_zoom": 0, "center_lon_e7": 0, "center_lat_e7": 0}, meta)
    os.replace(tmp, path)
    return os.path.getsize(path)


def mean_field(A, idx):
    """Mean over the valid values of the listed days, and how many days each cell had."""
    s = np.zeros(A.shape[1:], np.float64)
    c = np.zeros(A.shape[1:], np.int32)
    for t in idx:
        v = A[t]
        ok = np.isfinite(v)
        s[ok] += v[ok]
        c += ok
    m = np.full(A.shape[1:], np.nan, np.float32)
    np.divide(s, c, out=m, where=c > 0, casting="unsafe")
    return m, c


def stat(v, land_px):
    ok = np.isfinite(v)
    n = int(ok.sum())
    return {"mean": round(float(v[ok].mean()), 5) if n else None, "n": n, "cover": round(n / land_px, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="/home/cpuserver_data/personal_data/jaese/HDCA/Results/da_HDCA_2nd_2015_2025.nc")
    ap.add_argument("--work", default="/data/personal_data/project_hdca_portal/work")
    ap.add_argument("--out", default="/data/personal_data/project_hdca_portal/out")
    ap.add_argument("--procs", type=int, default=12)
    ap.add_argument("--skip-series", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    for d in ("daily", "monthly", "clim", "series"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)

    ds = nc.Dataset(a.src)
    T, H, W = ds["SM"].shape
    tv = ds["time"]
    days = [d if hasattr(d, "year") else None for d in nc.num2date(tv[:], tv.units, tv.calendar, only_use_cftime_datetimes=False)]
    days = [date(d.year, d.month, d.day) for d in days]
    assert days[0] == date(2015, 4, 1) and (days[-1] - days[0]).days == T - 1, "the time axis must be complete and daily"
    n_valid_px = np.load(os.path.join(a.work, "n_valid_px.npy"))
    land = n_valid_px > 0
    land_px = int(land.sum())
    rows, cols = np.nonzero(land)                       # the series store holds one entry per land cell, in row-major order
    S = len(rows)
    log(f"{T} days, {H} x {W} cells, {land_px} land cells")

    month_keys = sorted({(d.year, d.month) for d in days})
    by_month = {k: [t for t, d in enumerate(days) if (d.year, d.month) == k] for k in month_keys}
    by_cal = {m: [t for t, d in enumerate(days) if d.month == m] for m in range(1, 13)}
    years = sorted({d.year for d in days})

    ser_path = os.path.join(a.work, "series_u16.dat")
    mm = None if a.skip_series else np.lib.format.open_memmap(ser_path, mode="w+", dtype=np.uint16, shape=(S, T, 3))
    if mm is not None:
        mm[:] = SER_NODATA

    out = {"vars": {}, "land_px": land_px, "T": T, "first": days[0].isoformat(), "last": days[-1].isoformat(),
           "years": years, "months": [f"{y}-{m:02d}" for y, m in month_keys], "archives": {}}
    n_month_field = {}                                   # (y, m) -> days-observed field, from the SM mask
    n_cal_sum = {m: np.zeros((H, W), np.int64) for m in range(1, 13)}
    n_cal_years = {m: 0 for m in range(1, 13)}

    for var, spec in VARS.items():
        tv0 = time.time()
        A = np.ma.filled(ds[var][:].astype(np.float32), np.nan)
        log(f"{var}: loaded in {time.time() - tv0:.0f}s")
        G["A"], G["step"] = A, spec["step"]
        vout = {"step": spec["step"], "scale": spec["scale"], "units": spec["units"], "days": [], "months": [], "clim": [], "all": None}

        # ---- daily fields, one archive per year --------------------------------------------------
        with Pool(a.procs) as pool:
            res = pool.map(enc_day, range(T), chunksize=16)
        per_year = {y: [] for y in years}
        for t, png, mean, n in res:
            if png is None:
                continue
            d = days[t]
            per_year[d.year].append((zxy_to_tileid(9, d.timetuple().tm_yday, 0), png))
            vout["days"].append([t, round(mean, 5), n])
        for y in years:
            p = os.path.join(a.out, "daily", f"HDCA_{var}_{y}.pmtiles")
            size = write_archive(p, per_year[y], TileType.PNG,
                                 {"name": f"HDCA {var} daily {y}", "format": "png", "type": "overlay",
                                  "addressing": "z=9, x=day of year (1..366), y=0", "field": f"{W}x{H} EASE-Grid 2.0 36 km",
                                  "encoding": {"kind": "numeric-8bit", "step": spec["step"], "nodata_dn": NODATA_DN, "units": spec["units"]}})
            out["archives"][f"daily/HDCA_{var}_{y}.pmtiles"] = {"bytes": size, "entries": len(per_year[y])}
        log(f"{var}: {len(vout['days'])} daily fields written ({time.time() - tv0:.0f}s)")

        # ---- monthly means + days observed --------------------------------------------------------
        tiles, ntiles = [], []
        for (y, m), idx in by_month.items():
            fld, cnt = mean_field(A, idx)
            x = (y - Y0) * 12 + (m - 1)
            tiles.append((zxy_to_tileid(9, x, 0), png_bytes(quantize(fld, spec["step"]))))
            st = stat(fld, land_px)
            vout["months"].append([f"{y}-{m:02d}", st["mean"], st["n"], len(idx)])
            if var == "SM":
                n_month_field[(y, m)] = cnt
                q = np.full((H, W), NODATA_DN, np.uint8)
                q[land] = np.minimum(cnt[land], 254)
                ntiles.append((zxy_to_tileid(9, x, 0), png_bytes(q)))
        p = os.path.join(a.out, "monthly", f"HDCA_{var}_monthly.pmtiles")
        size = write_archive(p, tiles, TileType.PNG, {"name": f"HDCA {var} monthly means", "format": "png", "type": "overlay",
                             "addressing": "z=9, x=(year-2015)*12+month-1, y=0",
                             "encoding": {"kind": "numeric-8bit", "step": spec["step"], "nodata_dn": NODATA_DN, "units": spec["units"]}})
        out["archives"][f"monthly/HDCA_{var}_monthly.pmtiles"] = {"bytes": size, "entries": len(tiles)}
        if ntiles:
            p = os.path.join(a.out, "monthly", "HDCA_N_monthly.pmtiles")
            size = write_archive(p, ntiles, TileType.PNG, {"name": "HDCA days observed per month", "format": "png", "type": "overlay",
                                 "addressing": "z=9, x=(year-2015)*12+month-1, y=0",
                                 "encoding": {"kind": "numeric-8bit", "step": 1, "nodata_dn": NODATA_DN, "units": "days"}})
            out["archives"]["monthly/HDCA_N_monthly.pmtiles"] = {"bytes": size, "entries": len(ntiles)}
        log(f"{var}: monthly means written ({time.time() - tv0:.0f}s)")

        # ---- climatology: record mean (x=0) and calendar months (x=1..12) ------------------------
        tiles = []
        fld, cnt = mean_field(A, range(T))
        tiles.append((zxy_to_tileid(9, 0, 0), png_bytes(quantize(fld, spec["step"]))))
        vout["all"] = {**stat(fld, land_px), "days_per_cell_mean": round(float(cnt[land].mean()), 1)}
        ntiles = []
        if var == "SM":
            q = np.full((H, W), NODATA_DN, np.uint8)
            q[land] = np.minimum(np.rint(cnt[land] / 16), 254)       # days / 16 so 11 years fit in 8 bits
            ntiles.append((zxy_to_tileid(9, 0, 0), png_bytes(q)))
        for m in range(1, 13):
            fld, cnt = mean_field(A, by_cal[m])
            tiles.append((zxy_to_tileid(9, m, 0), png_bytes(quantize(fld, spec["step"]))))
            ny = len({days[t].year for t in by_cal[m]})
            vout["clim"].append([m, stat(fld, land_px)["mean"], stat(fld, land_px)["cover"], ny])
            if var == "SM":
                per_year_n = np.zeros((H, W), np.float64)
                for (y, mm_) , c in n_month_field.items():
                    if mm_ == m:
                        per_year_n += c
                q = np.full((H, W), NODATA_DN, np.uint8)
                q[land] = np.minimum(np.rint(per_year_n[land] / ny), 254)
                ntiles.append((zxy_to_tileid(9, m, 0), png_bytes(q)))
        p = os.path.join(a.out, "clim", f"HDCA_{var}_clim.pmtiles")
        size = write_archive(p, tiles, TileType.PNG, {"name": f"HDCA {var} climatology", "format": "png", "type": "overlay",
                             "addressing": "z=9, x=0 record mean, x=1..12 calendar-month mean, y=0",
                             "encoding": {"kind": "numeric-8bit", "step": spec["step"], "nodata_dn": NODATA_DN, "units": spec["units"]}})
        out["archives"][f"clim/HDCA_{var}_clim.pmtiles"] = {"bytes": size, "entries": len(tiles)}
        if ntiles:
            p = os.path.join(a.out, "clim", "HDCA_N_clim.pmtiles")
            size = write_archive(p, ntiles, TileType.PNG, {"name": "HDCA days observed", "format": "png", "type": "overlay",
                                 "addressing": "z=9, x=0 total days / 16, x=1..12 mean days per calendar month, y=0",
                                 "encoding": {"kind": "numeric-8bit", "step": "16 (x=0) or 1", "nodata_dn": NODATA_DN, "units": "days"}})
            out["archives"]["clim/HDCA_N_clim.pmtiles"] = {"bytes": size, "entries": len(ntiles)}
        log(f"{var}: climatology written ({time.time() - tv0:.0f}s)")

        # ---- series store: one uint16 row per land cell -----------------------------------------
        if mm is not None:
            k = spec["k"]
            for s0 in range(0, S, 8192):
                sl = slice(s0, min(S, s0 + 8192))
                v = A[:, rows[sl], cols[sl]]                        # [T, s]
                q = np.full(v.shape, SER_NODATA, np.uint16)
                ok = np.isfinite(v)
                q[ok] = np.minimum(np.rint(v[ok] / spec["scale"]), SER_NODATA - 1)
                mm[sl, :, k] = q.T
            mm.flush()
            log(f"{var}: series filled ({time.time() - tv0:.0f}s)")
        out["vars"][var] = vout
        del A, res
        G.clear()

    if mm is not None:
        tv0 = time.time()
        ids = np.array([zxy_to_tileid(10, int(c), int(r)) for r, c in zip(rows, cols)], np.int64)
        order = np.argsort(ids)
        p = os.path.join(a.out, "series", "HDCA_series.pmtiles")
        tmp = p + ".part"
        with open(tmp, "wb") as fh:
            w = Writer(fh)
            for i in order:
                w.write_tile(int(ids[i]), np.ascontiguousarray(mm[i]).astype("<u2").tobytes())
            w.finalize({"tile_type": TileType.UNKNOWN, "tile_compression": Compression.NONE,
                        "min_lon_e7": -1800000000, "min_lat_e7": -850445000, "max_lon_e7": 1800000000, "max_lat_e7": 850445000,
                        "center_zoom": 0, "center_lon_e7": 0, "center_lat_e7": 0},
                       {"name": "HDCA pixel series", "type": "series", "addressing": "z=10, x=column, y=row",
                        "layout": f"uint16 little-endian [{T} days][SM, VOD, OMEGA]; 65535 = no data",
                        "scale": {v: VARS[v]["scale"] for v in VARS}, "first_day": days[0].isoformat()})
        os.replace(tmp, p)
        out["archives"]["series/HDCA_series.pmtiles"] = {"bytes": os.path.getsize(p), "entries": S}
        log(f"series archive written: {S} cells, {os.path.getsize(p) / 1e9:.2f} GB ({time.time() - tv0:.0f}s)")
        del mm
        os.remove(ser_path)

    out["month_days"] = {f"{y}-{m:02d}": len(idx) for (y, m), idx in by_month.items()}
    with open(os.path.join(a.work, "layers.json"), "w") as fh:
        json.dump(out, fh)
    log(f"done in {time.time() - t0:.0f}s -> {a.work}/layers.json")


if __name__ == "__main__":
    main()
