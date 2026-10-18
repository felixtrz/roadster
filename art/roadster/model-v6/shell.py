"""Generate the v6 body shell from design.py: stations along y, each section built from the
character-line points with crowned spans between them; faces labelled by surface region."""
import json
import numpy as np
import design as D

def pchip(xk, yk, x):
    xk, yk = np.asarray(xk, float), np.asarray(yk, float)
    h = np.diff(xk); dl = np.diff(yk) / h
    m = np.zeros_like(yk)
    for i in range(1, len(xk) - 1):
        if dl[i - 1] * dl[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
    m[0], m[-1] = dl[0], dl[-1]
    x = np.clip(x, xk[0], xk[-1])
    i = np.clip(np.searchsorted(xk, x) - 1, 0, len(xk) - 2)
    t = (x - xk[i]) / h[i]
    h00, h10, h01, h11 = 2*t**3 - 3*t**2 + 1, t**3 - 2*t**2 + t, -2*t**3 + 3*t**2, t**3 - t**2
    return h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]

def line(knots, ys):
    k = np.array(knots, float)
    return np.c_[pchip(k[:, 0], k[:, 1], ys), pchip(k[:, 0], k[:, 2], ys)]

# stations: dense where the form turns quickly (nose, cowl, tail)
ys = np.unique(np.round(np.r_[np.linspace(-2.28, -1.9, 12), np.linspace(-1.9, -1.2, 22), np.linspace(-1.2, 1.9, 56),
                              np.linspace(1.9, 2.28, 12)], 4))
Cz = line(D.C, ys)[:, 1]
RMl = line(D.RM, ys)
rail = line(D.RAIL, ys)
RPl = RMl + rail
Bl, Sl, Wl, Kl = line(D.B, ys), line(D.S, ys), line(D.W, ys), line(D.K, ys)
k = np.array(D.Lz); Lz = pchip(k[:, 0], k[:, 1], ys)
Ll = np.c_[Kl[:, 0] - D.LIN, Lz]
Fl = np.c_[Ll[:, 0] - D.FIN, Lz - 0.02]
# named points in ring order, with subdivisions and crown (m) for the span that FOLLOWS each point
SPANS = [('C', 10, .014), ('RM', 1, 0), ('RP', 6, .008), ('B', 3, 0), ('S', 6, .012), ('W', 4, .006),
         ('K', 2, 0), ('L', 1, 0), ('F', 4, 0), ('FC', 0, 0)]
def ring(i):
    P = {'C': (0.0, Cz[i]), 'RM': tuple(RMl[i]), 'RP': tuple(RPl[i]), 'B': tuple(Bl[i]), 'S': tuple(Sl[i]),
         'W': tuple(Wl[i]), 'K': tuple(Kl[i]), 'L': tuple(Ll[i]), 'F': tuple(Fl[i]), 'FC': (0.0, Fl[i][1])}
    pts, tags = [], []
    names = [s[0] for s in SPANS]
    for j, (nm, sub, crown) in enumerate(SPANS):
        a = np.array(P[nm]); pts.append(a); tags.append(nm)
        if j == len(SPANS) - 1: break
        b = np.array(P[names[j + 1]])
        ch = b - a; L = np.linalg.norm(ch) + 1e-9
        # crown only where the reference surface is curved: roof and doors; hood, fenders and deck
        # are flat facets (front/rear views)
        yy = ys[i]
        cabin = np.clip((yy + 1.25) / 0.25, 0, 1) * np.clip((0.9 - yy) / 0.3, 0, 1)
        crown = crown * (cabin if nm in ('C', 'RP') else 1.0)
        n = np.array([ch[1], -ch[0]]) / L
        if n @ ((a + b) / 2 - np.array([0, 0.6])) < 0: n = -n
        for s in range(1, sub + 1):
            t = s / (sub + 1)
            pts.append(a + ch * t + n * crown * 4 * t * (1 - t)); tags.append(nm + '>')
    return np.array(pts), tags
R0, TAGS = ring(0)
K = len(R0)
half = np.array([ring(i)[0] for i in range(len(ys))])            # (S, K, 2)
left = np.dstack([half[:, :, 0], np.repeat(ys[:, None], K, 1), half[:, :, 1]])
right = left[:, -2:0:-1].copy(); right[:, :, 0] *= -1
full = np.concatenate([left, right], 1)
M = full.shape[1]; S = len(ys)
V = full.reshape(-1, 3)
# ring index -> span name (span that starts at that ring vertex), mirrored for the right half
span_of = []
cur = None
for t in TAGS:
    cur = t.rstrip('>'); span_of.append(cur)
ring_span = span_of + span_of[-2:0:-1][::-1][::-1]
right_span = [span_of[K - 2 - j] for j in range(K - 2)]       # vertex K+j mirrors left vertex K-2-j
# the span of the quad (j -> j+1): left half uses span at j; right half uses span at the mirrored j+1
def quad_span(j):
    if j < K - 1: return span_of[j]
    mj = M - j - 1                                            # mirror of vertex j+1 on the left
    return span_of[mj]
quads, region = [], []
for i in range(S - 1):
    for j in range(M):
        quads.append((i * M + j, i * M + (j + 1) % M, (i + 1) * M + (j + 1) % M, (i + 1) * M + j))
        region.append(quad_span(j))
sharp_rings = [j for j, t in enumerate(TAGS) if t in ('RM', 'RP', 'B', 'K')]   # S and W shade soft (judge: fender shoulders)
sharp_cols = sorted(set(sharp_rings + [M - j for j in sharp_rings]))
np.savez('shell.npz', co=V, quads=np.array(quads), region=np.array(region), stations=ys, M=M, K=K,
         sharp_cols=np.array(sharp_cols), tags=np.array(TAGS))
print('stations', S, 'ring', M, 'verts', len(V), 'quads', len(quads), 'bounds', V.min(0).round(3), V.max(0).round(3))
print('sharp ring columns', sharp_cols)
