import sys, os, io, json, datetime, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["TZ"] = "PST8PDT,M3.2.0,M11.1.0"; time.tzset()   # the expected times below are Sea Ranch clock times
os.environ["HOME"] = tempfile.mkdtemp()          # keep ~/.curator out of the real home
import weather, light, curator, sightings
ok = True
def check(label, got, want):
    global ok
    good = got == want
    ok &= good
    print(("PASS " if good else "FAIL ") + label + ("" if good else f"   got {got!r} want {want!r}"))

# ---------- weather: real rows captured Sep 12/13 ----------
HDR = "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE\n#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft\n"
F = {
 "46014": HDR + "2026 09 12 21 40 310  4.0  5.0    MM    MM    MM  MM 1016.4    MM  14.9    MM   MM   MM    MM\n2026 09 12 21 30 310  4.0  5.0    MM    MM    MM  MM 1016.4    MM  14.9    MM   MM   MM    MM\n2026 09 12 21 20 310  4.0  5.0   1.4    15   6.6 199 1016.4    MM  14.9    MM   MM   MM    MM\n",
 "46013": HDR + "2026 09 13 14 40 310  6.0  7.0    MM    MM    MM  MM 1017.3  15.0    MM  14.4   MM   MM    MM\n",
 "ANVC1": HDR + "2026 09 13 14 30 290  0.5  1.5    MM    MM    MM  MM 1017.5  14.0  12.1    MM   MM   MM    MM\n",
}
calls = []
class R(io.BytesIO): pass
def fake(url, timeout=None):
    st = url.rsplit("/",1)[1][:-4]; calls.append(st)
    if F.get(st) is None: raise OSError("down")
    return R(F[st].encode())
weather.urllib.request.urlopen = fake
weather.MAX_AGE_H = 1e9          # these rows are frozen in September; staleness is tested further down
wx = weather.fetch()
check("newest row has WVHT=MM -> walks back to 1.4 m = 4.6 ft", wx["wave_ft"], 4.6)
check("wind from newest row", (wx["wind_kn"], wx["wind_dir"]), (7.8, "NW"))
check("46014 has no air temp -> asks Bodega", calls, ["46014", "46013"])
check("fog from Bodega dewpoint (dep 0.6C) reads FOG", (wx["fog_src"], round(wx["fog"],2)), ("46013", 0.72))
check("label carries the condition", wx["label"], "NW 8 KN · SEAS 5 FT · FOG")
F["46013"] = None; calls.clear(); wx = weather.fetch()
check("Bodega down -> Arena Cove spread", (calls, wx["fog_src"]), (["46014","46013","ANVC1"], "ANVC1"))
F["ANVC1"] = None; wx = weather.fetch()
check("nobody can say -> default fog, flagged, no condition word", (wx["fog"], wx["fog_src"], wx["label"]), (0.45, "default", "NW 8 KN · SEAS 5 FT"))
F["46014"] = None; wx = weather.fetch()
check("everything down -> calm default, never crashes, caption admits it", (wx["wind_kn"], wx["wave_ft"], wx["label"]), (10.0, 4.0, "NO BUOY REPORT"))
F["46014"] = HDR + "2026 09 12 21 40 999 99.0  5.0  99.0    MM    MM  MM 1016.4  15.0  14.9    MM   MM   MM    MM\n"
wx = weather.fetch()
check("out-of-range sensor junk treated as missing", (wx["wind_kn"], wx["wave_ft"], wx["fog_src"], wx["label"]), (10.0, 4.0, "46014", "FOG"))

