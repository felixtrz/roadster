/**
 * Thruster and vapor effect prototypes. All geometry lives here; the runtime
 * ReplayEffects drives uniforms, instance transforms and lights from the
 * reconstructed track. Every system is a single draw call.
 */
import {
  AdditiveBlending, CylinderGeometry, DoubleSide, Group, InstancedBufferAttribute, InstancedMesh,
  Mesh, NormalBlending, PlaneGeometry, ShaderMaterial, Vector3,
} from '@iwsdk/core';
import { createGlowSprites, FX_TIME, FX_XR, NOISE_GLSL } from './lib/fx-materials.js';

export const VAPOR_COUNT = 300;
/** The last TIRE_SMOKE_COUNT vapor instances are reserved for drive-away tyre smoke. */
export const TIRE_SMOKE_COUNT = 56;
export const SPARK_COUNT = 110;
export const SPLASH_COUNT = 220;
/** Default lift nozzle anchors (car-local, +X forward), used when the car GLB has no NozzleAnchor_n nodes. */
export const DEFAULT_NOZZLES: readonly [number, number, number][] = [[1.05, 0.14, -0.55], [1.05, 0.14, 0.55], [-1.05, 0.14, -0.55], [-1.05, 0.14, 0.55]];

const JET_VERTEX = /* glsl */ `
  varying vec2 vUv; varying vec3 vWorld; varying vec3 vNormalW;
  void main(){
    vUv = uv;
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    vec3 s = vec3(dot(modelMatrix[0].xyz, modelMatrix[0].xyz), dot(modelMatrix[1].xyz, modelMatrix[1].xyz), dot(modelMatrix[2].xyz, modelMatrix[2].xyz));
    vNormalW = normalize(mat3(modelMatrix) * (normal / max(s, vec3(1e-6))));
    gl_Position = projectionMatrix * viewMatrix * world;
  }`;

/** Bright supersonic core with shock diamonds. */
function coreMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    name: 'JetCore', transparent: true, depthWrite: false, side: DoubleSide, blending: AdditiveBlending, fog: false,
    uniforms: { time: FX_TIME, intensity: { value: 0 }, length: { value: 1.6 } },
    vertexShader: JET_VERTEX,
    fragmentShader: /* glsl */ `
      uniform float time; uniform float intensity; uniform float length;
      varying vec2 vUv; varying vec3 vWorld; varying vec3 vNormalW;
      void main(){
        vec3 V = normalize(cameraPosition - vWorld);
        float facing = abs(dot(normalize(vNormalW), V));
        float r = 1.0 - facing;
        float along = 1.0 - vUv.y;
        float d = along * length;
        float ph = fract(d / 0.26 - time * 0.4);
        float pinch = abs(ph - 0.5) * 2.0;
        float width = 0.18 + 0.55 * pinch;
        float inner = smoothstep(width, width - 0.28, r);
        float knot = pow(1.0 - pinch, 5.0);
        float flick = 0.95 + 0.05 * sin(d * 13.0 - time * 6.0);
        float bright = (inner * (0.55 + 1.6 * knot) + 0.25 * facing) * exp(-along * 2.6) * smoothstep(0.0, 0.03, along) * flick;
        vec3 color = mix(vec3(0.35, 0.62, 1.0), vec3(1.0, 0.97, 1.0), inner * (0.4 + 0.6 * knot));
        gl_FragColor = vec4(color * bright * intensity * 4.5, 1.0);
      }`,
  });
}

/**
 * Lift plume: a narrow, dense white exhaust column (alpha-blended, not additive) that
 * billows with turbulence and only flares out where it meets the ground, feeding the cloud.
 */
function plumeMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    name: 'JetPlume', transparent: true, depthWrite: false, side: DoubleSide, blending: NormalBlending, premultipliedAlpha: true, fog: false,
    uniforms: { time: FX_TIME, intensity: { value: 0 }, length: { value: 3 }, flare: { value: 1 }, free: { value: 0 } },
    vertexShader: /* glsl */ `
      uniform float length; uniform float time; uniform float flare; uniform float free;
      varying vec2 vUv; varying vec3 vWorld; varying vec3 vNormalW;
      void main(){
        vUv = uv;
        float along = 1.0 - uv.y;
        float d = along * length;
        // flare only in the last ~1.2 m above the ground, plus a slow billow along the column
        // grounded plumes flare where they hit the pad; free jets spread as a slow cone instead
        float spread = (1.0 - free * 0.7) * (1.0 + flare * 3.2 * smoothstep(length - 1.3, length, d) + free * d * 0.75);
        float billow = 1.0 + 0.14 * sin(d * 4.0 - time * 7.0) * sin(uv.x * 6.2831853 * 3.0 + d * 2.0);
        vec3 p = vec3(position.x * spread * billow, position.y, position.z * spread * billow);
        vec4 world = modelMatrix * vec4(p, 1.0);
        vWorld = world.xyz;
        vec3 s = vec3(dot(modelMatrix[0].xyz, modelMatrix[0].xyz), dot(modelMatrix[1].xyz, modelMatrix[1].xyz), dot(modelMatrix[2].xyz, modelMatrix[2].xyz));
        vNormalW = normalize(mat3(modelMatrix) * (normal / max(s, vec3(1e-6))));
        gl_Position = projectionMatrix * viewMatrix * world;
      }`,
    fragmentShader: /* glsl */ `
      uniform float time; uniform float intensity; uniform float length; uniform float free;
      varying vec2 vUv; varying vec3 vWorld; varying vec3 vNormalW;
      ${NOISE_GLSL}
      void main(){
        vec3 V = normalize(cameraPosition - vWorld);
        float facing = abs(dot(normalize(vNormalW), V));
        float along = 1.0 - vUv.y;
        float d = along * length;
        float a = vUv.x * 6.2831853;
        vec3 q = vec3(cos(a) * 1.8, sin(a) * 1.8, d * 2.2 - time * 8.0);
        float n = fxNoise(q) * 0.5 + fxNoise(q * 2.3 + 7.0) * 0.32 + fxNoise(q * 5.3 - 3.0) * 0.18;
        float density = smoothstep(0.2, 0.75, facing + (n - 0.5) * 0.95);
        float alpha = density * (0.55 + 0.45 * n) * smoothstep(0.0, 0.05, along) * (1.0 - 0.45 * smoothstep(0.75, 1.0, along));
        alpha *= smoothstep(-0.05, 0.25, vWorld.y) * clamp(intensity * 1.4, 0.0, 1.0) * 0.62 * exp(-max(0.0, d - 1.0) * (0.3 + free * 0.25));
        // lit white steam, a touch of blue at the nozzle and shading on the rolling eddies
        // free cold-gas jets read cyan-white against the night sky (broadcast R01-R04); grounded ones steam white
        vec3 c = mix(vec3(0.82, 0.9, 1.0), vec3(0.92, 0.93, 0.95), smoothstep(0.0, 0.35, along)) * (0.62 + 0.45 * n);
        c = mix(c, vec3(0.6, 0.82, 1.0) * (0.95 + 0.6 * n), free * 0.9);
        // free jets: dense at the nozzle, fraying into wisps and fading out along the length
        float wisp = fxNoise(vec3(cos(a) * 2.6, sin(a) * 2.6, d * 3.1 - time * 11.0));
        float fray = smoothstep(0.15, 0.7, facing + (n - 0.5) * 0.9 + (wisp - 0.5) * along * 1.2);
        alpha *= mix(1.0, fray * pow(facing, 1.6) * exp(-d / 1.9) * (1.0 - smoothstep(0.55, 1.0, along)) * 1.25, free);
        c += vec3(0.6, 0.8, 1.0) * pow(facing, 4.0) * exp(-along * 6.0) * 1.4;
        c = mix(c, c * vec3(0.8, 0.93, 1.08), 1.0 - smoothstep(0.0, 0.7, along));
        if (alpha < 0.004) discard;
        gl_FragColor = vec4(c * alpha, alpha);
      }`,
  });
}

function jetGeometry(r0: number, r1: number): CylinderGeometry {
  const geometry = new CylinderGeometry(r0, r1, 1, 28, 10, true);
  geometry.translate(0, -0.5, 0); // nozzle at the origin, exhaust along -Y, uv.y = 1 at the nozzle
  return geometry;
}

