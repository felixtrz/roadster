import {
  type BufferGeometry, type InstancedBufferAttribute, InstancedMesh, Matrix4, Mesh, NoColorSpace, Object3D, PointLight, Quaternion, ShaderMaterial,
  type Texture, Vector3,
} from '@iwsdk/core';
import { TrackPlayer, type ReconstructionTrack } from './replay-track.js';
import { FX_TIME, FX_XR } from './scene-assets/lib/fx-materials.js';
import thrustData from './data/thrusters.json';
import { DEFAULT_NOZZLES, SIDE_NOZZLES, SPARK_COUNT, SPLASH_COUNT, TIRE_SMOKE_COUNT, VAPOR_COUNT } from './scene-assets/effects.scene-asset.js';

function smooth(e0: number, e1: number, v: number): number { const t = Math.min(1, Math.max(0, (v - e0) / (e1 - e0))); return t * t * (3 - 2 * t); }
const random = (i: number): number => { const v = Math.sin(i * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
const TOUCHDOWN = 11.533;
const JET_PARTICLES = VAPOR_COUNT - TIRE_SMOKE_COUNT;
const BURST_PARTICLES = 100;
const MAIN_PARTICLES = JET_PARTICLES - BURST_PARTICLES;

export interface EffectLights { lift: PointLight }

/**
 * Drives every replay effect as a pure function of replay time, so seeking and
 * slow motion stay exact: layered jets, nozzle glows, jet lights, the landing
 * vapor cloud (CPU-sorted billboards), tyre smoke, sparks and ground splash.
 * No allocation happens in update().
 */
export class ReplayEffects {
  private readonly vapor: InstancedMesh;
  private readonly vaporMaterial: ShaderMaterial;
  private readonly seedAttr: InstancedBufferAttribute;
  private readonly opacityAttr: InstancedBufferAttribute;
  private readonly lightAttr: InstancedBufferAttribute;
  private readonly liftJets: Object3D[];
  private readonly coreMaterial: ShaderMaterial;
  private readonly plumeMaterial: ShaderMaterial;
  /** One plume and one core material per corner nozzle: each runs at its own solved thrust. */
  private readonly jetPlumes: ShaderMaterial[] = [];
  private readonly jetCores: ShaderMaterial[] = [];
  /** Per-instance geometry clones this class owns and must dispose (the vapor geometry is disposed directly). */
  private readonly ownedGeometries: BufferGeometry[] = [];
  /** Exhaust direction of each canted corner nozzle in the car frame (from the thrust solution). */
  private readonly exhaust: Vector3[] = (thrustData as { exhaust_dirs: number[][] }).exhaust_dirs.map(([x, y, z]) => new Vector3(x, y, z));
  private readonly exhaustWorld = new Vector3();
  private readonly nozzleWorld = new Vector3();
  private readonly nozzleGlows: InstancedMesh;
  private readonly sparkMaterial: ShaderMaterial;
  private readonly splashMaterial: ShaderMaterial;
  private readonly splashGlow: Mesh;
  private readonly splashGlowMaterial: ShaderMaterial;
  // Per-particle immutable emission data (track-local).
  private readonly emitTime = new Float32Array(VAPOR_COUNT);
  private readonly emitPos = new Float32Array(VAPOR_COUNT * 3);
  private readonly emitVel = new Float32Array(VAPOR_COUNT * 3);
  private readonly life = new Float32Array(VAPOR_COUNT);
  // Per-frame scratch, preallocated.
  private readonly px = new Float32Array(VAPOR_COUNT);
  private readonly py = new Float32Array(VAPOR_COUNT);
  private readonly pz = new Float32Array(VAPOR_COUNT);
  private readonly size = new Float32Array(VAPOR_COUNT);
  private readonly alpha = new Float32Array(VAPOR_COUNT);
  private readonly depth = new Float32Array(VAPOR_COUNT);
  /** Packed sort keys: quantized far-to-near depth in the high bits, the puff index in the low 10 bits. */
  private readonly sortKeys = new Uint32Array(VAPOR_COUNT);
  private readonly lightScratch = new Float32Array(VAPOR_COUNT * 4);
  private readonly position = new Vector3();
  private readonly scale = new Vector3();
  private readonly matrix = new Matrix4();
  private readonly billboard = new Quaternion();
  private readonly identity = new Quaternion();
  private readonly cameraPosition = new Vector3();
  private readonly cameraForward = new Vector3();
  private readonly offset = new Vector3();
  private readonly temp = new Vector3();
  private readonly carDown = new Vector3();
  private readonly nozzles: Vector3[] = DEFAULT_NOZZLES.map(([x, y, z]) => new Vector3(x, y, z));
  private readonly sideNozzles: Vector3[] = SIDE_NOZZLES.map(([x, y, z]) => new Vector3(x, y, z));
  private readonly sideExhaust: Vector3[] = (thrustData as { side_exhaust_dirs: number[][] }).side_exhaust_dirs.map(([x, y, z]) => new Vector3(x, y, z));
  private readonly sideJets: Object3D[];
  private readonly sidePlumes: ShaderMaterial[] = [];
  private readonly sideCores: ShaderMaterial[] = [];
  private quality = 1;
  thrust = 0;
  /** Close camera views (Car view) keep the sight line to the car fully clear of vapor. */
  forceClear = false;
  private liftNow = 0;
  /** 0..1 impact envelope used by the camera for shake and by the HUD for g-force flashes. */
  impact = 0;

  constructor(private readonly thrusters: Object3D, private readonly vaporRoot: Object3D, track: ReconstructionTrack, private readonly lights: EffectLights, atlas?: Texture | null) {
    this.vapor = vaporRoot.getObjectByName('VaporBillboards') as InstancedMesh;
    this.vaporMaterial = (this.vapor.material as ShaderMaterial).clone();
    this.vaporMaterial.uniforms.xr = FX_XR;   // clone() copies uniforms; keep the shared XR flag linked
    this.vapor.material = this.vaporMaterial;
    if (atlas) {
      atlas.colorSpace = NoColorSpace;
      this.vaporMaterial.uniforms.atlas.value = atlas;
      this.vaporMaterial.uniforms.useAtlas.value = 1;
    }
    this.vapor.geometry = this.vapor.geometry.clone();
    this.seedAttr = this.vapor.geometry.getAttribute('cloudSeed') as InstancedBufferAttribute;
    this.opacityAttr = this.vapor.geometry.getAttribute('cloudOpacity') as InstancedBufferAttribute;
    this.lightAttr = this.vapor.geometry.getAttribute('cloudLight') as InstancedBufferAttribute;
    this.liftJets = thrusters.children.filter((child) => child.name.startsWith('LiftJet_'));
    this.sideJets = thrusters.children.filter((child) => child.name.startsWith('SideJet_'));
    const cloneOn = (name: string): ShaderMaterial => {
      const source = (thrusters.getObjectByName(name) as Mesh).material as ShaderMaterial;
      const clone = source.clone();
      clone.uniforms.time = FX_TIME;
      thrusters.traverse((part) => { if (part instanceof Mesh && part.material === source) part.material = clone; });
      return clone;
    };
    this.coreMaterial = cloneOn('JetCore');
    this.plumeMaterial = cloneOn('JetPlume');
    this.nozzleGlows = thrusters.getObjectByName('NozzleGlows') as InstancedMesh;
    const down = new Vector3(0, -1, 0);
    this.liftJets.forEach((jet, i) => {
      const plume = this.plumeMaterial.clone(); plume.uniforms.time = FX_TIME;
      const core = this.coreMaterial.clone(); core.uniforms.time = FX_TIME;
      (jet.children[0] as Mesh).material = plume; (jet.children[1] as Mesh).material = core;
      this.jetPlumes.push(plume); this.jetCores.push(core);
      // the jet meshes exhaust along their local -Y: point that along the canted nozzle axis
      jet.quaternion.setFromUnitVectors(down, this.exhaust[i]);
    });
    this.sideJets.forEach((jet, i) => {
      const plume = this.plumeMaterial.clone(); plume.uniforms.time = FX_TIME;
      const core = this.coreMaterial.clone(); core.uniforms.time = FX_TIME;
      (jet.getObjectByName('JetPlume') as Mesh).material = plume; (jet.getObjectByName('JetCore') as Mesh).material = core;
      plume.uniforms.flare.value = 0; plume.uniforms.free.value = 1;
      this.sidePlumes.push(plume); this.sideCores.push(core);
      jet.quaternion.setFromUnitVectors(down, this.sideExhaust[i]);
    });
    const sparks = vaporRoot.getObjectByName('Sparks') as InstancedMesh;
    const splash = vaporRoot.getObjectByName('JetSplash') as InstancedMesh;
    this.sparkMaterial = (sparks.material as ShaderMaterial).clone(); sparks.material = this.sparkMaterial;
    this.splashMaterial = (splash.material as ShaderMaterial).clone(); splash.material = this.splashMaterial;
    sparks.geometry = sparks.geometry.clone(); splash.geometry = splash.geometry.clone();
    this.ownedGeometries.push(sparks.geometry, splash.geometry);
    this.splashGlow = vaporRoot.getObjectByName('SplashGlow') as Mesh;
    this.splashGlowMaterial = (this.splashGlow.material as ShaderMaterial).clone();
    this.splashGlow.material = this.splashGlowMaterial;
    this.bakeEmission(new TrackPlayer(track));
    this.bakeStreaks(new TrackPlayer(track), sparks, splash);
  }

  /** Scale particle work down inside XR (Quest budget). */
  setQuality(quality: number): void { this.quality = quality; }

  private bakeEmission(track: TrackPlayer): void {
    // Jet vapor is emitted in proportion to thrust times ground proximity: inverse-CDF sampling.
    const t0 = 9.9, t1 = 11.5, steps = 400; // while the plumes reach the ground
    const cdf = new Float32Array(steps + 1);
    for (let s = 1; s <= steps; s++) {
      const t = t0 + (t1 - t0) * s / steps;
      track.evaluate(t);
      const proximity = Math.pow(Math.max(0, 1 - track.position.y / 5.5), 1.1);
      this.temp.set(0, 1, 0).applyQuaternion(track.quaternion);
      cdf[s] = cdf[s - 1] + track.lift * smooth(0.68, 0.82, this.temp.y) * smooth(9.75, 10.05, t) * proximity + 0.002;
    }
    const sampleTime = (u: number): number => {
      const target = u * cdf[steps];
      let lo = 0, hi = steps;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (cdf[mid] < target) lo = mid + 1; else hi = mid; }
      return t0 + (t1 - t0) * lo / steps;
    };
    for (let i = 0; i < VAPOR_COUNT; i++) {
      const seed = random(i + 1), angle = random(i + 31) * Math.PI * 2, r2 = random(i + 57);
      this.seeds[i] = random(i + 401);
      let time: number, speed: number;
      if (i < MAIN_PARTICLES) {
        time = sampleTime((i + random(i + 7)) / MAIN_PARTICLES);
        speed = 5 + r2 * 8;
        this.life[i] = 7 + seed * 5;
      } else if (i < JET_PARTICLES) {
        // Touchdown burst: half hug the ground and race outward, half (tall) billow up around the car.
        time = seed > 0.42 ? 11.0 + random(i + 3) * 0.45 : TOUCHDOWN - 0.35 + random(i + 3) * 0.5;
        speed = seed > 0.42 ? 1.2 + r2 * 3.2 : 9 + r2 * 10;
        this.life[i] = 6.5 + seed * 4;
      } else {
        const k = i - JET_PARTICLES;
        time = TOUCHDOWN + 0.05 + (k / TIRE_SMOKE_COUNT) * 1.6 + random(i + 3) * 0.05;
        speed = 0.4 + r2 * 0.8;
        this.life[i] = 2.5 + seed * 2;
      }
      this.emitTime[i] = time;
      // Tall touchdown billows are centred where the car sits just after touchdown, so they swallow it.
      const tallBurst = i >= MAIN_PARTICLES && i < JET_PARTICLES && seed > 0.42;
      track.evaluate(tallBurst ? 11.72 : time);
      let x = track.position.x, z = track.position.z;
      if (i >= JET_PARTICLES) {
        this.temp.set(-1.35, 0.3, (i % 2 ? 1 : -1) * 0.8).applyQuaternion(track.quaternion);
        x += this.temp.x; z += this.temp.z;
      } else {
        if (i < MAIN_PARTICLES) {
          // Descent vapor is born at the plume impact points under the four corner nozzles.
          const n = DEFAULT_NOZZLES[i % 4];
          this.temp.set(n[0], 0, n[2]).applyQuaternion(track.quaternion);
          x += this.temp.x + (random(i + 91) - 0.5) * 0.7; z += this.temp.z + (random(i + 93) - 0.5) * 0.7;
        } else {
          const jitter = tallBurst ? 2.0 : 1.0;
          x += (random(i + 91) - 0.5) * 2.4 * jitter; z += (random(i + 93) - 0.5) * 1.8 * jitter;
        }
      }
      this.emitPos[i * 3] = x; this.emitPos[i * 3 + 1] = i >= JET_PARTICLES ? 0.25 : i < MAIN_PARTICLES ? 0.15 + seed * 0.3 : 0.25 + seed * 0.5; this.emitPos[i * 3 + 2] = z;
      // spread is mostly sideways out of the lane and forward along the motion
      const vx = Math.cos(angle) * speed * 0.75, vz = Math.sin(angle) * speed;
      this.emitVel[i * 3] = vx; this.emitVel[i * 3 + 1] = 0; this.emitVel[i * 3 + 2] = vz;
    }
  }

  private bakeStreaks(track: TrackPlayer, sparks: InstancedMesh, splash: InstancedMesh): void {
    const fill = (mesh: InstancedMesh, count: number, spark: boolean): void => {
      const origin = mesh.geometry.getAttribute('origin') as InstancedBufferAttribute;
      const velocity = mesh.geometry.getAttribute('velocity') as InstancedBufferAttribute;
      const birth = mesh.geometry.getAttribute('birth') as InstancedBufferAttribute;
      for (let i = 0; i < count; i++) {
        const seed = random(i * 3 + (spark ? 7 : 911)), a = random(i * 5 + (spark ? 13 : 517)) * Math.PI * 2, s2 = random(i * 7 + (spark ? 29 : 233));
        if (spark) {
          const t = TOUCHDOWN - 0.02 + seed * 0.32;
          track.evaluate(t);
          const wheel = i % 4;
          this.temp.set(wheel < 2 ? 1.05 : -1.05, 0.05, wheel % 2 ? 0.55 : -0.55).applyQuaternion(track.quaternion);
          origin.setXYZ(i, track.position.x + this.temp.x, 0.06, track.position.z + this.temp.z);
          const speed = 5 + s2 * 9;
          velocity.setXYZ(i, -9 + Math.cos(a) * speed * 0.5, 1.5 + s2 * 4.5, Math.sin(a) * speed * 0.6);
          birth.setXYZ(i, t, 0.35 + random(i + 77) * 0.6, 0.6 + random(i + 99) * 0.6);
        } else {
          const t = 9.6 + (i / count) * 2.05 + seed * 0.01;
          track.evaluate(t);
          const altitude = track.position.y;
          this.temp.set(0, 1, 0).applyQuaternion(track.quaternion);
          const energy = track.lift * smooth(0.68, 0.82, this.temp.y) * smooth(9.75, 10.05, t) * Math.max(0, 1 - altitude / 4.5);
          const n = this.nozzles[i % 4];
          this.temp.copy(n).applyQuaternion(track.quaternion);
          origin.setXYZ(i, track.position.x + this.temp.x, 0.08 + seed * 0.15, track.position.z + this.temp.z);
          const speed = 9 + s2 * 10;
          velocity.setXYZ(i, Math.cos(a) * speed, 0, Math.sin(a) * speed);
          birth.setXYZ(i, t, 0.35 + random(i + 41) * 0.35, energy);
        }
      }
      origin.needsUpdate = velocity.needsUpdate = birth.needsUpdate = true;
    };
    fill(sparks, SPARK_COUNT, true);
    fill(splash, SPLASH_COUNT, false);
  }

  update(time: number, car: TrackPlayer, camera: Object3D): void {
    this.offset.copy(this.vaporRoot.position);
    this.thrusters.position.copy(car.position).add(this.offset);
    this.thrusters.quaternion.copy(car.quaternion);
    this.updateJets(time, car);
    this.updateVapor(time, car, camera);
    this.sparkMaterial.uniforms.time.value = time;
    this.splashMaterial.uniforms.time.value = time;
    this.impact = time >= TOUCHDOWN ? Math.exp(-(time - TOUCHDOWN) * 3.2) : 0;
  }

  private updateJets(time: number, car: TrackPlayer): void {
    const altitude = car.position.y;
    // Plume shimmer stays subtle and slow enough not to strobe at display rates; the light that
    // reaches the car and ground only breathes, so the scene lighting never flickers.
    const flicker = 0.97 + 0.02 * Math.sin(time * 23) + 0.01 * Math.sin(time * 37.7);
    const glow = 0.985 + 0.015 * Math.sin(time * 6.3);
    this.carDown.set(0, -1, 0).applyQuaternion(car.quaternion);
    // Physics-solved firing: each corner nozzle runs at its own thrust, including while the car is
    // upside down (its nozzles then point at the sky and one side fires to roll the car over).
    const lift = car.lift > 0.01 ? car.lift : 0;
    this.thrust = lift;
    this.liftNow = lift;
    let touchesAll = 0;
    for (let i = 0; i < this.liftJets.length; i++) {
      const jet = this.liftJets[i];
      const t = car.nozzle[i];
      jet.visible = t > 0.02;
      if (!jet.visible) continue;
      this.exhaustWorld.copy(this.exhaust[i]).applyQuaternion(car.quaternion);
      this.nozzleWorld.copy(this.nozzles[i]).applyQuaternion(car.quaternion).add(car.position);
      // grounded when the exhaust heads down and the pad is within the jet's reach
      const toGround = this.exhaustWorld.y < -0.2 ? (this.nozzleWorld.y + 0.05) / -this.exhaustWorld.y : Infinity;
      // 1.5-3 car widths at full thrust (overhead d001-d007), breathing slowly with the gas flow
      const freeLength = (1.8 + 2.8 * t) * (0.94 + 0.06 * Math.sin(time * 3.1 + i * 1.7));
      const grounded = toGround < freeLength + 1.5 ? 1 : 0;
      const length = grounded ? Math.max(0.5, toGround) : freeLength;
      touchesAll += grounded * t;
      // grounded columns are wide and dense; free jets start thin and fan out in the shader
      const w = grounded ? 1.35 + t * 0.6 : 0.8 + t * 0.3;
      jet.scale.set(w, 1, w);
      const plume = jet.children[0], core = jet.children[1];
      plume.scale.set(1, length, 1);
      core.scale.set(1, Math.min(length, 0.6 + 1.0 * t), 1);
      this.jetPlumes[i].uniforms.intensity.value = t * flicker;
      this.jetPlumes[i].uniforms.length.value = length;
      this.jetPlumes[i].uniforms.flare.value = grounded;
      this.jetPlumes[i].uniforms.free.value = 1 - grounded;
      // cold-gas jets have no hot core: only a faint condensation glint at the nozzle when free
      this.jetCores[i].uniforms.intensity.value = t * flicker * (0.15 + 0.45 * grounded);
      this.jetCores[i].uniforms.length.value = 1.6;
    }
    const touches = Math.min(1, touchesAll / Math.max(1e-3, lift * 4));
    // Side (yaw) thrusters: short sharp pulses straight out of the front corners, always free jets.
    for (let i = 0; i < this.sideJets.length; i++) {
      const jet = this.sideJets[i];
      const t = car.side[i];
      jet.visible = t > 0.02;
      if (!jet.visible) continue;
      const length = (2.4 + 1.4 * t) * (0.95 + 0.05 * Math.sin(time * 4.3 + i * 2.1));
      jet.scale.set(0.7 + 0.2 * t, 1, 0.7 + 0.2 * t);
      (jet.children[0] as Object3D).scale.set(1, length, 1);
      (jet.children[1] as Object3D).scale.set(1, Math.min(length, 0.5 + 0.6 * t), 1);
      this.sidePlumes[i].uniforms.intensity.value = t * flicker * 1.1;
      this.sidePlumes[i].uniforms.length.value = length;
      this.sideCores[i].uniforms.intensity.value = t * flicker * 0.18;
      this.sideCores[i].uniforms.length.value = 0.9;
    }
    // Nozzle glows, sized by each nozzle's thrust (four floor nozzles, then the two side nozzles).
    for (let i = 0; i < 6; i++) {
      const side = i >= 4;
      const k = side ? car.side[i - 4] * 0.7 : car.nozzle[i];
      if (side) this.position.copy(this.sideNozzles[i - 4]).addScaledVector(this.sideExhaust[i - 4], 0.08);
      else this.position.copy(this.nozzles[i]).addScaledVector(this.exhaust[i], 0.12);
      this.matrix.compose(this.position, this.identity, this.scale.setScalar(k > 0.01 ? (0.25 + k * 0.35) * flicker : 0));
      this.nozzleGlows.setMatrixAt(i, this.matrix);
    }
    this.nozzleGlows.instanceMatrix.needsUpdate = true;
    // Jet light sits well below the car so it lights the plumes and ground rather than the floor pan.
    this.position.copy(this.carDown).multiplyScalar(Math.min(3, altitude * 0.6 + 0.8)).add(car.position).add(this.offset);
    this.lights.lift.position.copy(this.position);
    this.lights.lift.intensity = lift * glow * 80;
    // Ground splash glow only where a plume actually reaches the ground.
    const ground = lift * touches;
    this.splashGlow.visible = ground > 0.01;
    this.splashGlow.position.set(car.position.x, 0.025, car.position.z);
    const r = 2.4 + altitude * 0.5;
    this.splashGlow.scale.set(r * 2.2, r * 1.6, 1);
    this.splashGlowMaterial.uniforms.intensity.value = ground * glow * 0.8;
  }

  private updateVapor(time: number, car: TrackPlayer, camera: Object3D): void {
    camera.getWorldQuaternion(this.billboard);
    camera.getWorldPosition(this.cameraPosition);
    camera.getWorldDirection(this.cameraForward);
    this.vaporMaterial.uniforms.time.value = time;
    const lift = this.liftNow;
    const carX = car.position.x, carY = car.position.y, carZ = car.position.z;
    const onGround = time > TOUCHDOWN;
    const stride = this.quality < 1 ? 2 : 1;
    let active = 0;
    for (let i = 0; i < VAPOR_COUNT; i += stride) {
      const age = time - this.emitTime[i];
      const life = this.life[i];
      if (age <= 0 || age >= life) continue;
      const seed = random(i + 1);
      const smoke = i >= JET_PARTICLES;
      const burst = i >= MAIN_PARTICLES && !smoke;
      const k = burst ? 0.9 : 1.15;
      const spread = (1 - Math.exp(-k * age)) / k;
      let x = this.emitPos[i * 3] + this.emitVel[i * 3] * spread + 0.32 * age;
      let z = this.emitPos[i * 3 + 2] + this.emitVel[i * 3 + 2] * spread + 0.18 * age;
      let y: number, s: number, a: number;
      if (smoke) {
        y = this.emitPos[i * 3 + 1] + 0.5 * age + seed * 0.4;
        s = 0.45 + age * 0.75 + seed * 0.3;
        a = 0.28 * Math.min(1, age * 6) * Math.pow(1 - age / life, 1.5);
      } else {
        const tall = burst && seed > 0.42;
        const rise = tall ? 1.6 + seed * 2.8 : burst ? 0.3 + seed * 0.8 : 0.6 + seed * 2.0;
        y = this.emitPos[i * 3 + 1] + rise * (1 - Math.exp(-(tall ? 1.4 : 0.55) * age)) + 0.28 * age;
        const s0 = tall ? 1.5 + seed * 1.3 : burst ? 1.1 + seed * 1.0 : 0.9 + seed * 1.4;
        s = s0 * (1 + 1.5 * (1 - Math.exp(-0.9 * age)) + 0.14 * age);
        const fadeIn = Math.min(1, age * 5);
        const fadeOut = Math.min(1, (life - age) / 2.5);
        a = (tall ? 0.3 : burst ? 0.24 : 0.21) * fadeIn * fadeOut * fadeOut * Math.exp(-0.05 * age);
      }
      // The car parts the cloud as it drives through it.
      if (onGround) {
        const dx = x - carX, dz = z - carZ;
        const d = Math.sqrt(dx * dx + dz * dz) + 1e-4;
        if (d < 4) { const push = (4 - d) * 0.55; x += dx / d * push; z += dz / d * push; }
      }
      // Keep the car readable: thin puffs hugging the car and those between the lens and the car.
      // At touchdown the car is partly enveloped; over the next second it emerges as the cloud clears around it.
      if (time > 10.4) {
        // Swallowed at touchdown (~11.3-12.0 s), then the car drives out of it.
        const emerge = this.forceClear && time > 12.0 ? 1 : smooth(12.0, 12.9, time);
        a *= 1 - emerge + emerge * this.carClearance(x, y, z, s, carX, carY + 0.7, carZ);
      }
      this.px[active] = x; this.py[active] = y; this.pz[active] = z; this.size[active] = s; this.alpha[active] = a;
      // lighting terms
      const jdx = x - carX, jdy = y - carY, jdz = z - carZ;
      const jd = Math.sqrt(jdx * jdx + jdy * jdy + jdz * jdz);
      const jet = lift * Math.exp(-jd / 3.0) * 3.2;
      const inner = lift * Math.exp(-jd / 1.6) * 1.2;
      const edge = Math.abs(z);
      const red = (0.22 + 1.3 * Math.exp(-Math.abs(8 - edge) / 3.0)) * Math.exp(-Math.max(0, y) / 1.8);
      const lx = x + 56, lz = z + 4;
      const lit = 0.32 + 0.75 * Math.exp(-Math.sqrt(lx * lx + lz * lz) / 18);
      const o = active * 4;
      this.lightScratch[o] = jet; this.lightScratch[o + 1] = red; this.lightScratch[o + 2] = lit; this.lightScratch[o + 3] = inner;
      this.depth[active] = (x + this.offset.x - this.cameraPosition.x) * this.cameraForward.x + (y - this.cameraPosition.y) * this.cameraForward.y + (z + this.offset.z - this.cameraPosition.z) * this.cameraForward.z;
      // far puffs first: larger depth -> smaller key (1 mm resolution, 10-bit index; VAPOR_COUNT <= 1024)
      this.sortKeys[active] = Math.min(2097151, Math.max(0, Math.round((2000 - this.depth[active]) * 1000))) * 1024 + active;
      this.seedScratch[active] = this.seeds[i];
      active++;
    }
    // Back-to-front: native numeric sort of the packed keys (no comparator, no allocation); unused
    // slots are filled with the maximum key so they sort to the end.
    this.sortKeys.fill(0xffffffff, active);
    this.sortKeys.sort();
    for (let n = 0; n < active; n++) {
      const p = this.sortKeys[n] & 1023;
      this.position.set(this.px[p], this.py[p], this.pz[p]);
      // ground-hugging puffs spread flat into a low skirt; higher puffs stay rounder
      const skirt = Math.max(0, 1 - this.py[p] / 1.2);
      this.scale.set(this.size[p] * (1.45 + skirt * 0.9), this.size[p] * (0.8 - skirt * 0.3), 1);
      this.matrix.compose(this.position, this.billboard, this.scale);
      this.vapor.setMatrixAt(n, this.matrix);
      this.opacityAttr.setX(n, this.alpha[p]);
      this.seedAttr.setX(n, this.seedScratch[p]);
      this.lightAttr.setXYZW(n, this.lightScratch[p * 4], this.lightScratch[p * 4 + 1], this.lightScratch[p * 4 + 2], this.lightScratch[p * 4 + 3]);
    }
    this.vapor.count = active;
    this.vapor.instanceMatrix.needsUpdate = true;
    this.opacityAttr.needsUpdate = true;
    this.seedAttr.needsUpdate = true;
    this.lightAttr.needsUpdate = true;
  }

  /** 0.12..1 opacity factor for a puff (track-local) relative to the car and the camera->car sight line. */
  private carClearance(x: number, y: number, z: number, size: number, cx: number, cy: number, cz: number): number {
    const dx = x - cx, dy = y - cy, dz = z - cz;
    let k = smooth(0.8 + size * 0.35, 3.2 + size * 0.6, Math.sqrt(dx * dx + dy * dy + dz * dz));
    // sight line from the camera (world) to the car (world)
    const camX = this.cameraPosition.x - this.offset.x, camY = this.cameraPosition.y, camZ = this.cameraPosition.z - this.offset.z;
    const sx = cx - camX, sy = cy - camY, sz = cz - camZ;
    const len2 = sx * sx + sy * sy + sz * sz;
    if (len2 > 1e-4) {
      const t = ((x - camX) * sx + (y - camY) * sy + (z - camZ) * sz) / len2;
      if (t > 0 && t < 1) {
        const qx = camX + sx * t - x, qy = camY + sy * t - y, qz = camZ + sz * t - z;
        k = Math.min(k, smooth(size * 0.45, size * 0.45 + 2.4, Math.sqrt(qx * qx + qy * qy + qz * qz)));
      }
    }
    return 0.12 + 0.88 * k;
  }

  private readonly seedScratch = new Float32Array(VAPOR_COUNT);
  private readonly seeds = new Float32Array(VAPOR_COUNT);

  dispose(): void {
    this.vapor.geometry.dispose(); this.vaporMaterial.dispose();
    for (const geometry of this.ownedGeometries) geometry.dispose();
    for (const material of [this.coreMaterial, this.plumeMaterial, this.sparkMaterial, this.splashMaterial, this.splashGlowMaterial, ...this.jetPlumes, ...this.jetCores, ...this.sidePlumes, ...this.sideCores]) material.dispose();
  }
}
