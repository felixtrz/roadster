"""Annotated computer-vision segment for the film: the broadcast's main ramp camera with the
reconstruction drawn over it, frame by frame, at real time.

Per frame, the camera is registered to the reconstruction's canonical frame (SIFT + RANSAC homography
against main frame 14, the same method as tools/reconstruction/reconstruct.py). Through that
registration it draws: the two-view ramp fit (rails and ribs), the solved car path, the car's posed
bounding box and body axes (attitude from the physics solve in src/data/thrusters.json, so the box
rolls through the flip), the firing nozzles, a roll dial and live per-nozzle thrust, the observed car
centres the solve used, and the tracked ramp features.

Needs the local broadcast excerpt (references/roadster/media/ramp-main_0708-0726.mp4, not distributed;
see NOTICE.md) and opencv-python-headless, scipy, numpy, Pillow.

    python3 tools/film/annotate_cv.py [t0] [t1]   -> artifacts/film/cv/f00000.png ...
"""
import json
import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from title_cards import font as title_font  # noqa: E402  (shared portable font lookup)

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / 'references/roadster/reconstruction'
CLIP = ROOT / 'references/roadster/media/ramp-main_0708-0726.mp4'
OUT = ROOT / 'artifacts/film/cv'
T0 = float(sys.argv[1]) if len(sys.argv) > 1 else 5.6
T1 = float(sys.argv[2]) if len(sys.argv) > 2 else 11.4

geo = json.loads((REC / 'geometry-fit.json').read_text())
rec = json.loads((REC / 'reconstruction.json').read_text())
obs = json.loads((REC / 'observations.json').read_text())
CAM = np.array(geo['main_camera'])
CAR = rec['car']
THR = json.loads((ROOT / 'src/data/thrusters.json').read_text())
TQ = np.array(THR['quaternions'])
TF = np.array(THR['thrust'])
NOZ = np.array(THR['nozzles'])
EXH = np.array(THR['exhaust_dirs'])


def project(p):
    q = Rotation.from_rotvec(CAM[:3]).apply(p) + CAM[3:6]
    return q[:, :2] / q[:, 2, None] * math.exp(CAM[6]) + np.array([960.0, 540.0])


def to_frame(uv, Hinv):
    pts = cv2.perspectiveTransform(np.asarray(uv, np.float32)[None], Hinv)[0]
    return pts


# ---------------------------------------------------------------- reconstruction geometry
cl = np.array(rec['ramp']['centerline'])
half = rec['ramp']['width'] / 2
rails = [project(cl + np.array([0, 0, s * half])) for s in (-1, 1)]
ribs = [(project(np.array([cl[i] + [0, 0, -half]]))[0], project(np.array([cl[i] + [0, 0, half]]))[0]) for i in range(0, len(cl), 12)]
ST = np.array([s['time'] for s in rec['samples']])
SP = np.array([s['position'] for s in rec['samples']])
SQ = np.array([s['quaternion'] for s in rec['samples']])
up = np.array(CAR['bodyReferenceOffset'])
body = np.array([p + Rotation.from_quat(q).apply(up) for p, q in zip(SP, SQ)])
path_uv = project(body)
L, W, Hh = CAR['length'] / 2, CAR['width'] / 2, CAR['height']
BOX = np.array([[x, y, z] for x in (-L, L) for y in (0, Hh) for z in (-W, W)])
EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count('1') == 1]
tracks = obs['carTracks']


def pose_at(t):
    """Position from the reconstruction; attitude and thrust from the physics solve (the app's own)."""
    i = int(np.clip(np.searchsorted(ST, t), 1, len(ST) - 1))
    u = (t - ST[i - 1]) / (ST[i] - ST[i - 1])
    p = SP[i - 1] * (1 - u) + SP[i] * u
    k = int(np.clip((t - THR['t0']) / THR['dt'], 0, len(TQ) - 2))
    w = np.clip((t - THR['t0']) / THR['dt'] - k, 0, 1)
    qa, qb = TQ[k], TQ[k + 1] * (1 if np.dot(TQ[k], TQ[k + 1]) >= 0 else -1)
    q = qa * (1 - w) + qb * w
    return p, Rotation.from_quat(q / np.linalg.norm(q)), TF[k] * (1 - w) + TF[k + 1] * w


def signed_roll(R):
    """Roll about the car's long axis away from wheels-down, in degrees (0 = upright, +-180 = inverted)."""
    fwd, up = R.apply([1, 0, 0]), R.apply([0, 1, 0])
    ref = np.array([0, 1.0, 0]) - fwd * fwd[1]
    if np.linalg.norm(ref) < 1e-6:
        return 0.0
    ref /= np.linalg.norm(ref)
    return math.degrees(math.atan2(np.dot(np.cross(ref, up), fwd), np.dot(ref, up)))


