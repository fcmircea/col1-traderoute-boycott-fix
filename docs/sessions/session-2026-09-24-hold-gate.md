# Session 2026-09-24: 3-stop route skips the 2nd pick-up

## Question
Route "Santo Domingo Ferry": load sugar at Santo Domingo, load sugar at
Veracruz, unload sugar at Isabella. The caravel never takes sugar at Veracruz.
Is it the boycott, or the hold-count check at file 0x41380?

## Answer
Not the boycott. The hold-count check at 0x41380/0x41384 causes it: when
every hold is in use, even part-full, the colony load loop loads nothing.
New experimental patch `traderoute-topup` (0x41384 `74 03` -> `90 90`).

## Setup
- Cloud container. QEMU 9.2.2 built from the GitHub source
  (download.qemu.org is blocked here).
- Boot floppy colboot_2.img and COLONIZE.zip supplied by Florin.
- EXE: pristine 0f5d5b00 + traderoute-boycott = d60ddedb.
  With traderoute-topup as well: f827c0bd.
- Save COLONY00.SAV, md5 7db77d60, 32533 bytes (turn 284). Not in git.
- `harness/run_probe.sh` + `harness/decode_route.py`.

## Runs
See docs/ANALYSIS.md "Second bug" and docs/data/traderoute-2026-09-24/.
- boy / nob (one boycott bit apart): identical; Veracruz never loaded.
- C (stop 1 loads nothing), D (stop 1 loads 40 cotton): Veracruz loads sugar
  into a free hold, with sugar boycotted.
- X (topup patch): Veracruz fills the 24 hold to 100.
- E (topup, both holds full of horses): loads nothing, no hang.
- XL (topup, 1200 s, about 24 turns): 6 cycles, topped up every time, no hang.

## Other findings
- The route-stop function (0x41080) takes the unit index in [bp+6], not a
  colony. Unit table at DS:0x3144, 28 bytes per unit.
- 181f:0c2c is find_hold(unit, good); the real unload is 191f:0594 (colony)
  or 191f:0d02 (Europe, [bp-0x18] == 999).
- Europe load path 0x4124F-0x41294 skips the hold-count check.
- DS:0x84BC weight table changes a little over time (rum, coats, muskets
  moved by 1 during run X), so it looks like price data, not fixed rules.
  It is the same with and without the boycott.
- Boycott word: nation record +0x20 in the save.

## Changes (branch traderoute-topup)
- patch/patches.json: new experimental `traderoute-topup`.
- tests: live-install md5 test now names its two patches; new md5 test for
  boycott + topup. 38 tests pass with COL1_PRISTINE_EXE (pwsh tests skipped:
  no pwsh here).
- docs/ANALYSIS.md: unit-not-colony fix, unload loop names, offsets table,
  boycott word offset, "Second bug" section.
- README.md: patch 3 section, corrected pseudocode, removed the claim that
  Europe is not a route stop (the code has a Europe path).
- harness: run_probe.sh, decode_route.py.

## Not done
- Wagon-train route test; long session in a real game (DOSBox).
- skip_test (191f:0cd8) still not named.
- Live EXE not touched.

## Follow-up 2026-09-25: wagon train
- Save: unit 1 made a wagon train (type 12), route 0 made a land route:
  Isabella load cotton -> Veracruz load cotton. Isabella cotton 105,
  Veracruz cotton 60, Spain's unit counts adjusted. Built with
  pavelbel/smcol_saves_utility, then checked byte by byte.
- First two tries sent the wagon to New Amsterdam: unit +0x17 = 0x20 means
  route 0, stop 2, and the new route has only 2 stops. Set to 0x00.
- W0 (boycott patch): Veracruz keeps 60 on every visit (about 12 trips).
- W1 (+ topup): 5 -> 65 on the first visit, Veracruz 0; no hang.
- Left to do before "recommended": a long session in a real game (DOSBox).
