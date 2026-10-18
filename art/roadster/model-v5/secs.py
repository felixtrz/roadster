"""Offline section cutter (numpy) with the skill's JSON format.
  python3 secs.py <tag> [auth.npz ...]   planes from SECTIONS below."""
import sys, json, numpy as np
AXES = {'x': (0, 1, 2), 'y': (1, 0, 2), 'z': (2, 0, 1)}
def cut(co, tri, axis, value, window):
    a, u, v = AXES[axis]
    s = (co[:, a] - value)[tri]
    hit = (s.min(1) < 0) & (s.max(1) > 0)
    T, S = tri[hit], s[hit]
    segs = []
    P = co[T]
    for k in range(len(T)):
        q = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (S[k, i] < 0) != (S[k, j] < 0):
                t = S[k, i] / (S[k, i] - S[k, j]); q.append(P[k, i] + t * (P[k, j] - P[k, i]))
        if len(q) == 2: segs.append((q[0][u], q[0][v], q[1][u], q[1][v]))
    segs = np.array(segs).reshape(-1, 4)
    u0, u1, v0, v1 = window
    ins = ((np.minimum(segs[:, 0], segs[:, 2]) <= u1) & (np.maximum(segs[:, 0], segs[:, 2]) >= u0) & (np.minimum(segs[:, 1], segs[:, 3]) <= v1) & (np.maximum(segs[:, 1], segs[:, 3]) >= v0))
    return segs[ins]
W_SIDE = [-2.45, 2.45, -0.05, 1.4]; W_FRONT = [-1.3, 1.3, -0.05, 1.4]; W_PLAN = [-1.3, 1.3, -2.45, 2.45]
SECTIONS = [dict(name='side x=0', axis='x', value=0.003, window=W_SIDE), dict(name='side x=0.55', axis='x', value=0.55, window=W_SIDE),
  dict(name='side x=0.85', axis='x', value=0.85, window=W_SIDE), dict(name='side x=1.05', axis='x', value=1.05, window=W_SIDE),
  dict(name='plan z=0.45', axis='z', value=0.45, window=W_PLAN), dict(name='plan z=0.75', axis='z', value=0.75, window=W_PLAN),
  dict(name='plan z=0.95', axis='z', value=0.95, window=W_PLAN), dict(name='plan z=1.15', axis='z', value=1.15, window=W_PLAN)] + \
  [dict(name=f'front y={y}', axis='y', value=y, window=W_FRONT) for y in (-2.0, -1.6, -1.0, -0.4, 0.2, 0.8, 1.4, 2.0)]
if __name__ == '__main__':
    tag = sys.argv[1]
    R = np.load('reference/faces.npz')
    auths = [np.load(p) for p in sys.argv[2:]]
    out = []
    for pl in SECTIONS:
        rec = dict(pl); rec['ref'] = cut(R['co'], R['tri'], pl['axis'], pl['value'], pl['window']).round(5).tolist()
        segs = [cut(A['co'], A['tri'], pl['axis'], pl['value'], pl['window']) for A in auths]
        rec['auth'] = (np.concatenate(segs) if segs else np.zeros((0, 4))).round(5).tolist()
        out.append(rec)
    json.dump({'tag': tag, 'planes': out}, open(f'sections/{tag}.json', 'w'))
