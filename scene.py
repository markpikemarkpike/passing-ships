"""The A2 painting, rebuilt as a real watercolour: value plan, light, atmosphere.

Value ladder (fog day): luminous sky glowing brightest just above the horizon,
horizon melting into mist, sea grading from mist-light in the distance to the
darkest, most saturated pigment in the foreground. The ship sits at the light
band so its dark hull silhouettes; it is faded toward the fog colour with
distance (aerial perspective), lit on its top planes, and seated in the water
by a bow wave, a bare-paper foam line, and a broken reflection astern.
"""
import numpy as np
import cv2
import config
from watercolor import PAPER_RGB

S = 1.0                      # render scale: 3.0 paints a 2400x1440 master
W, H = 800, 480
HORIZON = 250


def set_scale(s=1.0):
    """Repaint the world larger: layout, atmosphere and stroke scale together."""
    global S, W, H, HORIZON
    S = float(s)
    W, H = int(round(800 * S)), int(round(480 * S))
    HORIZON = int(round(250 * S))

# masstones
INDIGO   = (0.13, 0.19, 0.36)
PAYNE    = (0.26, 0.32, 0.42)
TEAL     = (0.28, 0.50, 0.53)
SKYBLUE  = (0.60, 0.71, 0.83)
FOGGREY  = (0.79, 0.81, 0.82)
SUNWARM  = (0.945, 0.90, 0.80)   # cream, not yellow: must land on panel white
VERMIL   = (0.78, 0.30, 0.20)
OCHRE    = (0.83, 0.66, 0.36)
SUMI     = (0.13, 0.12, 0.14)
HULLDARK = (0.16, 0.19, 0.27)
RUST     = (0.66, 0.30, 0.22)


def mix(a, b, t):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    return tuple(a * (1 - t) + b * t)


def fade(rgb, fog):
    """Aerial perspective: distance lifts and cools pigment toward the mist.
    The ship is close (a few hundred metres), so it fades only gently."""
    return mix(rgb, FOGGREY, np.clip(fog * 0.30, 0, 0.35))


def gauss_mask(cx, cy, sx, sy):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2)).astype(np.float32)


# ------------------------------------------------------------------ sky

def paint_sky(cv, seed, fog=0.4, sun_x=None, sun_y=None, light=None, flip=False):
    """Sky glows brightest just above the horizon; the hour picks the palette
    (light dict from light.py): cool rose alpenglow at dawn (sun is behind the
    ridge), a peach/copper glow with the disc going into the sea at sunset."""
    hz_glow = SUNWARM
    top_base = SKYBLUE
    glow_str = 0.16
    sun_h = None
    if light:
        hz_glow = light.get("horizon", SUNWARM)
        top_base = light.get("sky_top", SKYBLUE)
        glow_str = light.get("glow_strength", 0.16)
        sun_h = light.get("sun_h")                    # None = below the horizon
    if sun_x is None:
        sun_x = 560 * S
    if sun_y is None:
        sun_y = HORIZON - 70 * S if sun_h is None else HORIZON - (18 + 240 * sun_h) * S
        if sun_h is not None:
            sun_x = 668 * S                            # low sun sits out over open water
    if flip:                                           # the sheet is mirrored at the end:
        sun_x = W - sun_x                              # paint the sun where it will land right
    top_dens = 0.30 + 0.30 * fog          # heavier grey overhead in fog
    top_pig = mix(top_base, FOGGREY, fog)
    cv.graded_pour(0, HORIZON, [
        (0.00, top_pig, top_dens),
        (0.45, mix(top_base, FOGGREY, min(1.0, fog + 0.2)), top_dens * 0.55),
        (0.80, mix(FOGGREY, hz_glow, 0.35), 0.10 + 0.12 * fog),
        (1.00, hz_glow, 0.06 + 0.5 * glow_str * (1 - fog * 0.6)),
    ], drag=0.30, seed=seed)
    # the glow: a soft oval at the sun (or a broad low band when the sun is
    # behind us / below the horizon), heart lifted toward bare paper
    if sun_h is None:
        glow = gauss_mask(sun_x, HORIZON - 12 * S, 300 * S, 44 * S)
        cv.mask_wash(glow, hz_glow, density=glow_str)
        cv.lift_mask(gauss_mask(sun_x, HORIZON - 10 * S, 260 * S, 20 * S), amount=0.30 - 0.1 * fog)
    else:
        glow = gauss_mask(sun_x, sun_y, 210 * S, 62 * S)
        cv.mask_wash(glow, hz_glow, density=glow_str)
        cv.lift_mask(gauss_mask(sun_x, sun_y, 78 * S, 30 * S), amount=0.62 - 0.15 * fog)
        if sun_h < 0.08:                                          # the disc, low and warm
            cv.lift_mask(gauss_mask(sun_x, sun_y, 26 * S, 14 * S), amount=0.75 - 0.3 * fog)


# ------------------------------------------------------------------ sea

def paint_sea(cv, seed, fog=0.4, wave=0.5, wind=0.4, light=None, flip=False):
    """Mist-light at the horizon, darkest and richest in the foreground. At the
    warm hours the far water takes the sky's colour and a glitter path of
    lifted flakes runs down from a low western sun."""
    far = FOGGREY
    glitter = 0.0
    if light:
        far = mix(FOGGREY, light.get("horizon", FOGGREY), 0.32)
        glitter = light.get("glitter", 0.0) * (1 - fog * 0.6)
    cv.graded_pour(HORIZON, H, [
        (0.00, far, 0.10 + 0.10 * fog),
        (0.15, mix(TEAL, far, 0.55), 0.15),
        (0.55, TEAL, 0.28),
        (1.00, mix(INDIGO, TEAL, 0.4), 0.36 + 0.10 * wave),
    ], drag=0.45, seed=seed + 10)
    if glitter > 0.02:                          # sun path: broken flakes of light
        rg = np.random.default_rng(seed + 900)
        sx = W - 668 * S if flip else 668 * S            # under the western sun
        for k in range(int(110 * glitter) + 16):
            d = rg.uniform(0.02, 1.0) ** 1.3            # denser near the horizon
            yy = HORIZON + d * (H - HORIZON) * 0.95
            spread = (10 + 220 * d) * S
            xx = sx + rg.normal(0, spread * 0.32)
            wlen = (3 + 26 * d) * S * rg.uniform(0.5, 1.3)
            m = np.zeros((H, W), np.float32)
            cv2.line(m, (int(xx - wlen), int(yy)), (int(xx + wlen), int(yy)), 1.0,
                     max(1, int((1 + 2 * d) * S)), cv2.LINE_AA)
            m = cv2.GaussianBlur(m, (0, 0), 0.9 * S)
            cv.lift_mask(m, amount=(0.35 + 0.5 * (1 - d)) * min(1.0, glitter * 2.4))
    # swell bands: sparse near the horizon, heavier and looser toward us
    r = np.random.default_rng(seed + 11)
    y, i = HORIZON + 18 * S, 0
    caps = []
    while y < H:
        depth = (y - HORIZON) / (H - HORIZON)
        y += r.uniform(20, 44) * (1.3 - 0.55 * wave) * S
        i += 1
        if r.random() < 0.32 * (1.3 - wave) or depth < 0.05:
            continue
        amp = (2 + 8 * depth) * (0.55 + 1.2 * wave) * S
        xs = np.linspace(-20 * S, W + 20 * S, 22)
        ys_top = y + np.sin(xs / (r.uniform(60, 140) * S) + r.uniform(0, 6)) * amp
        thick = (r.uniform(6, 16) + 30 * depth) * S
        band = list(zip(xs, ys_top)) + [(W + 20 * S, y + thick), (-20 * S, y + thick)]
        pig = INDIGO if r.random() < 0.6 else PAYNE
        cv.wash(band, pig, density=(0.05 + 0.20 * depth) * (0.7 + 0.5 * wave),
                jitter=2.5, feather=1.4 + 2.5 * depth, edge_dark=0.8,
                granulation=0.25 + 0.4 * depth, variegation=0.5,
                seed=seed + 20 + i)
        if r.random() < wind and 0.1 < depth < 0.92:
            j = int(r.integers(2, 22))
            caps.append((xs[j % 22], float(np.min(ys_top)), depth))
    # a fresh breeze earns its whitecaps: top up to what the wind promises
    want = int(round(1 + 7 * wind))
    while len(caps) < want:
        d = float(r.uniform(0.15, 0.85))
        caps.append((float(r.uniform(0, W)), HORIZON + d * (H - HORIZON), d))
    # light streaks skating across the middle water
    for k in range(4):
        yy = r.uniform(HORIZON + 40 * S, H - 60 * S)
        d = (yy - HORIZON) / (H - HORIZON)
        m = np.zeros((H, W), np.float32)
        x0 = r.uniform(-40 * S, W * 0.5)
        cv2.line(m, (int(x0), int(yy)),
                 (int(x0 + r.uniform(160, 340) * S), int(yy + r.uniform(-3, 3) * S)),
                 1.0, max(1, int((2 + 3 * d) * S)), cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 1.2 * S) * cv._dry_keep(0.42)
        cv.lift_mask(m, amount=0.28 + 0.2 * d)
    # a restrained flick of foreground sparkle
    cv.spatter((0, H - 90 * S, W, H - 6 * S), INDIGO, n=18, density=0.3, seed=seed + 40)
    cv.clear_reserves()
    # whitecaps: crisp, dry-brushed, brightest riding the crests
    for k, (cx_, cy_, depth) in enumerate(caps):
        wlen = (12 + 30 * depth) * S
        fleck = [(cx_ - wlen / 2, cy_ + 1 * S), (cx_ + wlen / 2, cy_ - 1 * S),
                 (cx_ + wlen * 0.32, cy_ + (3 + 2 * depth) * S),
                 (cx_ - wlen * 0.36, cy_ + (2.5 + 2 * depth) * S)]
        cv.gouache(fleck, (0.965, 0.96, 0.95), alpha=0.92, jitter=1.4,
                   feather=0.7, dry=0.38, seed=seed + 60 + k)


# ------------------------------------------------------------------ ship

def paint_container_ship(cv, cx, y, L, seed, fog=0.4, livery=None, length_m=None):
    """Side profile facing left, lit on top planes, faded by mist. The owner's
    livery colours hull / boxes / castle / funnel (liveries.py)."""
    lv = livery or {}
    Hh = L * 0.085
    x0, x1 = cx - L / 2, cx + L / 2
    hull_col = fade(lv.get("hull") or HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)                      # ink softens in fog
    hull = [(x0, y - Hh), (x0 + L * 0.05, y - Hh * 0.15), (x0 + L * 0.075, y + 1),
            (x1 - L * 0.02, y + 1), (x1, y - Hh * 0.5), (x1 - L * 0.008, y - Hh)]
    # hull mass: found (crisp) top edge, lost lower edge into the water
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.3, variegation=0.35, seed=seed)
    # light raking the upper strake + a rusty boot-topping at the waterline
    strake = [(x0 + L * 0.02, y - Hh + 3), (x1 - L * 0.015, y - Hh + 3),
              (x1 - L * 0.02, y - Hh + Hh * 0.42), (x0 + L * 0.04, y - Hh + Hh * 0.42)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.50)
    cv.wash([(x0 + L * 0.06, y - 4), (x1 - L * 0.005, y - 4),
             (x1 - L * 0.01, y + 1), (x0 + L * 0.075, y + 1)],
            fade(lv.get("boot") or RUST, fog), density=0.5, jitter=1.4, feather=0.9, seed=seed + 1)
    # containers: the OPERATOR's own boxes dominate the stack, mixed with the
    # generic slot-charter colours (a ONE ship is loaded with pink ONE boxes)
    r = np.random.default_rng(seed + 2)
    generic = [VERMIL, TEAL, OCHRE, PAYNE, RUST, PAYNE, TEAL, PAYNE]
    own = lv.get("boxes")
    cols = (list(own) * 3 + generic) if own else generic
    # ULCVs (Emma Maersk onward) are TWIN ISLAND: the bridge block stands a
    # third back from the bow, the funnel is its own island aft, and the boxes
    # run in two stacks -- bow to bridge, then bridge to funnel. Smaller ships
    # keep the single castle aft.
    twin = bool(length_m) and length_m >= 290
    sx = x1 - L * 0.18                                # aft island (castle / funnel)
    bay_w0 = (L * 0.64) / max(6, int(L / 44))
    if twin:
        bwb = L * 0.09
        bxb = x0 + L * 0.29                           # bridge island position
        # (x_start, x_end, taper_start, taper_end): stacks stay full height up
        # against the islands and only step down at the bow.
        regions = [(x0 + L * 0.05, bxb - L * 0.010, True, False),   # bow -> bridge
                   (bxb + bwb + L * 0.010, sx - L * 0.012, False, True)]  # bridge -> funnel
    else:
        regions = [(x0 + L * 0.11, x0 + L * 0.11 + L * 0.64, True, True)]
    top_line = y - Hh
    h_ = int(r.integers(4, 6))
    gi = 0                                            # global bay counter for seeds
    hi_min = y - Hh                                   # highest box top (for the bridge)
    for ra, rb, tap_a, tap_b in regions:
        n_bays = max(2, int(round((rb - ra) / bay_w0)))
        bay_w = (rb - ra) / n_bays
        heights = []
        for b in range(n_bays):             # step every bay so the skyline stays busy
            h_ = int(np.clip(h_ + r.integers(-1, 2), 3, 5))
            t = (b + 0.5) / n_bays          # 0 at region start, 1 at region end
            prof = 1.0
            if tap_a: prof = min(prof, 0.62 + 0.38 * np.sin(np.pi * t / 2.0) ** 0.6)
            if tap_b: prof = min(prof, 0.62 + 0.38 * np.sin(np.pi * (1 - t) / 2.0) ** 0.6)
            heights.append(max(2, int(round(h_ * prof))))
        for b in range(n_bays):
            for s in range(heights[b]):
                c = fade(cols[int(r.integers(0, len(cols)))], fog)
                c = mix(c, PAPER_RGB, 0.06)          # keep pale boxes solid, no holes
                top = top_line - (s + 1) * Hh * 0.36
                crisp = r.random() < 0.6               # lost & found edges
                cell = [(ra + b * bay_w + 1.0, top),
                        (ra + (b + 1) * bay_w - 1.0, top),
                        (ra + (b + 1) * bay_w - 1.0, top + Hh * 0.38),
                        (ra + b * bay_w + 1.0, top + Hh * 0.38)]
                cv.gouache(cell, c, alpha=0.9, jitter=0.7 if crisp else 1.6,
                           feather=0.45 if crisp else 1.1, seed=seed + 50 + gi * 7 + s)
                if s == heights[b] - 1:                # sky light on the top box
                    hi_min = min(hi_min, top)
                    lit = [(cell[0][0], top), (cell[1][0], top),
                           (cell[1][0], top + Hh * 0.11), (cell[0][0], top + Hh * 0.11)]
                    cv.lift_mask(cv2.GaussianBlur(_polymask(lit), (0, 0), 0.8 * S), 0.42)
            gi += 1
    if twin:
        # forward bridge island: tall white block, wraparound window strip, mast.
        bt = max(min(y - Hh - Hh * 1.7, hi_min - Hh * 0.45), y - Hh * 4.6)   # a deck above the boxes, capped
        blk = [(bxb, y - Hh), (bxb, bt), (bxb + bwb, bt), (bxb + bwb, y - Hh)]
        cv.gouache(blk, mix(lv.get("house") or (0.95, 0.94, 0.92), FOGGREY, fog * 0.4),
                   alpha=0.95, jitter=1.0, feather=0.7, seed=seed + 30)
        cv.wash([(bxb + bwb * 0.62, bt), (bxb + bwb, bt), (bxb + bwb, y - Hh),
                 (bxb + bwb * 0.62, y - Hh)], fade(PAYNE, fog * 0.5), density=0.35,
                jitter=1.2, feather=1.4, seed=seed + 31)                 # shaded flank
        cv.line([(bxb, y - Hh), (bxb, bt), (bxb + bwb, bt)], ink, width=1,
                density=inkd * 0.85, seed=seed + 32)                        # found edges
        cv.line([(bxb + 2, bt + Hh * 0.32), (bxb + bwb - 2, bt + Hh * 0.32)],
                ink, width=1, density=inkd * 0.8, seed=seed + 33)            # bridge windows
        cv.line([(bxb + bwb * 0.5, bt), (bxb + bwb * 0.5, bt - Hh * 0.55)],
                ink, width=1, density=inkd * 0.7, seed=seed + 34)            # mast
    # aft castle: white body, cool shaded flank, bridge window strip
    sw = L * 0.13
    st = y - Hh - Hh * (1.35 if twin else 1.8)        # funnel island sits lower than the bridge
    castle = [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)]
    cv.gouache(castle, mix(lv.get("house") or (0.95, 0.94, 0.92), FOGGREY, fog * 0.4),
               alpha=0.95, jitter=1.0, feather=0.7, seed=seed + 3)
    cv.wash([(sx + sw * 0.45, st), (sx + sw, st), (sx + sw, y - Hh),
             (sx + sw * 0.45, y - Hh)], fade(PAYNE, fog * 0.5), density=0.55,
            jitter=1.2, feather=1.4, seed=seed + 4)                # deeper cool flank
    # found edges on the tower: top and fore edge inked against the sky
    cv.line([(sx, y - Hh), (sx, st), (sx + sw, st)], ink, width=1,
            density=inkd * 0.85, seed=seed + 40)
    cv.line([(sx + 3, st + Hh * 0.30), (sx + sw - 3, st + Hh * 0.30)],
            ink, width=1, density=inkd * 0.8, seed=seed + 15)
    cv.line([(sx - 4, st + 3), (sx + sw + 4, st + 3)], ink, width=2,
            density=inkd, seed=seed + 5)
    # funnel with a smudge of exhaust dissolving up-left (downwind)
    fw = sw * 0.36
    fx = sx + sw * 0.52
    fun = [(fx, st), (fx + fw * 0.15, st - Hh * 0.5),
           (fx + fw * 0.85, st - Hh * 0.5), (fx + fw, st)]
    cv.wash(fun, fade(lv.get("funnel") or VERMIL, fog), density=0.8, jitter=1,
            feather=0.8, seed=seed + 6)
    cv.line([(fx + fw * 0.12, st - Hh * 0.46), (fx + fw * 0.88, st - Hh * 0.46)],
            fade(lv.get("band"), fog) if lv.get("band") else ink, width=2,
            density=inkd if not lv.get("band") else 0.9, seed=seed + 17)
    smoke = [(fx, st - Hh * 0.55), (fx + fw, st - Hh * 0.6),
             (fx - fw * 3.5, st - Hh * 2.6), (fx - fw * 4.5, st - Hh * 1.9)]
    cv.wash(smoke, mix(PAYNE, FOGGREY, 0.5), density=0.12, jitter=8, feather=9,
            edge_dark=0.15, variegation=0.7, seed=seed + 18)
    # found edges: crisp sheer line and bow against the light water
    cv.line([(x0, y - Hh), (x1 - L * 0.008, y - Hh)], ink, width=2,
            density=inkd * 0.85, seed=seed + 7)
    cv.line([(x0, y - Hh), (x0 + L * 0.05, y - Hh * 0.15), (x0 + L * 0.075, y + 1)],
            ink, width=2, density=inkd, seed=seed + 8)
    cv.line([(x0 + L * 0.07, y - Hh), (x0 + L * 0.07, y - Hh * 2.5)], ink,
            width=1, density=inkd * 0.7, seed=seed + 9)
    return hull_col


def _polymask(poly):
    m = np.zeros((H, W), np.float32)
    cv2.fillPoly(m, [np.round(np.asarray(poly)).astype(np.int32)], 1.0)
    return m


def paint_tanker(cv, cx, y, L, seed, fog=0.4, livery=None):
    """Laden tanker: long low hull, flat rust-grey pipe deck, castle aft.
    Owner livery colours hull / house / funnel (liveries.py)."""
    lv = livery or {}
    Hh = L * 0.07                      # low freeboard, she's full
    x0, x1 = cx - L / 2, cx + L / 2
    hull_col = fade(lv.get("hull") or HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull = [(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1),
            (x1 - L * 0.015, y + 1), (x1, y - Hh * 0.45), (x1 - L * 0.006, y - Hh)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.3, variegation=0.35, seed=seed)
    strake = [(x0 + L * 0.02, y - Hh + 2), (x1 - L * 0.012, y - Hh + 2),
              (x1 - L * 0.015, y - Hh + Hh * 0.45), (x0 + L * 0.035, y - Hh + Hh * 0.45)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.45)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.004, y - 3),
             (x1 - L * 0.008, y + 1), (x0 + L * 0.06, y + 1)],
            fade(RUST, fog), density=0.55, jitter=1.4, feather=0.9, seed=seed + 1)
    # the deck: a long low pipe deck; raised catwalk on stanchions runs its
    # length, manifold humps of varying size, a piperack, midship mast
    dtop = y - Hh - Hh * 0.42
    deck = [(x0 + L * 0.09, y - Hh), (x0 + L * 0.09, dtop),
            (x1 - L * 0.22, dtop), (x1 - L * 0.22, y - Hh)]
    cv.wash(deck, fade(mix(RUST, PAYNE, 0.55), fog), density=0.8, jitter=1.2,
            feather=0.9, edge_dark=0.45, granulation=0.35, variegation=0.4, seed=seed + 2)
    r = np.random.default_rng(seed + 3)
    # catwalk: an elevated line on evenly-spaced legs (the tanker tell)
    cw_y = dtop - Hh * 0.45
    cx0, cx1 = x0 + L * 0.11, x1 - L * 0.24
    cv.line([(cx0, cw_y), (cx1, cw_y)], ink, width=1, density=inkd * 0.8, seed=seed + 20)
    xk = cx0
    while xk < cx1:
        cv.line([(xk, cw_y), (xk, dtop)], ink, width=1, density=inkd * 0.55,
                seed=seed + 200 + int(xk))
        xk += L * 0.045
    # manifold humps + a low piperack straddling the catwalk
    for k in range(5):
        mx = x0 + L * (0.16 + 0.115 * k) + r.uniform(-6, 6)
        wide = L * r.uniform(0.018, 0.032)
        tall = Hh * r.uniform(0.22, 0.42)
        hump = [(mx - wide, dtop + 2), (mx - wide * 0.7, dtop - tall),
                (mx + wide * 0.7, dtop - tall), (mx + wide, dtop + 2)]
        cv.wash(hump, fade(mix(PAYNE, RUST, 0.3), fog), density=0.85, jitter=1,
                feather=0.8, edge_dark=0.45, seed=seed + 30 + k)
    rack = [(x0 + L * 0.42, dtop - Hh * 0.20), (x0 + L * 0.62, dtop - Hh * 0.20),
            (x0 + L * 0.62, dtop + 2), (x0 + L * 0.42, dtop + 2)]
    cv.wash(rack, fade(mix(OCHRE, PAYNE, 0.5), fog), density=0.55, jitter=1.2,
            feather=1.0, edge_dark=0.35, granulation=0.3, seed=seed + 36)
    cv.line([(x0 + L * 0.50, dtop), (x0 + L * 0.50, dtop - Hh * 1.5)], ink,
            width=1, density=inkd * 0.7, seed=seed + 21)
    cv.line([(x0 + L * 0.46, dtop - Hh * 1.1), (x0 + L * 0.54, dtop - Hh * 1.1)],
            ink, width=1, density=inkd * 0.6, seed=seed + 22)
    # aft castle: a wide accommodation BLOCK (a building, not a tower), bridge
    # glass committed dark, funnel stepped aft off the block's centreline
    sw = L * 0.185
    sx = x1 - L * 0.245
    st = y - Hh - Hh * 1.75
    castle = [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)]
    cv.wash(castle, mix(lv.get("house") or (0.93, 0.92, 0.89), FOGGREY, fog * 0.4), density=0.75,
            jitter=1.1, feather=0.8, edge_dark=0.45, granulation=0.3, seed=seed + 4)
    cv.wash([(sx + sw * 0.55, st), (sx + sw, st), (sx + sw, y - Hh),
             (sx + sw * 0.55, y - Hh)], fade(PAYNE, fog), density=0.35,
            jitter=1.2, feather=1.4, seed=seed + 5)                # cool aft flank
    # bridge windows: a committed DARK strip -- the panel must read a building
    cv.wash([(sx + 3, st + Hh * 0.20), (sx + sw - 3, st + Hh * 0.20),
             (sx + sw - 3, st + Hh * 0.55), (sx + 3, st + Hh * 0.55)],
            fade(mix(INDIGO, SUMI, 0.45), fog * 0.7), density=0.95, jitter=0.8,
            feather=0.6, dry=0.10, seed=seed + 22)
    # a second, thinner deck-of-portholes line lower on the block
    cv.line([(sx + 4, st + Hh * 0.95), (sx + sw - 4, st + Hh * 0.95)], ink,
            width=1, density=inkd * 0.55, seed=seed + 26)
    cv.line([(sx - 2, st + 3), (sx + sw + 2, st + 3)], ink, width=2,
            density=inkd, seed=seed + 6)
    cv.line([(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)], ink,
            width=1, density=inkd * 0.7, seed=seed + 23)
    fw = sw * 0.30
    fx = sx + sw * 0.68                                   # aft of the block's centre
    fun = [(fx, st), (fx + fw * 0.15, st - Hh * 0.62),
           (fx + fw * 0.85, st - Hh * 0.62), (fx + fw, st)]
    cv.wash(fun, fade(lv.get("funnel") or VERMIL, fog), density=0.8, jitter=1,
            feather=0.8, edge_dark=0.4, seed=seed + 7)
    if lv.get("band"):                                          # owner's funnel band
        cv.line([(fx + fw * 0.10, st - Hh * 0.32), (fx + fw * 0.92, st - Hh * 0.32)],
                fade(lv["band"], fog), width=2, density=0.9, seed=seed + 27)
    cv.line([(fx + fw * 0.12, st - Hh * 0.62), (fx + fw * 0.88, st - Hh * 0.62)],
            ink, width=2, density=inkd, seed=seed + 24)             # black funnel cap band
    smoke = [(fx, st - Hh * 0.75), (fx + fw, st - Hh * 0.8),
             (fx - fw * 3.5, st - Hh * 3.2), (fx - fw * 4.5, st - Hh * 2.4)]
    cv.wash(smoke, mix(PAYNE, FOGGREY, 0.5), density=0.12, jitter=8, feather=9,
            edge_dark=0.15, variegation=0.7, seed=seed + 25)
    cv.line([(x0, y - Hh), (x1 - L * 0.006, y - Hh)], ink, width=2,
            density=inkd * 0.85, seed=seed + 8)
    cv.line([(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1)],
            ink, width=2, density=inkd, seed=seed + 9)
    return hull_col


