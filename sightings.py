#!/usr/bin/env python3
"""PASSING SHIPS sightings logger — runs every 5 minutes on the frame Pi.

Every ship the radio hears becomes a durable sighting in the archive
(~/.curator/sightings.json), keyed by MMSI: first/last seen, closest
approach to the Sea Ranch, and the AIS record + weather captured at that
closest moment (so the painting can show the conditions she passed in).
The hourly curator picks from this archive, not just from who is in range
this minute. Entries older than KEEP_DAYS are pruned.
"""
import datetime, json, math, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config
STATE_DIR = os.path.expanduser("~/.curator")
os.makedirs(STATE_DIR, exist_ok=True)
ARCHIVE = os.path.join(STATE_DIR, "sightings.json")
AIS_URL = os.environ.get("AIS_URL", "http://localhost:8100/api/ships.json")
HOME_LAT, HOME_LON = config.LAT, config.LON  # default: the Sea Ranch bluff
LOG_RANGE_NMI = config.MAX_RANGE_NMI           # ducted skip is not a passer
MAX_AGE_S = 20 * 60                            # stale positions ignored
KEEP_DAYS = 14
MAX_ARCHIVE = 5000                             # ships remembered at once; the oldest go first
# what a ship says about herself (AIS messages 5 / 24), as opposed to where she is
STATIC_KEYS = ("shipname", "callsign", "imo", "shiptype", "to_bow", "to_stern",
               "to_port", "to_starboard", "draught", "destination", "country",
               "eta_month", "eta_day", "eta_hour", "eta_minute")


def load():
    try:
        return json.load(open(ARCHIVE))
    except Exception:
        return {}


def save(a):
    tmp = ARCHIVE + ".tmp"
    with open(tmp, "w") as f:         # closed (and so flushed) before the swap
        json.dump(a, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ARCHIVE)


def nmi(lat, lon):
    la1, lo1 = map(math.radians, (HOME_LAT, HOME_LON))
    la2, lo2 = map(math.radians, (lat, lon))
    c = math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return 3440.0 * math.acos(min(1.0, max(-1.0, c)))


RUN = os.path.join(STATE_DIR, "sightings-run.json")     # when this last ran: a gap is a power cut
GAP_MIN = 20


def passages(day, timeout=10):
    """One day of the radio's own diary (radio/passages.py), {} if it has none."""
    import re, curator
    url = re.sub(r":8100/.*$", ":8101/passages/%s.json" % day, AIS_URL)
    try:
        raw = urllib.request.urlopen(url, timeout=timeout).read(curator.MAX_FEED_BYTES + 1)
        d = json.loads(raw) if len(raw) <= curator.MAX_FEED_BYTES else None
    except Exception:
        return None                             # no answer, which is not the same as an empty sea
    return d if isinstance(d, dict) else None


def entry(e):
    """One diary entry, every field checked: it came over the network."""
    import curator
    if not isinstance(e, dict):
        return None
    def one(x):
        rec = curator.clean_record(x.get("record")) if isinstance(x, dict) else None
        d, at = (x.get("nmi"), x.get("at")) if isinstance(x, dict) else (None, None)
        try:
            datetime.datetime.fromisoformat(at)
        except (TypeError, ValueError):
            return None
        if not rec or isinstance(d, bool) or not isinstance(d, (int, float)) or not 0 <= d <= LOG_RANGE_NMI:
            return None
        return dict(nmi=round(float(d), 1), at=at[:19], record=rec)
    near, day = one(e), one(e.get("day"))
    if not near:
        return None
    last = e.get("last") if isinstance(e.get("last"), str) else near["at"]
    first = e.get("first") if isinstance(e.get("first"), str) else near["at"]
    return dict(near=near, day=day, first=first[:19], last=last[:19])


def catch_up(arch, since, now, weather_at):
    """The frame was off: read the hours it missed out of the radio's diary."""
    import curator
    added, d = 0, since.date()
    while d <= now.date():
        for e in filter(None, map(entry, (passages(d.isoformat()) or {}).values())):
            rec = e["near"]["record"]
            mmsi = str(rec["mmsi"])
            old = arch.get(mmsi)
            if old and (old.get("closest_nmi") or 1e9) <= e["near"]["nmi"] and old.get("last_seen", "") >= e["near"]["at"][:13]:
                continue
            if e["last"] < since.isoformat() and old:
                continue
            cat, label = curator.category(rec)
            a = arch[mmsi] = dict(old or {}, mmsi=rec["mmsi"], name=rec["shipname"] or (old or {}).get("name"),
                                  category=cat, label=label, record=rec, closest_nmi=e["near"]["nmi"],
                                  closest_at=e["near"]["at"], wx=weather_at(e["near"]["at"]))
            a.setdefault("first_seen", e["first"])
            a["last_seen"] = max(e["last"], (old or {}).get("last_seen", ""))
            a.pop("day", None)
            if e["day"]:
                a["day"] = dict(e["day"], wx=weather_at(e["day"]["at"]))
            added += 1
        d += datetime.timedelta(days=1)
    return added


