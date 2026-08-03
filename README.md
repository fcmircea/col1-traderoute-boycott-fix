# Colonization (1994) — trade-route boycott drop-off fix

A two-byte fix for a 30-year-old bug in **Sid Meier's Colonization**, MS-DOS version 3.0.

## The bug

Trade routes automate cargo carriers between New World colonies. Europe is not a
valid trade-route stop, so a purely domestic transfer should have nothing to do
with European trade policy.

It does. Once a good is **boycotted** — after refusing the King's tax demand —
a trade route silently stops delivering that good. The carrier picks the cargo
up correctly, travels correctly, arrives at the destination colony, and then
fails to drop off. No message is shown. The carrier keeps shuttling the same
cargo forever.

Unloading by hand still works, which is the tell: MicroProse fixed the *manual*
`U`-key case in the v3.0 patch (README, fix #1: *"The 'U'nload key working
during a boycott"*) and missed the automated trade-route entry point. Same
defect class, different caller.

## The fix

One conditional jump, at file offset `0x4121A` in `VICEROY.EXE`:

```
0x4121A:  75 DA   jne 0x411F6     ->   90 90   nop / nop
```

Nothing else in the file changes.

| | MD5 |
|---|---|
| `VICEROY.EXE` original (v3.0, 494,910 bytes) | `0f5d5b0063721fbc6aca314e5a43ddaf` |
| `VICEROY.EXE` patched | `d60ddedbfa17f7058cdbe2bb3873b39e` |

Apply it with the included patcher, which verifies the checksum before touching
anything and writes a backup:

```
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE
```

## Why that byte

The cargo drop-off is a loop over the carrier's cargo items:

```
i = 0
while i < cargo_count:
    item = get_cargo(i)                 ; lcall 1a1f:021c
    if skip_test(item) != 0:
        i++ ; continue                  ; 0x4121A: jne 0x411F6   <-- removed
    unload(item, colony)                ; lcall 181f:0c2c
    ...
```

The boycott does not make the unload routine *refuse*. It makes this caller
**never call it at all**. That distinction is what took the longest to establish,
and it is why the obvious-looking patches elsewhere in the binary do not work
(see [docs/DEAD-ENDS.md](docs/DEAD-ENDS.md)).

NOPing the `jne` makes the loop stop skipping items, so the drop-off proceeds.

Full reasoning, offsets and the runtime evidence: [docs/ANALYSIS.md](docs/ANALYSIS.md).

## What has been verified

All in DOSBox-Daum, on the original install that first showed the bug:

- Drop-off works with the boycott in effect, over 50+ turns, on the save that
  first reproduced the failure.
- Selling a boycotted good in Europe is **still refused**.
- The **Custom House** still respects boycotts (Peter Stuyvesant's mechanic is
  intact — it is supposed to sell boycotted goods, and it still does).
- A **5-stop route carrying 7 cargo types** delivers correctly: each good is
  dropped at the stops configured to receive it, with no over-unloading
  elsewhere. This was the main regression risk and it did not materialise.

## Known limitation of this documentation

The skip predicate is not *positively identified*. The call at `191f:0cd8` is
reached through the overlay thunk tables, which have their own load bases;
resolving it statically from the resident base lands in string data. So this
repository documents *that* the patch removes a per-cargo skip and that the
resulting behaviour is correct under the testing above — not that the predicate
is provably and exclusively the boycott test.

In practice the 5-stop / 7-cargo result makes a broader predicate unlikely, but
if you can name that function precisely, please open an issue and it will be
corrected here.

## Repository contents

- `patch/` — checksum-verified patcher and the raw offset/bytes.
- `docs/ANALYSIS.md` — the bug mechanism, all confirmed offsets, runtime evidence.
- `docs/METHOD.md` — how to reproduce the investigation.
- `docs/DEAD-ENDS.md` — what looked right and wasn't. Read this before re-deriving it.
- `harness/` — headless QEMU + gdb rig for runtime RE of a DOS game, with
  hardware watchpoints and scripted save editing. Reusable for other Col1 bugs,
  and probably for other DOS-era titles.

## Legal

No game code is redistributed here. The patcher modifies a copy of
`VICEROY.EXE` that you already own. Colonization is © MicroProse / 2K.
Tooling and documentation in this repository are MIT licensed (see `LICENSE`).
