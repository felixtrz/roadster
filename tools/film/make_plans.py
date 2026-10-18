"""Shot plans for the Roadster film (30 fps).

Everything plays at real time (no slow motion). 2D: the title card, then the whole run in the
browser app's Show camera. XR: a shorter first-person headset shot driven through the IWER
emulator: standing just outside the lane down-range of the ramp, watching the flip and descent with
lagging head motion while taking a few steps in, then the car drives straight at the viewer and
passes about 3 m in front.

    python3 tools/film/make_plans.py   -> tools/film/out/plan-2d.json, plan-xr.json
"""
import json
import math
import os

import numpy as np

FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.dirname(os.path.dirname(HERE))
data = json.load(open(os.path.join(ROOT, 'references/roadster/reconstruction/reconstruction.json')))
OFFSET = np.array([12.0, 0.0, -34.0])
ST = np.array([s['time'] for s in data['samples']])
SP = np.array([s['position'] for s in data['samples']])


def car(t):
    return np.array([np.interp(t, ST, SP[:, k]) for k in range(3)]) + OFFSET


def realtime(t0, t1, hold=0.0):
    """Replay time per frame at 1x speed, optionally holding t0 for `hold` seconds first."""
    n_hold = int(round(hold * FPS))
    n = int(round((t1 - t0) * FPS))
    return np.r_[np.full(n_hold, t0), t0 + (np.arange(n) + 0.5) / FPS]


INTRO = 2.6


def smoother(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def damped(series, omega):
    """Critically damped follow of a per-frame series (a smooth, lag-limited camera operator)."""
    out = np.zeros_like(series)
    out[0] = series[0]
    vel = np.zeros(series.shape[1])
    dt = 1 / FPS
    for i in range(1, len(series)):
        acc = omega * omega * (series[i] - out[i - 1]) - 2 * omega * vel
        vel = vel + acc * dt
        out[i] = out[i - 1] + vel * dt
    return out


ORBIT = 7.5          # video seconds circling the parked car before the run starts
RUN_END = 14.0       # replay time where the 2D part ends (car driving away)
TRIPOD = np.array([-38.0, 3.2, 2.0])   # fixed vantage on the key-light side of the lane, ~40-60 m off


def plan_2d():
    """One continuous shot, no cuts: an eased orbit around the parked car, a crane out to a tripod,
    then the whole run from that tripod with a smooth pan and a gentle zoom."""
    n = int(round((ORBIT + RUN_END) * FPS))
    v = (np.arange(n) + 0.5) / FPS
    t = np.clip(v - ORBIT, 0.0, RUN_END)
    c0 = car(0.0)
    # orbit: front three-quarter -> right side -> rear three-quarter, rising, slowly widening
    u = smoother(v / 9.5)
    az_deg = 22 + 150 * u
    az = np.radians(az_deg)
    # stay inside the lane (its LED curtain is at z = -26) while passing the car's side; widen behind it
    rad = 5.2 + 0.3 * u + 2.2 * smoother((az_deg - 128) / 40)
    hgt = 0.8 + 1.0 * u
    orbit_pos = np.stack([c0[0] + rad * np.cos(az), hgt, c0[2] + rad * np.sin(az)], 1)
    orbit_tgt = np.stack([c0[0] + 0.6 * np.cos(az * 0.0) * (1 - u) - 0.4 * u, 0.55 + 0.25 * u, np.full(n, c0[2])], 1)
    # run: pan with a smoothed follow of the car, framed slightly toward the scene centre
    omega = 3.2
    ahead = np.array([car(tt + 2 / omega) for tt in t])        # look-ahead equal to the follow's lag
    follow = damped(ahead + np.array([0, 0.6, 0]), omega)
    centre = np.array([-8.0, 9.0, -34.0])
    bias = np.interp(t, [0, 10.0, 11.6], [0.18, 0.18, 0.0])[:, None]
    run_tgt = (1 - bias) * follow + bias * centre
    # crane from the orbit to the tripod, blended continuously (no stop at the join)
    w = smoother((v - 5.8) / 4.6)[:, None]
    pos = orbit_pos * (1 - w) + TRIPOD[None] * w
    tgt = orbit_tgt * (1 - w) + run_tgt * w
    # lens: the visible height at the car's distance eases from the whole ramp to a tighter flip/landing
    dist = np.linalg.norm(follow - TRIPOD[None], axis=1)
    H = np.interp(t, [0, 2.4, 4.2, 6.0, 7.6, 8.3, 9.6, 11.0, 12.2, 14.0], [13, 15, 26, 30, 25, 17, 16, 15, 12.5, 11])
    run_fov = np.degrees(2 * np.arctan(H / (2 * dist)))
    run_fov = damped(run_fov[:, None], 2.0)[:, 0]
    fov = 34 * (1 - w[:, 0]) + run_fov * w[:, 0]
    # the parked car sits under the site floods: expose down for the close orbit, back to normal on the crane
    exposure = 0.55 + 0.45 * w[:, 0]
    frames = []
    for i in range(n):
        frames.append({'t': round(float(t[i]), 4), 'view': 0, 'intro': False,
                       'camera': {'position': np.round(pos[i], 4).tolist(), 'target': np.round(tgt[i], 4).tolist(), 'fov': round(float(fov[i]), 3),
                                  'exposure': round(float(exposure[i]), 3)},
                       'shellOpacity': round(float(smoother((v[i] - ORBIT - 0.6) / 1.2)), 3)})
    return {'mode': '2d', 'width': 1920, 'height': 1080, 'fps': FPS, 'frames': frames}


def quat_look(fwd, roll=0.0):
    """Quaternion (x, y, z, w) of a camera looking along fwd (three.js: camera looks down -Z, +Y up)."""
    f = fwd / np.linalg.norm(fwd)
    yaw = math.atan2(-f[0], -f[2])
    pitch = math.asin(np.clip(f[1], -1, 1))
    def q_axis(ax, ang):
        s = math.sin(ang / 2)
        return np.array([ax[0] * s, ax[1] * s, ax[2] * s, math.cos(ang / 2)])
    def mul(a, b):
        x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
        return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                         w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])
    q = mul(q_axis((0, 1, 0), yaw), q_axis((1, 0, 0), pitch))
    return mul(q, q_axis((0, 0, 1), roll))