# ---------- category ----------
C = lambda **k: curator.category(k)[0]
check("US type 35, no name clue -> naval (was unreachable)", C(shiptype=35, mmsi=369970001, shipname="WARSHIP 112"), "naval")
check("US type 35 plain name -> naval", C(shiptype=35, mmsi=366999000, shipname="JOHN PAUL JONES"), "naval")
check("US type 55 -> cutter", C(shiptype=55, mmsi=369970000, shipname="TERRAPIN"), "cutter")
check("CG name on type 35 -> cutter", C(shiptype=35, mmsi=369970000, shipname="CG STRATTON"), "cutter")
check("USCGC name -> cutter", C(shiptype=0, mmsi=367000000, shipname="USCGC WAESCHE"), "cutter")
check("LONE STAR tanker stays a tanker", C(shiptype=80, mmsi=538000000, shipname="LONE STAR STATE"), "tanker")
check("OVERSEAS KEYSTONE stays a tanker", C(shiptype=80, mmsi=538000000, shipname="OVERSEAS KEYSTONE X"), "tanker")
check("FOREVER LUCKY cargo -> bulk not container", C(shiptype=70, mmsi=538000000, shipname="FOREVER LUCKY"), "bulk")
check("ONE APUS still container", C(shiptype=70, mmsi=431000000, shipname="ONE APUS"), "container")
check("EVER GIVEN still container", C(shiptype=71, mmsi=353136000, shipname="EVER GIVEN"), "container")
check("GJERTRUD MAERSK still container", C(shiptype=70, mmsi=219000000, shipname="GJERTRUD MAERSK"), "container")
check("MSC flagged tanker still container", C(shiptype=80, mmsi=353000000, shipname="MSC ANNA"), "container")
check("SEVEN SEAS HIGHWAY car carrier", C(shiptype=70, mmsi=370363000, shipname="SEVEN SEAS HIGHWAY"), "carcarrier")
check("PACIFIC ACE car carrier", C(shiptype=70, mmsi=370000000, shipname="PACIFIC ACE"), "carcarrier")
check("ACE ETERNITY (first word) not a car carrier", C(shiptype=70, mmsi=370000000, shipname="ACE ETERNITY"), "bulk")
check("GRACE not a car carrier", C(shiptype=70, mmsi=370000000, shipname="OCEAN GRACE"), "bulk")
check("MSC ATLANTIS is a box ship, not research", C(shiptype=70, mmsi=353000000, shipname="MSC ATLANTIS"), "container")
check("ATLANTIS type 90 is research", C(shiptype=90, mmsi=367000000, shipname="ATLANTIS"), "research")
check("SIKULIAQ research", C(shiptype=0, mmsi=367444540, shipname="SIKULIAQ"), "research")
check("pilot boat now has a painter", (curator.category(dict(shiptype=50, mmsi=367000000, shipname="GOLDEN GATE"))[1], curator.PAINTER.get("workboat")), ("Pilot Vessel", "workboat"))
check("every category() result except 'other' has a painter", sorted(c for c in {C(shiptype=t, mmsi=367000000, shipname="X") for t in range(100)} if c not in curator.PAINTER), ["other"])
check("spliethoff stem still general", C(shiptype=70, mmsi=244000000, shipname="SPLIETHOFF X"), "general")

# ---------- heading ----------
check("heading 511 + moving -> course", curator.course_of(dict(heading=511, cog=87.1, speed=7.8)), 87)
check("heading 511, drifting -> None", curator.course_of(dict(heading=511, cog=87.1, speed=0.2)), None)
check("heading 0 (due north) is a real heading", curator.course_of(dict(heading=0, cog=180.0, speed=10)), 0)
check("null heading, cog 360 -> None", curator.course_of(dict(heading=None, cog=360.0, speed=10)), None)
check("good heading wins", curator.course_of(dict(heading=82, cog=87.1, speed=7.8)), 82)

# ---------- caption ----------
now = datetime.datetime(2026, 9, 13, 15, 0)
check("1 HR AGO grammar", curator.spotted_text(dict(live=False, at="2026-09-13T13:40:00", nmi=12.2), now), "SPOTTED 1 HR AGO · 12 NMI OFF")
check("3 HRS AGO", curator.spotted_text(dict(live=False, at="2026-09-13T12:00:00", nmi=12.2), now), "SPOTTED 3 HRS AGO · 12 NMI OFF")

# ---------- light ----------
r, s = light.sun_times(datetime.date(2026, 9, 13))
print("     Sep 13 sunrise %.2f sunset %.2f (expect ~6.9 / ~19.4 PDT)" % (r, s))
check("Sep 13 sunset within 6 min of 7:22pm", abs(s - 19.37) < 0.1, True)
r, s = light.sun_times(datetime.date(2026, 12, 21))
print("     Dec 21 sunrise %.2f sunset %.2f (expect ~7.4 / ~16.9 PST)" % (r, s))
check("Dec 21 sunset within 6 min of 4:54pm", abs(s - 16.9) < 0.1, True)
r, s = light.sun_times(datetime.date(2026, 7, 15))
check("mid-July matches the table's anchor (6.0 / 20.65) within 6 min", (abs(r-6.0) < 0.1, abs(s-20.65) < 0.1), (True, True))
check("Dec 5:30pm is dusk/night, not afternoon", light.for_iso("2026-12-21T17:30:00")["name"] in ("dusk","night"), True)
check("Dec 8pm has no sun disc", light.for_iso("2026-12-21T20:00:00")["sun_h"], None)
check("Dec 4:40pm is sunset", light.for_iso("2026-12-21T16:40:00")["name"], "sunset")
check("Sep 13 7:10pm is sunset (old table said golden)", light.for_iso("2026-09-13T19:10:00")["name"], "sunset")
check("July 8:20pm unchanged: sunset", light.for_iso("2026-07-15T20:20:00")["name"], "sunset")
check("for_hour(13) with no date = fixed table (fleet test renders reproducible)", light.for_hour(13.0), light.MIDDAY)
check("Dec noon is midday", light.for_iso("2026-12-21T12:00:00")["name"], "midday")
names = [light.for_hour(h/4, datetime.date(2026,12,21))["name"] for h in range(96)]
order = [n for i,n in enumerate(names) if i==0 or n!=names[i-1]]
check("Dec day runs in order", order, ["night","predawn","dawn","morning","midday","late","golden","sunset","dusk","night"])

