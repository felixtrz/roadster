"""Synthesized soundtrack for the Roadster film, in sync with the replay data (numpy only).

Rebuilds the film's timeline exactly as assemble.sh cuts it (the parts' frame counts, 0.5 s fades
through black, the end card), then, at every audio sample, knows which part is on screen and its
replay time. From that it drives:
  * sound effects: the floor-jet roar and hiss from the solved thrust (src/data/thrusters.json), crisp
    side-thruster bursts panned by nozzle, an electric-motor whine and wind from the car's speed, a hit
    on the cold open and a boom at every touchdown; louder onboard, distant on the broadcast, and by
    the head-to-car distance in VR;
  * an original music bed: a D-minor pad (Dm Bb F C), a sub drone, an eighth-note bass pulse and a
    kick that build into the flip, a riser before it, and a final chord on the end card.

    python3 tools/film/soundtrack.py <out.wav>   (run from anywhere; reads artifacts/film/* frame dirs)
"""
import json
import math
import os
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILM = os.path.join(ROOT, 'artifacts', 'film')
PLANS = os.path.join(ROOT, 'tools', 'film', 'out')
SR, FPS, XF, END = 48000, 30, 0.5, 2.2
OFFSET = np.array([12.0, 0.0, -34.0])
rng = np.random.default_rng(7)

thr = json.load(open(os.path.join(ROOT, 'src', 'data', 'thrusters.json')))
rec = json.load(open(os.path.join(ROOT, 'references', 'roadster', 'reconstruction', 'reconstruction.json')))
ST = np.array([s['time'] for s in rec['samples']])
SP = np.array([s['position'] for s in rec['samples']])
SPEED = np.linalg.norm(np.gradient(SP, ST, axis=0), axis=1)
SPEED = np.convolve(SPEED, np.ones(9) / 9, mode='same')
TT = thr['t0'] + np.arange(len(thr['thrust'])) * thr['dt']
LIFT = np.array(thr['thrust']).mean(axis=1)
SIDE = np.array(thr['side_thrust'])


def frames(name):
    d = os.path.join(FILM, name)
    return len([f for f in os.listdir(d) if f.endswith('.png')]) if os.path.isdir(d) else 0


# ---- timeline: the same parts, order and fades as assemble.sh
parts = []
for name, plan in (('coldopen', 'plan-coldopen.json'), ('2d', 'plan-2d.json'), ('cv', None), ('xr', 'plan-xr.json')):
    n = frames(name)
    if not n:
        continue
    if plan:
        p = json.load(open(os.path.join(PLANS, plan)))
        t = np.array([f['t'] for f in p['frames']][:n])
        head = np.array([f['head'][:3] for f in p['frames']][:n]) if name == 'xr' else None
    else:
        t, head = 5.6 + np.arange(n) / 29.97, None                       # annotate_cv.py's broadcast window
    parts.append({'name': name, 'n': n, 'dur': n / FPS, 't': t, 'head': head})
start = 0.0
for i, p in enumerate(parts):
    p['start'] = start
    start += p['dur'] - (XF if i < len(parts) - 1 else 0)
end_card = start
total = end_card + END
N = int(round(total * SR))
time = np.arange(N) / SR


def part_weight(i):
    """Equal-power crossfade across the fades through black."""
    p = parts[i]
    a, b = p['start'], p['start'] + p['dur']
    w = np.zeros(N)
    inside = (time >= a) & (time < b)
    w[inside] = 1.0
    if i > 0:
        k = inside & (time < a + XF)
        w[k] = np.sin(0.5 * math.pi * (time[k] - a) / XF)
    if i < len(parts) - 1:
        k = inside & (time > b - XF)
        w[k] = np.cos(0.5 * math.pi * (time[k] - (b - XF)) / XF)
    return w


