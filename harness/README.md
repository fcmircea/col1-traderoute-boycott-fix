# Headless DOS reverse-engineering harness

Runs Colonization under QEMU with no display, drives it by script, and puts
**hardware watchpoints** on game state via QEMU's gdb stub. Built to find the
trade-route boycott bug; nothing here is specific to that bug beyond the search
signature in `scan_stock.py`.

| file | what it does |
|---|---|
| `make_disk.sh` | builds a FAT16 disk image from a `COLONIZE` folder, zeroing `CONFIG.COL` |
| `run_watch.sh` | one-shot boot → load → locate → attach → drive; everything in one process |
| `scan_stock.py` | finds a colony's commodity-store word in a RAM dump by signature |
| `gdb_watch_write.py` | gdb script: write-watchpoint, logs `CS:IP`, registers, stack, code bytes |
| `gdb_watch_read.py` | same, read-watchpoint — use it to prove a routine is *never entered* |
| `detect_popup.py` | detects the click-to-dismiss colony-arrival popup from a screenshot |
| `run_probe.sh` | boot → load → SPACE through turns, decoding a trade-route carrier from RAM every 6 steps (no gdb) |
| `decode_route.py` | finds the unit and colony tables in a RAM dump by signature; prints a carrier's holds and colony stock |

Read `../docs/METHOD.md` first, and `../docs/DEAD-ENDS.md` before debugging the
harness itself — several failure modes look like something other than what they
are.

You supply the boot floppy (FreeDOS 1.4 + `HIMEM.EXE` + `CTMOUSE.EXE`; layout in
`METHOD.md`) and your own copy of the game.

## RNG tooling

| file | what it does |
|---|---|
| `make_boot_floppy.sh` | copies a boot floppy and makes it start `VICEROY.EXE` by itself |
| `sample_rng_state.sh` | samples the LCG state through the QEMU monitor at **full speed** |
| `rng_stats.py` | turns samples into next-draw statistics (r1, chi², gap, range) |

```
make_disk.sh      COLONIZE/ disk.img
make_boot_floppy.sh colboot.img boot.img
QEMU=/path/to/qemu-system-i386 sample_rng_state.sh disk.img boot.img run.tsv
rng_stats.py run.tsv
```

Sample, do not trap. A breakpoint on anything in the idle loop fires about
1,000 times a second, and QEMU freezes guest time on every trap. The tick
counter stops, the game stops advancing, and every sample looks the same. Reading
memory through the monitor changes nothing in the guest.
