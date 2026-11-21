# HDCA Data Portal

Web portal for the lab's HDCA product: daily soil moisture (SM), vegetation optical depth (VOD) and
effective scattering albedo (ω̄) retrieved from SMAP L-band brightness temperatures on the 36 km
EASE-Grid 2.0 global grid, 1 April 2015 – 31 December 2025 (Lee et al., *Remote Sensing of Environment*
349, 115787, doi:10.1016/j.rse.2026.115787; the issue is dated January 2027, online since 2026-11-18).
**The data are public on Zenodo since 2026-11-20**: doi:10.5281/zenodo.24359287, CC BY 4.0, eleven files
`HDCA_YYYY.nc` (one calendar year each, 322–383 MB, 4.0 GB in all) with SM, VOD, OMEGA, TBv, TBh, Teff on a
complete daily `time` axis (days since 2015-04-01, NaN where nothing was retrieved) — not the daily files and
merged file of the lab storage. `js/config.js` carries the record (`zenodo`: DOI, page, files with sizes and
MD5 sums); the Download tab lists the files with direct links, the code examples read them, and the About tab
cites both the paper and the data record (updated 2026-11-22 at the PI's word, "연구실 사이트 업데이트 해
제노도 링크랑 같이"). The lab-storage tables (`#dlLab`) show only with `?nas=` or an `ncBase`. It shows daily, monthly and climatological maps on a
globe and the full 11-year record of any cell for all three variables.

**Status (2026-11-15): public on GitHub Pages** at https://hyunglok-kim.github.io/hdca-data-portal/
(the PI's decision the same day: "공개해") **and embedded on hydroai.net/data#hdca** the way Hampyeong is.
The lab dashboard embeds the public page (`hdca.html`) and still serves a local copy at `/rd/hdca/` for lab
members as a fallback. Paper and data are published (above); nothing is left to deposit.

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
the live text plus the entrance and nothing else, and that is what was pasted that evening. **Before the next
paste, copy the editor's text out and compare it with this file; if they differ, somebody has edited the page
since — merge, never overwrite.** After pasting, check every card on the live page.

**The hub cards (since 2026-11-17).** The lab head asked for cards that say more and for
nicer, moving pictures. Each dataset card now opens with a short silent loop, then its key facts (grid or
resolution, record, coverage, paper status) and what the portal offers. The loops and their first-frame
stills are in `embed/media/`, served from this repository's Pages site; `embed/tools/README.md` says how each
is made, which rules it keeps (only what is published; the other product behind the ET globe named on the
picture; the basemap credited on the picture) and how a loop's caption times belong to it. **The facts on a
card repeat its portal's own numbers** — when a portal's record, counts or paper status change, change its
card. A card's pictures play only while it is on screen, stop when a dataset is opened, and stay still for
visitors who asked for reduced motion. Pasted and published from the Prithvi-ET portal session at the lab
head's word; editor text, live page and the file compared equal, then the hub and every panel checked on
the live page in three browser engines.

The same day the page changed twice more. The SMAP time-variant error portal's session added a fourth card
and panel (`#tca`; its pictures are in that portal's repository), and with it the hub's columns: four across
from 1700 px, two by two from 1181 px, one column of horizontal cards down to 761 px, stacked cards below.
Then the lab head asked for the ET card's loop to open on the globe with ET over all land and to go into
the Pyeongchang sample area: `et-v2`, with the background product named in its first caption and in its
credit line (`embed/tools/README.md`). A re-made loop gets a new file name, so that a cached copy of the
old picture never plays under new captions; the old files are removed once the new text is live.

Later that day the lab head asked for the HDCA card to turn, come down on the Amazon with soil moisture
showing, and make much of that region's time series: `hdca-v2` — the globe turn, the zoom into the Amazon
basin, then the basin's soil moisture month by month with a chart over it drawing the box's monthly area mean
(`embed/tools/README.md`; the box 74–50°W, 13°S–3°N and its means from the portal's own fields,
`amazon_series.py` → `amazon_sm.json`). Applied in the Designer by exact replacements through `view.dispatch`
(the editor's sha1 compared with this file first), published, written back here, and the live page checked
line for line against this file. The first loop's files (`hdca.*`) were removed afterwards. Then the lab head found
the opening turn too slow (`hdca-v3`: turn and zoom 1.7 s each, the Amazon stage from 3.3 s) and had the credit
lines ("Imagery © Esri…", the ET card's background line) taken off every card; the attribution stays in the
portals' own maps and in `embed/tools/README.md`.

**A fifth card, 2026-11-18.** The Korea inland water quality portal's session added the card and panel `#wq`
(its loop and the tools that make it are in that portal's repository, `korea-water-quality-portal: embed/`),
at the lab head's word. With five cards the hub's columns changed: three across from 1700 to 1999 px (three
and two), five across from 2000 px (all five in one row on the lab head's 2048 px display, each 382 px wide);
below 1700 px nothing changed (two across, then one column of horizontal cards, then stacked). Six exact
replacements through `view.dispatch` after the editor's text matched this file (29,626 chars, sha1 404c7920);
the editor after saving, the live page and this file are equal: 33,673 chars, sha1
`911d4393a1a8a7da5ebc13bfd967f34680c5ff6e`. `check_captions.py` and `check_playback.py` pass on the live page
with all five cards. No other card's words, captions or pictures were touched.

**The ET card names France, 2026-11-21.** The lab head put the France maps on the server and asked for the
site to show them; the Prithvi-ET session made France the portal's second region and changed its card here:
the loop is `et-v3` (globe, France, across to the Korean Peninsula, Pyeongchang at 30 m; `embed/tools/cap_et_v3.py`)
with seven captions, and four sentences name France beside the peninsula ("The Korean Peninsula and France
are open now", "160 monthly maps per region", "Korean Peninsula and France now", "down to about 120 m").
Ten exact replacements inside the ET card through `view.dispatch` after the editor's text matched this file
(33,673 chars, sha1 911d4393); the editor after saving, the live page and this file are equal: 33,831 chars,
sha1 `a61a64eaa949339440216b41acaa377070d0b8a1`, published 02:59:07 UTC. `check_captions.py` and
`check_playback.py` pass on the live page, and every card opens its portal. `et-v2.*` stays in `embed/media/`
because the home page's reel played it; ask the home-page session before removing a loop from that folder.
Two things learned that day about the Designer, from the sessions working on the site: it opens on the page
last used (Home), not on the page you want; and while a page is open it may re-measure that page's own
pictures and save new `sizes` attributes, which go out with the next publish by anyone. So keep a copy of
every page you had open from before, and compare the pictures' `sizes` after the publish, not only the
embed's text. (On /data both pictures kept theirs.)

**The ET card counts 19 sample areas, 2026-11-21 evening.** The lab head approved 30 m sample areas for
France (the paper's eleven French flux-tower sites, as for the Korean eight); the portal got them first, and
the card's Status line followed: "at 30 m in eight sample areas" became "at 30 m in 19 sample areas". One
replacement through `view.dispatch` after the editor's text matched this file (33,831 chars, sha1 a61a64ea);
the editor after saving, the live page and this file are equal: 33,828 chars, sha1
`27180c0905e86d1560ba8a41ea54eb1dd40a065c`, published 09:06:39 UTC. The loop and its captions are unchanged
(`et-v3` shows no area marks, and its 30 m part is still Pyeongchang). A copy of all 43 pages from right
before the click, compared with one from after it (`site_snapshot.py` of the water-quality portal's
repository), shows that one place on /data and no picture's `sizes` changed. `check_captions.py` and
`check_playback.py` pass on the live page and all five cards open their portals.

**Home's pictures changed with the next publish; the cause is not established.** For this edit the Designer
was opened by the site's plain address and landed on Home for some 35 seconds before the Data page was chosen;
nothing was touched there. Home went out unchanged with this publish (09:06:39 UTC). With the next one, by the
projects session at 09:29:53 UTC, three of Home's pictures had other `sizes`: `main_ML-min.png` "31px",
`main_LSM-min.png` "(max-width: 479px) 45vw, 108px", `satellite.png` "(max-width: 479px) 60vw, 144px". The
layout held (the home-page session had given those pictures explicit widths that morning) but the browser
then drew two of them from the 500 px file at 462 and 635 px wide. This was first reported as the doing of
the landing on Home. The home-page session's record of the day's publishes does not bear that out: four
publishes that followed a visit to Home (two by this session, at 02:59:07 and 09:06:39, two by the home-page
session) left the values alone, and the two that changed them (01:41:15 and 09:29:53) both followed Designer
work on the project pages. What sets it off is not known. **Still: open the Designer by the target page's own
address** (`…design.webflow.com/?pageId=` + the `data-wf-page` value in that page's live `<html>` tag) and
stay off pages that are not yours; compare the whole site before and after a publish; look at Home again
after the next publish by anybody; and do not name a cause before the whole day's record has been read. The
repair of Home (a few lines in its first block that tell each picture the width it is drawn at) is the
home-page session's.

Two things learned in the Designer that day. The editor's text can be read and patched without the clipboard,
which may hold something of the lab head's: with the editor open, `c = document.querySelector('.cm-content')`,
`t = c.cmTile || c.cmView`, `view = t.view || t.root.view`; `view.state.doc.toString()` reads the text,
`view.dispatch({changes: [{from, to, insert}]})` patches it, and "Save & Close" stores it (reopen the editor
and hash the text to confirm). And single-key shortcuts fire if you type before the page switcher's search
box has focus ("A" opens the Add panel) — look before typing. The Designer's toolbar is not where it was
last time either: the lab head resizes that Chrome window, so take a screenshot before the first click.

The retrieval code (`Time_Varing_1Order_Scattering_code`) and the manuscript repository stay private; the
portal does not link them (PI decision 2026-11-15). The pipeline here only builds browse data from the product.

Both items once left for the PI are done (2026-11-22): the NetCDF files are on Zenodo (the `zenodo` block of
`js/config.js`; `ncBase` stays empty because the release is per year, not the lab's daily/merged layout), and the
published reference is in the use-strip, the Download tab, the About tab and `gateway/research_datasets.json`.
If the files are ever re-deposited (a new Zenodo version), update the record, the file list and the MD5 sums in
`js/config.js` — the Download tab and the code examples read nothing else.

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
