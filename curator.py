#!/usr/bin/env python3
"""PASSING SHIPS curator — runs at the top of every hour on the frame Pi.

Rule (Mark, Jul 30): once an hour, on the hour, hang the most interesting
ship currently in range. Container ships are welcome but never two in a
row. No scoring contest: variety beats containers, then closest wins. Quiet
overnight (holds one image). If nothing's out there, the last painting stays.
"""
import datetime, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config, liveries
from liveries import has_word
STATE_DIR = os.path.expanduser("~/.curator")
os.makedirs(STATE_DIR, exist_ok=True)
STATE = os.path.join(STATE_DIR, "state.json")
LOG = os.path.join(STATE_DIR, "log.txt")
AIS_URL = os.environ.get("AIS_URL", "http://localhost:8100/api/ships.json")
HEALTH_URL = re.sub(r":8100/.*$", ":8101/health.json", AIS_URL)
MAX_AGE_S = 20 * 60           # ignore ships silent for 20+ minutes


def log(msg):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save_state(st):
    """Atomic: a power cut mid-write must not wipe the painted history (an empty
    state.json reads as 'nothing ever painted' and the wall starts repeating)."""
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)


US_MIDS = ("303", "338", "366", "367", "368", "369")
_NUMBERS = ("lat", "lon", "heading", "cog", "speed", "shiptype", "to_bow", "to_stern",
            "last_signal", "to_port", "to_starboard", "draught", "status", "imo",
            "eta_month", "eta_day", "eta_hour", "eta_minute")
MAX_FEED_BYTES = 4 * 1024 * 1024     # a busy night is a few hundred ships, well under 1 MB
MAX_SHIPS = 2000


def tidy(raw, limit=20):
    """Text off the air, made safe to log, print and put in a caption. An AIS
    name or destination is at most 20 printable characters; anything longer, or
    carrying control characters, did not come from a ship."""
    if not isinstance(raw, str):
        return ""
    s = "".join(ch if ch.isprintable() else " " for ch in raw)
    return " ".join(s.split())[:limit].strip()


def real_name(raw):
    """Her name, or "" when the packet was garbled ('DEYUM*>V8Q49', Nov 2026): a ship
    with no name waits for a clean packet, and they come every six minutes."""
    s = " ".join(tidy(raw).replace("_", " ").split())
    if any(ch in "<>*^\\[]{}=;|~`" for ch in s) or not any(ch.isalnum() for ch in s):
        return ""
    return s


def read_feed():
    """ships.json from the radio Pi, as a list of raw records. Bounded in bytes and in
    ships: the frame is a small computer, and whoever answers at that address decides
    how much it is asked to swallow. Raises if there is no usable feed."""
    raw = urllib.request.urlopen(AIS_URL, timeout=15).read(MAX_FEED_BYTES + 1)
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("feed is over %d bytes" % MAX_FEED_BYTES)
    d = json.loads(raw)
    ships = d.get("ships") if isinstance(d, dict) else None
    return ships[:MAX_SHIPS] if isinstance(ships, list) else []


def read_health():
    """The radio Pi's own verdict on itself, every field checked before use.
    It arrives over the network like the ship feed does, so it gets the same
    treatment. {} = no opinion (server absent, or not saying anything sensible)."""
    try:
        h = json.loads(urllib.request.urlopen(HEALTH_URL, timeout=10).read(65536))
    except Exception:
        return {}
    if not isinstance(h, dict):
        return {}
    sil = h.get("silent_h")
    ok = isinstance(sil, (int, float)) and not isinstance(sil, bool) and 0 <= sil <= 9999
    return {"verdict": tidy(h.get("verdict"), 12), "detail": tidy(h.get("detail"), 120),
            "silent_h": float(sil) if ok else None}


