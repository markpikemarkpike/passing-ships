"""Operator liveries: a ship's colour is her owner.

Every merchant vessel reads as three colour zones -- HULL, HOUSE (super-
structure) and FUNNEL (the company's signature) -- plus, for a container
ship, the BOX MIX she is stacked with (a ONE ship is loaded with pink ONE
boxes). This module returns those zones for a named ship, cascading:

    unknown ship  ->  the honest generic for her TYPE (laden tankers really
                      are black-and-red; bulkers rust-and-black)
    known operator ->  overrides only the zones the company actually owns

Matched by keyword in the AIS name (that is all AIS gives us), and only
against operators of her own kind: a tug called OCEAN TITAN is not a Wallenius
car carrier and a tanker called LONE STAR is not a ONE box ship. The regulars
here are SF/Oakland traffic: ONE, Matson + Pasha (the Hawaii run passes
this bluff), Maersk, MSC, Evergreen, CMA CGM, COSCO, Hapag, Wan Hai, HMM,
MOL car carriers, WW/EUKOR, K Line/Glovis, the SF cruise callers, Foss and
Crowley tugs, NOAA whites.

SIX-INK NOTE: colours here are the real-world hue; the panel dithers them
into the six primaries (magenta -> red+blue weave = reads rose; orange ->
red+yellow; light blue -> blue+white; green is a NATIVE ink and pops). Test
new liveries through fleet.py + the panel preview before trusting them.
Colours are float RGB in [0,1] like scene.py's masstones."""
import re

# --- honest generics per type (what an anonymous ship of that type is) ---
WHITE      = (0.965, 0.955, 0.93)
STEEL      = (0.62, 0.65, 0.72)          # panel-safe "white" box: pale steel that keeps its edges on 6 inks
CREAM      = (0.93, 0.91, 0.86)
BLACK_HULL = (0.16, 0.19, 0.27)          # scene.HULLDARK family
RUST       = (0.66, 0.30, 0.22)
NAVY       = (0.16, 0.24, 0.45)
BUFF       = (0.86, 0.72, 0.42)

GENERIC = {
    "container":  dict(hull=BLACK_HULL, boot=RUST, house=CREAM, funnel=RUST, band=None,
                       boxes=None),                        # None = the mixed generic stack
    "tanker":     dict(hull=BLACK_HULL, boot=RUST, house=CREAM, funnel=(0.78, 0.30, 0.20), band=None),
    "bulk":       dict(hull=BLACK_HULL, boot=RUST, house=CREAM, funnel=(0.13, 0.12, 0.14), band=(0.78, 0.30, 0.20)),
    "general":    dict(hull=BLACK_HULL, boot=RUST, house=CREAM, funnel=(0.28, 0.50, 0.53), band=None),
    "carcarrier": dict(hull=WHITE, boot=(0.16, 0.19, 0.27), house=WHITE, funnel=WHITE, band=None),
    "cruise":     dict(hull=WHITE, boot=NAVY, house=WHITE, funnel=WHITE, band=None),
    "research":   dict(hull=(0.16, 0.32, 0.62), boot=RUST, house=WHITE, funnel=WHITE, band=None),
    "tug":        dict(hull=BLACK_HULL, boot=(0.78, 0.30, 0.20), house=WHITE, funnel=(0.13, 0.12, 0.14), band=None),
    "atb":        dict(hull=BLACK_HULL, boot=(0.78, 0.30, 0.20), house=WHITE, funnel=(0.13, 0.12, 0.14), band=None),
    "workboat":   dict(hull=BLACK_HULL, boot=(0.78, 0.30, 0.20), house=WHITE, funnel=(0.13, 0.12, 0.14), band=None),
}

