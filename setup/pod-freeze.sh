#!/bin/bash
# Make the pod's root filesystem read-only (an overlay in RAM takes the writes).
# A card that is never written cannot be corrupted by a brown-out, and nothing,
# including a mistake made over a remote shell, can delete its wifi settings.
#
#   ~/pod-freeze.sh          freeze, after the checks below
#   ~/pod-freeze.sh --thaw   back to a normal writable card (to change anything)
#
# Run it LAST. After the freeze every change is forgotten at the next reboot.
set -euo pipefail
if [ "${1:-}" = --thaw ]; then
  sudo raspi-config nonint do_overlayfs 1
  echo "Writable again after this reboot. (If /boot/firmware is still read-only afterwards,"
  echo "run --thaw once more: the boot partition can only be released once the overlay is gone.)"
  sudo reboot; exit 0
fi

echo "Wifi networks saved on this card:"
nmcli -t -f NAME,TYPE connection show | awk -F: '$2 ~ /wireless/ {print "   " $1; n++} END {if (!n) print "   (none)"}'
echo "If you built this somewhere other than where it will live, BOTH networks must be"
echo "in that list. A Pi Zero has no ethernet: a frozen pod that cannot join the wifi at"
echo "its post has to come back indoors and have its card pulled. To add one now:"
echo "   sudo nmcli connection add type wifi con-name SITE ssid 'NAME' wifi-sec.key-mgmt wpa-psk wifi-sec.psk 'PASSPHRASE'"
echo
echo "Receiver: $(systemctl is-active ais-catcher)   last health: $(cat "$HOME/status/health.json" 2>/dev/null || echo none yet)"
echo "Timezone: $(timedatectl show -p Timezone --value)"
echo
read -r -p "Freeze this card now? [y/N] " a < /dev/tty
[ "$a" = y ] || [ "$a" = Y ] || { echo "Left writable."; exit 0; }
sudo raspi-config nonint do_overlayfs 0
echo "Frozen after this reboot. Check with: findmnt -no FSTYPE /   (says 'overlay')"
sudo reboot; exit 0
