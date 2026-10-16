"""Compose a watercolor ship print (800x480) from an AIS-style record."""
import re
import numpy as np
import config
from PIL import Image, ImageDraw, ImageFont
from watercolor import Canvas, PAPER_RGB

W, H = 800, 480
HORIZON = 262

# masstones (watercolor palette)
INDIGO   = (0.16, 0.22, 0.38)
PAYNE    = (0.28, 0.34, 0.44)
TEAL     = (0.30, 0.52, 0.55)
SKYBLUE  = (0.62, 0.72, 0.82)
FOGGREY  = (0.78, 0.80, 0.80)
SUNWARM  = (0.94, 0.86, 0.70)
VERMIL   = (0.80, 0.28, 0.18)
OCHRE    = (0.82, 0.62, 0.32)
SUMI     = (0.13, 0.12, 0.14)
HULLDARK = (0.20, 0.23, 0.30)


def _font(size, bold=False, cjk=False):
    cands = ["/System/Library/Fonts/Hiragino Sans GB.ttc"] if cjk else [
        "/System/Library/Fonts/Supplemental/Georgia%s.ttf" % (" Bold" if bold else ""),
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_mask(text, size, xy, anchor="la", bold=False, tracking=0):
    im = Image.new("F", (W, H), 0.0)
    d = ImageDraw.Draw(im)
    f = _font(size, bold)
    if tracking:
        x, y = xy
        for ch in text:
            d.text((x, y), ch, font=f, fill=1.0, anchor="la")
            x += d.textlength(ch, font=f) + tracking
    else:
        d.text(xy, text, font=f, fill=1.0, anchor=anchor)
    return np.asarray(im, dtype=np.float32)


def ship_px(length_m):
    """Nonlinear scale: 20m boat reads, 366m ship dominates."""
    L = min(max(length_m, 12), 400)
    return 90 + 500 * (L / 400) ** 0.7


def paint_sky(cv, seed, fog=0.35):
    """fog in [0,1]: 0 = clear blue, 1 = socked-in Sea Ranch grey."""
    blue = 0.34 * (1 - fog * 0.8)
    cv.graded_pour(0, HORIZON + 8, [
        (0.00, SUNWARM, 0.16 * (1 - fog * 0.6)),
        (0.35, SKYBLUE, blue),
        (0.70, FOGGREY, 0.20 + 0.30 * fog),
        (1.00, FOGGREY, 0.08 + 0.38 * fog),
    ], drag=0.35, seed=seed)
    # a loose cloud shoulder, negative-painted with a second sky glaze
    r = np.random.default_rng(seed + 2)
    cy = r.uniform(60, 120)
    cloud = [(60, cy + 30), (200, cy - 18), (380, cy + 4), (560, cy - 26),
             (740, cy + 22), (740, cy + 64), (60, cy + 70)]
    cv.wash(cloud, SKYBLUE, density=0.16, jitter=9, feather=9,
            edge_dark=0.25, variegation=0.6, seed=seed + 3)


def paint_sea(cv, seed, wake_poly=None, wave=0.5, wind=0.4):
    """wave in [0,1] scales swell height/frequency; wind adds whitecaps."""
    if wake_poly is not None:
        cv.add_reserve(wake_poly, feather=3)
    cv.wash([(0, HORIZON), (W, HORIZON), (W, H), (0, H)], TEAL,
            density=0.34, jitter=2, feather=2.5, edge_dark=0.35,
            granulation=0.45, variegation=0.5, seed=seed + 10)
    # swell bands: irregular spacing, some skipped, alternating pigment
    r = np.random.default_rng(seed + 11)
    y, i = HORIZON + 12, 0
    caps = []
    while y < H:
        depth = (y - HORIZON) / (H - HORIZON)
        y += r.uniform(22, 46) * (1.25 - 0.5 * wave)
        i += 1
        if r.random() < 0.28 * (1.2 - wave):
            continue
        amp = (2.5 + 8 * depth) * (0.5 + 1.3 * wave)
        xs = np.linspace(-20, W + 20, 24)
        ys_top = y + np.sin(xs / r.uniform(55, 130) + r.uniform(0, 6)) * amp
        thick = r.uniform(8, 20) + 26 * depth
        band = list(zip(xs, ys_top)) + [(W + 20, y + thick), (-20, y + thick)]
        pig = INDIGO if r.random() < 0.65 else TEAL
        cv.wash(band, pig, density=r.uniform(0.06, 0.14) + 0.15 * depth,
                jitter=2.5, feather=r.uniform(1.5, 3.0), edge_dark=0.9,
                granulation=0.3, variegation=0.45, seed=seed + 20 + i)
        if r.random() < wind and depth > 0.12:
            j = int(r.integers(2, 24))
            caps.append((xs[j % 24], float(np.min(ys_top)) + 1, depth))
    # sparkle spatter in the foreground
    cv.spatter((0, H - 90, W, H - 8), INDIGO, n=48, density=0.35, seed=seed + 40)
    cv.clear_reserves()
    # whitecaps: small opaque foam dashes riding the band crests
    for k, (cx_, cy_, depth) in enumerate(caps):
        wlen = 14 + 26 * depth
        fleck = [(cx_ - wlen / 2, cy_), (cx_ + wlen / 2, cy_ - 1),
                 (cx_ + wlen * 0.30, cy_ + 2.5 + 2 * depth),
                 (cx_ - wlen * 0.34, cy_ + 2 + 2 * depth)]
        cv.gouache(fleck, (0.95, 0.95, 0.93), alpha=0.75, jitter=1.5,
                   feather=1.0, seed=seed + 60 + k)


def paint_container_ship(cv, cx, y, L, seed):
    """Side profile facing left. cx: center x, y: waterline, L: pixel length."""
    Hh = L * 0.085                       # hull height above water
    x0, x1 = cx - L / 2, cx + L / 2
    bow = [(x0, y - Hh), (x0 + L * 0.055, y - Hh * 0.2), (x0 + L * 0.075, y + 2)]
    hull = [(x0, y - Hh)] + bow[1:] + [(x1 - L * 0.02, y + 2), (x1, y - Hh * 0.55),
                                        (x1 - L * 0.01, y - Hh)]
    cv.wash(hull, HULLDARK, density=0.95, jitter=2, feather=1.6,
            edge_dark=0.5, granulation=0.25, variegation=0.3, seed=seed)
    # waterline stripe
    cv.wash([(x0 + L * 0.06, y - 3), (x1, y - 3), (x1, y + 2), (x0 + L * 0.075, y + 2)],
            VERMIL, density=0.5, jitter=1.5, feather=1.0, seed=seed + 1)
    # container stacks: gouache cells in a muted triad, ending before the castle
    r = np.random.default_rng(seed + 2)
    cols = [VERMIL, TEAL, OCHRE, PAYNE, VERMIL, TEAL]
    n_bays = max(6, int(L / 46))
    bay_w = (L * 0.66) / n_bays
    bx0 = x0 + L * 0.10
    for b in range(n_bays):
        stack_h = r.integers(2, 5)
        for s in range(stack_h):
            c = cols[int(r.integers(0, len(cols)))]
            top = y - Hh - (s + 1) * Hh * 0.42
            cell = [(bx0 + b * bay_w + 1, top),
                    (bx0 + (b + 1) * bay_w - 1, top),
                    (bx0 + (b + 1) * bay_w - 1, top + Hh * 0.40),
                    (bx0 + b * bay_w + 1, top + Hh * 0.40)]
            tint = np.clip(np.array(c) + r.uniform(-0.05, 0.05, 3), 0, 1)
            cv.gouache(cell, tint * 0.9 + np.array(PAPER_RGB) * 0.1,
                       alpha=0.75, jitter=1.2, feather=0.8, seed=seed + 50 + b * 7 + s)
    # superstructure aft (white castle), wider and shorter than v1
    sw = L * 0.135
    sx = x1 - L * 0.185
    st = y - Hh - Hh * 1.75
    castle = [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)]
    cv.gouache(castle, (0.94, 0.93, 0.91), alpha=0.92, jitter=1.2, feather=0.8, seed=seed + 3)
    cv.wash([(sx, st + Hh * 0.5), (sx + sw, st + Hh * 0.5),
             (sx + sw, y - Hh), (sx, y - Hh)], PAYNE, density=0.16,
            jitter=1.5, feather=1.2, seed=seed + 4)
    # bridge wings, window strip, castle outline
    cv.line([(sx - 5, st + 3), (sx + sw + 5, st + 3)], SUMI, width=2, density=0.7, seed=seed + 5)
    cv.line([(sx + 3, st + Hh * 0.28), (sx + sw - 3, st + Hh * 0.28)], SUMI,
            width=1, density=0.5, seed=seed + 15)
    cv.line(castle + [castle[0]], SUMI, width=1, density=0.4, seed=seed + 16)
    # funnel: short, behind the bridge, dark cap
    fw = sw * 0.34
    fx = sx + sw * 0.55
    fun = [(fx, st), (fx + fw * 0.15, st - Hh * 0.45),
           (fx + fw * 0.85, st - Hh * 0.45), (fx + fw, st)]
    cv.wash(fun, VERMIL, density=0.6, jitter=1, feather=0.9, seed=seed + 6)
    cv.line([(fx + fw * 0.15, st - Hh * 0.42), (fx + fw * 0.85, st - Hh * 0.42)],
            SUMI, width=2, density=0.6, seed=seed + 17)
    # ink accents: sheer line + bow
    cv.line([(x0, y - Hh), (x1 - L * 0.01, y - Hh)], SUMI, width=2, density=0.55, seed=seed + 7)
    cv.line(bow, SUMI, width=2, density=0.6, seed=seed + 8)
    # mast
    cv.line([(x0 + L * 0.07, y - Hh), (x0 + L * 0.07, y - Hh * 2.6)], SUMI,
            width=1, density=0.5, seed=seed + 9)


