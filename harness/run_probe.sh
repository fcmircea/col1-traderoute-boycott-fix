#!/bin/bash
# Boot, load the first save, then drive turns with SPACE and decode a
# trade-route carrier from a RAM dump every 6 steps. No gdb.
#
#   ./run_probe.sh disk.img boot-floppy.img COLONY00.SAV out-tag [seconds]
#
# Writes probe_<tag>/log.txt and probe_<tag>/snaps/ in the current folder.
# The save file is the same one that is on the disk; it is only read, to find
# the tables in RAM (decode_route.py). About 8 game turns per 420 s.
#
# Environment: QEMU [qemu-system-i386], BOOT_WAIT [47], DECODE_ARGS [].
set -uo pipefail
IMG=${1:?usage: run_probe.sh <disk.img> <floppy.img> <save> <tag> [seconds]}
FL=${2:?}; SAV=${3:?}; TAG=${4:-run}; SECS=${5:-420}
QEMU=${QEMU:-qemu-system-i386}; BOOT_WAIT=${BOOT_WAIT:-47}
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(pwd)/probe_$TAG"; rm -rf "$OUT"; mkdir -p "$OUT/snaps"
W=$(mktemp -d); S="$W/qmon.sock"; QPID=
cleanup(){ [ -n "$QPID" ] && kill -9 "$QPID" 2>/dev/null; rm -rf "$W"; }
trap cleanup EXIT
cp "$IMG" "$W/disk.img"; cp "$FL" "$W/fl.img"

"$QEMU" -m 16 -drive file="$W/fl.img",format=raw,if=floppy \
  -drive file="$W/disk.img",format=raw,if=ide,index=0,media=disk \
  -boot a -display none -monitor unix:"$S",server,nowait 2>"$W/qemu.err" &
QPID=$!

# NOTE: the space in "-T 4" is required. "-T4" silently does nothing.
M(){ printf '%s\n' "$1" | socat -T 4 - unix-connect:"$S" >/dev/null 2>&1 || true; }
snap(){ M "screendump \"$W/s.ppm\""; sleep .6; convert "$W/s.ppm" "$OUT/snaps/$1.png" 2>/dev/null; }
dec(){ python3 "$HERE/decode_route.py" "$SAV" "$W/mem.bin" ${DECODE_ARGS:-} "$@"; }

sleep "$BOOT_WAIT"
kill -0 "$QPID" 2>/dev/null || { echo "qemu died:" >&2; cat "$W/qemu.err" >&2; exit 1; }
M 'sendkey down'; sleep .6; M 'sendkey down'; sleep .6; M 'sendkey down'; sleep .6
M 'sendkey ret'; sleep 4                    # LOAD Game
M 'sendkey ret'; sleep 11                   # first save slot
M 'mouse_move -3000 -3000'; sleep .4; M 'mouse_move 320 200'; sleep .4
M 'mouse_button 1'; sleep .3; M 'mouse_button 0'; sleep 2
snap 00_loaded
M "pmemsave 0 0x100000 \"$W/mem.bin\""; sleep 4
dec --init >> "$OUT/log.txt" 2>&1 || { echo "locate failed" >&2; exit 1; }

# SPACE only. Enter, Escape and map clicks derail the game (docs/DEAD-ENDS.md).
START=$(date +%s); n=0
while [ $(( $(date +%s) - START )) -lt "$SECS" ]; do
  M "screendump \"$W/cur.ppm\""; sleep .5
  POP=$(python3 "$HERE/detect_popup.py" "$W/cur.ppm" 2>/dev/null || echo NOPOPUP)
  if [ "${POP%% *}" = POPUP ]; then
    Y=${POP#* }
    M 'mouse_move -3000 -3000'; sleep .3; M "mouse_move 150 $Y"; sleep .3
    M 'mouse_button 1'; sleep .2; M 'mouse_button 0'; sleep .4
  else
    M 'sendkey spc'; sleep .5
  fi
  n=$((n + 1))
  if [ $((n % 6)) -eq 0 ]; then
    M "pmemsave 0 0x100000 \"$W/mem.bin\""; sleep 2
    echo "n=$n t=$(( $(date +%s) - START )) $(dec 2>&1)" >> "$OUT/log.txt"
  fi
  [ $((n % 30)) -eq 0 ] && snap "t_$n"
done
snap 99_final; M quit; sleep 1
cat "$OUT/log.txt"
