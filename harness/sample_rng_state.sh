#!/bin/bash
# Sample the game's RNG state at full speed through the QEMU monitor.
#
#   sample_rng_state.sh <disk.img> <boot-floppy.img> <out.tsv>
#
# No gdb and no breakpoints: the guest and its clock run normally. A trap on a
# hot path freezes guest time (QEMU stops the clock while the gdb stub holds
# the CPU), which starves the tick-based seeder and fakes the result.
#
# The floppy must start the game by itself (see make_boot_floppy.sh). After
# boot the script loads the first save slot, finds DS, then reads the 32-bit
# LCG state at DS:0x28EE (low) / DS:0x28F0 (high) N times.
#
# Output: tab-separated "i  seconds  low  high"  (hex words).
#
# Environment (defaults in brackets):
#   QEMU        qemu-system-i386 binary      [qemu-system-i386]
#   N           number of samples            [40]
#   INTERVAL    seconds between samples      [1.5]
#   BOOT_WAIT   seconds from power-on to menu [47]
#
# Everything runs inside this one process: the VM does not survive between
# calls. Only the QEMU started here is killed.
set -euo pipefail

IMG=${1:?usage: sample_rng_state.sh <disk.img> <floppy.img> <out.tsv>}
FLOPPY=${2:?usage: sample_rng_state.sh <disk.img> <floppy.img> <out.tsv>}
OUT=${3:?usage: sample_rng_state.sh <disk.img> <floppy.img> <out.tsv>}
QEMU=${QEMU:-qemu-system-i386}
N=${N:-40}
INTERVAL=${INTERVAL:-1.5}
BOOT_WAIT=${BOOT_WAIT:-47}

WORK=$(mktemp -d)
SOCK="$WORK/qmon.sock"
QPID=
cleanup() {
  if [ -n "$QPID" ] && kill -0 "$QPID" 2>/dev/null; then
    kill -9 "$QPID" 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

# The disk is written by the guest; work on a copy so the input stays clean.
cp "$IMG" "$WORK/disk.img"
cp "$FLOPPY" "$WORK/floppy.img"

"$QEMU" -m 16 \
  -drive file="$WORK/floppy.img",format=raw,if=floppy \
  -drive file="$WORK/disk.img",format=raw,if=ide,index=0,media=disk \
  -boot a -display none \
  -monitor unix:"$SOCK",server,nowait 2>"$WORK/qemu.err" &
QPID=$!

# NOTE: the space in "-T 4" is required. "-T4" silently does nothing.
M()  { printf '%s\n' "$1" | socat -T 4 - unix-connect:"$SOCK" >/dev/null 2>&1 || true; }
MO() { printf '%s\n' "$1" | socat -T 4 - unix-connect:"$SOCK" 2>/dev/null | tr -d '\r' || true; }

sleep "$BOOT_WAIT"
kill -0 "$QPID" 2>/dev/null || { echo "qemu died:" >&2; cat "$WORK/qemu.err" >&2; exit 1; }

# Main menu -> LOAD GAME -> first slot. SPACE/arrows/Enter only here;
# Escape on the map quits to DOS.
M 'sendkey down'; sleep .6; M 'sendkey down'; sleep .6; M 'sendkey down'; sleep .6
M 'sendkey ret'; sleep 4
M 'sendkey ret'; sleep 11
# The load confirmation is click-to-dismiss; the centre is forgiving.
M 'mouse_move -3000 -3000'; sleep .4; M 'mouse_move 320 200'; sleep .4
M 'mouse_button 1'; sleep .3; M 'mouse_button 0'; sleep 2

# DS can be caught mid-interrupt, so read it several times and take the mode.
DS=$(for _ in 1 2 3 4 5 6 7; do
       MO 'info registers' | grep -oE 'DS =[0-9a-fA-F]+' | head -1 | grep -oE '[0-9a-fA-F]+$'
       sleep .3
     done | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
[ -n "$DS" ] || { echo "could not read DS" >&2; exit 1; }
ADDR=$(printf '0x%x' $(( 0x$DS * 16 + 0x28EE )))
echo "DS=$DS  state at $ADDR" >&2
M "screendump \"$WORK/loaded.ppm\""; sleep .6
cp -f "$WORK/loaded.ppm" "${OUT%.tsv}.loaded.ppm" 2>/dev/null || true

: > "$OUT"
START=$(date +%s.%N)
for i in $(seq 1 "$N"); do
  V=$(MO "xp/2xh $ADDR" | grep -oE '0x[0-9a-f]{4} 0x[0-9a-f]{4}' | head -1 || true)
  T=$(echo "$(date +%s.%N) - $START" | bc)
  printf '%s\t%s\t%s\t%s\n' "$i" "$T" ${V:-? ?} >> "$OUT"
  sleep "$INTERVAL"
done

M quit
echo "wrote $N samples to $OUT" >&2