def clean_record(s):
    """One ship from ships.json with every field the type the rest of the code
    assumes, or None if she has no usable MMSI. A field that is not what it
    should be becomes None (= she isn't saying). Only the fields named here come
    through: records are saved to the card, so nothing unexpected rides along. The
    curator and the sightings logger both read the feed through this, so one
    malformed record costs one ship, never the hourly paint."""
    if not isinstance(s, dict):
        return None
    s = {k: s.get(k) for k in ("mmsi", "shipname", "destination", "country", "callsign") + _NUMBERS}
    try:
        s["mmsi"] = int(s.get("mmsi") or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if not 201000000 <= s["mmsi"] <= 775999999:      # ship stations only (ITU country codes run 201-775).
        return None                                  # Buoys, aircraft and garbled packets fall outside.
    for k in _NUMBERS:
        v = s.get(k)
        if isinstance(v, bool):
            v = None
        elif not isinstance(v, (int, float)):
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
        s[k] = v if v is not None and v == v and abs(v) != float("inf") else None
    s["shiptype"] = int(s["shiptype"]) if s["shiptype"] is not None else None
    s["shipname"], s["destination"] = real_name(s.get("shipname")), tidy(s.get("destination"))
    s["country"], s["callsign"] = tidy(s.get("country"), 2), tidy(s.get("callsign"), 7)
    return s


def hull_length(s):
    """Metres from the AIS dimensions, or 0 when she hasn't given a real one
    (511 in either field means 'this much or more', not a measurement)."""
    bow, stern = s.get("to_bow") or 0, s.get("to_stern") or 0
    return bow + stern if 0 <= bow < 511 and 0 <= stern < 511 else 0


def course_of(s):
    """Degrees true for the arrow and the mirroring, or None when she isn't
    saying. AIS sends heading 511 and course 360 for 'not available', and a
    drifting hull's course is noise, so course only counts when she is moving
    (the same rule AIS-catcher's own map uses)."""
    h, c = s.get("heading"), s.get("cog")
    if isinstance(h, (int, float)) and 0 <= h < 360:
        return int(h)
    if isinstance(c, (int, float)) and 0 <= c < 360 and (s.get("speed") or 0) >= 1.0:
        return int(c)
    return None


def category(s):
    """Map an AIS record to one of our painter categories + a nice type label."""
    t = s.get("shiptype") or 0
    name = (s.get("shipname") or "").upper()
    mid = str(s.get("mmsi") or "")[:3]
    # Names first, they are the better evidence: cutters and warships both sail
    # under type 35 (military ops), so the code alone cannot tell them apart.
    if name.startswith(("CG ", "USCG ", "USCGC ", "CGC ")) or "COAST GUARD" in name:
        return "cutter", "Coast Guard Cutter"
    if name.startswith(("USS ", "USNS ")) or has_word(name, "WARSHIP", "NAVY"):
        return "naval", "Warship"
    # then the codes, US hulls only: law enforcement = the Coast Guard,
    # military ops = grey hulls up and down the coast
    if t == 55 and mid in US_MIDS:
        return "cutter", "Coast Guard Cutter"
    if t == 35 and mid in US_MIDS:
        return "naval", "Warship"
    # research / survey ships hide in the "other" codes; find them by name. A hull
    # that declares itself passenger, cargo, tanker, fishing or pleasure is believed
    # over a name that merely rhymes (MSC ATLANTIS is not the Woods Hole ship, and
    # the yacht FAIRWEATHER is not NOAA's). liveries.py knows the government fleets.
    if not (60 <= t <= 89 or t in (30, 36, 37)) and (
            liveries.operator_of(name, ("research",), sure=True) or
            any(k in name for k in ("SIKULIAQ", "R/V ", "R.V. ", "RESEARCH", "OCEANOGRAPH", "SURVEY",
                                    "ATLANTIS", "ROGER REVELLE", "SALLY RIDE", "BOB & BETTY",
                                    "OCEAN OBSERVER"))):
        return "research", "Research Vessel"
    # AIS has no code for a cable ship: they sail as passenger, cargo or "other". liveries.py
    # knows them by name. A hull that says it fishes, sails or is a pleasure boat is believed.
    if t not in (30, 36, 37) and not (0 < hull_length(s) < 60) and \
            liveries.operator_of(name, ("cable",), sure=True):
        return "cable", "Cable Layer"
    if 60 <= t <= 69:
        if 0 < hull_length(s) < 60:              # the whale-watch boat is not a liner
            return "excursion", "Passenger Vessel"
        return "cruise", "Cruise Ship"
    if t == 36:
        return "sailing", "Sailing Vessel"
    if t == 37:
        return "motoryacht", "Motor Yacht"
    if t == 30:
        return "fishing", "Fishing Vessel"
    # liveries.py knows the box fleets, ship by ship where the name carries no
    # company word (MAHIMAHI, LURLINE); these are the lines we have no colours for
    LINERS = ("SEASPAN", "CSCL", "CHINA SHIPPING", "SITC", "X-PRESS", "SAFMARINE")
    liner = bool(liveries.operator_of(name, ("container",), sure=True)) or has_word(name, *LINERS) \
        or name.startswith(("SM ", "APL ", "PIL "))
    if 80 <= t <= 89:
        if liner:                                # a box line mis-flagged as a tanker
            return "container", "Container Ship"
        return "tanker", "Tanker"
    if t in (31, 32, 52):
        # AIS type 32 = towing, tow length > 200 m: that IS the articulated
        # tug-barge fuel run. So is a "tug" that reports a 95 m+ hull.
        if t == 32 or hull_length(s) >= 95 or has_word(name, "ATB"):
            return "atb", "Tug and Barge"
        return "tug", "Tug"
    if t in (50, 51, 53, 54, 55, 58):
        # small working craft share one hull form on the wall; the caption keeps
        # the honest label (ITU-R M.1371 ship type table)
        return "workboat", {50: "Pilot Vessel", 51: "Search and Rescue", 53: "Port Tender",
                            54: "Anti-Pollution Vessel", 55: "Patrol Vessel",
                            58: "Medical Transport"}[t]
    if 70 <= t <= 79:  # generic cargo: name tells the real story
        if liveries.operator_of(name, ("carcarrier",), sure=True) or \
           has_word(name, " HIGHWAY", " LEADER", " ACE", "AUTO ", "GLOVIS", " CROWN"):
            return "carcarrier", "Car Carrier"
        if liner:
            return "container", "Container Ship"
        if name in ("MOL COURAGE", "MOL PROFICIENCY", "NYK REMUS", "ANL WARRNAMBOOL") or (
                name.startswith("PRESIDENT ") and hull_length(s) >= 200):     # APL's
            return "container", "Container Ship"
        if liveries.operator_of(name, ("general",), sure=True):
            return "general", "General Cargo"
        if has_word(name, "BBC ", "SAL ", "JUMBO") or \
           any(k in name for k in ("SPLIET", "SWL", "HEAVY")):      # stems, not words
            return "general", "General Cargo"           # heavy-lift / breakbulk regulars
        return "bulk", "Bulk Carrier"                    # non-liner cargo here = bulkers
    return "other", "Vessel"


# categories we can currently paint, and which painter draws them
PAINTER = {"container": "container", "cargo": "container", "bulk": "bulk",
           "carcarrier": "carcarrier", "tug": "tug", "cutter": "cutter",
           "research": "research", "tanker": "tanker", "cruise": "cruise",
           "sailing": "sailing", "fishing": "fishing", "general": "general",
           "naval": "naval", "motoryacht": "motoryacht", "atb": "atb",
           "cable": "cable",
           "workboat": "workboat",   # pilot / SAR / patrol boats: the tug's hull, no tow
           "excursion": "excursion"} # party boats and small ferries: the motor yacht's hull
CONTAINERISH = {"container", "cargo", "carcarrier", "bulk"}
MAX_RANGE_NMI = config.MAX_RANGE_NMI   # loft antenna ducts 400+ nmi; only paint real passers


from ports import clean_dest      # her destination, as a person would say it ("Sea" = she is not saying)


RARE = {"cutter", "research", "cruise", "sailing", "fishing", "tug", "naval", "motoryacht", "atb",
        "workboat", "excursion", "cable"}
COMMON = {"container", "cargo", "bulk", "tanker", "carcarrier", "general"}
EST = {"tug": 34, "atb": 185, "fishing": 24, "sailing": 14, "motoryacht": 30,
       "cutter": 60, "research": 80, "cable": 140, "cruise": 290, "naval": 155,
       "carcarrier": 200, "container": 300, "tanker": 190, "bulk": 190,
       "general": 150, "workboat": 20}       # metres, when she has not said; printed with a ~
# Faster than this and the number is not hers (knots). Princess Lily, a "fishing vessel" doing 31.
TOP_SPEED = {"tug": 16, "atb": 16, "fishing": 20, "sailing": 20, "tanker": 20, "bulk": 20, "general": 22,
             "container": 28, "cargo": 28, "carcarrier": 24, "cable": 20, "research": 20, "cruise": 28}
MIDWAY_NMI = 45               # past this she was heard on a freak of the air, not passing
DARK_OK = {"cruise", "cutter", "naval", "cable", "research"}     # worth hanging by night
SOURCE_DAYS = 3               # paint from anything sighted in the last N days
KEEP_PAINTED = 500            # must outlast SOURCE_DAYS even at 24 a day; also "have we ever hung her"
GALLERY = os.path.join(STATE_DIR, "gallery")
os.makedirs(GALLERY, exist_ok=True)


def visible_nmi(length_m):
    """How far off a ship this size can be and still show above the horizon, seen from
    EYE_M metres up. 2.08 * sqrt(metres) is the mariner's distance to the horizon in
    nautical miles, with ordinary air; each of us gets one. From 30 m: 25 for a big
    ship, 16 for a small boat. Radio bends further than light, so being heard is no proof."""
    top = 6 if length_m < 24 else 12 if length_m < 60 else 25 if length_m < 150 else 40
    return 2.08 * (config.EYE_M ** 0.5 + top ** 0.5)


def in_sight(c):
    d = c.get("nmi")
    size = hull_length(c.get("rec") or {}) or EST.get(c.get("cat"), 180)
    return d is not None and d <= visible_nmi(size)


def by_night(iso):
    try:
        import light
        return (light.for_iso(iso) or {}).get("name") == "night"
    except Exception:
        return False


def moment(e, cat):
    """Which moment of her pass to hang: her closest, or, when that was in the dark and
    she was still a fair sight by day, her closest in daylight."""
    best = dict(rec=e.get("record"), nmi=e.get("closest_nmi"), at=e.get("closest_at"), wx=e.get("wx"))
    day = e.get("day") if isinstance(e.get("day"), dict) else None
    if not day or cat == "cruise" or not by_night(best["at"]):      # a liner is best with her lights on
        return best
    d, rec = day.get("nmi"), clean_record(day.get("record"))
    if not isinstance(d, (int, float)) or not rec:
        return best
    size = hull_length(rec) or EST.get(cat, 180)
    if d <= max(visible_nmi(size), 1.5 * (best["nmi"] or 0)):
        return dict(rec=rec, nmi=d, at=day.get("at"), wx=day.get("wx"))
    return best


def candidates(live_ships, painted, now):
    """Pool = live in-range ships + archive sightings from the last SOURCE_DAYS,
    minus anything painted in that window. Each candidate carries a sighting
    (record, closest_nmi, closest_at, wx, live?) so the caption can say when
    she passed and how far off."""
    cutoff = (now - datetime.timedelta(days=SOURCE_DAYS)).isoformat(timespec="seconds")
    recent = {int(p["mmsi"]) for p in painted if p.get("at", "") >= cutoff}
    pool = {}
    try:
        arch = json.load(open(os.path.join(STATE_DIR, "sightings.json")))
    except Exception:
        arch = {}
    for k, e in arch.items():
        rec = clean_record(e.get("record"))
        if e.get("last_seen", "") < cutoff or not rec:
            continue
        if not rec["shipname"]:
            continue              # logged by MMSI, still waiting on her name packet
        cat, label = category(rec)
        m = moment(dict(e, record=rec), cat)
        m["rec"] = dict(m["rec"], shipname=m["rec"].get("shipname") or rec["shipname"])
        pool[rec["mmsi"]] = dict(m, cat=cat, label=label, live=False)
    for s in map(clean_record, live_ships):   # live wins: freshest position
        if not s or not s["shipname"] or s["lat"] is None or s["lon"] is None:
            continue
        if (s.get("last_signal") or 0) > MAX_AGE_S or abs(s["lat"]) > 90 or abs(s["lon"]) > 180:
            continue                  # AIS sends lat 91 / lon 181 for "no position"
        d = dist_key(s) * 3440.0
        if d > MAX_RANGE_NMI:
            continue
        cat, label = category(s)
        prev = pool.get(s["mmsi"])
        nmi_ = d                          # where she is this minute, not the closest she ever came
        if prev and prev.get("nmi") is not None and prev["nmi"] < d and (
                by_night(now.isoformat()) and not by_night(prev.get("at"))):
            continue                      # she came closer, by daylight, earlier in this pass: hang that
        pool[s["mmsi"]] = dict(rec=s, cat=cat, label=label, nmi=round(nmi_, 1),
                                             at=now.isoformat(timespec="seconds"),
                                             wx=None, live=True)
    return [dict(mmsi=m, **c) for m, c in pool.items()
            if c["cat"] in PAINTER and m not in recent]


def level(c, recent_dark=0):
    """How good a passer she is, 0 the best. In sight beats merely heard (Mark, Nov 2026:
    seven paintings in ten were ships below the horizon), and daylight beats dark unless she
    is worth a nocturne or the wall has hung none lately."""
    d = c.get("nmi")
    lv = 0.0 if in_sight(c) else 1.0 if d is not None and d <= MIDWAY_NMI else 2.0
    if c.get("at") and by_night(c["at"]) and not (c.get("cat") in DARK_OK and lv == 0) and recent_dark:
        lv += 1.5
    return lv


def pick(cands, painted):
    """Real passers first (see level), and among them the variety rule (Mark, Jul 30):
    alternate the everyday (box/bulk/tanker/car ship) with the unique (research, cutter,
    cruise, sail, fish, tow) whenever the last-3-days pool allows: cargo, research, cargo,
    cutter. Never the same type twice running if there is a choice. Cargo runs are fine
    when that is all the coast offers. Within a group: never-painted, then most recent."""
    if not cands:
        return None
    hung = [p for p in painted if not p.get("failed")]
    hist = [p.get("cat") for p in hung][-6:]
    last = hist[-1] if hist else None
    ever = {int(p.get("mmsi", 0)) for p in hung}
    dark = sum(1 for p in hung[-3:] if p.get("dark"))        # so about one in four may be a night piece
    lv = {id(c): level(c, dark) for c in cands}
    near = [c for c in cands if lv[id(c)] < 2]               # in sight, or midway by daylight
    pool = near if any(c["cat"] != last for c in near) else cands
    rare = [c for c in pool if c["cat"] in RARE]
    common = [c for c in pool if c["cat"] not in RARE]
    if last in RARE and common:
        group = common                                   # unique last: an everyday one
    elif (last not in RARE or last is None) and rare:
        group = rare                                     # everyday last: a unique one
    else:
        group = common or rare
    diff = [c for c in group if c["cat"] != last]        # not the same type twice
    if diff:
        group = diff
    # nearest level, then rarest: types least recently shown, then unseen ships, then recency
    def since_shown(cat):
        for i, h in enumerate(reversed(hist)):
            if h == cat:
                return i
        return 99
    group.sort(key=lambda c: (lv[id(c)], -since_shown(c["cat"]), c["mmsi"] in ever,
                              -_ts(c.get("at")), c.get("nmi") or 0))
    return group[0]


def _ts(iso):
    try:
        return datetime.datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0


def spotted_text(c, now):
    """'PASSING NOW · 12 NMI OFF' or 'SPOTTED TUE 4:20 PM · 22 NMI OFF'. A ship below the
    horizon was not spotted and is not passing: she was HEARD."""
    seen = in_sight(c)
    verb = "SPOTTED" if seen else "HEARD"
    nmi_ = c.get("nmi")
    off = "%d NMI OFF" % round(nmi_) if nmi_ is not None else ""
    if c.get("live"):
        when = "PASSING NOW" if seen else "HEARD NOW"
    else:
        try:
            t = datetime.datetime.fromisoformat(c.get("at"))
            hours = (now - t).total_seconds() / 3600.0
            if hours < 1.2:
                when = verb + " THIS HOUR"
            elif hours < 20 and t.date() == now.date():
                n = round(hours)
                when = "%s %d %s AGO" % (verb, n, "HR" if n == 1 else "HRS")
            else:
                when = t.strftime(verb + " %a %-I:%M %p").upper()
        except Exception:
            when = verb
    return " · ".join(x for x in (when, off) if x)


def extras(s):
    """The rest of what she broadcasts, for painters that can use it and for the data file
    beside her picture. Only plausible numbers get through; anything else is simply absent."""
    def num(k, lo, hi):
        v = s.get(k)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi else None
    bow, stern, port, stbd = (num(k, 0, 510) for k in ("to_bow", "to_stern", "to_port", "to_starboard"))
    out = {"beam_m": port + stbd if port is not None and stbd is not None and 0 < port + stbd <= 80 else None,
           # where her GPS aerial sits, 0 at the bow and 1 at the stern: usually on the bridge roof
           "aerial_at": round(bow / (bow + stern), 2) if bow is not None and stern is not None and bow + stern > 0 else None,
           "draught_m": num("draught", 0.1, 25.5), "status": num("status", 0, 15), "imo": num("imo", 1000000, 9999999),
           "shiptype": num("shiptype", 0, 99)}
    return {k: v for k, v in out.items() if v is not None}


def offline_text(since_iso, hrs):
    """The red line under the weather. The last painting before the archive runs dry
    can hang for weeks (Sept 2026: 'OFFLINE 60 HRS' for 18 days), so past two days
    it gives the date, which stays true."""
    if hrs >= 48:
        return "RADIO OFFLINE SINCE " + datetime.datetime.fromisoformat(since_iso).strftime("%-d %b").upper()
    return "RADIO OFFLINE %d HRS" % round(hrs) if hrs >= 2 else "RADIO OFFLINE"


def dist_key(s):
    import math
    lat, lon = s.get("lat"), s.get("lon")
    la1, lo1 = map(math.radians, (config.LAT, config.LON))
    la2, lo2 = map(math.radians, (lat, lon))
    c = math.sin(la1)*math.sin(la2)+math.cos(la1)*math.cos(la2)*math.cos(lo2-lo1)
    return math.acos(max(-1.0, min(1.0, c)))


def note_for(st, now, live, feed_ok):
    """What the wall should say about the radio, if anything. An empty sea is not a fault:
    this coast goes silent for up to nine hours with a good antenna (measured Oct-Nov 2026),
    and on Nov 1 and Nov 23 the old rule blamed the connector after four."""
    if not feed_ok:
        hrs = (now.timestamp() - _ts(st.get("feed_down_since"))) / 3600.0
        log("RADIO OFFLINE: no feed from the receiver (%.1f hrs)" % hrs)
        return offline_text(st["feed_down_since"], hrs)
    h = read_health()
    if h.get("verdict") == "FAULT":                       # the receiver board itself is not answering
        log("radio self-test FAULT: %s" % h["detail"])
        return "RECEIVER NOT ANSWERING"
    if h.get("verdict") == "DEAF":                        # silent far longer than it has been lately
        log("radio self-test DEAF: %s" % h["detail"])
        return "NOTHING HEARD %d HRS · CHECK ANTENNA" % round(h.get("silent_h") or 0)
    if live:
        return None
    if h:
        sil = h.get("silent_h")
    else:                                                 # no self-test to ask: go by when a ship was last heard,
        sil = (now.timestamp() - _ts(st.get("last_live_at"))) / 3600.0 if st.get("last_live_at") else None
        if now.timestamp() - _ts(st.get("last_run_at")) > 2 * 3600:
            sil = None                                    # but only while this frame was there to listen
            st["last_live_at"] = now.isoformat(timespec="seconds")
    if sil is not None and sil >= 3:
        log("quiet sea: nothing heard in %.1f hrs" % sil)
        return "QUIET SEA · %d HRS" % round(sil)
    return None


def build_ship(c, now, note=None):
    """The record a painting is made from, out of a candidate."""
    import light, layout
    s, cat, label = c["rec"], c["cat"], c["label"]
    known = hull_length(s)
    est = EST.get(cat, 180)
    # an ATB gives the tug's own length: 39 m of tug is pushing 150 m of barge
    tug_only = cat == "atb" and 0 < known < 95
    length = est if tug_only else known or est            # never invent a fact silently
    when = datetime.datetime.fromisoformat(c["at"]) if c.get("at") else now
    course = course_of(s)
    if course is None:
        log("no usable heading/course (heading=%r cog=%r); arrow defaults south"
            % (s.get("heading"), s.get("cog")))
        course = 180
    speed = s.get("speed")
    speed = float(speed) if isinstance(speed, (int, float)) and 0 <= speed < 102.3 else 0.0
    doubt = speed > TOP_SPEED.get(cat, 60)
    if doubt:
        log("%s says %.1f kn, more than a %s makes; painted without it" % (s["shipname"], speed, label.lower()))
        speed = 0.0
    ship = dict(v=2, name=s["shipname"].title(), type=PAINTER[cat], length_m=int(length),
                length_est=not bool(known) or tug_only,
                dest=clean_dest(s.get("destination")).title(), speed_kn=speed, country=s.get("country") or "",
                date=when.strftime("%-d %B %Y").upper(), mmsi=int(s.get("mmsi") or 0),
                heading=course, shiptype_text=label,
                spotted=spotted_text(c, now), nmi=c.get("nmi"), radio_note=note, ais=extras(s))
    if tug_only:
        ship["tug_m"] = int(known)
    if doubt or not isinstance(s.get("speed"), (int, float)):
        ship["speed_unknown"] = True
    ship["light"] = light.for_iso(c.get("at"))            # ...and the light of that hour
    ship["layout"] = layout.choose(ship)
    return ship


def keep_copy(src, ship, wx, at, **more):
    """Keep every sourced painting: the frame is a printmaker, not a whiteboard. Beside the
    picture goes what she was painted FROM, so repaint.py can paint her again at any size.
    The place settings go along: they decide which way she sails and what the corner says."""
    import shutil
    safe = "".join(ch if ch.isalnum() else "_" for ch in ship["name"].lower())
    keep = os.path.join(GALLERY, "%s_%s_%d" % (at.strftime("%Y%m%d_%H%M"), safe, ship["mmsi"]))
    shutil.copy(src, keep + ".png")
    with open(keep + ".json.tmp", "w") as f:
        json.dump(dict({"ship": ship, "wx": wx, "painted_at": at.isoformat(timespec="seconds"),
                        "place": config.PLACE, "sea_bearing": config.SEA_BEARING}, **more), f, indent=1)
    os.replace(keep + ".json.tmp", keep + ".json")
    return keep


def main(aside=()):
    """aside: ships the painter choked on earlier in this same run (see below)."""
    now = datetime.datetime.now()
    if config.is_quiet(now.hour):
        log("quiet hours, holding current image"); return
    st = load_state()
    painted = st.get("painted", [])
    # radio health: unreachable feed = radio Pi down; a reachable radio grades itself.
    # Either way the wall says so instead of quietly repainting.
    feed_ok = True
    try:
        live = read_feed()
        st["feed_down_since"] = None
    except Exception as e:
        log(f"no AIS feed ({e}); painting from the archive")
        live, feed_ok = [], False
        st["feed_down_since"] = st.get("feed_down_since") or now.isoformat(timespec="seconds")
    if live:
        st["last_live_at"] = now.isoformat(timespec="seconds")
    radio_note = note_for(st, now, live, feed_ok)
    st["last_run_at"] = now.isoformat(timespec="seconds")
    cands = [c for c in candidates(live, painted, now)
             if c["mmsi"] not in {a["mmsi"] for a in aside}]
    if config.FAR_WAIT_H and (now.timestamp() - _ts(st.get("since"))) / 3600.0 < config.FAR_WAIT_H:
        cands = [c for c in cands if in_sight(c)]
    c = pick(cands, painted)
    if not c or len(aside) >= 3:
        save_state(st)
        if aside:     # nobody painted: that is a fault in the frame, not in the ships. Blame no one.
            log("PAINTER FAILING on every ship tried (%s); holding current, nobody set aside"
                % ", ".join(a["name"] for a in aside))
        else:
            log("nothing paintable in the last %d days; holding current" % SOURCE_DAYS)
        return
    cat, label = c["cat"], c["label"]
    ship = build_ship(c, now, radio_note)
    import weather, art_directions as A
    wx = c.get("wx")                             # the conditions she passed in
    if not wx:
        wx = weather.fetch()
        if not c.get("live"):
            log("no weather was logged at her passing; painting under this hour's instead")
    log(f"painting {ship['name']} ({label}, {ship['length_m']}m, {ship['spotted']}, {wx['label']}"
        f"; fog via {wx.get('fog_src', 'n/a')})")
    src = os.path.join(STATE_DIR, "current_render.png")
    wall = os.path.join(STATE_DIR, "current_wall.png")
    import panel
    try:
        A.option_A2(ship, wx, src)
        panel.to_wall(src, wall)
    except Exception as e:
        # A ship the painter chokes on would be picked again every hour until she
        # aged out of the pool, three days of a frozen wall. Try the next one. She
        # is only written down as unpaintable if another ship then paints fine; a
        # full card or a broken library fails for everyone and must not use up the pool.
        log("PAINT FAILED for %s (%s: %s); trying the next ship" % (ship["name"], type(e).__name__, e))
        return main(aside + ({"mmsi": ship["mmsi"], "cat": cat, "name": ship["name"], "failed": True,
                              "at": now.isoformat(timespec="seconds")},))
    ok, secs, note = panel.show(wall)
    if not ok and note != "no-panel":
        log("PAINTED BUT PANEL FAILED: %s -- render is at %s" % (note, src))
    elif ok:
        log("panel %s" % note)
    try:
        keep_copy(src, ship, wx, now)
    except Exception as e:
        log(f"gallery copy failed: {e}")
    painted.extend(aside)
    painted.append({"mmsi": ship["mmsi"], "cat": cat, "name": ship["name"],
                    "dark": ship["light"].get("name") == "night", "at": now.isoformat(timespec="seconds")})
    st.update({"last_cat": cat, "last_mmsi": ship["mmsi"], "name": ship["name"],
               "since": now.isoformat(timespec="seconds"), "painted": painted[-KEEP_PAINTED:]})
    save_state(st)
    log(f"hung {ship['name']}" + ("" if ok or note == "no-panel" else "  [ARCHIVED ONLY -- NOT ON WALL]"))


if __name__ == "__main__":
    main()
