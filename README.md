# Colonization (1994) — binary fixes

Small, verified binary patches for **Sid Meier's Colonization**, MS-DOS
version 3.0 (`VICEROY.EXE`, 494,910 bytes, md5 `0f5d5b0063721fbc6aca314e5a43ddaf`).
Each one was found by runtime measurement, not by guessing.

| patch | offset | status | what it fixes |
|---|---|---|---|
| `traderoute-boycott` | `0x4121A` | **recommended** | trade routes silently refuse to deliver boycotted goods |
| `traderoute-topup` | `0x41384` | experimental | a later pick-up stop on a route loads nothing when every hold is in use, even part-full |
| `rng-idle-stir` | `0xC2FD` | experimental | the RNG is reset to the clock about 18 times a second, so battles close in time draw nearly the same number |

`--all` applies only **recommended** patches. You have to name an experimental
patch to apply it.

## Apply

```
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE --list
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE --status
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE --all
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE rng-idle-stir
python3 patch/apply_patch.py /path/to/COLONIZE/VICEROY.EXE --all --revert
```

No Python? `patch/Apply-Patch.ps1` does the same job with the same rules and
exit codes, on Windows PowerShell 5.1 or PowerShell 7+:

```powershell
.\patch\Apply-Patch.ps1 "D:\...\COLONIZE\VICEROY.EXE" -Status
.\patch\Apply-Patch.ps1 "D:\...\COLONIZE\VICEROY.EXE" -All
.\patch\Apply-Patch.ps1 "D:\...\COLONIZE\VICEROY.EXE" rng-idle-stir
```

Both patchers:

- check every byte at every patch site before writing, and write nothing if
  one site is wrong;
- copy the current file to `VICEROY.EXE.<first 8 of md5>.bak` before each
  change (the pristine file becomes `VICEROY.EXE.0f5d5b00.bak`). A backup is
  never overwritten, so every state you had is kept;
- write to a temporary file and rename it, so an interrupted run cannot leave
  a half-written EXE;
- refuse patch combinations that conflict, and never block `--revert`.

Exit codes: 0 ok · 1 file not found · 2 bad command line · 3 unexpected bytes
or size · 5 conflict · 6 invalid `patches.json`.

---

# Patch 1: trade-route boycott drop-off (`traderoute-boycott`)

## The bug

Trade routes automate cargo carriers between colonies. A delivery from one
colony to another is a domestic transfer, so it should have nothing to do with
European trade policy.

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

## Why that byte

The cargo drop-off is a loop over the carrier's cargo items:

```
i = 0
while i < cargo_count:
    good = unload_list_get(i)           ; lcall 1a1f:021c
    if skip_test(good) != 0:
        i++ ; continue                  ; 0x4121A: jne 0x411F6   <-- removed
    while find_hold(unit, good) >= 0:   ; lcall 181f:0c2c
        unload(unit, good, 0)           ; lcall 191f:0594
    i++
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

---

# Patch 2: battle randomness (`rng-idle-stir`) — experimental

The game's `rand()` is the standard Microsoft C generator and is fine. The
problem is the **idle loop**: while the game waits for input, it calls
`srand(tick)` about 18 times a second. That resets the whole RNG state to the
current tick count, so draws made close in time are close in value.

The patch changes 13 bytes in that idle wrapper so it **adds** the tick into
the state instead of resetting it. `srand()` itself is left byte-identical,
because the game uses it on purpose for content that must stay the same
(colony screen layout, which skill a village teaches).

Measured in QEMU on 2026-09-23 (same save and script for both builds, 40
samples each):

| | r1 (0 = no correlation) | chi² (pass < 14.07) | high state word = 0 |
|---|---|---|---|
| stock | +0.925 | 152.4 | 40 / 40 |
| patched | +0.060 | 4.8 | 0 / 40 |

**Why experimental:** the play checks are not done yet (colony layout stable
across visits, village teaching stable turn to turn, new worlds differ).
Full workings, including the MZ relocation trap this patch has to avoid:
[docs/RNG-ANALYSIS.md](docs/RNG-ANALYSIS.md).

---

# Patch 3: part-full holds on a route (`traderoute-topup`) — experimental

Not a boycott bug, though it looks like one. On a route with two pick-up stops,
the second stop loads nothing if the first stop put something in **every**
hold, even if a hold is only part full. Example: a caravel takes 124 sugar at
the first stop (100 + 24), then passes a colony with 100 sugar and takes none.

The colony load loop checks "holds in use == capacity" before it tries to load:

```
0x41384:  74 03   je 0x41389     ->   90 90   nop / nop
```

With the check removed, the load call fills up the part-full hold and stops
the loop by itself when nothing more fits. Europe stops use a different path
and are not changed.

Measured in QEMU on 2026-09-24 (6 runs, one-bit differential on the boycott,
plus controls): the boycott makes no difference; with the patch the second
stop fills 24 → 100; a ship full of another good loads nothing and the game
does not hang; a 24-turn run topped up in all 6 cycles. Details: [docs/ANALYSIS.md](docs/ANALYSIS.md#second-bug-a-later-pick-up-stop-is-skipped-traderoute-topup).

**Why experimental:** tested in QEMU only, on one sea route and one
wagon-train land route. A long session in a real game is not done yet.

| | MD5 |
|---|---|
| original + `traderoute-topup` only | `f5399c8b96e37bd5b3c778fbae781b25` |
| original + `traderoute-boycott` + `traderoute-topup` | `f827c0bdd89a27de811941315b027c14` |

---

## Repository contents

- `patch/` — `patches.json` (the patch list) and the two patchers.
- `tests/` — tests for both patchers (`python3 -m unittest discover -s tests`).
  Set `COL1_PRISTINE_EXE` to your own unmodified `VICEROY.EXE` to also run
  the real-binary checks (md5 of every patch, `srand()` untouched,
  relocation audit).
- `docs/ANALYSIS.md` — the two trade-route bugs: mechanism, offsets, runtime evidence.
- `docs/data/` — raw measurement logs.
- `docs/sessions/` — session logs.
- `docs/RNG-ANALYSIS.md` — the RNG defect, the patch, and the measurements.
- `docs/METHOD.md` — how to reproduce the investigation.
- `docs/DEAD-ENDS.md` — what looked right and wasn't. Read this before re-deriving it.
- `harness/` — headless QEMU + gdb rig for runtime RE of a DOS game:
  hardware watchpoints, RNG state sampling, scripted input.

## Legal

No game code is redistributed here. The patcher modifies a copy of
`VICEROY.EXE` that you already own. Colonization is © MicroProse / 2K.
Tooling and documentation in this repository are MIT licensed (see `LICENSE`).