# --- operator overrides: keyword (in AIS name) -> zones the company owns ---
# ordered: first match wins, so put specific names before generic tokens.
# Keys match whole words only (has_word below): "ONE " never fires inside LONE
# or KEYSTONE, "LEADER" never inside LEADERSHIP.
# ---------------- container lines ----------------
_BOX_LINES = [
    (("ONE ", "ONE "), dict(hull=(0.62, 0.10, 0.55), house=WHITE, funnel=(0.62, 0.10, 0.55),   # bluer: panel weaves red+blue = rose
                                  boxes=[(0.72, 0.18, 0.58), STEEL, (0.72, 0.18, 0.58)]),
     "ONE (Ocean Network Express): magenta hull + funnel, pink boxes"),
    (("MAERSK", "MOLLER"), dict(hull=(0.55, 0.72, 0.84), house=(0.86, 0.82, 0.72),
                                funnel=(0.55, 0.72, 0.84), boxes=[(0.60, 0.66, 0.72), (0.55, 0.72, 0.84)]),
     "Maersk: the light-blue hull, sand-coloured house, grey/blue boxes"),
    (("MSC ",), dict(hull=BLACK_HULL, house=CREAM, funnel=CREAM, band=(0.13, 0.12, 0.14),
                     boxes=[(0.78, 0.62, 0.28), (0.78, 0.62, 0.28), (0.60, 0.60, 0.62)]),
     "MSC: black hull, cream house/funnel, mustard boxes"),
    (("EVER ", "EVERGREEN"), dict(hull=(0.13, 0.36, 0.24), house=CREAM, funnel=(0.13, 0.36, 0.24),
                                    boxes=[(0.18, 0.45, 0.30), (0.18, 0.45, 0.30), STEEL]),
     "Evergreen: green hull, funnel, boxes -- green is a native panel ink, she pops"),
    (("CMA CGM",), dict(hull=(0.13, 0.20, 0.42), house=WHITE, funnel=(0.20, 0.32, 0.62), band=(0.78, 0.20, 0.16),
                        boxes=[(0.20, 0.32, 0.62), (0.20, 0.32, 0.62), STEEL]),
     "CMA CGM: dark blue hull, blue funnel with a red band, blue boxes"),
    (("COSCO",), dict(hull=(0.13, 0.20, 0.42), house=WHITE, funnel=(0.13, 0.20, 0.42),
                      boxes=[(0.55, 0.60, 0.68), (0.20, 0.32, 0.62), STEEL]),
     "COSCO: dark blue hull, grey/blue boxes"),
    (("HAPAG", "EXPRESS"), dict(hull=(0.13, 0.20, 0.42), house=WHITE, funnel=(0.86, 0.46, 0.16),
                                   band=(0.13, 0.20, 0.42), boxes=[(0.88, 0.48, 0.16), (0.88, 0.48, 0.16), (0.60, 0.60, 0.62)]),
     "Hapag-Lloyd: blue hull, ORANGE funnel and boxes"),
    (("OOCL",), dict(hull=(0.90, 0.90, 0.88), house=WHITE, funnel=WHITE, band=(0.78, 0.20, 0.16),
                     boxes=[STEEL, STEEL, (0.60, 0.60, 0.62)]),
     "OOCL: pale grey hull, white boxes with red"),
    (("YANG MING", "YM "), dict(hull=BLACK_HULL, funnel=(0.20, 0.32, 0.62),
                              boxes=[(0.60, 0.60, 0.62), STEEL]),
     "Yang Ming: dark hull, grey boxes"),
    (("HMM ", "HYUNDAI"), dict(hull=(0.13, 0.20, 0.42), funnel=(0.13, 0.20, 0.42),
                              boxes=[(0.20, 0.32, 0.62), STEEL]),
     "HMM: dark blue hull, blue/white boxes"),
    (("WAN HAI",), dict(hull=BLACK_HULL, funnel=(0.78, 0.20, 0.16), boxes=[(0.60, 0.60, 0.62), (0.20, 0.32, 0.62)]),
     "Wan Hai: black hull, red funnel"),
    (("ZIM ",), dict(hull=(0.16, 0.19, 0.27), funnel=(0.16, 0.19, 0.27), boxes=[(0.60, 0.60, 0.62), STEEL]),
     "ZIM: dark hull, grey boxes"),
    # the Hawaii run passes this bluff daily
    (("MATSON", "MANOA", "MAHIMAHI", "MANULANI", "KAIMANA HILA", "DANIEL K INOUYE", "LURLINE", "MATSONIA", "MANUKAI", "MAUNAWILI", "MAUNALEI", "MOKIHANA"),
     dict(hull=(0.10, 0.16, 0.36), house=WHITE, funnel=BUFF, band=(0.10, 0.16, 0.36),
          boxes=[STEEL, (0.30, 0.36, 0.52), STEEL]),
     "Matson (Hawaii run): navy hull, white house, BUFF funnel with the navy band"),
    (("PASHA", "HORIZON PACIFIC", "HORIZON RELIANCE", "HORIZON SPIRIT", "HORIZON ENTERPRISE", "HORIZON ", "GEORGE II", "GEORGE III", "JANET MARIE", "MARJORIE C", "JEAN ANNE"),
     dict(hull=(0.13, 0.28, 0.55), house=WHITE, funnel=BUFF, band=(0.13, 0.28, 0.55),
          boxes=[STEEL, (0.30, 0.36, 0.52)]),
     "Pasha Hawaii: blue hull, buff funnel"),
]
# ---------------- car carriers (band + hull) ----------------
_CAR_CARRIERS = [
    (("HIGHWAY", "K LINE"), dict(hull=WHITE, band=(0.78, 0.20, 0.16), funnel=(0.78, 0.20, 0.16)),
     "K Line PCTC: white hull, red band + funnel"),
    (("GLOVIS",), dict(hull=WHITE, band=(0.13, 0.28, 0.55), funnel=(0.13, 0.28, 0.55)),
     "Hyundai Glovis: white hull, blue band"),
    ((" ACE", "MOL ", "COURAGEOUS ACE", "GALAXY ACE"), dict(hull=(0.20, 0.42, 0.68), band=WHITE, funnel=(0.20, 0.42, 0.68)),
     "MOL car carriers (-ACE names): the light BLUE hull"),
    (("LEADER", "AUTO ", "NYK "), dict(hull=WHITE, band=(0.13, 0.20, 0.42), funnel=(0.78, 0.20, 0.16)),
     "NYK PCTC: white hull, blue band, red funnel"),
    (("TITANIA", "TITUS", "TAMESIS", "TALISMAN", "MORNING", "EUKOR", "WALLENIUS", "WILHELMSEN", "TIRRANNA", "TARAGO"),
     dict(hull=(0.24, 0.48, 0.44), band=WHITE, funnel=WHITE),
     "Wallenius Wilhelmsen / EUKOR: teal-green hull"),
    (("HOEGH", "HÖEGH"), dict(hull=(0.13, 0.20, 0.42), band=(0.78, 0.20, 0.16), funnel=WHITE),
     "Hoegh Autoliners: dark blue hull, red band"),
]
# ---------------- cruise callers at San Francisco ----------------
_CRUISE_LINES = [
    (("CARNIVAL",), dict(hull=WHITE, boot=NAVY, house=WHITE, funnel=WHITE, tail=True),
     "Carnival: white ship + the red/white/blue whale-tail funnel"),
    (("PRINCESS",), dict(hull=WHITE, boot=NAVY, house=WHITE, funnel=WHITE, band=(0.13, 0.28, 0.55)),
     "Princess: white ship, blue seawitch funnel logo"),
    (("HOLLAND", "KONINGSDAM", "NIEUW ", "EURODAM", "OOSTERDAM", "ZAANDAM", "VOLENDAM", "WESTERDAM"),
     dict(hull=(0.10, 0.16, 0.36), boot=(0.78, 0.20, 0.16), house=WHITE, funnel=WHITE, band=BUFF),
     "Holland America: the dark blue hull, white upperworks"),
    (("DISNEY",), dict(hull=(0.08, 0.10, 0.24), boot=(0.78, 0.20, 0.16), house=WHITE, funnel=(0.78, 0.20, 0.16), band=(0.86, 0.72, 0.30)),
     "Disney: navy hull, RED funnels, gold trim line"),
    (("QUEEN ", "CUNARD"), dict(hull=(0.13, 0.12, 0.14), boot=(0.78, 0.20, 0.16), house=WHITE, funnel=(0.78, 0.20, 0.16), band=(0.13, 0.12, 0.14)),
     "Cunard: black hull, the red-and-black funnel"),
    (("NORWEGIAN", "NORWEGIAN "), dict(hull=WHITE, boot=NAVY, house=WHITE, funnel=WHITE, band=(0.20, 0.32, 0.62)),
     "Norwegian: white ship (hull art varies -- keep white)"),
    (("VIKING",), dict(hull=WHITE, boot=(0.13, 0.20, 0.42), house=WHITE, funnel=WHITE, band=(0.60, 0.10, 0.14)),
     "Viking ocean: white ship, red band"),
    (("CELEBRITY",), dict(hull=(0.13, 0.20, 0.42), house=WHITE, funnel=(0.13, 0.20, 0.42)),
     "Celebrity: dark blue hull + X funnel"),
]
# ---------------- research / government whites ----------------
_RESEARCH = [
    (("NOAA ", "SHIMADA", "RONALD H BROWN", "OSCAR DYSON", "RAINIER", "OKEANOS", "REUBEN LASKER", "FAIRWEATHER"),
     dict(hull=WHITE, boot=(0.13, 0.28, 0.55), house=WHITE, funnel=BUFF),
     "NOAA fleet: white hull, blue boot, buff stack"),
    (("FALKOR",), dict(hull=WHITE, boot=(0.13, 0.28, 0.55), house=WHITE, funnel=(0.13, 0.28, 0.55)),
     "Schmidt Ocean Falkor: white with blue"),
]
# ---------------- tugs & the fuel run ----------------
_TUGS = [
    (("FOSS",), dict(hull=(0.13, 0.36, 0.24), house=WHITE, funnel=(0.13, 0.36, 0.24), band=WHITE),
     "Foss Maritime: GREEN hull, white house, green stack with white bands -- native green ink"),
    (("CROWLEY",), dict(hull=(0.16, 0.19, 0.27), house=WHITE, funnel=(0.78, 0.20, 0.16), band=WHITE),
     "Crowley: dark hull, white house, red trim"),
    (("HARLEY", "GENE DUNLAP", "STARLIGHT", "MILLENNIUM", "OLYMPIC"), dict(house=WHITE, funnel=(0.78, 0.20, 0.16), band=(0.13, 0.20, 0.42)),
     "Harley Marine / Centerline: white house, red-and-blue stacks"),
]
# ---------------- tanker owners with a real look ----------------
_TANKERS = [
    (("POLAR ",), dict(hull=(0.20, 0.32, 0.62), house=WHITE, funnel=WHITE, band=(0.78, 0.20, 0.16)),
     "Polar Tankers (Alaska crude): blue hull"),
    (("OVERSEAS",), dict(hull=BLACK_HULL, house=WHITE, funnel=(0.13, 0.20, 0.42), band=(0.78, 0.20, 0.16)),
     "OSG: black hull, blue funnel with red"),
    (("CHEVRON", "TEXACO"), dict(hull=BLACK_HULL, house=WHITE, funnel=WHITE, band=(0.13, 0.20, 0.42)),
     "Chevron shipping: black hull, white funnel with the blue chevron band"),
]
OPERATORS = [row + (kind,) for kind, rows in (
    ("container", _BOX_LINES), ("carcarrier", _CAR_CARRIERS), ("cruise", _CRUISE_LINES),
    ("research", _RESEARCH), ("tug", _TUGS), ("tanker", _TANKERS)) for row in rows]