def rotate(q, v):
    x, y, z, w = q
    u = np.array([x, y, z])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def plan_xr():
    t = realtime(8.0, 13.7)
    n = len(t)
    tv = np.arange(n) / FPS
    # stand just outside the lane edge, 66 m down the lane from the ramp, and step in toward it: the
    # car lands, drives straight at the viewer and passes about 3 m in front at t ~ 13
    p0 = np.array([-68.5, 0.0, -25.2])
    p1 = np.array([-66.0, 0.0, -29.4])
    walk_end = 3.6
    s = np.clip(tv / walk_end, 0, 1)
    s = s * s * (3 - 2 * s)
    speed = np.gradient(s) * FPS * np.linalg.norm(p1 - p0)
    base = p0[None] + s[:, None] * (p1 - p0)[None]
    phase = np.cumsum(speed / FPS) / 0.72 * math.pi          # one step per 0.72 m
    walking = np.clip(speed / 1.0, 0, 1)
    rng = np.random.default_rng(7)
    def noise(freq, amp, seed):
        r = np.random.default_rng(seed)
        ph = r.uniform(0, 2 * math.pi, 3)
        return amp * (0.6 * np.sin(2 * math.pi * freq * tv + ph[0]) + 0.3 * np.sin(2 * math.pi * freq * 2.3 * tv + ph[1])
                      + 0.1 * np.sin(2 * math.pi * freq * 5.1 * tv + ph[2]))
    head = base.copy()
    head[:, 1] = 1.66 + walking * 0.028 * np.abs(np.sin(phase)) - walking * 0.014 + noise(0.23, 0.006, 1)
    side = np.cross((p1 - p0) / np.linalg.norm(p1 - p0), [0, 1, 0])
    head += side[None] * (walking * 0.018 * np.sin(phase / 2 * 2) + noise(0.17, 0.008, 2))[:, None]
    # look target: the car with a human lag (critically damped follow) and a little anticipation
    target = np.array([car(tt) + np.array([0, 0.6, 0]) for tt in t])
    lead = np.array([car(tt + 0.25) + np.array([0, 0.6, 0]) for tt in t])
    want = 0.6 * target + 0.4 * lead
    look = np.zeros_like(want)
    look[0] = want[0]
    vel = np.zeros(3)
    k = 9.0
    for i in range(1, n):
        dt = 1 / FPS
        acc = k * k * (want[i] - look[i - 1]) - 2 * k * vel
        vel = vel + acc * dt
        look[i] = look[i - 1] + vel * dt
    frames = []
    for i in range(n):
        d = look[i] - head[i]
        d = d + np.array([noise(0.31, 0.12, 3)[i], noise(0.27, 0.07, 4)[i], 0]) * 0.08 * np.linalg.norm(d)
        roll = walking[i] * 0.012 * math.sin(phase[i]) + noise(0.2, 0.01, 5)[i]
        q = quat_look(d, roll)
        # controllers held loosely at the waist, swinging with the gait
        sw = walking[i] * math.sin(phase[i])
        lpos = head[i] + rotate(q, np.array([-0.21, -0.48 + 0.01 * sw, -0.30 - 0.04 * sw]))
        rpos = head[i] + rotate(q, np.array([0.21, -0.48 - 0.01 * sw, -0.30 + 0.04 * sw]))
        tilt = quat_look(rotate(q, np.array([0, -0.55, -1.0])), 0.0)
        frames.append({'t': round(float(t[i]), 4), 'head': [*np.round(head[i], 4).tolist(), *np.round(q, 6).tolist()],
                       'left': [*np.round(lpos, 4).tolist(), *np.round(tilt, 6).tolist()],
                       'right': [*np.round(rpos, 4).tolist(), *np.round(tilt, 6).tolist()]})
    return {'mode': 'xr', 'width': 1920, 'height': 1080, 'fps': FPS, 'frames': frames}


if __name__ == '__main__':
    for name, plan in (('plan-2d.json', plan_2d()), ('plan-xr.json', plan_xr())):
        json.dump(plan, open(os.path.join(OUT, name), 'w'))
        ts = [f['t'] for f in plan['frames']]
        print(name, len(plan['frames']), 'frames', round(len(ts) / FPS, 2), 's video, replay', ts[0], '->', ts[-1])