def paint_fishing_boat(cv, cx, y, L, seed, fog=0.4):
    """Working crab boat: white hull, red bottom, cabin forward, outriggers."""
    Hh = L * 0.15
    x0, x1 = cx - L / 2, cx + L / 2
    lw = 2 if L > 240 else 1                             # line weight scales with hull
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    white = mix((0.95, 0.94, 0.91), FOGGREY, fog * 0.35)
    hull = [(x0, y - Hh), (x0 + L * 0.10, y + 2), (x1 - L * 0.06, y + 2),
            (x1, y - Hh * 0.75), (x1 - L * 0.04, y - Hh * 1.0)]
    cv.gouache(hull, white, alpha=0.95, jitter=1.4, feather=0.8, seed=seed)
    # red antifouling at the waterline, shadowed underside
    cv.wash([(x0 + L * 0.04, y - 3), (x1 - L * 0.03, y - 3),
             (x1 - L * 0.05, y + 2), (x0 + L * 0.09, y + 2)],
            fade(VERMIL, fog), density=0.7, jitter=1, feather=0.8, seed=seed + 1)
    cv.wash(hull, fade(PAYNE, fog), density=0.20, jitter=1.5, feather=1.4,
            seed=seed + 2)
    # cabin: white house forward with a dark window band
    cb = [(x0 + L * 0.14, y - Hh), (x0 + L * 0.14, y - Hh * 2.05),
          (x0 + L * 0.42, y - Hh * 2.05), (x0 + L * 0.42, y - Hh)]
    cv.gouache(cb, white, alpha=0.95, jitter=1.0, feather=0.7, seed=seed + 3)
    cv.wash([(cb[1][0] + 2, cb[1][1] + Hh * 0.22), (cb[2][0] - 2, cb[2][1] + Hh * 0.22),
             (cb[2][0] - 2, cb[2][1] + Hh * 0.48), (cb[1][0] + 2, cb[1][1] + Hh * 0.48)],
            fade(INDIGO, fog), density=0.45, jitter=1, feather=0.8, seed=seed + 4)
    cv.line(cb + [cb[0]], ink, width=1, density=inkd * 0.7, jitter=0.7, seed=seed + 5)
    # crab pot stack aft: the coast's signature, a warm crated block on deck
    px0, px1 = x0 + L * 0.56, x1 - L * 0.10
    ptop = y - Hh * 1.85                                  # pots stacked chest-high
    cv.wash([(px0, y - Hh), (px0, ptop), (px1, ptop), (px1, y - Hh)],
            fade(mix(OCHRE, RUST, 0.35), fog), density=0.8, jitter=1.0, feather=0.8,
            edge_dark=0.45, granulation=0.35, seed=seed + 20)
    r2 = np.random.default_rng(seed + 21)
    for k in range(3):                                   # crate lines within the stack
        yy = y - Hh - (ptop - (y - Hh)) * 0 - (k + 1) * Hh * 0.26
        cv.line([(px0 + 2, y - Hh - (k + 1) * (Hh * 1.05) / 4),
                 (px1 - 2, y - Hh - (k + 1) * (Hh * 1.05) / 4)],
                ink, width=1, density=inkd * 0.45, seed=seed + 30 + k)
    # net drum amidships + a red buoy on deck (the working accents)
    dx = x0 + L * 0.50
    cv.wash([(dx - L * 0.03, y - Hh), (dx - L * 0.03, y - Hh * 1.55),
             (dx + L * 0.03, y - Hh * 1.55), (dx + L * 0.03, y - Hh)],
            fade(mix(PAYNE, SUMI, 0.3), fog), density=0.75, jitter=0.9, feather=0.8,
            edge_dark=0.4, seed=seed + 24)
    cv.wash([(x0 + L * 0.44, y - Hh * 1.3), (x0 + L * 0.47, y - Hh * 1.3),
             (x0 + L * 0.47, y - Hh), (x0 + L * 0.44, y - Hh)],
            fade(VERMIL, fog * 0.6), density=0.9, jitter=0.7, feather=0.6, seed=seed + 25)
    # a rusty scum line along the white hull (working boats are not clean)
    cv.wash([(x0 + L * 0.06, y - Hh * 0.55), (x1 - L * 0.05, y - Hh * 0.55),
             (x1 - L * 0.06, y - Hh * 0.30), (x0 + L * 0.08, y - Hh * 0.30)],
            fade(RUST, fog), density=0.22, jitter=1.6, feather=1.6, dry=0.25, seed=seed + 26)
    # mast, boom, outriggers swung out for stability
    mx = x0 + L * 0.52
    cv.line([(mx, y - Hh), (mx, y - Hh * 3.3)], ink, width=lw, density=inkd, seed=seed + 6)
    cv.line([(mx, y - Hh * 3.1), (x1 + L * 0.10, y - Hh * 1.2)], ink, width=1,
            density=inkd * 0.85, seed=seed + 7)
    cv.line([(mx, y - Hh * 3.1), (x0 - L * 0.04, y - Hh * 1.1)], ink, width=1,
            density=inkd * 0.85, seed=seed + 8)
    cv.line([(x0, y - Hh), (x1 - L * 0.04, y - Hh * 1.0)], ink, width=lw,
            density=inkd * 0.7, seed=seed + 9)
    return mix(white, PAYNE, 0.5)


def paint_research_ship(cv, cx, y, L, seed, fog=0.4, livery=None):
    """Ocean research vessel (v1, Jul 30, from RV Sikuliaq): blue hull with a
    raked ice-strengthened bow, white superstructure massed FORWARD, a low
    open working deck aft, and the signature white A-frame gantry over the
    stern. Faces left. Value plan: the blue hull is the darkest mass; the
    superstructure is found by its cool shaded flank + inked edges, never by
    white-on-white; the A-frame is drawn as crisp white legs cutting the sky."""
    Hh = L * 0.13                                       # tall freeboard, ice bow
    x0, x1 = cx - L / 2, cx + L / 2
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    lv = livery or {}
    hc = lv.get("hull")
    blue = fade(hc if (hc and not _is_white(hc)) else (0.16, 0.32, 0.62), fog * 0.7)
    if hc and _is_white(hc):                            # NOAA white hulls: soft flank shade
        blue = fade(mix((0.76, 0.79, 0.85), PAYNE, 0.45), fog * 0.6)
    white = mix((0.965, 0.955, 0.93), FOGGREY, fog * 0.35)
    shade = mix((0.76, 0.80, 0.86), FOGGREY, fog * 0.4)  # cool flank, not grey
    # hull: raked bow (leans forward at the top), full length, cruiser stern
    hull = [(x0 - L * 0.03, y - Hh), (x0 + L * 0.03, y - Hh * 0.30), (x0 + L * 0.05, y + 1),
            (x1 - L * 0.02, y + 1), (x1, y - Hh * 0.55), (x1 - L * 0.01, y - Hh)]
    cv.wash(hull, blue, density=1.05, jitter=1.4, feather=1.0, edge_dark=0.55,
            granulation=0.3, variegation=0.3, seed=seed)
    # white sheer stripe just under the deck edge (research ships carry one)
    stripe = [(x0 + L * 0.01, y - Hh + 3), (x1 - L * 0.015, y - Hh + 3),
              (x1 - L * 0.018, y - Hh + 3 + Hh * 0.16), (x0 + L * 0.02, y - Hh + 3 + Hh * 0.16)]
    cv.gouache(stripe, white, alpha=0.9, jitter=0.8, feather=0.5, seed=seed + 1)
    # boot-topping shadow at the waterline (lost lower edge into the water)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.02, y - 3),
             (x1 - L * 0.025, y + 1), (x0 + L * 0.055, y + 1)],
            fade(PAYNE, fog), density=0.35, jitter=1.4, feather=1.4, seed=seed + 2)
    # ---- superstructure FORWARD: two decks stepping up to the bridge ----
    base = y - Hh
    sx0 = x0 + L * 0.10                                 # house starts abaft the bow
    sx1 = x0 + L * 0.55                                 # ends amidships; deck aft
    d1 = Hh * 1.10                                      # tall boxy research house
    house = [(sx0, base - d1), (sx1, base - d1), (sx1, base), (sx0, base)]
    cv.gouache(house, shade, alpha=0.94, jitter=0.9, feather=0.7, seed=seed + 3)
    lit = [(sx0, base - d1), (sx1, base - d1), (sx1, base - d1 * 0.62), (sx0, base - d1 * 0.62)]
    cv.gouache(lit, white, alpha=0.95, jitter=0.6, feather=0.5, seed=seed + 4)
    # bridge deck on top, set back, wraparound dark windows
    bx0, bx1 = sx0 + L * 0.05, sx1 - L * 0.10
    d2 = Hh * 0.70
    bridge = [(bx0, base - d1 - d2), (bx1, base - d1 - d2), (bx1, base - d1), (bx0, base - d1)]
    cv.gouache(bridge, shade, alpha=0.94, jitter=0.8, feather=0.6, seed=seed + 5)
    blit = [(bx0, base - d1 - d2), (bx1, base - d1 - d2),
            (bx1, base - d1 - d2 * 0.55), (bx0, base - d1 - d2 * 0.55)]
    cv.gouache(blit, white, alpha=0.95, jitter=0.6, feather=0.5, seed=seed + 6)
    cv.wash([(bx0 + 2, base - d1 - d2 * 0.85), (bx1 - 2, base - d1 - d2 * 0.85),
             (bx1 - 2, base - d1 - d2 * 0.55), (bx0 + 2, base - d1 - d2 * 0.55)],
            fade(INDIGO, fog), density=0.55, jitter=0.8, feather=0.6, seed=seed + 7)
    # window row on the main house
    wy = base - d1 * 0.32
    r = np.random.default_rng(seed + 8)
    xk = sx0 + L * 0.02
    while xk < sx1 - L * 0.03:
        seg = r.uniform(L * 0.012, L * 0.026)
        cv.line([(xk, wy), (min(xk + seg, sx1 - L * 0.03), wy)], ink, width=1,
                density=inkd * 0.6, seed=seed + 30 + int(xk))
        xk += seg + r.uniform(L * 0.006, L * 0.014)
    # inked found edges on the house so the whites don't melt into the sky
    cv.line([(sx0, base), (sx0, base - d1), (sx1, base - d1)], ink, width=1,
            density=inkd * 0.85, seed=seed + 9)
    cv.line([(bx0, base - d1), (bx0, base - d1 - d2), (bx1, base - d1 - d2), (bx1, base - d1)],
            ink, width=1, density=inkd * 0.85, seed=seed + 10)
    # twin thin uptakes just abaft the bridge (Sikuliaq's side stacks)
    for i, ux in enumerate((sx1 - L * 0.06, sx1 - L * 0.02)):
        uw = L * 0.014
        stack = [(ux, base - d1), (ux, base - d1 - d2 * 1.35),
                 (ux + uw, base - d1 - d2 * 1.35), (ux + uw, base - d1)]
        cv.gouache(stack, mix(white, shade, 0.5), alpha=0.95, jitter=0.5, feather=0.4,
                   seed=seed + 11 + i)
        cv.wash([(ux, base - d1 - d2 * 1.35), (ux + uw, base - d1 - d2 * 1.35),
                 (ux + uw, base - d1 - d2 * 1.35 + Hh * 0.14), (ux, base - d1 - d2 * 1.35 + Hh * 0.14)],
                fade(SUMI, fog), density=0.7, jitter=0.5, feather=0.4, seed=seed + 13 + i)
    # ---- open working deck aft: low bulwark line, a knuckle crane ----
    cv.line([(sx1, base), (x1 - L * 0.03, base)], ink, width=2,
            density=inkd * 0.8, seed=seed + 15)                # deck edge / bulwark
    cbx = sx1 + (x1 - sx1) * 0.45                        # crane pedestal
    cv.line([(cbx, base), (cbx, base - Hh * 0.9)], ink, width=2, density=inkd, seed=seed + 16)
    cv.line([(cbx, base - Hh * 0.85), (cbx - L * 0.10, base - Hh * 0.30)],
            ink, width=2, density=inkd * 0.9, seed=seed + 17)          # crane boom, lowered fwd
    # ---- the A-frame: two white legs at the stern, cross-tie at the top ----
    ax = x1 - L * 0.05                                   # gantry base near the transom
    at = base - Hh * 2.5                                 # gantry height above deck
    spread = L * 0.075
    at = base - Hh * 3.0                                 # gantry stands tall
    spread = L * 0.11
    lw = max(3.0, L * 0.014)                             # leg thickness in px
    steel = mix(shade, PAYNE, 0.45)                      # cool steel: tone, not white
    def _leg(p0, p1, k):
        (ax0, ay0), (ax1, ay1) = p0, p1
        vx, vy = ax1 - ax0, ay1 - ay0
        n = (vx * vx + vy * vy) ** 0.5 or 1.0
        px, py = -vy / n * lw / 2, vx / n * lw / 2
        quad = [(ax0 + px, ay0 + py), (ax1 + px, ay1 + py),
                (ax1 - px, ay1 - py), (ax0 - px, ay0 - py)]
        cv.gouache(quad, steel, alpha=0.98, jitter=0.5, feather=0.4, seed=seed + k)
        cv.line([quad[0], quad[1]], ink, width=1, density=inkd * 0.8, seed=seed + k + 1)
        cv.line([quad[3], quad[2]], ink, width=1, density=inkd * 0.8, seed=seed + k + 2)
    _leg((ax - spread / 2, base), (ax, at), 20)         # two legs meeting at apex
    _leg((ax + spread / 2, base), (ax, at), 30)
    _leg((ax - spread * 0.42, at + Hh * 0.45), (ax + spread * 0.42, at + Hh * 0.45), 40)  # cross-tie
    # a warm sheave block at the apex (the hook that hangs the gear)
    cv.gouache([(ax - lw, at - 2), (ax + lw, at - 2), (ax + lw, at + lw * 1.2), (ax - lw, at + lw * 1.2)],
               fade(mix(VERMIL, OCHRE, 0.5), fog * 0.4), alpha=0.95, jitter=0.4,
               feather=0.3, seed=seed + 25)
    # orange gear on the working deck: the one warm accent (survival buoys)
    ob = sx1 + (x1 - sx1) * 0.72
    cv.gouache([(ob - L * 0.02, base - Hh * 0.30), (ob + L * 0.02, base - Hh * 0.30),
                (ob + L * 0.02, base), (ob - L * 0.02, base)],
               fade(mix(VERMIL, OCHRE, 0.45), fog * 0.4), alpha=0.95, jitter=0.5,
               feather=0.4, seed=seed + 26)
    # found edges: crisp sheer line, and the raked bow against the water
    cv.line([(x0 - L * 0.03, y - Hh), (x1 - L * 0.01, y - Hh)], ink, width=2,
            density=inkd * 0.8, seed=seed + 24)
    cv.line([(x0 - L * 0.03, y - Hh), (x0 + L * 0.03, y - Hh * 0.30), (x0 + L * 0.05, y + 1)],
            ink, width=2, density=inkd, seed=seed + 25)
    return blue


def paint_sailboat(cv, cx, y, L, seed, fog=0.4):
    """Sloop close-hauled: dark hull, two sails ghosting out of the mist."""
    Hh = L * 0.10
    x0, x1 = cx - L / 2, cx + L / 2
    lw = 2 if L > 240 else 1                             # line weight scales with hull
    hull_col = fade(HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull = [(x0, y - Hh), (x0 + L * 0.09, y + 1), (x1 - L * 0.10, y + 1), (x1, y - Hh)]
    cv.wash(hull, hull_col, density=1.0, jitter=1.4, feather=1.0, edge_dark=0.5,
            seed=seed)
    mx = cx - L * 0.04
    mt = y - Hh - L * 0.85
    cv.line([(mx, y - Hh), (mx, mt)], ink, 2, inkd, seed=seed + 1)
    main = [(mx + 2, mt + 4), (mx + 2, y - Hh - 2), (mx + L * 0.44, y - Hh - 2)]
    jib = [(mx - 3, mt + L * 0.12), (mx - 3, y - Hh - 2), (mx - L * 0.40, y - Hh - 2)]
    sail = mix((0.965, 0.955, 0.925), FOGGREY, fog * 0.45)   # sails ghost in fog
    cv.gouache(main, sail, alpha=0.95, jitter=1.2, feather=0.9, seed=seed + 2)
    cv.gouache(jib, sail, alpha=0.95, jitter=1.2, feather=0.9, seed=seed + 3)
    cv.wash(jib, fade(PAYNE, fog), density=0.20, jitter=1.5, feather=2.0,
            edge_dark=0.4, seed=seed + 4)
    belly = [(mx + 2, y - Hh - L * 0.32), (mx + L * 0.32, y - Hh - 2), (mx + 2, y - Hh - 2)]
    cv.wash(belly, FOGGREY, density=0.24, jitter=2, feather=2.5, seed=seed + 5)
    for sailp, s in ((main, 6), (jib, 7)):
        cv.line(sailp + [sailp[0]], ink, width=1, density=inkd * 0.7, jitter=0.8,
                seed=seed + s)
    # sail reflection: a pale drop of the sail into the water, then hull drag
    top = y + 8
    sailref = [(mx - L * 0.18, top), (mx + L * 0.30, top),
               (mx + L * 0.16, top + L * 0.30), (mx - L * 0.06, top + L * 0.28)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(sailref), (0, 0), 4.0 * S) *
                 cv._dry_keep(0.40), amount=0.32)
    return hull_col


PAINTERS = {"container": paint_container_ship, "cargo": paint_container_ship,
            "tanker": paint_tanker, "fishing": paint_fishing_boat,
            "sailing": paint_sailboat}
# reflection tone per vessel (its dominant hull colour)
REFL_COL = {"container": HULLDARK, "cargo": HULLDARK, "tanker": HULLDARK,
            "fishing": mix((0.85, 0.84, 0.82), PAYNE, 0.45),
            "sailing": HULLDARK}


def paint_reflection(cv, cx, y, L, seed, fog=0.0, hull_col=HULLDARK):
    """Broken reflection on a moving sea: horizontal drags of the hull's colour,
    tightening and fading downward. (7-ft swell = broken, never a mirror.)
    hull_col is already fog-faded by the painter."""
    r = np.random.default_rng(seed)
    col = fade(hull_col, fog)
    n = 8
    for k in range(n):
        t = k / (n - 1)
        yy = y + 10 * S + t * (Hh_ref(L) * 3.0)
        width_ = L * (1.00 - 0.55 * t) * r.uniform(0.7, 1.0)
        xc = cx + r.uniform(-L * 0.08, L * 0.08)
        h = max(1.5 * S, (3.5 * (1 - t) + r.uniform(0, 1.5)) * S)
        strk = [(xc - width_ / 2, yy), (xc + width_ / 2, yy + r.uniform(-1.5, 1.5)),
                (xc + width_ * 0.45, yy + h), (xc - width_ * 0.47, yy + h * 0.9)]
        cv.wash(strk, col, density=0.45 * (1 - t) + 0.06, jitter=3.0,
                feather=1.4 + 1.5 * t, edge_dark=0.0, granulation=0.25,
                variegation=0.4, seed=seed + k, dry=0.28 if k > 3 else 0.0)


def Hh_ref(L):
    return L * 0.085


