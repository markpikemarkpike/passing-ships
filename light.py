"""The light of the hour, for a west-facing coast (the Sea Ranch bluff).

A ship spotted at 8:20pm should hang in 8:20pm's light. This module turns a
local time into a small palette the scene understands: what the sky pours,
what colour glows at the horizon, whether the sun is low over the water
(west = out to sea, so evening sun sits ON the horizon and lays a glitter
path), and a thin unifying glaze that ties ship, sea and sky into one hour.

(Set SEA_BEARING in config.env if your sea is to the east; the day is mirrored.)
Dawn is different from dusk here: the sun rises behind the ridge, so the
morning sea gets cool rose alpenglow and NO disc; the evening sun goes down
into the Pacific in front of us. Times are for July at 38.7N; the buckets
are broad on purpose (a painting, not an ephemeris)."""

# masstones borrowed from scene.py's palette family (kept local: no import loop)
CREAM   = (0.945, 0.90, 0.80)
PEACH   = (0.94, 0.78, 0.68)
ROSE    = (0.90, 0.70, 0.72)
COPPER  = (0.86, 0.50, 0.38)   # leans red: six inks have no orange
LILAC   = (0.72, 0.68, 0.80)
STEEL   = (0.60, 0.66, 0.76)
INKBLUE = (0.30, 0.36, 0.52)
SKYBLUE = (0.60, 0.71, 0.83)


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


# hour -> light. sun_h: sun height above the horizon in units of "sky height"
# (0 = on the sea, 0.35 = mid-morning/late-afternoon high). None = below horizon.
_TABLE = [
    # (start_hour, name, sky_top, horizon_glow, glow_strength, sun_h, glitter, glaze, glaze_amt)
    (0.0,  "night",   INKBLUE, STEEL,  0.06, None, 0.0, INKBLUE, 0.10),
    (5.0,  "predawn", STEEL,   LILAC,  0.10, None, 0.0, LILAC,   0.06),
    (5.9,  "dawn",    SKYBLUE, ROSE,   0.18, None, 0.0, ROSE,    0.06),   # alpenglow, no disc
    (7.2,  "morning", SKYBLUE, CREAM,  0.14, None, 0.0, None,    0.00),
    (10.5, "midday",  SKYBLUE, CREAM,  0.12, None, 0.0, None,    0.00),
    (16.0, "late",    SKYBLUE, CREAM,  0.16, 0.30, 0.05, None,   0.00),
    (18.6, "golden",  SKYBLUE, PEACH,  0.20, 0.14, 0.30, PEACH,  0.04),
    (20.1, "sunset",  LILAC,   COPPER, 0.26, 0.02, 0.50, COPPER, 0.06),   # disc on the sea
    (20.7, "dusk",    STEEL,   ROSE,   0.20, None, 0.08, ROSE,   0.07),
    (21.6, "night",   INKBLUE, STEEL,  0.06, None, 0.0, INKBLUE, 0.10),
]


# The table above is the mid-July day (sunrise ~6:00, sunset ~8:39pm local). For
# any other date the buckets slide with the real sun: morning rows ride on
# sunrise, evening rows ride on sunset, midday stays put. Without this a
# December ship at 5:30pm hung in full afternoon light and an 8pm ship got a
# sun disc on the sea three hours after dark.
import config
HOME_LAT, HOME_LON = config.LAT, config.LON
_JULY_RISE, _JULY_SET = 6.0, 20.65      # sun_times(July 15)
_RIDES = {"predawn": "rise", "dawn": "rise", "morning": "rise",
          "late": "set", "golden": "set", "sunset": "set", "dusk": "set"}


def sun_times(date):
    """(sunrise, sunset) as local decimal clock hours for a date at the bluff.
    NOAA's short solar formula: good to a couple of minutes, no dependencies.
    Local = whatever the machine's timezone says for that date (DST included)."""
    import math, time, datetime as _dt
    n = date.timetuple().tm_yday
    g = 2 * math.pi / 365.0 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    lat = math.radians(HOME_LAT)
    x = math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(decl)) - math.tan(lat) * math.tan(decl)
    ha = math.degrees(math.acos(max(-1.0, min(1.0, x))))
    rise_utc = (720 - 4 * (HOME_LON + ha) - eqtime) / 60.0
    set_utc = (720 - 4 * (HOME_LON - ha) - eqtime) / 60.0
    noon = _dt.datetime(date.year, date.month, date.day, 12)
    off = time.localtime(time.mktime(noon.timetuple())).tm_gmtoff / 3600.0
    return (rise_utc + off) % 24, (set_utc + off) % 24


