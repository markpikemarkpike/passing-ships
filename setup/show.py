#!/usr/bin/env python3
"""Drive the 7.3" Spectra 6 panel with an already-quantized PNG.

Called by panel.py in a fresh subprocess and TIMED: a real refresh takes ~24 s;
returning instantly means the panel did not drive (see panel.py).

Checked against the frame's live copy Oct 14 2026: same library calls, same
rotation, plus the finally below.
"""
import signal, sys, os
for lib in ("~/epaper", "~/epaper/RaspberryPi_JetsonNano/python/lib"):    # our installer's layout, or a full vendor clone
    if os.path.isdir(os.path.expanduser(lib + "/waveshare_epd")):
        sys.path.insert(0, os.path.expanduser(lib))
from PIL import Image
from waveshare_epd import epd7in3e

path = sys.argv[1]
# The PhotoPainter frame holds its panel upside down relative to the driver.
ROTATE = {"0": None, "180": Image.ROTATE_180}.get(os.environ.get("PANEL_ROTATE", "180"), Image.ROTATE_180)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))    # asked to stop: still run the finally below
epd = epd7in3e.EPD()
try:
    epd.init()
    img = Image.open(path).convert("RGB")
    if ROTATE is not None:
        img = img.transpose(ROTATE)
    if img.size != (epd.width, epd.height):
        img = img.resize((epd.width, epd.height))
    epd.display(epd.getbuffer(img))
finally:
    # Try not to leave the panel's high-voltage rail up: the vendor warns that a
    # panel left powered is damaged over time. (Nothing can run after a SIGKILL,
    # which is why panel.py asks politely first.)
    try:
        epd.sleep()
    except Exception:
        pass                      # the first error is the one worth reporting
print("SHOWN", epd.width, epd.height)