def paint_scene(cv, ship, wx, seed):
    """Compose the whole picture from a ship record + weather."""
    fog = float(wx.get("fog", 0.4))
    wave = min(wx.get("wave_ft", 4) / 12.0, 1.0)
    wind = min(wx.get("wind_kn", 10) / 30.0, 1.0)
    L = ship_px(ship["length_m"])
    if ship["length_m"] < 60:                        # small craft come closer,
        L *= 1.28                                    # not a speck at the horizon
    # distance is truth: a passer at 8 nmi looms; at 60 she's a small shape in
    # the marine layer. Closest approach scales her and thickens the air.
    nmi = ship.get("nmi")
    if nmi is not None:
        dist_scale = float(np.interp(nmi, [3, 8, 15, 30, 60, 100],
                                          [1.18, 1.05, 0.95, 0.82, 0.70, 0.62]))
        L *= dist_scale
        fog = min(0.92, fog + float(np.interp(nmi, [10, 40, 100], [0.0, 0.12, 0.28])))
    cx = W * 0.30 if ship.get("type") == "tug" else W * 0.46   # tow trails astern
    y = HORIZON + 34 * S

    lt = ship.get("light")                            # light of the sighting hour
    # A ship sailing left to right is painted bow-left like the rest and the sheet
    # is mirrored at the end. The sun does not change sides with her heading.
    flip = config.sails_right(ship.get("heading", 180))
    paint_sky(cv, seed, fog=fog, light=lt, flip=flip)
    # reserves: a real foam line along the waterline, wake trailing astern,
    # and a bow-wave curl climbing the stem. These are the brightest whites,
    # scaled to the vessel so a small boat doesn't ride an ice floe.
    x0 = cx - L / 2                       # the stem (bow), ship-space faces left
    spd = float(ship.get("speed_kn") or 0.0)
    way = float(np.clip(spd / 14.0, 0.08, 1.5))       # 0.08 = adrift, 1.0 = 14 kn service
    th = float(np.clip(L * 0.026 * (0.35 + 0.65 * min(way, 1.2)), 2.5 * S, 13.0 * S))
    foam = [(x0 - 2, y + th * 0.15), (cx + L * 0.50, y - th * 0.15),
            (cx + L * 0.86, y + th * 0.4), (cx + L * 0.90, y + th * 0.85),
            (cx + L * 0.56, y + th), (x0, y + th * 0.7)]
    curl = min(1.4, way ** 0.7)                       # bow wave climbs with speed
    bow = [(x0 - L * 0.045 * curl, y + th * 0.3), (x0 + L * 0.010, y - th * 0.95 * curl),
           (x0 + L * 0.055, y - th * 0.3 * curl), (x0 + L * 0.020, y + th * 0.7)]
    cv.add_reserve(foam, feather=1.4)
    cv.add_reserve(bow, feather=1.1)
    paint_sea(cv, seed, fog=fog, wave=wave, wind=wind, light=lt, flip=flip)
    # mist dissolves the horizon (kept clear of the foam line below)
    cv.soften_band(HORIZON - (30 + 25 * fog) * S, HORIZON + (8 + 8 * fog) * S, (4 + 12 * fog) * S)
    cv.add_reserve(foam, feather=1.2)     # protect foam through ship + reflection
    cv.add_reserve(bow, feather=1.0)
    painter = PAINTERS.get(ship["type"], paint_container_ship)
    refl = REFL_COL.get(ship["type"], HULLDARK)
    if ship["type"] in HULL_OF:                       # painters with a colour of her own (end of file)
        own = HULL_OF[ship["type"]](ship)
        refl = mix((0.85, 0.84, 0.82), PAYNE, 0.45) if _is_white(own) else own
    refl = fade(refl, fog)
    paint_reflection(cv, cx, y, L, seed + 300, fog=0.0, hull_col=refl)
    kw = {"fog": fog}
    params = dict(ship.get("params") or {})              # remix hooks per record
    if "livery" not in params:                            # owner colours (liveries.py)
        params["livery"] = cargo_livery(ship)         # her owner's colours, or her own dice (end of file)
    import inspect
    sig = inspect.signature(painter).parameters
    for k, v in params.items():
        if k in sig:
            kw[k] = v
    if "ship" in sig:                                 # ...and some read everything she and the buoy said
        kw["ship"] = ship
    if "wx" in sig:
        kw["wx"] = wx
    if "length_m" in sig and "length_m" not in kw:   # some painters change layout by size
        kw["length_m"] = ship.get("length_m")
    ys = y - riding_high(ship) * 0.045 * L            # a light ship stands up out of the water (end of file)
    paint_bottom(cv, cx, y, ys, L, seed, fog, params["livery"].get("boot"))
    dark = bool(lt) and "moon" in lt                  # after sunset (light.for_iso): see Night, end of file
    before = cv.img.copy() if dark else None
    if dark:                                          # her shape is wanted later, without her smoke: a very soft thin
        real_wash = cv.wash                           # wash is exhaust or haze, so lay it on the "before" sheet too
        def wash(poly, masstone, *a, **k):
            if k.get("feather", 2.5) >= 6 and k.get("density", 0.55) <= 0.25:
                pre = cv.img.copy()
                real_wash(poly, masstone, *a, **k)
                np.multiply(before, cv.img / np.maximum(pre, 1e-4), out=before)
            else:
                real_wash(poly, masstone, *a, **k)
        cv.wash = wash
    try:
        painter(cv, cx, ys, L, seed + 100, **kw)
        weather_her(cv, ship, cx, ys, L, seed, fog)
    finally:
        if dark:
            del cv.wash
    after = cv.img.copy() if dark else None
    cv.clear_reserves()
    # finishing whites in gouache, the way a painter closes: the wave slapping
    # the hull (found edge, brightest accent), the wake trailing astern, spray.
    WHT = (0.975, 0.97, 0.955)
    cv.gouache_line([(x0 + 3, y + th * 0.25), (cx - L * 0.05, y + 1),
                     (cx + L * 0.48, y + 2)], WHT, width=2, alpha=0.85,
                    jitter=1.2, seed=seed + 420)
    r = np.random.default_rng(seed + 401)
    xa = cx + L * 0.50                     # wake dashes astern, widening back
    for k in range(int(round(5 * min(way, 1.3)))):     # wake fades with steerage way
        t = k / 4.0
        wx0 = xa + t * L * 0.34 * min(way, 1.2) + r.uniform(-6, 6) * S
        wy = y + th * 0.3 + t * th * 0.7 + r.uniform(-2, 2) * S
        cv.gouache_line([(wx0, wy), (wx0 + (8 + 20 * t) * S, wy + r.uniform(-2, 2) * S)],
                        WHT, width=2, alpha=0.85 - 0.4 * t, jitter=1.0,
                        seed=seed + 430 + k)
    for k in range(int(round(7 * min(way, 1.3) ** 1.5))):   # spray only when she's driving
        sx = x0 - L * 0.01 + r.uniform(-L * 0.05, L * 0.04)
        sy = y + r.uniform(-th * 1.3, th * 0.25)
        cv.gouache([(sx, sy), (sx + r.uniform(2, 4) * S, sy - 1 * S),
                    (sx + r.uniform(1, 3) * S, sy + 2 * S)], WHT,
                   alpha=0.9, jitter=0.6, feather=0.5, dry=0.3, seed=seed + 410 + k)
    # the unifying glaze: one thin transparent wash of the hour's colour over
    # everything, the classic move that seats ship, sea and sky in one light
    if lt and lt.get("glaze") and lt.get("glaze_amt", 0) > 0:
        cv.mask_wash(np.ones((H, W), np.float32), lt["glaze"], density=lt["glaze_amt"])
    if dark:
        twilight = lt.get("name") != "night"
        nocturne_glaze(cv, lt, fog, twilight)
        shape = cv2.GaussianBlur((np.abs(after - before).max(axis=2) > 0.05).astype(np.float32), (0, 0), 0.8 * S)
        paint_moon_and_stars(cv, lt, fog, seed, flip, np.clip(shape * 1.5, 0, 1), twilight)
        paint_lights(cv, before, after, ship, wx, cx, y, L, seed, fog, flip)
    # northbound traffic (up the coast) reads left-to-right: mirror the painting.
    # The caption is laid over afterward.
    if flip:
        cv.img = np.ascontiguousarray(cv.img[:, ::-1, :])
    return cv


def ship_px(length_m):
    L = min(max(length_m, 12), 400)
    return (100 + 480 * (L / 400) ** 0.7) * S


def paint_cruise_ship(cv, cx, y, L, seed, fog=0.4, livery=None):
    """Cruise ship v2 (Jul 30, repaint under the grade-sheet loop). Value plan
    FIRST, because v1 died on the panel (survival 0.31): a white ship is drawn
    by her darks. So every deck reads as a committed dark window/balcony BAND
    between white lit strips; the tier faces are cool ink, not pale grey; the
    profile rakes back toward the funnel like a real ship, and the hull throws
    real water. Signature = Carnival whale-tail funnel + the orange lifeboat
    line. Faces left."""
    Hh = L * 0.070                                     # hull freeboard
    x0, x1 = cx - L / 2, cx + L / 2
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    white = mix((0.97, 0.96, 0.935), FOGGREY, fog * 0.35)
    deep = fade(mix((0.72, 0.76, 0.84), PAYNE, 0.55), fog * 0.6)   # committed cool
    band = fade(mix(INDIGO, SUMI, 0.35), fog * 0.6)              # window/balcony ink
    lv = livery or {}
    hullc = lv.get("hull")                                       # HAL navy / Cunard black
    dark_hull = hullc is not None and not _is_white(hullc)
    bootc = lv.get("boot")
    # ---- hull: white (bare paper) or a painted dark liner hull ----
    hull = [(x0 - L * 0.04, y - Hh), (x0 + L * 0.02, y - Hh * 0.30), (x0 + L * 0.05, y + 1),
            (x1 - L * 0.012, y + 1), (x1, y - Hh * 0.55), (x1 - L * 0.006, y - Hh)]
    # white hull = bare paper (never painted); OR a painted dark liner hull
    if dark_hull:                                       # HAL / Cunard / Disney
        cv.wash(hull, fade(hullc, fog * 0.6), density=1.05, jitter=1.4, feather=1.0,
                edge_dark=0.5, granulation=0.35, variegation=0.4, seed=seed)
        strake = [(x0 - L * 0.03, y - Hh + 2), (x1 - L * 0.01, y - Hh + 2),
                  (x1 - L * 0.012, y - Hh * 0.6), (x0 + L * 0.005, y - Hh * 0.6)]
        cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.40)
    lowflank = [(x0 + L * 0.02, y - Hh * 0.40), (x1 - L * 0.008, y - Hh * 0.40),
                (x1 - L * 0.012, y - 2), (x0 + L * 0.05, y - 2)]
    cv.wash(lowflank, deep, density=0.30, jitter=1.6, feather=2.6, edge_dark=0.10,
            granulation=0.3, variegation=0.5, seed=seed)
    r = np.random.default_rng(seed + 2)
    # blue boot-topping riding the waterline (protected)
    boot = [(x0 + L * 0.045, y - Hh * 0.18), (x1 - L * 0.02, y - Hh * 0.18),
            (x1 - L * 0.016, y + 1), (x0 + L * 0.055, y + 1)]
    cv.wash(boot, fade(bootc or INDIGO, fog * 0.7), density=0.85, jitter=1.0, feather=0.9,
            dry=0.12, seed=seed + 3)
    # ---- superstructure: tiers stepping up AND raking aft toward the funnel ----
    base = y - Hh
    # (left inset, right inset, height) — front faces step back, stern near-vertical
    tiers = [(0.05, 0.02, 0.52), (0.09, 0.05, 0.48), (0.15, 0.10, 0.44), (0.24, 0.19, 0.36)]  # stern tapers
    top = base
    for i, (li, ri, ht) in enumerate(tiers):
        tx0, tx1, th = x0 + L * li, x1 - L * ri, Hh * ht
        rake = th * 0.55                                   # front face leans aft
        deck = [(tx0 + rake, top - th), (tx1, top - th), (tx1, top), (tx0, top)]
        # committed shadow flank so the deck EXISTS on six inks
        soft = 1.0 - 0.10 * i                              # upper decks lose their edge
        # the deck top is bare paper; only its shadowed lower flank gets a soft
        # cool graded wash (no dark rim), fading as fog eats the upper decks
        flank = [(tx0 + rake * 0.4, top - th * 0.55), (tx1, top - th * 0.55),
                 (tx1, top - 1), (tx0 + 2, top - 1)]
        cv.wash(flank, mix(deep, FOGGREY, 0.15 * i), density=0.50 * soft, jitter=1.4 + 0.5 * i,
                feather=1.8 + 0.6 * i, edge_dark=0.12, granulation=0.3, variegation=0.5,
                seed=seed + 10 + i)
        # the window/balcony BAND: committed dark strip = a real deck of glass.
        # Heaviest at the promenade, lightening upward; aft end dissolves (timbre).
        by0, by1 = top - th * 0.34, top - th * 0.18
        dens = (0.62, 0.50, 0.42, 0.34)[i]
        cv.wash([(tx0 + rake * 0.5, by0), (tx1 - L * 0.05, by0),
                 (tx1 - L * 0.05, by1), (tx0 + 2, by1)],
                band, density=dens, jitter=1.0, feather=0.7, dry=0.18, seed=seed + 30 + i)
        cv.wash([(tx1 - L * 0.07, by0), (tx1 - 2, by0), (tx1 - 2, by1), (tx1 - L * 0.07, by1)],
                band, density=dens * 0.55, jitter=1.2, feather=2.2, seed=seed + 35 + i)  # lost aft
        # crisp deck-top ink (found edge) + cool shadow under the lip
        cv.line([(tx0 + rake, top - th), (tx1, top - th)], ink, width=1,
                density=inkd * 0.75, seed=seed + 40 + i)
        top -= th
    top_x0 = x0 + L * (tiers[-1][0]) + Hh * tiers[-1][2] * 0.55           # topmost front
    # ---- lifeboats: the orange dotted line along the lowest tier (protected) ----
    ly = base - Hh * tiers[0][2] * 0.50
    xk = x0 + L * 0.11
    while xk < x1 - L * 0.05:
        cv.gouache([(xk, ly - 3), (xk + L * 0.024, ly - 3),
                    (xk + L * 0.024, ly + 2.2), (xk, ly + 2.2)],
                   fade(mix(VERMIL, OCHRE, 0.35), fog * 0.5), alpha=0.95, jitter=0.6,
                   feather=0.4, seed=seed + 60 + int(xk))
        xk += L * 0.038
    fw, fh = L * 0.055, Hh * 0.95
    fx = x1 - L * 0.36
    ft = top                                              # sits on the top tier
    if not lv.get("tail"):                                # a normal raked liner funnel
        fcol = lv.get("funnel")
        painted = fcol is not None and not _is_white(fcol)
        fbody = [(fx, ft), (fx + fw * 0.30, ft - fh * 1.05), (fx + fw * 1.35, ft - fh * 1.05),
                 (fx + fw * 1.55, ft)]
        cv.wash(fbody, fade(fcol, fog * 0.5) if painted else deep,
                density=0.8 if painted else 0.55, jitter=0.9, feather=0.7,
                edge_dark=0.45, seed=seed + 70)
        if lv.get("band"):                                # the line's funnel band / logo
            cv.wash([(fx + fw * 0.05, ft - fh * 0.75), (fx + fw * 1.42, ft - fh * 0.75),
                     (fx + fw * 1.48, ft - fh * 0.50), (fx + fw * 0.10, ft - fh * 0.50)],
                    fade(lv["band"], fog * 0.5), density=0.85, jitter=0.7, feather=0.5, seed=seed + 71)
        cv.line([(fx, ft), (fx + fw * 0.30, ft - fh * 1.05), (fx + fw * 1.35, ft - fh * 1.05),
                 (fx + fw * 1.55, ft)], ink, width=1, density=inkd * 0.75, seed=seed + 73)
        cv.wash([(fx + fw * 0.5, ft - fh * 0.95), (fx + fw * 0.9, ft - fh * 1.0),
                 (fx - fw * 2.6, ft - fh * 2.6), (fx - fw * 3.4, ft - fh * 2.0)],
                mix(PAYNE, FOGGREY, 0.5), density=0.10, jitter=7, feather=8,
                edge_dark=0.15, variegation=0.7, seed=seed + 74)
        return deep
    # ---- Carnival funnel: chunky white stack, red whale-tail sweeping AFT ----
    body = [(fx, ft), (fx + fw * 0.20, ft - fh), (fx + fw * 0.80, ft - fh), (fx + fw, ft)]
    aft = [(fx + fw * 0.5, ft), (fx + fw * 0.5, ft - fh + 2), (fx + fw * 0.80, ft - fh + 2), (fx + fw, ft)]
    cv.wash(aft, deep, density=0.55, jitter=0.8, feather=1.2, edge_dark=0.2,
            granulation=0.3, seed=seed + 70)                                   # shaded aft half
    cv.line([(fx, ft), (fx + fw * 0.20, ft - fh), (fx + fw * 0.80, ft - fh), (fx + fw, ft)],
            ink, width=1, density=inkd * 0.7, seed=seed + 78)
    # the tail: red wing thrown back and slightly up from the funnel top
    tail = [(fx + fw * 0.15, ft - fh * 0.98), (fx + fw * 2.6, ft - fh * 1.30),
            (fx + fw * 2.9, ft - fh * 0.98), (fx + fw * 0.75, ft - fh * 0.62)]
    cv.wash(tail, fade(VERMIL, fog * 0.4), density=0.9, jitter=0.9, feather=0.6,
            edge_dark=0.45, seed=seed + 71)
    cv.wash([(fx + fw * 1.7, ft - fh * 1.14), (fx + fw * 2.6, ft - fh * 1.30),
             (fx + fw * 2.75, ft - fh * 1.05), (fx + fw * 1.9, ft - fh * 0.95)],
            fade(INDIGO, fog * 0.4), density=0.8, jitter=0.7, feather=0.5, seed=seed + 72)  # blue tip
    cv.line([(fx, ft), (fx + fw * 0.20, ft - fh), (fx + fw * 2.6, ft - fh * 1.30)],
            ink, width=1, density=inkd * 0.8, seed=seed + 73)
    # a wisp of exhaust off the tail, downwind
    cv.wash([(fx + fw * 0.3, ft - fh * 0.9), (fx + fw * 0.7, ft - fh * 1.0),
             (fx - fw * 2.6, ft - fh * 2.6), (fx - fw * 3.4, ft - fh * 2.0)],
            mix(PAYNE, FOGGREY, 0.5), density=0.10, jitter=7, feather=8,
            edge_dark=0.15, variegation=0.7, seed=seed + 74)
    # navigation mast: a fine ink stick over the bridge (top tier, forward)
    mx = x0 + L * 0.34
    cv.line([(mx, top), (mx, top - Hh * 0.75)], ink, width=1, density=inkd * 0.7, seed=seed + 76)
    cv.line([(mx - L * 0.02, top - Hh * 0.5), (mx + L * 0.02, top - Hh * 0.5)],
            ink, width=1, density=inkd * 0.6, seed=seed + 77)
    # ---- weathering / incident: rust weep at scuppers, a scuff on the hull ----
    for k in range(4):
        sx = x0 + L * (0.18 + 0.19 * k) + r.uniform(-6, 6)
        cv.wash([(sx, y - Hh * 0.42), (sx + L * 0.006, y - Hh * 0.42),
                 (sx + L * 0.010, y - Hh * 0.05), (sx + L * 0.002, y - Hh * 0.05)],
                fade(RUST, fog * 0.5), density=0.28, jitter=0.8, feather=0.9,
                seed=seed + 80 + k)                    # faint rust weep, restraint
    # ---- found edges: sheer line, clipper bow, and the top profile ----
    cv.line([(x0 - L * 0.04, y - Hh), (x1 - L * 0.006, y - Hh)], ink, width=2,
            density=inkd * 0.8, seed=seed + 90)
    cv.line([(x0 - L * 0.04, y - Hh), (x0 + L * 0.02, y - Hh * 0.30), (x0 + L * 0.05, y + 1)],
            ink, width=2, density=inkd, seed=seed + 91)
    return deep


PAINTERS["cruise"] = paint_cruise_ship
PAINTERS["passenger"] = paint_cruise_ship
REFL_COL["cruise"] = mix((0.72, 0.76, 0.84), PAYNE, 0.55)
REFL_COL["passenger"] = REFL_COL["cruise"]

PAINTERS["research"] = paint_research_ship
REFL_COL["research"] = HULLDARK


# =====================================================================
# Fleet painters (Jul 30). APPEND-ONLY block: never edit by replacing a
# span between an earlier def and a later anchor -- that is how these four
# were once deleted. Register each painter immediately after its def.
# =====================================================================

def _is_white(c):
    """A near-white masstone means 'unpainted / bare paper' on this frame."""
    return c is None or (c[0] > 0.85 and c[1] > 0.85 and c[2] > 0.80)


def _pctc_livery(livery, seed):
    """Normalise the car-carrier livery: accepts the old bare band colour, a
    liveries.py dict, or None (random band, white wall)."""
    if isinstance(livery, dict):
        lv = dict(livery)
        lv.setdefault("band", INDIGO)
        lv.setdefault("hull", (0.965, 0.955, 0.93))
        if lv.get("band") is None:
            lv["band"] = INDIGO
        return lv
    band = livery
    if band is None:
        r0 = np.random.default_rng(seed)
        band = [VERMIL, INDIGO, TEAL][int(r0.integers(0, 3))]
    return dict(band=band, hull=(0.965, 0.955, 0.93), funnel=None)


def livery_for(name):
    """PCTC operator livery band from the ship name (this coast's regulars)."""
    n = (name or "").upper()
    if "HIGHWAY" in n or "K LINE" in n or "GLOVIS" in n:
        return VERMIL                                    # K Line / Glovis red
    if "LEADER" in n or "ACE" in n or "AUTO" in n or "NYK" in n:
        return INDIGO                                    # NYK / MOL blue
    if any(k in n for k in ("TITAN", "TAMES", "TALIS", "MORNING", "EUKOR",
                           "WALLENIUS", "WILHELMSEN")):
        return TEAL                                      # WW / EUKOR green
    return INDIGO


