# Root-cause analysis

Target: `VICEROY.EXE`, Sid Meier's Colonization, MS-DOS version 3.0
(7-Feb-95, 494,910 bytes, MD5 `0f5d5b0063721fbc6aca314e5a43ddaf`).

## Binary shape

16-bit real-mode MZ executable built with Microsoft C, no DOS extender. The file
is roughly a 132 KB resident load module followed by ~362 KB of demand-loaded
**overlays**. 2,260 relocations. Entry `110d:071d`.

Overlay code is reached through thunk tables via far calls of the form
`lcall 181f:xxxx`, `lcall 191f:xxxx`, `lcall 1a1f:xxxx`. This matters: overlay
segments load at bases that differ from the resident base, so a far address seen
at runtime cannot be converted to a file offset with a single global delta.

Useful constant: the **resident** module loads such that

```
file_offset = (segment * 16 + offset) - 0x32A0
```

That relation was calibrated by matching a runtime memory window back to the
file. It holds for resident code only.

## The bug

Boycott state is a 16-bit bitmap, one bit per good, stored per nation. Furs are
bit 4. In the reproduction save the Dutch player is `nation[3]` and the bitmap
reads `0x187F` (furs boycotted); the control reads `0x186F`.

A wagon train on a trade route from New Amsterdam to Fort Orange loads 100 furs,
travels, arrives — and never deposits. Fort Orange's fur stock does not change.

## Where the goods are actually deposited

The colony commodity store is a 16-word array `[food, sugar, tobacco, cotton,
furs, lumber, ore, silver, horses, rum, cigars, cloth, coats, trade_goods,
tools, muskets]` at offset `0x9A` inside the colony record.

The cargo unload routine begins at file `0x2A6A6` (`enter 0xe,0`) and its
deposit instruction is:

```
0x2A874:  01 80 9A 00     add word ptr [bx+si+0x9A], ax
```

with `bx` = colony pointer (loaded from near data `[0x8542]`), `si` = good index
× 2, and `ax` = the amount being unloaded.

That single instruction is the ground truth for "cargo was delivered", and
watching it is what settled the diagnosis.

## The decisive experiment

Two saves identical except for one bit — the furs boycott flag — were run under
QEMU with a **hardware write-watchpoint** on Fort Orange's fur word.

**Boycott lifted (control).** The watchpoint fires with `AX = 0x64` (100), fur
stock 31 → 147 → 181. The cargo is deposited. Reading the handler's stack frame
at that moment shows it was entered with `good = 4` (furs) and its third
parameter `flag = 0`.

**Boycott set (repro).** The watchpoint fires only with `AX = 8` and `AX = 10`,
once per turn — that is fur *production* from the colony's trappers, a different
instruction entirely. The deposit store never executes, even though the
on-screen banner confirms "Wagon Train arrives in Fort Orange".

A **read**-watchpoint on the same word in the broken run then showed the decisive
fact: none of the unload routine's own read instructions ever execute. The
handler is **never entered** for the boycotted good.

That rules out the intuitive explanation. The unload routine does not inspect
the boycott flag and refuse. Something upstream declines to call it.

## The caller

The caller is a loop over the carrier's cargo items, at file `0x411D8`–`0x41248`:

```
0x411D8:  mov  word [bp-0x1E], 0        ; i = 0
0x411DD:  jmp  0x411F9
0x411F6:  inc  word [bp-0x1E]           ; i++
0x411F9:  mov  ax, [bp-0x42]            ; ax = cargo_count
0x411FC:  cmp  [bp-0x1E], ax
0x411FF:  jge  0x41248                  ; loop done
0x41201:  push [bp-0x1E]
0x41204:  lcall 1a1f:021c               ; item = get_cargo(i)
0x4120C:  mov  [bp-0x20], ax
0x4120F:  push ax
0x41210:  lcall 191f:0cd8               ; test = skip_test(item)
0x41218:  or   ax, ax
0x4121A:  jne  0x411F6                  ; if (test) { i++; continue; }   <-- THE BUG
0x4121C:  push [bp-0x20]
0x4121F:  push [bp+6]
0x41222:  lcall 181f:0c2c               ; unload(item, colony)
```

When the good is boycotted, `skip_test` returns non-zero and the `jne` at
`0x4121A` jumps past the unload call. The cargo is silently left on board, which
is exactly the observed symptom: pickup fine, travel fine, drop-off nothing, no
message.

## The fix

```
0x4121A:  75 DA   jne 0x411F6   ->   90 90   nop / nop
```

The loop stops skipping items and the unload proceeds.

This is caller-side, which is what makes it safe. The European sale path and the
Custom House reach the unload machinery through *different* callers and are not
touched. That was confirmed in play: selling a boycotted good in Europe is still
refused, and the Custom House still behaves as designed.

## Corroboration

The v3.0 README lists, among its fixes, *"The 'U'nload key working during a
boycott."* MicroProse hit this same defect class from the manual-unload entry
point and fixed that one caller. The automated trade-route caller at `0x411D8`
was missed. `GAME.TXT` still carries the matching message key `@SOMEBOYCOTT`
("Some of the cargo could not be unloaded because of a parliamentary boycott"),
which is never raised on the automated path — hence the silence.

## Confirmed offsets

| What | File offset | Bytes / note |
|---|---|---|
| **Patch site** (per-cargo skip branch) | `0x4121A` | `75 DA` → `90 90` |
| Cargo loop start | `0x411D8` | `i = 0` |
| `get_cargo(i)` | `0x41204` | `lcall 1a1f:021c` |
| `skip_test(item)` | `0x41210` | `lcall 191f:0cd8` — not positively identified |
| `unload(item, colony)` | `0x41222` | `lcall 181f:0c2c` |
| Unload routine entry | `0x2A6A6` | `enter 0xe,0`, far, `retf` |
| **Deposit store** | `0x2A874` | `add [bx+si+0x9A], ax` |
| Unload sale/boycott gate | `0x2A781`, `0x2A786` | **do not patch** — this is the sell path |
| Fur production writer | overlay `IP=0x09A2` | colony output, not cargo |
| Load-time nation-record copy | `0x10374` | `rep movsw` |
| `SOMEBOYCOTT` message key string | `0x1E9C7` | |

## Open question

`skip_test` (`191f:0cd8`) has not been positively identified. It is reached
through an overlay thunk table with its own load base, so resolving it from the
resident base lands in string data. Behaviourally the patch is correct under
testing — including a 5-stop route with 7 cargo types, which delivers each good
only to the stops configured for it — but naming that function precisely is
unfinished business. If you can, please open an issue.
