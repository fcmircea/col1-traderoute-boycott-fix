#!/usr/bin/env python3
"""
Print a trade-route carrier and three colonies' stock of one good from a QEMU
`pmemsave` RAM dump. Used for the traderoute-topup measurements.

The unit and colony tables are found by signature from the save file (units
2..9 and colony 0's name), so nothing is hardcoded. Run once with --init right
after loading the save; it writes loc.txt next to the dump.

    decode_route.py COLONY00.SAV mem.bin --init
    decode_route.py COLONY00.SAV mem.bin --unit 1 --colonies 8,19,4 --good 1

Output: unit x/y, orders, holds used, cargo nibbles, hold amounts, then each
colony's stock of the good. The unit table sits at DS:0x3144, so
DS base = unit table - 0x3144; the load weight table DS:0x84BC is printed for
the unit's nation.
"""
import argparse
import os
import re
import struct
import sys

ap = argparse.ArgumentParser()
ap.add_argument("save"); ap.add_argument("dump")
ap.add_argument("--init", action="store_true")
ap.add_argument("--unit", type=int, default=1)
ap.add_argument("--colonies", default="8,19,4")
ap.add_argument("--good", type=int, default=1, help="0=food 1=sugar ...")
a = ap.parse_args()

sav = open(a.save, "rb").read()
mem = open(a.dump, "rb").read()
nu, nc = struct.unpack_from("<HH", sav, 0x2C)
C = 0x186
U = C + nc * 0xCA
loc = os.path.join(os.path.dirname(a.dump) or ".", "loc.txt")

if a.init:
    blk = sav[U + 2 * 28:U + 10 * 28]
    units = [m.start() - 2 * 28 for m in re.finditer(re.escape(blk), mem)]
    name = sav[C + 2:C + 0x1A]
    cols = [m.start() - 2 for m in re.finditer(re.escape(name), mem)]
    print("unit table", [hex(x) for x in units], "colony table", [hex(x) for x in cols], file=sys.stderr)
    if not units or not cols:
        print("FAIL"); sys.exit(1)
    open(loc, "w").write("%d %d\n" % (units[0], cols[0]))

ub, cb = map(int, open(loc).read().split())
u = mem[ub + a.unit * 28:ub + (a.unit + 1) * 28]
ds = ub - 0x3144
nation = u[3] & 15
w = list(mem[ds + 0x84BC + nation * 16:ds + 0x84BC + nation * 16 + 16])
out = "u%d x=%d y=%d ord=%d holds=%d cargo=%s amt=%s |" % (
    a.unit, u[0], u[1], u[8], u[12], u[13:16].hex(), list(u[16:22]))
for c in map(int, a.colonies.split(",")):
    o = cb + c * 0xCA
    nm = mem[o + 2:o + 26].split(b"\0")[0].decode("latin1")
    out += " %s=%d" % (nm, struct.unpack_from("<H", mem, o + 0x9A + a.good * 2)[0])
print(out + " | w84BC=%s" % w)