# ---------- atomic state ----------
curator.save_state({"painted":[{"mmsi":1}]})
check("state round-trips, no tmp left", (curator.load_state(), os.path.exists(curator.STATE + ".tmp")), ({"painted":[{"mmsi":1}]}, False))

# ---------- sightings: nameless then named ----------
feed = {"ships": []}
class J(io.BytesIO): pass
sightings.urllib.request.urlopen = lambda url, timeout=None: J(json.dumps(feed).encode())
_real_fetch = weather.fetch
weather.fetch = lambda timeout=10: dict(weather.DEFAULT, label="x", fog_src="default")
base = dict(mmsi=636026213, lat=38.70, lon=-123.70, last_signal=5, heading=511, cog=330.0, speed=14.0)
feed["ships"] = [dict(base)]                                # pass 1: position only
sightings.main(); a = sightings.load()
check("nameless ship is logged by MMSI", ("636026213" in a, a["636026213"]["name"]), (True, None))
check("...but curator will not paint her yet", curator.candidates([], [], datetime.datetime.now()), [])
feed["ships"] = [dict(base, lat=38.9, lon=-123.9, shipname="CAP SAN JUAN", shiptype=71, to_bow=200, to_stern=100, destination="USOAK")]   # pass 2: farther off, name arrives
sightings.main(); a = sightings.load(); e = a["636026213"]
check("name backfilled into the closest-approach record", (e["name"], e["record"]["shipname"], e["record"]["to_bow"], e["record"]["lat"]), ("CAP SAN JUAN", "CAP SAN JUAN", 200, 38.70))
check("category follows the name", e["category"], "bulk")
c = curator.candidates([], [], datetime.datetime.now())
check("now she is paintable", [x["mmsi"] for x in c], [636026213])
feed["ships"] = [dict(base, lat=38.71, lon=-123.60)]        # pass 3: closer, nameless again
sightings.main(); e = sightings.load()["636026213"]
check("closer nameless fix keeps her name and size", (e["record"]["shipname"], e["record"]["to_bow"], e["record"]["lon"]), ("CAP SAN JUAN", 200, -123.60))
feed["ships"] = [dict(base, lat=91.0, lon=181.0, mmsi=1)]
sightings.main()
check("lat 91 / lon 181 (no position) ignored", "1" in sightings.load(), False)

# =====================================================================
# Oct 3 QA pass
# =====================================================================
UTC = datetime.timezone.utc
# ---------- weather: a buoy that stopped reporting is not weather ----------
weather.fetch = _real_fetch
weather.urllib.request.urlopen = fake            # (urllib is one shared module: last patch wins)
weather.MAX_AGE_H = 3.0
weather._now = lambda: datetime.datetime(2026, 9, 12, 22, 0, tzinfo=UTC)
F.update({"46014": HDR + "2026 09 12 21 40 310  4.0  5.0   1.4    15   6.6 199 1016.4  13.0  14.9    MM   MM   MM    MM\n", "46013": None, "ANVC1": None})
check("20-minute-old row is used", weather.fetch()["label"], "NW 8 KN · SEAS 5 FT · FOG")
weather._now = lambda: datetime.datetime(2026, 9, 20, 22, 0, tzinfo=UTC)
check("the same row 8 days later is history, and the caption says so", weather.fetch()["label"], "NO BUOY REPORT")
weather._now = lambda: datetime.datetime(2026, 9, 12, 22, 0, tzinfo=UTC)
F["46014"] = HDR + "2026 09 12 21 40 310  4.0  5.0    MM    MM    MM  MM 1016.4    MM  14.9    MM   MM   MM    MM\n2026 09 12 16 00 310  4.0  5.0   3.0    15   6.6 199 1016.4    MM  14.9    MM   MM   MM    MM\n"
check("fresh wind kept, 6-hour-old wave height dropped", weather.fetch()["label"], "NW 8 KN")
F["46014"] = HDR + "garbage row\n"
check("nothing but an unreadable line: no report", weather.fetch()["label"], "NO BUOY REPORT")
F["46014"] = HDR + "\ngarbled line here\n2026 09 12 21 40 310  4.0  5.0   1.4    15   6.6 199 1016.4  13.0  14.9    MM   MM   MM    MM\n"
check("a garbled line does not hide the good rows under it", weather.fetch()["label"], "NW 8 KN · SEAS 5 FT · FOG")

