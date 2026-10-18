"""Body shell as a measured section loft (v5).
Each station is a y-section of the reference (wheel/tyre faces removed); its outer contour is read
by polar rays from a centre on the mirror plane, resampled by arc length with feature anchors,
lightly faired along the car, mirrored, and lofted into one closed quad shell. Writes fit/loft.npz
(co, quads, per-face reference colour) for the Blender build and sections."""
from lib5 import *
sys.path.insert(0, V5)
from secs import cut
co, tri = R['co'], R['tri']
# drop wheel/tyre/brake geometry so stations through the arches read the body only
fc = co[tri].mean(1)
keep = np.ones(len(tri), bool)
for yc, zc, rr in ((-1.414, 0.365, 0.40), (1.437, 0.393, 0.43)):
    keep &= ~((np.hypot(fc[:, 1] - yc, fc[:, 2] - zc) < rr) & (np.abs(fc[:, 0]) > 0.62))
T = tri[keep]
K = 72                     # half-section samples, top centre -> bottom centre
NRAY = 720
ARCH = ((-1.414, 0.365, 0.47), (1.437, 0.393, 0.50))
th = np.linspace(0, np.pi, NRAY)
ZC = {}
BAD = {}
def polar(y):
    segs = cut(co, T, 'y', y, [0.0, 1.5, -0.1, 1.6])
    pts = np.r_[segs[:, :2], segs[:, 2:]]
    pts = pts[pts[:, 0] >= -0.002]
    zc = 0.5 * (pts[:, 1].min() + pts[:, 1].max()); ZC[y] = zc
    ang = np.arctan2(pts[:, 0], pts[:, 1] - zc)
    rad = np.hypot(pts[:, 0], pts[:, 1] - zc)
    idx = np.clip(np.round(ang / np.pi * (NRAY - 1)).astype(int), 0, NRAY - 1)
    rmax = np.full(NRAY, np.nan)
    np.fmax.at(rmax, idx, rad)
    # inside a wheel arch the outer-lower rays only see liners and brakes: mark unknown
    x, z = rmax * np.sin(th), zc + rmax * np.cos(th)
    for yc, zw, ra in ARCH:
        bad = (np.hypot(y - yc, z - zw) < ra) & (x < 1.08) & (x > 0.55) & (z < zw + ra)
        if abs(y - yc) < ra * 0.98:
            bad |= (th > np.pi * 0.3) & (th < np.pi * 0.92) & (np.isnan(rmax) | (z < zw + ra * 0.95))
        BAD[y] = bad
    ok = ~np.isnan(rmax) & ~bad
    return np.interp(th, th[ok], rmax[ok])
def contour(rmax, zc):
    from numpy.lib.stride_tricks import sliding_window_view as sw
    pad = np.r_[rmax[:2], rmax, rmax[-2:]]
    rmax = np.median(sw(pad, 5), axis=1)
    x, z = rmax * np.sin(th), zc + rmax * np.cos(th)
    x[0] = 0; x[-1] = 0
    d = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(z)))]
    s = np.linspace(0, d[-1], K)
    return np.c_[np.interp(s, d, x), np.interp(s, d, z)]
ys = np.r_[np.linspace(-2.285, -2.05, 8)[:-1], np.linspace(-2.05, 2.05, 60), np.linspace(2.05, 2.252, 7)[1:]]
RM = np.array([polar(y) for y in ys])
# fill unknown rays along the car from stations either side of the arch
BM = np.array([BAD[y] for y in ys])
for j in range(NRAY):
    col = RM[:, j]; ok = ~BM[:, j]
    if ok.sum() >= 2 and (~ok).any(): RM[~ok, j] = np.interp(ys[~ok], ys[ok], col[ok])
