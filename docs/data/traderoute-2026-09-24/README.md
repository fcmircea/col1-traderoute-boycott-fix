# Trade-route runs, 2026-09-24

Logs from `harness/run_probe.sh`. Save: turn 284, Spain, route "Santo Domingo
Ferry" (load sugar at Santo Domingo, load sugar at Veracruz, unload sugar at
Isabella), carrier = unit 1, a caravel with 2 holds.

Each line: step, seconds, unit 1 x/y (254 = inside a colony), orders,
holds used, cargo nibbles, hold amounts, sugar in the three colonies, and the
DS:0x84BC weight row for the unit's nation. The first line is the table search.

| file | EXE | save change |
|---|---|---|
| boy.txt | boycott patch | none (sugar boycotted) |
| nob.txt | boycott patch | sugar boycott bit off (file 0x2CF8: 0x73 -> 0x71) |
| C.txt | boycott patch | stop 1 loads nothing |
| D.txt | boycott patch | stop 1 loads cotton, Santo Domingo cotton = 40 |
| X.txt | boycott + topup | none |
| E.txt | boycott + topup | stop 1 loads horses (fills both holds) |
| XL.txt | boycott + topup | none, 1200 s |
| W0.txt | boycott patch | unit 1 made a wagon train; land route: load cotton at Isabella, load cotton at Veracruz; Isabella cotton 105, Veracruz cotton 60; unit +0x17 = 0x00 |
| W1.txt | boycott + topup | same save as W0 |

W0/W1 lines print cotton, not sugar (`DECODE_ARGS="--colonies 4,19 --good 3"`).

The save and the game files are not in this repository.
