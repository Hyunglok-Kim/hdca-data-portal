# HDCA Data Portal

Web portal for the lab's HDCA product: daily soil moisture (SM), vegetation optical depth (VOD) and
effective scattering albedo (ω̄) retrieved from SMAP L-band brightness temperatures on the 36 km
EASE-Grid 2.0 global grid, 1 April 2015 – 31 December 2025 (Lee et al., accepted in *Remote Sensing of
Environment*; preprint doi:10.2139/ssrn.7287481). It shows daily, monthly and climatological maps on a
globe and the full 11-year record of any cell for all three variables.

**Status (2026-11-15): prototype, lab-internal.** The paper is accepted but not yet published, so the
portal runs inside the lab dashboard only. At publication the same folder goes public the way the
Prithvi-ET portal is meant to (GitHub Pages, embedded in hydroai.net), and the NetCDF files to a
repository such as Zenodo.

This portal follows the Prithvi-ET portal (`~/orca/projects/prithvi-et/portal/`) in structure, look and
dashboard wiring; read that folder's `CLAUDE.md` for the shared background. What differs is the data
model: a coarse global grid instead of 30 m tiles, which changes how the map gets its numbers (below).

## Where things are

| What | Where |
|---|---|
| Portal app (this folder) | `~/orca/projects/hdca/portal/` — static site, no build step |
| Source NetCDF (CPU server) | `/home/cpuserver_data/personal_data/jaese/HDCA/Retrieved_2nd/YYYY/YYYY.MM.DD/HDCA_2nd_YYYYMMDD.nc` (3,842 files, 30 GB) and the merged `…/HDCA/Results/da_HDCA_2nd_2015_2025.nc` (3.6 GB) |
| Build workspace (CPU server) | `/data/personal_data/project_hdca_portal/` (`scripts/`, `venv/`, `out/`, `work/`, `logs/`) |
| Browse data served to the lab (3.05 GB) | `~/.hydroai/datasets/hdca/` on the dashboard Mac (outside the Drive-synced tree) |
| Dashboard pages | `hydroai-dashboard/gateway/static/research-data.html` (hub), `hdca.html` (shell) |
| Dashboard backend | `hydroai-dashboard/gateway/research_data.py` (unchanged), registry `gateway/research_datasets.json` (entry `hdca`) |
| Manuscript and code | `../Time_Varing_1Order_Scattering/` (Overleaf-synced), `../Time_Varing_1Order_Scattering_code/` |

```
portal/
  index.html          one page: Explore / Download / Use in code / About the data
  css/portal.css      Prithvi-ET's stylesheet plus the day picker
  js/config.js        deployment settings (data location, public NetCDF address, contacts)
  js/app.js           the app (MapLibre GL globe + in-browser projection + SVG charts), one IIFE
  assets/land-110m.json   Natural Earth land outline, cut at the antimeridian (public domain)
  pipeline/           stats → layers → catalog; runs on the CPU server, not here
  tests/smoke.py      headless-browser test (Playwright); field_ref.json holds field checksums
  dev_server.py       local preview with HTTP Range support
```

## How the data reaches the map

```
merged NetCDF [3928 days x 406 x 964]                     CPU server
  └─ pipeline/stats.py       value ranges, land mask (cells with any SM), day coverage     -> work/
  └─ pipeline/build_layers.py
       daily/HDCA_<VAR>_<YYYY>.pmtiles      one 964x406 8-bit PNG per day (entry z9/x=day-of-year/y0)
       monthly/HDCA_<VAR>_monthly.pmtiles   mean of each month's days   (z9/x=(year-2015)*12+month-1)
       clim/HDCA_<VAR>_clim.pmtiles         x=0 record mean, x=1..12 calendar-month means
       series/HDCA_series.pmtiles           per land cell: uint16 LE [3928][SM, VOD, OMEGA]  (z10/x=col/y=row)
  └─ pipeline/make_catalog.py             catalog.json — the one file the app reads first
rsync to the dashboard Mac → gateway serves /rd/hdca/data/… → browser
```