ring = np.array([contour(r, ZC[y]) for r, y in zip(RM, ys)])        # (S, K, 2)
# nose and tail: the generated mesh has intake/lamp pockets there, so the end stations are the last
# clean station tapered to the measured end extents (x max, z min, z max fitted as smooth quadratics)
ext = np.array([(r[:, 0].max(), r[:, 1].min(), r[:, 1].max()) for r in ring])
for sign, yref in ((-1, -1.95), (1, 1.95)):
    iref = int(np.argmin(np.abs(ys - yref)))
    idx = np.nonzero(sign * ys > sign * ys[iref])[0]
    fit_i = np.r_[iref, idx]
    base = ring[iref].copy()
    bx, bz0, bz1 = ext[iref]
    # measured end extents (reference, 25 mm bins: x max at lamp height, z min, z max)
    if sign < 0:
        my = [-2.285, -2.25, -2.2, -2.15, -2.1, -2.05, -2.0, -1.95]
        mx = [0.81, 0.82, 0.873, 0.908, 0.953, 0.99, 1.027, 1.067]
        m0 = [0.21, 0.185, 0.172, 0.161, 0.149, 0.14, 0.135, 0.132]
        m1 = [0.53, 0.552, 0.576, 0.61, 0.647, 0.675, 0.701, 0.721]
    else:
        my = [1.95, 2.0, 2.05, 2.1, 2.15, 2.2, 2.252]
        mx = [1.14, 1.131, 1.111, 1.089, 1.066, 1.047, 1.031]
        m0 = [0.099, 0.104, 0.15, 0.22, 0.29, 0.36, 0.40]
        m1 = [1.035, 1.02, 1.008, 0.992, 0.977, 0.953, 0.93]
    sc = [np.interp(ys[idx], my, m) / np.interp(ys[iref], my, m) for m in (mx, m0, m1)]
    for k in range(3):
        ext[idx, k] = ext[iref, k] * sc[k]
    for i in idx:
        xm, z0, z1 = ext[i]
        r2 = base.copy()
        r2[:, 0] = base[:, 0] * xm / bx
        r2[:, 1] = z0 + (base[:, 1] - bz0) * (z1 - z0) / (bz1 - bz0)
        ring[i] = r2
    print('end', sign, np.round(ext[idx], 3).tolist())
# fair along the car (light 1-2-1 smoothing on interior stations, twice)
for _ in range(2):
    ring[1:-1] = 0.25 * ring[:-2] + 0.5 * ring[1:-1] + 0.25 * ring[2:]
# the nose and tail carry intake/lamp pockets: fair the lower half harder there
end = (np.abs(ys) > 1.80)[:, None, None] & (np.arange(K) > K * 0.12)[None, :, None]
for _ in range(3):
    sm = ring.copy(); sm[1:-1] = 0.25 * ring[:-2] + 0.5 * ring[1:-1] + 0.25 * ring[2:]
    ring = np.where(end, sm, ring)
# fair around the section once (keeps creases at 72-sample density)
ring[:, 1:-1] = 0.2 * ring[:, :-2] + 0.6 * ring[:, 1:-1] + 0.2 * ring[:, 2:]
# lower body (sills, lower fascia): the generated mesh drapes there; fair along the car and around
lower = (np.arange(K) > K * 0.55)[None, :, None]
for _ in range(6):
    sm = ring.copy(); sm[1:-1] = 0.25 * ring[:-2] + 0.5 * ring[1:-1] + 0.25 * ring[2:]
    sm[:, 1:-1] = 0.25 * sm[:, :-2] + 0.5 * sm[:, 1:-1] + 0.25 * sm[:, 2:]
    ring = np.where(lower, sm, ring)
# upper surfaces (hood, glass, roof, deck) carry Tripo ripple that shows in reflections: fair them more
upper = (np.arange(K) < K * 0.42)[None, :, None]
for _ in range(4):
    sm = ring.copy(); sm[1:-1] = 0.25 * ring[:-2] + 0.5 * ring[1:-1] + 0.25 * ring[2:]
    ring = np.where(upper, sm, ring)
for _ in range(2):
    sm = ring.copy(); sm[:, 1:-1] = 0.25 * ring[:, :-2] + 0.5 * ring[:, 1:-1] + 0.25 * ring[:, 2:]
    ring = np.where(upper | (np.abs(ys) > 1.8)[:, None, None], sm, ring)
S = len(ys)
# full ring: left half (x>=0) top->bottom, then right half bottom->top (excluding the shared centre points)
left = np.dstack([ring[:, :, 0], np.repeat(ys[:, None], K, 1), ring[:, :, 1]])
right = left[:, -2:0:-1].copy(); right[:, :, 0] *= -1
full = np.concatenate([left, right], 1)          # (S, 2K-2, 3)
M = full.shape[1]
V = full.reshape(-1, 3)
quads = []
for i in range(S - 1):
    for j in range(M):
        a, b = i * M + j, i * M + (j + 1) % M
        quads.append((a, b, b + M, a + M))
# end caps as n-gons, recorded separately
caps = [list(range(M))[::-1], list(range((S - 1) * M, S * M))]
np.savez('fit/loft.npz', ring=ring, co=V, quads=np.array(quads), stations=ys, K=K, M=M, cap0=np.array(caps[0]), cap1=np.array(caps[1]))
# triangulated copy for offline sections
tris = [(a, b, c) for a, b, c, d in quads] + [(a, c, d) for a, b, c, d in quads]
for cap in caps:
    for k in range(1, len(cap) - 1): tris.append((cap[0], cap[k], cap[k + 1]))
np.savez('fit/loft_tris.npz', co=V, tri=np.array(tris))
print('stations', S, 'verts', len(V), 'quads', len(quads), 'bounds', V.min(0).round(3), V.max(0).round(3))