# ---------- type and colours come from one list ----------
import liveries
L = lambda n, t: liveries.for_ship(n, t)["note"]
for n in ("MAHIMAHI", "MANULANI", "KAIMANA HILA", "DANIEL K INOUYE", "LURLINE", "MATSONIA", "MANUKAI", "MAUNAWILI", "MAUNALEI", "MOKIHANA", "MANOA"):
    check("Matson's %s is a container ship" % n, C(shiptype=70, mmsi=367000000, shipname=n), "container")
check("WW / Hoegh / Glovis fleets are car carriers", [C(shiptype=70, mmsi=257000000, shipname=n) for n in ("TAMESIS", "TALISMAN", "HOEGH TRACER", "GLOVIS COUNTESS")], ["carcarrier"] * 4)
# a word good enough to pick a colour is not always good enough to pick a hull
check("tankers stay tankers whatever they are called", [C(shiptype=80, mmsi=367000000, shipname=n) for n in ("EVERGREEN STATE", "TEXAS EXPRESS", "HORIZON THETIS", "GAS EXPRESS")], ["tanker"] * 4)
check("ordinary words do not make a box ship", [C(shiptype=70, mmsi=367000000, shipname=n) for n in ("GIROLANDO EXPRESS", "HORIZON STAR", "BUDAPEST EXPRESS")], ["bulk"] * 3)
check("...or a car carrier", [C(shiptype=70, mmsi=367000000, shipname=n) for n in ("NYK VEGA", "MOL TRIUMPH", "MORNING GLORY", "STAR LEADERSHIP", "GOLDEN ACER", "TALISKER", "HIGHWAYMAN")], ["bulk"] * 7)
check("...but still choose her colours once her type is known", [L(n, t)[:5] for n, t in (("Budapest Express", "container"), ("Morning Celine", "carcarrier"), ("Nyk Leader", "carcarrier"))], ["Hapag", "Walle", "NYK P"])
check("a yacht or a troller called FAIRWEATHER is not NOAA's", [C(shiptype=t, mmsi=367000000, shipname="FAIRWEATHER") for t in (37, 30, 36, 90)], ["motoryacht", "fishing", "sailing", "research"])
check("HORIZON PACIFIC is Pasha, PACIFIC HORIZON is nobody", (C(shiptype=70, mmsi=367000000, shipname="HORIZON PACIFIC"), C(shiptype=70, mmsi=367000000, shipname="PACIFIC HORIZON")), ("container", "bulk"))
check("NOAA ship known only to liveries.py is research", C(shiptype=90, mmsi=367000000, shipname="REUBEN LASKER"), "research")
check("LONE STAR tanker is not painted ONE magenta", L("Lone Star State", "tanker"), "generic tanker")
check("KEYSTONE tanker keeps OSG, not ONE", L("Overseas Keystone", "tanker")[:3], "OSG")
check("FOREVER bulker is not Evergreen green", L("Forever Lucky", "bulk"), "generic bulk")
check("tug OCEAN TITAN is not a Wallenius car carrier", L("Ocean Titan", "tug"), "generic tug")
check("tanker OLYMPIC SPIRIT is not a Harley tug", L("Olympic Spirit", "tanker"), "generic tanker")
check("real liveries still land", [L(n, t)[:5] for n, t in (("One Apus", "container"), ("Ever Given", "container"), ("Pacific Ace", "carcarrier"), ("Titania", "carcarrier"), ("Lindsey Foss", "tug"), ("Polar Endeavour", "tanker"), ("Carnival Luminosa", "cruise"))], ["ONE (", "Everg", "MOL c", "Walle", "Foss ", "Polar", "Carni"])
check("every operator row carries its kind", {len(r) for r in liveries.OPERATORS}, {4})

# ---------- honest captions ----------
import ship_print as sp
N = lambda n, t: sp.full_name(dict(name=n, type=t))
check("no doubled prefixes", [N("Uscgc Waesche", "cutter"), N("Cg Stratton", "cutter"), N("Uss John Paul Jones", "naval"), N("Usns Mercy", "naval"), N("Warship 112", "naval"), N("R/V Sally Ride", "research"), N("Tug Ocean Titan", "tug")],
      ["USCGC WAESCHE", "USCGC STRATTON", "USS JOHN PAUL JONES", "USNS MERCY", "WARSHIP 112", "R/V SALLY RIDE", "TUG OCEAN TITAN"])
