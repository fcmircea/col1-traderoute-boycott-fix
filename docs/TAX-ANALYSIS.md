# Tax raise, Tea Party and boycott

Target: `VICEROY.EXE`, Sid Meier's Colonization, MS-DOS version 3.0
(MD5 `0f5d5b0063721fbc6aca314e5a43ddaf`). All offsets are file offsets in
that EXE. `DS:` addresses are in the game's data segment. Most of this code
is in overlay 4 (file base `0x30550`). Static reading was checked in QEMU on
a test-only build (see "Proof").

No published reverse engineering of these rules was found (web search,
2026-10-08). FreeCol uses its own rules. The numbers here come from the code.

## Names used

| name | where | what it holds |
|---|---|---|
| tax | nation record `+01h` (byte) | the tax rate in % |
| boycott mask | nation record `+20h` (word) | one bit per goods; bit set = boycotted |
| gold | nation record `+2Ah` (long) | the treasury |
| trade volume | nation record `+0BCh + 4*g` (long) | per goods; weights the Tea Party goods |
| last change | nation record `+10h` (word) | the last tax change |
| rebel % | `DS:53D0h` (save `0x60`) | the human player's rebel %; same as nation `+19h` |
| colony count | `DS:9298h + player` (byte) | colonies the player owns |
| colonists | `DS:9410h + player` (byte) | colony population + colonist units, max 255 |
| port flag | colony record `+1Ch` bit `40h` | the colony touches the open ocean |
| colony bells | colony record `+0C2h` (long) | liberty bells; SoL % = 100 * this / `+0C6h` |

Nation records: 316 bytes at `DS:8808h`. Colony records: 202 bytes at
`DS:5D46h` (save `0x186`); x and y first, the name at `+2`, the nation at
`+1Ah`, stock at `+9Ah + 2*g`. Goods order: food, sugar, tobacco, cotton,
furs, lumber, ore, silver, horses, rum, cigars, cloth, coats, trade goods,
tools, muskets.

## When the King changes the tax

Routine `0x36138` runs once per player turn. It acts only if all of these hold:

1. The player owns at least one colony: `DS:9298h + player` is not 0
   (`0x36146`). The colony founder adds 1 (`0x2EBB3`), the colony remover
   takes 1 (`0x2EE47`), and the turn recount sets it again (`0x42638`).
2. The turn number is 30 or more (`0x36150`).
3. The turn number is a multiple of the period (`0x361B6`).
4. The tax is 85 % or less (`0x361C3`).

The period depends on the year (`0x3615A`-`0x36180`):

| year | period |
|---|---|
| up to 1600 | 18 turns |
| 1601-1700 | 15 |
| 1701-1750 | 12 |
| after 1750 | 9 |

For the human player the period also changes with difficulty `d`
(`DS:53A6h`, 0 = Discoverer ... 4 = Viceroy): period minus `2*(d-2)`. So
Discoverer adds 4 turns, Viceroy takes away 4. Computer players use the
plain period (`0x36184`-`0x361A0`).

## How the amount is chosen

The game makes a score (`0x361CC`-`0x36221`):

```
score = random(1..1000)
      + gold / 100
      + 10 * rebel%
      - 5 * tax
      + colonists
      + turn / 30
```

`rebel%` is the human player's rebel percentage (`DS:53D0h`). It is the
same number that shows the REBELUP / REBELDOWN messages (`0x3E8BA`,
section names at `0x3E91C` ff.). `colonists` is the per-player count at
`DS:9410h` (`0x3620E`). It counts people in colonies plus colonist units
outside them (`0x422B5`, `0x4264D`), up to 255.

So the King raises more often when you are rich, rebellious and big, and
less often when the tax is already high.

The score picks the message and the change (`0x3624E`-`0x36371`):

| score | message | change |
|---|---|---|
| below 100 | KINGVICTORY | lower by random(2..5), never below 0 |
| 100-649 | KINGWIFE | +1 (only while the King has had fewer than 30 wives, `DS:53A7h`) |
| 650-949 (or 100-649 after 30 wives) | KINGWAR | +2; the enemy is a random other country |
| 950-1099 | KINGNAVACT | +3 or +4 |
| 1100 and more | KINGSTAMPACT | +5 to +8 |

`random(a..b)` includes both ends (`0xC322`). The change is stored at
nation `+10h` (`0x36387`) and passed to the tax routine `0x34318`
(through the near stub `0x3681D`).

## The tax routine

Routine `0x34318` gets the message name and the change.

1. A cut never takes the tax below 0 (`0x3431E`-`0x34342`).
2. It adds the change. A raise never takes the tax above 75 %; the rest is
   dropped (`0x3434C`-`0x3436B`). If nothing is left, it stops.
3. For a computer player it stops here: the tax changes, with no message
   (`0x34377`-`0x3438D`). Only the human player sees the dialog and can
   hold a Tea Party.

