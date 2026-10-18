import { MathUtils, type Object3D, PerspectiveCamera, Vector3 } from '@iwsdk/core';
import { MOUNT_LENS } from './mount-rig.js';
import { TrackPlayer, type ReconstructionTrack } from './replay-track.js';

export const VIEW_NAMES = ['Ground', 'Mounted', 'Drone'] as const;

/**
 * Browser-view camera director. Every pose is a pure function of replay time (plus wall-clock drift
 * for the idle intro), so scrubbing and slow motion stay exact, and no view ever cuts:
 * - Ground: circles the parked car, cranes out to a fixed vantage beside the lane and follows the
 *   whole run from there with a smooth pan and a gentle zoom, like the broadcast footage.
 * - Mounted: a camera rig fixed behind the car, like a supercar content rig; it rolls with the car.
 * - Drone: a loose follow from the air off the car's flank.
 * The smooth follows are baked once from the track (critically damped), so they stay functions of time.
 * Positions are authored in track-local metres and converted with `offset`.
 */
export class ReplayCamera {
  private static readonly RATE = 60;
  /** Ground vantage beside the lane on the key-light side, about 40-60 m from the action (track-local). */
  private static readonly TRIPOD = new Vector3(-50, 3.2, 36);
  private static readonly SCENE_CENTRE = new Vector3(-20, 9, 0);
  private readonly player: TrackPlayer;
  private readonly position = new Vector3();
  private readonly target = new Vector3();
  private readonly up = new Vector3(0, 1, 0);
  private readonly local = new Vector3();
  private readonly orbit = new Vector3();
  private readonly orbitTarget = new Vector3();
  private readonly groundTarget: Float32Array;
  private readonly groundFov: Float32Array;
  private readonly droneFollow: Float32Array;
  private fov = 40;
  private portraitCap = 1.9;
  private lastFov = -1;
  private lastAspect = -1;
  /** Film capture override (world space): when set, the director uses exactly this pose and lens. */
  override: { position: [number, number, number]; target: [number, number, number]; fov: number; exposure?: number } | null = null;

  constructor(track: ReconstructionTrack, private readonly offset: Vector3) {
    this.player = new TrackPlayer(track);
    const n = Math.ceil(track.duration * ReplayCamera.RATE) + 1;
    const dt = 1 / ReplayCamera.RATE;
    const car = new Float32Array(n * 3), ahead = new Float32Array(n * 3);
    const omega = 3.2;                       // ground operator's follow; look ahead by its lag (2 / omega)
    for (let i = 0; i < n; i++) {
      const p = this.player.evaluate(i * dt).position;
      car[i * 3] = p.x; car[i * 3 + 1] = p.y + 0.6; car[i * 3 + 2] = p.z;
      const q = this.player.evaluate(i * dt + 2 / omega).position;
      ahead[i * 3] = q.x; ahead[i * 3 + 1] = q.y + 0.6; ahead[i * 3 + 2] = q.z;
    }
    const follow = damped(ahead, n, omega, dt);
    this.groundTarget = new Float32Array(n * 3);
    const fov = new Float32Array(n);
    const c = ReplayCamera.SCENE_CENTRE, tri = ReplayCamera.TRIPOD;
    for (let i = 0; i < n; i++) {
      const t = i * dt;
      const bias = 0.18 * (1 - MathUtils.smoothstep(t, 10.0, 11.6));
      const x = follow[i * 3] * (1 - bias) + c.x * bias, y = follow[i * 3 + 1] * (1 - bias) + c.y * bias, z = follow[i * 3 + 2] * (1 - bias) + c.z * bias;
      this.groundTarget[i * 3] = x; this.groundTarget[i * 3 + 1] = y; this.groundTarget[i * 3 + 2] = z;
      // lens: the visible height at the car eases from the whole ramp on the climb to a tighter flip and landing
      const dist = Math.hypot(follow[i * 3] - tri.x, follow[i * 3 + 1] - tri.y, follow[i * 3 + 2] - tri.z);
      fov[i] = MathUtils.radToDeg(2 * Math.atan(interp(t, GROUND_HEIGHT_T, GROUND_HEIGHT_M) / (2 * dist)));
    }
    this.groundFov = damped(fov, n, 2.0, dt, 1);
    this.droneFollow = damped(car, n, 1.6, dt);
  }

