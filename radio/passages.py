#!/usr/bin/env python3
"""The radio's own diary: every ship in range, at her closest, day by day.

Runs every 2 minutes on the radio Pi (passages.timer). Writes
~/status/passages/2026-11-23.json, which health-server already serves on :8101, and keeps
KEEP_DAYS of them. The frame's own archive has a hole wherever the frame was unplugged
(eleven days in Nov 2026); this has none, so the frame can come back and fill in.

One entry per ship per day: the record from her closest approach that day, and from her
closest in daylight if that was another moment. No weather: the buoy keeps its own 45 days.
Standard library only, shared with nothing: a receiver should not depend on the painter."""
import datetime, json, math, os, sys, urllib.request

URL = os.environ.get("AIS_URL", "http://localhost:8100/api/ships.json")
OUT = os.environ.get("PASSAGES_DIR", os.path.expanduser("~/status/passages"))
LAT, LON = float(os.environ.get("LAT", 38.72)), float(os.environ.get("LON", -123.45))
RANGE_NMI = float(os.environ.get("MAX_RANGE_NMI", 100))
KEEP_DAYS, MAX_A_DAY = 30, 600
MAX_AGE_S = 10 * 60
FIELDS = ("mmsi", "shipname", "callsign", "imo", "country", "shiptype", "to_bow", "to_stern", "to_port",
          "to_starboard", "draught", "status", "destination", "eta_month", "eta_day", "eta_hour", "eta_minute",
          "lat", "lon", "heading", "cog", "speed", "last_signal", "level")
STATIC = FIELDS[1:13] + FIELDS[13:17]


def nmi(lat, lon):
    a, b, c, d = map(math.radians, (LAT, LON, lat, lon))
    x = math.sin(a) * math.sin(c) + math.cos(a) * math.cos(c) * math.cos(d - b)
    return 3440.0 * math.acos(min(1.0, max(-1.0, x)))


def daylight(t):
    """Is the sun up? Local clock; good to a few minutes, which is all this needs."""
    n, g = t.timetuple().tm_yday, 0
    g = 2 * math.pi / 365.0 * (n - 1)
    dec = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
    la = math.radians(LAT)
    x = (math.cos(math.radians(90.833)) - math.sin(la) * math.sin(dec)) / (math.cos(la) * math.cos(dec))
    half = math.degrees(math.acos(max(-1.0, min(1.0, x)))) / 15.0
    off = (t.astimezone().utcoffset() or datetime.timedelta()).total_seconds() / 3600.0
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                   - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g)) / 60.0
    noon = 12 - LON / 15.0 + off - eq
    h = t.hour + t.minute / 60.0
    return noon - half <= h <= noon + half


def load(p):
    try:
        d = json.load(open(p))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def note(day, ships, now):
    """Fold one look at the sea into the day's diary. Returns True if anything changed."""
    stamp, lit, changed = now.isoformat(timespec="seconds"), daylight(now), False
    for s in ships:
        if not isinstance(s, dict):
            continue
        r = {k: s.get(k) for k in FIELDS if s.get(k) not in (None, "")}
        try:
            m, lat, lon = int(r["mmsi"]), float(r["lat"]), float(r["lon"])
            age = float(r.get("last_signal") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if not 201000000 <= m <= 775999999 or abs(lat) > 90 or abs(lon) > 180 or not 0 <= age <= MAX_AGE_S:
            continue
        d = nmi(lat, lon)
        if d != d or d > RANGE_NMI:
            continue
        e = day.get(str(m))
        if e is None:
            if len(day) >= MAX_A_DAY:
                continue
            e = day[str(m)] = {"first": stamp, "looks": 0}
            changed = True
        e["last"] = stamp
        e["looks"] += 1
        for rec in (e.get("record"), (e.get("day") or {}).get("record")):
            if rec:                                   # her name and size come in a later packet
                for k in STATIC:
                    if k in r and k not in rec:
                        rec[k] = r[k]
                        changed = True
        for slot, use in (("near", True), ("day", lit)):
            if not use:
                continue
            old = e.get("nmi") if slot == "near" else (e.get("day") or {}).get("nmi")
            if old is not None and d >= old - 0.2:        # 0.2: not worth wearing the card for
                continue
            prev = e.get("record") if slot == "near" else (e.get("day") or {}).get("record")
            rec = dict({k: v for k, v in (prev or e.get("record") or {}).items() if k in STATIC}, **r)
            if slot == "near":
                e.update(nmi=round(d, 1), at=stamp, record=rec)
            else:
                e["day"] = {"nmi": round(d, 1), "at": stamp, "record": rec}
            changed = True
    return changed


def main(now=None):
    now = now or datetime.datetime.now()
    raw = urllib.request.urlopen(URL, timeout=15).read(4 * 1024 * 1024)
    ships = json.loads(raw).get("ships") or []
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, now.strftime("%Y-%m-%d.json"))
    day = load(p)
    new = not os.path.exists(p)
    if note(day, ships[:2000], now) or new:              # a file for every day the radio was awake, ships or none
        save(p, day)
    cut = (now - datetime.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d.json")
    for f in os.listdir(OUT):
        if f.endswith(".json") and len(f) == 15 and f < cut:
            os.remove(os.path.join(OUT, f))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("passages: %s: %s" % (type(e).__name__, e))
        sys.exit(1)
