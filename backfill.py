#!/usr/bin/env python3
"""Paint the days this frame was off the wall, from the radio's diary and the buoy's records.

Runs once a night (backfill.timer, a few minutes past midnight). Any finished day in the
last LOOK_BACK with no painting at all gets one: a ship the radio heard that day, in the
light and weather of her passing. She goes in the gallery only, never on the wall, and her
data file says "backfilled". A day with no diary, or an empty one, stays empty."""
import datetime, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import curator, sightings

LOOK_BACK, A_NIGHT = 28, 3


def blank_days(now):
    have = {f[:8] for f in os.listdir(curator.GALLERY) if f.endswith(".png")}
    days = [(now - datetime.timedelta(days=n)).date() for n in range(1, LOOK_BACK + 1)]
    start = min(have, default="99999999")                  # nothing before the first painting ever
    return [d for d in sorted(days) if d.strftime("%Y%m%d") not in have and d.strftime("%Y%m%d") > start]


def choices(day, diary):
    """Candidates for one day, in the shape curator.pick wants. Only moments of that day."""
    out = []
    for e in filter(None, map(sightings.entry, diary.values())):
        rec = e["near"]["record"]
        cat, label = curator.category(rec)
        if cat not in curator.PAINTER:
            continue
        m = curator.moment(dict(record=rec, closest_nmi=e["near"]["nmi"], closest_at=e["near"]["at"],
                                day=e["day"]), cat)
        m["rec"] = dict(m["rec"], shipname=m["rec"].get("shipname") or rec["shipname"])
        if m["rec"]["shipname"] and m["at"][:10] == day.isoformat():
            out.append(dict(m, mmsi=rec["mmsi"], cat=cat, label=label, live=False))
    return out


def main(now=None, paint=None):
    now = now or datetime.datetime.now()
    painted = curator.load_state().get("painted", [])
    recent = {int(p["mmsi"]) for p in painted[-60:] if not p.get("failed")}
    done, hung = 0, list(painted)
    for day in blank_days(now):
        if done >= A_NIGHT:
            break
        diary = sightings.passages(day.isoformat())
        if not diary:
            continue
        cands = choices(day, diary)
        fresh = [c for c in cands if c["mmsi"] not in recent] or cands
        c = curator.pick(fresh, hung)
        if not c:
            curator.log("backfill %s: the radio heard %d, none we can paint" % (day, len(diary)))
            continue
        import weather
        wx = weather.fetch(timeout=15, at=c["at"])
        ship = curator.build_ship(c, now)
        t = datetime.datetime.fromisoformat(c["at"])
        ship["spotted"] = curator.spotted_text(c, t + datetime.timedelta(days=8))     # 'SPOTTED FRI 12:29 PM'
        src = os.path.join(curator.STATE_DIR, "backfill_render.png")
        try:
            if paint:
                paint(ship, wx, src)
            else:
                import art_directions as A
                A.option_A2(ship, wx, src)
        except Exception as e:
            curator.log("backfill %s: PAINT FAILED for %s (%s: %s)" % (day, ship["name"], type(e).__name__, e))
            continue
        curator.keep_copy(src, ship, wx, t, backfilled=now.date().isoformat())
        curator.log("backfill %s: %s (%s, %s)" % (day, ship["name"], ship["shiptype_text"], ship["spotted"]))
        recent.add(ship["mmsi"])
        hung.append({"mmsi": ship["mmsi"], "cat": c["cat"], "dark": ship["light"].get("name") == "night"})
        done += 1
    return done


if __name__ == "__main__":
    main()
