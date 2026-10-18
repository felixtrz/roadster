"""Physics-based thruster firing for the Roadster flip and descent.

Evidence (artifacts/thruster-study/, frames sampled every 1/30 s from the broadcast, its close
replay angle and Tesla's overhead edit):
  * The car leaves the overhang lip upside down and ROLLS about its long axis to wheels-down; its
    heading never changes (overhead edit d001-d033, replay r101-r146).
  * There are no side thrusters. Four corner nozzles point down (car frame) and are canted outward,
    so from above the plumes fan out in an X (overhead d033-d051).
  * The roll is started by firing the nozzles on ONE side only: upside down they point at the sky,
    so that side is pushed toward the ground. The opposite side then fires to stop the roll
    (overhead d033-d041, the long plume on the other side). Then all four fire together to arrest
    the fall and hover into the vapour cloud.
  * Broadcast timing: lip about 8.25 s, rolled 90 deg about 8.75 s, upright about 9.45 s.
  * Two side thrusters at the front bumper corners fire straight out sideways, alternately, in short
    bang-bang pulses through the flip and the descent (close replay 92.6-97.1 s, main angle
    f0010-f0095, overhead o0072-o0090; Tesla presentation: "attitude control thrusters"; press: two
    front nozzles for yaw). The floor nozzles cannot yaw the car (their thrust lines are parallel to
    the yaw axis), so heading is the side pair's job.

Model: rigid car, m = 1900 kg, box inertia (4.6 x 2.0 x 1.2 m). The roll is a constant-torque
bang-bang manoeuvre over [8.25, 9.45] s. For every 1/60 s sample the required body wrench (force
from the track's translational acceleration, torque from I*alpha + w x I*w) is allocated to the
four nozzles by bounded least squares (thrust >= 0, <= 15 kN each). Output: src/data/thrusters.json
(car quaternion override for the air phase and normalised thrust per nozzle).

    python3 tools/thrusters/solve_thrusters.py
"""
import itertools
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = json.load(open(os.path.join(ROOT, 'references/roadster/reconstruction/reconstruction.json')))
OUT = os.path.join(ROOT, 'src/data/thrusters.json')

M = 1900.0
L, W, H = 4.6, 2.0, 1.2
I = np.diag([M * (W * W + H * H) / 12, M * (L * L + W * W) / 12, M * (L * L + H * H) / 12])  # x roll, y yaw, z pitch
G = np.array([0.0, -9.81, 0.0])
TMAX = 15000.0
CG = np.array([0.0, 0.45, 0.0])
# nozzle order matches DEFAULT_NOZZLES: front-left, front-right, rear-left, rear-right (car +X forward, +Z right)
NOZZLES = np.array([[1.05, 0.14, -0.55], [1.05, 0.14, 0.55], [-1.05, 0.14, -0.55], [-1.05, 0.14, 0.55]])   # under the floor, inboard of the wheels
CANT_LAT, CANT_LON = 0.0, 0.0   # nozzles perpendicular to the floor pan (owner's call; B09/R05 show parallel columns)
EXHAUST = np.array([[np.sign(p[0]) * math.tan(CANT_LON), -1.0, np.sign(p[2]) * math.tan(CANT_LAT)] for p in NOZZLES])
EXHAUST /= np.linalg.norm(EXHAUST, axis=1, keepdims=True)
THRUST_DIR = -EXHAUST                       # force on the car per newton of thrust (car frame)
ARM = NOZZLES - CG
WRENCH = np.vstack([THRUST_DIR.T, np.cross(ARM, THRUST_DIR).T])   # 6 x 4

# Side (yaw) thrusters at the front bumper corners, firing straight out of the side panels.
SIDE_NOZZLES = np.array([[2.04, 0.40, -1.02], [2.04, 0.40, 1.02]])          # front-left, front-right
SIDE_EXHAUST = np.array([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]])
SIDE_TMAX = 1500.0           # footage-consistent range 1.5-4 kN (low confidence); the low end keeps heading within a few degrees
# Pulses read from the footage (main-clip seconds; nozzle 0 = FL, 1 = FR); full thrust, 40 ms valve ramps.
SIDE_PULSES = [(0, 8.21, 8.48), (1, 8.51, 8.64), (1, 9.09, 9.51), (0, 9.53, 9.88), (1, 9.89, 10.38), (0, 10.40, 10.84), (1, 10.84, 11.00)]
YAW_WINDOW = (8.20, 11.50)    # leaves the lip with a residual yaw rate; heading back to zero by touchdown

