"""Overlay the ortho renders on the turnaround at the measured scales: blueprint dimmed, render at 55%."""
import os
import sys
from PIL import Image, ImageEnhance
pre = sys.argv[1]
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
TURNAROUND = os.path.join(REPO, 'art', 'roadster', 'reference-images', 'turnaround-v2.png')
if not os.path.exists(TURNAROUND):
    sys.exit(f'overlay.py: {TURNAROUND} is missing. The AI turnaround is not distributed (see NOTICE.md).')
T = Image.open(TURNAROUND).convert('RGBA')
s_side = 4.6 / 726
# (render, blueprint centre col, centre row) for render centre (u, z)
specs = [('side', 513 + 2.3 / s_side, 458 - (0.93 + 0.02) / s_side),
         ('front', 258.5, 469 - 0.66 / (1.31 / 255)),
         ('back', 256.9, 1055 - 0.66 / (1.31 / 267))]
outs = []
for name, cx, cy in specs:
    r = Image.open(f'{pre}-{name}.png').convert('RGBA')
    w, h = r.size
    box = (int(cx - w / 2), int(cy - h / 2), int(cx - w / 2) + w, int(cy - h / 2) + h)
    bg = T.crop(box)
    a = r.split()[3].point(lambda v: int(v * 0.55))
    r.putalpha(a)
    comp = Image.alpha_composite(bg, r)
    side = Image.new('RGBA', (w * 2, h), (255, 255, 255, 255))
    side.paste(T.crop(box), (0, 0)); side.paste(comp, (w, 0))
    outs.append(side)
W = max(o.width for o in outs); H = sum(o.height for o in outs)
sheet = Image.new('RGB', (W, H), 'white'); y = 0
for o in outs: sheet.paste(o.convert('RGB'), (0, y)); y += o.height
sheet.save(f'{pre}-overlay.png')
print(sheet.size)
