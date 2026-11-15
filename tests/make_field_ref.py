#!/usr/bin/env python3
"""Write tests/field_ref.json: checksums of a few fields read straight from the archives.

Run where the archives are (the CPU server's venv has pmtiles, numpy and Pillow):

    venv/bin/python make_field_ref.py /data/personal_data/project_hdca_portal/out > field_ref.json

tests/smoke.py --ref compares what the browser decodes against these numbers, cell for cell.
Keys are "VAR|mode|when" as the portal's layer keys; the archive entry follows from them.
"""
import io
import json
import sys

import numpy as np
from PIL import Image
from pmtiles.reader import MmapSource, Reader

FIELDS = [("SM|all|", "clim/HDCA_SM_clim.pmtiles", 0),
          ("SM|day|2020-10-28", "daily/HDCA_SM_2020.pmtiles", 302),
          ("OMEGA|month|2018-07", "monthly/HDCA_OMEGA_monthly.pmtiles", (2018 - 2015) * 12 + 6),
          ("VOD|clim|1", "clim/HDCA_VOD_clim.pmtiles", 1)]

root, out = sys.argv[1].rstrip("/"), {}
for key, name, x in FIELDS:
    with open(f"{root}/{name}", "rb") as f:
        data = Reader(MmapSource(f)).get(9, x, 0)
    a = np.array(Image.open(io.BytesIO(data)))
    assert a.shape == (406, 964), a.shape
    out[key] = {"sum": int(a.astype(np.int64).sum()), "n255": int((a == 255).sum()),
                "px": [int(a[248, 296]), int(a[67, 284]), int(a[201, 540]), int(a[82, 823])]}   # Tambopata, Millbrook, Congo, Korea
print(json.dumps(out, indent=1))