**Why whole fields, not tiles.** The grid has 391,384 cells; a day is one ~100 KB PNG. The browser
fetches the one field it needs, keeps the numbers, and projects them onto Web Mercator tiles itself
(`hdca://` protocol in `app.js`): for each tile pixel, latitude → EASE row through the authalic
latitude, longitude → column linearly. Cells are drawn as the blocks they are, nothing is resampled,
the cursor readout is exact, and a day-by-day "Play" costs one small request per day.

**Why PMTiles as the container.** The gateway serves only `.json` and `.pmtiles` from a portal's data
folder and counts `.pmtiles` bytes for the hub card. A PMTiles archive is a range-readable key-value
store addressed by z/x/y, so the day-of-year, month index and cell row/column are used as keys. The
addressing is written in each archive's metadata and in `catalog.json`. `pmtiles.js` fetches an entry
with one or two range requests (leaf directory, then data).

**Field contract.** PNG 964 × 406, 8-bit grayscale, `value = DN × step`, `DN 255 = no retrieval`.
Steps: SM 0.0035 m³/m³ (DN 254 = 0.889 ≥ record maximum 0.884), VOD 0.006 (DN 254 = 1.524 ≥ search bound
1.5), ω̄ 0.001 (DN 254 = 0.254; larger values are drawn as ≥ 0.254), days observed 1 (record total ÷ 16).
The series store is exact to 1e-4 (SM, VOD) and 2e-4 (ω̄); 65535 = no retrieval.

**Statistics.** The EASE grid is equal-area, so a plain mean over cells is an area mean; the app computes
means, coverage and the legend histogram from the field it has, and `catalog.json` carries the pipeline's
exact means for the layer card. "Land" is the 105,938 cells with at least one SM retrieval in the record.

## Rebuilding

Runs on the CPU server as `discover`; one full run took five minutes with 12 PNG encoders and about
8 GB of memory (one variable loaded at a time). The usage-declaration page (`/server.html`, pool `cpu`)
needs a member password, so declare there yourself if the run will be long.

```bash
ssh -p 33222 discover@172.26.252.31
cd /data/personal_data/project_hdca_portal
# copy pipeline/*.py and run.sh into scripts/ if they changed
scripts/run.sh all              # stats (5 min) → layers (5 min) → catalog (seconds)
scripts/run.sh catalog          # only rebuild catalog.json
venv/bin/python scripts/make_field_ref.py out > field_ref.json   # then copy to tests/ if the fields changed
```

- `venv/` is `python3 -m venv --system-site-packages` plus `pip install netCDF4 pmtiles`; NumPy and
  Pillow come from the system (Python 3.10).
- Output: `out/daily` 489 MB (33 archives), `out/monthly` 34 MB, `out/clim` 3.4 MB, `out/series` 2.5 GB,
  `out/catalog.json` 0.4 MB. Copy to the dashboard Mac (about 6 MB/s from the server room, ~9 minutes):

```bash
rsync -a --exclude '*.part' --exclude '*.dat' -e "ssh -i ~/.hydroai/l40_ssh_key -p 33222" \
  discover@172.26.252.31:/data/personal_data/project_hdca_portal/out/ ~/.hydroai/datasets/hdca/
```

No gateway restart is needed after new data arrive; `catalog.json` is read on every page load.
When a new year of retrievals is added, `stats` must run again (the land mask and day coverage change)
and the series store is rebuilt whole.

## Running it

**Local preview** (needs the data under `~/.hydroai/datasets/hdca/`):

```bash
~/.venvs/hydroai/bin/python dev_server.py            # http://127.0.0.1:8791/
~/miniconda3/bin/python tests/smoke.py --base http://127.0.0.1:8791/ --shots /tmp/shots --ref tests/field_ref.json
~/miniconda3/bin/python tests/smoke.py --browser webkit --base http://127.0.0.1:8791/ --shots /tmp/shots-safari --ref tests/field_ref.json
```

`python -m http.server` will not do: PMTiles needs HTTP Range requests.

**In the lab dashboard**: `http://192.168.50.88:8787/hdca.html` (sidebar 🌏 연구자료). The gateway serves
this folder at `/rd/hdca/` and the data at `/rd/hdca/data/`, for signed-in lab members only. The shell
page passes the internal settings in the address:
`?embed=1&data=/rd/hdca/data/&nas=/home/cpuserver_data/personal_data/jaese/HDCA`. Editing a file here
changes what the lab sees on the next page load, so bump the `?v=` on the script and style tags in
`index.html` when you change them.