def paint_car_carrier(cv, cx, y, L, seed, fog=0.4, livery=None):
    livery = _pctc_livery(livery, seed)
    """PCTC / RoRo: one enormous unbroken slab, bridge perched forward on top,
    folded ramp on the stern quarter. The slab is near-white against a pale
    sky, so it is FOUND by its committed cool shaded lower flank (must survive
    the six-ink panel: Luminosa lesson), inked top/bow edges and a livery band."""
    Hh = L * 0.215                                       # freeboard: a wall
    x0, x1 = cx - L / 2, cx + L / 2
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    white = mix((0.965, 0.955, 0.93), FOGGREY, fog * 0.35)
    shade = mix((0.76, 0.79, 0.85), FOGGREY, fog * 0.4)   # cool flank, not grey
    deep = fade(mix((0.76, 0.79, 0.85), PAYNE, 0.52), fog * 0.6)
    band = fade(livery["band"], fog * 0.6)
    hullc = livery["hull"]                                    # white wall or a coloured hull
    top = y - Hh
    body = [(x0 + L * 0.018, y + 1),
            (x0, y - Hh * 0.30),                         # bow knuckle
            (x0 + L * 0.008, top + Hh * 0.14),           # steep stem
            (x0 + L * 0.045, top),                       # rounded shoulder
            (x1 - L * 0.01, top),                        # long unbroken top
            (x1, top + Hh * 0.10),                       # transom corner
            (x1 - L * 0.005, y + 1)]
    if _is_white(hullc):
        cv.wash(body, deep, density=1.0, jitter=1.2, feather=1.0, edge_dark=0.5,
                granulation=0.35, variegation=0.45, seed=seed)
        # sunlit upper wall above the livery band: lifted toward bare paper
        lit = [(x0 + L * 0.008, top + Hh * 0.14), (x0 + L * 0.045, top),
               (x1 - L * 0.01, top), (x1, top + Hh * 0.10),
               (x1 - L * 0.008, top + Hh * 0.30), (x0 + L * 0.004, top + Hh * 0.30)]
        cv.lift_mask(cv2.GaussianBlur(_polymask(lit), (0, 0), 2.0 * S), amount=0.72)
    else:                                                     # a painted wall: MOL blue, WW teal
        cv.wash(body, fade(hullc, fog * 0.6), density=1.0, jitter=1.2, feather=1.0,
                edge_dark=0.55, granulation=0.4, variegation=0.5, seed=seed)
        cv.wash(body, deep, density=0.28, jitter=1.4, feather=1.6, edge_dark=0.1, seed=seed + 90)
        lit = [(x0 + L * 0.008, top + Hh * 0.14), (x0 + L * 0.045, top),
               (x1 - L * 0.01, top), (x1, top + Hh * 0.10),
               (x1 - L * 0.008, top + Hh * 0.22), (x0 + L * 0.004, top + Hh * 0.22)]
        cv.lift_mask(cv2.GaussianBlur(_polymask(lit), (0, 0), 2.0 * S), amount=0.30)
    # livery band across the flank
    by0, by1 = top + Hh * 0.30, top + Hh * 0.42
    stripe = [(x0 + L * 0.012, by0), (x1 - L * 0.008, by0),
              (x1 - L * 0.008, by1), (x0 + L * 0.005, by1)]
    cv.wash(stripe, band, density=0.8, jitter=1.0, feather=0.8, edge_dark=0.4,
            dry=0.12, seed=seed + 2)
    # bridge crowns the bow: wraparound dark windows on a set-back wheelhouse
    bx0, bx1 = x0 + L * 0.03, x0 + L * 0.22
    bt = top - Hh * 0.22
    house = [(bx0, top), (bx0 + L * 0.015, bt), (bx1, bt), (bx1, top)]
    cv.wash(house, shade, density=0.7, jitter=1.0, feather=0.8, edge_dark=0.45,
            granulation=0.3, seed=seed + 3)
    cv.wash([(bx0 + L * 0.02, bt + Hh * 0.05), (bx1 - L * 0.008, bt + Hh * 0.05),
             (bx1 - L * 0.008, bt + Hh * 0.14), (bx0 + L * 0.025, bt + Hh * 0.14)],
            fade(INDIGO, fog), density=0.7, jitter=0.7, feather=0.6, seed=seed + 4)
    cv.line([(bx0, top), (bx0 + L * 0.015, bt), (bx1, bt), (bx1, top)], ink,
            width=1, density=inkd * 0.85, seed=seed + 5)
    # vent grille row high on the flank + two deck-level lines that catch light
    r = np.random.default_rng(seed + 6)
    gy = top + Hh * 0.14
    xk = x0 + L * 0.30
    while xk < x1 - L * 0.04:
        seg = r.uniform(L * 0.010, L * 0.020)
        cv.line([(xk, gy), (xk + seg, gy)], ink, width=1,
                density=inkd * 0.45, seed=seed + 30 + int(xk))
        xk += seg + r.uniform(L * 0.008, L * 0.018)
    for k, fy in enumerate((0.58, 0.78)):
        cv.line([(x0 + L * 0.02, top + Hh * fy), (x1 - L * 0.012, top + Hh * fy)],
                shade, width=1, density=0.55 * (1 - fog * 0.4), seed=seed + 40 + k)
    # weathering: rust weep from the scuppers down the wall (restrained)
    for k in range(3):
        sx = x0 + L * (0.15 + 0.31 * k) + r.uniform(-20, 20)
        run = r.uniform(0.35, 0.8)                              # weeps of varied length
        cv.wash([(sx, top + Hh * 0.44), (sx + L * 0.006, top + Hh * 0.44),
                 (sx + L * 0.010, top + Hh * (0.44 + 0.6 * run)),
                 (sx + L * 0.002, top + Hh * (0.44 + 0.6 * run))],
                fade(RUST, fog * 0.5), density=0.16, jitter=1.2, feather=1.4,
                seed=seed + 100 + k)
    # stern quarter ramp: folded up, a dark diagonal wedge on the transom
    ramp = [(x1 - L * 0.012, y - Hh * 0.10), (x1, top + Hh * 0.42),
            (x1 - L * 0.055, y - Hh * 0.55), (x1 - L * 0.06, y - Hh * 0.12)]
    cv.wash(ramp, fade(PAYNE, fog * 0.7), density=0.7, jitter=0.9, feather=0.8,
            edge_dark=0.5, seed=seed + 7)
    cv.line([ramp[0], ramp[1]], ink, width=1, density=inkd * 0.8, seed=seed + 8)
    # small funnel casing aft on top + a wisp downwind
    fw = L * 0.03
    fx = x1 - L * 0.16
    ft = top - Hh * 0.16
    fcol = livery.get("funnel")
    cv.wash([(fx, top), (fx + fw * 0.15, ft), (fx + fw * 0.85, ft), (fx + fw, top)],
            fade(fcol, fog * 0.6) if fcol and not _is_white(fcol) else mix(white, shade, 0.5),
            density=0.75, jitter=0.7, feather=0.6, seed=seed + 9)
    cv.line([(fx + fw * 0.1, ft + 1), (fx + fw * 0.9, ft + 1)], ink, width=2,
            density=inkd, seed=seed + 10)
    cv.wash([(fx, ft), (fx + fw, ft - Hh * 0.05),
             (fx - fw * 3.0, ft - Hh * 0.75), (fx - fw * 4.0, ft - Hh * 0.45)],
            mix(PAYNE, FOGGREY, 0.5), density=0.10, jitter=7, feather=8,
            edge_dark=0.15, variegation=0.7, seed=seed + 11)
    # boot-topping: a dark antifouling sliver grounding the wall in the water
    cv.wash([(x0 + L * 0.02, y - Hh * 0.09), (x1 - L * 0.004, y - Hh * 0.09),
             (x1 - L * 0.006, y + 1), (x0 + L * 0.024, y + 1)],
            fade(HULLDARK, fog * 0.6), density=0.9, jitter=1.2, feather=0.8,
            edge_dark=0.4, dry=0.1, seed=seed + 12)
    # found edges: the razor top of the slab against the sky, and the stem
    cv.line([(x0 + L * 0.045, top), (x1 - L * 0.01, top)], ink, width=2,
            density=inkd * 0.85, seed=seed + 13)
    cv.line([(x0 + L * 0.018, y + 1), (x0, y - Hh * 0.30),
             (x0 + L * 0.008, top + Hh * 0.14), (x0 + L * 0.045, top)],
            ink, width=2, density=inkd, seed=seed + 14)
    return deep


PAINTERS["carcarrier"] = paint_car_carrier
REFL_COL["carcarrier"] = mix((0.76, 0.79, 0.85), PAYNE, 0.52)


def paint_bulk_carrier(cv, cx, y, L, seed, fog=0.4, livery=None):
    """Geared bulker, laden: long low black hull, five raised hatch covers
    marching down the deck, ochre deck cranes standing between them with jibs
    cocked forward, chunky white castle and funnel right aft. The cranes
    crossing the sky are the found edges that name the type."""
    lv = livery or {}
    Hh = L * 0.075                                       # she's full: low
    x0, x1 = cx - L / 2, cx + L / 2
    hull_col = fade(lv.get("hull") or HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull = [(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1),
            (x1 - L * 0.015, y + 1), (x1, y - Hh * 0.45), (x1 - L * 0.006, y - Hh)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.35, variegation=0.4, seed=seed)
    strake = [(x0 + L * 0.02, y - Hh + 2), (x1 - L * 0.012, y - Hh + 2),
              (x1 - L * 0.015, y - Hh + Hh * 0.45), (x0 + L * 0.035, y - Hh + Hh * 0.45)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.42)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.004, y - 3),
             (x1 - L * 0.008, y + 1), (x0 + L * 0.06, y + 1)],
            fade(RUST, fog), density=0.55, jitter=1.4, feather=0.9, dry=0.15, seed=seed + 1)
    # forecastle: a low raised deck at the bow with the foremast
    fc = [(x0 + L * 0.008, y - Hh), (x0 + L * 0.008, y - Hh * 1.30),
          (x0 + L * 0.085, y - Hh * 1.30), (x0 + L * 0.10, y - Hh)]
    cv.wash(fc, fade(mix((0.85, 0.83, 0.80), PAYNE, 0.35), fog), density=0.7,
            jitter=1.0, feather=0.9, edge_dark=0.4, seed=seed + 2)
    cv.line([(x0 + L * 0.045, y - Hh * 1.30), (x0 + L * 0.045, y - Hh * 2.6)],
            ink, width=1, density=inkd * 0.7, seed=seed + 3)
    # hatch covers: raised committed-tone slabs down the deck, lids catching light
    deck = y - Hh
    hatch_col = fade(mix((0.62, 0.58, 0.50), PAYNE, 0.35), fog)   # warm, has an ink home
    n_h = 5
    hx0, hx1 = x0 + L * 0.13, x1 - L * 0.21          # cargo length, castle aft
    span = (hx1 - hx0) / n_h
    hw = span * 0.74                                  # sky between the hatches
    hh = Hh * 0.62
    for k in range(n_h):
        ax = hx0 + k * span + (span - hw) / 2
        slab = [(ax, deck), (ax, deck - hh), (ax + hw, deck - hh), (ax + hw, deck)]
        cv.wash(slab, hatch_col, density=0.85, jitter=1.0, feather=0.7, edge_dark=0.5,
                granulation=0.3, seed=seed + 10 + k)
        lid = [(ax, deck - hh), (ax + hw, deck - hh), (ax + hw, deck - hh * 0.78),
               (ax, deck - hh * 0.78)]
        cv.lift_mask(cv2.GaussianBlur(_polymask(lid), (0, 0), 0.8 * S), 0.35)  # sky on the lid
        cv.line([(ax, deck - hh), (ax + hw, deck - hh)], ink, width=1,
                density=inkd * 0.7, seed=seed + 20 + k)
        cv.line([(ax, deck - hh), (ax, deck), (ax + hw, deck), (ax + hw, deck - hh)],
                ink, width=1, density=inkd * 0.5, seed=seed + 25 + k)   # box edges
    # deck cranes: ochre pedestals in the gaps, jibs cocked forward-up
    crane_col = fade(mix(OCHRE, VERMIL, 0.25), fog * 0.6)
    for k in range(1, n_h):                            # cranes between hatch pairs
        px = hx0 + k * span
        ph = Hh * 1.05                                 # pedestal + cab height
        cw = max(3.0, L * 0.014)
        cv.wash([(px - cw, deck), (px - cw, deck - ph), (px + cw, deck - ph), (px + cw, deck)],
                crane_col, density=0.95, jitter=0.7, feather=0.6, edge_dark=0.4,
                seed=seed + 30 + k)
        j0 = (px, deck - ph * 0.95)
        rake = 1.0 + 0.22 * ((k * 37) % 3 - 1)          # jibs cocked, not marching
        j1 = (px - L * 0.10 * rake, deck - ph * (1.35 + 0.75 * rake))
        cv.line([j0, j1], crane_col, width=3, density=0.9 * (1 - fog * 0.3), seed=seed + 40 + k)
        cv.line([j0, j1], ink, width=1, density=inkd * 0.75, seed=seed + 45 + k)
        cv.line([j1, (j1[0] + L * 0.005, j1[1] + Hh * 0.9)], ink, width=1,
                density=inkd * 0.6, seed=seed + 50 + k)     # pendant from the jib head
    # aft castle + funnel + downwind exhaust
    sw = L * 0.145                                       # chunky house, not a tower
    sx = x1 - L * 0.19
    st = y - Hh - Hh * 2.0
    castle = [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)]
    cv.wash(castle, mix(lv.get("house") or (0.92, 0.90, 0.86), FOGGREY, fog * 0.4), density=0.7,
            jitter=1.1, feather=0.8, edge_dark=0.4, granulation=0.3, seed=seed + 60)
    cv.wash([(sx + sw * 0.55, st), (sx + sw, st), (sx + sw, y - Hh),
             (sx + sw * 0.55, y - Hh)], fade(PAYNE, fog), density=0.32,
            jitter=1.2, feather=1.4, seed=seed + 61)
    cv.line([(sx + 3, st + Hh * 0.35), (sx + sw - 3, st + Hh * 0.35)],
            ink, width=1, density=inkd * 0.8, seed=seed + 62)
    cv.line([(sx - 3, st + 3), (sx + sw + 3, st + 3)], ink, width=2,
            density=inkd, seed=seed + 63)
    cv.line([(sx, y - Hh), (sx, st), (sx + sw, st)], ink, width=1,
            density=inkd * 0.75, seed=seed + 64)
    fw = sw * 0.36
    fx = sx + sw * 0.5
    fun = [(fx, st), (fx + fw * 0.15, st - Hh * 0.6),
           (fx + fw * 0.85, st - Hh * 0.6), (fx + fw, st)]
    cv.wash(fun, fade(lv.get("funnel") or mix(SUMI, PAYNE, 0.5), fog), density=0.8, jitter=1,
            feather=0.8, seed=seed + 65)
    cv.line([(fx + fw * 0.12, st - Hh * 0.55), (fx + fw * 0.88, st - Hh * 0.55)],
            fade(lv.get("band") or VERMIL, fog * 0.5), width=2, density=0.9, seed=seed + 66)   # band on funnel
    cv.wash([(fx, st - Hh * 0.65), (fx + fw, st - Hh * 0.7),
             (fx - fw * 3.5, st - Hh * 3.0), (fx - fw * 4.5, st - Hh * 2.2)],
            mix(PAYNE, FOGGREY, 0.5), density=0.12, jitter=8, feather=9,
            edge_dark=0.15, variegation=0.7, seed=seed + 67)
    cv.line([(x0, y - Hh), (x1 - L * 0.006, y - Hh)], ink, width=2,
            density=inkd * 0.85, seed=seed + 68)
    cv.line([(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1)],
            ink, width=2, density=inkd, seed=seed + 69)
    return hull_col


PAINTERS["bulk"] = paint_bulk_carrier
REFL_COL["bulk"] = HULLDARK


def paint_tug(cv, cx, y, L, seed, fog=0.4, livery=None, tow=True):
    """Ocean tug with a barge on the wire (tow=False: running light). The tug leads, facing left: squat
    black hull with flare and tyre fenders, white house and tall wheelhouse
    forward, twin black stacks, low afterdeck. The hawser catenaries down
    astern to a long low petroleum barge on the same swell. L is the TUG's
    length; the tow trails astern of the tug's transom."""
    Hh = L * 0.17
    x0, x1 = cx - L / 2, cx + L / 2
    lw = 2 if L > 240 else 1                             # line weight scales with hull
    lv = livery or {}
    hull_col = fade(lv.get("hull") or HULLDARK, fog)
    stack_col = lv.get("funnel") or SUMI
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    white = mix((0.96, 0.95, 0.92), FOGGREY, fog * 0.35)
    shade = mix((0.78, 0.81, 0.86), FOGGREY, fog * 0.4)
    deep = fade(mix((0.78, 0.81, 0.86), PAYNE, 0.5), fog * 0.6)
    hull = [(x0, y - Hh * 1.35), (x0 + L * 0.10, y + 1), (x1 - L * 0.05, y + 1),
            (x1, y - Hh * 0.55), (x1 - L * 0.02, y - Hh * 0.62),
            (x0 + L * 0.55, y - Hh * 0.85), (x0 + L * 0.20, y - Hh * 1.05)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.4, feather=1.0, edge_dark=0.5,
            granulation=0.35, variegation=0.4, seed=seed)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.02, y - 3),
             (x1 - L * 0.05, y + 1), (x0 + L * 0.09, y + 1)],
            fade(VERMIL, fog), density=0.65, jitter=1, feather=0.8, dry=0.12, seed=seed + 1)
    r = np.random.default_rng(seed + 2)
    for k in range(4):                                   # tyre fenders on the shoulder
        fx = x0 + L * (0.16 + 0.11 * k) + r.uniform(-2, 2)
        fy = y - Hh * (0.98 - 0.09 * k)
        rr = max(2.0, L * 0.026)
        cv.wash([(fx - rr, fy - rr * 0.7), (fx + rr, fy - rr * 0.7),
                 (fx + rr, fy + rr * 0.7), (fx - rr, fy + rr * 0.7)],
                fade(SUMI, fog), density=0.9, jitter=0.9, feather=0.7, seed=seed + 10 + k)
    # deckhouse + tall wheelhouse forward: white = paper, found by ink + windows
    base = y - Hh * 0.95
    hx0, hx1 = x0 + L * 0.16, x0 + L * 0.62
    h1 = Hh * 0.95
    house = [(hx0, base - h1), (hx1, base - h1), (hx1, base), (hx0, base)]
    cv.wash([(hx0, base - h1 * 0.45), (hx1, base - h1 * 0.45), (hx1, base), (hx0, base)],
            deep, density=0.4, jitter=1.2, feather=1.6, edge_dark=0.12, seed=seed + 3)  # shaded flank
    wx0, wx1 = hx0 + L * 0.02, hx0 + L * 0.30
    h2 = Hh * 0.85
    top = base - h1
    cv.wash([(wx0, top - h2 * 0.4), (wx1, top - h2 * 0.4), (wx1, top), (wx0, top)],
            deep, density=0.35, jitter=1.0, feather=1.4, edge_dark=0.12, seed=seed + 5)
    cv.wash([(wx0 + 2, top - h2 * 0.85), (wx1 - 2, top - h2 * 0.85),
             (wx1 - 2, top - h2 * 0.55), (wx0 + 2, top - h2 * 0.55)],
            fade(INDIGO, fog), density=0.7, jitter=0.7, feather=0.5, seed=seed + 7)  # bridge glass
    cv.line([(hx0, base), (hx0, base - h1), (hx1, base - h1), (hx1, base)], ink,
            width=1, density=inkd * 0.8, seed=seed + 8)
    cv.line([(wx0, top), (wx0, top - h2), (wx1, top - h2), (wx1, top)], ink,
            width=1, density=inkd * 0.85, seed=seed + 9)
    mx = (wx0 + wx1) / 2
    cv.line([(mx, top - h2), (mx, top - h2 - Hh * 1.1)], ink, width=1,
            density=inkd * 0.8, seed=seed + 15)
    cv.line([(mx - L * 0.05, top - h2 - Hh * 0.75), (mx + L * 0.05, top - h2 - Hh * 0.75)],
            ink, width=1, density=inkd * 0.7, seed=seed + 16)
    for i in range(2):                                   # twin black stacks
        sxk = hx0 + L * 0.36 + i * L * 0.075
        cv.wash([(sxk, top), (sxk, top - Hh * 0.75), (sxk + L * 0.05, top - Hh * 0.75),
                 (sxk + L * 0.05, top)], fade(stack_col, fog), density=0.95, jitter=0.8,
                feather=0.7, edge_dark=0.4, seed=seed + 20 + i)
        if lv.get("band"):                                # the company's stack band
            cv.line([(sxk, top - Hh * 0.45), (sxk + L * 0.05, top - Hh * 0.45)],
                    fade(lv["band"], fog), width=2, density=0.9, seed=seed + 22 + i)
    cv.wash([(hx0 + L * 0.36, top - Hh * 0.78), (hx0 + L * 0.49, top - Hh * 0.8),
             (hx0 + L * 0.10, top - Hh * 2.4), (hx0 - L * 0.05, top - Hh * 1.8)],
            mix(PAYNE, FOGGREY, 0.5), density=0.11, jitter=7, feather=8,
            edge_dark=0.15, variegation=0.7, seed=seed + 25)
    wch = (x1 - L * 0.12, y - Hh * 0.60)                    # towing winch drum
    cv.wash([(wch[0] - L * 0.03, wch[1] - Hh * 0.28), (wch[0] + L * 0.03, wch[1] - Hh * 0.28),
             (wch[0] + L * 0.03, wch[1]), (wch[0] - L * 0.03, wch[1])],
            fade(mix(SUMI, PAYNE, 0.5), fog), density=0.9, jitter=0.7, feather=0.6, seed=seed + 30)
    cv.line([(x0, y - Hh * 1.35), (x0 + L * 0.20, y - Hh * 1.05),
             (x0 + L * 0.55, y - Hh * 0.85), (x1 - L * 0.02, y - Hh * 0.62)],
            ink, width=lw, density=inkd * 0.8, seed=seed + 31)
    cv.line([(x0, y - Hh * 1.35), (x0 + L * 0.10, y + 1)], ink, width=lw,
            density=inkd, seed=seed + 32)
    if not tow:
        return hull_col
    # ---- the tow: hawser catenary out to a long low petroleum barge ----
    gap = L * 0.55
    bl = L * 1.55
    bx0, bx1 = x1 + gap, x1 + gap + bl
    bh = Hh * 0.60
    p0 = (wch[0], wch[1] - Hh * 0.12)
    p1 = (bx0 + L * 0.03, y - bh * 1.05)
    xs = np.linspace(p0[0], p1[0], 24)
    sag = Hh * 1.05                                      # the wire kisses the sea
    t = (xs - p0[0]) / (p1[0] - p0[0])
    ys = p0[1] * (1 - t) + p1[1] * t + sag * (4 * t * (1 - t))
    cv.line(list(zip(xs, ys)), ink, width=1, density=inkd * 0.75, seed=seed + 40)
    barge_col = fade(mix(HULLDARK, RUST, 0.35), fog)
    barge = [(bx0, y - bh), (bx0 + L * 0.09, y + 1), (bx1 - L * 0.02, y + 1),
             (bx1, y - bh * 0.5), (bx1 - L * 0.01, y - bh)]
    cv.wash(barge, barge_col, density=1.0, jitter=1.4, feather=1.0, edge_dark=0.5,
            granulation=0.35, variegation=0.45, seed=seed + 50)
    cv.wash([(bx0 + L * 0.05, y - 3), (bx1 - L * 0.01, y - 3),
             (bx1 - L * 0.02, y + 1), (bx0 + L * 0.08, y + 1)],
            fade(VERMIL, fog), density=0.55, jitter=1, feather=0.8, dry=0.12, seed=seed + 51)
    # barge deck: coaming line, two hatch domes, pump house aft, a bollard pair
    cv.line([(bx0 + L * 0.06, y - bh - Hh * 0.05), (bx1 - L * 0.05, y - bh - Hh * 0.05)],
            fade(mix(RUST, PAYNE, 0.5), fog), width=lw, density=0.7, seed=seed + 52)  # coaming
    for k in range(2):
        dx = bx0 + bl * (0.32 + 0.28 * k)
        cv.wash([(dx - L * 0.06, y - bh), (dx - L * 0.05, y - bh - Hh * 0.20),
                 (dx + L * 0.05, y - bh - Hh * 0.20), (dx + L * 0.06, y - bh)],
                fade(mix((0.72, 0.70, 0.66), PAYNE, 0.4), fog), density=0.8,
                jitter=0.9, feather=0.7, edge_dark=0.4, seed=seed + 55 + k)
    ph0 = bx1 - L * 0.16
    cv.wash([(ph0, y - bh), (ph0, y - bh - Hh * 0.42), (ph0 + L * 0.11, y - bh - Hh * 0.42),
             (ph0 + L * 0.11, y - bh)], deep, density=0.4, jitter=1.0, feather=1.2,
            edge_dark=0.15, seed=seed + 60)
    cv.line([(ph0, y - bh), (ph0, y - bh - Hh * 0.42), (ph0 + L * 0.11, y - bh - Hh * 0.42)],
            ink, width=1, density=inkd * 0.75, seed=seed + 62)
    for k in range(2):                                   # bollards near the barge bow
        bxk = bx0 + L * (0.10 + 0.04 * k)
        cv.wash([(bxk, y - bh), (bxk, y - bh - Hh * 0.16), (bxk + L * 0.02, y - bh - Hh * 0.16),
                 (bxk + L * 0.02, y - bh)], fade(SUMI, fog), density=0.85, jitter=0.6,
                feather=0.5, seed=seed + 70 + k)
    cv.line([(bx0, y - bh), (bx1 - L * 0.01, y - bh)], ink, width=lw,
            density=inkd * 0.8, seed=seed + 63)
    cv.line([(bx0, y - bh), (bx0 + L * 0.09, y + 1)], ink, width=lw,
            density=inkd * 0.9, seed=seed + 64)
    cv.gouache_line([(bx0 + L * 0.02, y + 2), (bx1 - L * 0.04, y + 2)],
                    (0.965, 0.96, 0.945), width=lw, alpha=0.7, jitter=1.2, seed=seed + 65)
    return hull_col


PAINTERS["tug"] = paint_tug
REFL_COL["tug"] = HULLDARK