def paint_fishing_boat(cv, cx, y, L, seed):
    Hh = L * 0.14
    x0, x1 = cx - L / 2, cx + L / 2
    hull = [(x0, y - Hh), (x0 + L * 0.12, y + 2), (x1 - L * 0.06, y + 2),
            (x1, y - Hh * 0.8), (x1 - L * 0.05, y - Hh * 1.05)]
    cv.wash(hull, (0.75, 0.73, 0.68), density=0.75, jitter=2, feather=1.4,
            edge_dark=0.6, seed=seed)
    cv.wash([(x0 + L * 0.05, y - 2), (x1 - L * 0.03, y - 2),
             (x1 - L * 0.05, y + 2), (x0 + L * 0.11, y + 2)], VERMIL,
            density=0.45, jitter=1, feather=0.8, seed=seed + 1)
    cabin = [(x0 + L * 0.16, y - Hh), (x0 + L * 0.16, y - Hh * 2.0),
             (x0 + L * 0.44, y - Hh * 2.0), (x0 + L * 0.44, y - Hh)]
    cv.gouache(cabin, (0.92, 0.91, 0.88), alpha=0.9, jitter=1, feather=0.8, seed=seed + 2)
    cv.wash([(cabin[1][0], cabin[1][1]), (cabin[2][0], cabin[2][1]),
             (cabin[2][0], cabin[2][1] + Hh * 0.4), (cabin[1][0], cabin[1][1] + Hh * 0.4)],
            TEAL, density=0.45, jitter=1, feather=0.9, seed=seed + 3)
    cv.line(cabin + [cabin[0]], SUMI, width=1, density=0.5, jitter=0.8, seed=seed + 8)
    # boom + rigging
    cv.line([(x0 + L * 0.5, y - Hh), (x0 + L * 0.5, y - Hh * 3.2)], SUMI, 2, 0.7, seed=seed + 4)
    cv.line([(x0 + L * 0.5, y - Hh * 3.0), (x1 + L * 0.08, y - Hh * 1.3)], SUMI, 1, 0.6, seed=seed + 5)
    cv.line([(x0 + L * 0.5, y - Hh * 3.0), (x0 - L * 0.02, y - Hh * 1.2)], SUMI, 1, 0.6, seed=seed + 6)
    cv.line([(x0, y - Hh), (x1 - L * 0.05, y - Hh * 1.02)], SUMI, 2, 0.55, seed=seed + 7)