  update(camera: Object3D, mode: number, time: number, clock: number, car: Vector3, impact: number, intro: boolean): void {
    const aspect = camera instanceof PerspectiveCamera ? camera.aspect : 16 / 9;
    this.up.set(0, 1, 0);
    this.portraitCap = 1.9;
    if (this.override) {
      const o = this.override;
      camera.position.set(o.position[0], o.position[1], o.position[2]);
      camera.parent?.worldToLocal(camera.position);
      camera.up.set(0, 1, 0);
      camera.lookAt(o.target[0], o.target[1], o.target[2]);
      if (camera instanceof PerspectiveCamera && Math.abs(camera.fov - o.fov) > 1e-4) { camera.fov = o.fov; camera.updateProjectionMatrix(); this.lastFov = -1; }
      return;
    }
    if (intro) this.introShot(clock);
    else if (mode === 1) this.mounted(time, impact);
    else if (mode === 2) this.drone(time, car);
    else this.ground(time);
    // Landing impact: a short, sharp, decaying shake (the mounted rig has its own jolt).
    if (impact > 0.002 && mode !== 1 && !intro) {
      const k = impact * (mode === 0 ? 0.35 : 0.6);
      this.position.y += Math.sin(time * 67.0 + 1.1) * 0.07 * k;
      this.target.y += Math.sin(time * 41.0 + 2.3) * 0.12 * k;
    }
    this.position.add(this.offset);
    this.target.add(this.offset);
    camera.position.copy(this.position);
    camera.parent?.worldToLocal(camera.position);
    camera.up.copy(this.up);
    camera.lookAt(this.target);
    if (camera instanceof PerspectiveCamera) {
      // Portrait screens get a wider lens so the action stays in frame.
      const fov = this.fov * MathUtils.clamp(Math.pow(1.5 / aspect, 0.55), 1, this.portraitCap);
      if (Math.abs(fov - this.lastFov) > 0.01 || aspect !== this.lastAspect) {
        camera.fov = fov; camera.updateProjectionMatrix(); this.lastFov = fov; this.lastAspect = aspect;
      }
    }
  }

  private introShot(clock: number): void {
    const a = -2.55 + Math.sin(clock * 0.09) * 0.35;
    this.position.set(-6 + Math.cos(a) * 9.5, 1.15 + Math.sin(clock * 0.13) * 0.25, Math.sin(a) * 9.5);
    this.target.set(-5.2, 1.6, 0);
    this.fov = 34;
  }

  /** Ground: the opening round of the parked car, a crane out to the tripod, then pan and zoom only. */
  private ground(time: number): void {
    const i = this.sample(time);
    this.position.copy(ReplayCamera.TRIPOD);
    this.target.set(lerpAt(this.groundTarget, i, 0), lerpAt(this.groundTarget, i, 1), lerpAt(this.groundTarget, i, 2));
    this.fov = lerpAt(this.groundFov, i, 0, 1);
    const w = MathUtils.smootherstep(time, 0.6, 3.6);
    if (w < 1) {
      // continue the intro's slow round behind the car and rise, then blend out to the tripod
      const u = MathUtils.smootherstep(time, 0, 3.6);
      const a = -2.55 - 1.15 * u, r = 9.5 + 2.5 * u;
      this.orbit.set(-6 + Math.cos(a) * r, 1.15 + 1.3 * u, Math.sin(a) * r);
      this.orbitTarget.set(-5.2, 1.6 - 0.6 * u, 0);
      this.position.lerpVectors(this.orbit, this.position, w);
      this.target.lerpVectors(this.orbitTarget, this.target, w);
      this.fov = MathUtils.lerp(34, this.fov, w);
    }
  }

