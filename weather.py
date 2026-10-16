"""Live conditions from NDBC buoy 46014 (Point Arena, ~9 nmi off Sea Ranch).

Feeds the painting: wind sets whitecaps, wave height sets swell, and a fog
estimate softens the horizon and fades the ship. NDBC has no fog sensor, so
fog is inferred: dewpoint depression when a station reports dewpoint (air
within a degree of its dewpoint = the marine layer is down), else the
air-water spread.

Two lessons from the live feed (Sep 2026):
  * the newest row is often half empty. Wind reports every 10 minutes, waves
    only every 20-30, so each field is read from the newest row that HAS it,
    looking back LOOKBACK_ROWS.
  * sensors die for months. 46014 lost its air temperature, which silently
    pinned every painting at the default fog. When the home buoy cannot give a
    fog estimate we ask the neighbours (Bodega buoy, Arena Cove) before giving
    up, and when we do give up we SAY so: wx["fog_src"] == "default" and the
    caption drops the FOG/HAZE/CLEAR word rather than inventing one.
  * a buoy that goes adrift or dark leaves its last rows at the top of the file
    for weeks. Rows older than MAX_AGE_H are not weather, they are history.
Falls back to a calm default when nothing is reachable, never crashes."""
import datetime, urllib.request
import config

BASE = "https://www.ndbc.noaa.gov/data/realtime2/%s.txt"
HOME = config.BUOY                # default 46014, Point Arena: wind, waves, water temp
NEIGHBOURS = config.BUOY_NEIGHBOURS   # default Bodega buoy (dewpoint), Arena Cove (air+water)
URL = BASE % HOME                 # kept for anything that imported it
LOOKBACK_ROWS = 14                # ~2 h at the 10-minute cadence
MAX_AGE_H = 3.0                   # a reading older than this is treated as missing
MAX_BYTES = 200_000               # the newest rows are at the top; never need more
DEFAULT = dict(wind_kn=10.0, wave_ft=4.0, fog=0.45, wind_dir="NW")
COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
# sane physical ranges; anything outside is a sensor glitch, treated as missing
RANGE = dict(WSPD=(0, 60), WDIR=(0, 360), WVHT=(0, 20), ATMP=(-10, 45),
             WTMP=(0, 35), DEWP=(-20, 40))


def _f(v, key=None):
    try:
        x = None if v in ("MM", "", None) else float(v)
    except ValueError:
        return None
    if x is not None and key in RANGE and not (RANGE[key][0] <= x <= RANGE[key][1]):
        return None
    return x


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _age_h(r, now):
    """Hours since this row was observed (NDBC stamps rows in UTC), or None for a
    line whose stamp cannot be read."""
    try:
        t = datetime.datetime(*(int(r[k]) for k in ("YY", "MM", "DD", "hh", "mm")),
                              tzinfo=datetime.timezone.utc)
    except (KeyError, ValueError):
        return None
    return (now - t).total_seconds() / 3600.0


def _station(station, timeout):
    """Newest non-missing value per field from one station's realtime file."""
    raw = urllib.request.urlopen(BASE % station, timeout=timeout).read(MAX_BYTES)
    rows = raw.decode("ascii", "replace").splitlines()
    hdr = rows[0].lstrip("#").split()
    out, now = {}, _now()
    for line in rows[2:2 + LOOKBACK_ROWS]:          # rows[1] is the units row
        r = dict(zip(hdr, line.split()))
        age = _age_h(r, now)
        if age is None:
            continue                                # a garbled line says nothing about the next
        if age > MAX_AGE_H:
            break                                   # newest first: the rest are older still
        for k in RANGE:
            if k not in out:
                v = _f(r.get(k), k)
                if v is not None:
                    out[k] = v
    return out


def _fog_from(obs):
    """Fog estimate 0.15-0.9 from one station's readings, or None."""
    atmp, dewp, wtmp = obs.get("ATMP"), obs.get("DEWP"), obs.get("WTMP")
    if atmp is not None and dewp is not None:       # humidity: the better signal
        return float(min(0.9, max(0.15, 0.82 - 0.16 * max(0.0, atmp - dewp))))
    if atmp is not None and wtmp is not None:       # air near/below water temp
        return float(min(0.9, max(0.15, 0.75 - 0.35 * (atmp - wtmp))))
    return None


def fetch(timeout=10):
    wx = dict(DEFAULT)
    src = dict(wind="default", wave="default", fog="default")
    try:
        home = _station(HOME, timeout)
    except Exception:
        home = {}
    if home.get("WSPD") is not None:
        wx["wind_kn"] = round(home["WSPD"] * 1.94384, 1); src["wind"] = HOME
        if home.get("WDIR") is not None:
            wx["wind_dir"] = COMPASS[int((home["WDIR"] % 360) / 22.5 + 0.5) % 16]
    if home.get("WVHT") is not None:
        wx["wave_ft"] = round(home["WVHT"] * 3.28084, 1); src["wave"] = HOME
    fog = _fog_from(home)
    if fog is not None:
        src["fog"] = HOME
    else:
        for st in NEIGHBOURS:                       # only when the home buoy can't say
            try:
                fog = _fog_from(_station(st, min(timeout, 8)))
            except Exception:
                fog = None
            if fog is not None:
                src["fog"] = st
                break
    if fog is not None:
        wx["fog"] = fog
    wx["fog_src"], wx["src"] = src["fog"], src
    cond = "FOG" if wx["fog"] > 0.65 else "MIST" if wx["fog"] > 0.45 else "HAZE" if wx["fog"] > 0.3 else "CLEAR"
    # never invent a fact silently: the painting may use a default, the caption may not
    parts = []
    if src["wind"] != "default":
        parts.append("%s %d KN" % (wx["wind_dir"], round(wx["wind_kn"])))
    if src["wave"] != "default":
        parts.append("SEAS %d FT" % round(wx["wave_ft"]))
    if src["fog"] != "default":
        parts.append(cond)
    wx["label"] = " · ".join(parts) or "NO BUOY REPORT"
    return wx


if __name__ == "__main__":
    print(fetch())
