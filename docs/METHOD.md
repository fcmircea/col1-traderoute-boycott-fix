# Reproducing the investigation

The whole rig runs headless in a Linux container. No Windows, no GUI, no
physical machine. The point is a **hardware watchpoint on a memory address in a
1994 DOS game**, driven entirely by scripts.

## Shape of the technique

1. Build a bootable FreeDOS disk and a FAT16 hard-disk image holding the game.
2. Boot it in QEMU with `-display none` and a Unix-socket monitor.
3. Drive the menus with `sendkey`, capture the screen with `screendump`.
4. Dump guest RAM with `pmemsave` and locate the structure of interest by
   signature — addresses move between runs, so always re-locate.
5. Attach gdb to QEMU's stub, set `rwatch` / `watch` on that address.
6. Drive the game until the watchpoint fires; log `CS:IP` plus registers.
7. Convert the runtime address to a file offset and disassemble.

The differential trick is what made it decisive: run the **same save twice**,
differing by a single bit, and compare which instructions touch the address. The
instruction present in one run and absent in the other is the mechanism.

## Environment

```
apt install qemu-system-x86 gdb socat imagemagick mtools fdisk dosfstools
pip install capstone
```

Then **build QEMU from source** — the packaged 8.2.2 has a `vvfat` abort that
kills long runs (see DEAD-ENDS.md):

```
git clone --depth 1 --branch v10.0.2 https://github.com/qemu/qemu qemu-src
cd qemu-src
./configure --target-list=i386-softmmu --disable-docs --disable-werror \
            --disable-gtk --disable-sdl --disable-opengl --disable-vnc \
            --disable-guest-agent --disable-user --disable-tools
ninja -C build qemu-system-i386
```

`libfdt-dev` is required. If subproject downloads fail, clone
`keycodemapdb`, `berkeley-softfloat-3` and `berkeley-testfloat-3` into
`subprojects/` manually and copy the matching `packagefiles/` overrides in.

## Boot floppy

FreeDOS 1.4 `KERNEL.SYS` plus two things the game will not run without:

- **`HIMEM.EXE`** with `DOS=HIGH,UMB`. Without it only ~509 KB is free and the
  game refuses to start, wanting 575,000 bytes. With it, ~620 KB.
- **`CTMOUSE.EXE`** (CuteMouse 2.1b4). Colonization requires an INT 33h driver;
  without one it hangs immediately after loading a save, spinning in a scan loop
  waiting for mouse data.

`FDCONFIG.SYS`:

```
DEVICE=\FREEDOS\BIN\HIMEM.EXE
DOS=HIGH,UMB
FILES=30
BUFFERS=10
LASTDRIVE=E
SHELL=\FREEDOS\BIN\COMMAND.COM \FREEDOS\BIN /E:512 /P=\FDAUTO.BAT
```

`FDAUTO.BAT` loads the mouse driver, then `C:` / `cd COLONIZE` / `VICEROY`.
If your floppy stops at the prompt instead, `harness/make_boot_floppy.sh` makes
a copy with those three lines added.

## Game disk

Two non-obvious requirements:

- **Zero `CONFIG.COL`** to 20 zero bytes. That means "no sound card". With the
  original sound configuration the game switches video mode and hangs on a black
  screen. Equivalent to choosing NO SOUND CARD in `INSTALL.EXE`.
- **Launch `VICEROY.EXE` directly**, not `OPENING.EXE`. `OPENING -g` plays the
  intro sequence; running the engine straight lands on the main menu in about 40
  seconds with no animation to skip.

Build the disk with `harness/make_disk.sh`.

## Driving the game

Automating a 1994 GUI is the fiddly part. What works:

- **`sendkey spc`** advances through units and ends turns cleanly. This is the
  only input needed for most work.
- Do **not** send `ret`, click on the map, or press Escape while automating.
  Enter and map clicks open colony views and rename dialogs; Escape quits to DOS.
- Some event popups are click-to-dismiss. Detect them from a screenshot before
  clicking rather than clicking blindly — `harness/detect_popup.py` does this by
  looking for the two green option rows.

Everything — boot, load, locate, attach, drive — must happen inside **one**
process lifetime; roughly four minutes end to end.

## Locating structures in RAM

Never hardcode an address. Dump and search by signature:

- A colony's commodity store is 16 little-endian words. Search for the exact
  stock vector read out of the save file; `harness/scan_stock.py` does this and
  returns the address of one good's word.
- The nation boycott bitmap is findable as the word preceded by `01 00`.

Loading a mouse driver shifts DOS memory, so addresses differ between an
otherwise identical run with and without `CTMOUSE`.

## Watchpoints

From the QEMU monitor, `gdbserver` (no arguments) starts the stub on the
already-running VM. Then:

```
gdb -q -batch -x harness/gdb_watch_write.py
```

with `set architecture i8086` and `target remote 127.0.0.1:1234`. Both `watch`
(write) and `rwatch` (read) work, backed by real x86 debug registers.

Two gotchas: gdb's `printf` cannot do 16-bit segment arithmetic
(`$cs*16+$eip` errors), so log raw registers and compute linear addresses
offline; and software breakpoints on overlay code are unreliable because the
overlay may be reloaded at a different address — prefer `hbreak` and watchpoints.

## Editing saves

`pavelbel/smcol_saves_utility` decodes and re-encodes the save format. The round
trip is faithful to within three cosmetic name bytes, which is good enough to
construct controlled experiments: flip exactly one boycott bit, or move a unit
onto a specific tile, and re-encode.

Call `encode_sav_file(json_path, settings)` directly to bypass the interactive
menu. Files must be named `COLONY0N.SAV`.

One finding worth keeping: a carrier **pre-placed** on the destination tile does
not unload. The drop-off is triggered by *arriving*, so experiments must let the
unit actually move onto the colony.
