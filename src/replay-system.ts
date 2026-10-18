import { createSystem, Mesh, Object3D, PerspectiveCamera, PointLight, Quaternion, UIKitMLAsset, Vector3, VisibilityState } from '@iwsdk/core';
import data from '../references/roadster/reconstruction/reconstruction.json';
import { RoadsterReplay } from './replay-component.js';
import { TrackPlayer, type ReconstructionTrack } from './replay-track.js';
import { ReplayEffects } from './replay-effects.js';
import { PHASES, ReplayControls } from './replay-controls.js';
import { AUTOMATION } from './automation.js';
import { ReplayCamera } from './replay-camera.js';
import { CinematicRenderer } from './cinematic-renderer.js';
import { createMountRig, disposeMountRig } from './mount-rig.js';
import type { ShellFrame } from './shell.js';
import { FX_TIME, FX_XR } from './scene-assets/lib/fx-materials.js';
import { SITE_OFFSET } from './scene-assets/lib/site-layout.js';

const OFFSET = new Vector3(...SITE_OFFSET);
const WHEEL_AXIS = new Vector3(1, 0, 0);
const FORWARD = new Vector3(1, 0, 0);
const UP = new Vector3(0, 1, 0);

export class RoadsterSystem extends createSystem({ cars: { required: [RoadsterReplay] } }) {
  private readonly track = new TrackPlayer(data as ReconstructionTrack);
  private effects!: ReplayEffects;
  private controls!: ReplayControls;
  private director!: ReplayCamera;
  private cinematic: CinematicRenderer | null = null;
  private readonly wheels: Object3D[] = [];
  private readonly carShadowMeshes: Mesh[] = [];
  private readonly mountRig = createMountRig();
  private carCastsShadow = false;
  private readonly wheelRest: Quaternion[] = [];
  private readonly wheelSpin = new Quaternion();
  private readonly distance = new Float64Array(data.samples.length);
  private readonly gLoad = new Float32Array(data.samples.length);
  private readonly phaseLabels = new Map<string, string>();
  private readonly forward = new Vector3();
  private readonly up = new Vector3();
  private readonly frame: ShellFrame = { time: 0, playing: false, speed: 1, view: 0, phase: 'ready', altitudeFt: 0, g: 1, pitchDeg: 0, inverted: false, rollScale: 1, impact: 0 };
  private clock = 0;
  private carKey!: PointLight;
  private wasXR = false;
  private baseExposure = -1;

  init(): void {
    const car = this.world.requireSceneObject('roadster');
    // Only a silhouette proxy casts the car's ground shadow: the closed inner body and the tyres, not
    // every detail part (a handful of draws per shadow map instead of the whole car).
    car.traverse((part) => {
      if (!(part instanceof Mesh)) return;
      part.castShadow = false; part.receiveShadow = false;
      const name = (Array.isArray(part.material) ? part.material[0] : part.material)?.name ?? '';
      if (name === 'PanelGap' || name === 'Tyre_Rubber') this.carShadowMeshes.push(part);
    });
    for (const name of ['Wheel_FL', 'Wheel_FR', 'Wheel_RL', 'Wheel_RR']) {
      const wheel = car.getObjectByName(name);
      if (wheel) { this.wheels.push(wheel); this.wheelRest.push(wheel.quaternion.clone()); }
    }
    car.add(this.mountRig);
    this.cleanupFuncs.push(() => { this.mountRig.removeFromParent(); disposeMountRig(this.mountRig); });
    this.bakeTrack();
    const lights = {
      lift: this.makeLight(0x9cc8ff, 30),
    };
    this.carKey = this.makeLight(0xdce8ff, 30);
    this.effects = new ReplayEffects(this.world.requireSceneObject('thrusters'), this.world.requireSceneObject('vapor'), data as ReconstructionTrack, lights, this.world.assetManager.getTexture('vapor-lit'));
    // Lift jets stay at the four car-local corners (DEFAULT_NOZZLES), matching the broadcast; the GLB's
    // NozzleAnchor_n are the rear exhaust nozzles and are not used for the downward lift plumes.
    this.controls = new ReplayControls(this.world, this.world.requireSceneObject<UIKitMLAsset>('controls'), () => this.queries.cars.entities, data.duration);
    this.director = new ReplayCamera(data as ReconstructionTrack, OFFSET);
    try {
      this.cinematic = new CinematicRenderer(this.world, OFFSET);
    } catch (error) {
      console.warn('[roadster] post-processing unavailable, rendering directly', error);
    }
    this.cleanupFuncs.push(() => this.controls.dispose(), () => this.effects.dispose(), () => this.cinematic?.dispose());
    if (AUTOMATION) this.installAutomationHooks();
  }

