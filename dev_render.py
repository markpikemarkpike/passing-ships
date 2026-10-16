"""Quick iteration harness: render one vessel type through the real A2 path.
Usage: .venv/bin/python dev_render.py <type> [outfile] [wall]"""
import sys, art_directions as A

SHIPS = {
    "carcarrier": dict(name="Seven Seas Highway", type="carcarrier", length_m=200,
                       dest="Benicia", speed_kn=14.2, date="30 JULY 2026",
                       mmsi=370363000, heading=140, country="PA", shiptype_text="Car Carrier"),
    "bulk": dict(name="Pacific Basin", type="bulk", length_m=190,
                 dest="Stockton", speed_kn=11.4, date="30 JULY 2026",
                 mmsi=477999000, heading=150, country="HK", shiptype_text="Bulk Carrier"),
    "tug": dict(name="Ocean Titan", type="tug", length_m=38,
                dest="Coos Bay", speed_kn=7.8, date="30 JULY 2026",
                mmsi=367123000, heading=340, country="US", shiptype_text="Tug and Tow"),
    "cutter": dict(name="Terrapin", type="cutter", length_m=47,
                   dest="Sea", speed_kn=18.0, date="30 JULY 2026",
                   mmsi=369970000, heading=175, country="US", shiptype_text="Coast Guard Cutter"),
    "tanker": dict(name="Ginga Cougar", type="tanker", length_m=183,
                   dest="Long Beach", speed_kn=12.6, date="30 JULY 2026",
                   mmsi=477222000, heading=160, country="HK", shiptype_text="Tanker"),
    "cruise": dict(name="Carnival Luminosa", type="cruise", length_m=294,
                   dest="San Francisco", speed_kn=17.9, date="30 JULY 2026",
                   mmsi=311001201, heading=157, country="BS", shiptype_text="Cruise Ship"),
    "research": dict(name="Sikuliaq", type="research", length_m=80,
                     dest="San Francisco", speed_kn=9.6, date="30 JULY 2026",
                     mmsi=367444540, heading=140, country="US", shiptype_text="Research Vessel"),
    "sailing": dict(name="Wild Rose", type="sailing", length_m=14,
                    dest="Fort Bragg", speed_kn=6.1, date="30 JULY 2026",
                    mmsi=367002000, heading=200, country="US", shiptype_text="Sailing Vessel"),
    "fishing": dict(name="Sea Dancer Ii", type="fishing", length_m=22,
                    dest="Bodega Bay", speed_kn=8.4, date="30 JULY 2026",
                    mmsi=367003000, heading=190, country="US", shiptype_text="Fishing Vessel"),
    "container": dict(name="Cosco Pacific", type="container", length_m=366,
                      dest="Oakland", speed_kn=16.2, date="30 JULY 2026",
                      mmsi=477123456, heading=132, country="HK", shiptype_text="Container Ship"),
}
WX = dict(wind_kn=16, wave_ft=4, fog=0.42, wind_dir="NNW",
          label="NNW 16 KN · SEAS 4 FT · HAZE")

if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "container"
    out = sys.argv[2] if len(sys.argv) > 2 else "renders/dev_%s.png" % kind
    print(A.option_A2(SHIPS[kind], WX, out))
    if len(sys.argv) > 3:                       # optional panel preview
        import panel
        print(panel.to_wall(out, sys.argv[3]))
