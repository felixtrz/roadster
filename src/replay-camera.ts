import { MathUtils, type Object3D, PerspectiveCamera, Vector3 } from '@iwsdk/core';
import { TrackPlayer, type ReconstructionTrack } from './replay-track.js';

export const VIEW_NAMES = ['Show', 'Wide', 'Car', 'Top'] as const;

/**
 * Browser-view camera director. Every pose is a pure function of replay time
 * (plus wall-clock drift for the idle intro), so scrubbing and slow motion stay
 * exact. View 0 cuts between broadcast-style shots like the real coverage.
 * Positions are authored in track-local metres and converted with `offset`.
 */
export class ReplayCamera {
  private readonly lag: TrackPlayer;
  private readonly position = new Vector3();
  private readonly target = new Vector3();
  private readonly car = new Vector3();
  private readonly carLag = new Vector3();
  private fov = 40;
  private portraitCap = 1.9;
  private readonly flipPos = new Vector3();
  private readonly flipTarget = new Vector3();
  private readonly flipUp = new Vector3(0, 1, 0);
  private readonly offA = new Vector3();
  private readonly offB = new Vector3();
  private readonly up = new Vector3(0, 1, 0);
  /** Broadcast main camera from geometry-fit.json (track-local), with its slight roll. */
  private static readonly MAIN_POS = new Vector3(-67.5, 1.28, 18.6);
  private static readonly MAIN_TARGET = new Vector3(-1.0, 10.4, -1.2);
  private static readonly MAIN_UP = new Vector3(-0.127, 0.992, 0.03).normalize();
  private lastFov = -1;
  private lastAspect = -1;
  /** Film capture override (world space): when set, the director uses exactly this pose and lens. */
  override: { position: [number, number, number]; target: [number, number, number]; fov: number; exposure?: number } | null = null;

  constructor(track: ReconstructionTrack, private readonly offset: Vector3) {
    this.lag = new TrackPlayer(track);
  }

