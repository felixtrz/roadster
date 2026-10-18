/**
 * Light-emitting set dressing for the ramp site: mast light towers, tripod
 * flood banks, ramp uplights and sky searchlights. Each fixture has real
 * geometry, HDR lenses, a camera-facing halo and a volumetric beam cone.
 * The matching real SpotLights live in the scene JSON (towers 0-1, ramp wash).
 *
 * Placed at SITE_OFFSET, so coordinates are track-local.
 */
import { BoxGeometry, CylinderGeometry, Group, InstancedMesh, Matrix4, Mesh, MeshStandardMaterial, Quaternion, Vector3 } from '@iwsdk/core';
import { createBeams, createGlowSprites, emitter, type BeamSpec, type GlowSpec } from './lib/fx-materials.js';
import { FLOOD_BANKS, RAMP_WASH, SKY_BEAMS, TOWERS } from './lib/site-layout.js';

const housing = new MeshStandardMaterial({ color: '#2a2f36', roughness: 0.45, metalness: 0.7 });
const mastMaterial = new MeshStandardMaterial({ color: '#7d838b', roughness: 0.5, metalness: 0.6 });
const trailerMaterial = new MeshStandardMaterial({ color: '#202328', roughness: 0.7, metalness: 0.3 });
const lens = emitter(2.4, 2.55, 2.7);
const box = new BoxGeometry(1, 1, 1);
const FORWARD = new Vector3(0, 0, 1);

class Batcher {
  private readonly items = new Map<MeshStandardMaterial | ReturnType<typeof emitter>, Matrix4[]>();
  add(material: MeshStandardMaterial | ReturnType<typeof emitter>, position: Vector3, quaternion: Quaternion, scale: Vector3): void {
    const list = this.items.get(material) ?? [];
    list.push(new Matrix4().compose(position, quaternion, scale));
    this.items.set(material, list);
  }
  span(material: MeshStandardMaterial, a: Vector3, b: Vector3, width: number): void {
    const dir = b.clone().sub(a);
    const q = new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), dir.clone().normalize());
    this.add(material, a.clone().lerp(b, 0.5), q, new Vector3(width, dir.length(), width));
  }
  build(root: Group, name: string): void {
    let k = 0;
    for (const [material, matrices] of this.items) {
      const mesh = new InstancedMesh(box, material, matrices.length);
      mesh.name = `${name}-${k++}`;
      matrices.forEach((m, i) => mesh.setMatrixAt(i, m));
      mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere();
      root.add(mesh);
    }
  }
}

/** Builds a lamp head: a grid of housings facing `dir`, each with an HDR lens and a halo. */
function lampHead(batch: Batcher, glows: GlowSpec[], center: Vector3, dir: Vector3, columns: number, rows: number, pitch: number, glowSize: number): void {
  const q = new Quaternion().setFromUnitVectors(FORWARD, dir.clone().normalize());
  const right = new Vector3(1, 0, 0).applyQuaternion(q);
  const up = new Vector3(0, 1, 0).applyQuaternion(q);
  const forward = dir.clone().normalize();
  batch.add(housing, center.clone().addScaledVector(forward, -0.22), q, new Vector3(columns * pitch + 0.2, rows * pitch + 0.2, 0.12));
  for (let c = 0; c < columns; c++) for (let r = 0; r < rows; r++) {
    const p = center.clone().addScaledVector(right, (c - (columns - 1) / 2) * pitch).addScaledVector(up, (r - (rows - 1) / 2) * pitch);
    batch.add(housing, p, q, new Vector3(pitch * 0.9, pitch * 0.9, 0.3));
    batch.add(lens, p.clone().addScaledVector(forward, 0.16), q, new Vector3(pitch * 0.72, pitch * 0.72, 0.02));
    glows.push({ position: p.clone().addScaledVector(forward, 0.2), size: glowSize * 0.8, color: [1.0, 1.0, 1.0], streak: 0.06 });
  }
}