# ---------------------------------------------------------------- registration
def decode():
    cap = cv2.VideoCapture(str(CLIP))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames, base, i = {}, None, 0
    f0, f1, fb = int(T0 * fps), int(T1 * fps), 14 * 15
    while True:
        ok, im = cap.read()
        if not ok or i > max(f1, fb):
            break
        if f0 <= i < f1:
            frames[i] = im
        if i == fb:
            base = im
        i += 1
    cap.release()
    return frames, base, fps


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames, base, fps = decode()
    sift = cv2.SIFT_create(nfeatures=2400)
    mask = np.zeros(base.shape[:2], np.uint8)
    mask[45:900, 790:1170] = 255
    mask[170:330, 900:1060] = 0
    kb, db = sift.detectAndCompute(base, mask)
    matcher = cv2.BFMatcher()
    Hs, inl = {}, {}
    prev = None
    for i in sorted(frames):
        im = frames[i]
        k, d = sift.detectAndCompute(im, None)
        good = [a for a, b in matcher.knnMatch(d, db, k=2) if a.distance < 0.72 * b.distance]
        H, ok = None, None
        if len(good) >= 12:
            src = np.float32([k[m.queryIdx].pt for m in good])
            dst = np.float32([kb[m.trainIdx].pt for m in good])
            H, ok = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        n_in = int(ok.sum()) if ok is not None else 0
        if H is None or n_in < 25:
            # chain from the previous frame when the ramp texture is out of view
            pk, pd, pH = prev
            pairs = [a for a, b in matcher.knnMatch(d, pd, k=2) if a.distance < 0.72 * b.distance]
            src = np.float32([k[m.queryIdx].pt for m in pairs])
            dst = np.float32([pk[m.trainIdx].pt for m in pairs])
            Hp, okp = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
            H = pH @ Hp
            src = src[okp.ravel() > 0]
            print(f'frame {i}: chained ({n_in} direct inliers)')
        else:
            src = src[ok.ravel() > 0]
        Hs[i], inl[i] = H, src
        prev = (k, d, H)
    # light temporal smoothing of the registration (normalised homographies)
    keys = sorted(Hs)
    Hn = np.array([Hs[i] / Hs[i][2, 2] for i in keys])
    Hsm = Hn.copy()
    for j in range(len(keys)):
        a, b = max(0, j - 2), min(len(keys), j + 3)
        w = np.array([1, 2, 3, 2, 1][2 - (j - a): 2 + (b - j)], float)
        Hsm[j] = np.tensordot(w / w.sum(), Hn[a:b], axes=1)
    font_b, font, font_s = title_font('bold', 30), title_font('regular', 22), title_font('regular', 18)
    CYAN, AMBER, MAG, GREEN, WHITE = (255, 225, 60), (40, 190, 255), (255, 90, 230), (120, 255, 120), (255, 255, 255)
    rail_rms = geo['rail_reprojection'][0]['rms_px']
    car_rms = rec['validation']['carCenterRmsPx']
    for n, i in enumerate(keys):
        t = i / fps
        Hinv = np.linalg.inv(Hsm[n])
        im = (frames[i].astype(np.float32) * 0.82).astype(np.uint8)
        over = np.zeros_like(im)
        # tracked ramp features
        for x, y in inl[i][:: max(1, len(inl[i]) // 90)]:
            cv2.drawMarker(over, (int(x), int(y)), GREEN, cv2.MARKER_TILTED_CROSS, 7, 1, cv2.LINE_AA)
        # ramp fit
        for r in rails:
            cv2.polylines(over, [to_frame(r, Hinv).astype(np.int32)], False, CYAN, 2, cv2.LINE_AA)
        for a, b in ribs:
            ab = to_frame(np.array([a, b]), Hinv).astype(np.int32)
            cv2.line(over, tuple(ab[0]), tuple(ab[1]), CYAN, 1, cv2.LINE_AA)
        # solved path: past solid, future dotted
        puv = to_frame(path_uv, Hinv)
        past = puv[(ST <= t) & (ST >= 1.5)].astype(np.int32)
        if len(past) > 1:
            cv2.polylines(over, [past], False, AMBER, 2, cv2.LINE_AA)
        fut = puv[(ST > t) & (ST < 12.4)]
        for p in fut[::4]:
            cv2.circle(over, (int(p[0]), int(p[1])), 2, AMBER, -1, cv2.LINE_AA)
        # observed car centres used by the solve
        for tr in tracks:
            if tr['time'] <= t + 1e-6:
                c = to_frame(np.array([tr['observedCanonicalPx']]), Hinv)[0]
                cv2.circle(over, (int(c[0]), int(c[1])), 9, MAG, 2, cv2.LINE_AA)
        # posed car box, body axes and firing nozzles (physics-solved attitude: it rolls through the flip)
        p, R, thrust = pose_at(t)
        corners = to_frame(project(p + R.apply(BOX)), Hinv).astype(np.int32)
        for a, b in EDGES:
            cv2.line(over, tuple(corners[a]), tuple(corners[b]), WHITE, 2, cv2.LINE_AA)
        roof = to_frame(project(p + R.apply(np.array([[L, Hh, -W], [L, Hh, W], [-L, Hh, W], [-L, Hh, -W]]))), Hinv).astype(np.int32)
        cv2.fillPoly(over, [roof], (70, 70, 70), cv2.LINE_AA)                    # shaded roof face shows which way is up
        c = p + R.apply([0, Hh / 2, 0])
        axes = to_frame(project(np.array([c, c + R.apply([3.2, 0, 0]), c + R.apply([0, 3.2, 0])])), Hinv)
        cv2.arrowedLine(over, tuple(axes[0].astype(int)), tuple(axes[1].astype(int)), AMBER, 2, cv2.LINE_AA, tipLength=0.18)
        cv2.arrowedLine(over, tuple(axes[0].astype(int)), tuple(axes[2].astype(int)), CYAN, 3, cv2.LINE_AA, tipLength=0.18)
        for k in range(4):
            if thrust[k] > 0.04:
                a0 = p + R.apply(NOZ[k])
                a1 = a0 + R.apply(EXH[k]) * (0.8 + 5.5 * thrust[k])
                seg = to_frame(project(np.array([a0, a1])), Hinv).astype(int)
                cv2.line(over, tuple(seg[0]), tuple(seg[1]), (255, 255, 200), 5, cv2.LINE_AA)
                cv2.line(over, tuple(seg[0]), tuple(seg[1]), (255, 210, 120), 2, cv2.LINE_AA)
        im = cv2.add(im, over)
        img = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).convert('RGBA')
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((36, 34, 760, 150), 14, fill=(6, 8, 12, 190))
        d.text((60, 48), 'COMPUTER-VISION PASS', font=font_b, fill=(255, 255, 255))
        d.text((60, 90), 'Broadcast camera registered frame by frame (SIFT + RANSAC)', font=font, fill=(215, 222, 230))
        d.text((60, 118), 'Ramp and car path solved from the footage, reprojected here', font=font_s, fill=(170, 180, 190))
        roll = signed_roll(R)
        rows = [((60, 225, 255), f'Ramp fit, two views  ·  {rail_rms:.1f} px RMS'),
                ((255, 190, 40), f'Solved car path  ·  car-centre {car_rms:.1f} px RMS'),
                ((230, 90, 255), 'Observed car centres'),
                ((120, 255, 120), f'Tracked ramp features  ·  {len(inl[i])}'),
                ((255, 255, 255), f'Posed car, solved attitude  ·  broadcast t {t:5.2f} s'),
                ((120, 210, 255), 'Nozzles firing (physics solve)')]
        y = 1080 - 40 - 34 * len(rows)
        d.rounded_rectangle((36, y - 18, 640, 1080 - 34), 14, fill=(6, 8, 12, 215))
        for col, txt in rows:
            d.rounded_rectangle((58, y + 6, 76, y + 18), 3, fill=col)
            d.text((90, y), txt, font=font_s, fill=(235, 238, 242))
            y += 34
        d.text((1880, 60), 'Footage: Tesla, Roadster Event (Oct 2026)', font=font_s, fill=(200, 205, 210, 230), anchor='rs')
        # roll dial and per-nozzle thrust, top right
        d.rounded_rectangle((1560, 84, 1884, 330), 14, fill=(6, 8, 12, 200))
        cx, cy, rr = 1650, 200, 62
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(120, 130, 140, 255), width=2)
        d.line((cx - rr - 6, cy, cx - rr + 8, cy), fill=(120, 130, 140, 255), width=2)
        d.line((cx + rr - 8, cy, cx + rr + 6, cy), fill=(120, 130, 140, 255), width=2)
        ang = math.radians(roll)
        def rot(x, y):
            return (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))
        cabin = [rot(-36, -6), rot(36, -6), rot(30, -20), rot(-30, -20)]          # car seen from behind
        d.polygon(cabin, fill=(240, 244, 248, 255))
        d.polygon([rot(-38, -6), rot(38, -6), rot(38, 4), rot(-38, 4)], fill=(150, 156, 164, 255))
        for wx in (-28, 28):
            d.polygon([rot(wx - 6, 4), rot(wx + 6, 4), rot(wx + 6, 14), rot(wx - 6, 14)], fill=(30, 32, 36, 255))
        d.text((cx, cy - rr - 12), 'ROLL', font=font_s, fill=(170, 180, 190, 255), anchor='ms')
        d.text((cx, cy + rr + 26), f'{abs(roll):5.1f}°', font=font, fill=(255, 255, 255, 255), anchor='ms')
        names = ['FL', 'FR', 'RL', 'RR']
        for k in range(4):
            x0 = 1748 + k * 32
            d.rectangle((x0, 120, x0 + 18, 270), outline=(90, 100, 110, 255), width=1)
            h = int(148 * min(1.0, thrust[k]))
            if h > 0:
                d.rectangle((x0 + 1, 269 - h, x0 + 17, 269), fill=(120, 210, 255, 255))
            d.text((x0 + 9, 292), names[k], font=font_s, fill=(170, 180, 190, 255), anchor='ms')
        d.text((1812, 112), 'THRUST', font=font_s, fill=(170, 180, 190, 255), anchor='ms')
        Image.alpha_composite(img, layer).convert('RGB').save(OUT / f'f{n:05d}.png')
    print('wrote', len(keys), 'frames to', OUT)


if __name__ == '__main__':
    main()
