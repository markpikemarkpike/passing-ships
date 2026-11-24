"""Where she sits in the picture, and how close. Chosen once, when she is painted, and
saved in her record, so painting her again gives the same picture. Seeded by her name and
the hour: the same ship on another day gets another look.

    x      centre of the hull, as a fraction of the sheet (bow to the left; northbound
           sheets are mirrored at the end). Small x = she is leaving us, big = arriving.
    zoom   on top of the distance scale in scene.py.

A ship the eye could nearly touch gets a close look, cropped by the edge if need be;
one at the edge of sight sits small with the sea to herself."""
import zlib


def choose(ship):
    seed = zlib.crc32(("%s|%s" % (ship.get("name"), ship.get("spotted"))).encode("utf-8"))
    kind, nmi, L = ship.get("type"), ship.get("nmi"), float(ship.get("length_m") or 100)
    if kind in ("tug",):                       # the tow needs the room astern
        return {"x": 0.30, "zoom": 1.0, "look": "tow"}
    looks = ["middle", "arriving", "leaving", "arriving", "leaving"]
    if nmi is not None and nmi <= 12 and L >= 60:
        looks += ["close", "close"]
    if nmi is not None and nmi >= 20 and L >= 120:
        looks += ["far", "far"]
    look = looks[seed % len(looks)]
    j = ((seed >> 8) % 100) / 100.0             # 0..1, a nudge so no two are ruled on the same line
    x, zoom = {"middle": (0.45 + 0.06 * j, 1.0),
               "arriving": (0.57 + 0.06 * j, 1.0),
               "leaving": (0.34 + 0.05 * j, 1.0),
               "close": (0.60 + 0.06 * j, 1.45),
               "far": ((0.30 + 0.04 * j) if seed & 64 else (0.64 + 0.04 * j), 0.82)}[look]
    return {"x": round(x, 3), "zoom": zoom, "look": look}