  /** Debug and film hooks for the tools in tools/film and tools/verification (see src/automation.ts). */
  private installAutomationHooks(): void {
    Object.assign(window, { roadsterRenderInfo: () => ({
      toneMapping: this.world.renderer.toneMapping, exposure: this.world.renderer.toneMappingExposure, fog: !!this.world.scene.fog,
      shadows: this.world.renderer.shadowMap.enabled, post: this.cinematic?.enabled ?? false, render: this.world.renderer.info.render,
      camera: { position: this.world.camera.position.toArray(), fov: (this.world.camera as PerspectiveCamera).fov },
    }), roadsterCinematic: () => this.cinematic, roadsterScene: () => this.world.scene,
      roadsterFilmCamera: (pose: ReplayCamera['override']) => {
        // exposure is relative to the app's own tone-mapping exposure, restored when the override ends
        if (this.baseExposure < 0) this.baseExposure = this.world.renderer.toneMappingExposure;
        this.world.renderer.toneMappingExposure = this.baseExposure * (pose?.exposure ?? 1);
        this.director.override = pose;
      }, roadsterPost: (on: boolean, reflection = true) => { if (this.cinematic) { this.cinematic.enabled = on; this.cinematic.reflection = reflection; } } });
    this.cleanupFuncs.push(() => { for (const key of ['roadsterRenderInfo', 'roadsterCinematic', 'roadsterScene', 'roadsterFilmCamera', 'roadsterPost']) Reflect.deleteProperty(window, key); });
  }

  private makeLight(color: number, distance: number): PointLight {
    const light = new PointLight(color, 0, distance, 2);
    light.name = 'ReplayEffectLight';
    this.world.createTransformEntity(light);
    return light;
  }

  /** Wheel travel and proper acceleration (g-load) per reconstruction sample. */
  private bakeTrack(): void {
    const samples = data.samples;
    let traveled = 0;
    for (let i = 0; i < samples.length; i++) {
      const sample = samples[i];
      if (i > 0 && ['ready', 'approach', 'climb', 'landing', 'drive-away'].includes(sample.phase)) {
        const a = sample.position, b = samples[i - 1].position;
        traveled += Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
      }
      this.distance[i] = traveled;
      this.phaseLabels.set(sample.phase, sample.phase.replace('-', ' ').toUpperCase());
    }
    for (const phase of PHASES) this.phaseLabels.set(phase.id, phase.label.toUpperCase());
    const raw = new Float32Array(samples.length);
    const k = 4, dt = (samples[1].time - samples[0].time) * k;
    for (let i = 0; i < samples.length; i++) {
      const a = samples[Math.max(0, i - k)].position, b = samples[i].position, c = samples[Math.min(samples.length - 1, i + k)].position;
      const ax = (a[0] - 2 * b[0] + c[0]) / (dt * dt), ay = (a[1] - 2 * b[1] + c[1]) / (dt * dt) + 9.81, az = (a[2] - 2 * b[2] + c[2]) / (dt * dt);
      raw[i] = Math.min(6, Math.hypot(ax, ay, az) / 9.81);
    }
    for (let i = 0; i < samples.length; i++) {
      let sum = 0, n = 0;
      for (let j = Math.max(0, i - 6); j <= Math.min(samples.length - 1, i + 6); j++) { sum += raw[j]; n++; }
      this.gLoad[i] = sum / n;
    }
  }

