#!/usr/bin/env python3
"""
Locate a colony's commodity-store word in a QEMU `pmemsave` RAM dump.

A colony's store is 16 little-endian words, in this order:
    food sugar tobacco cotton furs lumber ore silver
    horses rum cigars cloth coats trade_goods tools muskets

Read the vector for the colony you care about out of the decoded save file,
pass it here, and this prints the linear address of one good's word - ready to
hand to gdb as a watchpoint target.

Addresses move between runs (DOS memory layout, resident drivers), so re-run
this every time rather than hardcoding the result.

    scan_stock.py mem.bin
    scan_stock.py mem.bin --stock 60,0,0,24,31,11,38,0,101,0,0,46,0,0,36,0 --good furs
"""
import argparse
import re
import sys

GOODS = ["food", "sugar", "tobacco", "cotton", "furs", "lumber", "ore", "silver",
         "horses", "rum", "cigars", "cloth", "coats", "trade_goods", "tools", "muskets"]

# Fort Orange in the reference reproduction save.
DEFAULT_STOCK = [60, 0, 0, 24, 31, 11, 38, 0, 101, 0, 0, 46, 0, 0, 36, 0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--stock", help="16 comma-separated commodity amounts")
    ap.add_argument("--good", default="furs", choices=GOODS)
    args = ap.parse_args()

    stock = ([int(x) for x in args.stock.split(",")] if args.stock else DEFAULT_STOCK)
    if len(stock) != 16:
        print(f"error: need 16 values, got {len(stock)}", file=sys.stderr)
        return 2

    mem = open(args.dump, "rb").read()
    needle = b"".join(v.to_bytes(2, "little") for v in stock)
    hits = [m.start() for m in re.finditer(re.escape(needle), mem)]

    if not hits:
        # Fall back to a distinctive interior run, in case production ticked
        # a value between dumping and searching.
        sub = b"".join(v.to_bytes(2, "little") for v in stock[3:7])
        hits = [m.start() - 6 for m in re.finditer(re.escape(sub), mem)]
        print("warning: exact match failed, used partial signature", file=sys.stderr)

    print(f"candidates={[hex(h) for h in hits]}", file=sys.stderr)
    if not hits:
        print("FAIL")
        return 1
    if len(hits) > 1:
        print(f"warning: {len(hits)} matches, using the first", file=sys.stderr)

    print(hex(hits[0] + GOODS.index(args.good) * 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
