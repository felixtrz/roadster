"""Faceted hard-surface shell (v5b): every station is the polygon of tangent facets at fixed normal
angles (the 2D form of the skill's plane fit: facet offset = support of the measured section along
that normal), so sections are clean convex polygons with no generated-mesh dents. Facet offsets are
faired along the car, so each facet becomes one continuous panel and the facet boundaries become
continuous feature lines. Writes fit/shell.npz in the loft.npz format plus a facet id per ring vertex."""
import numpy as np
d = np.load('fit/loft.npz')
ring, ys = d['ring'], d['stations']               # (S, K, 2) half sections x>=0, top -> bottom
S = len(ys)
# facet normal angles from straight up (0) through the side (90) to straight down (180)
PHI = np.radians([0, 7, 15, 24, 34, 45, 56, 66, 76, 86, 94, 103, 115, 132, 155, 180])
F = len(PHI)
n = np.c_[np.sin(PHI), np.cos(PHI)]               # (F, 2) as (x, z)
H = np.einsum('skc,fc->sf', ring, n).max(2) if False else np.max(ring @ n.T, axis=1)   # (S, F) support
def gsmooth(a, sigma, axis=0):
    r = int(3 * sigma); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, [(r, r) if i == axis else (0, 0) for i in range(a.ndim)], mode='edge')
    return np.apply_along_axis(lambda v: np.convolve(v, k, 'valid'), axis, pad)
H0 = H.copy()
# panels must be fair along the car: Tripo ripple is 0.1-0.3 m long, so fair each facet offset with a
# wide kernel, keeping the nose/tail ends anchored (edge padding)
H = gsmooth(H, 4.0)
# hood: one flat plane per top facet ahead of the windshield (the reference's wedge), blended back in
hood = ys < -1.25
for f in range(4):
    sel = ys < -1.45
    c = np.polyfit(ys[sel], H[sel, f], 1)
    lin = np.polyval(c, ys)
    wgt = np.clip((-1.25 - ys) / 0.2, 0, 1)
    H[:, f] = wgt * lin + (1 - wgt) * H[:, f]
print('max |faired - measured| per facet (mm):', np.round(np.abs(H - H0).max(0) * 1000).astype(int).tolist())
# polygon vertices: mid-plane top point, facet-facet intersections, mid-plane bottom point
def vert(i, a, b):
    A = np.array([n[a], n[b]]); return np.linalg.solve(A, [H[i, a], H[i, b]])
half = []
for i in range(S):
    pts = [(0.0, H[i, 0])]
    for f in range(F - 1):
        p = vert(i, f, f + 1)
        pts.append((max(p[0], 0.0), p[1]))
    pts.append((0.0, -H[i, F - 1]))
    half.append(pts)
half = np.array(half)                               # (S, F+1, 2)
# guard against collapsed facets producing points out of order: enforce monotone angle around centre
K = half.shape[1]
left = np.dstack([half[:, :, 0], np.repeat(ys[:, None], K, 1), half[:, :, 1]])
right = left[:, -2:0:-1].copy(); right[:, :, 0] *= -1
full = np.concatenate([left, right], 1)
M = full.shape[1]
V = full.reshape(-1, 3)
quads = [(i * M + j, i * M + (j + 1) % M, (i + 1) * M + (j + 1) % M, (i + 1) * M + j) for i in range(S - 1) for j in range(M)]
cap0 = np.arange(M)[::-1]; cap1 = np.arange((S - 1) * M, S * M)
np.savez('fit/shell.npz', co=V, quads=np.array(quads), stations=ys, K=K, M=M, cap0=cap0, cap1=cap1, ring=half, phi=PHI)
tris = [(a, b, c) for a, b, c, dd in quads] + [(a, c, dd) for a, b, c, dd in quads]
for cap in (cap0, cap1):
    for k in range(1, len(cap) - 1): tris.append((cap[0], cap[k], cap[k + 1]))
np.savez('fit/shell_tris.npz', co=V, tri=np.array(tris))
print('facets/half', F, 'ring verts', M, 'stations', S, 'bounds', V.min(0).round(3), V.max(0).round(3))