def paint_sailboat(cv, cx, y, L, seed):
    Hh = L * 0.10
    x0, x1 = cx - L / 2, cx + L / 2
    hull = [(x0, y - Hh), (x0 + L * 0.1, y + 1), (x1 - L * 0.12, y + 1), (x1, y - Hh)]
    cv.wash(hull, HULLDARK, density=0.8, jitter=1.5, feather=1.2, edge_dark=0.6, seed=seed)
    mx = cx - L * 0.05
    mt = y - Hh - L * 0.78
    cv.line([(mx, y - Hh), (mx, mt)], SUMI, 2, 0.7, seed=seed + 1)
    main = [(mx + 2, mt + 4), (mx + 2, y - Hh - 2), (mx + L * 0.42, y - Hh - 2)]
    jib = [(mx - 3, mt + L * 0.10), (mx - 3, y - Hh - 2), (mx - L * 0.40, y - Hh - 2)]
    # white sails must be MADE white: gouache body, shading glaze, ink outline
    cv.gouache(main, (0.97, 0.96, 0.93), alpha=0.95, jitter=1.2, feather=0.9, seed=seed + 2)
    cv.gouache(jib, (0.97, 0.96, 0.93), alpha=0.95, jitter=1.2, feather=0.9, seed=seed + 3)
    # leeward shading on the jib + a soft belly shadow on the main
    cv.wash(jib, PAYNE, density=0.18, jitter=1.5, feather=2.0, edge_dark=0.4, seed=seed + 4)
    belly = [(mx + 2, y - Hh - L * 0.30), (mx + L * 0.30, y - Hh - 2), (mx + 2, y - Hh - 2)]
    cv.wash(belly, FOGGREY, density=0.22, jitter=2, feather=2.5, seed=seed + 5)
    for sail, s in ((main, 6), (jib, 7)):
        cv.line(sail + [sail[0]], SUMI, width=1, density=0.55, jitter=0.8, seed=seed + s)


