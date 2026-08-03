#!/usr/bin/env python3
"""Detect the colony-arrival / Sons-of-Liberty popup with the
"Continue turn" / "Zoom to colony" options.
Prints: "POPUP <y1>" (y-center of the first/"Continue turn" option row) or "NOPOPUP".
Signature: bright-green text runs on brown at TWO option rows in x in [90,245]."""
import sys
from PIL import Image

im = Image.open(sys.argv[1]).convert('RGB')
px = im.load()

def green_count(y, x0=90, x1=245):
    c = 0
    for x in range(x0, x1):
        r, g, b = px[x, y]
        if g > 130 and g > r + 25 and b < 130:
            c += 1
    return c

# scan candidate option rows in the lower dialog band; find two green text bands
band = [(y, green_count(y)) for y in range(295, 360)]
rows = [y for y, c in band if c >= 12]
# group consecutive rows into bands
bands = []
for y in rows:
    if bands and y - bands[-1][-1] <= 2:
        bands[-1].append(y)
    else:
        bands.append([y])
if len(bands) >= 2:
    y1 = sum(bands[0]) // len(bands[0])
    print(f'POPUP {y1}')
else:
    print('NOPOPUP')
print(f'bands={[(b[0],b[-1]) for b in bands]}', file=sys.stderr)
