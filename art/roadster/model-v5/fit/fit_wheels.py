"""Wheel centres/radii from the reference tyre faces (circle fit about the lateral axis)."""
from lib5 import *
out = {}
for name, yc, sx in (('FL', -1.42, 1), ('FR', -1.42, -1), ('RL', 1.42, 1), ('RR', 1.42, -1)):
    # outer tyre tread: faces whose normal is radial in the y-z plane, |x| > 0.8
    r = np.hypot(P[:, 1] - yc, P[:, 2] - 0.37)
    m = (r < 0.45) & (r > 0.25) & (sx * P[:, 0] > 0.8) & (np.abs(N[:, 0]) < 0.3) & (P[:, 2] > 0.05)
    c, rad = circle_fit(P[m], np.array([1.0, 0, 0]))
    xs = P[m][:, 0] * sx
    # side wall / disc face: faces with normal ~ +-x at outer side
    side = (r < 0.36) & (sx * P[:, 0] > 0.8) & (sx * N[:, 0] > 0.9)
    out[name] = dict(centre=np.round(c, 4).tolist(), radius=round(float(rad), 4), tread_x=[round(float(np.percentile(xs, 3)), 3), round(float(np.percentile(xs, 97)), 3)],
                     face_x=round(float(np.median(P[side][:, 0] * sx)), 3) if side.any() else None, n=int(m.sum()))
    print(name, out[name])
json.dump(out, open('fit/wheels.json', 'w'), indent=1)
