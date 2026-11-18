#!/bin/bash
# soak.sh [RUN_DIR]: four laps of the 13 multiplayer maps, 12 s each, RSS every 2 s.
# The Deck and the Nova run in parallel, the AppImage and then the Flatpak on each. Output lines are prefixed with
# the column name. RUN_DIR defaults to $OPENCE_VALIDATE_DIR/<date>-soak ($OPENCE_VALIDATE_DIR defaults to
# ~/opence-validate). Needs the game ids of the four shortcuts: OPENCE_GID_DECK_APPIMAGE, OPENCE_GID_DECK_FLATPAK,
# OPENCE_GID_NOVA_APPIMAGE and OPENCE_GID_NOVA_FLATPAK (vdf_list.py prints them; see devices.py).
# For the G14 reference: run_full.py --device g14 --package ref --maps soak --seconds 12 --rss-every 2 --run RUN_DIR
case "$1" in
  -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac
cd "$(dirname "$0")" || exit 1
R=${1:-${OPENCE_VALIDATE_DIR:-$HOME/opence-validate}/$(date +%Y%m%d)-soak}
A=(--maps soak --seconds 12 --rss-every 2 --status-every 13 --run "$R")
( python3 -u run_full.py --device deck --package appimage "${A[@]}" 2>&1 | sed -u 's/^/[deck-appimage] /'
  python3 -u run_full.py --device deck --package flatpak "${A[@]}" 2>&1 | sed -u 's/^/[deck-flatpak] /' ) &
( python3 -u run_full.py --device nova --package appimage "${A[@]}" 2>&1 | sed -u 's/^/[nova-appimage] /'
  python3 -u run_full.py --device nova --package flatpak "${A[@]}" 2>&1 | sed -u 's/^/[nova-flatpak] /' ) &
wait