check("prefix still added when she has none", [N("Terrapin", "cutter"), N("Sikuliaq", "research"), N("Cosco Pacific", "container"), N("Golden Gate", "workboat"), N("Mystic", "sailing")],
      ["USCGC TERRAPIN", "R/V SIKULIAQ", "M/V COSCO PACIFIC", "M/V GOLDEN GATE", "S/V MYSTIC"])
check("a prefix with nothing after it is a name", N("Tug", "tug"), "TUG TUG")
check("pilot boat: own painter, no tow", (curator.PAINTER["workboat"], "tow" in __import__("inspect").signature(__import__("scene").paint_tug).parameters), ("workboat", True))
check("every painter the curator names exists in scene.py", sorted(set(curator.PAINTER.values()) - set(__import__("scene").PAINTERS)), [])
check("20 m passenger boat is not a cruise ship", curator.category(dict(shiptype=60, mmsi=367000000, shipname="NEW SEA ANGLER", to_bow=10, to_stern=10)), ("excursion", "Passenger Vessel"))
check("294 m passenger ship still is", C(shiptype=60, mmsi=311001201, shipname="CARNIVAL LUMINOSA", to_bow=150, to_stern=144), "cruise")
check("passenger ship with no dimensions stays a cruise ship", C(shiptype=60, mmsi=311001201, shipname="X"), "cruise")
check("511 is 'this big or bigger', not a length", (curator.hull_length(dict(to_bow=511, to_stern=511)), curator.hull_length(dict(to_bow=200, to_stern=100)), curator.hull_length({})), (0, 300, 0))
check("FOR ORDERS does not print FOR FOR ORDERS", curator.clean_dest("FOR ORDERS"), "Orders")
check("five letters are not always a LOCODE", [curator.clean_dest(d) for d in ("FOR ORDER", "TOKYO", "BUSAN", "OAKLAND>FOR ORDER", "USNTD", "US OAK", "CAPRR>USSFO")], ["Order", "Tokyo", "Busan", "Order", "Usntd", "Oakland", "San Francisco"])
check("two-letter words are not always prefixes", [N("My Girl", "fishing"), N("My Way", "motoryacht"), N("Mt Everest", "bulk"), N("Sv Rambler", "fishing"), N("Cg Marie", "fishing")],
      ["F/V MY GIRL", "M/Y MY WAY", "M/V MT EVEREST", "F/V SV RAMBLER", "F/V CG MARIE"])
check("...except on the ship that would get that prefix anyway", [N("Mv Cosco Pacific", "container"), N("Sv Delos", "sailing"), N("Rv Sally Ride", "research"), N("Fv Sea Dancer", "fishing")],
      ["M/V COSCO PACIFIC", "S/V DELOS", "R/V SALLY RIDE", "F/V SEA DANCER"])

# ---------- the feed is untrusted ----------
R = curator.clean_record            # (the R class near the top is done with)
check("control characters and length", (curator.tidy("EVIL\nLOG  LINE\x00\x07"), len(curator.tidy("A" * 60))), ("EVIL LOG LINE", 20))
check("numbers that are not numbers become None", [R(dict(mmsi=1, lat=v))["lat"] for v in ("38.7", "x", None, True, float("nan"), float("inf"), [1])], [38.7, None, None, None, None, None, None])
check("real numbers are left exactly as sent", (R(dict(mmsi="367000001", to_bow=200, speed=14.5))["mmsi"], R(dict(mmsi=1, to_bow=200))["to_bow"], R(dict(mmsi=1, speed=14.5))["speed"]), (367000001, 200, 14.5))
check("no usable MMSI, no ship", [R(x) for x in (None, [], "x", {}, dict(mmsi=0), dict(mmsi="abc"), dict(mmsi=-5), dict(mmsi=float("inf")), dict(mmsi=float("nan")))], [None] * 9)
check("text that is not text is missing, not stringified", [(R(dict(mmsi=1, shipname=v, destination=v))["shipname"], R(dict(mmsi=1, destination=v))["destination"]) for v in ({"a": 1}, True, 0, ["X"])], [("", "")] * 4)
check("country must be text", (R(dict(mmsi=1, country=5))["country"], R(dict(mmsi=1, country="US"))["country"]), ("", "US"))
sightings.urllib.request.urlopen = lambda url, timeout=None: J(json.dumps(feed).encode())
weather.fetch = lambda timeout=10: dict(weather.DEFAULT, label="x", fog_src="default")
feed["ships"] = [None, 7, dict(mmsi="x"), dict(base, mmsi=2, lat="38.70", shiptype="70", shipname="GOOD\nSHIP"), dict(base, mmsi=3, lat={}, shipname="BAD")]
sightings.main(); a = sightings.load()
check("one malformed record costs one ship, not the run", ("2" in a and a["2"]["name"], "3" in a), ("GOOD SHIP", False))
c = curator.candidates(feed["ships"], [], datetime.datetime.now())
check("curator reads the same feed without crashing", 2 in [x["mmsi"] for x in c], True)