def paint_cutter(cv, cx, y, L, seed, fog=0.4):
    """USCG cutter. White hull found by its cool shadowed lower strake and
    boot-top, and named by the racing stripe raked at 64 degrees: wide
    red-orange bar forward, thin white keep-line, narrow blue bar aft, top of
    the stripe leaning toward the bow. White house, black bridge glass, tall
    mast, orange RHIB on the quarter. Faces left."""
    Hh = L * 0.115
    x0, x1 = cx - L / 2, cx + L / 2
    lw = 2 if L > 240 else 1                             # line weight scales with hull
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    white = mix((0.97, 0.96, 0.935), FOGGREY, fog * 0.35)
    shade = mix((0.76, 0.79, 0.85), FOGGREY, fog * 0.4)
    deep = fade(mix((0.76, 0.79, 0.85), PAYNE, 0.45), fog * 0.6)
    # hull: raised forecastle stepping down to a flush working deck. The white
    # is bare paper; the cool shadow low on the flank + boot-top hold her.
    top_f, top_a = y - Hh * 1.55, y - Hh * 0.95
    xs = x0 + L * 0.24                                         # forecastle break
    lowflank = [(x0 + L * 0.03, y - Hh * 0.55), (x1 - L * 0.012, y - Hh * 0.50),
                (x1 - L * 0.02, y - Hh * 0.16), (x0 + L * 0.055, y - Hh * 0.16)]
    cv.wash(lowflank, deep, density=0.45, jitter=1.4, feather=2.0, edge_dark=0.12,
            granulation=0.3, variegation=0.4, seed=seed)
    # boot-topping: black band + a rust sliver at the waterline
    cv.wash([(x0 + L * 0.05, y - Hh * 0.16), (x1 - L * 0.012, y - Hh * 0.16),
             (x1 - L * 0.018, y + 1), (x0 + L * 0.06, y + 1)],
            fade(HULLDARK, fog * 0.6), density=0.95, jitter=1.0, feather=0.7,
            dry=0.1, seed=seed + 2)
    cv.line([(x0 + L * 0.056, y - 1), (x1 - L * 0.02, y - 1)], fade(VERMIL, fog),
            width=1, density=0.8, seed=seed + 3)
    # ---- the racing stripe: raked 64 deg, top toward the bow ----
    import math
    ang = math.radians(64)
    dxr = ((y - Hh * 0.16) - top_f) / math.tan(ang)         # top leans toward the bow
    sy0, sy1 = y - Hh * 0.16, top_f + Hh * 0.06
    bx = x0 + L * 0.13
    wr, wb, gapw = L * 0.06, L * 0.02, L * 0.012
    def _bar(x_bottom, w_, col, k):
        p = [(x_bottom, sy0), (x_bottom + w_, sy0),
             (x_bottom + w_ - dxr, sy1), (x_bottom - dxr, sy1)]
        cv.wash(p, col, density=0.9, jitter=0.7, feather=0.6, edge_dark=0.35, seed=seed + k)
    _bar(bx, wr, fade(mix(VERMIL, OCHRE, 0.18), fog * 0.5), 4)       # red-orange bar
    _bar(bx + wr + gapw, wb, fade(INDIGO, fog * 0.5), 5)              # narrow blue bar
    # deckhouse on the main deck: white block, black wraparound bridge glass
    hx0, hx1 = x0 + L * 0.27, x0 + L * 0.60
    hb = top_a                                                  # house sits on the main deck
    h1 = Hh * 0.90
    cv.wash([(hx0, hb - h1 * 0.45), (hx1, hb - h1 * 0.45), (hx1, hb), (hx0, hb)],
            deep, density=0.4, jitter=1.2, feather=1.6, edge_dark=0.12, seed=seed + 6)  # shaded flank
    wx0, wx1 = hx0 + L * 0.03, hx0 + L * 0.19
    h2 = Hh * 0.70
    wt = hb - h1
    cv.wash([(wx0, wt - h2 * 0.4), (wx1, wt - h2 * 0.4), (wx1, wt), (wx0, wt)],
            deep, density=0.35, jitter=1.0, feather=1.4, edge_dark=0.12, seed=seed + 8)
    cv.wash([(wx0 + 2, wt - h2 * 0.85), (wx1 - 2, wt - h2 * 0.85),
             (wx1 - 2, wt - h2 * 0.50), (wx0 + 2, wt - h2 * 0.50)],
            fade(INDIGO, fog), density=0.75, jitter=0.7, feather=0.5, seed=seed + 9)   # bridge glass
    cv.line([(hx0, hb), (hx0, hb - h1), (hx1, hb - h1), (hx1, hb)], ink, width=1,
            density=inkd * 0.5, seed=seed + 10)
    cv.line([(wx0, wt), (wx0, wt - h2), (wx1, wt - h2), (wx1, wt)], ink, width=1,
            density=inkd * 0.85, seed=seed + 11)
    # tall mast with a radar bar and yard, over the wheelhouse
    mx = wx1 + L * 0.04
    mtop = wt - h2 - Hh * 1.9
    cv.line([(mx, wt - h2 * 0.9), (mx, mtop)], ink, width=lw, density=inkd * 0.65, seed=seed + 12)
    cv.line([(mx - L * 0.045, mtop + Hh * 0.45), (mx + L * 0.045, mtop + Hh * 0.45)],
            ink, width=lw, density=inkd * 0.85, seed=seed + 13)      # radar bar
    cv.line([(mx - L * 0.07, mtop + Hh * 0.95), (mx + L * 0.07, mtop + Hh * 0.95)],
            ink, width=1, density=inkd * 0.7, seed=seed + 14)       # yardarm
    # RHIB in her davit on the quarter: the one warm accent
    rb = (x0 + L * 0.72, hb + Hh * 0.05)
    cv.wash([(rb[0] - L * 0.045, rb[1] - Hh * 0.30), (rb[0] + L * 0.045, rb[1] - Hh * 0.30),
             (rb[0] + L * 0.03, rb[1]), (rb[0] - L * 0.03, rb[1])],
            fade(mix(VERMIL, OCHRE, 0.4), fog * 0.4), density=0.9, jitter=0.7,
            feather=0.6, edge_dark=0.35, seed=seed + 15)
    # found edges: sheer line over the forecastle step, and the flared bow
    cv.line([(x0, top_f), (xs, top_f + Hh * 0.04), (xs + L * 0.012, top_a),
             (x1 - L * 0.01, top_a)], ink, width=lw, density=inkd * 0.5, seed=seed + 20)
    cv.line([(x0, top_f), (x0 + L * 0.055, y + 1)], ink, width=lw, density=inkd * 0.65, seed=seed + 21)
    return deep


PAINTERS["cutter"] = paint_cutter
REFL_COL["cutter"] = mix((0.76, 0.79, 0.85), PAYNE, 0.45)


def paint_general_cargo(cv, cx, y, L, seed, fog=0.4):
    """Geared general cargo / heavy-lift: the tweendecker that is neither box
    ship nor bulker. Dark hull, three tall mast-cranes (derricks), loose crated
    deck cargo and a couple of stray containers, accommodation aft."""
    Hh = L * 0.09
    x0, x1 = cx - L / 2, cx + L / 2
    hull_col = fade(HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull = [(x0, y - Hh), (x0 + L * 0.05, y - Hh * 0.15), (x0 + L * 0.07, y + 1),
            (x1 - L * 0.02, y + 1), (x1, y - Hh * 0.5), (x1 - L * 0.008, y - Hh)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.35, variegation=0.4, seed=seed)
    strake = [(x0 + L * 0.02, y - Hh + 3), (x1 - L * 0.015, y - Hh + 3),
              (x1 - L * 0.02, y - Hh + Hh * 0.42), (x0 + L * 0.04, y - Hh + Hh * 0.42)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.45)
    cv.wash([(x0 + L * 0.06, y - 4), (x1 - L * 0.005, y - 4),
             (x1 - L * 0.01, y + 1), (x0 + L * 0.075, y + 1)],
            fade(RUST, fog), density=0.5, jitter=1.4, feather=0.9, dry=0.15, seed=seed + 1)
    deck = y - Hh
    r = np.random.default_rng(seed + 2)
    cols = [RUST, TEAL, OCHRE, PAYNE]
    xk = x0 + L * 0.13                                    # loose deck cargo
    while xk < x1 - L * 0.26:
        wbox = r.uniform(L * 0.05, L * 0.09)
        hbox = Hh * r.uniform(0.35, 0.75)
        c = fade(mix(cols[int(r.integers(0, 4))], PAPER_RGB, 0.15), fog)
        crate = [(xk, deck), (xk, deck - hbox), (xk + wbox, deck - hbox), (xk + wbox, deck)]
        crisp = r.random() < 0.55
        cv.wash(crate, c, density=0.8, jitter=1.0 if crisp else 2.0,
                feather=0.7 if crisp else 1.8, edge_dark=0.45, granulation=0.3,
                seed=seed + 10 + int(xk))
        xk += wbox + r.uniform(L * 0.01, L * 0.04)
    crane = fade(mix(OCHRE, PAYNE, 0.35), fog * 0.6)     # three mast derricks
    for k in range(3):
        px = x0 + L * (0.18 + 0.20 * k)
        ph = Hh * 1.9
        cv.line([(px, deck), (px, deck - ph)], crane, width=3, density=0.9, seed=seed + 30 + k)
        cv.line([(px, deck), (px, deck - ph)], ink, width=1, density=inkd * 0.6, seed=seed + 33 + k)
        rake = 1 if k % 2 == 0 else -1
        b0, b1 = (px, deck - ph * 0.85), (px + rake * L * 0.11, deck - ph * 0.35)
        cv.line([b0, b1], crane, width=3, density=0.85, seed=seed + 36 + k)
        cv.line([b0, b1], ink, width=1, density=inkd * 0.6, seed=seed + 39 + k)
        cv.line([b1, (b1[0], b1[1] + Hh * 0.55)], ink, width=1, density=inkd * 0.6, seed=seed + 42 + k)
    sw, sx = L * 0.13, x1 - L * 0.19                      # aft house + funnel
    st = y - Hh - Hh * 2.1
    cv.wash([(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)],
            mix((0.9, 0.88, 0.84), FOGGREY, fog * 0.4), density=0.75, jitter=1.2,
            feather=0.9, edge_dark=0.4, granulation=0.3, seed=seed + 50)
    cv.wash([(sx + sw * 0.55, st), (sx + sw, st), (sx + sw, y - Hh), (sx + sw * 0.55, y - Hh)],
            fade(PAYNE, fog), density=0.35, jitter=1.2, feather=1.4, seed=seed + 51)
    cv.line([(sx + 3, st + Hh * 0.4), (sx + sw - 3, st + Hh * 0.4)], ink, width=1,
            density=inkd * 0.8, seed=seed + 52)
    cv.line([(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)], ink, width=1,
            density=inkd * 0.7, seed=seed + 53)
    fw, fx = sw * 0.34, sx + sw * 0.5
    cv.wash([(fx, st), (fx + fw * 0.15, st - Hh * 0.7), (fx + fw * 0.85, st - Hh * 0.7), (fx + fw, st)],
            fade(mix(TEAL, PAYNE, 0.5), fog), density=0.75, jitter=1, feather=0.8, seed=seed + 54)
    cv.wash([(fx, st - Hh * 0.75), (fx + fw, st - Hh * 0.8),
             (fx - fw * 3.5, st - Hh * 3.2), (fx - fw * 4.5, st - Hh * 2.4)],
            mix(PAYNE, FOGGREY, 0.5), density=0.11, jitter=8, feather=9, edge_dark=0.15,
            variegation=0.7, seed=seed + 55)
    cv.line([(x0, y - Hh), (x1 - L * 0.008, y - Hh)], ink, width=2, density=inkd * 0.85, seed=seed + 60)
    cv.line([(x0, y - Hh), (x0 + L * 0.05, y - Hh * 0.15), (x0 + L * 0.07, y + 1)],
            ink, width=2, density=inkd, seed=seed + 61)
    return hull_col


PAINTERS["general"] = paint_general_cargo
REFL_COL["general"] = HULLDARK


def paint_naval(cv, cx, y, L, seed, fog=0.4):
    """Warship (Arleigh-Burke-ish): long low haze-grey hull, flared knuckle
    bow, faceted slab superstructure amidships, tripod mast, gun on the
    foredeck, black boot-top. Grey on grey is the whole problem: she is drawn
    by her shadow planes and one committed dark waterline."""
    Hh = L * 0.085
    x0, x1 = cx - L / 2, cx + L / 2
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    grey = fade(mix((0.66, 0.69, 0.72), PAYNE, 0.3), fog * 0.5)     # haze grey
    dark = fade(mix((0.66, 0.69, 0.72), PAYNE, 0.65), fog * 0.5)    # shadow plane
    top_f, top_a = y - Hh * 1.55, y - Hh * 1.0
    hull = [(x0 + L * 0.06, y + 1), (x0, top_f), (x0 + L * 0.28, top_f + Hh * 0.08),
            (x0 + L * 0.42, top_a), (x1 - L * 0.01, top_a), (x1, y - Hh * 0.35),
            (x1 - L * 0.02, y + 1)]
    cv.wash(hull, grey, density=1.0, jitter=1.4, feather=1.0, edge_dark=0.55,
            granulation=0.35, variegation=0.45, seed=seed)
    cv.wash([(x0 + L * 0.05, y - Hh * 0.55), (x1 - L * 0.015, y - Hh * 0.45),
             (x1 - L * 0.02, y - 2), (x0 + L * 0.06, y - 2)], dark, density=0.7,
            jitter=1.4, feather=1.8, edge_dark=0.2, seed=seed + 1)
    cv.wash([(x0 + L * 0.055, y - Hh * 0.16), (x1 - L * 0.02, y - Hh * 0.16),
             (x1 - L * 0.024, y + 1), (x0 + L * 0.065, y + 1)],
            fade(HULLDARK, fog * 0.6), density=0.95, jitter=1.0, feather=0.7, dry=0.1, seed=seed + 2)
    b0x, b1x = x0 + L * 0.30, x0 + L * 0.62                       # faceted superstructure
    bh1 = Hh * 1.25
    blk = [(b0x, top_a - bh1), (b1x - L * 0.02, top_a - bh1), (b1x, top_a), (b0x - L * 0.02, top_a)]
    cv.wash(blk, grey, density=0.95, jitter=1.0, feather=0.8, edge_dark=0.5,
            granulation=0.3, seed=seed + 3)
    cv.wash([(b0x + L * 0.14, top_a - bh1), (b1x - L * 0.02, top_a - bh1),
             (b1x, top_a), (b0x + L * 0.16, top_a)], dark, density=0.55, jitter=1.0,
            feather=1.2, seed=seed + 4)                                # aft block in shade
    br = [(b0x + L * 0.03, top_a - bh1 - Hh * 0.7), (b0x + L * 0.16, top_a - bh1 - Hh * 0.7),
          (b0x + L * 0.18, top_a - bh1), (b0x + L * 0.01, top_a - bh1)]
    cv.wash(br, grey, density=0.9, jitter=0.9, feather=0.7, edge_dark=0.5, seed=seed + 5)
    cv.wash([(b0x + L * 0.045, top_a - bh1 - Hh * 0.55), (b0x + L * 0.15, top_a - bh1 - Hh * 0.55),
             (b0x + L * 0.16, top_a - bh1 - Hh * 0.30), (b0x + L * 0.05, top_a - bh1 - Hh * 0.30)],
            fade(SUMI, fog), density=0.7, jitter=0.8, feather=0.6, seed=seed + 6)   # bridge glass
    for e, pts in enumerate((blk + [blk[0]], br + [br[0]])):
        cv.line(pts, ink, width=1, density=inkd * 0.75, seed=seed + 7 + e)
    mx = b0x + L * 0.17                                            # tripod mast
    mb = top_a - bh1 - Hh * 0.7
    mt = mb - Hh * 2.4
    cv.line([(mx, mb), (mx + L * 0.02, mt)], ink, width=2, density=inkd, seed=seed + 20)
    cv.line([(mx + L * 0.06, mb), (mx + L * 0.02, mt)], ink, width=1, density=inkd * 0.7, seed=seed + 21)
    cv.line([(mx - L * 0.03, mt + Hh * 0.55), (mx + L * 0.075, mt + Hh * 0.45)],
            ink, width=2, density=inkd * 0.85, seed=seed + 22)
    cv.line([(mx + L * 0.02, mt), (mx + L * 0.02, mt - Hh * 0.5)], ink, width=1,
            density=inkd * 0.8, seed=seed + 23)
    gx = x0 + L * 0.20                                             # forward gun
    cv.wash([(gx - L * 0.03, top_f + Hh * 0.13), (gx - L * 0.02, top_f - Hh * 0.35),
             (gx + L * 0.025, top_f - Hh * 0.35), (gx + L * 0.035, top_f + Hh * 0.13)],
            dark, density=0.85, jitter=0.8, feather=0.7, edge_dark=0.4, seed=seed + 30)
    cv.line([(gx - L * 0.02, top_f - Hh * 0.2), (gx - L * 0.10, top_f - Hh * 0.55)],
            ink, width=2, density=inkd * 0.85, seed=seed + 31)
    for k in range(2):                                             # hull number
        nx = x0 + L * (0.09 + 0.02 * k)
        cv.line([(nx, y - Hh * 1.1), (nx, y - Hh * 0.75)], ink, width=2,
                density=inkd * 0.6, seed=seed + 40 + k)
    cv.line([(x0, top_f), (x0 + L * 0.28, top_f + Hh * 0.08), (x0 + L * 0.42, top_a),
             (x1 - L * 0.01, top_a)], ink, width=2, density=inkd * 0.8, seed=seed + 50)
    cv.line([(x0, top_f), (x0 + L * 0.06, y + 1)], ink, width=2, density=inkd, seed=seed + 51)
    return dark


PAINTERS["naval"] = paint_naval
REFL_COL["naval"] = mix((0.66, 0.69, 0.72), PAYNE, 0.55)


def paint_motoryacht(cv, cx, y, L, seed, fog=0.4):
    """Motor yacht: low white wedge, raked bow, a long black glazing sweep
    along the main deck, flybridge stepped back with a radar arch, swim
    platform aft. White = paper; the black glass and boot line carry her."""
    Hh = L * 0.13
    x0, x1 = cx - L / 2, cx + L / 2
    lw = 2 if L > 240 else 1                             # line weight scales with hull
    ink = fade(SUMI, fog)
    inkd = 0.8 * (1 - 0.45 * fog)
    deep = fade(mix((0.76, 0.79, 0.85), PAYNE, 0.5), fog * 0.6)
    top_f, top_a = y - Hh * 1.5, y - Hh * 0.9
    tint = [(x0, top_f), (x0 + L * 0.55, top_a), (x1 - L * 0.03, top_a + Hh * 0.15),
            (x1, y - Hh * 0.15), (x1 - L * 0.01, y + 1), (x0 + L * 0.03, y + 1)]
    cv.wash(tint, mix((0.95, 0.93, 0.88), FOGGREY, fog * 0.4), density=0.55, jitter=1.4,
            feather=1.4, edge_dark=0.25, granulation=0.3, variegation=0.4, seed=seed + 90)
    cv.wash([(x0 + L * 0.02, y - Hh * 0.5), (x1 - L * 0.01, y - Hh * 0.35),
             (x1 - L * 0.012, y - 2), (x0 + L * 0.04, y - 2)], deep, density=0.35,
            jitter=1.5, feather=2.2, edge_dark=0.1, granulation=0.3, seed=seed)   # soft flank
    cv.wash([(x0 + L * 0.035, y - Hh * 0.12), (x1 - L * 0.012, y - Hh * 0.12),
             (x1 - L * 0.016, y + 1), (x0 + L * 0.045, y + 1)],
            fade(INDIGO, fog * 0.6), density=0.85, jitter=1.0, feather=0.7, seed=seed + 1)  # boot
    hx0, hx1 = x0 + L * 0.16, x0 + L * 0.70
    ht = Hh * 0.85
    base = y - Hh * 0.95
    house = [(hx0 + L * 0.06, base - ht), (hx1 - L * 0.05, base - ht), (hx1, base), (hx0, base)]
    cv.wash([(hx0 + L * 0.05, base - ht * 0.35), (hx1 - L * 0.02, base - ht * 0.35),
             (hx1, base), (hx0 + L * 0.01, base)], deep, density=0.3, jitter=1.3,
            feather=1.8, edge_dark=0.1, seed=seed + 2)                   # under-lip shade
    glass = [(hx0 + L * 0.07, base - ht * 0.85), (hx1 - L * 0.06, base - ht * 0.85),
             (hx1 - L * 0.02, base - ht * 0.40), (hx0 + L * 0.03, base - ht * 0.40)]
    cv.wash(glass, fade(mix(INDIGO, SUMI, 0.4), fog * 0.6), density=0.8, jitter=0.9,
            feather=0.7, dry=0.15, edge_dark=0.35, seed=seed + 3)     # the black sweep
    cv.line(house + [house[0]], ink, width=1, density=inkd * 0.5, seed=seed + 4)
    fb0, fb1 = hx0 + L * 0.12, hx1 - L * 0.16                     # flybridge
    ft = base - ht
    fbt = ft - Hh * 0.55
    cv.wash([(fb0 + L * 0.04, fbt), (fb1, fbt), (fb1 + L * 0.02, ft), (fb0, ft)],
            deep, density=0.32, jitter=1.2, feather=1.6, edge_dark=0.12, seed=seed + 5)
    cv.line([(fb0, ft), (fb0 + L * 0.04, fbt), (fb1, fbt), (fb1 + L * 0.02, ft)],
            ink, width=1, density=inkd * 0.5, seed=seed + 6)
    ax = fb1 - L * 0.06                                            # radar arch
    cv.line([(ax, fbt), (ax + L * 0.02, fbt - Hh * 0.55), (ax + L * 0.06, fbt - Hh * 0.55),
             (ax + L * 0.08, fbt)], ink, width=lw, density=inkd * 0.5, seed=seed + 7)
    cv.line([(x0, top_f), (x0 + L * 0.55, top_a), (x1 - L * 0.03, top_a + Hh * 0.15)],
            ink, width=lw, density=inkd * 0.5, seed=seed + 10)
    cv.line([(x0, top_f), (x0 + L * 0.03, y + 1)], ink, width=lw, density=inkd * 0.65, seed=seed + 11)
    return deep


PAINTERS["motoryacht"] = paint_motoryacht
REFL_COL["motoryacht"] = mix((0.78, 0.80, 0.84), PAYNE, 0.45)


def paint_atb(cv, cx, y, L, seed, fog=0.4):
    """Articulated tug-barge (ATB): the coast's fuel run. AIS reports one
    ~180-200 m unit: a long low petroleum barge with a raked notched bow, and
    a tug locked into her stern notch pushing -- what you SEE of the tug is a
    tall stacked pilothouse tower and twin stacks rising above the barge's
    stern. Deck reads as a tanker: catwalk, manifold humps, no cranes."""
    Hh = L * 0.065                                       # barge rides low
    x0, x1 = cx - L / 2, cx + L / 2
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull_col = fade(mix(HULLDARK, RUST, 0.25), fog)
    # barge hull: raked bow, long straight sheer, blunt notched stern
    hull = [(x0 + L * 0.02, y - Hh), (x0 + L * 0.075, y + 1),
            (x1 - L * 0.09, y + 1), (x1 - L * 0.09, y - Hh)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.35, variegation=0.4, seed=seed)
    strake = [(x0 + L * 0.04, y - Hh + 2), (x1 - L * 0.10, y - Hh + 2),
              (x1 - L * 0.10, y - Hh + Hh * 0.45), (x0 + L * 0.055, y - Hh + Hh * 0.45)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.4)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.09, y - 3),
             (x1 - L * 0.095, y + 1), (x0 + L * 0.07, y + 1)],
            fade(VERMIL, fog), density=0.6, jitter=1.2, feather=0.9, dry=0.12, seed=seed + 1)
    # petroleum deck: raised trunk with catwalk on legs + manifold humps
    dtop = y - Hh - Hh * 0.45
    dx0, dx1 = x0 + L * 0.06, x1 - L * 0.13
    cv.wash([(dx0, y - Hh), (dx0, dtop), (dx1, dtop), (dx1, y - Hh)],
            fade(mix(RUST, PAYNE, 0.55), fog), density=0.75, jitter=1.2, feather=0.9,
            edge_dark=0.45, granulation=0.3, seed=seed + 2)
    cw_y = dtop - Hh * 0.42
    cv.line([(dx0 + L * 0.02, cw_y), (dx1 - L * 0.02, cw_y)], ink, width=1,
            density=inkd * 0.8, seed=seed + 3)
    xk = dx0 + L * 0.02
    while xk < dx1 - L * 0.02:
        cv.line([(xk, cw_y), (xk, dtop)], ink, width=1, density=inkd * 0.5,
                seed=seed + 100 + int(xk))
        xk += L * 0.05
    r = np.random.default_rng(seed + 4)
    for k in range(4):
        mx = dx0 + L * (0.10 + 0.14 * k) + r.uniform(-5, 5)
        wide = L * r.uniform(0.016, 0.028)
        tall = Hh * r.uniform(0.25, 0.45)
        cv.wash([(mx - wide, dtop + 2), (mx - wide * 0.7, dtop - tall),
                 (mx + wide * 0.7, dtop - tall), (mx + wide, dtop + 2)],
                fade(mix(PAYNE, RUST, 0.3), fog), density=0.85, jitter=1, feather=0.8,
                edge_dark=0.45, seed=seed + 30 + k)
    # the tug in the notch: hull hidden, tower + stacks rise above the stern
    tx0 = x1 - L * 0.115                                  # tug shoulders in the notch
    tw = L * 0.115
    tug_top = y - Hh * 0.9
    tug_body = [(tx0, y - Hh * 0.3), (tx0 + tw * 0.15, tug_top), (x1, tug_top),
                (x1, y + 1), (tx0 + tw * 0.1, y + 1)]
    cv.wash(tug_body, fade(HULLDARK, fog), density=1.0, jitter=1.4, feather=1.0,
            edge_dark=0.5, granulation=0.3, seed=seed + 40)   # tug's black shoulder
    # stacked pilothouse tower: three stepped decks, glass on top
    base = tug_top
    tiers = [(tw * 0.05, tw * 0.05, Hh * 0.75), (tw * 0.15, tw * 0.15, Hh * 0.7),
             (tw * 0.22, tw * 0.22, Hh * 0.65)]
    top = base
    deep = fade(mix((0.78, 0.81, 0.86), PAYNE, 0.5), fog * 0.6)
    for i, (li, ri, th) in enumerate(tiers):
        a, b = tx0 + li, x1 - ri
        cv.wash([(a, top - th * 0.45), (b, top - th * 0.45), (b, top), (a, top)],
                deep, density=0.42, jitter=1.2, feather=1.5, edge_dark=0.15, seed=seed + 50 + i)
        cv.line([(a, top), (a, top - th), (b, top - th), (b, top)], ink, width=1,
                density=inkd * 0.7, seed=seed + 55 + i)
        top -= th
    # pilothouse glass band on the top deck + a mast
    a, b = tx0 + tiers[-1][0], x1 - tiers[-1][1]
    th = tiers[-1][2]
    cv.wash([(a + 2, top + th * 0.15), (b - 2, top + th * 0.15),
             (b - 2, top + th * 0.5), (a + 2, top + th * 0.5)],
            fade(INDIGO, fog), density=0.7, jitter=0.7, feather=0.5, seed=seed + 60)
    mx = (a + b) / 2
    cv.line([(mx, top), (mx, top - Hh * 1.0)], ink, width=1, density=inkd * 0.8, seed=seed + 61)
    cv.line([(mx - L * 0.02, top - Hh * 0.65), (mx + L * 0.02, top - Hh * 0.65)],
            ink, width=1, density=inkd * 0.7, seed=seed + 62)
    # twin stacks just forward of the tower + exhaust
    for i in range(2):
        sxk = tx0 - L * 0.045 + i * L * 0.02
        cv.wash([(sxk, base), (sxk, base - Hh * 0.85), (sxk + L * 0.014, base - Hh * 0.85),
                 (sxk + L * 0.014, base)], fade(SUMI, fog), density=0.95, jitter=0.8,
                feather=0.7, edge_dark=0.4, seed=seed + 70 + i)
    cv.wash([(tx0 - L * 0.045, base - Hh * 0.9), (tx0 - L * 0.01, base - Hh * 0.95),
             (tx0 - L * 0.35, base - Hh * 3.2), (tx0 - L * 0.45, base - Hh * 2.5)],
            mix(PAYNE, FOGGREY, 0.5), density=0.11, jitter=8, feather=9, edge_dark=0.15,
            variegation=0.7, seed=seed + 75)
    # found edges: barge sheer and raked bow
    cv.line([(x0 + L * 0.02, y - Hh), (x1 - L * 0.09, y - Hh)], ink, width=2,
            density=inkd * 0.8, seed=seed + 80)
    cv.line([(x0 + L * 0.02, y - Hh), (x0 + L * 0.075, y + 1)], ink, width=2,
            density=inkd, seed=seed + 81)
    return hull_col


