#!/bin/bash
# ais-watch.sh -- message-rate health + recovery watchdog for the radio Pi.
# Runs three times an hour via ais-watch.timer (:37 :47 :57).
#
# Verdicts written to ~/status/health.json (served on :8101; curator.py reads
# verdict=="DEAF" -> CHECK ANTENNA CONNECTOR, weak_streak>=6 (9am-7pm) ->
# ANTENNA WEAK N HRS):
#   OK   - >=1 AIS msg decoded in the last 60 min.
#   WEAK - 0 msgs in the last 60 min. A quiet coast at night is legitimately
#          this quiet, so WEAK alone is not an alarm; the streak is.
#   DEAF - 0 msgs for QUIET_HRS_BEFORE_CYCLE hours AND the recovery below did
#          not bring traffic back by the next run.
#
# Recovery, mildest first. Each step is rate-limited; none can loop tightly.
#   1. after QUIET_HRS_BEFORE_CYCLE silent hours: restart the receiver, and with
#      RECOVER=uhubctl first cut 5V to the dongle's USB port for 60 s (the "pull
#      both plugs" rule, automated). At most once per CYCLE_COOLDOWN_MIN.
#   2. after REBOOT_AFTER_H silent hours (0 = never): reboot the Pi.
#   3. after NET_REBOOT_AFTER_MIN with no route to the gateway (0 = never):
#      bounce wifi on first sight, then reboot.
#   Reboots are gated on UPTIME, not on a saved timestamp, so the limit still
#   holds on a read-only root where nothing written here survives a reboot.
#
# Settings come from the environment (~/.config/passing-ships/watch.env, written
# by setup/radio.sh); the defaults are the indoor SDR build.
set -u
HEALTH=${HEALTH:-/home/mark/status/health.json}
LOG=${LOG:-/home/mark/rf-health.log}
STATEF=${STATEF:-/home/mark/status/watch-state.json}
RECOVER=${RECOVER:-uhubctl}               # uhubctl | none (dAISy, or any Pi Zero: its port cannot switch)
HUB_LOC=${HUB_LOC:-1}; HUB_PORT=${HUB_PORT:-1}    # run `uhubctl` to list yours
# Pi 5: the four sockets share one 5V switch, which opens only when EVERY onboard port is
# off (uhubctl README). List the hubs here, e.g. "2 4", and they are switched together.
HUB_ALL=${HUB_ALL:-}
# 1 = dongle-off.timer rests the dongle :05-:29. Not told? Look.
DUTY_CYCLE=${DUTY_CYCLE:-$(systemctl is-enabled dongle-off.timer >/dev/null 2>&1 && echo 1 || echo 0)}
QUIET_HRS_BEFORE_CYCLE=${QUIET_HRS_BEFORE_CYCLE:-4}
CYCLE_COOLDOWN_MIN=${CYCLE_COOLDOWN_MIN:-170}
REBOOT_AFTER_H=${REBOOT_AFTER_H:-0}
NET_REBOOT_AFTER_MIN=${NET_REBOOT_AFTER_MIN:-0}
STAMP=$(date +%Y-%m-%dT%H:%M)
MIN=$(date +%-M)
if [ "$DUTY_CYCLE" = 1 ] && [ "$MIN" -ge 5 ] && [ "$MIN" -lt 30 ]; then exit 0; fi   # resting; nothing to judge
export HEALTH LOG STATEF RECOVER HUB_LOC HUB_PORT HUB_ALL QUIET_HRS_BEFORE_CYCLE CYCLE_COOLDOWN_MIN \
       REBOOT_AFTER_H NET_REBOOT_AFTER_MIN STAMP
mkdir -p "$(dirname "$HEALTH")"

msgs_since() { # $1 = "N min ago"
  journalctl -u ais-catcher --since "$1" --no-pager 2>/dev/null \
    | grep -oE 'received: [0-9]+ msgs' | awk '{s+=$2} END{print s+0}'
}
M60=$(msgs_since "60 min ago")
MQUIET=$(msgs_since "$QUIET_HRS_BEFORE_CYCLE hours ago")
MBOOT=0; [ "$REBOOT_AFTER_H" != 0 ] && MBOOT=$(msgs_since "$REBOOT_AFTER_H hours ago")
UP=$(systemctl is-active ais-catcher)
NET=skip
if [ "$NET_REBOOT_AFTER_MIN" != 0 ]; then
  GW=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
  NET=down                                # a Zero in wifi power-save answers slowly: three patient tries
  for _ in 1 2 3; do [ -n "$GW" ] && ping -c1 -W4 "$GW" >/dev/null 2>&1 && { NET=up; break; }; done
fi