# ---------- a ship the painter chokes on must not freeze the wall ----------
import art_directions, panel, config
tried = []
def boom(ship, wx, path, scale=1.0):
    tried.append(ship["name"])
    if ship["name"] == "Cursed": raise ValueError("boom")
    open(path, "w").close()
_real_A2 = art_directions.option_A2          # the night checks further down want the real painter back
art_directions.option_A2, panel.to_wall, panel.show = boom, (lambda s, d: d), (lambda p: (False, 0.0, "no-panel"))
config.is_quiet = lambda h: False
weather.fetch = lambda timeout=10: dict(weather.DEFAULT, label="x", fog_src="default")
for f_ in (curator.STATE, sightings.ARCHIVE):
    if os.path.exists(f_): os.remove(f_)
feed["ships"] = [dict(base, mmsi=10, shipname="CURSED", shiptype=36), dict(base, mmsi=11, shipname="FINE", shiptype=70, lat=38.9)]
curator.urllib.request.urlopen = lambda url, timeout=None: J(json.dumps(feed).encode()) if "8100" in url else (_ for _ in ()).throw(OSError())
curator.main(); st = curator.load_state()
check("painter raised -> she is set aside and the next ship hangs the same hour", (tried, st.get("name"), [(p["name"], bool(p.get("failed"))) for p in st["painted"]]), (["Cursed", "Fine"], "Fine", [("Cursed", True), ("Fine", False)]))
side = [json.load(open(os.path.join(curator.GALLERY, f_))) for f_ in sorted(os.listdir(curator.GALLERY)) if f_.endswith(".json")]
check("each painting keeps the data it was painted from, and only finished paintings do", ([(d_["ship"]["name"], d_["ship"]["mmsi"], d_["wx"]["label"], d_["place"]) for d_ in side], [f_ for f_ in os.listdir(curator.GALLERY) if f_.endswith(".tmp")]), ([("Fine", 11, "x", "THE SEA RANCH")], []))
tried.clear(); feed["ships"].append(dict(base, mmsi=12, shipname="THIRD", shiptype=30)); curator.main()
check("...and she is not retried next hour", tried, ["Third"])
# a fault in the frame (full card, broken library) fails for every ship and must not use up the pool
for f_ in (curator.STATE, sightings.ARCHIVE):
    if os.path.exists(f_): os.remove(f_)
def allboom(ship, wx, path, scale=1.0):
    tried.append(ship["name"]); raise OSError("No space left on device")
art_directions.option_A2 = allboom
feed["ships"] = [dict(base, mmsi=20 + i, shipname="SHIP %d" % i, shiptype=70) for i in range(6)]
tried.clear(); curator.main(); curator.main()
check("every ship fails -> three tries an hour, nobody blamed", (len(tried), curator.load_state().get("painted", [])), (6, []))
art_directions.option_A2 = boom; tried.clear(); curator.main()
check("...and the pool is intact when the fault clears", (len(tried), len(curator.candidates(feed["ships"], curator.load_state()["painted"], datetime.datetime.now()))), (1, 5))
check("a failed attempt does not count as the last type hung", curator.pick([dict(mmsi=1, cat="sailing", at=None, nmi=1)], [dict(mmsi=9, cat="sailing", failed=True)])["mmsi"], 1)

check("the offline note counts hours, then gives a date that cannot go stale", [curator.offline_text("2026-09-24T07:00:16", h) for h in (0.5, 5.2, 47, 60, 492)],
      ["RADIO OFFLINE", "RADIO OFFLINE 5 HRS", "RADIO OFFLINE 47 HRS", "RADIO OFFLINE SINCE 24 SEP", "RADIO OFFLINE SINCE 24 SEP"])

check("the rest of her broadcast is kept when it is sane, dropped when it is not",
      (curator.extras(dict(to_bow=147, to_stern=36, to_port=12, to_starboard=20, draught=11.6, status=0, imo=9834870, shiptype=80)),
       curator.extras(dict(to_bow="x", to_stern=None, to_port=400, to_starboard=400, draught=99, status=True, imo=5, shiptype=-1))),
      ({"beam_m": 32, "aerial_at": 0.8, "draught_m": 11.6, "status": 0, "imo": 9834870, "shiptype": 80}, {}))

