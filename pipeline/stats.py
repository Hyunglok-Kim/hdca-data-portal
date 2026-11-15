#!/usr/bin/env python3
"""First look at the merged HDCA file: value ranges, valid-pixel counts, day coverage, grid axes.

Writes work/stats.json plus the per-pixel masks the other scripts reuse:
  work/lats.npy, work/lons.npy        row-centre latitudes (406) and column-centre longitudes (964)
  work/n_valid_px.npy                 uint16 [406, 964]: number of days with a valid SM at each pixel
  work/day_valid.npy                  int32 [T]: valid SM pixels per day (0 = the day is missing)
Reads the file in blocks of days so memory stays around 2 GB.
"""
import argparse, json, time
import numpy as np
import netCDF4 as nc

ap = argparse.ArgumentParser()
ap.add_argument("--src", default="/home/cpuserver_data/personal_data/jaese/HDCA/Results/da_HDCA_2nd_2015_2025.nc")
ap.add_argument("--work", default="/data/personal_data/project_hdca_portal/work")
ap.add_argument("--block", type=int, default=120)
a = ap.parse_args()

VARS = {"SM": (0.0, 1.0, 1e-4), "VOD": (0.0, 6.0, 1e-3), "OMEGA": (0.0, 1.0, 1e-4), "Teff": (200.0, 350.0, 0.1)}
t0 = time.time()
ds = nc.Dataset(a.src)
T, H, W = ds["SM"].shape
lat2 = np.ma.filled(ds["latitude"][:], np.nan); lon2 = np.ma.filled(ds["longitude"][:], np.nan)
lats = np.nanmedian(lat2, axis=1); lons = np.nanmedian(lon2, axis=0)
tv = ds["time"]; times = nc.num2date(tv[:], tv.units, tv.calendar, only_use_cftime_datetimes=False)
hist = {v: np.zeros(int(round((hi - lo) / st)) + 1, np.int64) for v, (lo, hi, st) in VARS.items()}
below = {v: 0 for v in VARS}; above = {v: 0 for v in VARS}; vmin = {v: np.inf for v in VARS}; vmax = {v: -np.inf for v in VARS}
n_valid_px = np.zeros((H, W), np.int32); day_valid = np.zeros(T, np.int32)
corr_sm_vod = 0
for t in range(0, T, a.block):
    sl = slice(t, min(T, t + a.block))
    arrs = {v: np.ma.filled(ds[v][sl].astype(np.float32), np.nan) for v in VARS}
    ok = np.isfinite(arrs["SM"])
    n_valid_px += ok.sum(axis=0); day_valid[sl] = ok.sum(axis=(1, 2))
    for v, (lo, hi, st) in VARS.items():
        x = arrs[v][np.isfinite(arrs[v])]
        if not x.size: continue
        vmin[v] = min(vmin[v], float(x.min())); vmax[v] = max(vmax[v], float(x.max()))
        below[v] += int((x < lo).sum()); above[v] += int((x > hi).sum())
        idx = np.clip(np.rint((x - lo) / st).astype(np.int64), 0, hist[v].size - 1)
        hist[v] += np.bincount(idx, minlength=hist[v].size)
    print(f"{time.strftime('%H:%M:%S')} days {sl.start}-{sl.stop} done ({time.time() - t0:.0f}s)", flush=True)

def pct(v, ps):
    lo, hi, st = VARS[v]; c = np.cumsum(hist[v]); n = c[-1]
    return {str(p): round(float(lo + np.searchsorted(c, n * p / 100.0) * st), 5) for p in ps}
out = {"shape": [T, H, W], "first": str(times[0])[:10], "last": str(times[-1])[:10],
       "days_total": int(T), "days_with_data": int((day_valid > 0).sum()),
       "missing_days": [str(times[i])[:10] for i in np.nonzero(day_valid == 0)[0]],
       "px_any_valid": int((n_valid_px > 0).sum()), "px_total": int(H * W),
       "px_ge_30_days": int((n_valid_px >= 30).sum()), "px_ge_365_days": int((n_valid_px >= 365).sum()),
       "day_valid_mean": float(day_valid[day_valid > 0].mean()), "day_valid_max": int(day_valid.max()),
       "lat_rows_nan": int(np.isnan(lats).sum()), "lon_cols_nan": int(np.isnan(lons).sum()),
       "lat_first_last": [float(lats[0]), float(lats[-1])], "lon_first_last": [float(lons[0]), float(lons[-1])],
       "vars": {v: {"min": vmin[v], "max": vmax[v], "n": int(hist[v].sum()), "below_range": below[v], "above_range": above[v],
                    "pct": pct(v, [0.1, 1, 2, 25, 50, 75, 98, 99, 99.9, 99.99])} for v in VARS}}
np.save(f"{a.work}/lats.npy", lats); np.save(f"{a.work}/lons.npy", lons)
np.save(f"{a.work}/n_valid_px.npy", n_valid_px.astype(np.uint16)); np.save(f"{a.work}/day_valid.npy", day_valid)
for v in VARS: np.save(f"{a.work}/hist_{v}.npy", hist[v])
json.dump(out, open(f"{a.work}/stats.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "missing_days"}, indent=1)); print("missing days:", len(out["missing_days"]))