export function createThrusters(): Group {
  const root = new Group(); root.name = 'Thrusters';
  root.userData.iwsdkPreviewBounds = 'exclude';
  const core = coreMaterial(), plume = plumeMaterial();
  const coreGeometry = jetGeometry(0.07, 0.12), plumeGeometry = jetGeometry(0.09, 0.32);
  DEFAULT_NOZZLES.forEach(([x, y, z], i) => {
    const jet = new Group(); jet.name = `LiftJet_${i + 1}`; jet.position.set(x, y, z);
    const shell = new Mesh(plumeGeometry, plume); shell.name = 'JetPlume'; shell.renderOrder = 21; jet.add(shell);
    const center = new Mesh(coreGeometry, core); center.name = 'JetCore'; center.renderOrder = 23; jet.add(center);
    jet.visible = false; root.add(jet);
  });
  const glows = createGlowSprites('NozzleGlows', [0, 1, 2, 3].map(() => ({ position: new Vector3(), size: 0, color: [0.6, 0.8, 1.0] as const, streak: 0.05 })));
  root.add(glows);
  return root;
}

/** Soft lit vapor billboards (one sorted instanced draw) plus GPU-analytic sparks and jet splash. */
export function createVapor(): Group {
  const group = new Group(); group.name = 'GroundVapor'; group.userData.iwsdkPreviewBounds = 'exclude';
  const material = new ShaderMaterial({
    name: 'VaporBillboard',
    transparent: true, depthWrite: false, side: DoubleSide, blending: NormalBlending, premultipliedAlpha: true, fog: false,
    uniforms: { time: { value: 0 }, xr: FX_XR, atlas: { value: null }, useAtlas: { value: 0 }, flood: { value: [0.8, 0.86, 0.95] }, jetColor: { value: [0.5, 0.75, 1.0] }, redColor: { value: [1.0, 0.06, 0.1] } },
    vertexShader: /* glsl */ `
      attribute float cloudSeed; attribute float cloudOpacity; attribute vec4 cloudLight;
      varying vec2 vUv; varying float vSeed; varying float vOpacity; varying vec4 vLight; varying vec3 vWorld; varying float vCamDist;
      void main(){
        vUv = uv; vSeed = cloudSeed; vOpacity = cloudOpacity; vLight = cloudLight;
        vec4 world = modelMatrix * instanceMatrix * vec4(position, 1.0);
        vWorld = world.xyz;
        vec4 view = viewMatrix * world;
        vCamDist = -view.z;
        gl_Position = projectionMatrix * view;
      }`,
    fragmentShader: /* glsl */ `
      uniform float time; uniform float xr; uniform sampler2D atlas; uniform float useAtlas; uniform vec3 flood; uniform vec3 jetColor; uniform vec3 redColor;
      varying vec2 vUv; varying float vSeed; varying float vOpacity; varying vec4 vLight; varying vec3 vWorld; varying float vCamDist;
      ${NOISE_GLSL}
      void main(){
        if (vOpacity < 0.002) discard;
        // gentle roll: a small rotation plus swirling distortion keeps sprites from reading as stamps
        float ang = (vSeed - 0.5) * 0.5 + sin(time * 0.3 + vSeed * 20.0) * 0.06;
        vec2 p = vUv - 0.5;
        p = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * p;
        float flow = time * 0.35 + vSeed * 17.0;
        // in XR (two eyes, heavy overdraw at landing) skip the swirl and the two finest erosion octaves
        vec2 swirl = xr > 0.5 ? vec2(0.0) : vec2(fxNoise2(p * 3.0 + vec2(flow, vSeed * 9.0)), fxNoise2(p * 3.0 + vec2(vSeed * 5.0, -flow))) - 0.5;
        float env = 1.0 - smoothstep(0.25, 0.5, length(p));
        p += swirl * 0.1 * env;
        if (fract(vSeed * 13.7) > 0.5) p.x = -p.x;
        vec2 uv = clamp(p + 0.5, 0.004, 0.996);
        vec4 t;
        if (useAtlas > 0.5) {
          float cell = floor(fract(vSeed * 7.31) * 8.0);
          vec2 tile = vec2(mod(cell, 4.0), floor(cell / 4.0));
          t = texture2D(atlas, (uv + tile) / vec2(4.0, 2.0));
        } else {
          float r = length(p) * 2.0;
          float n = fxNoise2(uv * 5.0 + vSeed * 10.0);
          t = vec4(1.0 - p.y, 0.6 + p.y, 0.5, (1.0 - smoothstep(0.5, 1.0, r + (n - 0.5) * 0.4)) * 0.8);
        }
        // erode the sprite with drifting noise so edges tear and overlap like real vapor
        float erosion = fxNoise2(uv * 6.0 + vec2(vSeed * 13.0, time * 0.15)) * 0.5
          + (xr > 0.5 ? 0.25 : fxNoise2(uv * 15.0 - vec2(time * 0.25, vSeed * 7.0)) * 0.32 + fxNoise2(uv * 34.0 + vSeed * 3.0) * 0.18);
        float rim = clamp(length(p) * 2.0, 0.0, 1.0);
        // wispy, thin edges: the rim is eaten away hardest, the core stays soft rather than solid
        t.a = smoothstep(0.1 + 0.62 * pow(rim, 1.5), 1.0, t.a * (0.35 + 1.05 * erosion)) * (0.75 + 0.25 * erosion);
        float top = t.r, bottom = t.g, thin = t.b;
        float jet = vLight.x, red = vLight.y, lit = vLight.z, inner = vLight.w;
        vec3 c = vec3(0.016, 0.018, 0.024) * (0.5 + bottom);
        float tone = 0.72 + 0.4 * fract(vSeed * 3.71);
        c += flood * top * lit * 0.7 * tone;
        c += flood * 0.07 * lit;
        c += jetColor * (bottom * 1.6 + thin * 1.2 + 0.25) * jet;
        // runway red stays in the base of each puff
        float base = 1.0 - smoothstep(0.0, 0.55, uv.y);
        c += redColor * (bottom * 1.9 + thin * 1.1) * red * base * base * 1.7;
        c += vec3(1.0, 0.98, 0.95) * inner * thin * 2.0;
        c += vec3(0.75, 0.82, 0.95) * thin * 0.06 * lit; // light scattering through the thin parts
        float a = t.a * vOpacity * (1.0 - smoothstep(0.5, 1.0, rim));
        a *= smoothstep(-0.25, 0.9, vWorld.y);
        a *= smoothstep(2.0, 8.0, vCamDist);
        if (a < 0.003) discard;
        gl_FragColor = vec4(c * a, a);
      }`,
  });
  const geometry = new PlaneGeometry(2, 2);
  geometry.setAttribute('cloudSeed', new InstancedBufferAttribute(new Float32Array(VAPOR_COUNT), 1));
  geometry.setAttribute('cloudOpacity', new InstancedBufferAttribute(new Float32Array(VAPOR_COUNT), 1));
  geometry.setAttribute('cloudLight', new InstancedBufferAttribute(new Float32Array(VAPOR_COUNT * 4), 4));
  const vapor = new InstancedMesh(geometry, material, VAPOR_COUNT);
  vapor.name = 'VaporBillboards'; vapor.frustumCulled = false; vapor.renderOrder = 20;
  group.add(vapor);
  group.add(createStreaks('Sparks', SPARK_COUNT, true));
  group.add(createStreaks('JetSplash', SPLASH_COUNT, false));
  const splash = new Mesh(new PlaneGeometry(1, 1), new ShaderMaterial({
    name: 'SplashGlow', transparent: true, depthWrite: false, blending: AdditiveBlending, fog: false,
    uniforms: { intensity: { value: 0 }, time: FX_TIME },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
    fragmentShader: `uniform float intensity; uniform float time; varying vec2 vUv; ${NOISE_GLSL}
      void main(){ vec2 p = (vUv - .5) * 2.; float r = length(p);
        float rings = .75 + .25 * sin(r * 22. - time * 30.);
        float n = .7 + .3 * fxNoise2(p * 6. + time * 3.);
        float a = (exp(-r * r * 9.) * 1.6 + exp(-r * 3.) * .35) * (1. - smoothstep(.85, 1., r)) * rings * n * intensity;
        gl_FragColor = vec4(vec3(.55, .78, 1.) * a, 1.); }`,
  }));
  splash.name = 'SplashGlow'; splash.rotation.x = -Math.PI / 2; splash.renderOrder = 19; splash.visible = false;
  group.add(splash);
  return group;
}

