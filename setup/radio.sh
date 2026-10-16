#!/bin/bash
# Radio Pi setup: AIS receiver + health watchdog. Called by install.sh.
set -euo pipefail
DEST="$HOME/passing-ships"
DAISY=0; DAISY_PORT=""; SHARE=0; SHARE_KEY=""; DUTY=0; POD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --daisy) DAISY=1; shift ;;
    --daisy-port) DAISY=1; DAISY_PORT="$2"; shift 2 ;;
    --share) SHARE=1; shift ;;
    --duty-cycle) DUTY=1; shift ;;
    --pod) POD=1; shift ;;
    *) echo "radio.sh: unknown option $1"; exit 1 ;;
  esac
done
U="$(id -un)"; H="$HOME"
CONF="$H/.config/passing-ships"; mkdir -p "$CONF"
SHARECONF="$CONF/share.json"
BOOTCFG=/boot/firmware/config.txt; [ -f "$BOOTCFG" ] || BOOTCFG=/boot/config.txt
bootcfg() { grep -qxF "$1" "$BOOTCFG" || echo "$1" | sudo tee -a "$BOOTCFG" >/dev/null; }
if [ "$SHARE" = 1 ] && [ ! -s "$SHARECONF" ]; then
  read -r -s -p "aiscatcher.org sharing key (shown when you registered your station): " SHARE_KEY < /dev/tty; echo
  # A key is a UUID. Checking the shape catches a bad paste, and means nothing odd can end up inside the JSON.
  if ! [[ "$SHARE_KEY" =~ ^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$ ]]; then   # the whole string, not line by line
    echo "radio.sh: that does not look like a sharing key (expected 8-4-4-4-12 hex digits). Nothing saved; run again."; exit 1
  fi
  (umask 077; printf '{"config":"aiscatcher","version":1,"sharing":true,"sharing_key":"%s"}\n' "$SHARE_KEY" > "$SHARECONF")
  unset SHARE_KEY
fi

echo "== packages"
sudo apt-get install -y -qq python3 uhubctl rtl-sdr librtlsdr-dev cmake build-essential pkg-config libusb-1.0-0-dev zlib1g-dev libssl-dev

echo "== AIS-catcher (GPL-3.0, separate program, jvde-github)"
if ! command -v AIS-catcher >/dev/null; then
  AC_REF=8833c64b3da0c42e9a724b9bd13eaab2fffadcca   # v0.70. A commit, not the tag: a tag can be moved. Bump deliberately after testing.
  # One compiler per core wants more memory than a small Pi has, and the kernel
  # ends the build by killing it. Slower beats dead.
  MEM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
  JOBS=$(nproc); [ "$MEM_MB" -lt 3000 ] && JOBS=2; [ "$MEM_MB" -lt 900 ] && JOBS=1
  tmp=$(mktemp -d); git init -q "$tmp/ac"
  git -C "$tmp/ac" remote add origin https://github.com/jvde-github/AIS-catcher
  git -C "$tmp/ac" fetch -q --depth 1 origin "$AC_REF"
  git -C "$tmp/ac" checkout -q FETCH_HEAD
  [ "$(git -C "$tmp/ac" rev-parse HEAD)" = "$AC_REF" ] || { echo "radio.sh: did not get the pinned AIS-catcher commit"; exit 1; }
  (cd "$tmp/ac" && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release >/dev/null && make -j"$JOBS" >/dev/null && sudo make install >/dev/null)
  rm -rf "$tmp"
fi
AC="$(command -v AIS-catcher)"