PAINTERS = {"container": paint_container_ship, "cargo": paint_container_ship,
            "tanker": paint_container_ship, "fishing": paint_fishing_boat,
            "sailing": paint_sailboat}


PREFIX = {"fishing": "F/V", "sailing": "S/V", "research": "R/V",
          "cutter": "USCGC", "military": "USS", "naval": "USS", "tug": "TUG",
          "motoryacht": "M/Y", "atb": "ATB"}
# prefixes ships put in their own AIS name; she knows better than her type code
_OWN_PREFIX = re.compile(r"(USCGC|USCG|CGC|CG|USS|USNS|WARSHIP|[RMFSTP]/[VTY]|[RM]\.V\.|TUG|ATB"
                         r"|[RMFS]V) +(?=\S)")


def full_name(ship):
    """'M/V COSCO PACIFIC'. A name that already carries its own prefix keeps it
    (USNS MERCY is not 'USS USNS MERCY'). The Coast Guard's short forms are spelled
    out. The bare two-letter forms are also ordinary words and initials, so MV, RV,
    FV and SV count only on the kind of ship that would get that prefix anyway;
    MY and MT never do (F/V MY GIRL, M/V MT EVEREST)."""
    name, mine = ship["name"].upper(), PREFIX.get(ship["type"], "M/V")
    m = _OWN_PREFIX.match(name)
    own, rest = (m.group(1), name[m.end():]) if m else (None, name)
    if own in ("CG", "CGC", "USCG") or (own and len(own) == 2):
        return "%s %s" % (mine, rest if mine in ("USCGC", own[0] + "/" + own[1]) else name)
    return name if own else "%s %s" % (mine, name)