T0, T1 = 8.25, 9.45           # roll burn window (broadcast timing)
AIR = (8.0, 11.55)            # release to touchdown
LAND = 11.533


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


def qaxis(axis, ang):
    s = math.sin(ang / 2)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, math.cos(ang / 2)])


def qrot(q, v):
    u = q[:3]; w = q[3]
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def qinv(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])


def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0: b, d = -b, -d
    if d > 0.9995:
        q = a + t * (b - a); return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / math.sin(th)


def roll_angle(t):
    """Remaining roll (rad) from upside down (pi) to upright (0): constant +torque then -torque."""
    if t <= T0: return math.pi
    if t >= T1: return 0.0
    T = T1 - T0
    alpha = 4 * math.pi / (T * T)
    u = t - T0
    if u < T / 2: return math.pi - 0.5 * alpha * u * u
    v = T - u
    return 0.5 * alpha * v * v


samples = DATA['samples']
ts = np.array([s['time'] for s in samples])
pos = np.array([s['position'] for s in samples])
quat = np.array([s['quaternion'] for s in samples])
# attitude override: the car's heading and pitch come from the track at the endpoints; the roll is
# the bang-bang profile about the car's own long axis
q_inv_end = quat[np.argmin(np.abs(ts - 8.0))]          # upside down at release (track)
q_up_end = quat[np.argmin(np.abs(ts - 10.0))]          # wheels down (track)
q_up_heading = q_up_end
roll_sign = 1.0
qs = quat.copy()
for i, t in enumerate(ts):
    if AIR[0] <= t <= 10.2:
        phi = roll_angle(t)
        pitch_blend = np.clip((t - 8.0) / (10.0 - 8.0), 0, 1)
        base = slerp(q_inv_end, q_up_heading, 0.0)          # heading/pitch frame of the departing car
        # build from the upright frame: rotate by phi about the car's forward axis
        up_frame = slerp(qmul(q_inv_end, qaxis((1, 0, 0), math.pi)), q_up_heading, pitch_blend)
        qs[i] = qmul(up_frame, qaxis((1, 0, 0), roll_sign * phi))
for i in range(1, len(qs)):
    if np.dot(qs[i], qs[i - 1]) < 0: qs[i] = -qs[i]


dt = ts[1] - ts[0]
side = np.zeros((len(ts), 2))
for k, a, b in SIDE_PULSES:
    ramp = np.clip((ts - a) / 0.04, 0, 1) * np.clip((b - ts) / 0.04, 0, 1)
    side[:, k] = np.maximum(side[:, k], ramp * SIDE_TMAX)
SIDE_ARM = SIDE_NOZZLES - CG
SIDE_DIR = -SIDE_EXHAUST                                   # force on the car per newton
side_tau = np.array([np.cross(SIDE_ARM[k], SIDE_DIR[k]) for k in range(2)])   # torque per newton (car frame)
yaw_torque = side @ side_tau[:, 1]                          # about the car's up axis
# Yaw response: I_yaw * psi'' = side torque + a steady disturbance (floor-nozzle misalignment, flow near
# the ground), with the residual yaw rate the car carries off the lip. Disturbance and initial rate are
# solved so heading and yaw rate are back to zero at touchdown: the pulses are the controller's work.
w0, w1 = YAW_WINDOW
win = (ts >= w0) & (ts <= w1)
tw = ts[win] - w0
S = np.cumsum(yaw_torque[win]) * dt                         # integral of side torque
SS = np.cumsum(S) * dt
Iy, D = I[1, 1], tw[-1]
A = np.array([[1.0, D / Iy], [D, D * D / (2 * Iy)]])
rhs = -np.array([S[-1] / Iy, SS[-1] / Iy])
omega0, tau_d = np.linalg.solve(A, rhs)
psi = np.zeros(len(ts))
psi[win] = omega0 * tw + (SS + tau_d * tw * tw / 2) / Iy
for i in np.where(win)[0]:
    qs[i] = qmul(qs[i], qaxis((0, 1, 0), psi[i]))
for i in range(1, len(qs)):
    if np.dot(qs[i], qs[i - 1]) < 0: qs[i] = -qs[i]
print('yaw: residual rate off the lip %.1f deg/s, disturbance %.0f N m, heading within %.1f..%.1f deg'
      % (math.degrees(omega0), tau_d, math.degrees(psi.min()), math.degrees(psi.max())))


def gsmooth(a, sigma):
    r = int(3 * sigma); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, [(r, r)] + [(0, 0)] * (a.ndim - 1), mode='edge')
    return np.stack([np.convolve(pad[:, j], k, 'valid') for j in range(a.shape[1])], 1)


