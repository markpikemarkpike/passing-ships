"""Three art-direction options for the ship print.

A: watercolor scene + Supergraphic caption band (BSS type treatment)
B: full Supergraphic — flat hard-edge geometry, Helvetica Bold, Sea Ranch palette
C: hybrid — watercolor painting sliced by a hard graphic arc + vertical type
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from watercolor import Canvas
import config
import ship_print as sp
import flags

W, H = sp.W, sp.H
SC = 1.0                                                       # type/layout scale


def set_scale(s=1.0):
    global SC, W, H
    SC = float(s)
    W, H = int(round(sp.W * SC)), int(round(sp.H * SC))

NAVY = (0.13, 0.20, 0.38)     # BSS ultramarine-ish
RED = (0.78, 0.15, 0.12)      # supergraphic red
BLACK = (0.10, 0.10, 0.11)
INK_BLACK = BLACK
PALE = (0.95, 0.93, 0.87)       # the caption's ink on a night sky
WHITE = (0.97, 0.965, 0.95)


# (path with %s for the weight, bold word, regular word, bold index, regular index)
_FONT_CANDIDATES = [
    ("/System/Library/Fonts/Helvetica.ttc", "", "", 1, 0),                      # macOS
    ("/usr/share/fonts/truetype/liberation/LiberationSans-%s.ttf",              # Pi: apt fonts-liberation,
     "Bold", "Regular", 0, 0),                                                  # metric-compatible Helvetica
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-%s.ttf", "Bold", "Regular", 0, 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf", "-Bold", "", 0, 0),   # wider, but it is type
]

def helv(size, bold=True):
    """Helvetica or the nearest thing installed. A missing font must never cost
    the painting: the last resort is PIL's built-in face."""
    size = max(1, int(round(size * SC)))
    for path, b, r, bi, ri in _FONT_CANDIDATES:
        p = path % (b if bold else r) if "%s" in path else path
        if os.path.exists(p):
            return ImageFont.truetype(p, size, index=bi if bold else ri)
    try:
        return ImageFont.load_default(size)                 # Pillow >= 10.1: scalable
    except TypeError:
        return ImageFont.load_default()


def text_w(text, size=12, tracking=0):
    """Pixel width of a caption string, matching text_mask's tracking."""
    f = helv(size, bold=False)
    b = f.getbbox(text)
    return int((b[2] - b[0]) + tracking * SC * max(0, len(text) - 1))

def text_mask(text, font, xy, anchor="la", tracking=0):
    tracking = tracking * SC
    im = Image.new("F", (W, H), 0.0)
    d = ImageDraw.Draw(im)
    if tracking:
        x, y = xy
        total = sum(d.textlength(ch, font=font) + tracking for ch in text) - tracking
        if anchor.startswith("r"):
            x -= total
        elif anchor.startswith("m"):
            x -= total / 2
        for ch in text:
            d.text((x, y), ch, font=font, fill=1.0, anchor="la")
            x += d.textlength(ch, font=font) + tracking
    else:
        d.text(xy, text, font=font, fill=1.0, anchor=anchor)
    return np.asarray(im, np.float32)


