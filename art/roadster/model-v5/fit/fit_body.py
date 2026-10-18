"""Seeded facet fit of the body hull and cabin (v5). Seeds come from fit/explore.py clusters."""
from lib5 import *
B = 2.6
L = lambda y0, y1, z0, z1, x0=0.0, x1=1.4: ((x0, y0, z0), (x1, y1, z1))
BODY = [
  ('bottom', (0, 0, -1), -0.115, 'fixed', *L(-3, 3, 0, 2)),
  ('fascia', (0.062, -0.98, -0.19), 2.163, 'mid', *L(-2.35, -2.15, 0.25, 0.55)),
  ('noseLip', (0.019, -0.555, 0.832), 1.701, 'mid', *L(-2.3, -1.95, 0.5, 0.72)),
  ('noseTop', (0.017, -0.411, 0.912), 1.449, 'mid', *L(-2.2, -1.65, 0.6, 0.83)),
  ('hoodFront', (0.01, -0.208, 0.978), 1.147, 'mid', *L(-1.8, -1.5, 0.75, 0.88)),
  ('hood', (0.0, 0.011, 0.997), 0.84, 'fixed', *L(-1.6, -1.0, 0.8, 0.92)),
  ('hoodValley', (-0.07, 0.011, 0.997), 0.792, 'pair', *L(-1.6, -1.0, 0.75, 0.95, 0.3, 1.1)),
  ('sideF', (0.997, 0.016, 0.076), 1.0996, 'pair', *L(-1.0, 0.3, 0.3, 0.8, 0.9)),
  ('sideR', (0.976, -0.126, 0.18), 1.109, 'pair', *L(0.1, 1.3, 0.35, 0.85, 0.9)),
  ('flankR', (0.963, 0.083, 0.258), 1.458, 'pair', *L(1.4, 2.0, 0.7, 0.95, 0.9)),
  ('flankR2', (0.966, 0.245, 0.08), 1.625, 'pair', *L(1.8, 2.25, 0.6, 0.95, 0.9)),
  ('shoulderR', (0.903, -0.142, 0.405), 1.186, 'pair', *L(0.4, 1.4, 0.7, 0.95, 0.8)),
  ('shoulderF', (0.811, 0.226, 0.539), 1.071, 'pair', *L(-1.3, -0.8, 0.7, 0.9, 0.8)),
  ('cornerF', (0.797, -0.598, 0.081), 2.036, 'pair', *L(-2.25, -1.8, 0.3, 0.6, 0.6)),
  ('cornerF2', (0.733, -0.604, 0.313), 2.11, 'pair', *L(-2.25, -1.75, 0.5, 0.72, 0.6)),
  ('cornerF3', (0.483, -0.40, 0.779), 1.806, 'pair', *L(-1.85, -1.55, 0.7, 0.87, 0.6)),
  ('deckHaunch', (0.302, -0.063, 0.951), 1.133, 'pair', *L(0.2, 1.65, 0.88, 1.02, 0.7)),
  ('rearDeck', (0.154, 0.101, 0.983), 1.286, 'pair', *L(1.55, 2.2, 0.9, 1.05, 0.5)),
  ('tailSlope', (0.005, 0.376, 0.927), 1.702, 'mid', *L(2.1, 2.3, 0.88, 1.0)),
  ('rearFace', (0.0, 1.0, 0.0), 2.257, 'mid', *L(2.2, 2.3, 0.55, 0.8)),
  ('rearCorner', (0.918, 0.393, -0.056), 1.775, 'pair', *L(2.0, 2.25, 0.65, 0.9, 0.8)),
  ('rearCornerLo', (0.83, 0.496, -0.256), 1.776, 'pair', *L(1.85, 2.2, 0.3, 0.68, 0.8)),
  ('sill', (0.973, -0.061, 0.221), 1.114, 'pair', *L(-0.8, 0.8, 0.1, 0.34, 0.9)),
  ('sillUnder', (0.981, -0.083, -0.176), 1.015, 'pair', *L(-0.75, 1.0, 0.12, 0.35, 0.9)),
  ('sillBottom', (0.91, -0.071, -0.41), 0.891, 'pair', *L(-0.7, 0.4, 0.09, 0.24, 0.9)),
  ('cornerFLo', (0.801, -0.591, -0.097), 1.975, 'pair', *L(-2.2, -1.9, 0.15, 0.3, 0.6)),
]
CABIN = [
  ('cabinBottom', (0, 0, -1), -0.70, 'fixed', *L(-3, 3, 0, 2)),
  ('roof', (0.05, 0.149, 0.988), 1.3806, 'pair', *L(0.6, 1.45, 1.13, 1.3, 0.0, 0.7)),
  ('roofFront', (0.058, -0.182, 0.982), 1.329, 'pair', *L(-0.45, -0.1, 1.22, 1.32, 0.0, 0.7)),
  ('windshield', (0.061, -0.349, 0.935), 1.346, 'pair', *L(-1.55, -0.45, 0.84, 1.24, 0.0, 0.7)),
  ('aPillar', (0.249, -0.35, 0.903), 1.429, 'pair', *L(-1.45, -0.65, 0.85, 1.15, 0.4, 0.9)),
  ('aPillar2', (0.488, -0.245, 0.838), 1.368, 'pair', *L(-1.4, -0.85, 0.85, 1.1, 0.4, 1.0)),
  ('roofEdge', (0.464, -0.164, 0.87), 1.4445, 'pair', *L(-0.75, -0.15, 1.08, 1.28, 0.5, 0.9)),
  ('sideGlass', (0.809, 0.032, 0.586), 1.3007, 'pair', *L(0.0, 0.85, 0.95, 1.23, 0.6, 1.0)),
  ('sideGlassLo', (0.913, 0.101, 0.395), 1.173, 'pair', *L(-0.5, 0.4, 0.85, 1.2, 0.7, 1.0)),
  ('haunch', (0.764, 0.057, 0.643), 1.353, 'pair', *L(0.3, 1.2, 0.9, 1.26, 0.6, 1.0)),
  ('haunchRear', (0.645, 0.186, 0.742), 1.5256, 'pair', *L(1.0, 1.85, 1.0, 1.18, 0.5, 0.9)),
  ('rearGlass', (0.011, 0.303, 0.953), 1.580, 'mid', *L(1.8, 2.15, 0.97, 1.08, 0.0, 0.5)),
  ('rearDeckC', (0.168, 0.281, 0.945), 1.594, 'pair', *L(1.55, 2.15, 0.93, 1.1, 0.4, 0.8)),
]
FRONT_NAMES = {'bottom','fascia','noseLip','noseTop','hoodFront','hood','sideF','shoulderF','cornerF','cornerF2','cornerF3','sill','sillUnder','sillBottom','cornerFLo'}
REAR_NAMES = {'bottom','sideF','sideR','flankR','flankR2','shoulderR','deckHaunch','rearDeck','tailSlope','rearFace','rearCorner','rearCornerLo','sill','sillUnder','sillBottom'}
if __name__ == '__main__':
    allp, r1 = seeded(BODY); cabin, r2 = seeded(CABIN)
    base = lambda nm: nm[:-1] if nm[-1] in 'LR' and nm[:-1] in {b[0] for b in BODY} else nm
    front = [p for p in allp if base(p[0]) in FRONT_NAMES] + [('frontCap', unit((0, 1, 0)), -0.3)]
    rear = [p for p in allp if base(p[0]) in REAR_NAMES] + [('rearCap', unit((0, -1, 0)), 1.05)]
    cabin += [p for p in allp if base(p[0]) in ('rearFace', 'tailSlope')]
    body = front
    print('\n'.join(r1)); print('--'); print('\n'.join(r2))
    for nm, pl in (('front', front), ('rear', rear), ('cabin', cabin)):
        V = polyhedron(pl); u = used_planes(pl, V)
        print(nm, len(V), 'verts; unused:', [p[0] for p in pl if p[0] not in u], 'bounds', V.min(0).round(3), V.max(0).round(3))
    save_solid('fit/body.json', {'BodyFront': front, 'BodyRear': rear, 'Cabin': cabin})
    import secs
    p = section_sheet('body', [front, rear, cabin], secs.SECTIONS); print(p)
