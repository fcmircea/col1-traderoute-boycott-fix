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

Read `../docs/METHOD.md` first, and `../docs/DEAD-ENDS.md` before debugging the
harness itself — several failure modes look like something other than what they
are.

You supply the boot floppy (FreeDOS 1.4 + `HIMEM.EXE` + `CTMOUSE.EXE`; layout in
`METHOD.md`) and your own copy of the game.
