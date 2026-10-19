# Combat: how a battle is decided

Target: `VICEROY.EXE`, Sid Meier's Colonization, MS-DOS version 3.0
(MD5 `0f5d5b0063721fbc6aca314e5a43ddaf`). All offsets are file offsets in
that EXE. Found 2026-10-19 by static reading, then checked in QEMU.

## The battle routine

The routine is the far function at file `0x5CA7E`, in overlay 16 (file base
`0x5AF70`, offset `0x1B0E`), reached through the thunk `181F:1A14`.

| argument | meaning |
|---|---|
| `[bp+6]` | attacking unit |
| `[bp+8]`, `[bp+0Ah]` | target x, y |
| `[bp+0Ch]` | show the messages and the animation |
| `[bp+0Eh]` | real fight; when 0 the routine only returns the odds `A*8/(D+1)` (`0x5D032`), which the computer players use to judge an attack |

## Strengths

- **A**, the attack strength, is kept in `[bp-90h]`. The base comes from
  `0x7C2A` (`181F:09C8`): the unit type's attack value × 8, plus 50 % for a
  veteran soldier or dragoon, minus 2 for damaged artillery. The routine
  then multiplies by (`DS:8D04h` + 4) / 4, then by 3/2 (the attack bonus),
  and adds (4 − `DS:53A6h`) when the attacker is a human player. `53A6h` is
  probably the difficulty level (not proven). Partial moves (the "HALF"
  prompt) and some artillery and terrain cases also change it; those were
  not traced in detail.
- **D**, the defence strength, is kept in `[bp-A6h]`; it comes from `0x7D3E`
  (`181F:09DC`).

Unit types are a table at `DS:5230h`, 14 bytes each: `+4` moves × 3,
`+5` defence, `+6` attack, `+7` cargo holds, `+9` cost, `+0Bh` guns,
`+0Ch` hull. Ship types are `0Dh`–`12h`.

## The draw

```
0x5D17D:  mov  ax, [bp-0A6h]        ; D
0x5D181:  add  ax, [bp-90h]         ; + A
0x5D185:  push ax
0x5D186:  push 1
0x5D188:  lcall 181F:04D4           ; random(1, A+D)
0x5D190:  mov  [bp-0D0h], ax
0x5D194:  cmp  ax, [bp-90h]
0x5D198:  jg   0x5D1A0              ; r > A: the attacker loses
0x5D19A:  mov  ax, 1                ; r <= A: the attacker wins
```

`random(lo, hi)` is file `0xC322`: `lo + (rand() * (hi - lo + 1) >> 15)`,
with `rand()` the Microsoft C generator at `0x103D4`. So the attacker wins
with probability **A / (A + D)**.

One special case follows (`0x5D1A6`, static reading only): a native brave
attacking a human player's artillery always loses.

This is the draw that `rng-idle-stir` is about: when the RNG state was reset
to the clock, battles fought close in time drew nearly the same `r`
(`docs/RNG-ANALYSIS.md`).

## What follows

- The loser is handled by `0x5BE30` (a whole stack) or `0x5B2C2` (one
  unit). `0x5B2C2` holds the messages LOOTCAPTURE, WAGONCAPTURE,
  COLONISTCAPTURE, DEMOTE, ARTILLERY, CARGOCAPTURE, SHIPDAMAGE and SHIPSUNK.
- A beaten ship is damaged rather than sunk when
  `random(1, winner.guns + loser.hull) <= loser.hull` (`0x5B849`). Some
  other conditions force a sinking; not fully traced.
- A naval defender may evade (EVASIVE) when its attack is lower than the
  attacker's: `random(1, fA + fD) <= fD` (`0x5D376`–`0x5D477`). The main draw
  has already been made by then.
- The winner may be promoted (`0x5C69C`; CONTINENTAL, VETERAN, VALOR), with
  chance `random(1, A + D ± difficulty) <= opponent strength`. With George
  Washington (father 11) there is no draw.

`0x5C69C` is called from inside the battle routine (`0x5D716` attacker wins,
`0x5D7C8` defender wins) through an overlay-local stub
(`0x5E71E: EA D4 06 1F 1A`, a jump to `1A1F:06D4` = thunk `181F:26D4`). A
search for the usual `9A … 1F 18` call bytes therefore finds no caller.

## The CHEAT menu, for setting up battles

The menu loader tests `DS:5383h` bit `20h` (`0x72A8B`) and hides menu 6
(CHEAT, `@CUP` in `MENU.TXT`) when it is clear. Two ways to set it:

- On the map, press Alt+W, Alt+I, Alt+N (key handler `0x23F2F`–`0x23FE2`;
  the toggle is `xor [5383h], 20h` at `0x23F9A`).
- In a save, set byte `0x13` bit `20h` (the save header from `0x12` holds
  `DS:5382h` onward).

CHEAT > Create Unit then places a unit at the cursor, so a battle can be set
up on demand.

## Proof

QEMU, TCG, 2026-10-19:

- With `EB FE` at `0x5D188` the game hung at `912A:2218`
  (`0x2218` = `0x5D188` − `0x5AF70`) when a created soldier attacked a Tupi
  brave. On the stack: A = 26, D = 4, the call arguments (1, 30). The RNG
  state predicted r = 4, so a win. With the bytes restored, the Combat
  Analysis box showed +26 / +30 / +4, and the brave's unit record was
  cleared afterwards.
- A save with byte `0x13` changed from `C6h` to `E6h` loads with CHEAT in the
  menu bar, without any keys.
