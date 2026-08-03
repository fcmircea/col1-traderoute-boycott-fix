#!/usr/bin/env python3
"""
Colonization (1994) DOS v3.0 — trade-route boycott drop-off fix.

Patches a single conditional jump in VICEROY.EXE so that automated trade-route
carriers stop skipping boycotted goods when unloading at a New World colony.

    0x4121A:  75 DA  (jne 0x411F6)  ->  90 90  (nop / nop)

Verifies the file before writing and keeps a backup. No game code is
distributed with this script; it edits a copy you already own.

Usage:
    python3 apply_patch.py /path/to/COLONIZE/VICEROY.EXE
    python3 apply_patch.py /path/to/VICEROY.EXE --revert
    python3 apply_patch.py /path/to/VICEROY.EXE --check
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

OFFSET = 0x4121A
ORIGINAL_BYTES = bytes((0x75, 0xDA))   # jne short -0x26
PATCHED_BYTES = bytes((0x90, 0x90))    # nop ; nop

EXPECTED_SIZE = 494910
MD5_ORIGINAL = "0f5d5b0063721fbc6aca314e5a43ddaf"
MD5_PATCHED = "d60ddedbfa17f7058cdbe2bb3873b39e"


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def classify(data: bytes):
    """Return 'original', 'patched', or None."""
    digest = md5(data)
    if digest == MD5_ORIGINAL:
        return "original"
    if digest == MD5_PATCHED:
        return "patched"
    return None


def describe(path: Path, data: bytes) -> None:
    print(f"file    : {path}")
    print(f"size    : {len(data)} bytes (expected {EXPECTED_SIZE})")
    print(f"md5     : {md5(data)}")
    if len(data) > OFFSET + 1:
        print(f"@0x{OFFSET:X}: {data[OFFSET:OFFSET + 2].hex()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe", type=Path, help="path to VICEROY.EXE")
    ap.add_argument("--revert", action="store_true", help="undo the patch")
    ap.add_argument("--check", action="store_true", help="report status, change nothing")
    ap.add_argument("--force", action="store_true",
                    help="proceed even if the checksum is unrecognised "
                         "(still requires the exact expected bytes at the offset)")
    args = ap.parse_args()

    path: Path = args.exe
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1

    data = bytearray(path.read_bytes())
    state = classify(bytes(data))

    if args.check:
        describe(path, bytes(data))
        print(f"status  : {state or 'UNRECOGNISED'}")
        return 0

    want_from = PATCHED_BYTES if args.revert else ORIGINAL_BYTES
    want_to = ORIGINAL_BYTES if args.revert else PATCHED_BYTES
    target_state = "patched" if args.revert else "original"
    done_state = "original" if args.revert else "patched"

    if state == done_state:
        print(f"Nothing to do — this file is already {done_state}.")
        return 0

    if state != target_state and not args.force:
        print("error: unrecognised VICEROY.EXE.", file=sys.stderr)
        describe(path, bytes(data))
        print("\nThis patch targets the MS-DOS v3.0 release (7-Feb-95, 494,910 bytes).",
              file=sys.stderr)
        print("Re-run with --force if you are certain, or open an issue with the "
              "md5 above.", file=sys.stderr)
        return 2

    if len(data) < OFFSET + 2:
        print("error: file is too small to contain the patch site.", file=sys.stderr)
        return 2

    found = bytes(data[OFFSET:OFFSET + 2])
    if found != want_from:
        print(f"error: expected {want_from.hex()} at 0x{OFFSET:X}, found {found.hex()}.",
              file=sys.stderr)
        print("Refusing to write. The file is not what this patch expects.", file=sys.stderr)
        return 2

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"backup  : {backup}")
    else:
        print(f"backup  : {backup} (already exists, left alone)")

    data[OFFSET:OFFSET + 2] = want_to
    path.write_bytes(bytes(data))

    print(f"patched : 0x{OFFSET:X}  {found.hex()} -> {want_to.hex()}")
    print(f"md5     : {md5(bytes(data))}")
    verb = "reverted" if args.revert else "applied"
    print(f"\nDone — {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