## When a Tea Party is offered

On a raise, the game looks for a goods to offer (`0x34390`-`0x34510`):

1. For each goods that is not boycotted, it finds the human player's
   **port colony** with the largest stock of it (strictly more than 0).
   A port colony has bit `40h` in its flag byte (`0x3446D`).
2. Each goods gets a weight from the nation's trade volume:
   `abs(volume) / 100` (`0x343AE`-`0x343D4`). Food and tools count half,
   horses and muskets a quarter (`0x343E2`-`0x343ED`).
3. It draws one goods at random, in proportion to the weights, among the
   goods that have a colony (`0x344B3`-`0x34510`). A goods with weight 0
   (never traded in Europe) is never drawn.

If no goods is found, or the change is a cut, the King's message comes
without a choice (`0x34546`-`0x34583`). Otherwise the dialog adds two
lines (TAXOPTIONS): "Kiss pinky ring" and "Hold '<goods> Party'" for the
chosen colony and goods.

SPACE or Enter on the dialog picks the first line (accept the tax).

### The port flag

The flag is set only when a colony is founded (`0x2EDE6`). The founder
first clears the whole flag byte (`0x2EBFA`). Then it looks at the eight
tiles around the colony (`0x8352`): among the water tiles it takes the
lowest ocean region number. If that region is 1 (the open sea), the colony
gets bit `40h`. No code clears the bit later (search of all `and` forms
on the flag byte; the other bits 01h-20h and 80h have their own writers).

Check in the saves: in COLONY08 all 20 colonies, and in COLONY00 all 16,
have bit `40h` exactly when a neighbour tile is water of region 1. Plymouth
and Barbados have no water next to them; Boston touches region 5 (a lake);
these three lack the bit.

The same flag is used to find the nearest port for ships (`0x846D`).

Bit `40h` is not "Sons of Liberty 50 %". That is bit `04h` (set at 50 %,
`0x2DB67`; cleared below 50 %, `0x2DC38`). Bit `02h` is 100 % (set at 100,
cleared below 95, `0x2DBAC` / `0x2DBF2`). Bit `08h` is the Tory penalty
(`0x2DD2E` / `0x2DD67`).

## What the Tea Party does

If the player picks the second line (`0x3466F`), the game:

1. **Cancels the raise**: the tax goes back to its old value (`0x3467F`).
   The tax panel at the right still shows the raised rate until it is
   redrawn later in the turn.
2. **Dumps the goods**: `min(stock, 100)` of the goods leave the colony's
   stock (`0x3468C`-`0x3469B`). A stock of 100 or less is emptied.
3. **Adds liberty bells**: the same amount goes to the colony's bells
   (`0x346A9`). This raises the colony's Sons of Liberty share. It can pass
   50 % at once and bring the "Sons of Liberty" message in the same turn.
4. Shows TEAPARTY with that amount (`0x346B7`).
5. **Sets the boycott** for that goods: bit `g` in the boycott mask
   (`0x34717`), after the message closes.

Other colonies and the gold are not touched.

## Boycott: what it blocks and how it ends

A boycotted goods cannot be bought or sold in Europe (TEAPARTY text). On a
trade route, the Europe stop leaves it on board: the unload loop asks
`skip_test` (file `0x30B38`), which reads this mask (`docs/ANALYSIS.md`).

Lifting it, routine `0x3334E` (goods `g`):

- For a computer player it clears the whole mask at once (`0x3336E`).
  Computer players never keep a boycott.
- For the human player it shows KISSUP with the back taxes:
  `500 * price(g)` (`0x333AF`). `price(g)` is routine `0x30566`: the
  nation's price byte at `+4Ch + g` plus a per-goods byte at
  `DS:9700h + 9*g`, not below 0.
- If the player pays and has the gold, the gold goes down, the nation's
  long at `+22h` goes up by the same amount, and bit `g` is cleared
  (`0x3340D`-`0x33423`). Without the gold: KISSSORRY.

A new game starts with no boycotts (`0x36622`).

## Proof

QEMU, TCG, 2026-10-19, on a test-only EXE with the King's check forced
every turn (`0x3614B`, `0x36155`, `0x361BA` -> `EB`), and a save with
England's boycott mask cleared. Memory dumps were read at DS base physical
`0x20C40`.

| moment | tax | coats in Jamestown | Jamestown bells | boycott mask |
|---|---|---|---|---|
| dialog up, KINGWAR +2 | 11 | 90 | 952 | 0000 |
| after "Hold Party" ("90 tons") | 9 | 0 | 1042 | 0000 |
| message closed | 9 | 0 | 1042 | 1000 (bit 12, coats) |
| map, panel redrawn | panel "9%" | | | |

An earlier raise in the same run (KINGWIFE +1) was accepted
with SPACE: the tax stayed at 9.