def paint_caption(cv, ship):
    meta = "%s · %d m · for %s · %.1f kn" % (
        ship["type"].capitalize(), ship["length_m"], ship["dest"], ship["speed_kn"])
    place = "PASSING %s · %s" % (config.PLACE, ship["date"])
    m = text_mask(full_name(ship), 30, (36, H - 74), bold=True, tracking=1)
    cv.mask_wash(m, SUMI, density=0.85)
    m = text_mask(meta, 17, (36, H - 40))
    cv.mask_wash(m, SUMI, density=0.6)
    m = text_mask(place, 12, (W - 36, 24), anchor="ra")
    cv.mask_wash(m, SUMI, density=0.5)
    # red seal: 波 (wave), knocked out to paper
    sx, sy, s = W - 70, H - 80, 44
    seal = [(sx, sy), (sx + s, sy), (sx + s, sy + s), (sx, sy + s)]
    cv.wash(seal, VERMIL, density=0.9, jitter=2.5, feather=1.2,
            granulation=0.5, seed=99)
    im = Image.new("F", (W, H), 0.0)
    d = ImageDraw.Draw(im)
    d.text((sx + s / 2, sy + s / 2 + 1), "波", font=_font(30, cjk=True),
           fill=1.0, anchor="mm")
    knock = np.asarray(im, np.float32)
    cv.img = cv.img * (1 - knock[..., None]) + \
        (cv.img + (np.array(PAPER_RGB) - cv.img) * 0.92) * knock[..., None]


def render(ship, path, seed=None):
    seed = seed if seed is not None else (hash(ship["name"]) & 0xFFFF)
    cv = Canvas(W, H, seed=seed)
    paint_sky(cv, seed)
    L = ship_px(ship["length_m"])
    cx = W * 0.44
    y = HORIZON + 26 + (12 if ship["length_m"] < 60 else 0)
    # foam reserve: bare paper along the waterline + wake trailing astern (right)
    foam = [(cx - L * 0.54, y - 1), (cx + L * 0.52, y - 1),
            (cx + L * 0.80, y + 6), (cx + L * 0.60, y + 11),
            (cx - L * 0.56, y + 5)]
    paint_sea(cv, seed, wake_poly=foam)
    PAINTERS.get(ship["type"], paint_container_ship)(cv, cx, y, L, seed + 100)
    # hull shadow just below the foam line
    cv.wash([(cx - L / 2, y + 6), (cx + L / 2, y + 6),
             (cx + L / 2, y + 12), (cx - L / 2, y + 12)],
            INDIGO, density=0.30, jitter=2, feather=2.5, seed=seed + 200)
    paint_caption(cv, ship)
    return cv.save(path)


if __name__ == "__main__":
    import sys
    ships = [
        dict(name="Cosco Pacific", type="container", length_m=366,
             dest="Oakland", speed_kn=16.2, date="22 JULY 2026"),
        dict(name="Sea Dancer II", type="fishing", length_m=22,
             dest="Bodega Bay", speed_kn=8.4, date="22 JULY 2026"),
        dict(name="Wild Rose", type="sailing", length_m=14,
             dest="Fort Bragg", speed_kn=6.1, date="22 JULY 2026"),
    ]
    which = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for i, s in enumerate(ships):
        if which is not None and i != which:
            continue
        out = "renders/%02d_%s.png" % (i, s["name"].lower().replace(" ", "_"))
        print(render(s, out))
