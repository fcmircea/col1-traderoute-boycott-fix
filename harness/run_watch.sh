#!/bin/bash
# One-shot: boot, load the first save, locate a colony's commodity word, attach
# gdb with a watchpoint on it, then drive turns until it fires.
#
#   ./run_watch.sh chd.img colboot.img out-tag
#
# Must run inside a SINGLE invocation - the VM cannot survive between calls.
# Allow ~5 minutes.
set -u
IMG=${1:?disk image}; FLOPPY=${2:?boot floppy}; TAG=${3:-run}
QEMU=${QEMU:-qemu-system-i386}
HERE="$(cd "$(dirname "$0")" && pwd)"

rm -f /tmp/hits.log /tmp/qmon.sock /tmp/cur.ppm
rm -rf "snaps_$TAG"; mkdir -p "snaps_$TAG"
pkill -9 -f qemu-system-i386 2>/dev/null; sleep 2

$QEMU -m 16 \
  -drive file="$FLOPPY",format=raw,if=floppy \
  -drive file="$IMG",format=raw,if=ide,index=0,media=disk \
  -boot a -display none \
  -monitor unix:/tmp/qmon.sock,server,nowait 2>/dev/null &
QPID=$!

# NOTE: the space in "-T 4" is required. "-T4" silently does nothing.
M(){ printf '%s\n' "$1" | socat -T 4 - unix-connect:/tmp/qmon.sock >/dev/null 2>&1; }
snap(){ M "screendump /tmp/s.ppm"; sleep 0.6; cp -f /tmp/s.ppm "snaps_$TAG/$1.ppm" 2>/dev/null; }
grab(){ M 'screendump "/tmp/cur.ppm"'; sleep 0.5; }

sleep 47                                   # boot + straight to main menu
M 'sendkey down'; sleep .6
M 'sendkey down'; sleep .6
M 'sendkey down'; sleep .6
M 'sendkey ret';  sleep 4                  # LOAD Game
M 'sendkey ret';  sleep 11                 # first save slot
# the load confirmation is click-to-dismiss; centre is forgiving
M 'mouse_move -3000 -3000'; sleep .4
M 'mouse_move 320 200';     sleep .4
M 'mouse_button 1'; sleep .3; M 'mouse_button 0'; sleep 2
snap 00_loaded

# addresses move every run - always re-locate
M 'pmemsave 0 0x100000 "/tmp/mem.bin"'; sleep 4
ADDR=$(python3 "$HERE/scan_stock.py" /tmp/mem.bin) || { echo "locate failed"; kill -9 $QPID; exit 1; }
echo "watching $ADDR"

M 'gdbserver'; sleep 2
WWATCH=$ADDR GDB_SECONDS=230 gdb -q -batch -x "$HERE/gdb_watch_write.py" >/tmp/gdb.out 2>&1 &

# SPACE only. ret/Escape/map clicks derail the game (see docs/DEAD-ENDS.md).
START=$(date +%s); n=0
while [ $(( $(date +%s) - START )) -lt 230 ]; do
  grep -q GDB-DONE /tmp/hits.log 2>/dev/null && break
  grab
  if [ "$(python3 "$HERE/detect_popup.py" /tmp/cur.ppm 2>/dev/null | cut -d' ' -f1)" = "POPUP" ]; then
    Y=$(python3 "$HERE/detect_popup.py" /tmp/cur.ppm 2>/dev/null | cut -d' ' -f2)
    M 'mouse_move -3000 -3000'; sleep .3; M "mouse_move 150 $Y"; sleep .3
    M 'mouse_button 1'; sleep .2; M 'mouse_button 0'; sleep .4
  else
    M 'sendkey spc'; sleep .5
  fi
  n=$((n+1))
  [ $((n % 8)) -eq 0 ] && snap "t_$n"
done

snap 99_final
M quit; sleep 1; pkill -9 -f qemu-system-i386 2>/dev/null
cp -f /tmp/hits.log "hits_$TAG.log" 2>/dev/null
for f in "snaps_$TAG"/*.ppm; do convert "$f" "${f%.ppm}.png" 2>/dev/null; done

echo "=== writes observed ==="
grep '^HIT' "hits_$TAG.log" 2>/dev/null | sed 's/ CODE=.*//' || echo "none"
