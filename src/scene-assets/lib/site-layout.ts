/**
 * Shared, deterministic layout of the McGregor ramp site in TRACK-LOCAL meters
 * (lane centre on z = 0, car approaches along +X, ramp foot at x = 0, landing
 * near x = -58). Every stage asset is placed at the same scene offset, so these
 * coordinates line up across the ramp, apron, fixtures and the runtime effects.
 *
 * Pure data only: imported by the asset manifest (two realms) and by systems.
 */

export type Vec3 = readonly [number, number, number];

export const SITE_OFFSET: Vec3 = [12, 0, -34];

/** Red LED boundary lines either side of the lane. */
export const LANE = { halfWidth: 8, start: -160, end: 14, footlightSpacing: 4 } as const;

/** Mast light towers. The four with `real` also exist as SpotLights in the scene JSON. */
export interface Tower { base: Vec3; height: number; aim: Vec3; lamps: number; beamLength: number; beamAngle: number; real: boolean }
export const TOWERS: readonly Tower[] = [
  { base: [-50, 0, -18], height: 13, aim: [-58, 0, -1], lamps: 6, beamLength: 26, beamAngle: 0.5, real: true },
  { base: [-14, 0, 15], height: 12, aim: [-4, 0.5, 0], lamps: 6, beamLength: 24, beamAngle: 0.46, real: true },
  { base: [-92, 0, -17], height: 11, aim: [-96, 0, 0], lamps: 4, beamLength: 20, beamAngle: 0.45, real: false },
  { base: [26, 0, 14], height: 12, aim: [9, 12, 0], lamps: 4, beamLength: 28, beamAngle: 0.32, real: false },
];

/** Ground uplights washing the ramp face (also real SpotLights). */
export const RAMP_WASH: readonly { pos: Vec3; aim: Vec3 }[] = [
  { pos: [-6, 0.6, 6.5], aim: [7, 9, 0] },
  { pos: [-6, 0.6, -6.5], aim: [7, 9, 0] },
];

/**
 * Low tripod flood banks, the bright white "glare" lights seen at lane level in
 * the broadcast. They aim across the lane toward the camera side.
 */
export interface FloodBank { pos: Vec3; aim: Vec3 }
export const FLOOD_BANKS: readonly FloodBank[] = [
  { pos: [-66, 1.6, -12.5], aim: [-60, 0, 6] },
  { pos: [-42, 1.6, -12.5], aim: [-48, 0, 6] },
  { pos: [4, 1.6, -12.5], aim: [-4, 0, 4] },
  { pos: [-118, 1.6, 12.5], aim: [-112, 0, -6] },
];

/** Searchlights raking the sky behind the site. */
export const SKY_BEAMS: readonly { pos: Vec3; dir: Vec3; length: number }[] = [
  { pos: [44, 0, -60], dir: [-0.25, 1, 0.12], length: 150 },
  { pos: [-150, 0, -70], dir: [0.3, 1, 0.05], length: 150 },
];