def weather_then():
    """weather.fetch for past moments, one request per station per run."""
    import weather
    got = {}
    def at(iso):
        hour = iso[:13]
        if hour not in got:
            try:
                got[hour] = weather.fetch(timeout=15, at=iso)
            except Exception:
                got[hour] = None
        return got[hour]
    return at


def main():
    now = datetime.datetime.now()
    stamp = now.isoformat(timespec="seconds")
    import curator                      # shared feed reader and category(), so both agree
    try:
        ships = curator.read_feed()
    except Exception as e:
        print(f"{stamp}  no AIS feed ({e})"); return
    arch = load()
    try:
        ran = datetime.datetime.fromisoformat(json.load(open(RUN))["at"])
    except Exception:
        ran = None
    if ran and (now - ran).total_seconds() > GAP_MIN * 60:
        since = max(ran, now - datetime.timedelta(days=KEEP_DAYS))
        try:
            print("%s  back after %.1f h: %d ships from the radio's diary" % (
                stamp, (now - ran).total_seconds() / 3600.0, catch_up(arch, since, now, weather_then())))
        except Exception as ex:
            print(f"{stamp}  catch-up failed ({ex})")
    wx = None
    seen = 0
    for s in map(curator.clean_record, ships):
        if not s or s["lat"] is None or s["lon"] is None:
            continue
        mmsi = str(s["mmsi"])
        if (s.get("last_signal") or 0) > MAX_AGE_S or abs(s["lat"]) > 90 or abs(s["lon"]) > 180:
            continue                  # AIS sends lat 91 / lon 181 for "no position"
        dist = nmi(s["lat"], s["lon"])
        if dist > LOG_RANGE_NMI:
            continue
        seen += 1
        # A ship sends her position every few seconds but her name only every six
        # minutes, so a short pass is often heard nameless first. Log her by MMSI
        # now and let the name catch up (the Aug 7 miss: two ships at 09:50 never
        # entered the pool). The curator still refuses to paint her until named.
        name = s["shipname"]
        e = arch.get(mmsi)
        if e is None:
            e = arch[mmsi] = dict(mmsi=int(mmsi), name=name or None,
                                  first_seen=stamp, closest_nmi=None)
        e["last_seen"] = stamp
        e["name"] = name or e.get("name")
        rec = e.get("record")
        if rec and name and not (rec.get("shipname") or "").strip():
            for k in STATIC_KEYS:     # her name packet arrived: fill in the saved record
                if s.get(k) not in (None, ""):
                    rec[k] = s[k]
        cat, label = curator.category(rec if rec and not name else s)
        e["category"], e["label"] = cat, label
        # keep the record from her closest approach: that's the passing moment
        if e.get("closest_nmi") is None or dist < e["closest_nmi"]:
            if wx is None:
                try:
                    import weather
                    wx = weather.fetch(timeout=8)
                except Exception:
                    wx = None
            e["closest_nmi"] = round(dist, 1)
            e["closest_at"] = stamp
            new = dict(s)
            if rec:                   # a closer fix must not forget what she already told us
                for k in STATIC_KEYS:
                    if new.get(k) in (None, "", 0) and rec.get(k) not in (None, "", 0):
                        new[k] = rec[k]
            e["record"] = new
            if wx:
                e["wx"] = wx
        # ...and from her closest in daylight, if she passes in the night as well
        import light
        lit = light.for_iso(now)["name"] != "night"
        old = e.get("day") if isinstance(e.get("day"), dict) else None
        if old and old.get("at", "") < (now - datetime.timedelta(days=curator.SOURCE_DAYS)).isoformat():
            old = None                # a daylight view from an earlier voyage is not this one
        if lit and (old is None or dist < old["nmi"]):
            if wx is None:
                try:
                    import weather
                    wx = weather.fetch(timeout=8)
                except Exception:
                    wx = None
            e["day"] = dict(nmi=round(dist, 1), at=stamp, record=dict(s), **({"wx": wx} if wx else {}))
        for r_ in (e["day"]["record"],) if e.get("day") else ():
            for k in STATIC_KEYS:
                if r_.get(k) in (None, "", 0) and (e.get("record") or {}).get(k) not in (None, "", 0):
                    r_[k] = e["record"][k]
    # prune the old
    cutoff = (now - datetime.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    for k in [k for k, v in arch.items() if v.get("last_seen", "") < cutoff]:
        del arch[k]
    for k in sorted(arch, key=lambda k: arch[k].get("last_seen", ""))[:max(0, len(arch) - MAX_ARCHIVE)]:
        del arch[k]
    save(arch)
    with open(RUN + ".tmp", "w") as f:
        json.dump({"at": stamp}, f)
    os.replace(RUN + ".tmp", RUN)
    print(f"{stamp}  logged {seen} in range; archive holds {len(arch)}")


if __name__ == "__main__":
    main()
