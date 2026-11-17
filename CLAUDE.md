# HDCA Data Portal

Web portal for the lab's HDCA product: daily soil moisture (SM), vegetation optical depth (VOD) and
effective scattering albedo (ω̄) retrieved from SMAP L-band brightness temperatures on the 36 km
EASE-Grid 2.0 global grid, 1 April 2015 – 31 December 2025 (Lee et al., accepted in *Remote Sensing of
Environment*; preprint doi:10.2139/ssrn.7287481). It shows daily, monthly and climatological maps on a
globe and the full 11-year record of any cell for all three variables.

**Status (2026-11-15): public on GitHub Pages** at https://hyunglok-kim.github.io/hdca-data-portal/
(the PI's decision the same day: "공개해") **and embedded on hydroai.net/data#hdca** the way Hampyeong is.
The paper is accepted but not yet published. The lab dashboard embeds the public page (`hdca.html`) and still
serves a local copy at `/rd/hdca/` for lab members as a fallback. Still to do: deposit the NetCDF files
(Zenodo or similar) and put the DOI into `js/config.js` (`ncBase`) and the About tab.

This portal follows the Prithvi-ET portal (`~/orca/projects/prithvi-et/portal/`) in structure, look and
dashboard wiring; read that folder's `CLAUDE.md` for the shared background. What differs is the data
model: a coarse global grid instead of 30 m tiles, which changes how the map gets its numbers (below).

## Where things are

| What | Where |
|---|---|
| Portal app (this folder) | `~/orca/projects/hdca/portal/` — static site, no build step; **git repository** pushed to github.com/Hyunglok-Kim/hdca-data-portal (GitHub Pages, branch `main`, root) |
| Public field data | `data/` in this repository (catalog.json, daily/, monthly/, clim/ — 527 MB; a copy of the dashboard Mac's folder minus the series) |
| Public series store | github.com/Hyunglok-Kim/hdca-data-portal-series (`~/orca/projects/hdca/series-site/`, 454 MB), served at https://hyunglok-kim.github.io/hdca-data-portal-series/series/… — same origin as the portal, so no CORS |
| Source NetCDF (CPU server) | `/home/cpuserver_data/personal_data/jaese/HDCA/Retrieved_2nd/YYYY/YYYY.MM.DD/HDCA_2nd_YYYYMMDD.nc` (3,842 files, 30 GB) and the merged `…/HDCA/Results/da_HDCA_2nd_2015_2025.nc` (3.6 GB) |
| Build workspace (CPU server) | `/data/personal_data/project_hdca_portal/` (`scripts/`, `venv/`, `out/`, `work/`, `logs/`) |
| Browse data served to the lab (0.98 GB) | `~/.hydroai/datasets/hdca/` on the dashboard Mac (outside the Drive-synced tree) |
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
       series/HDCA_series.pmtiles           per land cell: uint16 LE [3928][SM, VOD, OMEGA]  (z10/x=col/y=row), 2.5 GB
  └─ pipeline/pack_series.py              gzip each entry and split by row band into six files under 90 MB (0.48 GB)
       series/HDCA_series_r<r0>-<r1>.pmtiles   (tile_compression gzip; pmtiles.js inflates on read; the single file is deleted)
  └─ pipeline/make_catalog.py             catalog.json — the one file the app reads first (lists the series parts)
rsync to the dashboard Mac → gateway serves /rd/hdca/data/… → browser          (lab copy)
copy data/ into this repository, series/ into hdca-data-portal-series → push     (public copy)
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

**Why two GitHub repositories.** GitHub Pages serves one site of at most 1 GB and files under 100 MB, and
supports range requests (checked). Fields are 527 MB, the gzipped series store 454 MB, so the series lives
in `hdca-data-portal-series` on the same origin (`js/config.js` `seriesBase`). Release assets were ruled
out: they redirect to a host without CORS headers. The series entries are the exact uint16 values; gzip
alone brings 2.5 GB down to 0.48 GB because nodata days are long runs of 0xFFFF.

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
# ssh to the CPU server (address, port, user and key are in the lab dashboard's server page and the PI's notes)
cd /data/personal_data/project_hdca_portal
# copy pipeline/*.py and run.sh into scripts/ if they changed
scripts/run.sh all              # stats (5 min) → layers (5 min) → pack (1 min) → catalog (seconds)
scripts/run.sh catalog          # only rebuild catalog.json
venv/bin/python scripts/make_field_ref.py out > field_ref.json   # then copy to tests/ if the fields changed
```

- `venv/` is `python3 -m venv --system-site-packages` plus `pip install netCDF4 pmtiles`; NumPy and
  Pillow come from the system (Python 3.10).
- Output: `out/daily` 489 MB (33 archives), `out/monthly` 34 MB, `out/clim` 3.4 MB, `out/series` 454 MB
  (six gzipped row bands; `pack` deletes nothing, so remove the 2.5 GB `HDCA_series.pmtiles` by hand if it
  should not be copied), `out/catalog.json` 0.4 MB. Copy to the dashboard Mac (about 6 MB/s, ~3 minutes):

```bash
rsync -a --exclude '*.part' --exclude '*.dat' -e "ssh <lab CPU server options>" \
  <cpu-server>:/data/personal_data/project_hdca_portal/out/ ~/.hydroai/datasets/hdca/
```

No gateway restart is needed after new data arrive; `catalog.json` is read on every page load.
When a new year of retrievals is added, `stats` must run again (the land mask and day coverage change)
and the series store is rebuilt whole. To publish the new data: `rsync -a --delete --exclude series
~/.hydroai/datasets/hdca/ data/` here and `rsync -a --delete ~/.hydroai/datasets/hdca/series/
../series-site/series/`, commit and push both repositories (each push adds the changed archives to
history, so publish per data version, not per experiment).

## Running it

**Local preview** (needs the data under `~/.hydroai/datasets/hdca/`):

```bash
~/.venvs/hydroai/bin/python dev_server.py --port 8792        # http://127.0.0.1:8792/  (8791 is often the Prithvi-ET preview)
~/miniconda3/bin/python tests/smoke.py --base http://127.0.0.1:8792/ --query "intro=0&data=/data/" --shots /tmp/shots --ref tests/field_ref.json
~/miniconda3/bin/python tests/smoke.py --browser webkit --base http://127.0.0.1:8792/ --query "intro=0&data=/data/" --shots /tmp/shots-safari --ref tests/field_ref.json
```

`python -m http.server` will not do: PMTiles needs HTTP Range requests. Pass `data=/data/` so the preview
reads the series store locally; without it `js/config.js` points the series at the public site.

The test ends with two checks on the map failing: it takes WebGL away (a page whose canvases give no WebGL
context) and expects the message in the map's place with the rest of the page working, and it loses the map's
context on a running page and expects the message after a few seconds and the map back when the context
returns. Chromium is run with software drawing (SwiftShader) and Firefox does the same by itself, so the test
does not depend on the machine's graphics card. Headless WebKit uses the real one: when that card is busy with
other work WebKit loses its contexts ("WebGL: context lost", the first screen times out), and so does every
other map page on the machine. That is the machine, not the page.

**Public site**: https://hyunglok-kim.github.io/hdca-data-portal/ — test it with
`tests/smoke.py --base https://hyunglok-kim.github.io/hdca-data-portal/index.html --shots /tmp/shots-public --ref tests/field_ref.json`
(no cookie). Pages rebuilds a minute or two after a push.

**In the lab dashboard**: `/hdca.html` on the lab dashboard (sidebar 🌏 연구자료) embeds the public
site (`?embed=1`), the way `hampyeong.html` does. The gateway also serves this folder at `/rd/hdca/` and
the data at `/rd/hdca/data/` for signed-in lab members (a fallback when github.io is unreachable):
`/rd/hdca/index.html?embed=1&data=/rd/hdca/data/&nas=/home/cpuserver_data/personal_data/jaese/HDCA`.
Bump the `?v=` on the script and style tags in `index.html` when you change them.

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

## Public release (done 2026-11-15) and what is left

Done: this folder is the repository `hdca-data-portal` with Pages on `main`/root; the series store is
`hdca-data-portal-series`; `noindex` is gone; the dashboard's `hdca.html` embeds the public page and the
registry entry is `public` with `public_url`.

**hydroai.net (done the same day, through the Webflow Designer).** The Data page is one HTML Embed whose
hash routing shows one panel per dataset card. The HDCA panel now holds
`<iframe data-src="https://hyunglok-kim.github.io/hdca-data-portal/index.html?embed=1&hidefooter=1" …>` plus a
`portal-logo-bar` (HydroAI, GIST, MIT, NASA JPL, FMI; the images come from this repository's `assets/logos/`),
the card reads "Live · Open portal →", `show()` loads whichever active panel has a `data-src` iframe, and a
`message` listener sizes the HDCA frame from the portal's `portalHeight` posts. `hidefooter=1` hides the
portal's own strip because the page draws the same bar. Editing it again: Designer → Pages → Data →
Navigator → Code Embed → "Edit code embed"; the editor is CodeMirror 6, so copy the text out with ⌘A ⌘C,
patch it, and paste it back rather than typing. `embed/hydroai-data-page.html` here is the intended content of
that embed (the whole Data page: hub cards, three panels, routing script); after any Designer edit, copy the
editor's text back over it so the two stay equal. Its entrance animation (panel fade, cards rising, the
"Opening the portal" mark until the iframe loads) was written 2026-11-16 and **has been live since that
evening**: the file was pasted through the Designer and the site published to hydroai.net (from the Prithvi-ET
portal session, at the lab head's word). The editor's text, the live page and this file were compared and are
equal, byte for byte; all three cards were then checked on the live page.

That embed is shared with the other datasets' panels, and other sessions edit it for theirs. The copy first
committed here (`689078a`) was made from a snapshot older than the ET panel's change of 2026-11-15: pasted as
it was, it would have put the old static ET panel back (with the evaluation figures that were taken off the
site), set the ET card back to "New", and dropped the sizing of the ET frame. On 2026-11-16 it was replaced by
the live text plus the entrance and nothing else (28,139 characters, sha1 `9fab5b6d…`), and that is what was
pasted. **Before the next paste, copy the editor's text out and compare it with this file; if they differ,
somebody has edited the page since — merge, never overwrite.** After pasting, check all three cards on the
live page.

The retrieval code (`Time_Varing_1Order_Scattering_code`) and the manuscript repository stay private; the
portal does not link them (PI decision 2026-11-15). The pipeline here only builds browse data from the product.

Left for the PI:
1. **NetCDF files**: deposit on Zenodo (or similar) for a DOI; then set `ncBase` in `js/config.js` to the
   file address, so the Download tab shows direct links and the code examples use them.
2. **At publication**: replace "accepted" with the published reference and DOI in the About tab and in
   `pipeline/make_catalog.py`'s source block, and in `gateway/research_datasets.json`.

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
- **The partner strip is HydroAI, GIST, MIT, NASA JPL, FMI** (the co-authors' institutions), fixed to the
  bottom like Hampyeong's; `?hidefooter=1` hides it where the host page draws its own.
- **Fields and series are for looking, not analysis.** Every CSV says so and points to the NetCDF files.
- **The name is spelled out; "When to use" comes first, then the novelty.** The header says "Hybrid Dual-Channel
  Algorithm"; the Explore tab opens with a "When to use this data" box (satellite soil moisture has been unusable
  under dense vegetation; this record is expected to serve any study that needs observed soil moisture there)
  beside a "What is new" box (the time-varying effective scattering albedo), and the bottom of
  the Explore tab explains method and results in plain words with six of the paper's figures
  (`assets/figures/Fig3,4,5,7,9,11.jpg`, web copies of the manuscript's PNGs; the numbers in the text are
  quoted from the manuscript). Keep those numbers in step with the published version.
- **The retrieval code and manuscript repositories are private** and the portal does not link them.
- **The opening globe is sized to the map box** (`globeView()`: zoom for 80 % of the shorter side, at most
  1.55), because the fixed desktop zoom spilled the globe out of a phone-width frame.
- **Never leave a visitor on the loading screen.** The map needs WebGL and cannot be drawn without it. Where
  the browser gives no context (`webglWorks()`), or the map fails to start, or its context is lost and has not
  come back after `LOST_WAIT`, `noMap()` puts a message where the map would be — what is wrong and what to do
  about it — and takes the loading screen away. The cards, the layer buttons and the other tabs go on working
  without the map (`applyLayer` allows for `map` being undefined); keep it so.
- **The opening is a sequence, not a page load** (PI, 2026-11-16: "좀 더 dynamic하게"): `startIntro()` in
  `app.js`. The globe starts small and 140° to the west and sweeps east into the map box over 3.2 s while
  the data layer fades up (`raster-opacity` 0 → slider value with a transition) and the lead boxes, layer
  bar, map and side cards rise in turn (`html.intro` + the `rise` keyframes in `portal.css`). It then turns
  slowly (10° per 7 s) until the first wheel, drag, touch, jump or pick (`stopSpin`, also on any `movestart`
  that is not ours), or for three minutes. `?intro=0` and `prefers-reduced-motion` skip all of it; the smoke
  test runs with `intro=0`. On hydroai.net the embed adds its own entrance: the panel fades in, the frame
  stays hidden behind a breathing globe mark until the iframe's `load` event, then fades up.
- **Every block inside `main` is either full width (1640 px) or centred** (`margin: 0 auto`, or a grid with
  `justify-content: center` like the About tab). A narrower block left against the margin reads to the PI as
  "text cut off, line breaks wrong" (the About tab in the first version, then the "From the paper" section).
  Check layouts at 2048 CSS px wide (the PI's display) as well as 1440 and 390 before saying a change is done.

## Gotchas already paid for

- **"The site does not open."** On 2026-11-17 this page and the Prithvi-ET one stayed on "Loading the
  catalog…" in the lab head's Chrome and looked broken. The servers and the pages were fine. Chrome's graphics
  process had been killed three times in a few minutes the evening before (the Mac's graphics card was
  overloaded by other work), after which Chrome keeps graphics acceleration off until it is restarted, and
  current Chrome does not draw WebGL in software instead. `new maplibregl.Map` then throws, and the loading
  screen was only ever taken away by the map's `load` event. Hence the check before the map is made and the
  message (added from the Prithvi-ET portal session, at the lab head's word, in both portals). To tell this
  case from a broken site: in the browser that fails, `document.createElement("canvas").getContext("webgl")`
  is `null`, while a fresh browser opens the page.
- **Analytic grid mapping.** The EASE-Grid 2.0 row of a latitude comes from the authalic q(φ) with the
  grid constants in `app.js` (`EASE`). `loadCatalog` checks every catalogue row centre lands in its own
  row and warns otherwise; `tests/smoke.py` fails on a mismatch.
- **Raster tile zoom is rounded**, so the data source stops at `maxzoom` 7 and MapLibre overzooms with
  `raster-resampling: nearest` above zoom 2.5 to keep cell edges crisp.
- **`decodePNG8` checks the image size** (964 × 406), not 256 × 256 as in Prithvi-ET; the canvas path is
  only a fallback for browsers without `DecompressionStream`.
- **The pmtiles JS reader refuses zooms outside the header's min/max**, which the Python writer derives
  from the entries. Daily/monthly/climatology archives therefore have min = max = 9 and the series
  archives 10; every lookup must use exactly those zooms.
- **Series parts are chosen by row** (`CAT.series.parts[].rows`); rows 0–1 and 371–405 have no land cell
  and no archive, so `seriesArchive()` returns null there instead of fetching.
- **The input[type=date] fires `change`, not `input`**, in most browsers when typed; a day without a file
  falls through to the next day with one and the layer card says so.

## Not done yet

- Regional means (click a country or basin for its series without reading cells).
- Teff, TBv and TBh as map layers (they are in the files, not in the browse archives).
- Korean UI text, a dark theme, a favicon.
