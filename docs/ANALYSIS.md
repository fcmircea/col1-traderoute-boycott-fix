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

In the save file the word is at offset `+0x20` of the nation record. Nation
records are 316 bytes each and follow the unit table (units are 28 bytes each;
the unit and colony counts are the words at file `0x2C` and `0x2E`, and the
colony table starts at `0x186` with 202-byte records).

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

The caller is a loop over the stop's unload list, at file `0x411D8`–`0x41248`.
It is inside the route-stop function that starts at `0x41080`. That function's
argument `[bp+6]` is the **unit** index, not a colony: the code reads the unit
record at `DS:0x3144 + unit*0x1C` (for example the orders byte at `0x314C`,
where 2 = trade route). `[bp-0x18] == 999` means the stop is Europe.

```
0x411D8:  mov  word [bp-0x1E], 0        ; i = 0
0x411DD:  jmp  0x411F9
0x411F6:  inc  word [bp-0x1E]           ; i++
0x411F9:  mov  ax, [bp-0x42]            ; ax = cargo_count
0x411FC:  cmp  [bp-0x1E], ax
0x411FF:  jge  0x41248                  ; loop done
0x41201:  push [bp-0x1E]
0x41204:  lcall 1a1f:021c               ; good = unload_list_get(i)
0x4120C:  mov  [bp-0x20], ax
0x4120F:  push ax
0x41210:  lcall 191f:0cd8               ; test = skip_test(good)
0x41218:  or   ax, ax
0x4121A:  jne  0x411F6                  ; if (test) { i++; continue; }   <-- THE BUG
0x4121C:  push [bp-0x20]
0x4121F:  push [bp+6]
0x41222:  lcall 181f:0c2c               ; h = find_hold(unit, good)
0x4122D:  or   ax, ax
0x4122F:  jl   0x411F0                  ; no hold with this good -> next i
0x41231:  cmp  [bp-0x18], 999
0x41236:  jne  0x411E0                  ; colony: lcall 191f:0594 (unit, good, 0)
0x41240:  lcall 191f:0d02               ; Europe: (unit, good, 0)
```

The real unload is `191f:0594(unit, good, 0)`; its third argument is the
`flag = 0` seen in the handler's stack frame above. `find_hold` is called
again after each unload, so every hold holding that good is emptied.

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
| Route-stop function | `0x41080` | `[bp+6]` = unit index |
| Unload loop start | `0x411D8` | `i = 0` |
| `unload_list_get(i)` | `0x41204` | `lcall 1a1f:021c` |
| `skip_test(good)` | `0x41210` | `lcall 191f:0cd8` — not positively identified |
| `find_hold(unit, good)` | `0x41222` | `lcall 181f:0c2c`, < 0 = none |
| `unload(unit, good, 0)`, colony | `0x411E8` | `lcall 191f:0594` |
| Unload to Europe | `0x41240` | `lcall 191f:0d02` |
| Hold-count gate (second bug) | `0x41384` | `74 03` → `90 90`, see below |
| Colony load call | `0x41354` | `lcall 191f:07f8 (unit, good, 1, 0)` |
| Load weight table | `DS:0x84BC` | byte `[nation*16 + good]` |
| Unit table | `DS:0x3144` | 28 bytes per unit, holds used at `+0x0C` |
| Unload routine entry | `0x2A6A6` | `enter 0xe,0`, far, `retf` |
| **Deposit store** | `0x2A874` | `add [bx+si+0x9A], ax` |
| Unload sale/boycott gate | `0x2A781`, `0x2A786` | **do not patch** — this is the sell path |
| Fur production writer | overlay `IP=0x09A2` | colony output, not cargo |
| Load-time nation-record copy | `0x10374` | `rep movsw` |
| `SOMEBOYCOTT` message key string | `0x1E9C7` | |

## Second bug: a later pick-up stop is skipped (`traderoute-topup`)

This one is **not** caused by the boycott. It was first taken for a boycott
problem, so it is recorded here.

### Symptom

A 3-stop sea route: load sugar at Santo Domingo, load sugar at Veracruz,
unload sugar at Isabella. The caravel (2 holds) never takes sugar at Veracruz.
Santo Domingo gives it 124 sugar, stored as 100 + 24, so the caravel reaches
Veracruz with both holds in use and 76 free space in the second one.

### Mechanism

The colony load path starts at `0x41296`. Its loop test is at `0x41366`:

```
0x41366:  imul bx, [bp+6], 0x1C
0x4136A:  mov  al, [bx+0x3150]          ; holds used (unit +0x0C)
0x4136E:  mov  bl, [bx+0x3146]          ; unit type (unit +0x02)
          ...                           ; bx = type * 14
0x41380:  cmp  [bx+0x5237], al          ; capacity == holds used?
0x41384:  je   0x41389                  ; yes -> load nothing   <-- SECOND BUG
0x41386:  jmp  0x4129E                  ; loop body
```

The loop body builds a weight for each good in the stop's load list,
`byte DS:0x84BC[nation*16 + good] * colony.stock[good]`, sorts them
(`191f:0ed0`), stops if the best weight is 0, and calls
`191f:07f8(unit, good, 1, 0)`. It runs again only while `07f8` returns 0.

The capacity test counts holds **in use**, not free space. A ship with a
part-full hold in every slot is treated as full.

The Europe load path (`0x4124F`–`0x41294`) jumps straight to `0x41389` and
does not use this test.

### Measurements (QEMU, 2026-09-24)

Same save, patched EXE (`traderoute-boycott`), SPACE for 420 s (about 8
turns, 2 route cycles), RAM read every 6 steps with
`harness/run_probe.sh`. Raw logs: `docs/data/traderoute-2026-09-24/`.

| run | change | at Veracruz |
|---|---|---|
| boy | none, sugar boycotted (`0x5B73`) | holds 100 + 24; Veracruz sugar stays 100 |
| nob | sugar boycott bit off (`0x5B71`) | same as boy, same values in every sample |
| C | stop 1 loads nothing | arrives empty, loads 100 |
| D | stop 1 loads 40 cotton | loads 100 sugar into the free hold; next cycle 24 |
| X | + `0x41384` `74 03` → `90 90` | tops 24 up to 100 (Veracruz 100 → 24); next cycle 24 → 72 |
| E | X + stop 1 loads horses (both holds 100 horses) | loads nothing, no hang, 3 cycles |
| XL | as X, 1200 s (about 24 turns) | 6 cycles, tops up every time (24 → 72, 24 → 48), no hang |

The boycott has no effect: boy and nob match, and C and D (both with sugar
boycotted) load at Veracruz when a hold is free. The weight table row for
Spain was the same in boy and nob.

Runs X and E show that `07f8` fills up a part-full hold of the same good,
and returns non-zero when nothing more fits. So the loop ends by itself once
the gate is gone.

### The fix (experimental)

```
0x41384:  74 03   je 0x41389     ->   90 90   nop / nop
```

Not yet tested: wagon trains (same code, land routes) and a long play session
in a real game.

## Open question

`skip_test` (`191f:0cd8`) has not been positively identified. It is reached
through an overlay thunk table with its own load base, so resolving it from the
resident base lands in string data. Behaviourally the patch is correct under
testing — including a 5-stop route with 7 cargo types, which delivers each good
only to the stops configured for it — but naming that function precisely is
unfinished business. If you can, please open an issue.
