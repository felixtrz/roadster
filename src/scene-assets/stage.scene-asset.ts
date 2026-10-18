import {
  AdditiveBlending, BoxGeometry, BufferGeometry, DoubleSide, Float32BufferAttribute, Group, InstancedMesh, Mesh,
  MeshBasicMaterial, MeshStandardMaterial, PlaneGeometry, ShaderChunk, ShaderMaterial, Vector3,
} from '@iwsdk/core';
import { alignSpan } from './lib/hardsurface.js';
import { createGlowSprites, emitter, FX_TIME, NOISE_GLSL, type GlowSpec } from './lib/fx-materials.js';
import { FLOOD_BANKS, LANE } from './lib/site-layout.js';

const deckMaterial = new MeshStandardMaterial({ color: '#a7aaac', roughness: 0.8, metalness: 0.0 });
const deckUnderMaterial = new MeshStandardMaterial({ color: '#8d9194', roughness: 0.8, metalness: 0.1 });
const steelMaterial = new MeshStandardMaterial({ color: '#59606a', emissive: '#0e1013', roughness: 0.38, metalness: 0.75 });
const darkSteelMaterial = new MeshStandardMaterial({ color: '#1d2126', roughness: 0.5, metalness: 0.6 });
const redLed = emitter(2.6, 0.06, 0.1);
const redLedSoft = emitter(1.5, 0.03, 0.06);
const stripeMaterial = new MeshStandardMaterial({ color: '#f2f3f4', emissive: '#30343a', roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
const beamGeometry = new BoxGeometry(1, 1, 1);

deckMaterial.onBeforeCompile = (shader) => {
  shader.vertexShader = 'varying vec2 deckUv;\n' + shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n deckUv = uv;');
  shader.fragmentShader = `varying vec2 deckUv;\n${NOISE_GLSL}\n` + shader.fragmentShader;
  shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', `#include <color_fragment>
    float lat = deckUv.x, arc = deckUv.y;
    vec2 p = vec2(lat, arc);
    float mottling = .55 * fxNoise2(p * 1.3) + .3 * fxNoise2(p * 6.0) + .15 * fxNoise2(p * 31.0);
    diffuseColor.rgb *= .6 + mottling * .62;
    diffuseColor.rgb *= .85 + .3 * fxNoise2(p * vec2(.6, .15));
    // formwork panel seams: every 2.4 m along the arc and a construction joint either side of centre
    float aa = fwidth(arc) * 1.5 + .004;
    float seam = 1. - smoothstep(.03, aa + .07, abs(fract(arc / 2.4 + .5) - .5) * 2.4);
    diffuseColor.rgb *= .93 + .14 * fxHash2(vec2(floor(arc / 2.4), step(0., lat)));
    float joint = 1. - smoothstep(.0, fwidth(lat) * 1.5 + .01, abs(abs(lat) - .99));
    diffuseColor.rgb *= 1. - .6 * max(seam, joint * .7);
    // rubber laid down by the tyres along both wheel tracks
    float tk = (abs(lat) - .8) / .18; float track = exp(-tk * tk);
    float rubber = track * (.35 + .65 * fxNoise2(vec2(lat * 9., arc * .35))) * smoothstep(.3, 4., arc);
    diffuseColor.rgb *= 1. - .55 * rubber;
    // water stains streaking down the curve
    float streaks = smoothstep(.62, .9, fxNoise2(vec2(lat * 3.2, arc * .08)));
    diffuseColor.rgb *= 1. - .18 * streaks;`);
  shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
    // soft bounce from the lane LEDs and floods so the curve never collapses to black
    totalEmissiveRadiance += diffuseColor.rgb * vec3(.11, .115, .125) + vec3(.035, 0., .003) * exp(-(1.98 - abs(deckUv.x)) * 6.);`);
};
deckMaterial.customProgramCacheKey = () => 'roadster-ramp-deck-v4';

function span(name: string, a: Vector3, b: Vector3, width: number, material: MeshStandardMaterial | MeshBasicMaterial, depth = width): Mesh {
  const beam = new Mesh(beamGeometry, material);
  beam.name = name;
  alignSpan(beam, a, b, new Vector3(0, 0, 1));
  beam.scale.set(width, a.distanceTo(b), depth);
  return beam;
}

const BATCH_NAMES = new Map<MeshStandardMaterial | MeshBasicMaterial, string>([
  [steelMaterial, 'SteelTrusses'], [darkSteelMaterial, 'Fixtures'], [redLed, 'EdgeLighting'], [redLedSoft, 'LedDots'],
]);
function batchSpans(root: Group): void {
  for (const [material, name] of BATCH_NAMES) {
    const spans = root.children.filter((child): child is Mesh => child instanceof Mesh && child.geometry === beamGeometry && child.material === material);
    if (!spans.length) continue;
    const batch = new InstancedMesh(beamGeometry, material, spans.length);
    batch.name = name;
    spans.forEach((part, i) => { part.updateMatrix(); batch.setMatrixAt(i, part.matrix); root.remove(part); });
    batch.instanceMatrix.needsUpdate = true; batch.computeBoundingSphere(); root.add(batch);
  }
}

/** Sweeps a cross-section (pairs of [depth along normal, lateral z]) along the centreline. uv = (lateral, arc length). */
function sweep(center: Vector3[], profile: [number, number][], closed: boolean): BufferGeometry {
  const vertices: number[] = [], uvs: number[] = [], indices: number[] = [];
  const tangent = new Vector3(), normal = new Vector3();
  let arc = 0;
  const ring = profile.length;
  for (let i = 0; i < center.length; i++) {
    if (i > 0) arc += center[i].distanceTo(center[i - 1]);
    tangent.subVectors(center[Math.min(i + 1, center.length - 1)], center[Math.max(i - 1, 0)]).normalize();
    normal.set(-tangent.y, tangent.x, 0);
    for (const [depth, lateral] of profile) {
      vertices.push(center[i].x + normal.x * depth, center[i].y + normal.y * depth, lateral);
      uvs.push(lateral, arc);
    }
    if (i > 0) for (let s = 0; s < (closed ? ring : ring - 1); s++) {
      const a = (i - 1) * ring + s, b = (i - 1) * ring + (s + 1) % ring, c = i * ring + (s + 1) % ring, d = i * ring + s;
      indices.push(a, b, c, a, c, d);
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute(vertices, 3));
  geometry.setAttribute('uv', new Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices); geometry.computeVertexNormals();
  return geometry;
}

/** The curved ramp: textured concrete deck, red LED edges, steel truss with work lights, support tower. */
export function createRamp(centerline: number[][], width: number): Group {
  const ramp = new Group(); ramp.name = 'Ramp';
  const center = centerline.map((p) => new Vector3().fromArray(p));
  const half = width / 2;
  // Driving face (its own vertices so the normals stay true) plus a separate underside/side shell.
  const deck = new Mesh(sweep(center, [[0, half], [0, half * 0.5], [0, 0], [0, -half * 0.5], [0, -half]], false), deckMaterial);
  deck.name = 'DrivingDeck'; deck.receiveShadow = true; ramp.add(deck);
  const shell = new Mesh(sweep(center, [[-0.005, -half], [-0.22, -half - 0.02], [-0.22, half + 0.02], [-0.005, half]], false), deckUnderMaterial);
  shell.name = 'DeckShell'; ramp.add(shell);
  const stripe = new Mesh(sweep(center, [[0.008, 0.11], [0.008, -0.11]], false), stripeMaterial);
  stripe.name = 'LaneStripe'; ramp.add(stripe);

  const tangent = new Vector3(), normal = new Vector3();
  const edges: Vector3[][] = [[], []];
  const arcs: number[] = [0];
  for (let i = 0; i < center.length; i++) {
    if (i > 0) arcs.push(arcs[i - 1] + center[i].distanceTo(center[i - 1]));
    tangent.subVectors(center[Math.min(i + 1, center.length - 1)], center[Math.max(i - 1, 0)]).normalize();
    normal.set(-tangent.y, tangent.x, 0);
    for (let side = 0; side < 2; side++) edges[side].push(new Vector3(center[i].x + normal.x * 0.04, center[i].y + normal.y * 0.04, (side ? 1 : -1) * (half - 0.05)));
  }
  for (let i = 2; i < center.length; i += 2) {
    for (let side = 0; side < 2; side++) ramp.add(span(`EdgeLight-${side}-${i}`, edges[side][i - 2], edges[side][i], 0.06, redLed, 0.03));
  }
  // Discrete LED dots on the outer side faces, plus glow halos so the edge reads at broadcast distance.
  const glows: GlowSpec[] = [];
  let nextDot = 0.3, nextGlow = 0.6;
  for (let i = 1; i < center.length; i++) {
    tangent.subVectors(center[i], center[i - 1]).normalize();
    normal.set(-tangent.y, tangent.x, 0);
    while (arcs[i] >= nextDot) {
      const f = (nextDot - arcs[i - 1]) / Math.max(1e-6, arcs[i] - arcs[i - 1]);
      const p = center[i - 1].clone().lerp(center[i], f).addScaledVector(normal, -0.11);
      for (const side of [-1, 1]) {
        const a = p.clone(); a.z = side * (half + 0.035);
        const b = a.clone().addScaledVector(tangent, 0.07);
        ramp.add(span('LedDot', a, b, 0.05, redLedSoft, 0.02));
      }
      nextDot += 0.45;
    }
    while (arcs[i] >= nextGlow) {
      const f = (nextGlow - arcs[i - 1]) / Math.max(1e-6, arcs[i] - arcs[i - 1]);
      const p = center[i - 1].clone().lerp(center[i], f).addScaledVector(normal, 0.05);
      for (const side of [-1, 1]) glows.push({ position: new Vector3(p.x, p.y, side * (half + 0.02)), size: 0.55, color: [1.0, 0.05, 0.08], streak: 0 });
      nextGlow += 1.35;
    }
  }

  // Triangulated steel box truss on the outside of the curve.
  const ribs: Vector3[][] = [[], []];
  let distanceSinceBrace = 2;
  for (let i = 0; i < center.length; i++) {
    if (i > 0) distanceSinceBrace += center[i].distanceTo(center[i - 1]);
    if (distanceSinceBrace < 1.4 && i < center.length - 1) continue;
    distanceSinceBrace = 0;
    tangent.subVectors(center[Math.min(i + 1, center.length - 1)], center[Math.max(i - 1, 0)]).normalize();
    normal.set(tangent.y, -tangent.x, 0);
    const depth = 0.25 + 1.15 * Math.min(1, center[i].y / 3);
    for (let s = 0; s < 2; s++) {
      const side = s ? 1 : -1;
      const p = center[i].clone(); p.z = side * (half + 0.08);
      const outer = p.clone().addScaledVector(normal, depth); outer.y = Math.max(0.08, outer.y);
      ramp.add(span(`TrussRib-${side}-${i}`, p, outer, 0.1, steelMaterial));
      const previous = ribs[s][ribs[s].length - 1];
      if (previous) {
        ramp.add(span(`TrussSpine-${side}-${i}`, previous, outer, 0.16, steelMaterial));
        ramp.add(span(`TrussDiagonal-${side}-${i}`, previous, p, 0.07, steelMaterial));
      }
      ribs[s].push(outer);
    }
    const a = ribs[0][ribs[0].length - 1], b = ribs[1][ribs[1].length - 1];
    ramp.add(span(`TrussCross-${i}`, a, b, 0.08, steelMaterial));
    if (ribs[0].length > 1 && ribs[0].length % 2 === 0) ramp.add(span(`TrussX-${i}`, ribs[0][ribs[0].length - 2], b, 0.06, steelMaterial));
    if (ribs[0].length % 3 === 0 && center[i].y > 2) {
      // work lights on the truss: a small dark housing with a cool white lamp
      for (const point of [a, b]) {
        const lamp = point.clone().addScaledVector(normal, 0.18);
        ramp.add(span('TrussLamp', point, lamp, 0.22, darkSteelMaterial));
        glows.push({ position: lamp, size: 0.8, color: [0.9, 0.95, 1.0], streak: 0.04 });
      }
    }
  }

  // Support tower behind the vertical section and columns under the overhang.
  const legs: [number, number][] = [[10.9, -2.4], [10.9, 2.4], [13.6, -2.4], [13.6, 2.4]];
  const top = 22.6;
  for (const [x, z] of legs) ramp.add(span('TowerLeg', new Vector3(x, 0, z), new Vector3(x, top, z), 0.22, steelMaterial));
  for (let y = 1.5, k = 0; y < top; y += 3, k++) {
    for (let j = 0; j < 4; j++) {
      const [x0, z0] = legs[[0, 1, 3, 2][j]], [x1, z1] = legs[[1, 3, 2, 0][j]];
      ramp.add(span('TowerRing', new Vector3(x0, y, z0), new Vector3(x1, y, z1), 0.1, steelMaterial));
      ramp.add(span('TowerBrace', new Vector3(x0, y, z0), new Vector3(x1, Math.min(top, y + 3), z1), 0.06, steelMaterial));
    }
    if (k % 2 === 1) glows.push({ position: new Vector3(14.1, y, 2.6), size: 0.7, color: [1.0, 0.06, 0.08], blink: 0, streak: 0 });
  }
  // Concrete apron pad at the foot of the ramp.
  const pad = new Mesh(new BoxGeometry(14, 0.06, 7), new MeshStandardMaterial({ color: '#4a4c4f', roughness: 0.9 }));
  pad.name = 'RampPad'; pad.position.set(4, 0.03, 0); pad.receiveShadow = true; ramp.add(pad);
  ramp.add(createGlowSprites('RampGlows', glows));
  batchSpans(ramp);
  return ramp;
}

function asphaltShader(): MeshStandardMaterial {
  const asphalt = new MeshStandardMaterial({ color: '#0d0f12', roughness: 0.9, metalness: 0, envMapIntensity: 0.04 });
  // Analytic light pools from the decorative flood banks (the real towers are actual SpotLights).
  const pools = FLOOD_BANKS.map((bank) => {
    const dx = bank.aim[0] - bank.pos[0], dz = bank.aim[2] - bank.pos[2];
    const len = Math.hypot(dx, dz) || 1;
    return `pool(roadPosition.xz, vec2(${(bank.pos[0] + dx / len * 6).toFixed(2)}, ${(bank.pos[2] + dz / len * 6).toFixed(2)}), vec2(${(dx / len).toFixed(3)}, ${(dz / len).toFixed(3)}))`;
  }).join(' + ');
  asphalt.onBeforeCompile = (shader) => {
    shader.vertexShader = 'varying vec3 roadPosition;\n' + shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n roadPosition=position;');
    shader.fragmentShader = `varying vec3 roadPosition;\n${NOISE_GLSL}
      float pool(vec2 p, vec2 c, vec2 dir){ vec2 d=p-c; float along=dot(d,dir); float across=dot(d,vec2(-dir.y,dir.x));
        return exp(-along*along/42.-across*across/14.); }
      vec2 rot(vec2 p, float a){ float c=cos(a), s=sin(a); return vec2(c*p.x-s*p.y, s*p.x+c*p.y); }
      float wetMask(vec2 p){ float n=.6*fxNoise2(p*.07)+.3*fxNoise2(rot(p,1.1)*.21+17.3)+.1*fxNoise2(rot(p,2.3)*.9+5.1); return smoothstep(.48,.6,n); }
    ` + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace('#include <envmap_physical_pars_fragment>', ShaderChunk.envmap_physical_pars_fragment.replace(/envMapIntensity/g, '(envMapIntensity*0.015)'));
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', `#include <color_fragment>
      vec2 rp = roadPosition.xz;
      float grain = fxHash2(floor(rot(rp, .7) * 31.) + floor(rp.yx * .13));
      float aggregate = .6 * fxNoise2(rot(rp, .4) * 3.1) + .4 * fxNoise2(rot(rp, 2.1) * 7.7 + 9.);
      float patches = .6 * fxNoise2(rp * .045 + 3.) + .4 * fxNoise2(rot(rp, 1.7) * .013 + 11.);
      diffuseColor.rgb *= (.72 + grain * .5) * (.82 + aggregate * .3) * (.7 + patches * .55);
      float wet = wetMask(rp);
      diffuseColor.rgb *= mix(1., .45, wet);
      float paintAA = max(.01, fwidth(roadPosition.z));
      float dash = step(.45, fract(roadPosition.x / 6.));
      float centerPaint = (1. - smoothstep(.06 - paintAA, .06 + paintAA, abs(roadPosition.z))) * step(-160., roadPosition.x) * step(roadPosition.x, -.15) * dash;
      float landingBox = (1. - smoothstep(.0, paintAA * 2., abs(abs(roadPosition.z) - 3.4) - .05)) * step(-66., roadPosition.x) * step(roadPosition.x, -48.);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(.42, .43, .45) * (.7 + aggregate * .3), max(centerPaint, landingBox * .8));`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
      roughnessFactor = mix(.74, .58, wet) * (.92 + .16 * fxNoise2(roadPosition.xz * 2.3));`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
      vec2 ep = roadPosition.xz;
      float inLane = step(${LANE.start.toFixed(1)}, ep.x) * step(ep.x, ${LANE.end.toFixed(1)});
      float edgeD = abs(abs(ep.y) - ${LANE.halfWidth.toFixed(1)});
      float lineGlow = (exp(-edgeD * 2.4) * .16 + exp(-edgeD * 9.) * .5) * inLane;
      float fx = mod(ep.x - ${LANE.start.toFixed(1)} + ${(LANE.footlightSpacing / 2).toFixed(1)}, ${LANE.footlightSpacing.toFixed(1)}) - ${(LANE.footlightSpacing / 2).toFixed(1)};
      float fz = abs(ep.y) - ${(LANE.halfWidth + 0.25).toFixed(2)}; float footD = fx * fx + fz * fz * 1.6;
      float footGlow = exp(-footD * 1.1) * .9 * step(${LANE.start.toFixed(1)}, ep.x) * step(ep.x, ${(LANE.end - 2).toFixed(1)});
      float wetBoost = mix(1., 1.8, wet);   // wet: computed once in color_fragment, same scope
      totalEmissiveRadiance += vec3(1., .02, .04) * (lineGlow + footGlow) * wetBoost * .55;
      totalEmissiveRadiance += vec3(.75, .82, .9) * (${pools}) * .03 * mix(1., 1.2, wet);`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <dithering_fragment>', `#include <dithering_fragment>
      float boundaryFade = (1. - smoothstep(30., 88., abs(roadPosition.z))) * (1. - smoothstep(120., 178., abs(roadPosition.x)));
      gl_FragColor.rgb = mix(vec3(.012, .011, .013), gl_FragColor.rgb, boundaryFade);`);
  };
  asphalt.customProgramCacheKey = () => 'roadster-asphalt-v8';
  return asphalt;
}

/** Low vertical haze curtain that makes each LED line glow in the night air. */
function glowCurtainMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    name: 'LedCurtain', transparent: true, depthWrite: false, side: DoubleSide, blending: AdditiveBlending, fog: false,
    uniforms: { time: FX_TIME },
    vertexShader: 'varying vec2 vUv; varying vec3 vWorld; void main(){ vUv=uv; vec4 w=modelMatrix*vec4(position,1.); vWorld=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }',
    fragmentShader: `uniform float time; varying vec2 vUv; varying vec3 vWorld; ${NOISE_GLSL}
      void main(){ float h = vUv.y; float a = exp(-h * 9.) * .5 + exp(-h * 2.5) * .06;
        a *= smoothstep(0., .02, vUv.x) * smoothstep(0., .02, 1. - vUv.x);
        a *= .7 + .6 * fxNoise(vec3(vWorld.x * .15 + time * .2, h * 2., vWorld.z * .1));
        float d = length(cameraPosition - vWorld); a *= smoothstep(1., 6., d);
        gl_FragColor = vec4(vec3(1., .03, .06) * a, 1.); }`,
  });
}

export function createApron(): Group {
  const apron = new Group(); apron.name = 'Apron';
  const ground = new Mesh(new BoxGeometry(360, 0.22, 180), asphaltShader());
  ground.name = 'Ground'; ground.position.y = -0.11; ground.receiveShadow = true; apron.add(ground);
  const start = new Vector3(), end = new Vector3();
  const curtain = glowCurtainMaterial();
  const glows: GlowSpec[] = [];
  for (const z of [-LANE.halfWidth, LANE.halfWidth]) {
    start.set(LANE.start, 0.03, z); end.set(LANE.end, 0.03, z);
    apron.add(span(`Boundary-${z}`, start, end, 0.07, redLed, 0.05));
    const sheet = new Mesh(new PlaneGeometry(LANE.end - LANE.start, 1.4), curtain);
    sheet.name = `LedCurtain-${z}`; sheet.position.set((LANE.start + LANE.end) / 2, 0.7, z); apron.add(sheet);
  }
  for (let x = LANE.start; x <= LANE.end - 2; x += LANE.footlightSpacing) for (const z of [-(LANE.halfWidth + 0.25), LANE.halfWidth + 0.25]) {
    const base = new Mesh(beamGeometry, darkSteelMaterial); base.name = 'Footlight'; base.scale.set(0.34, 0.14, 0.3); base.position.set(x, 0.07, z); apron.add(base);
    const lens = new Mesh(beamGeometry, redLed); lens.name = 'FootlightLens'; lens.scale.set(0.22, 0.06, 0.18); lens.position.set(x, 0.16, z); apron.add(lens);
    glows.push({ position: new Vector3(x, 0.22, z), size: 0.8, color: [1.0, 0.04, 0.07], streak: 0.0 });
  }
  apron.add(createGlowSprites('LaneGlows', glows));
  batchSpans(apron);
  return apron;
}
