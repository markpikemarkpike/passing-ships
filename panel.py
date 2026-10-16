"""Render -> panel: quantize once ourselves, then hand the driver colours it
already knows so it never dithers over the top of our picture a second time.
T is the softness dial: lower = richer/muted (more of our dither shows),
1.0 = pure primaries. The setting approved on the real panel: 0.84."""
import os, sys
import numpy as np, cv2
from quantize import PALETTE, quantize

PURE = {"black": (0,0,0), "white": (255,255,255), "red": (255,0,0),
        "yellow": (255,255,0), "green": (0,255,0), "blue": (0,0,255)}
T = float(os.environ.get("PANEL_T", "0.84"))

def to_wall(src, dst):
    im = cv2.cvtColor(cv2.imread(src), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    q = quantize(im)
    keys = list(PALETTE)
    pal = np.array([PALETTE[k] for k in keys], np.float32)
    idx = ((q[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)
    mut = np.array([PALETTE[k] for k in keys], np.float32) * 255
    pure = np.array([PURE[k] for k in keys], np.float32)
    out = (mut * (1 - T) + pure * T).astype(np.uint8)[idx]
    cv2.imwrite(dst, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    return dst

def show(path):
    """Drive the Waveshare 7.3in E6, and PROVE it drove.

    History (Jul 30): the curator's in-process refresh after a heavy render
    silently no-op'd for two hours while the log said "hung"; a phone photo
    caught it. So: drive the panel in a FRESH subprocess (clean GPIO/memory,
    via the standalone ~/show.py that we know works), time it (a real
    Spectra-6 full refresh is ~20-25 s; under 8 s is the classic "instant
    SHOWN" = the panel never drove), retry once, and report the truth.
    Returns (ok, seconds, note). Off the Pi (no ~/show.py): (False, 0, "no-panel")."""
    import subprocess, time
    shower = os.path.expanduser("~/show.py")
    if not os.path.exists(shower):
        return False, 0.0, "no-panel"
    for attempt in (1, 2):
        t0 = time.time()
        try:
            r = subprocess.Popen([sys.executable, shower, path], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        except Exception as e:                       # launch failure
            return False, time.time() - t0, "show.py error: %s" % e
        try:
            r.stderr = r.communicate(timeout=240)[1]
        except subprocess.TimeoutExpired:
            r.terminate()                            # lets show.py put the panel to sleep...
            try:
                r.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                r.kill(); r.communicate()            # ...but not for ever
            return False, time.time() - t0, "show.py error: hung for 240 s (panel BUSY stuck?)"
        took = time.time() - t0
        if r.returncode != 0:
            return False, took, "show.py exit %d: %s" % (r.returncode, (r.stderr or "")[-200:])
        if took >= 8.0:
            return True, took, "drove in %.0fs%s" % (took, " (retry)" if attempt == 2 else "")
        # too fast = did not actually refresh; wait for the panel and try once more
        time.sleep(4)
    return False, took, "DISPLAY-DID-NOT-DRIVE (%.1fs, twice)" % took