def band(x, lo, hi, soft=0.25):
    """Zero-phase band-pass by FFT with raised-cosine edges (soft = edge width in octaves)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    lf = np.log2(np.maximum(f, 1e-3))
    g = np.clip((lf - math.log2(lo)) / soft + 0.5, 0, 1) * np.clip((math.log2(hi) - lf) / soft + 0.5, 0, 1)
    return np.fft.irfft(X * (0.5 - 0.5 * np.cos(math.pi * g)), len(x))


def norm(x):
    return x / (np.max(np.abs(x)) + 1e-9)


noise_hiss = norm(band(rng.standard_normal(N), 900, 7000))
noise_roar = norm(band(rng.standard_normal(N), 60, 900))
noise_bright = norm(band(rng.standard_normal(N), 2500, 11000))
noise_wind = norm(band(rng.standard_normal(N), 120, 1400, 0.6))
L = np.zeros(N)
R = np.zeros(N)

# ---- sound effects, per part
for i, p in enumerate(parts):
    w = part_weight(i)
    on = w > 0
    local = np.clip(time - p['start'], 0, p['dur'] - 1e-6)
    rt = np.interp(local, (np.arange(p['n']) + 0.5) / FPS, p['t'])           # replay time per sample
    lift = np.interp(rt, TT, LIFT)
    fl, fr = np.interp(rt, TT, SIDE[:, 0]), np.interp(rt, TT, SIDE[:, 1])
    speed = np.interp(rt, ST, SPEED)
    if p['name'] == 'xr':
        car = np.stack([np.interp(p['t'], ST, SP[:, k]) for k in range(3)], 1) + OFFSET
        dist = np.linalg.norm(car - p['head'], axis=1)
        near = np.interp(local, (np.arange(p['n']) + 0.5) / FPS, np.clip(9.0 / dist, 0.12, 1.0))
    else:
        near = np.full(N, {'coldopen': 1.0, '2d': 0.5, 'cv': 0.3}[p['name']])
    g = w * near
    roar = (0.55 * noise_hiss + 0.75 * noise_roar) * np.sqrt(np.clip(lift, 0, 1)) * g
    burst_l = noise_bright * np.clip(fl, 0, 1) ** 0.7 * g * 0.6
    burst_r = noise_bright * np.clip(fr, 0, 1) ** 0.7 * g * 0.6
    whine_f = 160 + 24 * speed
    phase = 2 * math.pi * np.cumsum(whine_f) / SR
    whine = (np.sin(phase) + 0.35 * np.sin(2 * phase + 0.4) + 0.15 * np.sin(3.1 * phase)) * np.clip(speed / 14, 0, 1) ** 1.5 * 0.09 * g
    wind = noise_wind * np.clip(speed / 16, 0, 1) ** 2 * 0.35 * g * (1.6 if p['name'] == 'coldopen' else 1.0)
    L += roar * 0.5 + burst_l + whine + wind * 0.9
    R += roar * 0.5 + burst_r + whine + wind
    # touchdown boom wherever the replay crosses 11.53 s inside this part's visible span
    cross = np.where(on[1:] & (rt[:-1] < 11.53) & (rt[1:] >= 11.53))[0]
    for c in cross:
        k = np.arange(N - c)
        env = np.exp(-k / (0.35 * SR))
        boom = (np.sin(2 * math.pi * 46 * k / SR) * env + 0.5 * noise_roar[c:] * np.exp(-k / (0.12 * SR))) * near[c] * 0.9
        L[c:] += boom
        R[c:] += boom

# ---- music: D minor, 100 bpm
beat = 0.6
midi = lambda m: 440.0 * 2 ** ((m - 69) / 12)
chords = [(50, 53, 57), (46, 50, 53), (53, 57, 60), (48, 52, 55)]          # Dm  Bb  F  C
roots = [38, 34, 41, 36]
bar = 4 * beat
pad_l, pad_r = np.zeros(N), np.zeros(N)
for ci in range(int(total / (2 * bar)) + 2):
    c0 = ci * 2 * bar
    chord = chords[ci % 4] if c0 < end_card - 0.2 else (50, 53, 57, 62)   # resolve to D on the end card
    seg = (time >= c0 - 0.1) & (time < c0 + 2 * bar + 0.9)
    tt = time[seg] - c0
    env = np.clip(tt / 0.7, 0, 1) * np.clip((2 * bar + 0.8 - tt) / 0.8, 0, 1)
    for m in chord:
        for k in range(1, 7):
            amp = 0.05 / k * env
            pad_l[seg] += amp * np.sin(2 * math.pi * midi(m) * 0.997 * k * tt + k)
            pad_r[seg] += amp * np.sin(2 * math.pi * midi(m) * 1.003 * k * tt + 2 * k)
drone = 0.12 * np.sin(2 * math.pi * midi(26) * time) + 0.06 * np.sin(2 * math.pi * midi(38) * time)
# energy arc: strong under the cold open, building through the run into the flip, calmer under the CV
# pass and VR, resolving on the end card
p2 = next((p for p in parts if p['name'] == '2d'), None)
flip_at = p2['start'] + (8.25 - p2['t'][0]) if p2 else 3.0
energy = np.interp(time, [0, 3.2, 4.0, flip_at - 4, flip_at, flip_at + 4, end_card - 6, end_card, total],
                   [1.0, 1.0, 0.55, 0.75, 1.0, 0.85, 0.45, 0.5, 0.0])
pulse = np.zeros(N)
kick = np.zeros(N)
for b in range(int(total / (beat / 2))):
    t0 = b * beat / 2
    if t0 > end_card:
        break
    c = int(t0 * SR)
    k = np.arange(min(int(0.4 * SR), N - c))
    root = midi(roots[int(t0 / (2 * bar)) % 4])
    pulse[c:c + len(k)] += (np.sin(2 * math.pi * root * k / SR) + 0.4 * np.sin(4 * math.pi * root * k / SR)) * np.exp(-k / (0.11 * SR)) * 0.16
    if b % 2 == 0 and (b // 2) % 2 == 0:
        f = 45 + 75 * np.exp(-k / (0.03 * SR))
        kick[c:c + len(k)] += np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-k / (0.16 * SR)) * 0.35
riser = np.zeros(N)
seg = (time > flip_at - 2.4) & (time < flip_at)
riser[seg] = noise_hiss[seg] * ((time[seg] - (flip_at - 2.4)) / 2.4) ** 2.5 * 0.35
music_l = (pad_l + drone) * (0.55 + 0.45 * energy) + (pulse + kick) * energy + riser * 0.8
music_r = (pad_r + drone) * (0.55 + 0.45 * energy) + (pulse + kick) * energy + riser
# hit on the first frame of the cold open
k = np.arange(int(1.2 * SR))
hit = np.sin(2 * math.pi * 42 * k / SR) * np.exp(-k / (0.45 * SR)) * 0.9 + noise_roar[:len(k)] * np.exp(-k / (0.2 * SR)) * 0.5
music_l[:len(k)] += hit
music_r[:len(k)] += hit
fade = np.clip((total - time) / 1.6, 0, 1)                                  # out before the studio outro
mix_l = (L * 0.8 + music_l * 0.7) * fade
mix_r = (R * 0.8 + music_r * 0.7) * fade
peak = max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)))
mix = np.stack([mix_l, mix_r], 1) / peak * 0.95
mix = np.tanh(mix * 1.4) / np.tanh(1.4) * 0.89                             # gentle limiter, about -1 dBFS
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FILM, 'soundtrack.wav')
with wave.open(out, 'wb') as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype('<i2').tobytes())
print('wrote', out, f'{total:.2f} s;', ', '.join(f"{p['name']} @{p['start']:.2f}" for p in parts), f'end card @{end_card:.2f}')
