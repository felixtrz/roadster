import os, sys
_SKILL = os.environ.get('MESH_REBUILD_SKILL', '')
if not os.path.isdir(_SKILL):
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory (contains facets.py).')
sys.path.insert(0, _SKILL)
from facets import *
R = load('reference/faces.npz')
P, N, A = R['fc'], R['fn'], R['fa']
# exclude wheel cylinders (approx) and underside
def wheel_mask():
    m = np.zeros(len(A), bool)
    for yc in (-1.42, 1.42):
        r = np.hypot(P[:, 1] - yc, P[:, 2] - 0.37)
        m |= (r < 0.40) & (np.abs(P[:, 0]) > 0.75)
    return m
ok = ~wheel_mask() & (N[:, 2] > -0.5)
def show(title, lo, hi, tol=8, band=0.012, min_area=4e-3, extra=None):
    m = ok if extra is None else ok & extra
    p, n, a = gather(R, m, lo, hi)
    cl = cluster(p, n, a, tol=tol, min_area=min_area, band=band, max_planes=40)
    print(f'== {title}: area {a.sum():.3f} m2')
    for nm, nn, d, s in cl:
        k = (n @ nn > np.cos(np.radians(tol))) & (np.abs(p @ nn - d) < band)
        c = (p[k] * a[k, None]).sum(0) / max(a[k].sum(), 1e-9)
        print(f'  {nm:4s} n=({nn[0]:+.3f},{nn[1]:+.3f},{nn[2]:+.3f}) d={d:+.4f} sup {s*1e4:7.0f} cm2  at ({c[0]:+.2f},{c[1]:+.2f},{c[2]:+.2f})  yrange {np.percentile(p[k,1],5):+.2f}..{np.percentile(p[k,1],95):+.2f} zrange {np.percentile(p[k,2],5):.2f}..{np.percentile(p[k,2],95):.2f}')
light = np.linalg.norm(R['col'] - 0.91, axis=1) < 0.25
show('white body (left half, folded)', (0, -2.5, 0.0), (1.4, 2.5, 1.5), extra=light)
show('dark non-white body', (0, -2.5, 0.0), (1.4, 2.5, 1.5), extra=~light)