dt = ts[1] - ts[0]
p_s = gsmooth(pos, 4)
acc = np.gradient(np.gradient(p_s, dt, axis=0), dt, axis=0)
acc = gsmooth(acc, 3)
# body rates from the attitude
omega = np.zeros((len(ts), 3))
for i in range(1, len(ts) - 1):
    dq = (qs[i + 1] - qs[i - 1]) / (2 * dt)
    omega[i] = 2 * qmul(qinv(qs[i]), dq)[:3]
omega = gsmooth(omega, 2)
alpha = gsmooth(np.gradient(omega, dt, axis=0), 2)


def allocate(w, weights):
    """Bounded least squares over 4 nozzles by active-set enumeration (exact for 4 variables)."""
    A = WRENCH * weights[:, None]
    b = w * weights
    best, bestT = None, np.zeros(4)
    for mask in itertools.product([0, 1], repeat=4):
        idx = [k for k in range(4) if mask[k]]
        T = np.zeros(4)
        if idx:
            sol, *_ = np.linalg.lstsq(A[:, idx], b, rcond=None)
            T[idx] = np.clip(sol, 0, TMAX)
        r = float(np.sum((A @ T - b) ** 2)) + 1e-12 * float(np.sum(T))
        if best is None or r < best:
            best, bestT = r, T
    return bestT


thrust = np.zeros((len(ts), 4))
report = []
for i, t in enumerate(ts):
    if not (AIR[0] <= t <= AIR[1]):
        continue
    R = np.array([qrot(qs[i], e) for e in np.eye(3)]).T          # car -> world
    F_world = M * (acc[i] - G)
    F_body = R.T @ F_world
    tau = I @ alpha[i] + np.cross(omega[i], I @ omega[i])
    # the side pair's force and torque are prescribed (the pulses); the floor nozzles carry the rest
    F_body = F_body - side[i] @ SIDE_DIR
    tau = tau - side[i] @ side_tau
    # the roll torque is what the footage shows; force matters most once the car is upright
    upright = max(0.0, float(qrot(qs[i], np.array([0, 1, 0]))[1]))
    wF = np.array([0.3, 1.0, 0.3]) * (0.15 + upright) / (M * 9.81)
    wT = np.array([1.0, 0.4, 0.4]) / 6000.0
    T = allocate(np.r_[F_body, tau], np.r_[wF, wT])
    thrust[i] = T
    if abs(t * 10 - round(t * 10)) < 1e-6:
        report.append((round(t, 2), np.round(T / 1000, 1).tolist(), round(math.degrees(roll_angle(t)) if t < 10.2 else 0, 0),
                       np.round(F_body / 1000, 1).tolist(), np.round(tau / 1000, 1).tolist()))
# hover floor: the fitted track is smoothed by a weak-acceleration prior, so between the braking
# burn and the touchdown burn it implies brief free fall (thrust 0). The footage shows the four
# plumes running continuously into the cloud, i.e. at least a partial hover; keep 40 % thrust there.
hover = (ts >= 9.6) & (ts <= 11.45)
thrust[hover] = np.maximum(thrust[hover], 0.40 * TMAX)
# valve response (~40 ms) and a little hysteresis so plumes do not flicker
thrust = gsmooth(thrust, 2.4)
thrust[thrust < 250] = 0
for r in report: print(r)
out = {
    'model': 'bang-bang roll about the long axis over [8.25, 9.45] s; four floor-perpendicular corner nozzles by bounded least-squares allocation; two front side (yaw) nozzles pulsing as in the footage, with the yaw response integrated into the attitude',
    'mass_kg': M, 'inertia_kgm2': np.diag(I).round(1).tolist(), 'max_thrust_N': TMAX,
    'nozzles': NOZZLES.tolist(), 'exhaust_dirs': EXHAUST.round(5).tolist(),
    'dt': dt, 't0': float(ts[0]),
    'quaternions': [[round(float(v), 6) for v in q] for q in qs],
    'thrust': [[round(float(v) / TMAX, 4) for v in T] for T in thrust],
    'side_nozzles': SIDE_NOZZLES.tolist(), 'side_exhaust_dirs': SIDE_EXHAUST.tolist(), 'side_max_thrust_N': SIDE_TMAX,
    'side_thrust': [[round(float(v) / SIDE_TMAX, 4) for v in T] for T in side],
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w'))
print('wrote', OUT, len(ts), 'samples')
