#!/bin/bash
# Frame Pi setup: panel driver + painter + curator timers. Called by install.sh.
set -euo pipefail
DEST="$HOME/passing-ships"
RADIO=""; BUOY=""; LAT=""; LON=""; PLACE=""; SEA=""; TZ_NAME=""     # empty = not given on the command line
while [ $# -gt 0 ]; do
  case "$1" in
    --radio) RADIO="$2"; shift 2 ;;
    --buoy) BUOY="$2"; shift 2 ;;
    --lat) LAT="$2"; shift 2 ;;
    --lon) LON="$2"; shift 2 ;;
    --place) PLACE="$2"; shift 2 ;;
    --sea-bearing) SEA="$2"; shift 2 ;;
    --timezone) TZ_NAME="$2"; shift 2 ;;
    *) echo "frame.sh: unknown option $1"; exit 1 ;;
  esac
done
U="$(id -un)"; H="$HOME"

echo "== packages (numpy/opencv from apt: pip builds take hours on a Zero)"
sudo apt-get install -y -qq python3-numpy python3-opencv python3-pil python3-spidev python3-gpiozero python3-rpi-lgpio fonts-liberation

echo "== clock"
# Quiet hours, the light in the sky and the time in the caption all follow the
# Pi's local clock, and a fresh card thinks it is in London.
[ -n "$TZ_NAME" ] && sudo timedatectl set-timezone "$TZ_NAME"
echo "   timezone: $(timedatectl show -p Timezone --value)   (wrong? re-run with --timezone America/Los_Angeles)"

echo "== SPI on"
sudo raspi-config nonint do_spi 0

echo "== Waveshare e-Paper library (vendor's, fetched not vendored)"
if [ ! -d "$H/epaper" ]; then
  # the repo carries every panel's firmware and docs; fetch only the one folder
  LIB=RaspberryPi_JetsonNano/python/lib/waveshare_epd
  # Pinned, like the receiver: this code drives the panel on your Pi, so you get the commit
  # this release was written against, not whatever the vendor pushed this morning.
  WV_REF=6781b6af588ba5c8b82e3861220b699b6f1dafcf   # 11 Dec 2025; bump deliberately after testing
  tmp=$(mktemp -d); git init -q "$tmp/wv"
  git -C "$tmp/wv" remote add origin https://github.com/waveshareteam/e-Paper
  git -C "$tmp/wv" sparse-checkout set "$LIB"
  git -C "$tmp/wv" fetch -q --depth 1 --filter=blob:none origin "$WV_REF"
  git -C "$tmp/wv" checkout -q FETCH_HEAD
  [ "$(git -C "$tmp/wv" rev-parse HEAD)" = "$WV_REF" ] || { echo "frame.sh: did not get the pinned Waveshare commit"; exit 1; }
  mkdir -p "$H/epaper"; cp -r "$tmp/wv/$LIB" "$H/epaper/"; rm -rf "$tmp"
fi
# PhotoPainter frame wiring: the panel's PWR pin is BCM 27, not the HAT's 18. With
# the wrong pin nothing errors: the driver returns at once and the wall never
# changes. The line is indented (a class attribute), and sed succeeds whether or
# not it matched, so check.
sed -i -E 's/^([[:space:]]*PWR_PIN[[:space:]]*=[[:space:]]*)18\b/\127/' "$H/epaper/waveshare_epd/epdconfig.py"
if ! grep -qE '^[[:space:]]*PWR_PIN[[:space:]]*=[[:space:]]*27\b' "$H/epaper/waveshare_epd/epdconfig.py"; then
  echo "frame.sh: could not set PWR_PIN = 27 in ~/epaper/waveshare_epd/epdconfig.py (vendor file changed?)."
  echo "          Edit it by hand before going on, or the panel will not drive."; exit 1
fi
install -m 755 "$DEST/setup/show.py" "$H/show.py"

echo "== config"
mkdir -p "$H/.curator"
CFG="$H/.curator/config.env"
setkey() {   # setkey KEY VALUE: replace that line, or add it
  grep -v "^$1=" "$CFG" > "$CFG.tmp" || true
  echo "$1=$2" >> "$CFG.tmp"; mv "$CFG.tmp" "$CFG"; echo "   $1=$2"
}
if [ -s "$CFG" ]; then
  echo "   keeping your ~/.curator/config.env; changing only what you passed just now:"
  [ -z "$RADIO" ] || setkey AIS_URL "http://$RADIO:8100/api/ships.json"
  [ -z "$BUOY" ]  || setkey BUOY "$BUOY"
  [ -z "$LAT" ]   || setkey LAT "$LAT"
  [ -z "$LON" ]   || setkey LON "$LON"
  [ -z "$PLACE" ] || setkey PLACE "$PLACE"
  [ -z "$SEA" ]   || setkey SEA_BEARING "$SEA"
  # settings newer than the file get their defaults written in, so they can be seen and edited
  grep -q '^PLACE=' "$CFG"       || setkey PLACE "THE SEA RANCH"
  grep -q '^SEA_BEARING=' "$CFG" || setkey SEA_BEARING 247.5
else
cat > "$CFG" <<EOF
# Passing Ships frame config. Edit and restart curator.timer.
AIS_URL=http://${RADIO:-radio.local}:8100/api/ships.json
BUOY=${BUOY:-46014}
LAT=${LAT:-38.72}
LON=${LON:--123.45}
# The words in the corner of every painting.
PLACE=${PLACE:-THE SEA RANCH}
# Compass bearing from your wall out to sea (west coast ~250, east coast ~90).
# Decides which way ships sail across the picture and which end of the day
# puts the sun on the water.
SEA_BEARING=${SEA:-247.5}
MAX_RANGE_NMI=100
QUIET_START=23
QUIET_END=7
# Optional: other NDBC stations to ask for a fog estimate when your buoy's air
# sensors are out (they die for months). Comma separated, nearest first.
# BUOY_NEIGHBOURS=
EOF
fi
# config.py reads every key above; a malformed value falls back to its default.

echo "== services"
for unit in curator sightings; do
  sudo tee /etc/systemd/system/$unit.service >/dev/null <<EOF
[Unit]
Description=Passing Ships $unit
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$U
WorkingDirectory=$DEST
EnvironmentFile=$H/.curator/config.env
ExecStart=/usr/bin/python3 $DEST/$unit.py
# a oneshot has no time limit of its own, and a timer will not start a unit that
# is still running: one hung run would silently end all the ones after it
TimeoutStartSec=15min
EOF
done
sudo tee /etc/systemd/system/curator.timer >/dev/null <<'EOF'
[Unit]
Description=Paint on the hour

[Timer]
OnCalendar=*:00:00
Persistent=false

[Install]
WantedBy=timers.target
EOF
sudo tee /etc/systemd/system/sightings.timer >/dev/null <<'EOF'
[Unit]
Description=Log every ship in range, every 5 min

[Timer]
OnCalendar=*:0/5
Persistent=false

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable curator.timer sightings.timer

echo "== done. Rebooting. First painting arrives on the hour; log: ~/.curator/log.txt"
sudo reboot
