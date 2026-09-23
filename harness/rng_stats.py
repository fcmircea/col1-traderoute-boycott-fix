#!/usr/bin/env python3
"""Summarise RNG state samples from sample_rng_state.sh.

    rng_stats.py stock.tsv patched.tsv ...

For each sampled 32-bit state it computes the value the NEXT rand() call
would return (Microsoft C LCG: state*214013 + 2531011, output bits 16-30),
and reports how much those next draws look like independent random numbers:

  r1        lag-1 autocorrelation of consecutive next-draws (0 = none)
  chi2      8 equal bins over 0..32767, 7 degrees of freedom
            (critical value 14.07 at p = 0.05)
  mean gap  average |difference| between consecutive next-draws
            (independent uniform draws: about 10923)
  range     (max - min) / 32768 of the next-draws
  hi==0     how many samples had the high state word at zero
"""
import math
import sys


def next_draw(state: int) -> int:
    return (((state * 214013 + 2531011) & 0xFFFFFFFF) >> 16) & 0x7FFF


def load(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) != 4 or "?" in parts:
                continue
            lo, hi = int(parts[2], 16), int(parts[3], 16)
            rows.append((lo, hi))
    return rows


def r1(xs):
    n = len(xs)
    m = sum(xs) / n
    num = sum((xs[i] - m) * (xs[i + 1] - m) for i in range(n - 1))
    den = sum((x - m) ** 2 for x in xs)
    return num / den if den else float("nan")


def chi2(xs, bins=8):
    counts = [0] * bins
    for x in xs:
        counts[x * bins // 32768] += 1
    e = len(xs) / bins
    return sum((c - e) ** 2 / e for c in counts)


def summary(path):
    rows = load(path)
    xs = [next_draw(hi << 16 | lo) for lo, hi in rows]
    n = len(xs)
    gaps = [abs(xs[i + 1] - xs[i]) for i in range(n - 1)]
    return dict(file=path, n=n, r1=r1(xs), se=1 / math.sqrt(n), chi2=chi2(xs),
                gap=sum(gaps) / len(gaps), range=(max(xs) - min(xs)) / 32768,
                hi0=sum(1 for _, hi in rows if hi == 0), first=xs[:6])


def main():
    print(f"{'file':28s} {'n':>3s} {'r1':>7s} {'SE':>5s} {'chi2':>7s} {'mean gap':>9s} {'range':>6s} {'hi==0':>6s}  first next-draws")
    for path in sys.argv[1:]:
        s = summary(path)
        print(f"{s['file'][-28:]:28s} {s['n']:3d} {s['r1']:+7.3f} {s['se']:5.3f} {s['chi2']:7.1f} "
              f"{s['gap']:9.0f} {s['range']:6.0%} {s['hi0']:3d}/{s['n']:<3d} {s['first']}")


if __name__ == "__main__":
    main()
