/**
 * Shared shader materials for light-emitting set dressing: volumetric beam
 * cones, camera-facing glow sprites and HDR LED emitters.
 *
 * Deterministic and DOM-free (evaluated by the runtime and the editor). The
 * exported FX_TIME uniform is advanced by the runtime RoadsterSystem; in the
 * editor realm it simply stays at zero.
 */
import {
  AdditiveBlending, Color, CylinderGeometry, DoubleSide, InstancedBufferAttribute, InstancedMesh,
  Matrix4, MeshBasicMaterial, PlaneGeometry, Quaternion, ShaderMaterial, Vector3,
} from '@iwsdk/core';

export const FX_TIME = { value: 0 };
/** 0 in the browser view, 1 in XR: lets shaders trim expensive terms. */
export const FX_XR = { value: 0 };

export const NOISE_GLSL = /* glsl */ `
float fxHash(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float fxNoise(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);
  return mix(mix(mix(fxHash(i),fxHash(i+vec3(1,0,0)),f.x),mix(fxHash(i+vec3(0,1,0)),fxHash(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(fxHash(i+vec3(0,0,1)),fxHash(i+vec3(1,0,1)),f.x),mix(fxHash(i+vec3(0,1,1)),fxHash(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fxHash2(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float fxNoise2(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(fxHash2(i),fxHash2(i+vec2(1,0)),f.x),mix(fxHash2(i+vec2(0,1)),fxHash2(i+vec2(1,1)),f.x),f.y);}
`;

/** HDR emitter: values above 1 drive bloom in the browser view and clip to a saturated colour in XR. */
export function emitter(r: number, g: number, b: number): MeshBasicMaterial {
  const material = new MeshBasicMaterial({ fog: false });
  material.color.setRGB(r, g, b);
  return material;
}

export interface BeamSpec { origin: Vector3; dir: Vector3; length: number; halfAngle: number; strength: number }
/**
 * Volumetric light shafts in one instanced draw: open cones whose apex sits at
 * the lamp. Brightness falls off along the length and toward the silhouette,
 * drifting dust noise breaks it up, and it fades into the ground and near the camera.
 */