python3 - "$M60" "$MQUIET" "$MBOOT" "$UP" "$NET" <<'PY'
import json, os, sys, time, subprocess
m60, mquiet, mboot, up, net = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
E = os.environ
H, S, LOG, stamp = E["HEALTH"], E["STATEF"], E["LOG"], E["STAMP"]
qh, cool = float(E["QUIET_HRS_BEFORE_CYCLE"]), float(E["CYCLE_COOLDOWN_MIN"])
reboot_h, net_min = float(E["REBOOT_AFTER_H"]), float(E["NET_REBOOT_AFTER_MIN"])
RUNS_PER_HOUR = 3                                   # ais-watch.timer
def load(p):
    try: return json.load(open(p))
    except Exception: return {}
def save(p, d):                                     # whole file or old file, never half
    with open(p + ".tmp", "w") as f: json.dump(d, f)
    os.replace(p + ".tmp", p)
def log(line):
    with open(LOG, "a") as f: f.write(f"{stamp}  {line}\n")
def sudo(*a):
    return subprocess.run(["sudo", "-n", *a], capture_output=True, text=True)
prev, st = load(H), load(S)
now = float(E.get("WATCH_NOW") or time.time())      # (WATCH_* are test hooks)
uptime_h = float(E.get("WATCH_UPTIME_S") or open("/proc/uptime").read().split()[0]) / 3600.0
cycled, reboot_why = False, None
detail = f"{m60} msgs/60min, {mquiet} msgs/{qh:g}h, service {up}, up {uptime_h:.1f}h"
if up != "active":
    sudo("systemctl", "restart", "ais-catcher")
    log(f"SERVICE-DOWN ({up}) -> restarted")
if m60 > 0:
    verdict = "OK"; st["last_traffic"] = now; st.pop("cycled_at", None)
else:
    verdict = "WEAK"
    last_cycle = st.get("cycled_at", 0)
    # the journal only reaches back to boot: silence shorter than the window proves nothing
    if mquiet == 0 and uptime_h >= qh and (now - last_cycle) / 60 >= cool:
        how = "receiver restart"
        if E["RECOVER"] == "uhubctl":
            hubs = E["HUB_ALL"].split()
            if hubs:
                rc = max(sudo("/usr/sbin/uhubctl", "-l", h, "-a", "off").returncode for h in hubs)
                time.sleep(float(E.get("WATCH_OFF_S") or 60))
                rc = max([rc] + [sudo("/usr/sbin/uhubctl", "-l", h, "-a", "on").returncode for h in hubs])
            else:
                rc = sudo("/usr/sbin/uhubctl", "-l", E["HUB_LOC"], "-p", E["HUB_PORT"], "-a", "cycle", "-d", "60").returncode
            how = f"USB power-cycled 60s (uhubctl rc={rc}) + receiver restart"
            time.sleep(5)
        sudo("systemctl", "restart", "ais-catcher")
        st["cycled_at"] = now; cycled = True
        log(f"QUIET {qh:g}h+ -> {how}")
        detail += f"; {how} this run"
    elif mquiet == 0 and last_cycle and st.get("last_traffic", 0) < last_cycle and (now - last_cycle) > 15 * 60:
        verdict = "DEAF"
        detail += "; recovery did not restore traffic"
    if reboot_h and mboot == 0 and uptime_h >= reboot_h:
        reboot_why = f"no AIS traffic in {reboot_h:g}h"
if net == "up":
    st.pop("net_down_since", None)
elif net == "down":
    first = "net_down_since" not in st
    down_min = (now - st.setdefault("net_down_since", now)) / 60
    detail += f"; gateway unreachable {down_min:.0f} min"
    if first:
        sudo("nmcli", "radio", "wifi", "off"); time.sleep(3); sudo("nmcli", "radio", "wifi", "on")
        log("NET-DOWN -> bounced wifi")
    elif down_min >= net_min and uptime_h * 60 >= net_min:
        reboot_why = reboot_why or f"gateway unreachable {down_min:.0f} min"
runs = prev.get("weak_runs", 0) + 1 if verdict in ("WEAK", "DEAF") else 0
# counted in runs, published in hours, so the frame's ANTENNA WEAK N HRS stays honest
save(H, {"stamp": stamp, "verdict": verdict, "weak_streak": runs // RUNS_PER_HOUR,
         "weak_runs": runs, "msgs_60min": m60, "uptime_h": round(uptime_h, 1), "detail": detail})
save(S, st)
log(f"{verdict}  {detail}" + ("  [CYCLED]" if cycled else ""))
if reboot_why:
    log(f"REBOOT: {reboot_why}")
    sudo("systemctl", "reboot")
PY
