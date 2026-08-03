#!/bin/bash
# Build a FAT16 hard-disk image containing the game.
#
#   ./make_disk.sh /path/to/COLONIZE chd.img
#
# Use a real partitioned image, NOT qemu's vvfat: vvfat limits the root
# directory to 255 entries (COLONIZE has ~300) and the packaged QEMU 8.2.2
# aborts on guest writes through it.
set -eu
SRC=${1:?usage: make_disk.sh <COLONIZE dir> <out.img>}
OUT=${2:?usage: make_disk.sh <COLONIZE dir> <out.img>}

python3 -c "open('$OUT','wb').truncate(101808*512)"
printf 'label: dos\nstart=63, size=101745, type=06\n' | sfdisk "$OUT" >/dev/null
mkfs.vfat -F 16 -g 16/63 -h 63 --offset 63 "$OUT" >/dev/null
mcopy -i "$OUT"@@32256 -s "$SRC" ::/COLONIZE

# "no sound card" - otherwise the game hangs on a black screen
python3 -c "open('/tmp/_cfg','wb').write(b'\x00'*20)"
mcopy -i "$OUT"@@32256 -o /tmp/_cfg ::/COLONIZE/CONFIG.COL
rm -f /tmp/_cfg

echo "built $OUT"
mdir -i "$OUT"@@32256 ::/COLONIZE | tail -2
