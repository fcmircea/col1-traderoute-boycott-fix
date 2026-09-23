# RNG analysis: `rng-idle-stir`

Status: **experimental**. The static checks and the emulator measurements below
were reproduced on 2026-09-23. The play checks are still open (see the end).

## The generator

`rand()` at file `0x103D4` is the stock Microsoft C LCG:

```
state = state * 214013 + 2531011        (32 bits)
return (state >> 16) & 0x7FFF
```

The state is two words: low at `DS:0x28EE`, high at `DS:0x28F0`.

`srand(seed)` at file `0x103C2` stores the seed in the low word and **sets the
high word to zero**:

```
103C2  55             push bp
103C3  8B EC          mov bp,sp
103C5  8B 46 06       mov ax,[bp+6]
103C8  A3 EE 28       mov [0x28EE],ax
103CB  C7 06 F0 28 00 00   mov word [0x28F0],0
103D1  5D             pop bp
103D2  CB             retf
```

Zeroing the high word is what makes `srand(X)` fully decide the numbers that
follow. Content that is meant to be the same every time (colony screen layout,
which skill a village teaches, start placement on predefined maps) calls
`srand(key)` and then draws. **So `srand()` must not change.**

## The defect

A small wrapper at file `0xC2F8` reads the BIOS tick counter and calls
`srand(tick & 0x7FFF)`. The game calls it from its idle/input-wait loop, about
18 times a second. While you look at the map, the RNG state is therefore just
"the current time in ticks", with the high word at zero.

Since the output is the high half of `state * 214013`, the next draw moves by
only `214013 / 65536 ≈ 3.27` per tick. Draws made close in time are close in
value. This is why fights at similar odds tend to go the same way in runs.

## The patch

```
0xC2F8:  9A 12 00 0C 0C   lcall <read tick>        ; unchanged (relocation 521 at 0xC2FB)
0xC2FD:  01 06 EE 28      add [0x28EE], ax         ; was: and ah,7F / push ax / lcall srand ...
0xC301:  EB 03            jmp 0xC306
0xC303:  90 00 00         ; never executed - relocation 523 is at 0xC304
0xC306:  CB               retf
0xC307:  90 90 90         ; padding up to the next routine at 0xC30A
```

The idle loop now **adds** the tick into the state instead of **resetting** the
state to it. `srand()` is not touched.

### The relocation trap

MZ relocation entry 523 points at file `0xC304`, the segment word of the
original `lcall srand`. The DOS loader adds the load segment to that word
when the program loads. Code placed there looks correct in the file but runs
as garbage in memory. The patch jumps over `0xC303`–`0xC305`.

To read the table: count at header `0x06`, table offset at `0x18`, header size
in paragraphs at `0x08`; each entry is `(offset, segment)` → file position
`header + segment*16 + offset`.

`tests/test_apply_patch.py` checks this. It lists every relocated word inside
every patch site and fails if the list is different from the known one, so a
new patch that touches a relocation cannot get in without the same check.

## Measurements (2026-09-23)

Setup: QEMU 9.2.2 built from source, FreeDOS 1.4 boot floppy with HIMEM +
CTMOUSE, game started with `VICEROY.EXE` directly, `COLONY00.SAV` loaded, no
input after loading. `harness/sample_rng_state.sh` read `DS:0x28EE` 40 times,
1.5 s apart, through the QEMU monitor. There were no breakpoints, so the
guest clock ran normally. Both builds used the same script and the same save.
DS was `0x20C4` in both runs.

`harness/rng_stats.py` computes what the next `rand()` would return from each
sampled state:

| build | n | r1 | chi² (7 df) | mean gap | range used | high word = 0 |
|---|---|---|---|---|---|---|
| stock (`0f5d5b00…`) | 40 | **+0.925** | **152.4** | 100 | 12% | 40 / 40 |
| rng-idle-stir (`9aae37e0…`) | 40 | +0.060 | 4.8 | 10620 | 91% | 0 / 40 |

- SE(r1) at n = 40 is about 0.158. Stock is about 6 SE away from zero, and patched is within 1 SE.
- The chi² critical value at 7 df, p = 0.05, is 14.07. Stock fails it by about 10×, and patched passes.
- Independent uniform draws would have a mean gap of about 10,923.
- Stock's next draws: 9443, 9541, 9642, 9740, 9841 … a steady climb of about 100 per sample.

Raw samples: [`docs/data/rng-2026-09-23/`](data/rng-2026-09-23/).

### Why not measure battles directly

With stock, consecutive draws differ by about 100 out of 32,768. Two fights at
similar odds usually get the same result. The sign of the bug is runs of the
same outcome, and telling that apart from normal luck needs about 30 fights.

A breakpoint on `rand()` does not work either. Each trap freezes guest time,
which stops the BIOS tick. That starves the stock build's only source of change
and makes the comparison unfair. Reading the state through the monitor
changes nothing in the guest.

## Dead end: patching `srand()` itself (`rng-reseed`)

An earlier attempt changed `srand()` to return before it zeroes the high word
(`0x103CB: C7 06 → 5D CB`). It is **not** in the manifest and cannot be
applied with the patchers.

It removes the reproducibility described above. The August 2026 play test
reported these results. They were **not re-checked** in the rebuild, because the
patch was dropped:

- villages re-roll which skill they teach, turn to turn. This breaks the
  "find the village that teaches X" mechanic;
- predefined-map starts always place you in the north;
- the colony screen re-rolls its decorative layout on every visit.

The 2004 CivFanatics fix (as described in the August notes; not re-checked)
returns one instruction earlier (`0x103C8: A3 EE → 5D CB`), which makes
`srand()` do nothing. That fits the report that it generates the same map every time.

## Still open (play checks)

The claim that seeded content is unchanged follows from `srand()` being
byte-identical. That is strong evidence, but it is not the same as having
played it. Before this patch becomes *recommended*, check in play:

1. The colony screen layout stays the same across visits.
2. A village teaches the same skill from turn to turn.
3. Two new worlds generated one after the other are different.