PAINTERS["atb"] = paint_atb
REFL_COL["atb"] = HULLDARK


def paint_workboat(cv, cx, y, L, seed, fog=0.4, livery=None):
    """Pilot boat, SAR launch, patrol or port tender: the tug's hull and house
    with nothing on the wire. The caption names what she really is."""
    return paint_tug(cv, cx, y, L, seed, fog=fog, livery=livery, tow=False)


PAINTERS["workboat"] = paint_workboat
REFL_COL["workboat"] = HULLDARK

# party boats, whale-watchers, small ferries: AIS calls them "passenger" like a
# liner; under 60 m the motor yacht's hull is the honest form
PAINTERS["excursion"] = paint_motoryacht
REFL_COL["excursion"] = REFL_COL["motoryacht"]


# =====================================================================
# Variety (Oct 15 2026). Seen one at a time on the wall the painters held up; seen
# side by side on the web every sloop was the same sloop. Two sources of difference:
#   WHAT THE RADIO AND THE BUOY KNOW (true): length picks the kind of boat, course
#   against the wind sets the sails, wind strength reefs them, speed lifts the bow.
#   HER OWN DICE (invented, but hers): what AIS never says, such as a yacht's hull
#   colour, is rolled from her MMSI. She looks the same every time she passes.
# Still APPEND-ONLY: new painters below, re-registered over the old names.
# =====================================================================
COMPASS = {n: i * 22.5 for i, n in enumerate(
    "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split())}
CLOTH_WHITE = (0.965, 0.955, 0.925)
YACHT_WHITE = (0.95, 0.94, 0.91)
YACHT_HULLS = [(5.0, YACHT_WHITE), (3.0, HULLDARK), (1.2, (0.13, 0.32, 0.25)), (1.0, (0.56, 0.14, 0.15)),
               (0.8, (0.11, 0.11, 0.13)), (1.0, (0.40, 0.58, 0.70))]
SAILCLOTH = [(7.0, CLOTH_WHITE), (2.0, (0.93, 0.89, 0.78)), (1.0, (0.62, 0.30, 0.22))]      # white, cream, tanbark
KITES = [VERMIL, (0.16, 0.32, 0.62), (0.90, 0.74, 0.25), (0.13, 0.45, 0.32), (0.62, 0.10, 0.55)]   # near the panel's own inks
CANVAS = [(0.16, 0.22, 0.38), (0.72, 0.62, 0.45), (0.60, 0.16, 0.15), (0.20, 0.36, 0.30)]


def _own(ship, salt=0):
    """A ship's own dice."""
    return np.random.default_rng((int((ship or {}).get("mmsi") or 0) * 2654435761 + salt) % (2 ** 32))


def _pick(r, options):
    w = np.array([o[0] for o in options], float)
    return options[int(r.choice(len(options), p=w / w.sum()))][1]


def wind_angle(ship, wx):
    """Degrees between her bow and where the wind blows FROM: 0 dead ahead, 180 dead
    astern. None when the buoy or the ship has not said."""
    d = COMPASS.get(str((wx or {}).get("wind_dir") or "").upper())
    h = (ship or {}).get("heading")
    return None if d is None or h is None else abs((d - h + 180.0) % 360.0 - 180.0)


def _bow(a, b, bulge, n=9):
    """Points from a to b along an arc that stands `bulge` px off the straight line."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1.0)
    return [tuple(a + d * t + nrm * bulge * 4 * t * (1 - t)) for t in np.linspace(0, 1, n)]


def yacht_hull_colour(ship, salt=0):
    return _pick(_own(ship, salt), YACHT_HULLS)


def _hull(cv, poly, col, fog, seed, boot=None, boot_poly=None):
    """A small-craft hull. White ones are opaque and found by their shaded underside;
    coloured ones are a full-strength wash."""
    if _is_white(col):
        cv.gouache(poly, mix(col, FOGGREY, fog * 0.35), alpha=0.95, jitter=1.3, feather=0.8, seed=seed)
        cv.wash(poly, fade(PAYNE, fog), density=0.20, jitter=1.5, feather=1.4, seed=seed + 1)
    else:
        cv.wash(poly, fade(col, fog), density=1.0, jitter=1.4, feather=1.0, edge_dark=0.5,
                granulation=0.3, variegation=0.35, seed=seed)
    if boot is not None and boot_poly is not None:
        cv.wash(boot_poly, fade(boot, fog), density=0.7, jitter=1.0, feather=0.8, seed=seed + 2)


def paint_sailboat2(cv, cx, y, L, seed, fog=0.4, ship=None, wx=None):
    """A sailing yacht doing what the wind and her course say she is doing."""
    ship = ship or {}
    r = _own(ship)
    length = float(ship.get("length_m") or 12)
    spd = float(ship.get("speed_kn") or 0)
    wind = float((wx or {}).get("wind_kn") or 8)
    twa = wind_angle(ship, wx)
    hullc, cloth = _pick(r, YACHT_HULLS), _pick(r, SAILCLOTH)
    k1, k2 = (KITES[i] for i in r.choice(len(KITES), 2, replace=False))
    canvas = CANVAS[int(r.integers(len(CANVAS)))]
    classic = r.random() < 0.35                                # overhangs and a counter, or plumb and open
    dice_rig, dice_frac, dice_dodger, dice_twa = r.random(), r.random(), r.random(), r.random()
    ketch = length >= 20 or (length >= 13 and dice_rig < 0.30)
    cutter = not ketch and length >= 11 and dice_rig > 0.65
    if twa is None:
        twa = 45 + 110 * dice_twa
    if spd < 0.7 or twa < 32 or (wind < 4 and spd > 2.5):
        mode = "bare"                                          # at rest, or motoring: nobody sails dead to windward
    else:
        mode = "beat" if twa < 65 else "reach" if twa < 135 else "run"
    reef = 0 if wind < 18 else 1 if wind < 27 else 2
    _NOTES["sail_mode"] = mode                                 # her lights at night depend on it
    ink, inkd = fade(SUMI, fog), 0.75 * (1 - 0.45 * fog)
    sail = mix(cloth, FOGGREY, fog * 0.45)
    lw = 2 if L > 240 else 1

    Hh = L * (0.095 + 0.02 * r.random())
    x0, x1 = cx - L / 2, cx + L / 2
    deck = y - Hh
    if classic:
        hull = [(x0, deck - Hh * 0.12), (x0 + L * 0.15, y + 1), (x1 - L * 0.17, y + 1), (x1, deck + Hh * 0.05)]
    else:
        hull = [(x0 + L * 0.02, deck - Hh * 0.05), (x0 + L * 0.06, y + 1), (x1 - L * 0.05, y + 1), (x1 - L * 0.01, deck + Hh * 0.08)]
    boot_poly = [(hull[1][0] - L * 0.03, y - 3 * S), (hull[2][0] + L * 0.03, y - 3 * S), hull[2], hull[1]]
    _hull(cv, hull, hullc, fog, seed, boot=VERMIL if _is_white(hullc) else YACHT_WHITE if r.random() < 0.5 else RUST,
          boot_poly=boot_poly)
    # coachroof, portlights, a canvas dodger
    c0, c1 = x0 + L * 0.33, x0 + L * 0.63
    cv.gouache([(c0, deck), (c0 + L * 0.03, deck - Hh * 0.38), (c1, deck - Hh * 0.38), (c1 + L * 0.02, deck)],
               mix(YACHT_WHITE, FOGGREY, fog * 0.35), alpha=0.92, jitter=0.8, feather=0.6, seed=seed + 3)
    for k in range(3 if length >= 10 else 2):
        px = c0 + L * (0.07 + 0.075 * k)
        cv.line([(px, deck - Hh * 0.20), (px + L * 0.03, deck - Hh * 0.20)], ink, width=lw, density=inkd * 0.8, seed=seed + 4 + k)
    if dice_dodger < 0.6:
        cv.wash([(c1 - L * 0.01, deck - Hh * 0.30), (c1 + L * 0.02, deck - Hh * 0.85), (c1 + L * 0.09, deck - Hh * 0.85),
                 (c1 + L * 0.10, deck - Hh * 0.05)], fade(canvas, fog), density=0.85, jitter=0.8, feather=0.7, seed=seed + 8)
    cv.line([hull[0], hull[3]], ink, width=lw, density=inkd * 0.75, seed=seed + 9)              # the sheer

    def rig(mx, height, foot, sd, headsails):
        """One mast and what it carries. Seen from abeam a sail sheeted hard in shows its whole
        area; eased right out on a run it turns edge-on."""
        mt = deck - height
        lean = math.radians(4.5) * min(1.0, wind / 20.0) * math.cos(math.radians(twa)) * (mode != "bare")
        def T(p):                                              # the whole rig leans off the wind
            dx, dy = p[0] - mx, p[1] - deck
            return (mx + dx * math.cos(lean) - dy * math.sin(lean), deck + dx * math.sin(lean) + dy * math.cos(lean))
        cv.line([T((mx, deck)), T((mx, mt))], ink, width=2 if L > 150 * S else 1, density=inkd, seed=sd)
        boom_y = deck - Hh * 0.75
        stem = (hull[0][0] + L * 0.01, hull[0][1])
        hound = mt + (height * 0.14 if dice_frac < 0.45 else 3 * S)         # fractional or masthead
        if headsails:
            cv.line([stem, T((mx, hound))], ink, width=1, density=inkd * 0.5, seed=sd + 1)      # forestay
            cv.line([T((mx, mt)), (hull[3][0] - L * 0.01, hull[3][1])], ink, width=1, density=inkd * 0.4, seed=sd + 2)
        if mode == "bare":
            cv.line([(mx, boom_y), (mx + foot, boom_y + Hh * 0.05)], fade(canvas, fog), width=4, density=0.85, seed=sd + 3)
            if headsails:
                a, b = np.array(stem), np.array(T((mx, hound)))
                cv.line([tuple(a + (b - a) * 0.06), tuple(a + (b - a) * 0.9)], fade(canvas, fog), width=2, density=0.7, seed=sd + 4)
            return
        show = {"beat": 1.0, "reach": 0.80, "run": 0.42}[mode]
        head = mt + 4 * S + (boom_y - mt) * (0.0, 0.20, 0.36)[reef]
        clew = (mx + foot * show, boom_y - Hh * 0.05)
        main = [T(p) for p in [(mx + 2 * S, boom_y)] + _bow((mx + 2 * S, head), clew, -foot * 0.10 * show) ]
        put = (lambda p, s_: cv.wash(p, sail, density=0.95, jitter=1.2, feather=0.9, edge_dark=0.4, seed=s_)) \
            if cloth[0] < 0.8 else (lambda p, s_: cv.gouache(p, sail, alpha=0.95, jitter=1.2, feather=0.9, seed=s_))
        put(main, sd + 5)
        cv.wash([T((mx + 2 * S, boom_y - (boom_y - head) * 0.42)), T((mx + foot * show * 0.62, boom_y - Hh * 0.05)), T((mx + 2 * S, boom_y))],
                FOGGREY if cloth[0] >= 0.8 else fade(SUMI, fog), density=0.22, jitter=2, feather=2.5, seed=sd + 6)
        cv.line(main + [main[0]], ink, width=1, density=inkd * 0.65, jitter=0.8, seed=sd + 7)
        cv.line([T((mx, boom_y)), T(clew)], ink, width=lw, density=inkd * 0.8, seed=sd + 8)     # boom
        for k in range(1, 3):                                   # batten seams
            t = k / 3.0
            a = (mx + 2 * S, boom_y + (head - boom_y) * t)
            cv.line([T(a), T((a[0] + foot * show * (1 - t) * 0.98, a[1] + Hh * 0.10))], ink, width=1, density=inkd * 0.22, seed=sd + 9 + k)
        if not headsails:
            return
        if mode == "run" and wind < 19 and reef == 0:           # the kite: three bands, head to foot
            # From abeam a kite is a fat D: the back edge hangs near the forestay, the front bellies out
            # ahead of the bow, fullest a little above half height, and tucks in again at the foot.
            hx, hy, fy = mx - 2 * S, hound + 4 * S, deck - Hh * 1.25
            def edge(t, side):
                back = hx + (mx - L * 0.13 - hx) * t + L * 0.03 * math.sin(math.pi * t)
                front = hx + (hull[0][0] + L * 0.02 - hx) * t - L * 0.27 * math.sin(math.pi * t ** 0.85) ** 0.9
                mid, half = (back + front) / 2, (back - front) / 2
                sag = Hh * 0.55 * (1 - side * side) * t ** 6            # the foot hangs in a curve
                return T((mid + side * half, hy + (fy - hy) * t + sag))
            for (t0, t1), col, sdd in (((0.0, 0.36), k1, 20), ((0.36, 0.68), CLOTH_WHITE, 21), ((0.68, 1.0), k2, 22)):
                ts = np.linspace(t0, t1, 7)
                band = [edge(t, -1) for t in ts] + [edge(t, 1) for t in ts[::-1]]
                cv.gouache(band, mix(col, FOGGREY, fog * 0.45), alpha=0.93, jitter=0.9, feather=0.8, seed=sd + sdd)
            ts = np.linspace(0, 1, 14)
            cv.line([edge(t, -1) for t in ts] + [edge(t, 1) for t in ts[::-1]], ink, width=1, density=inkd * 0.5, jitter=0.8, seed=sd + 23)
            cv.wash([edge(t, 0.15) for t in ts] + [edge(t, 1) for t in ts[::-1]], fade(PAYNE, fog), density=0.16, jitter=1.5,
                    feather=2.5, seed=sd + 24)
            return
        if reef == 2:
            return                                              # main alone in a gale
        top = np.array(stem) + (np.array((mx, hound)) - np.array(stem)) * (1.0, 0.72)[reef]
        over = (0.10 if dice_frac >= 0.45 else -0.03) * (reef == 0)         # a genoa overlaps the mast
        jclew = (mx + L * over * show - L * 0.03 - (1 - show) * L * 0.16, deck - Hh * 0.55)
        jib = [T(p) for p in [stem] + _bow(tuple(top), jclew, -L * 0.035) + _bow(jclew, stem, L * 0.012)[1:-1]]
        put(jib, sd + 30)
        cv.wash(jib, fade(PAYNE, fog), density=0.18, jitter=1.5, feather=2.0, edge_dark=0.4, seed=sd + 31)
        cv.line(jib + [jib[0]], ink, width=1, density=inkd * 0.6, jitter=0.8, seed=sd + 32)
        if cutter and reef == 0 and mode != "run":              # the inner staysail
            s0 = (stem[0] + L * 0.13, deck)
            st = [T(p) for p in [s0] + _bow((mx - 3 * S, mt + height * 0.34), (mx - L * 0.04, deck - Hh * 0.6), -L * 0.02)]
            put(st, sd + 33)
            cv.line(st + [st[0]], ink, width=1, density=inkd * 0.55, jitter=0.7, seed=sd + 34)

    tall = L * (0.80 + 0.10 * r.random()) * (0.92 if ketch else 1.0)
    mx = x0 + L * (0.36 if ketch else 0.41)
    rig(mx, tall, L * (0.34 if ketch else 0.42), seed + 20, True)
    if ketch:
        rig(x1 - L * 0.20, tall * 0.62, L * 0.19, seed + 70, False)
    if mode != "bare":                                          # the sails drop a pale shape into the water
        top = y + 8 * S
        cv.lift_mask(cv2.GaussianBlur(_polymask([(mx - L * 0.18, top), (mx + L * 0.30, top), (mx + L * 0.16, top + L * 0.30),
                                                 (mx - L * 0.06, top + L * 0.28)]), (0, 0), 4.0 * S) * cv._dry_keep(0.40), amount=0.30)
    return fade(hullc, fog)


def paint_motoryacht2(cv, cx, y, L, seed, fog=0.4, ship=None, wx=None):
    """'Pleasure craft' covers a 5 m skiff and a 60 m superyacht. Length picks the boat, her own
    dice pick among the kinds that size comes in, and speed sets her trim."""
    ship = ship or {}
    r = _own(ship, 1)
    length = float(ship.get("length_m") or 14)
    spd = float(ship.get("speed_kn") or 0)
    hullc = _pick(r, YACHT_HULLS if length >= 9 else YACHT_HULLS[:1] * 3 + YACHT_HULLS[1:])
    stripe = (INDIGO, VERMIL, (0.13, 0.32, 0.25), SUMI)[int(r.integers(4))]
    d = r.random()
    if length < 9:
        form = "console" if d < 0.6 else "cuddy"
    elif length < 19:
        form = "trawler" if (spd < 10 and d < 0.45) else "sportfish" if d < 0.75 else "express"
    elif length < 33:
        form = "flybridge"
    else:
        form = "superyacht"
    if form == "flybridge" and _is_white(hullc):
        return paint_motoryacht(cv, cx, y, L, seed, fog=fog)    # the original drawing is exactly this boat
    ink, inkd = fade(SUMI, fog), 0.8 * (1 - 0.45 * fog)
    lw = 2 if L > 240 else 1
    white = mix(YACHT_WHITE, FOGGREY, fog * 0.35)
    deep = fade(mix((0.76, 0.79, 0.85), PAYNE, 0.5), fog * 0.6)
    glassc = fade(mix(INDIGO, SUMI, 0.4), fog * 0.6)
    Hh = L * {"console": 0.105, "cuddy": 0.12, "trawler": 0.15, "sportfish": 0.125, "express": 0.11,
              "flybridge": 0.13, "superyacht": 0.075}[form]
    x0, x1 = cx - L / 2, cx + L / 2
    planing = spd > 13 and form not in ("trawler", "superyacht")
    trim = math.radians(3.2 if planing else 0.0)

    def P(u, v):
        """u: 0 at the stem, 1 at the transom. v: freeboards above the water. Planing lifts the bow."""
        dx, dy = (x0 + u * L) - x1, -v * Hh
        return (x1 + dx * math.cos(trim) - dy * math.sin(trim), y + dy * math.cos(trim) + dx * math.sin(trim))

    def Q(*uv):
        return [P(u, v) for u, v in uv]

    def house(pts, sd, shade=True):
        cv.gouache(pts, white, alpha=0.93, jitter=0.8, feather=0.6, seed=seed + sd)
        if shade:
            lo = min(p[1] for p in pts); hi = max(p[1] for p in pts)
            cv.wash([(p[0], max(p[1], lo + (hi - lo) * 0.55)) for p in pts], deep, density=0.30, jitter=1.1, feather=1.5,
                    edge_dark=0.1, seed=seed + sd + 1)
        cv.line(pts + [pts[0]], ink, width=1, density=inkd * 0.55, seed=seed + sd + 2)

    def glass(pts, sd):
        cv.wash(pts, glassc, density=0.85, jitter=0.7, feather=0.6, dry=0.12, edge_dark=0.3, seed=seed + sd)

    shapes = {
        "console":    ((0, 1.25), (0.05, 0.35), (0.15, -0.02), (0.98, -0.02), (1.0, 0.80), (0.55, 0.88)),
        "cuddy":      ((0, 1.35), (0.05, 0.35), (0.14, -0.02), (0.98, -0.02), (1.0, 0.85), (0.50, 1.0)),
        "trawler":    ((0.01, 1.45), (0.03, 0.4), (0.09, -0.02), (0.96, -0.02), (1.0, 0.95), (0.55, 1.0), (0.25, 1.18)),
        "sportfish":  ((0, 1.65), (0.06, 0.4), (0.16, -0.02), (0.98, -0.02), (1.0, 0.62), (0.62, 0.70), (0.40, 1.15)),
        "express":    ((0, 1.35), (0.07, 0.35), (0.17, -0.02), (0.97, -0.02), (1.0, 0.70), (0.55, 1.0)),
        "flybridge":  ((0, 1.5), (0.03, 0.3), (0.06, -0.02), (0.99, -0.02), (1.0, 0.15), (0.97, 0.75), (0.55, 0.9)),
        "superyacht": ((0, 1.75), (0.05, 0.5), (0.10, -0.02), (0.97, -0.02), (1.0, 0.55), (0.93, 1.0), (0.45, 1.15)),
    }[form]
    hull = Q(*shapes)
    _hull(cv, hull, hullc, fog, seed + 90, boot=stripe,
          boot_poly=Q((shapes[2][0] - 0.05, 0.16), (0.985, 0.16), (0.98, -0.02), shapes[2]))
    cv.line([hull[0]] + hull[:3:-1], ink, width=lw, density=inkd * 0.6, seed=seed + 10)         # sheer
    cv.line(hull[:3], ink, width=lw, density=inkd * 0.7, seed=seed + 11)                        # stem

    if form == "console":
        house(Q((0.47, 0.85), (0.49, 1.75), (0.57, 1.75), (0.59, 0.85)), 20, shade=False)
        glass(Q((0.46, 1.75), (0.44, 2.25), (0.47, 2.25), (0.52, 1.75)), 24)
        for u in (0.44, 0.62):
            cv.line(Q((u, 0.88), (u + 0.01, 2.95)), ink, width=1, density=inkd * 0.8, seed=seed + 25 + int(u * 100))
        cv.line(Q((0.38, 2.98), (0.69, 2.92)), fade(stripe, fog), width=3, density=0.9, seed=seed + 27)      # T-top
        cv.line(Q((0.60, 0.9), (0.605, 2.05)), ink, width=2, density=inkd * 0.9, seed=seed + 28)             # someone at the helm
        cv.wash(Q((0.99, 1.35), (1.045, 1.35), (1.05, 0.25), (1.0, 0.25)), fade(SUMI, fog), density=0.9, jitter=0.6, feather=0.5, seed=seed + 29)
    elif form == "cuddy":
        house(Q((0.20, 1.18), (0.34, 1.75), (0.52, 1.75), (0.55, 1.0)), 20)
        glass(Q((0.34, 1.75), (0.42, 2.35), (0.46, 2.35), (0.52, 1.75)), 24)
        cv.line(Q((0.46, 2.35), (0.72, 2.30), (0.73, 0.95)), fade(CANVAS[int(r.integers(4))], fog), width=2, density=0.85, seed=seed + 25)
        cv.wash(Q((0.99, 1.3), (1.04, 1.3), (1.045, 0.25), (1.0, 0.25)), fade(SUMI, fog), density=0.9, jitter=0.6, feather=0.5, seed=seed + 29)
    elif form == "trawler":
        house(Q((0.24, 1.15), (0.24, 2.05), (0.80, 2.05), (0.82, 1.0)), 20)
        for k in range(4):
            glass(Q((0.46 + 0.085 * k, 1.85), (0.515 + 0.085 * k, 1.85), (0.515 + 0.085 * k, 1.45), (0.46 + 0.085 * k, 1.45)), 30 + k)
        house(Q((0.25, 2.05), (0.22, 3.0), (0.44, 3.0), (0.45, 2.05)), 24)                       # pilothouse, windows raked forward
        glass(Q((0.225, 2.9), (0.435, 2.9), (0.44, 2.45), (0.235, 2.45)), 36)
        cv.line(Q((0.55, 2.05), (0.56, 4.3)), ink, width=lw, density=inkd, seed=seed + 37)       # mast and steadying boom
        cv.line(Q((0.56, 3.9), (0.80, 2.5)), ink, width=1, density=inkd * 0.8, seed=seed + 38)
        cv.wash(Q((0.62, 2.08), (0.63, 2.42), (0.78, 2.42), (0.79, 2.08)), fade(mix(VERMIL, OCHRE, 0.4), fog * 0.5), density=0.85,
                jitter=0.6, feather=0.5, seed=seed + 39)                                         # the dinghy on the boat deck
    elif form == "sportfish":
        house(Q((0.30, 1.28), (0.38, 2.0), (0.64, 2.0), (0.66, 0.72)), 20)
        glass(Q((0.335, 1.55), (0.385, 1.93), (0.60, 1.93), (0.60, 1.55)), 24)
        house(Q((0.42, 2.0), (0.44, 2.6), (0.62, 2.6), (0.63, 2.0)), 26, shade=False)            # flybridge
        for u in (0.45, 0.60):                                                                   # tuna tower
            cv.line(Q((u, 2.6), (0.5 + (u - 0.525) * 0.5, 4.5)), ink, width=1, density=inkd * 0.85, seed=seed + 30 + int(u * 100))
        cv.line(Q((0.455, 3.5), (0.595, 3.5)), ink, width=1, density=inkd * 0.7, seed=seed + 33)
        cv.line(Q((0.44, 4.5), (0.59, 4.5)), ink, width=2, density=inkd, seed=seed + 34)
        cv.line(Q((0.60, 2.0), (0.93, 4.6)), ink, width=1, density=inkd * 0.6, seed=seed + 35)   # outrigger, raked aft
    elif form == "express":
        house(Q((0.22, 1.2), (0.40, 1.85), (0.66, 1.80), (0.72, 0.95)), 20)
        glass(Q((0.27, 1.32), (0.41, 1.78), (0.60, 1.74), (0.62, 1.32)), 24)
        cv.line(Q((0.60, 1.8), (0.63, 2.5), (0.70, 2.5), (0.74, 0.95)), ink, width=lw, density=inkd * 0.7, seed=seed + 26)     # arch
    elif form == "flybridge":
        house(Q((0.22, 0.98), (0.30, 1.85), (0.68, 1.85), (0.74, 0.85)), 20)
        glass(Q((0.27, 1.25), (0.325, 1.75), (0.655, 1.75), (0.69, 1.25)), 24)
        house(Q((0.36, 1.85), (0.40, 2.4), (0.60, 2.4), (0.62, 1.85)), 26, shade=False)
        cv.line(Q((0.54, 2.4), (0.56, 2.95), (0.60, 2.95), (0.62, 2.4)), ink, width=lw, density=inkd * 0.6, seed=seed + 28)
    else:                                                                                        # superyacht
        for i, (a, b, v0, v1) in enumerate(((0.24, 0.90, 1.05, 1.95), (0.32, 0.80, 1.95, 2.75), (0.40, 0.66, 2.75, 3.45))):
            house(Q((a - 0.03, v0), (a + 0.03, v1), (b - 0.02, v1), (b, v0)), 20 + i * 6)
            glass(Q((a + 0.015, v0 + (v1 - v0) * 0.30), (a + 0.04, v1 - (v1 - v0) * 0.18), (b - 0.06, v1 - (v1 - v0) * 0.18),
                    (b - 0.05, v0 + (v1 - v0) * 0.30)), 23 + i * 6)
        cv.line(Q((0.53, 3.45), (0.55, 4.5)), ink, width=lw, density=inkd, seed=seed + 40)
        cv.gouache(Q((0.50, 4.0), (0.50, 4.35), (0.545, 4.35), (0.545, 4.0)), white, alpha=0.95, jitter=0.4, feather=0.4, seed=seed + 41)
        cv.line(Q((0.50, 4.0), (0.50, 4.35), (0.545, 4.35)), ink, width=1, density=inkd * 0.6, seed=seed + 42)
    if planing:                                                 # she is throwing water from amidships aft
        cv.gouache_line(Q((0.38, 0.10), (0.62, 0.34), (0.98, 0.16)), (0.975, 0.97, 0.955), width=3, alpha=0.85, jitter=1.2, seed=seed + 50)
    return fade(hullc if not _is_white(hullc) else mix((0.78, 0.80, 0.84), PAYNE, 0.45), fog)


import math
PAINTERS["sailing"] = paint_sailboat2
PAINTERS["motoryacht"] = paint_motoryacht2
PAINTERS["excursion"] = paint_motoryacht2
# the reflection is laid before the ship, so it has to know her colour too
HULL_OF = {"sailing": lambda s: yacht_hull_colour(s, 0),
           "motoryacht": lambda s: _pick(_own(s, 1), YACHT_HULLS if float(s.get("length_m") or 14) >= 9 else YACHT_HULLS[:1] * 3 + YACHT_HULLS[1:])}
HULL_OF["excursion"] = HULL_OF["motoryacht"]


# =====================================================================
# Night (Oct 15 2026). The frame paints round the clock now, and "night" used to be a grey
# afternoon: same sky every time, no dark, no moon, no lights. A nocturne is painted the way a
# watercolourist does it: the picture is finished in ordinary values, then one deep indigo glaze
# goes over everything, so the ship sinks to a silhouette. What shows after dark goes on top in
# body colour, and all of it is TRUE for the hour:
#   the moon     real phase, real bearing and height (light.moon); in the picture only when it
#                really hangs over the sea, otherwise it just lightens or darkens the night
#   her lights   what the collision regulations make her show to someone on OUR side of her
#   her windows  where her own painted house stands (found from the paint, so every painter works)
# Only scenes whose light carries a "moon" entry (light.for_iso after sunset) come here: the fixed
# test scenes in fleet.py do not, and render as before.
# =====================================================================
NOCTURNE = (0.10, 0.14, 0.30)
MOONPALE = (0.97, 0.95, 0.86)
LAMP_WHITE = (1.0, 0.97, 0.86)
LAMP_RED = (0.93, 0.12, 0.10)
LAMP_GREEN = (0.10, 0.72, 0.36)
WINDOW = (0.99, 0.84, 0.42)
_NOTES = {}                                   # what a painter decided, for whoever paints after it


def moon_of(lt):
    """The moon entry of a light, made safe: it may come back out of a saved file. Anything that is not four
    finite numbers means no moon, and the night is simply dark."""
    mn = (lt or {}).get("moon")
    if not isinstance(mn, dict):
        return None
    try:
        v = [float(mn.get("alt", -90)), float(mn.get("az", 0)), float(mn.get("fraction", 0)), float(mn.get("limb", 270))]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in v):
        return None
    return dict(alt=max(-90.0, min(90.0, v[0])), az=v[1] % 360.0, fraction=max(0.0, min(1.0, v[2])), limb=v[3] % 360.0)


def moonlight(lt):
    """0 = no moon in the sky, 1 = full moon riding high."""
    mn = moon_of(lt)
    if not mn or mn["alt"] <= 0:
        return 0.0
    return mn["fraction"] * min(1.0, math.sin(math.radians(mn["alt"])) * 1.6) ** 0.5


def _put(cv, x, y, col, core, halo, a_core=1.0, a_halo=0.45, keep=None, squash=1.0):
    """A point of light: a hard core and a soft halo, blended in a small window of the sheet.
    squash > 1 flattens the halo into a low wide loom."""
    R = int(max(core, halo) * 3) + 2
    xa, xb, ya, yb = max(0, int(x) - R), min(W, int(x) + R + 1), max(0, int(y) - R), min(H, int(y) + R + 1)
    if xa >= xb or ya >= yb:
        return
    yy, xx = np.mgrid[ya:yb, xa:xb].astype(np.float32)
    d2 = (xx - x) ** 2 + ((yy - y) * squash) ** 2
    a = np.maximum(a_halo * np.exp(-d2 / max(halo, 0.1) ** 2), a_core * np.clip(core + 0.5 - np.sqrt(d2), 0, 1))
    if keep is not None:
        a = a * keep[ya:yb, xa:xb]
    a = a[..., None]
    cv.img[ya:yb, xa:xb] = cv.img[ya:yb, xa:xb] * (1 - a) + np.asarray(col, np.float32) * a


def _streak(cv, x, y, col, r, fog, strength, length=1.0):
    """A light's broken reflection, hanging straight down under it in the water."""
    n = int(6 * length) + 2
    for k in range(n):
        t = k / float(n)
        yy = y + (5 + 46 * length * t ** 1.2) * S + r.uniform(-1.5, 1.5) * S
        w = (2.2 + 5.0 * t) * S
        xa, xb = int(x - w + r.uniform(-2, 2) * S), int(x + w + r.uniform(-2, 2) * S)
        ya, yb = int(yy), int(yy + max(1.0, 1.4 * S))
        xa, xb, ya, yb = max(0, xa), min(W, xb), max(0, ya), min(H, yb)
        if xa < xb and ya < yb and r.random() < min(0.9, strength * (0.80 - 0.62 * t) * (1 - 0.5 * fog)):
            a = 0.93 - 0.35 * fog                      # on or off, never half: half a yellow over blue prints green on six inks
            cv.img[ya:yb, xa:xb] = cv.img[ya:yb, xa:xb] * (1 - a) + np.asarray(col, np.float32) * a


def nocturne_glaze(cv, lt, fog, twilight=False):
    """The dark. Deepest overhead and in the near water, thinner along the horizon; a high bright
    moon thins it, fog flattens it. In twilight (dusk, predawn) it is the blue hour: the zenith has
    gone dark but the afterglow still lies along the sea."""
    ml = moonlight(lt)
    yy = np.arange(H, dtype=np.float32)
    if twilight:
        sky = np.interp(yy, [0, HORIZON * 0.45, HORIZON * 0.85, HORIZON], [1.0, 0.86, 0.40, 0.30])
        sea = np.interp(yy, [HORIZON, HORIZON + (H - HORIZON) * 0.35, H], [0.36, 0.78, 1.05])
    else:
        sky = np.interp(yy, [0, HORIZON * 0.55, HORIZON], [1.0, 0.90, 0.72])
        sea = np.interp(yy, [HORIZON, HORIZON + (H - HORIZON) * 0.4, H], [0.74, 0.92, 1.06])
    prof = np.where(yy < HORIZON, sky, sea)
    prof = prof * (1 - 0.35 * fog) + 0.86 * 0.35 * fog
    dens = (0.46 if twilight else 0.58 - 0.20 * ml) * (1 - 0.10 * fog)
    cv.mask_wash(np.repeat(prof[:, None], W, axis=1).astype(np.float32), NOCTURNE, density=dens)


def paint_moon_and_stars(cv, lt, fog, seed, flip, shipmask, twilight=False):
    mn = moon_of(lt) or dict(alt=-90.0, az=0.0, fraction=0.0, limb=270.0)
    r = np.random.default_rng(seed + 900)
    ml = moonlight(lt)
    keep = 1.0 - shipmask
    off = ((mn["az"] - config.SEA_BEARING + 180.0) % 360.0) - 180.0                    # right of centre = positive
    alt = mn["alt"]
    seen = alt > 1.5 and abs(off) <= 52 and alt <= 50 and mn["fraction"] > 0.015
    if fog < 0.36:                                     # stars: clear nights only, fewest under a bright moon, the first few at twilight
        for _ in range(int(150 * (0.12 if twilight else 1.0) * (1 - 0.8 * ml) * (1 - fog / 0.36))):
            sx, sy = r.uniform(0, W), r.uniform(4 * S, HORIZON - 46 * S)
            if (sx < 345 * S and sy < 128 * S) or (sx > W - 260 * S and sy < 86 * S) or (W - sx < 345 * S and sy < 128 * S) or (W - sx > W - 260 * S and sy < 86 * S):
                continue                               # not behind the caption, whichever way the sheet ends up
            b = r.uniform(0.35, 1.0) * (1 - sy / HORIZON * 0.55)
            _put(cv, sx, sy, MOONPALE, 0.55 * S + 0.6 * S * (b > 0.8), 1.6 * S, a_core=min(1.0, 1.15 * b), a_halo=0.16 * b, keep=keep)
    if not seen:
        return
    # a painting's field of view: 104 degrees of bearing across the sheet, 50 of height up to the caption's foot
    mx = W * (0.5 + off / 104.0 * 0.80)
    my = HORIZON - (24 + (alt / 50.0) ** 0.8 * 92) * S
    limb = math.radians(mn["limb"])
    ux, uy = -math.sin(limb), -math.cos(limb)          # the way the bright edge faces, on the sheet
    if flip:                                           # the sheet is mirrored at the end: paint it where it will land right
        mx, ux = W - mx, -ux
    R = 15.0 * S
    # She is drawn mid-sheet whatever her true bearing, so moon-behind-ship is an accident of the layout, not
    # a fact. Slide the moon along to the nearer clear sky.
    band = shipmask[max(0, int(my - R)):min(H, int(my + R)), :].max(axis=0) > 0.3
    if band[max(0, int(mx - 1.5 * R)):min(W, int(mx + 1.5 * R))].any():
        xs = np.where(band)[0]
        left, right = xs.min() - 2.6 * R, xs.max() + 2.6 * R
        ok = [c for c in (left, right) if 0.06 * W < c < 0.94 * W]
        if ok:
            mx = min(ok, key=lambda c: abs(c - mx))
    k = mn["fraction"]
    veil = 1 - 0.55 * fog
    low = float(np.clip(1 - alt / 14.0, 0, 1))         # near the horizon she goes amber through the thick air
    col = mix(MOONPALE, (0.96, 0.72, 0.42), 0.75 * low)
    _put(cv, mx, my, col, 0, R * (2.6 + 3.5 * fog), a_core=0, a_halo=(0.10 + 0.22 * k) * veil, keep=keep)      # the glow round her
    P = int(R) + 3
    xa, xb, ya, yb = max(0, int(mx) - P), min(W, int(mx) + P + 1), max(0, int(my) - P), min(H, int(my) + P + 1)
    yy, xx = np.mgrid[ya:yb, xa:xb].astype(np.float32)
    u, v = (xx - mx) / R, (yy - my) / R
    a_ = u * ux + v * uy                               # along the bright edge's direction
    b_ = -u * uy + v * ux
    disc = np.clip((1.0 - np.sqrt(u * u + v * v)) * R / (0.9 * S), 0, 1)
    lit = np.clip((a_ - (1 - 2 * k) * np.sqrt(np.clip(1 - b_ * b_, 0, 1))) * R / (0.9 * S) + 0.5, 0, 1)
    mare = 1 - 0.10 * np.clip(np.sin(u * 3.1 + 1.0) * np.cos(v * 2.6 - 0.4) + 0.2, 0, 1)                        # a hint of her seas
    a = (disc * (lit * 0.96 + (1 - lit) * 0.07) * veil * keep[ya:yb, xa:xb])[..., None]
    cv.img[ya:yb, xa:xb] = cv.img[ya:yb, xa:xb] * (1 - a) + (np.asarray(col, np.float32)[None, None, :] * mare[..., None]) * a
    # her path on the water: broken flakes, narrow at the horizon, widening toward us
    g = k ** 0.7 * (1 - 0.75 * fog) * min(1.0, 0.45 + alt / 30.0)
    for i in range(int(70 * g)):
        t = r.uniform(0, 1) ** 1.25
        py = HORIZON + (5 + t * (H - HORIZON - 30 * S) / S) * S
        spread = (7 + 52 * t) * S * (0.7 + alt / 60.0)
        px = mx + r.normal(0, spread * 0.5)
        w = (3 + 15 * t) * S * r.uniform(0.5, 1.2)
        xa, xb, ya, yb = max(0, int(px - w)), min(W, int(px + w)), int(py), min(H, int(py + max(1, (1.0 + 1.3 * t) * S)))
        if xa < xb and ya < yb:
            al = (0.55 - 0.25 * t) * g * keep[ya:yb, xa:xb][..., None]
            cv.img[ya:yb, xa:xb] = cv.img[ya:yb, xa:xb] * (1 - al) + np.asarray(col, np.float32) * al


# how much of her length the lit house may take up, and how many of its windows are lit
_HOUSE = {"container": (0.075, 0.55), "bulk": (0.085, 0.55), "tanker": (0.10, 0.55), "general": (0.10, 0.55),
          "carcarrier": (0.12, 0.35), "cruise": (1.0, 0.82), "motoryacht": (0.55, 0.60), "excursion": (0.7, 0.7),
          "research": (0.40, 0.55), "cutter": (0.32, 0.40), "naval": (0.30, 0.15), "tug": (0.40, 0.5), "atb": (0.40, 0.5),
          "fishing": (0.28, 0.6), "workboat": (0.35, 0.5), "sailing": (0.0, 0.0)}


def paint_lights(cv, before, after, ship, wx, cx, y, L, seed, fog, flip, strength=1.0):
    """Navigation lights, as the collision regulations have her show them to a watcher abeam, and
    the windows of her house. Positions come from her own paint: the difference between the sheet
    before and after her painter ran is her shape."""
    r = np.random.default_rng(seed + 950)
    typ = ship.get("type", "")
    length = float(ship.get("length_m") or 60)
    spd = float(ship.get("speed_kn") or 0)
    status = (ship.get("ais") or {}).get("status")
    x0, x1, yw = int(cx - L / 2), int(cx + L / 2), int(y)
    xa, xb = max(0, x0 - 2), min(W, x1 + 3)
    if xb - xa < 8:
        return
    fine = (np.abs(after - before).max(axis=2) > 0.05)
    fine[max(0, yw - 1):, :] = False
    fine[:, :xa] = False; fine[:, xb:] = False
    kk = max(3, int(0.016 * L)) | 1
    bulk = cv2.morphologyEx(fine.astype(np.uint8), cv2.MORPH_OPEN, np.ones((kk, kk), np.uint8)) > 0     # masts, stays and smoke wisps drop out
    cols = np.arange(xa, xb)
    top = lambda m: np.where(m[:, xa:xb].any(axis=0), m[:, xa:xb].argmax(axis=0), yw).astype(np.float32)
    tb, tf = top(bulk), top(fine)
    if (tb < yw - 2).sum() < 6:
        return
    deck = float(np.percentile(tb[tb < yw - 2], 62))                   # most of her length is deck or cargo at about this height
    core, halo = 2.3 * S, (5.5 + 9.0 * fog) * S
    seen_side = LAMP_GREEN if flip else LAMP_RED                       # sailing to our right shows us her starboard side

    def lamp(x, yy, col, big=1.0, streak=1.0):
        _put(cv, x, yy, col, core * big, halo * big, a_core=min(1.0, strength * (1 - 0.30 * fog)), a_halo=0.52 * strength)
        if streak:
            _streak(cv, x, y, col, r, fog, strength * 0.9, length=streak)

    def peak(f0, f1, m=tf):                                            # highest painted point between two fractions of her length
        i0, i1 = int((x0 + f0 * L) - xa), int((x0 + f1 * L) - xa)
        i0, i1 = max(0, i0), min(len(cols), max(i1, i0 + 1))
        j = i0 + int(np.argmin(m[i0:i1]))
        return float(cols[j]), float(m[j])

    # ---- windows: the tall block round her highest solid point
    wfrac, plit = _HOUSE.get(typ, (0.10, 0.5))
    hx, hy = peak(0.02, 0.98, tb)
    solid = cv2.morphologyEx(bulk.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((int(7 * S) | 1, int(7 * S) | 1), np.uint8)) > 0
    run0 = run1 = None
    if wfrac >= 0.25:                                                  # not a box boat: cranes, gallows and masts stand taller than the house
        up = tb < deck - 4 * S
        best, i = 0, 0
        while i < len(up):
            if up[i]:
                j = i
                while j + 1 < len(up) and up[j + 1]: j += 1
                if j - i > best: best, run0, run1 = j - i, i, j
                i = j + 1
            else:
                i += 1
        if run0 is not None and best > 0.06 * L:
            seg = np.sort(tb[run0:run1 + 1])
            hy = float(seg[int(len(seg) * 0.25)])                      # her roof line, ignoring a mast standing on it
            hx = float(cols[(run0 + run1) // 2])
        else:
            run0 = run1 = None
    if wfrac > 0 and hy < deck - 5 * S:
        tall = tb < deck - 3.5 * S if wfrac >= 0.3 else tb < (hy + (deck - hy) * 0.55)
        lo = hi = int(hx - xa)
        while lo > 0 and tall[lo - 1] and (hi - lo) < wfrac * L: lo -= 1
        while hi < len(cols) - 1 and tall[hi + 1] and (hi - lo) < wfrac * L: hi += 1
        if run0 is not None:
            lo, hi = run0, run1
        if wfrac >= 0.99:
            lo, hi = 0, len(cols) - 1
        sx, sy = (5.2 if typ == "cruise" else 5.8) * S, (6.4 if typ == "cruise" else 7.0) * S
        gy = hy + 4.5 * S
        while gy < (deck + 2 * S if typ != "cruise" else yw - 9 * S):
            if solid[int(gy), cols[lo]:cols[hi] + 1].mean() < (0.30 if wfrac >= 0.3 else 0.5):
                gy += sy; continue
            gx = cols[lo] + 2.5 * S + r.uniform(0, 2) * S
            while gx < cols[hi] - 2 * S:
                i = int(gx - xa)
                if solid[int(gy), int(gx)] and gy > tb[i] + 2.5 * S and r.random() < plit:
                    w_, h_ = int(round(max(2, 2.6 * S))), int(round(max(2, 2.2 * S)))
                    a = 0.97 * strength * (1 - 0.40 * fog)
                    sl = (slice(int(gy), int(gy) + h_), slice(int(gx), int(gx) + w_))
                    cv.img[sl] = cv.img[sl] * (1 - a) + np.asarray(WINDOW, np.float32) * a
                gx += sx
            gy += sy
        glow = {"cruise": 0.20, "excursion": 0.16, "motoryacht": 0.12}.get(typ, 0.06) * strength       # the loom of a lit ship
        _put(cv, (cols[lo] + cols[hi]) / 2.0, (hy + deck) / 2.0, (0.80, 0.85, 0.97), 0, max(14 * S, (cols[hi] - cols[lo]) * 0.40), a_core=0, a_halo=glow,
             squash=max(1.0, (cols[hi] - cols[lo]) / max(1.0, (yw - hy) * 1.5)))
        if typ in ("cruise", "excursion", "motoryacht"):
            for k in range(int(5 + (cols[hi] - cols[lo]) / (16 * S))):
                _streak(cv, r.uniform(cols[lo], cols[hi]), y, WINDOW, r, fog, 1.25 * strength, length=0.6)

    # ---- navigation lights
    if status in (1, 5) and spd < 0.7:                                 # at anchor or made fast: all-round white, no sidelights
        px, py = peak(0.03, 0.30)
        lamp(px, py - 3 * S, LAMP_WHITE)
        if length >= 50:
            px, py2 = peak(0.75, 0.97)
            lamp(px, max(py2 - 3 * S, py + 5 * S), LAMP_WHITE)
        return
    if typ == "sailing":
        mx_, my_ = peak(0.25, 0.60)
        if _NOTES.get("sail_mode") == "bare":                          # under power: a steaming light part-way up, sidelight at the bow
            lamp(mx_, my_ + (deck - my_) * 0.34, LAMP_WHITE)
            lamp(x0 + 0.06 * L, deck - 4 * S, seen_side, big=0.9)
        elif length < 20 and _own(ship, 7).random() < 0.6:             # under sail, small: the tricolour at the masthead
            lamp(mx_, my_ - 2 * S, seen_side)
        else:                                                          # under sail: sidelights only
            lamp(x0 + 0.06 * L, deck - 4 * S, seen_side, big=0.9)
        for k in range(2):                                             # someone is below with the lamp on
            _put(cv, x0 + L * (0.42 + 0.075 * k), deck - 2.0 * S, WINDOW, 0.9 * S, 2.5 * S, a_core=0.85 * strength, a_halo=0.18 * strength)
        return
    sx_, sy_ = hx, hy + (deck - hy) * 0.42                             # sidelight on the bridge wing
    if typ == "fishing" and (status == 7 or spd < 4.5):                # engaged in fishing: red over white, and the deck lit to work by
        px, py = peak(0.25, 0.75)
        lamp(px, py - 7 * S, LAMP_RED, streak=0.8); lamp(px, py - 1 * S, LAMP_WHITE, streak=0)
        for f in (0.50, 0.72):
            _put(cv, x0 + f * L, deck - 15 * S, LAMP_WHITE, 2.4 * S, (13 + 10 * fog) * S, a_core=strength, a_halo=0.5 * strength)
            _streak(cv, x0 + f * L, y, LAMP_WHITE, r, fog, strength, length=1.1)
        if spd > 0.5:
            lamp(sx_, sy_, seen_side, big=0.9)
        return
    if typ in ("tug", "atb"):                                          # towing: two masthead lights, one above the other
        px, py = peak(0.15, 0.85)
        lamp(px, py - 2 * S, LAMP_WHITE); lamp(px, py + 6 * S, LAMP_WHITE, streak=0)
        lamp(sx_, sy_, seen_side, big=0.9)
        return
    if length >= 50:                                                   # two masthead lights, the after one higher
        hf = (hx - x0) / L
        bx, by = peak(max(0.02, hf - 0.03), min(0.98, hf + 0.03))      # the mast above her bridge
        by = max(by, hy - 0.05 * L) - 3 * S
        if run0 is not None:                                           # liners, yachts, cutters: both lights stand on her upperworks
            tx, ty = peak(0.05, 0.95)
            fx = float(cols[run0]) + 0.12 * (cols[run1] - cols[run0])
            if abs(tx - fx) < 0.08 * L:
                tx = float(cols[run0]) + 0.70 * (cols[run1] - cols[run0])
            if tx < fx:
                fx, tx = tx, fx
            fy = tb[int(fx - xa)] - 4 * S
            lamp(fx, fy, LAMP_WHITE); lamp(tx, min(max(tf[int(tx - xa)], hy - 0.07 * L) - 3 * S, fy - 7 * S), LAMP_WHITE)
        elif hf > 0.22:                                                # the usual ship: high light over the bridge, low one on a foremast
            lamp(x0 + 0.055 * L, deck - max(10 * S, 0.45 * (deck - by)), LAMP_WHITE); lamp(bx, by, LAMP_WHITE)
        else:                                                          # bridge right forward (car carriers): it carries the low light
            lamp(bx, by, LAMP_WHITE); lamp(x0 + 0.60 * L, by - 7 * S, LAMP_WHITE)
    else:
        px, py = peak(0.15, 0.85)
        lamp(px, py - 3 * S, LAMP_WHITE)
    lamp(sx_, sy_, seen_side, big=0.9)


# =====================================================================
# Variety, part two: cargo ships (Oct 15 2026). 32 bulkers, 30 tankers and 30 box boats in the life
# list, and each kind was one drawing. Same two sources as before.
#   TRUE: draught against what a ship her size draws full = how high she rides (empty, she shows a
#   broad band of bottom paint and the top of her bulb); length = holds and gear; her IMO number
#   runs roughly with her year of build = how weathered she is.
#   HER OWN DICE: the colours of a ship whose owner liveries.py does not know. The old answer, every
#   stranger black with a cream house, was just as invented; this one at least tells them apart.
#   Owners we do know keep their real colours.
# =====================================================================
CARGO = ("bulk", "tanker", "container", "cargo", "general")
_FULL = {"bulk": (0.072, -2.7), "tanker": (0.070, -1.5), "container": (0.031, 4.3), "cargo": (0.031, 4.3), "general": (0.050, 1.5)}
_OXIDE, _DKGREEN, _SEAGREY, _MIDBLUE = (0.47, 0.21, 0.17), (0.12, 0.31, 0.25), (0.40, 0.44, 0.50), (0.16, 0.32, 0.62)
_ANON_HULL = {
    "bulk":       [(4, None), (2, (0.16, 0.24, 0.45)), (2, _OXIDE), (1.5, _DKGREEN), (1.5, _SEAGREY), (1.5, _MIDBLUE)],
    "tanker":     [(4, None), (2, (0.16, 0.24, 0.45)), (1.5, _OXIDE), (1, _DKGREEN), (1.5, _SEAGREY), (1, _MIDBLUE)],
    "container":  [(2, None), (2.5, (0.16, 0.24, 0.45)), (1.5, _DKGREEN), (1.5, _SEAGREY), (1.5, _OXIDE), (2, _MIDBLUE)],
    "carcarrier": [(3, None), (2, _MIDBLUE), (1, (0.13, 0.45, 0.32)), (2, (0.62, 0.66, 0.72)), (1, (0.16, 0.24, 0.45))],
}
_ANON_FUNNEL = [(0.13, 0.12, 0.14), (0.78, 0.22, 0.16), _MIDBLUE, (0.13, 0.45, 0.32), (0.88, 0.72, 0.30), (0.93, 0.91, 0.86), (0.16, 0.24, 0.45)]


def cargo_livery(ship):
    """Her colour zones: her owner's if liveries.py knows the owner, else rolled on her own dice."""
    import liveries
    typ = ship.get("type")
    lv = liveries.for_ship(ship.get("name", ""), typ)
    if typ not in _ANON_HULL or not str(lv.get("note", "")).startswith("generic"):
        return lv
    d = _own(ship, 13)
    hull = _pick(d, _ANON_HULL[typ])
    if hull is not None:
        lv["hull"] = hull
    lv["house"] = _pick(d, [(5, lv.get("house")), (4, (0.965, 0.955, 0.93)), (0.8, (0.88, 0.78, 0.55))])
    i, j = d.choice(len(_ANON_FUNNEL), 2, replace=False)
    lv["funnel"], lv["band"] = _ANON_FUNNEL[int(i)], (_ANON_FUNNEL[int(j)] if d.random() < 0.7 else None)
    if typ != "carcarrier":
        lv["boot"] = _pick(d, [(6, lv.get("boot")), (1, (0.18, 0.34, 0.52)), (1, _DKGREEN)])
    lv["note"] = "owner unknown: her own dice"
    return lv


def riding_high(ship):
    """0 = down to her marks, 1 = light ship in ballast. From the draught she broadcasts against what a ship
    of her kind and length draws full. No draught broadcast: somewhere in the middle."""
    k = _FULL.get(ship.get("type"))
    if not k:
        return 0.0
    dr = (ship.get("ais") or {}).get("draught_m")
    if not isinstance(dr, (int, float)) or isinstance(dr, bool) or not 0.5 <= dr <= 26:
        return 0.3
    full = max(4.0, k[0] * float(ship.get("length_m") or 150) + k[1])
    return float(np.clip((0.96 - dr / full) / 0.42, 0.0, 1.0))


def paint_bottom(cv, cx, y, ys, L, seed, fog, boot):
    """The band of bottom paint a light ship shows between her load line (ys) and the sea (y)."""
    if y - ys < 1.5 * S:
        return
    x0, x1 = cx - L / 2, cx + L / 2
    col = fade(boot or RUST, fog)
    band = [(x0 + L * 0.052, ys - 1), (x1 - L * 0.012, ys - 1), (x1 - L * 0.040, y + 1), (x0 + L * 0.070, y + 1)]
    cv.wash(band, col, density=0.95, jitter=1.3, feather=0.9, edge_dark=0.45, granulation=0.35, variegation=0.4, seed=seed + 700)
    cv.wash([(band[3][0], y - (y - ys) * 0.42), (band[2][0], y - (y - ys) * 0.42), band[2], band[3]], fade(PAYNE, fog), density=0.30,
            jitter=1.4, feather=1.6, seed=seed + 701)                       # turning under, into shadow
    if y - ys > 0.020 * L:                                                  # light enough to lift the top of her bulb
        bx = x0 + L * 0.050
        cv.wash([(bx + L * 0.012, y - (y - ys) * 0.62), (bx - L * 0.026, y - (y - ys) * 0.40), (bx - L * 0.030, y + 1), (bx + L * 0.022, y + 1)],
                col, density=0.95, jitter=0.9, feather=0.8, edge_dark=0.4, seed=seed + 702)


def built_about(ship):
    """A rough year of build from her IMO number, which has been handed out more or less in order. None if she has none."""
    imo = (ship.get("ais") or {}).get("imo")
    if not isinstance(imo, (int, float)) or isinstance(imo, bool) or not 5000000 <= imo <= 9999999:
        return None
    return float(np.interp(imo, [7000000, 8000000, 9000000, 9200000, 9300000, 9400000, 9500000, 9600000, 9700000, 9800000, 9900000, 9999999],
                                [1970, 1980, 1990, 2000, 2004.5, 2008, 2010, 2012, 2014.5, 2017.5, 2021, 2025]))


def weather_her(cv, ship, cx, ys, L, seed, fog):
    """Rust weeps down an old ship's side from her scuppers and hawse. A new one is clean."""
    yr = built_about(ship)
    if yr is None or ship.get("type") not in CARGO:
        return
    try:
        now = int(str(ship.get("date", ""))[-4:])
    except ValueError:
        now = 2026
    n = int(np.clip((now - yr - 7) / 1.6, 0, 11))
    r = _own(ship, 17)
    x0 = cx - L / 2
    for k in range(n):
        x = x0 + L * r.uniform(0.07, 0.95)
        top = ys - L * r.uniform(0.040, 0.058)
        ln = L * r.uniform(0.018, 0.045)
        w = max(1.0 * S, L * r.uniform(0.0022, 0.0050))
        cv.gouache([(x - w, top), (x + w, top), (x + w * 0.5, min(ys - 1, top + ln)), (x - w * 0.4, min(ys - 1, top + ln))],
                   fade((0.58, 0.31, 0.19), fog), alpha=0.42 * (1 - 0.4 * fog), jitter=0.8, feather=0.9, seed=seed + 720 + k)


def paint_bulk_carrier2(cv, cx, y, L, seed, fog=0.4, livery=None, ship=None):
    """paint_bulk_carrier, with the things that differ between real bulkers let loose. Her LENGTH sets the
    number of holds and whether she can have cranes at all (handysize and supramax carry their own gear,
    panamax rarely, capesize never). Her own dice settle what length leaves open: geared or not, jibs
    stowed flat for sea or left cocked, the paint on her cranes and hatch covers."""
    lv = livery or {}
    ship = ship or {}
    d = _own(ship, 11)
    length = float(ship.get("length_m") or 180)
    n_h = 4 if length < 140 else 5 if length < 205 else 7 if length < 245 else 9
    geared = d.random() < (0.85 if length < 205 else 0.30 if length < 232 else 0.0)
    stowed = d.random() < 0.55
    crane_paint = _pick(d, [(4, mix(OCHRE, VERMIL, 0.25)), (2.5, (0.90, 0.88, 0.82)), (1.5, (0.55, 0.58, 0.62)), (1.2, (0.16, 0.42, 0.34)), (1.0, (0.20, 0.36, 0.62))])
    hatch_paint = _pick(d, [(4, mix((0.62, 0.58, 0.50), PAYNE, 0.35)), (2.5, (0.55, 0.27, 0.20)), (1.5, (0.20, 0.40, 0.34)), (1.5, (0.45, 0.50, 0.58))])
    Hh = L * 0.075                                       # she's full: low
    x0, x1 = cx - L / 2, cx + L / 2
    hull_col = fade(lv.get("hull") or HULLDARK, fog)
    ink = fade(SUMI, fog)
    inkd = 0.75 * (1 - 0.45 * fog)
    hull = [(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1),
            (x1 - L * 0.015, y + 1), (x1, y - Hh * 0.45), (x1 - L * 0.006, y - Hh)]
    cv.wash(hull, hull_col, density=1.05, jitter=1.6, feather=1.2, edge_dark=0.5,
            granulation=0.35, variegation=0.4, seed=seed)
    strake = [(x0 + L * 0.02, y - Hh + 2), (x1 - L * 0.012, y - Hh + 2),
              (x1 - L * 0.015, y - Hh + Hh * 0.45), (x0 + L * 0.035, y - Hh + Hh * 0.45)]
    cv.lift_mask(cv2.GaussianBlur(_polymask(strake), (0, 0), 2.0 * S), amount=0.42)
    cv.wash([(x0 + L * 0.05, y - 3), (x1 - L * 0.004, y - 3),
             (x1 - L * 0.008, y + 1), (x0 + L * 0.06, y + 1)],
            fade(RUST, fog), density=0.55, jitter=1.4, feather=0.9, dry=0.15, seed=seed + 1)
    # forecastle: a low raised deck at the bow with the foremast
    fc = [(x0 + L * 0.008, y - Hh), (x0 + L * 0.008, y - Hh * 1.30),
          (x0 + L * 0.085, y - Hh * 1.30), (x0 + L * 0.10, y - Hh)]
    cv.wash(fc, fade(mix((0.85, 0.83, 0.80), PAYNE, 0.35), fog), density=0.7,
            jitter=1.0, feather=0.9, edge_dark=0.4, seed=seed + 2)
    cv.line([(x0 + L * 0.045, y - Hh * 1.30), (x0 + L * 0.045, y - Hh * 2.6)],
            ink, width=1, density=inkd * 0.7, seed=seed + 3)
    # hatch covers: raised committed-tone slabs down the deck, lids catching light
    deck = y - Hh
    hatch_col = fade(hatch_paint, fog)
    hx0, hx1 = x0 + L * 0.13, x1 - L * 0.21          # cargo length, castle aft
    span = (hx1 - hx0) / n_h
    hw = span * 0.74                                  # sky between the hatches
    hh = Hh * 0.62
    for k in range(n_h):
        ax = hx0 + k * span + (span - hw) / 2
        slab = [(ax, deck), (ax, deck - hh), (ax + hw, deck - hh), (ax + hw, deck)]
        cv.wash(slab, hatch_col, density=0.85, jitter=1.0, feather=0.7, edge_dark=0.5,
                granulation=0.3, seed=seed + 10 + k)
        lid = [(ax, deck - hh), (ax + hw, deck - hh), (ax + hw, deck - hh * 0.78),
               (ax, deck - hh * 0.78)]
        cv.lift_mask(cv2.GaussianBlur(_polymask(lid), (0, 0), 0.8 * S), 0.35)  # sky on the lid
        cv.line([(ax, deck - hh), (ax + hw, deck - hh)], ink, width=1,
                density=inkd * 0.7, seed=seed + 20 + k)
        cv.line([(ax, deck - hh), (ax, deck), (ax + hw, deck), (ax + hw, deck - hh)],
                ink, width=1, density=inkd * 0.5, seed=seed + 25 + k)   # box edges
    # deck cranes: ochre pedestals in the gaps, jibs cocked forward-up
    crane_col = fade(crane_paint, fog * 0.6)
    for k in (range(1, n_h) if geared else ()):        # cranes between hatch pairs
        px = hx0 + k * span
        ph = Hh * 1.05                                 # pedestal + cab height
        cw = max(3.0, L * 0.014)
        cv.wash([(px - cw, deck), (px - cw, deck - ph), (px + cw, deck - ph), (px + cw, deck)],
                crane_col, density=0.95, jitter=0.7, feather=0.6, edge_dark=0.4,
                seed=seed + 30 + k)
        j0 = (px, deck - ph * 0.95)
        rake = 1.0 + 0.22 * ((k * 37) % 3 - 1)          # jibs cocked, not marching
        j1 = (px - L * 0.10 * rake, deck - ph * (1.35 + 0.75 * rake))
        if stowed:                                     # at sea the jib lies in its crutch, just clear of the hatch
            j1 = (px - span * 0.86, deck - ph * 0.80)
        cv.line([j0, j1], crane_col, width=3, density=0.9 * (1 - fog * 0.3), seed=seed + 40 + k)
        cv.line([j0, j1], ink, width=1, density=inkd * 0.75, seed=seed + 45 + k)
        if not stowed:
            cv.line([j1, (j1[0] + L * 0.005, j1[1] + Hh * 0.9)], ink, width=1,
                    density=inkd * 0.6, seed=seed + 50 + k)     # pendant from the jib head
    # aft castle + funnel + downwind exhaust
    sw = L * 0.145                                       # chunky house, not a tower
    sx = x1 - L * 0.19
    st = y - Hh - Hh * 2.0
    castle = [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)]
    cv.wash(castle, mix(lv.get("house") or (0.92, 0.90, 0.86), FOGGREY, fog * 0.4), density=0.7,
            jitter=1.1, feather=0.8, edge_dark=0.4, granulation=0.3, seed=seed + 60)
    cv.wash([(sx + sw * 0.55, st), (sx + sw, st), (sx + sw, y - Hh),
             (sx + sw * 0.55, y - Hh)], fade(PAYNE, fog), density=0.32,
            jitter=1.2, feather=1.4, seed=seed + 61)
    cv.line([(sx + 3, st + Hh * 0.35), (sx + sw - 3, st + Hh * 0.35)],
            ink, width=1, density=inkd * 0.8, seed=seed + 62)
    cv.line([(sx - 3, st + 3), (sx + sw + 3, st + 3)], ink, width=2,
            density=inkd, seed=seed + 63)
    cv.line([(sx, y - Hh), (sx, st), (sx + sw, st)], ink, width=1,
            density=inkd * 0.75, seed=seed + 64)
    fw = sw * 0.36
    fx = sx + sw * 0.5
    fun = [(fx, st), (fx + fw * 0.15, st - Hh * 0.6),
           (fx + fw * 0.85, st - Hh * 0.6), (fx + fw, st)]
    cv.wash(fun, fade(lv.get("funnel") or mix(SUMI, PAYNE, 0.5), fog), density=0.8, jitter=1,
            feather=0.8, seed=seed + 65)
    cv.line([(fx + fw * 0.12, st - Hh * 0.55), (fx + fw * 0.88, st - Hh * 0.55)],
            fade(lv.get("band") or VERMIL, fog * 0.5), width=2, density=0.9, seed=seed + 66)   # band on funnel
    cv.wash([(fx, st - Hh * 0.65), (fx + fw, st - Hh * 0.7),
             (fx - fw * 3.5, st - Hh * 3.0), (fx - fw * 4.5, st - Hh * 2.2)],
            mix(PAYNE, FOGGREY, 0.5), density=0.12, jitter=8, feather=9,
            edge_dark=0.15, variegation=0.7, seed=seed + 67)
    cv.line([(x0, y - Hh), (x1 - L * 0.006, y - Hh)], ink, width=2,
            density=inkd * 0.85, seed=seed + 68)
    cv.line([(x0, y - Hh), (x0 + L * 0.045, y - Hh * 0.1), (x0 + L * 0.06, y + 1)],
            ink, width=2, density=inkd, seed=seed + 69)
    return hull_col


PAINTERS["bulk"] = paint_bulk_carrier2
for _t in _ANON_HULL:
    HULL_OF[_t] = lambda s: cargo_livery(s).get("hull") or HULLDARK
