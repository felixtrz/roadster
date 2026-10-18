import { Quaternion, Vector3 } from '@iwsdk/core';
import thrustData from './data/thrusters.json';

/**
 * Physics-derived firing (tools/thrusters/solve_thrusters.py): the air-phase attitude (a bang-bang
 * roll about the long axis, timed from the broadcast) and normalised thrust for the four canted
 * corner nozzles, solved by inverse dynamics from the track. Same 1/60 s grid as the track.
 */
const THRUST = thrustData as { dt: number; t0: number; quaternions: number[][]; thrust: number[][] };

export interface TrackSample {
  time: number;
  position: number[];
  quaternion: number[];
  phase: string;
  thrusters: { attitude: number; lift: number };
}

export interface ReconstructionTrack {
  duration: number;
  samples: TrackSample[];
  car: { length: number; width: number; height: number; wheelbase: number; track: number; wheelRadius: number };
  ramp: { centerline: number[][]; width: number; height: number };
}

/** Reuses caller-owned state; the source samples remain immutable. */
export class TrackPlayer {
  readonly position = new Vector3();
  readonly quaternion = new Quaternion();
  phase = 'Ready';
  attitude = 0;
  lift = 0;
  /** Thrust per corner nozzle, 0..1 (front-left, front-right, rear-left, rear-right). */
  readonly nozzle = new Float32Array(4);
  private readonly thrustQuaternion = new Quaternion();
  private cursor = 0;

  constructor(readonly track: ReconstructionTrack) {
    if (track.samples.length < 2 || track.duration <= 0) {
      throw new Error('A measured Roadster track with at least two samples is required.');
    }
  }

  evaluate(seconds: number): this {
    const time = Math.max(0, Math.min(seconds, this.track.duration));
    const samples = this.track.samples;
    while (this.cursor > 0 && samples[this.cursor].time > time) this.cursor--;
    while (this.cursor < samples.length - 2 && samples[this.cursor + 1].time <= time) this.cursor++;
    const a = samples[this.cursor];
    const b = samples[this.cursor + 1];
    const alpha = Math.max(0, Math.min(1, (time - a.time) / Math.max(0.00001, b.time - a.time)));
    this.position.set(
      a.position[0] + (b.position[0] - a.position[0]) * alpha,
      a.position[1] + (b.position[1] - a.position[1]) * alpha,
      a.position[2] + (b.position[2] - a.position[2]) * alpha,
    );
    this.phase = alpha < 1 ? a.phase : b.phase;
    // attitude and thrust come from the physics solution; the scalar envelopes are superseded
    const f = (time - THRUST.t0) / THRUST.dt;
    const k = Math.max(0, Math.min(THRUST.thrust.length - 2, Math.floor(f)));
    const u = Math.max(0, Math.min(1, f - k));
    const qa = THRUST.quaternions[k], qb = THRUST.quaternions[k + 1];
    this.quaternion.set(qa[0], qa[1], qa[2], qa[3]);
    this.thrustQuaternion.set(qb[0], qb[1], qb[2], qb[3]);
    this.quaternion.slerp(this.thrustQuaternion, u);
    const ta = THRUST.thrust[k], tb = THRUST.thrust[k + 1];
    let sum = 0;
    for (let i = 0; i < 4; i++) { this.nozzle[i] = ta[i] + (tb[i] - ta[i]) * u; sum += this.nozzle[i]; }
    this.lift = sum / 4;
    this.attitude = 0;
    return this;
  }
}
