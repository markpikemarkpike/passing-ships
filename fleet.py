#!/usr/bin/env python3
"""Fleet harness: render every vessel type across weather scenes, grade with
the countable referees, and build contact sheets. The remixable test loop.

  fleet.py render [--types t1 t2] [--scenes s1 s2]   -> renders/fleet/*.png
  fleet.py grade                                     -> renders/fleet/GRADES.md
  fleet.py sheet                                     -> renders/fleet/SHEET_*.png
  fleet.py all                                       -> render + grade + sheet

Every painter is exercised through the real A2 path (scene.paint_scene via
art_directions.option_A2) and through the panel model (panel.to_wall), so a
change to watercolor.py or scene.py is re-tested across the whole fleet in
one command. Ship records may carry an optional "params" dict; recognised
keys are passed to the painter (remix without editing code)."""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "renders", "fleet")
os.makedirs(OUT, exist_ok=True)

# the whole coast: every AIS form we paint, with a representative ship
FLEET = {
  "container":  dict(name="Cosco Pacific", type="container", length_m=366, dest="Oakland",
                     speed_kn=16.2, mmsi=477123456, heading=132, country="HK",
                     shiptype_text="Container Ship"),
  "tanker":     dict(name="Ginga Cougar", type="tanker", length_m=183, dest="Long Beach",
                     speed_kn=12.6, mmsi=477222000, heading=160, country="HK", shiptype_text="Tanker"),
  "bulk":       dict(name="Pacific Basin", type="bulk", length_m=190, dest="Stockton",
                     speed_kn=11.4, mmsi=477999000, heading=150, country="HK", shiptype_text="Bulk Carrier"),
  "carcarrier": dict(name="Seven Seas Highway", type="carcarrier", length_m=200, dest="Benicia",
                     speed_kn=14.2, mmsi=370363000, heading=140, country="PA", shiptype_text="Car Carrier"),
  "general":    dict(name="Atlantic Star", type="general", length_m=143, dest="Portland",
                     speed_kn=13.1, mmsi=636020000, heading=345, country="LR", shiptype_text="General Cargo"),
  "cruise":     dict(name="Carnival Luminosa", type="cruise", length_m=294, dest="San Francisco",
                     speed_kn=17.9, mmsi=311001201, heading=157, country="BS", shiptype_text="Cruise Ship"),
  "research":   dict(name="Sikuliaq", type="research", length_m=80, dest="San Francisco",
                     speed_kn=9.6, mmsi=367444540, heading=140, country="US", shiptype_text="Research Vessel"),
  "cutter":     dict(name="Terrapin", type="cutter", length_m=47, dest="Sea", speed_kn=18.0,
                     mmsi=369970000, heading=175, country="US", shiptype_text="Coast Guard Cutter"),
  "naval":      dict(name="John Paul Jones", type="naval", length_m=155, dest="San Diego",
                     speed_kn=20.0, mmsi=369970001, heading=170, country="US", shiptype_text="Warship"),
  "tug":        dict(name="Ocean Titan", type="tug", length_m=38, dest="Coos Bay", speed_kn=7.8,
                     mmsi=367123000, heading=340, country="US", shiptype_text="Tug and Tow"),
  "atb":        dict(name="Gene Dunlap", type="atb", length_m=200, dest="Vallejo",
                     speed_kn=8.5, mmsi=367472000, heading=150, country="US",
                     shiptype_text="Tug and Barge"),
  "sailing":    dict(name="Wild Rose", type="sailing", length_m=14, dest="Fort Bragg", speed_kn=6.1,
                     mmsi=367002000, heading=200, country="US", shiptype_text="Sailing Vessel"),
  "motoryacht": dict(name="Silver Lining", type="motoryacht", length_m=32, dest="Monterey",
                     speed_kn=14.0, mmsi=367002100, heading=190, country="US", shiptype_text="Motor Yacht"),
  "fishing":    dict(name="Sea Dancer Ii", type="fishing", length_m=22, dest="Bodega Bay", speed_kn=8.4,
                     mmsi=367003000, heading=190, country="US", shiptype_text="Fishing Vessel"),
  # two borrowed hulls: the tug's with no tow, the motor yacht's with an honest label
  "workboat":   dict(name="Golden Gate", type="workboat", length_m=22, dest="San Francisco", speed_kn=16.0,
                     mmsi=367004000, heading=150, country="US", shiptype_text="Pilot Vessel"),
  "excursion":  dict(name="New Sea Angler", type="excursion", length_m=20, dest="Bodega Bay", speed_kn=11.0,
                     mmsi=367005000, heading=330, country="US", shiptype_text="Passenger Vessel"),
}

