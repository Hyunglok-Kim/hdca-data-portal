#!/usr/bin/env bash
# Build everything the portal needs, on the CPU server as `discover`.
#
#   run.sh stats      value ranges, land mask, day coverage          -> work/stats.json (+ .npy)
#   run.sh layers     daily/monthly/climatology fields + series store -> out/{daily,monthly,clim,series}
#   run.sh pack       gzip + split the series store for publishing   -> out/series/*_r*.pmtiles
#   run.sh catalog    catalog.json                                     -> out/catalog.json
#   run.sh all        the three in order
#
# Environment: ROOT (work dir), SRC (merged NetCDF), PROCS (PNG encoders in parallel)
set -euo pipefail
ROOT=${ROOT:-/data/personal_data/project_hdca_portal}
SRC=${SRC:-/home/cpuserver_data/personal_data/jaese/HDCA/Results/da_HDCA_2nd_2015_2025.nc}
PROCS=${PROCS:-12}
PY=$ROOT/venv/bin/python
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$ROOT/out" "$ROOT/work" "$ROOT/logs"

step() {
  case "$1" in
    stats)   "$PY" "$HERE/stats.py" --src "$SRC" --work "$ROOT/work" 2>&1 | tee "$ROOT/logs/stats.log" ;;
    layers)  "$PY" "$HERE/build_layers.py" --src "$SRC" --work "$ROOT/work" --out "$ROOT/out" --procs "$PROCS" 2>&1 | tee "$ROOT/logs/layers.log" ;;
    pack)    "$PY" "$HERE/pack_series.py" --src "$ROOT/out/series/HDCA_series.pmtiles" --out-dir "$ROOT/out/series" --work "$ROOT/work" 2>&1 | tee "$ROOT/logs/pack.log" ;;
    catalog) "$PY" "$HERE/make_catalog.py" --work "$ROOT/work" --out "$ROOT/out" 2>&1 | tee "$ROOT/logs/catalog.log" ;;
    *) echo "usage: $0 stats | layers | pack | catalog | all" >&2; exit 2 ;;
  esac
}
if [ "${1:-}" = all ]; then step stats; step layers; step pack; step catalog; else step "${1:-}"; fi