def vtext_mask(text, font, x, y_center):
    """Vertical (rotated 90° CCW) text mask, reading bottom-to-top."""
    tmp = Image.new("F", (H, W), 0.0)
    d = ImageDraw.Draw(tmp)
    d.text((H // 2, x if False else 0), text, font=font, fill=1.0)  # placeholder
    tmp = Image.new("F", (H, 120), 0.0)
    d = ImageDraw.Draw(tmp)
    d.text((H - y_center, 60), text, font=font, fill=1.0, anchor="mm")
    rot = tmp.rotate(90, expand=True)  # now 120 x H
    m = np.zeros((H, W), np.float32)
    arr = np.asarray(rot, np.float32)
    x0 = int(x - 60)
    xs = max(0, x0)
    xe = min(W, x0 + arr.shape[1])
    m[:, xs:xe] = arr[:, xs - x0:xe - x0]
    return m


def apply_ink(cv, mask, rgb, opaque=True):
    a = np.clip(mask, 0, 1)[..., None]
    col = np.asarray(rgb, np.float32)
    cv.img = cv.img * (1 - a) + col * a


def crisp(cv, poly, rgb, seed=0):
    """Supergraphic mark: printed hard edge, no wet wobble, no feather.
    The razor edge of the type is meant to cut against the soft painting."""
    cv.gouache(poly, rgb, alpha=1.0, jitter=0.0, feather=0.0, seed=seed)


def flat(cv, poly, rgb, seed=0):
    """Hard-edge shape with the faintest print wobble."""
    cv.gouache(poly, rgb, alpha=1.0, jitter=0.35, feather=0.4, seed=seed)


def circle_poly(cx, cy, r, n=120, a0=0, a1=360):
    ang = np.radians(np.linspace(a0, a1, n))
    pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in ang]
    if (a1 - a0) % 360 != 0:
        pts.append((cx, cy))
    return pts


def arrow_poly(x, y, length=54, h=16, direction=-1):
    """BSS-style bar arrow. direction -1 = left (southbound), +1 = right."""
    d = direction
    tip = (x + d * length / 2, y)
    head = length * 0.42
    return [
        tip,
        (tip[0] - d * head, y - h),
        (tip[0] - d * head, y - h * 0.45),
        (x - d * length / 2, y - h * 0.45),
        (x - d * length / 2, y + h * 0.45),
        (tip[0] - d * head, y + h * 0.45),
        (tip[0] - d * head, y + h),
    ]


def flat_ship_silhouette(cv, cx, y, L, rgb, seed=5):
    """Container ship as one flat shape (hull + castle + stacks massed)."""
    Hh = L * 0.085
    x0, x1 = cx - L / 2, cx + L / 2
    hull = [(x0, y - Hh), (x0 + L * 0.055, y - Hh * 0.2), (x0 + L * 0.075, y),
            (x1 - L * 0.02, y), (x1, y - Hh * 0.55), (x1 - L * 0.01, y - Hh)]
    flat(cv, hull, rgb, seed=seed)
    r = np.random.default_rng(seed)
    n_bays = max(6, int(L / 46))
    bay_w = (L * 0.66) / n_bays
    bx0 = x0 + L * 0.10
    for b in range(n_bays):
        hgt = r.integers(2, 5) * Hh * 0.42
        flat(cv, [(bx0 + b * bay_w + 1, y - Hh - hgt),
                  (bx0 + (b + 1) * bay_w - 1, y - Hh - hgt),
                  (bx0 + (b + 1) * bay_w - 1, y - Hh),
                  (bx0 + b * bay_w + 1, y - Hh)], rgb, seed=seed + b)
    sw, sx = L * 0.135, x1 - L * 0.185
    st = y - Hh - Hh * 1.75
    flat(cv, [(sx, y - Hh), (sx, st), (sx + sw, st), (sx + sw, y - Hh)], rgb, seed=seed + 40)
    fx, fw = sx + sw * 0.55, sw * 0.34
    flat(cv, [(fx, st), (fx + fw * 0.15, st - Hh * 0.45),
              (fx + fw * 0.85, st - Hh * 0.45), (fx + fw, st)], rgb, seed=seed + 41)


# MMSI country prefix (MID) → flag state, the common Pacific-lane registries
MID_FLAGS = {477: "HONG KONG", 636: "LIBERIA", 563: "SINGAPORE", 351: "PANAMA",
             352: "PANAMA", 353: "PANAMA", 538: "MARSHALL IS.", 419: "INDIA",
             431: "JAPAN", 432: "JAPAN", 416: "TAIWAN", 440: "KOREA",
             219: "DENMARK", 244: "NETHERLANDS", 235: "UK", 366: "USA",
             367: "USA", 368: "USA", 369: "USA", 338: "USA", 316: "CANADA"}


MID_ISO = {201:"AL",203:"AT",205:"BE",209:"CY",210:"CY",212:"CY",215:"MT",229:"MT",248:"MT",249:"MT",256:"MT",
           219:"DK",220:"DK",211:"DE",218:"DE",224:"ES",225:"ES",226:"FR",227:"FR",228:"FR",232:"GB",233:"GB",
           234:"GB",235:"GB",236:"GI",237:"GR",239:"GR",240:"GR",241:"GR",244:"NL",245:"NL",246:"NL",
           247:"IT",257:"NO",258:"NO",259:"NO",255:"PT",263:"PT",273:"RU",303:"US",338:"US",366:"US",
           367:"US",368:"US",369:"US",316:"CA",303:"US",310:"BM",311:"BS",312:"BZ",314:"BB",319:"KY",
           325:"AG",332:"GT",334:"HN",336:"CR",338:"US",339:"JM",341:"KN",343:"LC",345:"MX",347:"MQ",
           351:"PA",352:"PA",353:"PA",354:"PA",355:"PA",356:"PA",357:"PA",370:"PA",371:"PA",372:"PA",
           373:"PA",374:"PA",375:"VC",376:"VC",377:"VC",379:"VG",401:"AF",403:"SA",405:"BD",412:"CN",
           413:"CN",414:"CN",416:"TW",417:"LK",419:"IN",422:"IR",431:"JP",432:"JP",440:"KR",441:"KR",
           445:"KP",447:"KW",450:"LB",453:"MO",455:"MV",457:"MN",461:"OM",463:"PK",466:"QA",467:"SY",
           468:"AE",470:"AE",471:"AE",472:"TJ",473:"YE",475:"YE",477:"HK",478:"BA",501:"AQ",503:"AU",
           506:"MM",508:"BN",510:"FM",511:"PW",512:"NZ",514:"KH",515:"KH",516:"CX",518:"CK",520:"FJ",
           523:"CC",525:"ID",529:"KI",531:"LA",533:"MY",536:"MP",538:"MH",540:"NC",542:"NU",544:"NR",
           546:"PF",548:"PH",553:"PG",555:"PN",557:"SB",559:"AS",561:"WS",563:"SG",564:"SG",565:"SG",
           566:"SG",567:"TH",570:"TO",572:"TV",574:"VN",576:"VU",577:"VU",578:"WF",601:"ZA",603:"AO",
           605:"DZ",636:"LR",637:"LR"}

ISO_NAME = {"PA":"PANAMA","LR":"LIBERIA","MH":"MARSHALL IS.","BS":"BAHAMAS","MT":"MALTA","SG":"SINGAPORE",
            "HK":"HONG KONG","US":"USA","CN":"CHINA","JP":"JAPAN","GB":"UK","GR":"GREECE","CY":"CYPRUS",
            "MX":"MEXICO","CA":"CANADA","KR":"KOREA","NL":"NETHERLANDS","DE":"GERMANY","FR":"FRANCE",
            "IT":"ITALY","NO":"NORWAY","DK":"DENMARK","AU":"AUSTRALIA","BM":"BERMUDA","KY":"CAYMAN IS.",
            "TW":"TAIWAN","RU":"RUSSIA","IN":"INDIA","VN":"VIETNAM","AG":"ANTIGUA","VU":"VANUATU","TV":"TUVALU",
            "ES":"SPAIN","PT":"PORTUGAL","PH":"PHILIPPINES","MY":"MALAYSIA","ID":"INDONESIA","TH":"THAILAND",
            "AE":"UAE","BZ":"BELIZE","VC":"ST. VINCENT","GI":"GIBRALTAR","IM":"ISLE OF MAN"}

def stable_seed(name):
    """Deterministic per-ship seed (str hash is randomized per process)."""
    import zlib
    return zlib.crc32(str(name).encode("utf-8")) & 0xFFFF


def flag_of(mmsi):
    return MID_FLAGS.get(int(str(mmsi)[:3]), "")


def option_A2(ship, wx, path, scale=1.0):
    """Mark's direction (Jul 23): full-bleed painting, info small and in the
    sky, richer ship metadata, weather-driven scene. Painting = scene.py.
    scale > 1 paints a supersampled master (2400x1440 at 3.0) for prints and
    screen; the frame stays at 1.0 (the Pi Zero can't afford 9x pixels)."""
    import scene
    scene.set_scale(scale)
    set_scale(scale)
    seed = stable_seed(ship["name"])
    cv = Canvas(W, H, seed=seed, k=scale)
    scene.paint_scene(cv, ship, wx, seed)
    info_block(cv, ship, wx)
    out = cv.save(path)
    scene.set_scale(1.0)
    set_scale(1.0)
    return out


def info_block(cv, ship, wx):
    """The A2 caption: compact Supergraphic type in the sky (shared by styles)."""
    x0, y0 = 34 * SC, 26 * SC
    # Dark type on a light sky, pale type on a dark one. Judged from the paint actually under the
    # words, so it follows the picture and not the clock.
    under = cv.img[int(20 * SC):int(125 * SC), int(30 * SC):int(330 * SC)]
    BLACK = PALE if float(under.mean()) < 0.50 else INK_BLACK
    apply_ink(cv, text_mask(sp.full_name(ship), helv(24), (x0, y0), tracking=1), BLACK)
    cv.gouache_line([(x0 + 1 * SC, y0 + 36 * SC), (x0 + 150 * SC, y0 + 36 * SC)], RED,
                    width=3, alpha=1.0, jitter=0.0, seed=70)
    iso = (ship.get("country") or MID_ISO.get(int(str(ship.get("mmsi", 0) or 0)[:3] or 0), "")).upper()
    flag_name = ISO_NAME.get(iso) or flag_of(ship.get("mmsi", 0))
    tx = x0 + 1 * SC
    apply_ink(cv, text_mask(ship["shiptype_text"].upper() + " ·", helv(12, bold=False),
                            (tx, y0 + 44 * SC), tracking=2), BLACK)
    tx += text_w(ship["shiptype_text"].upper() + " ·", 12, tracking=2) + 8 * SC
    # painted flag icon (six-ink friendly), then the country name
    if flags.paint_flag(cv, iso, tx, y0 + 43 * SC, w=26 * SC, h=17 * SC, seed=73):
        tx += (26 + 8) * SC
    if flag_name:
        apply_ink(cv, text_mask(flag_name, helv(12, bold=False), (tx, y0 + 44 * SC),
                                tracking=2), BLACK)
    line3 = "%s%d M · %.1f KN · FOR %s" % ("~" if ship.get("length_est") else "",
                                            ship["length_m"], ship["speed_kn"],
                                            ship["dest"].upper())
    apply_ink(cv, text_mask(line3, helv(12, bold=False), (x0 + 36 * SC, y0 + 63 * SC),
                            tracking=2), BLACK)
    if ship.get("spotted"):                              # when she passed, how far off
        apply_ink(cv, text_mask(ship["spotted"], helv(11, bold=False),
                                (x0 + 36 * SC, y0 + 82 * SC), tracking=2), BLACK)
    crisp(cv, arrow_poly(x0 + 13 * SC, y0 + 70 * SC, length=24 * SC, h=8 * SC,
                         direction=1 if config.sails_right(ship.get("heading", 180)) else -1),
          RED, seed=71)
    # ---- place/date/conditions, upper-right sky ----
    apply_ink(cv, text_mask(config.PLACE, helv(12), (W - 34 * SC, y0),
                            anchor="ra", tracking=4), BLACK)
    apply_ink(cv, text_mask(ship["date"], helv(11, bold=False), (W - 34 * SC, y0 + 19 * SC),
                            anchor="ra", tracking=2), BLACK)
    apply_ink(cv, text_mask(wx["label"], helv(11, bold=False), (W - 34 * SC, y0 + 36 * SC),
                            anchor="ra", tracking=2), BLACK)
    if ship.get("radio_note"):                           # the receiver went quiet: say so
        apply_ink(cv, text_mask(ship["radio_note"], helv(10, bold=False),
                                (W - 34 * SC, y0 + 53 * SC), anchor="ra", tracking=2), RED)


def stat_band_A(cv, ship):
    """Option A caption: white band, Helvetica Bold, red rule + arrow."""
    band_y = H - 96
    flat(cv, [(0, band_y), (W, band_y), (W, H), (0, H)], WHITE, seed=70)
    flat(cv, [(0, band_y), (W, band_y), (W, band_y + 6), (0, band_y + 6)], RED, seed=71)
    apply_ink(cv, text_mask(sp.full_name(ship), helv(38), (34, band_y + 18), tracking=1), BLACK)
    stats = "%d M   ·   %.1f KN   ·   %s" % (
        ship["length_m"], ship["speed_kn"], ship["dest"].upper())
    apply_ink(cv, text_mask(stats, helv(17, bold=False), (98, band_y + 62), tracking=2), BLACK)
    flat(cv, arrow_poly(58, band_y + 71, direction=-1), RED, seed=72)
    apply_ink(cv, text_mask("%s · %s" % (config.PLACE, ship["date"]), helv(12, bold=False),
                            (W - 34, band_y + 66), anchor="ra", tracking=1), BLACK)


def option_A(ship, path):
    seed = stable_seed(ship["name"])
    cv = Canvas(W, H, seed=seed)
    sp.paint_sky(cv, seed)
    L = sp.ship_px(ship["length_m"])
    cx, y = W * 0.44, sp.HORIZON + 26
    foam = [(cx - L * 0.54, y - 1), (cx + L * 0.52, y - 1), (cx + L * 0.80, y + 6),
            (cx + L * 0.60, y + 11), (cx - L * 0.56, y + 5)]
    sp.paint_sea(cv, seed, wake_poly=foam)
    sp.PAINTERS[ship["type"]](cv, cx, y, L, seed + 100)
    cv.wash([(cx - L / 2, y + 6), (cx + L / 2, y + 6), (cx + L / 2, y + 12),
             (cx - L / 2, y + 12)], sp.INDIGO, density=0.30, jitter=2,
            feather=2.5, seed=seed + 200)
    stat_band_A(cv, ship)
    return cv.save(path)


def option_B(ship, path):
    """Full Supergraphic: flat geometry, no watercolor scene."""
    seed = stable_seed(ship["name"])
    cv = Canvas(W, H, seed=seed)
    sea_y = 312
    # navy sea block
    flat(cv, [(0, sea_y), (W, sea_y), (W, H), (0, H)], NAVY, seed=1)
    # concentric white wave arcs biting in from bottom-RIGHT (clear of the type)
    for i, r in enumerate((200, 138, 76)):
        col = WHITE if i % 2 == 0 else NAVY
        flat(cv, circle_poly(W, H, r, a0=180, a1=270), col, seed=2 + i)
    # red sun, cropped by the top edge
    flat(cv, circle_poly(W - 130, 46, 92), RED, seed=6)
    # flat black ship riding the sea line
    L = sp.ship_px(ship["length_m"])
    flat_ship_silhouette(cv, W * 0.47, sea_y, L, BLACK, seed=8)
    # type block
    name = ship["name"].upper()
    y0 = H - 152
    apply_ink(cv, text_mask(name, helv(56), (34, y0)), WHITE)
    stats = "%d M · %.1f KN · FOR %s" % (ship["length_m"], ship["speed_kn"],
                                          ship["dest"].upper())
    apply_ink(cv, text_mask(stats, helv(18, bold=False), (118, y0 + 76), tracking=2), WHITE)
    flat(cv, arrow_poly(66, y0 + 86, length=64, h=19, direction=-1), RED, seed=9)
    apply_ink(cv, text_mask(config.PLACE, helv(13), (34, 26), tracking=6), BLACK)
    apply_ink(cv, text_mask(ship["date"], helv(12, bold=False), (34, 48), tracking=3), BLACK)
    return cv.save(path)


def option_C(ship, path):
    """Hybrid: watercolor scene, hard white margin, red arc slice, vertical type."""
    seed = stable_seed(ship["name"])
    cv = Canvas(W, H, seed=seed)
    sp.paint_sky(cv, seed)
    L = sp.ship_px(ship["length_m"]) * 0.9
    cx, y = W * 0.52, sp.HORIZON + 26
    foam = [(cx - L * 0.54, y - 1), (cx + L * 0.52, y - 1), (cx + L * 0.80, y + 6),
            (cx + L * 0.60, y + 11), (cx - L * 0.56, y + 5)]
    sp.paint_sea(cv, seed, wake_poly=foam)
    sp.PAINTERS[ship["type"]](cv, cx, y, L, seed + 100)
    # hard white margins (the painting floats)
    mL, mR, mT, mB = 96, 28, 28, 76
    flat(cv, [(0, 0), (mL, 0), (mL, H), (0, H)], WHITE, seed=20)
    flat(cv, [(W - mR, 0), (W, 0), (W, H), (W - mR, H)], WHITE, seed=21)
    flat(cv, [(0, 0), (W, 0), (W, mT), (0, mT)], WHITE, seed=22)
    flat(cv, [(0, H - mB), (W, H - mB), (W, H), (0, H)], WHITE, seed=23)
    # red quarter-arc slicing up from the bottom-left corner of the image area
    flat(cv, circle_poly(mL, H - mB, 150, a0=270, a1=360), RED, seed=24)
    # vertical name up the left margin
    name = ship["name"].upper()
    apply_ink(cv, vtext_mask(name, helv(40), mL // 2, H // 2 + 20), BLACK)
    # stats along the bottom
    stats = "%d M · %.1f KN · FOR %s" % (ship["length_m"], ship["speed_kn"],
                                          ship["dest"].upper())
    apply_ink(cv, text_mask(stats, helv(16, bold=False), (mL + 66, H - mB + 26),
                            tracking=2), BLACK)
    flat(cv, arrow_poly(mL + 30, H - mB + 34, length=44, h=13, direction=-1), RED, seed=25)
    apply_ink(cv, text_mask("%s · %s" % (config.PLACE, ship["date"]), helv(11),
                            (W - mR - 6, H - mB + 30), anchor="ra", tracking=1), BLACK)
    return cv.save(path)


if __name__ == "__main__":
    import sys
    ship = dict(name="Cosco Pacific", type="container", length_m=366,
                dest="Oakland", speed_kn=16.2, date="23 JULY 2026",
                mmsi=477123456, heading=132, shiptype_text="Container Ship")
    # live-ish Point Arena buoy 46014: NW 17 kn, seas 7 ft, fog
    wx = dict(wind_kn=17, wave_ft=7, fog=0.75,
              label="NW 17 KN · SEAS 7 FT · FOG")
    if len(sys.argv) > 1 and sys.argv[1] == "a2":
        print(option_A2(ship, wx, "renders/optA2_sky_info_weather.png"))
    else:
        print(option_A(ship, "renders/optA_watercolor_super_caption.png"))
        print(option_B(ship, "renders/optB_full_supergraphic.png"))
        print(option_C(ship, "renders/optC_hybrid_arc.png"))
        print(option_A2(ship, wx, "renders/optA2_sky_info_weather.png"))