  update(delta: number): void {
    this.clock += Math.min(delta, 0.1);
    const visibility = this.world.visibilityState.peek();
    const browser = visibility === VisibilityState.NonImmersive;
    if (browser === this.wasXR) {
      this.wasXR = !browser;
      FX_XR.value = browser ? 0 : 1;
      this.effects.setQuality(browser ? 1 : 0.5);
    }
    this.cinematic?.update(!browser);
    for (const entity of this.queries.cars.entities) {
      if (!entity.object3D) continue;
      let time = entity.getValue(RoadsterReplay, 'elapsed') ?? 0;
      const playing = !!entity.getValue(RoadsterReplay, 'playing');
      const speed = entity.getValue(RoadsterReplay, 'speed') ?? 1;
      if (playing && (visibility === VisibilityState.Visible || browser)) {
        time = Math.min(data.duration, time + Math.min(delta, 0.08) * speed);
        entity.setValue(RoadsterReplay, 'elapsed', time);
        if (time >= data.duration) this.controls.setPlaying(false);
      }
      FX_TIME.value = this.clock;
      const car = this.track.evaluate(time);
      entity.object3D.position.copy(car.position).add(OFFSET);
      entity.object3D.quaternion.copy(car.quaternion);
      const castShadow = car.position.y < 1.5;
      if (castShadow !== this.carCastsShadow) {
        for (const mesh of this.carShadowMeshes) mesh.castShadow = castShadow;
        this.carCastsShadow = castShadow;
        // The car is the only shadow caster: while it is airborne the shadow maps would re-render
        // empty every frame, so render them once more (to clear the old shadow) and then freeze them.
        const shadowMap = this.world.renderer.shadowMap;
        shadowMap.autoUpdate = castShadow;
        shadowMap.needsUpdate = true;
      }
      // Chapter advances to DESCENT once the car is upright and all four plumes fire (~9.5 s).
      const phase = car.phase === 'reorient' && time >= 9.5 ? 'descent' : car.phase;
      entity.setValue(RoadsterReplay, 'phase', phase);
      const frameIndex = Math.min(this.distance.length - 1, Math.floor(time * 60));
      this.wheelSpin.setFromAxisAngle(WHEEL_AXIS, this.distance[frameIndex] / data.car.wheelRadius);
      for (let i = 0; i < this.wheels.length; i++) this.wheels[i].quaternion.copy(this.wheelRest[i]).multiply(this.wheelSpin);
      // the close views (Mounted, Drone) keep the vapor from swallowing the lens on landing
      this.effects.forceClear = browser && this.controls.viewMode !== 0;
      this.effects.update(time, car, this.world.camera);
      // Broadcast key light that rides with the car in the air so the white body pops against the sky.
      // In the air it keys from the camera side; on the drive-away it moves ahead of the car as a soft front key.
      const air = Math.min(1, Math.max(0, (car.position.y - 1.5) / 4));
      const drive = Math.min(1, Math.max(0, (time - 11.9) / 0.6));
      if (drive > 0) this.carKey.position.set(car.position.x + OFFSET.x - 7, 3.2, car.position.z + OFFSET.z + 6);
      else if (this.controls.viewMode !== 0) {
        // Mounted and Drone views: a cool kicker from the far side/below so the dark underside keeps a readable silhouette.
        this.carKey.position.set(car.position.x + OFFSET.x - 5, car.position.y - 2.5, car.position.z + OFFSET.z - 6);
      } else this.carKey.position.set(car.position.x + OFFSET.x + 9, car.position.y - 2, car.position.z + OFFSET.z + 10); // Ground view: camera side, low
      const airKey = this.controls.viewMode !== 0 ? 340 : 260;
      this.carKey.intensity = airKey * air * air * (3 - 2 * air) + 130 * drive * drive * (3 - 2 * drive);
      // the camera rig on the car's rear deck exists only for the Mounted view
      this.mountRig.visible = browser && this.controls.viewMode === 1 && !this.controls.introActive;
      if (browser) this.director.update(this.world.camera, this.controls.viewMode, time, this.clock, car.position, this.effects.impact, this.controls.introActive);
      let shellFrame: ShellFrame | null = null;
      if (browser) {
        this.forward.copy(FORWARD).applyQuaternion(car.quaternion);
        this.up.copy(UP).applyQuaternion(car.quaternion);
        const f = this.frame;
        f.time = time; f.playing = playing; f.speed = speed; f.view = this.controls.viewMode; f.phase = phase;
        f.altitudeFt = Math.max(0, car.position.y) * 3.2808;
        f.g = this.gLoad[frameIndex];
        f.pitchDeg = Math.atan2(this.forward.y, this.forward.x) * 180 / Math.PI;
        // Side-profile icon: pitch rotates it; a roll about the long axis squashes it through edge-on
        // (cos of the roll seen from the side) and turns it over, so the flip reads as a roll.
        const len = Math.hypot(this.forward.x, this.forward.y) || 1;
        f.rollScale = (this.up.y * this.forward.x - this.up.x * this.forward.y) / len;
        f.inverted = f.rollScale < 0;
        f.impact = this.effects.impact;
        shellFrame = f;
      }
      this.controls.update(time, phase, this.phaseLabels.get(phase) ?? phase, shellFrame);
    }
  }
}