To run the smoke test against the dashboard copy, mint a session cookie as described at the top of
`gateway/research_data.py` (no password involved) and pass it in the environment:

```bash
SMOKE_COOKIE="hydroai_rd=<token>" ~/miniconda3/bin/python tests/smoke.py --shots /tmp/shots-live --ref tests/field_ref.json \
  --base "http://127.0.0.1:8787/rd/hdca/index.html?data=/rd/hdca/data/&nas=/home/cpuserver_data/personal_data/jaese/HDCA"
```

URL parameters the app understands: `embed=1` (fixed map height, reports its height to the parent
frame), `data=/path/` (same-origin data location), `nas=/path` (lab storage path shown in Download and
Code), `intro=0` (skip the globe ease-in), `tab=download|code|about`, `var=SM|VOD|OMEGA|N`,
`date=YYYY-MM-DD` (open on that day).

## Going public (at publication)

1. Put the data folder (3.05 GB) and the NetCDF files somewhere public with CORS for `GET` + `Range`
   (Cloudflare R2, as planned for Prithvi-ET). Archive the NetCDF files on Zenodo for a DOI.
2. In `js/config.js` set `dataBase` to the data address and `ncBase` to the NetCDF address. The Download
   tab then shows direct links and the code examples use them.
3. Make this folder its own GitHub repository with Pages enabled (the data do not go in the repo). A
   private repository's Pages site is public, so do not enable Pages before the paper is out.
4. Embed in Webflow like Hampyeong: `<iframe src="https://<pages address>/index.html?embed=1" width="100%" height="1500" style="border:0"></iframe>`.
5. Remove `<meta name="robots" content="noindex">` from `index.html`, replace "accepted" with the
   published reference and DOI in the About tab and in `pipeline/make_catalog.py`'s source block, and
   point the dashboard's shell page at the public address.

## Rules that must survive any redesign

- **Say what ω̄ is.** It is a parameter of the inversion; 4.2 % of retrievals have ω̄ ≥ 1. The About tab,
  the layer card and the CSV header all say so, and the map clips the scale at 0.25 rather than hiding
  those cells.
- **Never hide gaps.** A single day is ~43 % of land (swath pattern); monthly and climatological layers
  are means over the retrieved days, always shown with the share of land retrieved. 86 days have no file
  (SMAP safe modes in June–July 2019 and August–September 2022); the calendar and the About tab list them.
- **36 km is the grid.** The readout says "36 km cell", cells are drawn as blocks, and the About tab
  says what a cell averages.
- **Validation is five sites.** The portal names them (they are in the jump list and as markers) and
  says the quality elsewhere is unverified; no accuracy numbers are quoted beyond what the paper reports.
- **Basemap without labels.** Esri World Imagery; the only labels are the validation sites. Public label
  layers bring the East Sea / Dokdo naming problem.
- **Fields and series are for looking, not analysis.** Every CSV says so and points to the NetCDF files.

## Gotchas already paid for

- **Analytic grid mapping.** The EASE-Grid 2.0 row of a latitude comes from the authalic q(φ) with the
  grid constants in `app.js` (`EASE`). `loadCatalog` checks every catalogue row centre lands in its own
  row and warns otherwise; `tests/smoke.py` fails on a mismatch.
- **Raster tile zoom is rounded**, so the data source stops at `maxzoom` 7 and MapLibre overzooms with
  `raster-resampling: nearest` above zoom 2.5 to keep cell edges crisp.
- **`decodePNG8` checks the image size** (964 × 406), not 256 × 256 as in Prithvi-ET; the canvas path is
  only a fallback for browsers without `DecompressionStream`.
- **The pmtiles JS reader refuses zooms outside the header's min/max**, which the Python writer derives
  from the entries. Daily/monthly/climatology archives therefore have min = max = 9 and the series
  archive 10; every lookup must use exactly those zooms.
- **The input[type=date] fires `change`, not `input`**, in most browsers when typed; a day without a file
  falls through to the next day with one and the layer card says so.

## Not done yet

- Regional means (click a country or basin for its series without reading cells).
- Teff, TBv and TBh as map layers (they are in the files, not in the browse archives).
- Korean UI text, a dark theme, a favicon.