# ---------- night: the moon, the dark, her lights ----------
import datetime as _dtn, light as _lt, scene as _sc, art_directions as _AD
import numpy as np
from PIL import Image as _Im
_mo = lambda s_: _lt.moon(_dtn.datetime.fromisoformat(s_))
check("the moon's phase is right on known dates (new 10 Oct, quarter 18 Oct, full 25-26 Oct 2026)",
      (_mo("2026-10-10T08:50")["fraction"] < 0.01, abs(_mo("2026-10-18T09:00")["fraction"] - 0.5) < 0.03, _mo("2026-10-25T21:12")["fraction"] > 0.99), (True, True, True))
check("a full moon rises in the east at sunset and sets over the sea at sunrise",
      (0 < _mo("2026-10-25T18:00")["alt"] < 8, 60 < _mo("2026-10-25T18:00")["az"] < 90, 0 < _mo("2026-10-26T08:00")["alt"] < 8, 270 < _mo("2026-10-26T08:00")["az"] < 300), (True,) * 4)
check("only hours after sunset carry a moon, so daytime pictures are untouched",
      [("moon" in _lt.for_iso("2026-10-15T%s:00" % h_)) for h_ in ("03:00", "06:45", "08:30", "13:00", "18:15", "19:05", "23:00")], [True, True, False, False, False, True, True])
check("moon data out of a damaged file means no moon, never a crash",
      [_sc.moon_of({"moon": m_}) for m_ in ({}, None, "x", [1], {"alt": "x"}, {"alt": float("nan")}, {"alt": 1e9, "az": -10, "fraction": 7, "limb": 725})][1:],
      [None, None, None, None, None, {"alt": 90.0, "az": 350.0, "fraction": 1.0, "limb": 5.0}])
def _night(hdg_, when_="2026-10-10T23:00:00", typ_="tanker"):
    p_ = os.path.join(tempfile.mkdtemp(), "n.png")
    _real_A2(dict(name="Night Test", type=typ_, length_m=158, dest="Sea", speed_kn=12, date="X", mmsi=1, heading=hdg_, country="US", shiptype_text="X", nmi=10,
                       spotted="", light=_lt.for_iso(when_)), dict(label="x", wind_kn=6, wind_dir="NW", wave_ft=3, fog=0.14), p_)
    return np.asarray(_Im.open(p_).convert("RGB")).astype(int)
_nl, _nr, _dy = _night(160), _night(340), _night(160, "2026-10-10T13:00:00")
_red = lambda a_: int(((a_[130:300, :, 0] > 190) & (a_[130:300, :, 1] < 90) & (a_[130:300, :, 2] < 90)).sum())
_grn = lambda a_: int(((a_[130:300, :, 1] > 150) & (a_[130:300, :, 0] < 110) & (a_[130:300, :, 2] < 150)).sum())
check("night is dark and the caption turns pale to be read", (_nl[150:240].mean() < 110 < _dy[150:240].mean(), _nl[28:50, 36:200].max() > 225, _dy[28:50, 36:200].min() < 60), (True, True, True))
check("sailing left she shows us her red port light, sailing right her green starboard light",
      (_red(_nl) > 3, _grn(_nl) == 0, _grn(_nr) > 3, _red(_nr) == 0), (True, True, True, True))

# ---------- cargo ships that differ ----------
_vr = dict(name="Victory Ray", type="bulk", length_m=180, mmsi=311008700)
check("her broadcast draught sets how high she rides: full, in ballast, not given, nonsense",
      [round(_sc.riding_high(dict(_vr, ais=a_)), 2) for a_ in ({"draught_m": 10.3}, {"draught_m": 5.8}, {}, {"draught_m": "x"}, {"draught_m": True}, {"draught_m": 99})], [0.0, 0.94, 0.3, 0.3, 0.3, 0.3])
check("only cargo ships change trim", [_sc.riding_high(dict(_vr, type=t_, ais={"draught_m": 3})) for t_ in ("cruise", "sailing", "tug", "carcarrier")], [0.0] * 4)
check("an owner we know keeps her real colours; a stranger's are hers for good, whatever her load",
      ([_sc.cargo_livery(dict(name=n_, type="container", mmsi=5)) == liveries.for_ship(n_, "container") for n_ in ("EVER LEGACY", "MAERSK MAMMOTH", "MANULANI")],
       _sc.cargo_livery(dict(_vr, ais={"draught_m": 10})) == _sc.cargo_livery(dict(_vr, ais={"draught_m": 5})),
       len({str(_sc.cargo_livery(dict(_vr, mmsi=m_))["hull"]) for m_ in range(300, 340)}) >= 4), ([True] * 3, True, True))
