"""Generates public/textures/vapor-lit.png: a 4x2 atlas of billowing vapor puffs.

Channels (linear, not colour):
  R = light reaching the surface from above (self-shadowed)
  G = light reaching the surface from below (self-shadowed)
  B = thinness / translucency (for back- and rim-light)
  A = opacity
The runtime shader mixes floodlight, jet and lane-LED colours from these terms.
Deterministic: fixed seeds. Run: python3 tools/textures/gen_vapor_atlas.py
"""
import numpy as np
from PIL import Image
import os

CELL = 512
COLS, ROWS = 4, 2
rng_global = np.random.default_rng(7)

def value_noise(shape, scale, rng):
    gh, gw = int(shape[0] / scale) + 3, int(shape[1] / scale) + 3
    grid = rng.random((gh, gw))
    y = np.arange(shape[0]) / scale
    x = np.arange(shape[1]) / scale
    yi, xi = np.floor(y).astype(int), np.floor(x).astype(int)
    yf, xf = y - yi, x - xi
    yf = yf * yf * (3 - 2 * yf); xf = xf * xf * (3 - 2 * xf)
    a = grid[yi][:, xi]; b = grid[yi][:, xi + 1]; c = grid[yi + 1][:, xi]; d = grid[yi + 1][:, xi + 1]
    xf = xf[None, :]; yf = yf[:, None]
    return (a * (1 - xf) + b * xf) * (1 - yf) + (c * (1 - xf) + d * xf) * yf

def fbm(shape, base, rng, octaves=5):
    total = np.zeros(shape); amp = 0.5; norm = 0
    for o in range(octaves):
        total += amp * value_noise(shape, base / (2 ** o), rng); norm += amp; amp *= 0.5
    return total / norm

def puff(seed, kind):
    rng = np.random.default_rng(seed)
    n = CELL
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64) / n
    # domain warp for wispy, turbulent edges
    wx = fbm((n, n), 90, rng) - 0.5
    wy = fbm((n, n), 90, rng) - 0.5
    warp = 0.05 if kind != 'wisp' else 0.09
    px = xx + wx * warp; py = yy + wy * warp
    front = np.full((n, n), -1.0); back = np.full((n, n), 1.0)
    spheres = []
    if kind == 'mound':
        for _ in range(9):
            spheres.append((rng.uniform(0.24, 0.76), rng.uniform(0.58, 0.72), rng.uniform(-0.05, 0.05), rng.uniform(0.11, 0.19)))
    elif kind == 'tower':
        for i in range(10):
            t = i / 9
            spheres.append((0.5 + rng.uniform(-0.12, 0.12) + 0.06 * np.sin(t * 5), 0.76 - t * 0.5, rng.uniform(-0.05, 0.05), rng.uniform(0.1, 0.16) * (1.1 - 0.4 * t)))
    else:  # wisp / torn puff
        for _ in range(7):
            spheres.append((rng.uniform(0.25, 0.75), rng.uniform(0.4, 0.72), rng.uniform(-0.05, 0.05), rng.uniform(0.08, 0.15)))
    # cauliflower detail on top of the primary masses
    primary = list(spheres)
    for _ in range(46 if kind != 'wisp' else 30):
        cx, cy, cz, r = primary[rng.integers(len(primary))]
        theta = rng.uniform(-np.pi * 0.95, -np.pi * 0.05) if rng.random() < 0.8 else rng.uniform(0, np.pi * 2)
        rr = r * rng.uniform(0.75, 1.0)
        spheres.append((cx + np.cos(theta) * rr, cy + np.sin(theta) * rr, cz + rng.uniform(-0.04, 0.04), r * rng.uniform(0.25, 0.5)))
    for cx, cy, cz, r in spheres:
        d2 = (px - cx) ** 2 + (py - cy) ** 2
        inside = d2 < r * r
        h = np.sqrt(np.maximum(r * r - d2, 0))
        front = np.where(inside, np.maximum(front, cz + h), front)
        back = np.where(inside, np.minimum(back, cz - h), back)
    covered = front > back
    thickness = np.where(covered, front - back, 0.0)
    detail = fbm((n, n), 55, rng)
    fine = fbm((n, n), 16, rng, 4)
    # erode the soft shell with noise so edges tear into wisps instead of a hard silhouette
    density = np.clip(thickness * 1.6 - (1 - detail) * 0.22 - (1 - fine) * 0.06, 0, None)
    density *= 0.75 + 0.5 * detail
    if kind == 'wisp':
        density *= 0.75 + 0.5 * fbm((n, n), 70, rng)
    # soft cell window so nothing touches the atlas borders
    win = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) / 0.06, 0, 1)
    alpha = (1 - np.exp(-density * 14)) * win
    # bottom of each puff dissolves a little so it can sit in ground haze
    alpha *= 0.55 + 0.45 * np.clip((0.86 - yy) / 0.2, 0, 1)
    hf = np.where(covered, front, -0.3) + (detail - 0.5) * 0.05
    for axis in (0, 1):
        for _ in range(3):
            hf = (np.roll(hf, 2, axis) + np.roll(hf, -2, axis) + hf * 2) / 4
    gy, gx = np.gradient(hf * n * 0.6)
    nrm = np.stack([-gx, gy, np.ones_like(gx)], -1)  # image y down -> flip to y up
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    up = np.array([0.0, 1.0, 0.45]); up /= np.linalg.norm(up)
    dn = np.array([0.0, -1.0, 0.45]); dn /= np.linalg.norm(dn)
    lam_top = np.clip((nrm @ up + 0.35) / 1.35, 0, 1)
    lam_bot = np.clip((nrm @ dn + 0.35) / 1.35, 0, 1)
    step = 1.0 / n
    acc_top = np.cumsum(density, axis=0) * step  # rows above (smaller index)
    acc_bot = np.cumsum(density[::-1], axis=0)[::-1] * step
    shadow_top = np.exp(-acc_top * 16.0)
    shadow_bot = np.exp(-acc_bot * 16.0)
    top = shadow_top * (0.45 + 0.55 * lam_top)
    bottom = shadow_bot * (0.45 + 0.55 * lam_bot)
    thin = np.exp(-density * 9.0)
    rgba = np.stack([top, bottom, thin, alpha], -1)
    return np.clip(rgba, 0, 1)

kinds = ['mound', 'mound', 'tower', 'mound', 'wisp', 'tower', 'mound', 'wisp']
atlas = np.zeros((CELL * ROWS, CELL * COLS, 4))
for i, kind in enumerate(kinds):
    r, c = divmod(i, COLS)
    atlas[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = puff(101 + i * 17, kind)
out = os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'textures', 'vapor-lit.png')
Image.fromarray((atlas * 255 + 0.5).astype(np.uint8), 'RGBA').save(out, optimize=True)
print('wrote', os.path.abspath(out))