  /** Mounted: the lens on the end of the rig behind the car (see mount-rig.ts), looking forward over the
   *  roof; it rolls with the car, sways on the rods and buzzes harder when the jets fire or it lands. */
  private mounted(time: number, impact: number): void {
    const pose = this.player.evaluate(time);
    const q = pose.quaternion;
    const sway = 0.012 + 0.012 * pose.lift + 0.03 * impact;       // rod flex, a few hertz
    const buzz = 0.004 + 0.006 * pose.lift + 0.02 * impact;       // high-frequency vibration
    const sy = (Math.sin(time * 17.0) * 0.6 + Math.sin(time * 25.8 + 1.3) * 0.4) * sway;
    const sz = (Math.sin(time * 13.1 + 0.4) * 0.6 + Math.sin(time * 21.7 + 2.2) * 0.4) * sway * 0.7;
    this.local.set(MOUNT_LENS.x + Math.sin(time * 31.0) * buzz, MOUNT_LENS.y + sy + Math.sin(time * 43.0 + 0.7) * buzz, sz + Math.sin(time * 37.0 + 1.9) * buzz);
    this.position.copy(this.local).applyQuaternion(q).add(pose.position);
    this.local.set(9.0, 0.2 + sy * 2.5, sz * 2.5);
    this.target.copy(this.local).applyQuaternion(q).add(pose.position);
    this.up.set(0, 1, 0).applyQuaternion(q);
    this.fov = 74;                                                  // wide action-camera lens
    this.portraitCap = 1.25;
  }

  /** Drone: a loose, lagging follow from the air off the car's flank, looking at the car. */
  private drone(time: number, car: Vector3): void {
    const i = this.sample(time);
    const fx = lerpAt(this.droneFollow, i, 0), fy = lerpAt(this.droneFollow, i, 1), fz = lerpAt(this.droneFollow, i, 2);
    this.position.set(fx - 5, Math.max(3.5, fy + 5.5), fz + 14);
    this.target.set(car.x * 0.7 + fx * 0.3, car.y * 0.7 + fy * 0.3 + 0.4, car.z * 0.7 + fz * 0.3);
    this.fov = 44;
  }

  private sample(time: number): number {
    return MathUtils.clamp(time * ReplayCamera.RATE, 0, this.groundFov.length - 1);
  }
}

/** Visible height (m) at the car for the ground lens, by replay time: the whole ramp on the climb,
 *  tighter for the flip and the landing. */
const GROUND_HEIGHT_T = [0, 2.4, 4.2, 6.0, 7.6, 8.3, 9.6, 11.0, 12.2, 14.0];
const GROUND_HEIGHT_M = [13, 15, 26, 30, 25, 17, 16, 15, 12.5, 11];

function interp(x: number, xs: readonly number[], ys: readonly number[]): number {
  if (x <= xs[0]) return ys[0];
  for (let k = 1; k < xs.length; k++) {
    if (x <= xs[k]) return ys[k - 1] + (ys[k] - ys[k - 1]) * (x - xs[k - 1]) / (xs[k] - xs[k - 1]);
  }
  return ys[ys.length - 1];
}

/** Critically damped follow of a series (stride values per sample), as a smooth camera operator would. */
function damped(series: Float32Array, n: number, omega: number, dt: number, stride = 3): Float32Array {
  const out = new Float32Array(n * stride);
  for (let c = 0; c < stride; c++) {
    let pos = series[c], vel = 0;
    for (let i = 0; i < n; i++) {
      const acc = omega * omega * (series[i * stride + c] - pos) - 2 * omega * vel;
      vel += acc * dt; pos += vel * dt;
      out[i * stride + c] = i === 0 ? series[c] : pos;
    }
  }
  return out;
}

/** Linear interpolation of channel c of a baked series at fractional sample index i. */
function lerpAt(series: Float32Array, i: number, c: number, stride = 3): number {
  const k = Math.min(Math.floor(i), series.length / stride - 2), u = i - k;
  return series[k * stride + c] * (1 - u) + series[(k + 1) * stride + c] * u;
}