def _table_for(date):
    if date is None:
        return _TABLE
    rise, sset = sun_times(date)
    out = []
    for r in _TABLE:
        ride = _RIDES.get(r[1]) if r[0] < 21.0 else "set"      # the closing "night" row
        shift = (rise - _JULY_RISE) if ride == "rise" else (sset - _JULY_SET) if ride == "set" else 0.0
        out.append((r[0] + shift,) + r[1:])
    # a short winter day can push "late" back past "midday": keep the order sane
    out.sort(key=lambda r: r[0])
    return out


def for_hour(hour, date=None):
    """hour: local decimal hour (20.5 = 8:30pm). date: a datetime.date to slide
    the buckets with the season; None = the fixed mid-July table (what the test
    scenes in fleet.py use, so their renders stay reproducible)."""
    if date is not None and config.SEA_IS_EAST:
        # The table is written for a coast that faces the sunset. Where the sea
        # is to the east the day runs the other way round: the disc and its
        # glitter path belong to sunrise, the discless alpenglow to dusk.
        hour = sum(sun_times(date)) - hour
    table = _table_for(date)
    row = table[0]
    for r in table:
        if hour >= r[0]:
            row = r
    _, name, top, glow, gs, sun_h, glitter, glaze, gz = row
    return dict(name=name, sky_top=top, horizon=glow, glow_strength=gs,
                sun_h=sun_h, glitter=glitter, glaze=glaze, glaze_amt=gz)


def for_iso(iso_or_dt=None):
    """Light for an ISO timestamp / datetime; None = now (local clock)."""
    import datetime as _dt
    if iso_or_dt is None:
        t = _dt.datetime.now()
    elif isinstance(iso_or_dt, str):
        t = _dt.datetime.fromisoformat(iso_or_dt)
    else:
        t = iso_or_dt
    lt = for_hour(t.hour + t.minute / 60.0, date=t.date())
    if lt["name"] in DARK:                  # the sun is down: the moon is the light, and ships show theirs
        lt["moon"] = moon(t)
    return lt


DARK = ("dusk", "night", "predawn")


def moon(t):
    """Where the moon really is and how much of it is lit, for a local datetime at the bluff.
    alt: degrees above the horizon. az: degrees clockwise from north. fraction: 0 new, 1 full.
    limb: which way the bright edge faces, degrees anticlockwise from straight up as you look at it.
    The usual low-precision series (about a degree): a painting, not an ephemeris. No dependencies."""
    import math as m, time
    rad = m.pi / 180.0
    d = time.mktime(t.timetuple()) / 86400.0 - 0.5 + 2440588 - 2451545          # days since J2000, UT
    e = rad * 23.4397
    ra = lambda l, b: m.atan2(m.sin(l) * m.cos(e) - m.tan(b) * m.sin(e), m.cos(l))
    dec = lambda l, b: m.asin(m.sin(b) * m.cos(e) + m.cos(b) * m.sin(e) * m.sin(l))
    M = rad * (357.5291 + 0.98560028 * d)                                       # the sun
    Ls = M + rad * (1.9148 * m.sin(M) + 0.02 * m.sin(2 * M) + 0.0003 * m.sin(3 * M)) + rad * 102.9372 + m.pi
    sra, sdec = ra(Ls, 0), dec(Ls, 0)
    Mm = rad * (134.963 + 13.064993 * d)                                        # the moon
    l = rad * (218.316 + 13.176396 * d) + rad * 6.289 * m.sin(Mm)
    b = rad * 5.128 * m.sin(rad * (93.272 + 13.229350 * d))
    dist = 385001 - 20905 * m.cos(Mm)
    mra, mdec = ra(l, b), dec(l, b)
    phi = rad * HOME_LAT
    Hh = rad * (280.16 + 360.9856235 * d) + rad * HOME_LON - mra                # hour angle
    alt = m.asin(m.sin(phi) * m.sin(mdec) + m.cos(phi) * m.cos(mdec) * m.cos(Hh))
    az = m.atan2(m.sin(Hh), m.cos(Hh) * m.sin(phi) - m.tan(mdec) * m.cos(phi))  # from south, westward
    pa = m.atan2(m.sin(Hh), m.tan(phi) * m.cos(mdec) - m.sin(mdec) * m.cos(Hh))
    ph = m.acos(m.sin(sdec) * m.sin(mdec) + m.cos(sdec) * m.cos(mdec) * m.cos(sra - mra))
    inc = m.atan2(149598000 * m.sin(ph), dist - 149598000 * m.cos(ph))
    ang = m.atan2(m.cos(sdec) * m.sin(sra - mra), m.sin(sdec) * m.cos(mdec) - m.cos(sdec) * m.sin(mdec) * m.cos(sra - mra))
    return dict(alt=round(alt / rad, 1), az=round((az / rad + 180.0) % 360.0, 1), fraction=round((1 + m.cos(inc)) / 2, 3),
                waxing=bool(ang < 0), limb=round(((ang - pa) / rad) % 360.0, 1))


MIDDAY = for_hour(13.0)
