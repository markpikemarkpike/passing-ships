#!/bin/bash
# Regression test for ais-watch.sh. Runs anywhere with bash + python3; touches nothing.
#
#   bash radio/test-watch.sh
#
# The real script is run over simulated hours with a faked clock, uptime and system
# commands (journalctl, systemctl, sudo, uhubctl, nmcli, ping), and what it ASKED the
# system to do is counted. Written after the Aug 7 version was found never to save its
# state: it power-cycled the dongle on every silent run and could never say DEAF.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
fake() { printf '#!/bin/bash\n%s\n' "$2" > "$T/bin/$1"; chmod +x "$T/bin/$1"; }
fake journalctl 'echo "AIS-catcher[1]: [AIS engine] received: ${MSGS:-0} msgs, total: 1 msgs"'
fake systemctl  'case "$1" in is-active) echo active;; is-enabled) exit 1;; esac'
fake sudo       '[ "$1" = -n ] && shift; case "$1" in */uhubctl) echo uhubctl;; systemctl) echo "$2";; nmcli) echo "wifi-$4";; esac >> "$ACTIONS"'
fake ip         'echo "default via 192.0.2.1 dev wlan0"'
fake ping       '[ "${NETUP:-1}" = 1 ]'
fake date       'case "$*" in *%-M*) echo 47;; *) echo 2026-01-01T00:47;; esac'
sed -e "s#/home/mark#$T/home#g" -e 's/time\.sleep([0-9]*)/pass/' "$HERE/ais-watch.sh" > "$T/ais-watch.sh"
export ACTIONS="$T/actions" PATH="$T/bin:$PATH"
fails=0

# sim <start uptime, min> <runs> <msgs: one number, or a comma list per run> [VAR=value ...]
# Steps the timer's real rhythm (:37 :47 :57). Writes "minute verdict streak action..." per run to $T/trace.
# RO=1 wipes everything the script wrote at each reboot, as a read-only root does.
sim() { local up=$1 runs=$2 msgs=$3 t=0 i m; shift 3
  rm -rf "${T:?}/home" "${T:?}/trace"; mkdir -p "$T/home/status"
  for i in $(seq 1 "$runs"); do
    : > "$ACTIONS"; m=$msgs; case "$msgs" in *,*) m=$(echo "$msgs" | cut -d, -f"$i");; esac
    env "$@" MSGS="$m" WATCH_NOW=$((1800000000 + t * 60)) WATCH_UPTIME_S=$((up * 60)) bash "$T/ais-watch.sh"
    echo "$t $(python3 -c "import json;h=json.load(open('$T/home/status/health.json'));print(h['verdict'],h['weak_streak'])") $(tr '\n' ' ' < "$ACTIONS")" >> "$T/trace"
    if grep -q '^reboot' "$ACTIONS"; then up=0; [ "${RO:-0}" = 1 ] && rm -rf "${T:?}/home/status/"* "${T:?}/home/"*.log; fi
    local gap=10; [ $((i % 3)) = 0 ] && gap=40
    t=$((t + gap)); up=$((up + gap))
  done; }
count()  { grep -c " $1" "$T/trace"; }
mingap() { awk -v a="$1" '$0 ~ " "a {if (p != "" && (m == "" || $1 - p < m)) m = $1 - p; p = $1} END {print (m == "" ? 99999 : m)}' "$T/trace"; }
check()  { if test "$2" "$3" "$4"; then echo "PASS $1"; else echo "FAIL $1   got $2, want $3 $4"; fails=$((fails + 1)); sed 's/^/       /' "$T/trace"; fi; }

sim 600 14 0
check "SDR, 4.5 silent hours: power-cycled twice, not fourteen times"  "$(count uhubctl)" -eq 2
check "...never closer together than the cooldown"                      "$(mingap uhubctl)" -ge 170
check "...and DEAF is reached (the frame can say CHECK ANTENNA CONNECTOR)" "$(count DEAF)" -ge 6
check "...and the weak streak counts up in hours"                       "$(tail -1 "$T/trace" | cut -d' ' -f3)" -ge 4
check "state survives between runs"                                     "$(grep -c cycled_at "$T/home/status/watch-state.json")" -eq 1

sim 600 1 0 HUB_ALL="1 2 3 4" WATCH_OFF_S=0
check "Pi 5: every onboard hub goes off, then every one comes back on"  "$(head -1 "$T/trace" | grep -o uhubctl | wc -l | tr -d ' ')" -eq 8

sim 600 5 0,0,0,0,5
check "one ship heard: back to OK, streak cleared"  "$(tail -1 "$T/trace" | cut -d' ' -f2,3 | tr -d ' ')" = OK0

sim 7 9 0
check "fresh boot into a quiet night: nothing is restarted on no evidence"  "$(awk 'NF > 3' "$T/trace" | wc -l | tr -d ' ')" -eq 0

RO=1 sim 470 60 0 RECOVER=none REBOOT_AFTER_H=8 NET_REBOOT_AFTER_MIN=120
check "pod, dead receiver for 19 h on a read-only card: three reboots"  "$(count reboot)" -eq 3
check "...never more often than every 8 h, though nothing it wrote survives"  "$(mingap reboot)" -ge 480
check "...and it never reaches for a USB switch it does not have"       "$(count uhubctl)" -eq 0

RO=1 sim 600 16 9 RECOVER=none REBOOT_AFTER_H=8 NET_REBOOT_AFTER_MIN=120 NETUP=0
check "pod, ships fine, house router off 5 h: wifi bounced first"       "$(head -1 "$T/trace" | grep -c 'wifi-off wifi-on')" -eq 1
check "...then rebooted, at most every 2 h"                             "$(mingap reboot)" -ge 120
check "...and the receiver is left alone"                               "$(count restart)" -eq 0

sim 600 12 9 NETUP=0
check "indoor build: a router outage is none of its business"           "$(awk 'NF > 3' "$T/trace" | wc -l | tr -d ' ')" -eq 0

echo; [ "$fails" = 0 ] && echo "ALL PASS" || { echo "$fails FAILED"; exit 1; }
