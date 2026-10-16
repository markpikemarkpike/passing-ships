#!/bin/bash
# Passing Ships one-line installer. Run on a fresh Raspberry Pi OS Lite (64-bit).
#
#   curl -fsSLo install.sh https://raw.githubusercontent.com/markpikemarkpike/passing-ships/v1.0.0/setup/install.sh
#   sha256sum -c <<< "<sha256 from the release notes>  install.sh"   # optional but recommended
#   bash install.sh --role radio
#   bash install.sh --role frame --radio radio.local --buoy 46014
#
# The scripts always check out the same pinned release (REF below), never a moving branch.
#
# --role radio            the Pi with the antenna (SDR dongle, or --daisy for a dAISy-catcher)
# --role frame            the Pi inside the e-ink frame
# If --role is omitted, the hostname decides: "radio" or "ships".
#
# Radio options:  --daisy            use a dAISy-catcher instead of an RTL-SDR. Found by itself: on a USB cable
#                                    if one is plugged in, else on the GPIO header (/dev/serial0)
#                 --daisy-port PATH  ...or say exactly where it is
#                 --pod              unattended outdoor build: hardware watchdog, self-reboot when the feed or
#                                    the wifi dies, logs in RAM; finish with ~/pod-freeze.sh (read-only card)
#                 --share            feed aiscatcher.org; you'll be prompted for your station's sharing key
#                                    (not a flag, so it never lands in shell history)
#                 --duty-cycle       rest the SDR dongle 25 min an hour with its USB power cut (cheap-dongle heat fix;
#                                    needs a Pi 3/4/5, a Zero cannot switch its port; ignored with --daisy)
# Frame options:  --radio HOST       hostname/IP of the radio Pi (default radio.local)
#                 --buoy NNNNN       nearest NOAA NDBC buoy station number (default 46014, Point Arena)
#                 --lat N --lon N    your coordinates (default: The Sea Ranch)
#                 --place "NAME"     the words in the corner of every painting
#                 --sea-bearing N    compass bearing from your wall out to sea (default 247.5; an east coast is ~90)
#                 --timezone Area/City   set the Pi's clock zone (the imager can too)
#
# Takes 15-40 minutes (AIS-catcher compiles on the radio Pi). Reboots when done.
set -euo pipefail

REPO_URL="${PASSING_SHIPS_REPO:-https://github.com/markpikemarkpike/passing-ships.git}"
REF="${PASSING_SHIPS_REF:-v1.0.0}"   # the release this script belongs to
DEST="$HOME/passing-ships"
ROLE=""
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --role) ROLE="$2"; shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
if [ -z "$ROLE" ]; then
  case "$(hostname)" in
    radio) ROLE=radio ;;
    ships) ROLE=frame ;;
    *) echo "Pass --role radio or --role frame (or name the host radio/ships)."; exit 1 ;;
  esac
fi

sudo apt-get update -qq
sudo apt-get install -y -qq git
if [ ! -d "$DEST/.git" ]; then git clone -q "$REPO_URL" "$DEST"; fi
git -C "$DEST" fetch -q --tags origin && git -C "$DEST" checkout -q "$REF"

case "$ROLE" in
  radio) bash "$DEST/setup/radio.sh" "${ARGS[@]}" ;;
  frame) bash "$DEST/setup/frame.sh" "${ARGS[@]}" ;;
  *) echo "unknown role $ROLE"; exit 1 ;;
esac