export function createSiteLights(): Group {
  const root = new Group(); root.name = 'SiteLights';
  const batch = new Batcher();
  const glows: GlowSpec[] = [];
  const beams: BeamSpec[] = [];
  const skyBeams: BeamSpec[] = [];

  for (const tower of TOWERS) {
    const base = new Vector3(...tower.base);
    const head = base.clone(); head.y = tower.height;
    batch.span(mastMaterial, base, head.clone().setY(tower.height - 0.4), 0.22);
    // trailer + outriggers
    batch.add(trailerMaterial, base.clone().setY(0.75), new Quaternion(), new Vector3(3.2, 1.1, 1.7));
    batch.add(housing, base.clone().setY(0.18), new Quaternion(), new Vector3(3.8, 0.12, 0.2));
    batch.add(housing, base.clone().setY(0.18), new Quaternion(), new Vector3(0.2, 0.12, 3.4));
    const aim = new Vector3(...tower.aim);
    const dir = aim.clone().sub(head).normalize();
    batch.add(mastMaterial, head.clone(), new Quaternion().setFromUnitVectors(FORWARD, new Vector3(dir.x, 0, dir.z).normalize()), new Vector3(2.8, 0.12, 0.12));
    const columns = tower.lamps / 2;
    lampHead(batch, glows, head, dir, columns, 2, 0.62, 1.9);
    glows.push({ position: head.clone().setY(tower.height + 0.9), size: 0.6, color: [1.0, 0.05, 0.05], blink: 0.45, streak: 0 });
    beams.push({ origin: head.clone().addScaledVector(dir, 0.3), dir, length: tower.beamLength, halfAngle: tower.beamAngle * 0.8, strength: 0.15 });
  }

  for (const bank of FLOOD_BANKS) {
    const pos = new Vector3(...bank.pos);
    const aim = new Vector3(...bank.aim);
    const dir = aim.clone().sub(pos).normalize();
    for (let k = 0; k < 3; k++) {
      const a = k * Math.PI * 2 / 3 + 0.4;
      batch.span(mastMaterial, pos.clone().setY(pos.y - 0.3), new Vector3(pos.x + Math.cos(a) * 0.9, 0, pos.z + Math.sin(a) * 0.9), 0.05);
    }
    lampHead(batch, glows, pos, dir, 3, 2, 0.42, 1.25);
    beams.push({ origin: pos.clone().addScaledVector(dir, 0.25), dir, length: 16, halfAngle: 0.42, strength: 0.1 });
  }

  for (const wash of RAMP_WASH) {
    const pos = new Vector3(...wash.pos);
    const dir = new Vector3(...wash.aim).sub(pos).normalize();
    batch.add(housing, pos.clone().setY(0.25), new Quaternion(), new Vector3(1.2, 0.5, 1.2));
    lampHead(batch, glows, pos.clone().setY(0.75), dir, 2, 2, 0.45, 1.4);
    beams.push({ origin: pos.clone().setY(0.8), dir, length: 22, halfAngle: 0.36, strength: 0.08 });
  }

  for (const sky of SKY_BEAMS) {
    const pos = new Vector3(...sky.pos);
    const dir = new Vector3(...sky.dir).normalize();
    batch.add(housing, pos.clone().setY(0.6), new Quaternion(), new Vector3(1.4, 1.2, 1.4));
    glows.push({ position: pos.clone().setY(1.4), size: 2.4, color: [0.9, 0.95, 1.0], streak: 0.05 });
    skyBeams.push({ origin: pos.clone().setY(1.3), dir, length: sky.length, halfAngle: 0.03, strength: 0.11 });
  }

  batch.build(root, 'Fixtures');
  // generators hum quietly beside each tower trailer
  const exhaust = new Mesh(new CylinderGeometry(0.06, 0.06, 0.8, 8), housing);
  exhaust.name = 'TrailerExhaust'; exhaust.position.set(TOWERS[0].base[0] + 1.2, 1.6, TOWERS[0].base[2]); root.add(exhaust);
  root.add(createBeams('FloodBeams', [0.85, 0.92, 1.0], beams));
  root.add(createBeams('SkyBeams', [0.7, 0.8, 1.0], skyBeams));
  root.add(createGlowSprites('FixtureGlows', glows));
  return root;
}