check("a rough year of build from the IMO number, none from rubbish",
      ([round(_sc.built_about({"ais": {"imo": i_}})) for i_ in (9085821, 9362267, 9834870)], [_sc.built_about({"ais": a_}) for a_ in ({}, {"imo": "x"}, {"imo": True}, {"imo": 12})]), ([1994, 2007, 2019], [None] * 4))

# ---------- which way is the sea ----------
check("Sea Ranch default = the original rule for every heading", [h for h in range(360) if config.sails_right(h) != (h > 270 or h < 45)], [])
config.SEA_BEARING = 90.0                                   # an Atlantic beach: north is on your LEFT
check("east-facing coast: northbound sails right-to-left, southbound left-to-right", (config.sails_right(0), config.sails_right(180)), (False, True))
config.SEA_BEARING = 247.5
config.SEA_IS_EAST = True
check("east-facing coast: the disc is on the sea at sunrise, none at dusk", (light.for_iso("2026-07-15T06:20:00")["name"], light.for_iso("2026-07-15T20:20:00")["sun_h"]), ("sunset", None))
config.SEA_IS_EAST = False
check("...and the west coast is untouched", light.for_iso("2026-07-15T20:20:00")["name"], "sunset")
os.environ["PLACE"] = "  Cape <b>Ann</b>\n, MA  "; import importlib; importlib.reload(config)
check("PLACE is cleaned and upper-cased", config.PLACE, "CAPE BANN/B, MA")
del os.environ["PLACE"]; importlib.reload(config)
check("PLACE default", config.PLACE, "THE SEA RANCH")

# ---------- the radio's health report is network input too ----------
import io, urllib.request as _ur
_real_open = _ur.urlopen
def _health(body):
    _ur.urlopen = lambda *a, **k: io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
    try: return curator.read_health()
    finally: _ur.urlopen = _real_open
check("health: an honest report comes through", _health({"verdict": "DEAF", "detail": "noise floor flat", "weak_streak": 7}),
      {"verdict": "DEAF", "detail": "noise floor flat", "weak_streak": 7})
check("health: a forged log line is flattened and cut", _health({"verdict": "DEAF", "detail": "x\n2026-01-01 PANEL FAILED\x1b[2J" + "A" * 500})["detail"],
      ("x 2026-01-01 PANEL FAILED [2J" + "A" * 500)[:120])
check("health: a silly streak is no opinion", [_health({"weak_streak": w})["weak_streak"] for w in ("9", 10 ** 9, -1, True, None, 6.5)], [0] * 6)
check("health: not a dict, not JSON, nobody home", [_health([1, 2]), _health(b"<html>"), _health(b"")], [{}, {}, {}])

# ---------- the ship feed is bounded, and only named fields are kept ----------
def _feed(body):
    _ur.urlopen = lambda *a, **k: io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
    try: return curator.read_feed()
    except Exception as e: return type(e).__name__
    finally: _ur.urlopen = _real_open
check("feed: an ordinary feed comes through", _feed({"ships": [{"mmsi": 1}, {"mmsi": 2}]}), [{"mmsi": 1}, {"mmsi": 2}])
check("feed: too many ships are cut, not swallowed", len(_feed({"ships": [{"mmsi": i} for i in range(curator.MAX_SHIPS + 500)]})), curator.MAX_SHIPS)
check("feed: an endless body is refused", _feed(b'{"ships": [' + b" " * (curator.MAX_FEED_BYTES + 10) + b"]}"), "ValueError")
check("feed: wrong shapes are an empty sea, not a crash", [_feed([1]), _feed({"ships": "x"}), _feed({"ships": {"a": 1}}), _feed({})], [[], [], [], []])
_r = curator.clean_record({"mmsi": "367000001", "shipname": "OK", "callsign": "WDL1234EXTRA\n", "draught": "7.5", "imo": 9301122,
                           "status": True, "junk": "A" * 10 ** 6, "nested": {"a": [1] * 1000}, "eta_day": "soon"})
check("record: fields nobody named do not ride along", sorted(set(_r) - set(curator._NUMBERS)), ["callsign", "country", "destination", "mmsi", "shipname"])
check("record: kept fields are cleaned", (_r["callsign"], _r["draught"], _r["imo"], _r["status"], _r["eta_day"]), ("WDL1234", 7.5, 9301122, None, None))
check("record: small enough to save", len(json.dumps(_r)) < 600, True)
check("record: the painters' extras still work", curator.extras(_r), {"draught_m": 7.5, "imo": 9301122})

# ---------- a missing font must not cost the painting ----------
art_directions._FONT_CANDIDATES = [("/nonexistent/%s.ttf", "B", "R", 0, 0)]
check("no font on the machine -> PIL's built-in face, not a crash", art_directions.helv(12) is not None, True)
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