export function createBeams(name: string, color: readonly [number, number, number], beams: readonly BeamSpec[]): InstancedMesh {
  const geometry = new CylinderGeometry(0.05, 1, 1, 40, 14, true);
  geometry.translate(0, -0.5, 0);
  geometry.rotateX(Math.PI); // apex (uv.y = 1) at the origin, flaring toward +Y
  geometry.setAttribute('beamStrength', new InstancedBufferAttribute(new Float32Array(beams.map((b) => b.strength)), 1));
  const material = new ShaderMaterial({
    name: 'VolumetricBeam',
    transparent: true, depthWrite: false, side: DoubleSide, blending: AdditiveBlending, fog: false,
    uniforms: { time: FX_TIME, color: { value: new Color().setRGB(color[0], color[1], color[2]) } },
    vertexShader: /* glsl */ `
      attribute float beamStrength;
      varying vec3 vWorld; varying vec3 vNormalW; varying float vAlong; varying float vStrength;
      void main(){
        vAlong = uv.y; vStrength = beamStrength;
        mat4 m = modelMatrix * instanceMatrix;
        vec3 s2 = vec3(dot(m[0].xyz, m[0].xyz), dot(m[1].xyz, m[1].xyz), dot(m[2].xyz, m[2].xyz));
        vNormalW = normalize(mat3(m) * (normal / s2));
        vec4 world = m * vec4(position, 1.0);
        vWorld = world.xyz;
        gl_Position = projectionMatrix * viewMatrix * world;
      }`,
    fragmentShader: /* glsl */ `
      uniform float time; uniform vec3 color;
      varying vec3 vWorld; varying vec3 vNormalW; varying float vAlong; varying float vStrength;
      ${NOISE_GLSL}
      void main(){
        vec3 toCam = cameraPosition - vWorld;
        float camDist = length(toCam);
        float facing = abs(dot(normalize(vNormalW), toCam / camDist));
        float core = pow(facing, 2.4);
        float along = 1.0 - vAlong; // 0 at the lamp
        float falloff = pow(clamp(1.0 - along, 0.0, 1.0), 1.6) * smoothstep(0.0, 0.03, along) / (0.35 + along * 3.0);
        float dust = fxNoise(vWorld * 0.18 + vec3(time * 0.1, time * 0.04, -time * 0.07));
        dust = 0.5 + 0.9 * dust * (0.6 + 0.8 * fxNoise(vWorld * 0.7 - vec3(0.0, time * 0.15, 0.0)));
        float ground = smoothstep(0.0, 1.6, vWorld.y);
        float nearFade = smoothstep(4.0, 16.0, camDist); // never let a shaft fill the lens
        float a = vStrength * core * falloff * dust * ground * nearFade;
        gl_FragColor = vec4(color * a, 1.0);
      }`,
  });
  const mesh = new InstancedMesh(geometry, material, beams.length);
  mesh.name = name;
  const m = new Matrix4(), q = new Quaternion(), s = new Vector3(), d = new Vector3();
  beams.forEach((beam, i) => {
    q.setFromUnitVectors(UP, d.copy(beam.dir).normalize());
    const radius = Math.tan(beam.halfAngle) * beam.length;
    mesh.setMatrixAt(i, m.compose(beam.origin, q, s.set(radius, beam.length, radius)));
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.frustumCulled = false;
  mesh.renderOrder = 25;
  mesh.userData.iwsdkPreviewBounds = 'exclude';
  return mesh;
}

const UP = new Vector3(0, 1, 0);

/**
 * Camera-facing glow sprites (lamp halos, LED blooms, aviation beacons) in one
 * instanced draw. Billboarding happens in the vertex shader, so nothing is
 * updated on the CPU per frame. `blink` > 0 makes an instance pulse at that rate.
 */
export interface GlowSpec { position: Vector3; size: number; color: readonly [number, number, number]; blink?: number; streak?: number }
export function createGlowSprites(name: string, glows: readonly GlowSpec[], options: { depthTest?: boolean; minPixels?: number } = {}): InstancedMesh {
  const geometry = new PlaneGeometry(1, 1);
  const colors = new Float32Array(glows.length * 3);
  const params = new Float32Array(glows.length * 3);
  glows.forEach((glow, i) => {
    colors.set(glow.color, i * 3);
    params[i * 3] = glow.blink ?? 0;
    params[i * 3 + 1] = glow.streak ?? 0.05;
    params[i * 3 + 2] = (i * 0.6180339) % 1;
  });
  geometry.setAttribute('glowColor', new InstancedBufferAttribute(colors, 3));
  geometry.setAttribute('glowParams', new InstancedBufferAttribute(params, 3));
  const material = new ShaderMaterial({
    name: 'GlowSprite',
    transparent: true, depthWrite: false, depthTest: options.depthTest ?? true, blending: AdditiveBlending, fog: false,
    uniforms: { time: FX_TIME, minPixels: { value: options.minPixels ?? 0 } },
    vertexShader: /* glsl */ `
      attribute vec3 glowColor; attribute vec3 glowParams;
      uniform float time; uniform float minPixels;
      varying vec3 vColor; varying vec2 vUv; varying float vStreak;
      void main(){
        vec4 center = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
        float size = length(instanceMatrix[0].xyz);
        // keep distant lamps at least a few pixels wide so the horizon twinkles
        float pixelWorld = -center.z / projectionMatrix[1][1] * 2.0 / 900.0;
        size = max(size, minPixels * pixelWorld);
        float blink = glowParams.x > 0.0 ? 0.08 + 0.92 * smoothstep(0.35, 0.65, 0.5 + 0.5 * sin((time * glowParams.x + glowParams.z) * 6.2831853)) : 1.0; // slow beacon fade, never a strobe
        vColor = glowColor * blink;
        vStreak = glowParams.y;
        vUv = position.xy * 2.0;
        center.xyz += normalize(-center.xyz) * min(size * 0.6, 0.8); // sit in front of the fixture face
        center.xy += position.xy * size * vec2(1.0 + vStreak * 2.5, 1.0);
        gl_Position = projectionMatrix * center;
      }`,
    fragmentShader: /* glsl */ `
      varying vec3 vColor; varying vec2 vUv; varying float vStreak;
      void main(){
        vec2 p = vUv * vec2(1.0 + vStreak * 2.5, 1.0);
        float r = length(p);
        float core = exp(-r * r * 60.0) * 1.6;
        float halo = exp(-r * 4.5) * 0.32 * (1.0 - smoothstep(0.7, 1.0, r));
        float streak = vStreak * exp(-abs(vUv.y) * 38.0) * (1.0 - smoothstep(0.2, 1.0, abs(vUv.x))) * 0.7;
        float a = core + halo + streak;
        if (a < 0.002) discard;
        gl_FragColor = vec4(vColor * a, 1.0);
      }`,
  });
  const mesh = new InstancedMesh(geometry, material, glows.length);
  mesh.name = name;
  const m = new Matrix4(), q = new Quaternion(), s = new Vector3();
  glows.forEach((glow, i) => { mesh.setMatrixAt(i, m.compose(glow.position, q, s.setScalar(glow.size))); });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.frustumCulled = false;
  mesh.renderOrder = 30;
  mesh.userData.iwsdkPreviewBounds = 'exclude';
  return mesh;
}
