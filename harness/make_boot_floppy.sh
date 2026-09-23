#!/bin/bash
# Make a copy of a FreeDOS boot floppy that starts the game by itself.
#
#   make_boot_floppy.sh <in-floppy.img> <out-floppy.img>
#
# The input floppy must already boot to a prompt with HIMEM and CTMOUSE
# loaded (see docs/METHOD.md). This appends three lines to FDAUTO.BAT:
#   C:  /  CD \COLONIZE  /  VICEROY.EXE
# VICEROY.EXE is started directly, which skips the intro.
set -euo pipefail
IN=${1:?usage: make_boot_floppy.sh <in.img> <out.img>}
OUT=${2:?usage: make_boot_floppy.sh <in.img> <out.img>}
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

cp "$IN" "$OUT"
mtype -i "$OUT" ::/FDAUTO.BAT | tr -d '\r' > "$WORK/auto"
grep -qi 'VICEROY' "$WORK/auto" && { echo "already starts the game: $OUT"; exit 0; }
printf 'C:\nCD \\COLONIZE\nVICEROY.EXE\n' >> "$WORK/auto"
sed 's/$/\r/' "$WORK/auto" > "$WORK/auto.dos"
mcopy -o -i "$OUT" "$WORK/auto.dos" ::/FDAUTO.BAT
echo "built $OUT"
mtype -i "$OUT" ::/FDAUTO.BAT