# weather scenes: the same ship must hold up from socked-in to a blowing clear
SCENES = {
  "haze": dict(wind_kn=16, wave_ft=4, fog=0.42, wind_dir="NNW", label="NNW 16 KN · SEAS 4 FT · HAZE"),
  "fog":  dict(wind_kn=6, wave_ft=3, fog=0.78, wind_dir="W", label="W 6 KN · SEAS 3 FT · FOG"),
  "clear":dict(wind_kn=12, wave_ft=3, fog=0.14, wind_dir="NW", label="NW 12 KN · SEAS 3 FT · CLEAR"),
  "gale": dict(wind_kn=32, wave_ft=11, fog=0.50, wind_dir="NNW", label="NNW 32 KN · SEAS 11 FT · GALE"),
  "sunset": dict(wind_kn=8, wave_ft=3, fog=0.28, wind_dir="W", label="W 8 KN · SEAS 3 FT · SUNSET",
                 hour=20.4),
  "dawn": dict(wind_kn=6, wave_ft=3, fog=0.35, wind_dir="E", label="E 6 KN · SEAS 3 FT · DAWN",
               hour=6.4),
}
DATE = "31 JULY 2026"


def render(types, scenes, scale=1.0):
    import art_directions as A, panel
    made = []
    outdir = OUT if scale == 1.0 else os.path.join(OUT, "master")
    os.makedirs(outdir, exist_ok=True)
    for t in types:
        if t not in FLEET:
            print("unknown type", t); continue
        for sc in scenes:
            ship = dict(FLEET[t], date=DATE)
            wx = dict(SCENES[sc])
            if "hour" in wx:                          # warm-hour scenes carry their light
                import light
                ship["light"] = light.for_hour(wx.pop("hour"))
            out = os.path.join(outdir, f"{t}_{sc}.png")
            A.option_A2(ship, wx, out, scale=scale)
            if scale == 1.0:
                panel.to_wall(out, out.replace(".png", "_wall.png"))
            made.append(out)
            print("rendered", os.path.basename(out), f"@{scale}x")
    return made


def grade(types, scenes):
    import referee
    rows = []
    for t in types:
        for sc in scenes:
            f = os.path.join(OUT, f"{t}_{sc}.png")
            fw = f.replace(".png", "_wall.png")
            if not (os.path.exists(f) and os.path.exists(fw)):
                continue
            m = referee.measure(f, fw)
            rows.append(dict(type=t, scene=sc, surv=m["survival"]["survival"],
                             seat=m["seat_white"], edge=m["edge_ratio"],
                             flat=m["flatness"], gap_sky=m["value"]["gap_ship_sky"],
                             gap_sea=m["value"]["gap_ship_sea"], ink_dark=m["ink"]["dark"]))
    json.dump(rows, open(os.path.join(OUT, "grades.json"), "w"), indent=1)
    # flag physics failures (not taste): the panel bar and the seat
    lines = ["# Fleet referee report", "",
             "| type | scene | survival | seat | edge | flat | ship-sky | ship-sea | flags |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        flags = []
        if r["surv"] < 0.8: flags.append("PANEL-COLLAPSE")
        if r["seat"] < 0.02: flags.append("no-seat")
        if r["gap_sky"] < 15 and r["gap_sea"] < 15: flags.append("melts")
        if r["edge"] > 0.45: flags.append("etched")
        if r["edge"] < 0.05: flags.append("mush")
        lines.append("| {type} | {scene} | {surv:.2f} | {seat:.2f} | {edge:.2f} | {flat:.2f} | "
                     "{gap_sky:.0f} | {gap_sea:.0f} | {f} |".format(f=", ".join(flags) or "ok", **r))
    open(os.path.join(OUT, "GRADES.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return rows


def sheet(types, scenes, suffix=""):
    from PIL import Image
    for kind in ("", "_wall"):
        ims, labels = [], []
        for t in types:
            for sc in scenes:
                f = os.path.join(OUT, f"{t}_{sc}{kind}.png")
                if os.path.exists(f):
                    ims.append(Image.open(f)); labels.append(f"{t}/{sc}")
        if not ims:
            continue
        w, h = ims[0].size
        sw, sh = w // 2, h // 2
        cols = len(scenes) if len(scenes) > 1 else 3
        rows = (len(ims) + cols - 1) // cols
        s = Image.new("RGB", (sw * cols + 6 * (cols - 1), sh * rows + 6 * (rows - 1)), (245, 242, 235))
        for i, im in enumerate(ims):
            s.paste(im.resize((sw, sh)), ((i % cols) * (sw + 6), (i // cols) * (sh + 6)))
        s.save(os.path.join(OUT, f"SHEET{kind}{suffix}.png"))
    print("sheets written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["render", "grade", "sheet", "all"])
    ap.add_argument("--types", nargs="*", default=list(FLEET))
    ap.add_argument("--scenes", nargs="*", default=["haze"])
    ap.add_argument("--scale", type=float, default=1.0, help="3.0 = 2400x1440 print master")
    a = ap.parse_args()
    if a.cmd in ("render", "all"):
        render(a.types, a.scenes, scale=a.scale)
    if a.cmd in ("grade", "all"):
        grade(a.types, a.scenes)
    if a.cmd in ("sheet", "all"):
        sheet(a.types, a.scenes)