/**
 * Velocity-stretched streak particles evaluated entirely on the GPU from
 * per-instance birth data, so scrubbing the replay is free and exact.
 * Sparks bounce with gravity; splash streaks skim radially along the ground.
 */
function createStreaks(name: string, count: number, sparks: boolean): InstancedMesh {
  const geometry = new PlaneGeometry(1, 1);
  geometry.setAttribute('origin', new InstancedBufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute('velocity', new InstancedBufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute('birth', new InstancedBufferAttribute(new Float32Array(count * 3), 3)); // time, life, energy
  const material = new ShaderMaterial({
    name, transparent: true, depthWrite: false, side: DoubleSide, blending: AdditiveBlending, fog: false,
    uniforms: { time: { value: 0 } },
    vertexShader: /* glsl */ `
      attribute vec3 origin; attribute vec3 velocity; attribute vec3 birth;
      uniform float time;
      varying float vFade; varying vec2 vUv; varying float vHeat;
      vec3 posAt(float age){
        ${sparks
    ? `vec3 p = origin + velocity * age + vec3(0.0, -9.81, 0.0) * 0.5 * age * age;
        if (p.y < 0.02) { // one damped bounce
          float tb = (velocity.y + sqrt(max(0.0, velocity.y * velocity.y + 2.0 * 9.81 * origin.y))) / 9.81;
          vec3 hit = origin + velocity * tb + vec3(0.0, -4.905, 0.0) * tb * tb;
          vec3 v2 = vec3(velocity.x * 0.6, -(velocity.y - 9.81 * tb) * 0.35, velocity.z * 0.6);
          float a2 = age - tb;
          p = hit + v2 * a2 + vec3(0.0, -4.905, 0.0) * a2 * a2;
          p.y = max(p.y, 0.02);
        }
        return p;`
    : `float k = 3.2; float s = (1.0 - exp(-k * age)) / k;
        return origin + velocity * s + vec3(0.0, 0.35, 0.0) * age;`}
      }
      void main(){
        float age = time - birth.x;
        float life = birth.y;
        if (age < 0.0 || age > life || birth.z <= 0.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
        vec3 p0 = posAt(age);
        vec3 p1 = posAt(max(0.0, age - ${sparks ? '0.035' : '0.05'}));
        vec4 c0 = viewMatrix * modelMatrix * vec4(p0, 1.0);
        vec4 c1 = viewMatrix * modelMatrix * vec4(p1, 1.0);
        vec2 dir = c0.xy - c1.xy;
        float len = length(dir);
        dir = len > 1e-5 ? dir / len : vec2(1.0, 0.0);
        vec2 side = vec2(-dir.y, dir.x);
        float width = ${sparks ? '0.018' : '0.07'} * (1.0 + 0.5 * birth.z);
        vec4 c = mix(c1, c0, position.y + 0.5);
        c.xy += side * position.x * width;
        vUv = position.xy + 0.5;
        float t = age / life;
        vFade = birth.z * (1.0 - t) * (1.0 - t) * smoothstep(0.0, 0.03, age);
        vHeat = 1.0 - t;
        gl_Position = projectionMatrix * c;
      }`,
    fragmentShader: /* glsl */ `
      varying float vFade; varying vec2 vUv; varying float vHeat;
      void main(){
        float across = 1.0 - abs(vUv.x - 0.5) * 2.0;
        float a = across * across * vFade * smoothstep(0.0, 0.25, vUv.y);
        ${sparks
    ? 'vec3 col = mix(vec3(1.0, 0.25, 0.04), vec3(1.0, 0.85, 0.55), vHeat * vHeat) * 9.0;'
    : 'vec3 col = mix(vec3(0.6, 0.75, 0.95), vec3(0.75, 0.9, 1.0), vHeat) * 1.6;'}
        gl_FragColor = vec4(col * a, 1.0);
      }`,
  });
  const mesh = new InstancedMesh(geometry, material, count);
  mesh.name = name; mesh.frustumCulled = false; mesh.renderOrder = 24;
  return mesh;
}