  update(camera: Object3D, mode: number, time: number, clock: number, car: Vector3, impact: number, intro: boolean): void {
    const aspect = camera instanceof PerspectiveCamera ? camera.aspect : 16 / 9;
    this.car.copy(car);
    this.carLag.copy(this.lag.evaluate(Math.max(0, time - 0.22)).position);
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
    else if (mode === 1) this.wide(aspect);
    else if (mode === 2) this.chase(time);
    else if (mode === 3) this.overhead(aspect);
    else this.show(time, aspect);
    // Handheld drift: layered slow sines, stronger on long lenses like a real operator.
    const drift = (mode === 0 || intro ? 1 : 0.35) * (0.6 + 30 / this.fov * 0.4);
    this.target.x += (Math.sin(clock * 0.61) * 0.07 + Math.sin(clock * 1.73 + 1.3) * 0.025) * drift;
    this.target.y += (Math.sin(clock * 0.83 + 2.1) * 0.05 + Math.sin(clock * 2.31) * 0.018) * drift;
    this.position.y += Math.sin(clock * 0.47 + 0.7) * 0.03 * drift;
    // Landing impact: a short, sharp, decaying shake.
    if (impact > 0.002 && mode !== 3) {
      const k = impact * (mode === 2 ? 0.5 : 1);
      this.position.x += Math.sin(time * 53.0) * 0.05 * k;
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

  private show(time: number, aspect: number): void {
    const car = this.car, lag = this.carLag;
    if (time < 8.2) {
      this.broadcastPose(lag);
    } else if (time < 9.95) {
      // The flip: a low three-quarter view from the ramp-lip side, about 25 m from the car, so the
      // car fills roughly a third of the frame and the upside-down roll reads. Pure function of time:
      // it blends in from the broadcast camera (8.2-8.65 s) and out to the descent shot (9.45-9.95 s).
      const range = aspect < 1 ? 22 : 25;
      this.flipPos.set(car.x + range * 0.85, car.y - range * 0.3, car.z + range * 0.43);
      this.flipTarget.set(car.x - 0.6, car.y + 0.2, car.z);
      const flipFov = aspect < 1 ? 26 : 22;
      const into = MathUtils.smootherstep(time, 8.2, 8.65);
      const out = MathUtils.smootherstep(time, 9.45, 9.95);
      if (into < 1) {
        this.broadcastPose(lag);
        // Swing around the car (direction and distance interpolated separately) so the camera
        // never passes through the car on its way in from the broadcast vantage.
        this.offA.subVectors(this.position, car); this.offB.subVectors(this.flipPos, car);
        const dist = MathUtils.lerp(this.offA.length(), this.offB.length(), into);
        this.offA.normalize().lerp(this.offB.normalize(), into).normalize();
        this.position.copy(car).addScaledVector(this.offA, dist);
        this.target.lerpVectors(this.target, this.flipTarget, into);
        this.up.lerp(this.flipUp.set(0, 1, 0), into).normalize();
        this.fov = MathUtils.lerp(this.fov, flipFov, into);
      } else {
        this.descentPose(Math.max(time, 10.0), aspect, car, lag);
        this.position.lerpVectors(this.flipPos, this.position, out);
        this.target.lerpVectors(this.flipTarget, this.target, out);
        this.fov = MathUtils.lerp(flipFov, this.fov, out);
        if (out < 0.5) this.portraitCap = 1.4;
      }
    } else if (time < 11.4) {
      this.descentPose(time, aspect, car, lag);
    } else {
      this.portraitCap = 1.35;
      // Touchdown and drive-out: the lens waits down the lane, low, so the car lands in the
      // mid-ground with its cloud behind it, then drives out of the vapor and past camera.
      const k = MathUtils.smoothstep(time, 11.4, 18);
      this.position.set(-90 - k * 4, 1.05 + k * 0.4, 7.5 + k * 1.5);
      this.target.set(lag.x + 2.5 * (1 - k), 0.95, lag.z);
      this.fov = MathUtils.lerp(34, 26, MathUtils.smoothstep(time, 13.5, 18));
      if (aspect < 1) this.target.y -= 0.35;
    }
  }

  /** The broadcast main camera (solved from the footage): far down the lane, long lens, where the
   *  ramp reads as the tall narrow arc. It pans and tilts gently after the car. */
  private broadcastPose(lag: Vector3): void {
    this.position.copy(ReplayCamera.MAIN_POS);
    this.target.copy(ReplayCamera.MAIN_TARGET);
    this.target.x += (lag.x - this.target.x) * 0.28;
    this.target.y += (lag.y - this.target.y) * 0.3;
    this.up.copy(ReplayCamera.MAIN_UP);
    this.fov = 27.5;
  }

  /** Descent: low and close as the jets dig into the ground and the cloud builds. */
  private descentPose(time: number, aspect: number, car: Vector3, lag: Vector3): void {
    const k = MathUtils.smoothstep(time, 10.0, 11.4);
    this.portraitCap = 1.35;
    this.position.set(-46.5 - k * 2, 0.45 + k * 0.15, 14.5);
    this.target.set(MathUtils.lerp(lag.x, car.x, 0.5), Math.max(1.1, lag.y * 0.7 + 1.0), car.z);
    this.target.x = Math.min(this.target.x, -40);
    this.fov = 40;
    if (aspect < 1) { this.target.x = car.x; this.target.y -= 0.6; }
  }

  /** The broadcast overhead camera from geometry-fit.json: a fixed high three-quarter view of the site. */
  private wide(_aspect: number): void {
    // Same vantage, aimed a little up and toward the ramp so the whole arc stays in frame.
    this.position.set(-53.1, 37.2, 53.6);
    this.target.set(-14.0, -3.5, -13.0);
    this.fov = 52;
  }

  private chase(time: number): void {
    const car = this.car;
    if (time > 8.2 && time < 10.2) {
      // Flight: hold off the car's flank at its own height so the whole body stays in frame.
      this.target.set(car.x, car.y + 0.4, car.z);
      this.position.set(car.x + 5.5, car.y + 1.0, car.z + 9.5);
      this.fov = 42;
      return;
    }
    if (time > 10.6 && time < 13.2) {
      // Landing: stay on the far (-z) side, upwind of the cloud's drift, 7 m out and 1.2 m up.
      this.target.set(car.x, car.y + 0.6, car.z);
      this.position.set(car.x - 1.5, 1.2, car.z - 7.2);
      this.fov = 44;
      return;
    }
    const orbit = 0.62 + Math.sin(time * 0.25) * 0.25;
    this.target.copy(this.carLag).lerp(car, 0.7); this.target.y += 0.75;
    this.position.set(this.target.x + Math.cos(orbit) * 7.5, this.target.y + 0.85, Math.sin(orbit) * 8.5);
    this.fov = 38;
  }

  private overhead(aspect: number): void {
    const left = Math.min(-14, this.car.x - 4);
    const center = (left + 12) * 0.5;
    const height = Math.max(75, ((12 - left) * 0.5 + 8) / (Math.tan(MathUtils.degToRad(21)) * aspect));
    this.position.set(center, height, 0.1);
    this.target.set(center, 0, 0);
    this.fov = 42;
  }
}
