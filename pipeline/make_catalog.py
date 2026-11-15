#!/usr/bin/env python3
"""Assemble catalog.json — the one file the portal reads first.

Combines work/layers.json (what build_layers.py wrote), work/stats.json (stats.py) and an inventory
of the source NetCDF files on the lab storage (daily files per year, sizes, the merged file).
"""
import argparse
import json
import os
import time
from datetime import date, timedelta

import numpy as np

EASE = {"name": "EASE-Grid 2.0 global, 36 km (EPSG:6933)", "rows": 406, "cols": 964, "cell_m": 36032.220840584,
        "x0_m": -17367530.445161, "y0_m": 7314540.830638, "a": 6378137.0, "e2": 0.00669437999014, "lat1": 30.0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", default="/data/personal_data/project_hdca_portal/work")
    ap.add_argument("--out", default="/data/personal_data/project_hdca_portal/out")
    ap.add_argument("--daily-root", default="/home/cpuserver_data/personal_data/jaese/HDCA/Retrieved_2nd")
    ap.add_argument("--merged", default="/home/cpuserver_data/personal_data/jaese/HDCA/Results/da_HDCA_2nd_2015_2025.nc")
    ap.add_argument("--version", default=time.strftime("prototype-%Y-%m-%d"))
    a = ap.parse_args()

    L = json.load(open(os.path.join(a.work, "layers.json")))
    S = json.load(open(os.path.join(a.work, "stats.json")))
    lats = np.load(os.path.join(a.work, "lats.npy"))
    lons = np.load(os.path.join(a.work, "lons.npy"))
    first = date.fromisoformat(L["first"])
    T = L["T"]

    # inventory of the daily files: Retrieved_2nd/YYYY/YYYY.MM.DD/HDCA_2nd_YYYYMMDD.nc
    size_by_day = {}
    for y in sorted(os.listdir(a.daily_root)):
        yd = os.path.join(a.daily_root, y)
        if not os.path.isdir(yd):
            continue
        for d in os.listdir(yd):
            dd = os.path.join(yd, d)
            if not os.path.isdir(dd):
                continue
            for f in os.listdir(dd):
                if f.endswith(".nc"):
                    size_by_day[f"{d[:4]}-{d[5:7]}-{d[8:10]}"] = os.path.getsize(os.path.join(dd, f))

    vars_ = {}
    days = {}
    for v, vo in L["vars"].items():
        vars_[v] = {"step": vo["step"], "series_scale": vo["scale"], "units": vo["units"],
                    "all": vo["all"], "clim": [{"month": m, "mean": mean, "cover": cov, "years": ny} for m, mean, cov, ny in vo["clim"]]}
        for t, mean, n in vo["days"]:
            d = (first + timedelta(days=t)).isoformat()
            days.setdefault(d, {"d": d, "i": t, "n": n})[v] = mean
    months = {}
    for v, vo in L["vars"].items():
        for ym, mean, n, nd in vo["months"]:
            months.setdefault(ym, {"ym": ym, "days": nd, "n": n, "cover": round(n / L["land_px"], 4)})[v] = mean
    for ym, rec in months.items():                       # days that actually have a field (the time axis is complete, the data are not)
        rec["with_data"] = sum(1 for d in days if d.startswith(ym))
    for d, rec in days.items():
        rec["bytes"] = size_by_day.get(d, 0)
    all_days = [(first + timedelta(days=t)).isoformat() for t in range(T)]
    missing = [d for d in all_days if d not in days]
    years = []
    for y in L["years"]:
        ds_ = [r for d, r in days.items() if d.startswith(str(y))]
        years.append({"year": y, "files": len(ds_), "bytes": sum(r["bytes"] for r in ds_),
                      "missing": [d for d in missing if d.startswith(str(y))]})

    series = None
    sp = os.path.join(a.work, "series_parts.json")
    if os.path.exists(sp):                                 # pack_series.py ran: the split, gzipped store replaces the single file
        series = json.load(open(sp))
        L["archives"] = {k: v for k, v in L["archives"].items() if k != "series/HDCA_series.pmtiles"}
        for part in series["parts"]:
            L["archives"][part["file"]] = {"bytes": part["bytes"], "entries": part["cells"]}

    cat = {
        "id": "hdca-smap-36km",
        "version": a.version,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "grid": {**EASE, "lats": [round(float(x), 4) for x in lats], "lons": [round(float(x), 4) for x in lons]},
        "encoding": {"kind": "numeric-8bit-field", "nodata_dn": 255, "field": "964 x 406 PNG, value = DN x step, DN 255 = no data",
                     "series": f"uint16 little-endian [{T} days][SM, VOD, OMEGA] per land cell, 65535 = no data, value = raw x series_scale"},
        "archives": {"daily": "daily/HDCA_{VAR}_{YYYY}.pmtiles  z9/x=day-of-year/y0",
                     "monthly": "monthly/HDCA_{VAR}_monthly.pmtiles  z9/x=(year-2015)*12+month-1/y0",
                     "clim": "clim/HDCA_{VAR}_clim.pmtiles  z9/x=0 record mean, 1..12 calendar month/y0",
                     "series": "series/HDCA_series_r<r0>-<r1>.pmtiles  z10/x=column/y=row (one file per row band)",
                     "files": L["archives"]},
        "series": series,
        "variables": vars_,
        "land_px": L["land_px"],
        "record": {"first": L["first"], "last": L["last"], "n": T, "with_tiles": len(days), "unit": "day",
                   "missing": missing, "train": None},
        "source": {"grid": "EASE-Grid 2.0 global 36 km, 406 x 964 cells", "format": "NetCDF-4 (zlib), float32; SM, VOD, OMEGA, TBv, TBh, Teff + 2-D latitude/longitude",
                   "input": "SMAP L3 Radiometer Global Daily 36 km EASE-Grid Soil Moisture (SPL3SMP v9), AM overpass",
                   "merged_file": "Results/da_HDCA_2nd_2015_2025.nc", "merged_bytes": os.path.getsize(a.merged) if os.path.exists(a.merged) else 0,
                   "daily_dir": "Retrieved_2nd/YYYY/YYYY.MM.DD/HDCA_2nd_YYYYMMDD.nc",
                   "daily_files": len(days), "daily_bytes": sum(r["bytes"] for r in days.values()), "years": years},
        "stats": {v: {"min": S["vars"][v]["min"], "max": S["vars"][v]["max"], "pct": S["vars"][v]["pct"],
                      "above_1": S["vars"][v].get("above_range", 0) if v == "OMEGA" else 0, "n": S["vars"][v]["n"]} for v in ("SM", "VOD", "OMEGA")},
        "days": [days[d] for d in all_days if d in days],
        "months": [months[ym] for ym in L["months"]],
    }
    out = os.path.join(a.out, "catalog.json")
    with open(out + ".part", "w") as fh:
        json.dump(cat, fh, separators=(",", ":"))
    os.replace(out + ".part", out)
    print(f"{out}: {len(cat['days'])} days with fields of {T}, {len(cat['months'])} months, {len(missing)} missing days, "
          f"{os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
