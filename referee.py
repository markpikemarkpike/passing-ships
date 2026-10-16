"""Countable referees for a ship print. Adjectives argue; these return
numbers a review has to cite.

Each referee takes the screen render (H,W,3 uint8) and, where relevant, the
panel-model render (what the six inks will actually show), plus the ship's
bounding box. All are deterministic and cheap so the grade sheet can run
across the whole fleet."""
import numpy as np, cv2

W, H = 800, 480
HORIZON = 250


def _lum(img):
    return 0.2126 * img[..., 2] + 0.7152 * img[..., 1] + 0.0722 * img[..., 0]  # BGR


def value_plan(img, ship_box):
    """Three squint zones: sky, sea, ship. Returns their mean luminance and the
    two gaps that make a value plan read (ship vs sky, ship vs sea). A ship
    within ~18 of its background = it will melt into it."""
    lum = _lum(img.astype(np.float32))
    x0, y0, x1, y1 = ship_box
    sky = lum[10:HORIZON - 20, :].mean()
    sea = lum[HORIZON + 40:H - 10, :].mean()
    ship = lum[y0:y1, x0:x1].mean()
    return dict(sky=float(sky), sea=float(sea), ship=float(ship),
                gap_ship_sky=float(abs(ship - sky)), gap_ship_sea=float(abs(ship - sea)))


def edge_ratio(img, ship_box):
    """Found-vs-lost edge balance inside the ship: share of pixels with a hard
    gradient. Timbre wants BOTH crisp and soft; ~0.06-0.16 is the healthy
    band. Near 0 = mush (all lost), high = etched cartoon (all found)."""
    x0, y0, x1, y1 = ship_box
    g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return float((mag > 60).mean())


def ink_coverage(panel_img):
    """On the six-ink panel, what fraction is committed ink vs bare white.
    A ship print with <8% dark ink usually means the vessel washed out."""
    lum = _lum(panel_img.astype(np.float32))
    dark = (lum < 90).mean()
    mid = ((lum >= 90) & (lum < 190)).mean()
    white = (lum >= 190).mean()
    return dict(dark=float(dark), mid=float(mid), white=float(white))


def panel_survival(screen_img, panel_img, ship_box):
    """The Luminosa/car-carrier test: how much of the SHIP's visible form on
    screen still contrasts with its surroundings on the panel. We measure the
    ship-vs-background luminance gap on both; if the panel gap collapses, the
    vessel is depending on mid-tones the six inks cannot show."""
    x0, y0, x1, y1 = ship_box
    def gap(img):
        lum = _lum(img.astype(np.float32))
        inside = lum[y0:y1, x0:x1].mean()
        ring = np.concatenate([lum[max(0, y0 - 30):y0, x0:x1].ravel(),
                               lum[y1:min(H, y1 + 30), x0:x1].ravel()])
        return abs(inside - ring.mean())
    gs, gp = gap(screen_img), gap(panel_img)
    return dict(screen_gap=float(gs), panel_gap=float(gp),
                survival=float(gp / gs) if gs > 1e-3 else 0.0)


def whites_reserved(img, ship_box):
    """Foam-line integrity: is there a near-white found edge where the hull
    meets the water (the seat), rather than the ship floating on nothing."""
    x0, y0, x1, y1 = ship_box
    wl = HORIZON + 34                         # true layout waterline (scene.y)
    band = img[wl - 6:wl + 14, x0:x1]
    lum = _lum(band.astype(np.float32))
    return float((lum > 215).mean())


def flatness(img, ship_box):
    """The MS-Paint index: share of the ship's pixels sitting in a perfectly
    uniform 5x5 neighbourhood (zero local variance). Watercolour is never
    locally flat -- pigment pools, edges darken, paper shows. A wash-painted
    ship reads ~0.05-0.15; a gouache-block cartoon reads 0.35+."""
    x0, y0, x1, y1 = ship_box
    g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.blur(g, (5, 5))
    sq = cv2.blur(g * g, (5, 5))
    var = np.clip(sq - mean * mean, 0, None)
    return float((var < 4.0).mean())


def ship_box_from(img):
    """Estimate the ship's bounding box: darkest coherent mass near the
    horizon band, from the screen render. Falls back to the layout box."""
    lum = _lum(img.astype(np.float32))
    band = lum[HORIZON - 90:HORIZON + 90, :]
    mask = (band < 150).astype(np.uint8)
    ys, xs = np.where(mask)
    if len(xs) < 200:
        return (200, HORIZON - 60, 600, HORIZON + 40)
    x0, x1 = int(np.percentile(xs, 2)), int(np.percentile(xs, 98))
    y0 = int(np.percentile(ys, 2)) + HORIZON - 90
    y1 = int(np.percentile(ys, 98)) + HORIZON - 90
    return (x0, y0, x1, y1)


def measure(screen_path, panel_path):
    scr = cv2.imread(screen_path)
    pan = cv2.imread(panel_path)
    box = ship_box_from(scr)
    return dict(box=box, value=value_plan(scr, box), edge_ratio=edge_ratio(scr, box),
                ink=ink_coverage(pan), survival=panel_survival(scr, pan, box),
                flatness=flatness(scr, box),
                seat_white=whites_reserved(scr, box))
