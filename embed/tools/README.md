# The Data page's hub cards: pictures and how they are made

`../hydroai-data-page.html` is the text of the one HTML Embed that makes up hydroai.net/data. Its hub has
one card per dataset, and each card opens with a short silent loop from `../media/` (`<name>.webm`,
`<name>.mp4`, and `<name>.jpg`, the first frame, shown before the loop plays and to visitors who asked for
reduced motion). The words on a picture are in the card's `data-caps` attribute, as `[seconds, text]`
pairs; when a loop is re-made, its caption times must be re-made with it.

All three are 768 × 432 and about twelve seconds. They are made from what the portals themselves publish,
one settled frame at a time, with software drawing (no graphics card needed).

| Card | What it shows | Made by |
|---|---|---|
| `cvs` | The Hampyeong 1 km cell in the drone's true colour, ten flights from bare fields to harvest (2026), the 47 ground stations marked | `make_cvs.py`, from the Hampyeong portal's `data/uav/` layers and `data/stations.csv` |
| `et-v2` | The globe with ET over all land, then down to the Korean Peninsula and into one 30 m sample area (Pyeongchang), mean annual ET | `cap_et.py`, from a local preview of the Prithvi-ET portal on its **public** copy of the tiles |
| `hdca-v2` | The globe turning with the record-mean soil moisture, then into the Amazon basin, whose soil moisture plays month by month (April 2015 to December 2025) while a chart draws the basin's monthly area mean over it | `amazon_series.py` (the area means), `cap_hdca_amazon.py` (raw frames, from a local preview of this portal), then `compose_hdca_amazon.py` (box, chart, dissolve) |
| `hdca` (first version, retired) | The globe turning once: soil moisture, then vegetation optical depth, then the effective scattering albedo (record means) | `cap_hdca.py` then `blend_hdca.py` |

```bash
# Python with playwright (chromium installed), numpy, Pillow; ffmpeg with libx264 and libvpx-vp9.
# cvs — 15 frames a second: ten flights, each held 10 frames and cross-faded over 8
CVS_FPS=15 CVS_HOLD=10 CVS_FADE=8 python make_cvs.py ~/orca/projects/hampyeong-cal-val frames/cvs
./encode.sh frames/cvs cvs ../media 29 42 768 15

# et — the Prithvi-ET preview must serve the public copy of the tiles (see that repository's notes)
python cap_et.py "http://127.0.0.1:8791/?data=/data/prithvi-openet-tiles-1/&intro=0" frames/et
./encode.sh frames/et et-v2 ../media 31 44 768 24

# hdca-v2 — this portal's preview (dev_server.py --port 8792); needs the pmtiles package besides the above
python amazon_series.py ../../data amazon_sm.json          # area means of the Amazon box from the portal's own fields (kept here)
python cap_hdca_amazon.py "http://127.0.0.1:8792/?intro=0&data=/data/" frames/hdca/raw      # add 'test' for a handful of frames
python compose_hdca_amazon.py frames/hdca/raw amazon_sm.json frames/hdca/final
./encode.sh frames/hdca/final hdca-v2 ../media 30 44 768 24    # the maps change every frame, so CRF a step higher: 0.8 MB mp4, 1.1 MB webm
# the first HDCA loop, retired: cap_hdca.py BASE frames/hdca0; blend_hdca.py frames/hdca0 frames/hdca0/final; encode.sh … hdca …
```

`encode.sh FRAMES NAME OUT CRF_H264 CRF_VP9 WIDTH FPS` writes the three files. The sizes to expect are
0.4 to 0.7 MB a loop; a loop of detailed imagery that also drifts or zooms the whole time grows past 1 MB,
which is why the drone picture stands still and only the seasons and the station rings move.

Rules these pictures keep, and a re-made one must keep too:

- **Only what is published.** The ET loop is drawn from the public copy of the tiles (120 m, and 30 m inside
  the sample areas), never from the lab's full set, and it goes to 30 m only inside a sample area.
- **The background on the ET globe is named on the picture.** The lab head asked (2026-11-17) for the loop
  to open on the globe with ET over all land, as the portal itself does, and for the 30 m part to be
  Pyeongchang. Outside the Korean Peninsula those colours are the portal's background layer, another product
  (MOD16A2GF), so the card says so for as long as it shows: its first caption ("Global background: MODIS ET
  (MOD16A2GF)", also the words on the still picture) and its credit line ("Background ET: MOD16A2GF
  (NASA)"). Keep both when the captions are re-timed or the card is re-worded. The first version of the loop
  (`et.*`, the morning of the same day) had switched the background off instead.
- **A re-made loop gets a new file name** (`et-v2`), so that a cached copy of the old picture never plays
  under the new captions. The old files go once the new text is live.
- **The basemap is credited.** The ET and HDCA loops show Esri World Imagery; their cards carry
  "Imagery © Esri, Maxar, Earthstar Geographics" on the picture.
- **Clean flights only.** `make_cvs.py` lists ten flights; several others have colour artefacts over the
  forest and one is a false-colour composite.
- **The Amazon on the HDCA card is an area mean the viewer can check.** The box is 74–50°W, 13°S–3°N (3,747 cells of
  36 km with data); its monthly and daily means come from the portal's own published fields (`amazon_series.py`), and
  the dashed line is the box's record mean. The lab head asked (2026-11-17) for the HDCA card to turn, come down on
  the Amazon with soil moisture showing, and make much of that region's time series.
- **The numbers on the cards are the portals' own** (the Hampyeong About tab's station and sensor counts,
  each portal's header facts, the papers' status). When a portal's numbers change, change its card.

## After a loop is re-made or a card is changed: run both checks before publishing and again on the live page

```bash
python check_captions.py                      # the live page; or give the address of a local copy
python check_playback.py                      # the same; a second argument picks firefox or webkit
```

A caption is one line in a chip no wider than the picture minus 24 px, and anything longer is cut off with
an ellipsis; on a phone the picture is about 320 to 350 px wide, so about 47 characters is the limit. The
script puts every `data-caps` text of every card into its chip at eight window widths (2048 px down to a
360 px phone) and says which are cut off, and whether each credit line stays inside its picture. It found
the first Amazon caption cut off at 390 px on the day it was written (2026-11-17).

`check_playback.py` looks at the behaviour: every loop plays; every caption in a card's `data-caps` is shown
at some point of its loop (one timed past the loop's end never is); opening a dataset hides the hub and stops
the loops, and coming back starts them again; the page throws no script error; and with reduced motion no
video is fetched and each still picture carries its card's first caption. A loop plays only while its card is
on screen, so the test window is 2048 px wide, where all cards are in one row: widen it if the hub grows.
Console errors are listed but not counted, because a portal opened by the test may log its own (the
Hampyeong portal asks for station photos that do not exist).
