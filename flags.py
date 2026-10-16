"""Tiny painted flag icons for the info block, keyed by MMSI MID country.

Drawn as gouache blocks with the same wet edge as the rest of the picture so
they sit in the painting, not as pasted-on emoji. Simplified to what reads at
~26x17 px and survives six inks: stripes, cantons, one bold device. Flags of
convenience dominate this coast (Panama, Liberia, Marshall Islands, Bahamas,
Malta, Singapore, Hong Kong), plus the majors."""

import numpy as np

# ISO-3166 alpha-2 -> painter. Colours are our A2 pigments, not screen brights.
RED   = (0.78, 0.22, 0.16)
BLUE  = (0.18, 0.28, 0.62)
YELL  = (0.90, 0.76, 0.20)
GREEN = (0.20, 0.50, 0.28)
WHITE = (0.965, 0.955, 0.935)
INK   = (0.13, 0.12, 0.14)
ORNGE = (0.85, 0.45, 0.15)

# a flag is a list of (x0,y0,x1,y1,colour) rects in 0..1 flag space, painted in order
def _stripes_h(cols):
    n = len(cols)
    return [(0, i / n, 1, (i + 1) / n, c) for i, c in enumerate(cols)]

def _stripes_v(cols):
    n = len(cols)
    return [(i / n, 0, (i + 1) / n, 1, c) for i, c in enumerate(cols)]

FLAGS = {
    "PA": [(0,0,.5,.5,WHITE),(.5,0,1,.5,RED),(0,.5,.5,1,BLUE),(.5,.5,1,1,WHITE)],   # Panama (stars omitted)
    "LR": _stripes_h([RED,WHITE]*5 + [RED]) + [(0,0,.42,.55,BLUE)],                # Liberia
    "MH": [(0,0,1,1,BLUE),(0,.62,.55,.78,ORNGE),(0,.78,.55,.9,WHITE)],              # Marshall Is. (diag simplified)
    "BS": _stripes_h([BLUE,YELL,BLUE]) + [(0,0,.32,1,INK)],                          # Bahamas
    "MT": _stripes_v([WHITE,RED]),                                                    # Malta
    "SG": _stripes_h([RED,WHITE]),                                                    # Singapore
    "HK": [(0,0,1,1,RED),(.32,.3,.62,.62,WHITE)],                                     # Hong Kong (bauhinia as white bloom)
    "US": _stripes_h([RED,WHITE]*6+[RED]) + [(0,0,.45,.54,BLUE)],                     # USA
    "CN": [(0,0,1,1,RED),(.08,.1,.28,.34,YELL)],                                      # China
    "JP": [(0,0,1,1,WHITE),(.33,.28,.67,.72,RED)],                                    # Japan
    "GB": [(0,0,1,1,BLUE),(0,.4,1,.6,RED),(.42,0,.58,1,RED)],                         # UK (simplified)
    "GR": _stripes_h([BLUE,WHITE]*4+[BLUE]) + [(0,0,.4,.55,BLUE)],                    # Greece
    "CY": [(0,0,1,1,WHITE),(.3,.3,.7,.55,ORNGE)],                                     # Cyprus
    "MX": _stripes_v([GREEN,WHITE,RED]),                                              # Mexico
    "CA": _stripes_v([RED,WHITE,WHITE,RED]) + [(.4,.3,.6,.7,RED)],                    # Canada
    "KR": [(0,0,1,1,WHITE),(.33,.28,.67,.72,RED)],                                    # Korea (taegeuk simplified)
    "NL": _stripes_h([RED,WHITE,BLUE]),                                               # Netherlands
    "DE": _stripes_h([INK,RED,YELL]),                                                 # Germany
    "FR": _stripes_v([BLUE,WHITE,RED]),                                               # France
    "IT": _stripes_v([GREEN,WHITE,RED]),                                              # Italy
    "NO": [(0,0,1,1,RED),(.3,0,.42,1,WHITE),(0,.42,1,.58,WHITE),(.33,0,.39,1,BLUE),(0,.45,1,.55,BLUE)],  # Norway
    "DK": [(0,0,1,1,RED),(.3,0,.4,1,WHITE),(0,.44,1,.56,WHITE)],                     # Denmark
    "AU": [(0,0,1,1,BLUE),(0,0,.5,.5,RED),(0,.2,.5,.3,WHITE),(.2,0,.3,.5,WHITE)],   # Australia (crude)
    "BM": [(0,0,1,1,RED),(0,0,.5,.5,BLUE)],                                           # Bermuda
    "KY": [(0,0,1,1,BLUE),(0,0,.5,.5,RED)],                                           # Cayman
    "TW": [(0,0,1,1,RED),(0,0,.5,.5,BLUE)],                                           # Taiwan
    "RU": _stripes_h([WHITE,BLUE,RED]),                                               # Russia
    "IN": _stripes_h([ORNGE,WHITE,GREEN]),                                            # India
    "VN": [(0,0,1,1,RED),(.35,.3,.65,.65,YELL)],                                      # Vietnam
    "AG": [(0,0,1,1,RED),(.5-.35,0,.5+.35,.7,INK),(.5-.35,.35,.5+.35,.5,YELL),(.5-.35,.5,.5+.35,.7,WHITE)],  # Antigua & Barbuda
    "VU": _stripes_h([RED,GREEN]) + [(0,.4,1,.6,INK)],                                # Vanuatu
    "TV": [(0,0,1,1,BLUE),(0,0,.5,.5,BLUE),(0,.2,.5,.3,WHITE)],                       # Tuvalu (crude)
}
FLAGS["ES"] = _stripes_h([RED,YELL,YELL,RED])                                          # Spain
FLAGS["PT"] = _stripes_v([GREEN,RED,RED])                                              # Portugal
FLAGS["PH"] = _stripes_h([BLUE,RED]) + [(0,0,.4,1,WHITE)]                              # Philippines

def paint_flag(cv, country, x, y, w=26, h=17, seed=0):
    """Paint the flag at top-left (x, y); returns True if we knew it."""
    from art_directions import crisp as flat
    spec = FLAGS.get((country or "").upper())
    if not spec:
        return False
    for (a, b, c_, d, col) in spec:
        poly = [(x + a * w, y + b * h), (x + c_ * w, y + b * h),
                (x + c_ * w, y + d * h), (x + a * w, y + d * h)]
        flat(cv, poly, col, seed=seed)
    # a hairline ink border finds the flag against pale paper
    border = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    return True
