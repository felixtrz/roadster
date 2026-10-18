"""Paint boundaries from the reference texture: per 5 cm y-bin, on outward side faces, the z where the
white body meets the dark lower trim (sill line) and the dark glass (daylight opening)."""
from lib5 import *
white = np.linalg.norm(R['col'] - 0.91, axis=1) < 0.25
side = OK & (P[:, 0] > 0.55) & (N[:, 0] > 0.55)
out = {'sill': [], 'dlo': []}
for y in np.arange(-2.25, 2.26, 0.05):
    m = side & (np.abs(P[:, 1] - y) < 0.03)
    if m.sum() < 20: continue
    z, w, a = P[m, 2], white[m], A[m]
    zs = np.arange(0.05, 1.35, 0.01)
    frac = np.array([(a[(np.abs(z - zz) < 0.02) & w].sum() / max(a[np.abs(z - zz) < 0.02].sum(), 1e-9)) if (np.abs(z - zz) < 0.02).any() else np.nan for zz in zs])
    # lowest z where it is mostly white (from below)
    ok = np.where(frac > 0.6)[0]
    if len(ok):
        lo = zs[ok[0]]; hi = zs[ok[-1]]
        out['sill'].append((round(float(y), 3), round(float(lo), 3)))
        out['dlo'].append((round(float(y), 3), round(float(hi), 3)))
for k, v in out.items(): print(k, v)
json.dump(out, open('fit/paint.json', 'w'))
