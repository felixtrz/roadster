"""Shared fitting helpers for the v5 rebuild (numpy only)."""
import sys, json, math
import os
_SKILL = os.environ.get('MESH_REBUILD_SKILL', '')
if not os.path.isdir(_SKILL):
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory (contains facets.py).')
sys.path.insert(0, _SKILL)
V5 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from facets import *
R = load(os.path.join(V5, 'reference', 'faces.npz'))
P, N, A = R['fc'], R['fn'], R['fa']
WHEELS = {}
def wheel_mask():
    m = np.zeros(len(A), bool)
    for yc in (-1.42, 1.42):
        m |= (np.hypot(P[:, 1] - yc, P[:, 2] - 0.37) < 0.40) & (np.abs(P[:, 0]) > 0.75)
    return m
OK = ~wheel_mask()
def seeded(seeds, tol=8.0, band=0.012):
    """seeds: (name, n0, d0, sym, lo, hi). Returns planes + report."""
    planes, rep = [], []
    for name, n0, d0, sym, lo, hi in seeds:
        m = OK & box(R, (-hi[0], lo[1], lo[2]), hi) if sym != 'one' else OK & box(R, lo, hi)
        if sym == 'fixed':
            n = unit(n0); planes.append((name, n, float(d0))); rep.append(f'{name:12s} FIXED'); continue
        n, d, a, k = fit_one(R, m, n0, d0=d0, tol=tol, band=band, mirror=sym != 'one')
        if d is None: rep.append(f'{name:12s} NO SUPPORT'); continue
        if sym == 'mid': n[0] = 0; n = unit(n)
        if sym == 'pair':
            planes.append((name + 'L', n, d)); planes.append((name + 'R', n * MIRROR, d))
        else: planes.append((name, n, d))
        rep.append(f'{name:12s} n=({n[0]:+.3f},{n[1]:+.3f},{n[2]:+.3f}) d={d:+.4f} sup {a*1e4:6.0f} cm2 ({k})')
    return planes, rep
AX = {'x': (0, 1, 2), 'y': (1, 0, 2), 'z': (2, 0, 1)}
def poly_section(planes, axis, value, big=10.0):
    """Exact section polygon of the convex solid n.p<=d by an axis plane: 2D half-plane clip."""
    a, u, v = AX[axis]
    poly = [(-big, -big), (big, -big), (big, big), (-big, big)]
    for pl in planes:
        n, d = pl[1], pl[2]
        nu, nv, dd = n[u], n[v], d - n[a] * value
        if abs(nu) < 1e-12 and abs(nv) < 1e-12:
            if dd < 0: return []
            continue
        out = []
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            fp, fq = nu * p[0] + nv * p[1] - dd, nu * q[0] + nv * q[1] - dd
            if fp <= 0: out.append(p)
            if (fp < 0) != (fq < 0) and fp != fq:
                t = fp / (fp - fq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        poly = out
        if not poly: return []
    return poly
def poly_segs(poly):
    return [(poly[i][0], poly[i][1], poly[(i + 1) % len(poly)][0], poly[(i + 1) % len(poly)][1]) for i in range(len(poly))]
def section_sheet(tag, solids, sections, ppm=0.18):
    """solids: list of plane lists. Reference cut from faces table; writes sections/<tag>.json+png."""
    sys.path.insert(0, V5)
    from secs import cut
    out = []
    for pl in sections:
        rec = dict(pl); rec['ref'] = cut(R['co'], R['tri'], pl['axis'], pl['value'], pl['window']).round(5).tolist()
        segs = []
        for s in solids: segs += poly_segs(poly_section(s, pl['axis'], pl['value']))
        rec['auth'] = segs
        out.append(rec)
    path = os.path.join(V5, 'sections', f'{tag}.json')
    json.dump({'tag': tag, 'planes': out}, open(path, 'w'))
    return path
def save_solid(path, parts):
    """parts: {name: planes} -> json with planes and verts."""
    out = {}
    for name, planes in parts.items():
        V = polyhedron(planes)
        out[name] = {'planes': [(nm, list(map(float, n)), float(d)) for nm, n, d in planes], 'verts': V.tolist()}
    json.dump(out, open(path, 'w'), indent=1)