RECOVER=none; HUB_LOC=1; HUB_PORT=1
if [ "$DAISY" = 1 ]; then
  if [ -z "$DAISY_PORT" ]; then
    # On a USB cable the receiver appears under by-id, a name that does not move
    # the way ttyACM0 can. Seated on the GPIO header it is the Pi's own UART.
    for p in /dev/serial/by-id/*; do [ -e "$p" ] && { DAISY_PORT="$p"; break; }; done
    DAISY_PORT="${DAISY_PORT:-/dev/serial0}"
  fi
  echo "== dAISy-catcher on $DAISY_PORT"
  if [ "$DAISY_PORT" = /dev/serial0 ]; then
    echo "   GPIO header: enable the UART, free it from the login console and from Bluetooth"
    sudo raspi-config nonint do_serial_hw 0
    sudo raspi-config nonint do_serial_cons 1
    # Boards with Bluetooth give it the good UART and leave the header a lesser one
    # whose small buffer drops characters under load. The radio Pi needs no Bluetooth.
    bootcfg "dtoverlay=disable-bt"
    sudo systemctl disable --now hciuart 2>/dev/null || true
  fi
  sudo usermod -aG dialout "$U"
  # init_seq asks the receiver to report signal level and frequency offset with each message
  INPUT="-e 115200 $DAISY_PORT -ge init_seq co2,v"
  DUTY=0
else
  echo "== RTL-SDR: block the DVB driver so the dongle is free for AIS"
  echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl.conf >/dev/null
  # AIS-catcher's recommended line for RTL-SDR: 288K sample rate, AGC on, wide AFC
  INPUT="-s 288K -gr TUNER auto RTLAGC on -a 192K -go AFC_WIDE on"
  # Which hub and port is the dongle on, and can that port's power be switched?
  # (Pi 3/4/5: yes. Any Pi Zero: no, its single port is always live.)
  if read -r HUB_LOC HUB_PORT < <(sudo uhubctl 2>/dev/null | awk '
        /^Current status for hub/ {hub = $5}
        /0bda:283[28]/            {sub(":", "", $2); print hub, $2; exit}') && [ -n "${HUB_PORT:-}" ]; then
    RECOVER=uhubctl
    echo "   dongle on hub $HUB_LOC port $HUB_PORT, power switchable"
  else
    HUB_LOC=1; HUB_PORT=1
    echo "   this board cannot switch the dongle's USB power (or the dongle is not plugged in):"
    echo "   the watchdog will restart the receiver but cannot power-cycle it"
    [ "$DUTY" = 1 ] && echo "   --duty-cycle ignored for the same reason"
    DUTY=0
  fi
fi
# The key lives in a 0600 config file that AIS-catcher reads itself (-C), so it is not in the unit
# file, the shell history, or the process list. Register a new station if the Pi is ever lost.
SHAREOPT=""; [ -s "$SHARECONF" ] && SHAREOPT="-C $SHARECONF"

echo "== services"
sudo tee /etc/systemd/system/ais-catcher.service >/dev/null <<EOF
[Unit]
Description=AIS-catcher receiver (web map + ships.json on :8100)
After=network.target

[Service]
User=$U
ExecStart=/bin/sh -c 'exec $AC $INPUT $SHAREOPT -N 8100 -v 60'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# what the watchdog may do on this build (radio/ais-watch.sh explains each)
cat > "$CONF/watch.env" <<EOF
RECOVER=$RECOVER
HUB_LOC=$HUB_LOC
HUB_PORT=$HUB_PORT
DUTY_CYCLE=$DUTY
REBOOT_AFTER_H=$([ "$POD" = 1 ] && echo 8 || echo 0)
NET_REBOOT_AFTER_MIN=$([ "$POD" = 1 ] && echo 120 || echo 0)
EOF
mkdir -p "$H/status"
install -m 755 "$DEST/radio/ais-watch.sh" "$H/ais-watch.sh"
sed -i "s#/home/mark#$H#g" "$H/ais-watch.sh"
for f in ais-watch.service ais-watch.timer; do
  sed "s#/home/mark#$H#g; s#User=mark#User=$U#" "$DEST/radio/$f" | sudo tee /etc/systemd/system/$f >/dev/null
done
# health.json for the frame (curator reads :8101/health.json)
sudo tee /etc/systemd/system/health-server.service >/dev/null <<EOF
[Unit]
Description=Serve ~/status (health.json) on :8101
After=network.target

[Service]
User=$U
WorkingDirectory=$H/status
ExecStart=/usr/bin/python3 -m http.server 8101 --bind 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ais-catcher health-server ais-watch.timer

if [ "$DUTY" = 1 ]; then
  echo "== dongle duty cycle (35 min on / 25 min off, for cheap-dongle heat)"
  for f in dongle-on.service dongle-on.timer dongle-off.service dongle-off.timer; do
    sed "s#-l 1 -p 1 #-l $HUB_LOC -p $HUB_PORT #" "$DEST/radio/$f" | sudo tee /etc/systemd/system/$f >/dev/null
  done
  sudo systemctl daemon-reload
  sudo systemctl enable dongle-on.timer dongle-off.timer
fi

if [ "$POD" = 1 ]; then
  echo "== pod: nobody can walk up and pull the plug, so the board must rescue itself"
  # A hung kernel stops feeding the SoC's own timer and the chip resets the board.
  # 15 s is the most this hardware can count.
  bootcfg "dtparam=watchdog=on"
  sudo mkdir -p /etc/systemd/system.conf.d /etc/systemd/journald.conf.d
  printf '[Manager]\nRuntimeWatchdogSec=15\nRebootWatchdogSec=2min\n' | sudo tee /etc/systemd/system.conf.d/pod-watchdog.conf >/dev/null
  # Logs in memory: the card is about to become read-only, and until then this spares it.
  printf '[Journal]\nStorage=volatile\nRuntimeMaxUse=16M\n' | sudo tee /etc/systemd/journald.conf.d/pod.conf >/dev/null
  # Every milliwatt comes off the battery in December.
  bootcfg "dtoverlay=disable-bt"
  sudo systemctl disable --now hciuart bluetooth 2>/dev/null || true
  sudo systemctl disable --now dphys-swapfile 2>/dev/null || true
  install -m 755 "$DEST/setup/pod-freeze.sh" "$H/pod-freeze.sh"
  echo
  echo "   The card is still WRITABLE. Soak the pod on the bench for a day or two, then run"
  echo "   ~/pod-freeze.sh to make the root filesystem read-only. Do that last: nothing you"
  echo "   change afterwards (wifi networks included) survives a reboot."
fi

echo "== done. Rebooting. Web map: http://$(hostname).local:8100  ships.json: /api/ships.json"
sudo reboot
