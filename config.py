"""Where this frame lives, read from the environment (~/.curator/config.env via
the systemd units) with the Sea Ranch build's values as defaults. Anything
malformed or out of range falls back to the default rather than crashing the
hourly paint: a typo in config.env should cost a setting, not the wall."""
import os, re


def _num(name, default, lo, hi, cast=float):
    try:
        v = cast(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default
    return v if lo <= v <= hi else default


def _stations(raw):
    """NDBC station ids only (letters and digits); anything else is dropped,
    since these are pasted into a URL."""
    return tuple(s for s in (x.strip().upper() for x in raw.split(","))
                 if re.fullmatch(r"[A-Z0-9]{4,6}", s))


LAT = _num("LAT", 38.72, -90.0, 90.0)
LON = _num("LON", -123.45, -180.0, 180.0)
MAX_RANGE_NMI = _num("MAX_RANGE_NMI", 100.0, 1.0, 1000.0)   # the loft antenna ducts 400+ nmi
QUIET_START = _num("QUIET_START", 23, 0, 23, int)            # hold the image from this hour...
QUIET_END = _num("QUIET_END", 7, 0, 23, int)                 # ...until this one
# The words in the upper-right corner of every painting. Printable characters
# only, kept short enough to sit clear of the ship's name.
PLACE = (re.sub(r"[^\w .,'&/-]", "", os.environ.get("PLACE", "")).strip().upper()[:28]
         or "THE SEA RANCH")
# Compass bearing from the wall out to sea. It decides which way a ship sails
# across the picture and whether the sun rises or sets over the water.
SEA_BEARING = _num("SEA_BEARING", 247.5, 0.0, 360.0)

BUOY = (_stations(os.environ.get("BUOY", "")) or ("46014",))[0]
# Stations to ask for a fog estimate when the home buoy's sensors are out.
# The defaults only make sense for the default buoy; on another coast, list
# your own in BUOY_NEIGHBOURS or go without.
BUOY_NEIGHBOURS = _stations(os.environ.get(
    "BUOY_NEIGHBOURS", "46013,ANVC1" if BUOY == "46014" else ""))


def sails_right(heading):
    """True when a ship on this heading crosses the picture left to right. Face
    the sea: anything making ground toward your right hand sails right. Ships
    coming nearly straight in or out (within 22.5 degrees of the line of sight)
    keep the default, bow left. From the Sea Ranch bluff this is the original
    rule exactly: heading > 270 or < 45, i.e. northbound."""
    return 22.5 < (heading - SEA_BEARING) % 360.0 < 157.5


SEA_IS_EAST = 0.0 < SEA_BEARING < 180.0     # sunrise, not sunset, is over the water


def is_quiet(hour):
    if QUIET_START == QUIET_END:
        return False
    if QUIET_START > QUIET_END:                    # wraps midnight: 23 -> 7
        return hour >= QUIET_START or hour < QUIET_END
    return QUIET_START <= hour < QUIET_END
