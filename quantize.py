"""Spectra 6 preview: error-diffuse a render to the panel's six inks.

The Waveshare/Pimoroni driver does its own conversion, but previewing our own
serpentine Floyd-Steinberg pass shows us NOW what the fog gradients will do on
a six-colour panel, before the hardware arrives. Palette values are the muted
inks the panel actually shows, not the driver's pure primaries.
"""
import sys
import numpy as np
import cv2

# panel-realistic Spectra 6 inks (linear-ish sRGB, 0..1)
PALETTE = {
    "black":  (0.11, 0.11, 0.12),
    "white":  (0.90, 0.89, 0.87),
    "red":    (0.66, 0.18, 0.16),
    "yellow": (0.86, 0.76, 0.22),
    "green":  (0.28, 0.50, 0.34),
    "blue":   (0.25, 0.34, 0.60),
}
PAL = np.array(list(PALETTE.values()), np.float32)


def prep(img):
    """Commit the picture to inks before dithering: crisp type, clean whites,
    sparse stipple. (Standard practice for 6-colour e-ink.)"""
    x = img.astype(np.float32).copy()
    # gentle contrast S-curve so tones commit toward an ink
    x = np.clip(0.5 + (x - 0.5) * 1.18, 0, 1)
    lum = x @ np.array([0.30, 0.59, 0.11], np.float32)
    mx, mn = x.max(axis=2), x.min(axis=2)
    chroma = mx - mn
    # type, arrow, hull ink (NEUTRAL darks) -> solid black; chromatic darks
    # like the deep indigo sea are left to dither blue-and-black instead
    black = (lum < 0.30) & (chroma < 0.13)
    x[black] = PALETTE["black"]
    # foggy near-whites with little colour -> panel white (kills tint speckle)
    white = (mn > 0.78) & (chroma < 0.10)
    x[white] = PALETTE["white"]
    return x


def quantize(img, atkinson=True):
    """Dither to the 6-ink palette. Atkinson (default) drops 1/4 of the error,
    which keeps foggy highlights clean; falls back to serpentine Floyd-Steinberg."""
    h, w, _ = img.shape
    work = prep(img)
    out = np.zeros_like(work)
    for y in range(h):
        for x in range(w):
            old = work[y, x]
            i = int(np.argmin(((PAL - old) ** 2).sum(axis=1)))
            new = PAL[i]
            out[y, x] = new
            err = old - new
            if atkinson:
                e = err / 8.0
                for dx, dy in ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
                    yy, xx = y + dy, x + dx
                    if yy < h and 0 <= xx < w:
                        work[yy, xx] += e
            else:
                if x + 1 < w:
                    work[y, x + 1] += err * (7 / 16)
                if y + 1 < h:
                    if x - 1 >= 0:
                        work[y + 1, x - 1] += err * (3 / 16)
                    work[y + 1, x] += err * (5 / 16)
                    if x + 1 < w:
                        work[y + 1, x + 1] += err * (1 / 16)
    return np.clip(out, 0, 1)


def main(src, dst):
    bgr = cv2.imread(src).astype(np.float32) / 255.0
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    q = quantize(rgb)
    cv2.imwrite(dst, cv2.cvtColor((q * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print(dst)


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        main(sys.argv[1], sys.argv[2])
    else:
        for name in ("fleet_container_fog", "fleet_sailing_fog"):
            main("renders/%s.png" % name, "renders/%s_spectra6.png" % name)