# Keys good enough to choose a colour once we know what kind of ship she is, but
# too ordinary (or shared with another trade) to tell us the kind. NYK and MOL
# names sail on box ships too; there are tankers called EVERGREEN STATE and
# anything EXPRESS, and bulkers called MORNING anything.
_COLOUR_ONLY = {"EVERGREEN", "EXPRESS", "HORIZON ", "MOLLER", "GEORGE II", "GEORGE III",
                "HIGHWAY", " ACE", "MOL ", "LEADER", "AUTO ", "NYK ", "MORNING", "TITUS"}
# painter type -> whose fleets she could belong to (bulkers and the rest: nobody's)
_KIND = {"container": "container", "cargo": "container", "carcarrier": "carcarrier",
         "cruise": "cruise", "passenger": "cruise", "research": "research",
         "tug": "tug", "atb": "tug", "workboat": "tug", "tanker": "tanker"}


def has_word(name, *keys):
    """True if any key appears in name as whole words. A key's own leading or
    trailing space is kept and means what it says (' ACE' = a later word, never
    the first; 'EVER ' = followed by another word); an edge that is a letter or
    digit must sit on a word boundary. Plain substring matching painted LONE
    STAR and KEYSTONE as box ships ('ONE ') and FOREVER as Evergreen ('EVER ')."""
    for k in keys:
        pat = ((r"(?<![A-Z0-9])" if k[:1].isalnum() else "") + re.escape(k)
               + (r"(?![A-Z0-9])" if k[-1:].isalnum() else ""))
        if re.search(pat, name):
            return True
    return False


def operator_of(name, kinds, sure=False):
    """(kind, zones, note) for the first operator of one of these kinds whose
    keyword is in the name, else None. curator.category() asks this too, with
    sure=True (skip the keys that cannot vouch for her type), so a ship's TYPE and
    her COLOURS come from one list and cannot drift apart. They had: ten of
    Matson's eleven were painted as bulk carriers in Matson navy."""
    n = (name or "").upper().strip()
    for keys, zones, note, kind in OPERATORS:
        if kind in kinds and has_word(n, *(k for k in keys if not (sure and k in _COLOUR_ONLY))):
            return kind, zones, note
    return None


def for_ship(name, ship_type):
    """Return the colour zones for this ship: type generic + operator override.
    Keys: hull, boot, house, funnel, band (accent band / funnel band), boxes
    (list of box masstones for container ships, or None = mixed generic),
    tail (Carnival whale-tail), note (why)."""
    lv = dict(GENERIC.get(ship_type, GENERIC["container"]))
    lv.setdefault("boxes", None)
    lv["note"] = "generic %s" % ship_type
    op = operator_of(name, (_KIND.get(ship_type),))
    if op:
        lv.update(op[1])
        lv["note"] = op[2]
    return lv
