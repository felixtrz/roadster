/**
 * Night sky and the distant McGregor test site: a star-filled gradient dome
 * with a faint horizon glow, black silhouettes of test stands, gantries,
 * tanks and a water tower, and their work lights and aviation beacons.
 *
 * Placed at SITE_OFFSET. Deterministic (seeded) and DOM-free.
 */
import { BackSide, BoxGeometry, BufferGeometry, CircleGeometry, DoubleSide, Float32BufferAttribute, CylinderGeometry, Group, InstancedMesh, Matrix4, Mesh, MeshBasicMaterial, Quaternion, ShaderMaterial, SphereGeometry, Vector3 } from '@iwsdk/core';
import { makeRandom } from './lib/hardsurface.js';
import { createGlowSprites, FX_TIME, NOISE_GLSL, type GlowSpec } from './lib/fx-materials.js';

function skyMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    name: 'NightSky', side: BackSide, depthWrite: false, fog: false,
    uniforms: { time: FX_TIME },
    vertexShader: 'varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.); gl_Position = p.xyww; }',
    fragmentShader: /* glsl */ `
      uniform float time; varying vec3 vDir;
      ${NOISE_GLSL}
      vec3 starLayer(vec3 d, float scale, float threshold){
        vec3 p = d * scale; vec3 cell = floor(p); vec3 f = fract(p) - .5;
        float h = fxHash(cell);
        if (h < threshold) return vec3(0.);
        vec3 offset = vec3(fxHash(cell + 1.7), fxHash(cell + 3.1), fxHash(cell + 5.3)) - .5;
        float r = length(f - offset * .7);
        float twinkle = .65 + .35 * sin(time * (1.5 + h * 5.) + h * 40.);
        float b = smoothstep(.09, 0., r) * (h - threshold) / (1. - threshold);
        vec3 tint = mix(vec3(.75, .85, 1.), vec3(1., .9, .75), fxHash(cell + 9.));
        return tint * b * twinkle;
      }
      void main(){
        vec3 d = normalize(vDir);
        float h = d.y;
        vec3 zenith = vec3(.0004, .0006, .0015);
        vec3 horizon = vec3(.005, .0055, .009);
        vec3 col = mix(horizon, zenith, smoothstep(0., .45, h));
        // sodium glow from distant towns and the site's own light pollution
        float az = atan(d.z, d.x);
        float town = pow(max(0., cos(az - 2.4)), 6.) * .055 + pow(max(0., cos(az + 0.9)), 10.) * .03;
        col += vec3(1., .55, .25) * town * .45 * exp(-max(h, 0.) * 16.);
        col += vec3(.025, .005, .008) * exp(-max(h, 0.) * 22.) * (.6 + .4 * cos(az * 2.));
        // high thin haze and a hint of the milky way
        float bd = dot(d, normalize(vec3(.35, .55, -.76))) * 3.2; float band = exp(-bd * bd);
        float milky = band * (.4 + .6 * fxNoise(d * 9.)) * (.5 + .5 * fxNoise(d * 28.));
        col += vec3(.016, .017, .024) * milky * smoothstep(.05, .35, h);
        if (h > -.02) {
          float fade = smoothstep(-.02, .12, h);
          col += (starLayer(d, 180., .965) + starLayer(d, 420., .985) * .8 + milky * starLayer(d, 700., .97) * .6) * fade * 2.2;
        }
        // faint haze band right at the horizon so the hills and far ground read as silhouettes
        col += vec3(.011, .010, .013) * exp(-abs(h) * 28.);
        col = mix(col, vec3(.004, .0045, .006), smoothstep(0., -.05, h));
        gl_FragColor = vec4(col, 1.);
      }`,
  });
}

export function createBackdrop(): Group {
  const root = new Group(); root.name = 'Backdrop';
  root.userData.iwsdkPreviewBounds = 'exclude';
  const sky = new Mesh(new SphereGeometry(470, 48, 24), skyMaterial());
  // Drawn last among opaque objects: its depth sits on the far plane, so every pixel already covered
  // by the ground, ramp or hills is rejected by the depth test before the star shader runs.
  sky.name = 'NightSky'; sky.renderOrder = 1000; sky.frustumCulled = false; root.add(sky);
  // Far ground: a faint pool of site light around the lane that falls off to the horizon.
  const outer = new Mesh(new CircleGeometry(480, 64), new ShaderMaterial({
    name: 'FarGround', fog: false,
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
    fragmentShader: `varying vec2 vP; ${NOISE_GLSL}
      void main(){ float r = length(vP * vec2(0.55, 1.0));
        float n = .7 + .3 * fxNoise2(vP * .03) * fxNoise2(vP * .11 + 4.);
        vec3 c = mix(vec3(.016, .014, .017), vec3(.0035, .0035, .0045), smoothstep(40., 380., r)) * n;
        gl_FragColor = vec4(c, 1.); }`,
  }));
  outer.name = 'OuterGround'; outer.rotation.x = -Math.PI / 2; outer.position.y = -0.03; root.add(outer);
  // Low distant hills ringing the site: one cheap strip, black against a faint horizon haze.
  {
    const segments = 160, radius = 440;
    const hillRandom = makeRandom(97);
    const heights = Array.from({ length: segments }, () => hillRandom());
    const positions: number[] = [];
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      const h0 = heights[i % segments], h1 = heights[(i + 7) % segments], h2 = heights[(i * 3) % segments];
      const h = 5 + 9 * (0.5 + 0.5 * Math.sin(a * 3 + 1)) * (0.6 + 0.4 * h1) + 4 * h0 * h2;
      positions.push(Math.cos(a) * radius, -2, Math.sin(a) * radius, Math.cos(a) * radius, h, Math.sin(a) * radius);
    }
    const index: number[] = [];
    for (let i = 0; i < segments; i++) { const k = i * 2; index.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    const hills = new Mesh(geometry, new MeshBasicMaterial({ color: '#020203', fog: false, side: DoubleSide }));
    hills.name = 'DistantHills'; hills.renderOrder = -5; hills.frustumCulled = false; root.add(hills);
  }

  const silhouette = new MeshBasicMaterial({ color: '#010102', fog: false });
  const random = makeRandom(4242);
  const parts: Matrix4[] = [];
  const glows: GlowSpec[] = [];
  const tanks: Matrix4[] = [];
  const q = new Quaternion();
  const add = (x: number, y: number, z: number, sx: number, sy: number, sz: number, yaw = 0): void => {
    q.setFromAxisAngle(new Vector3(0, 1, 0), yaw);
    parts.push(new Matrix4().compose(new Vector3(x, y, z), q, new Vector3(sx, sy, sz)));
  };
  const polar = (angle: number, radius: number): [number, number] => [Math.cos(angle) * radius, Math.sin(angle) * radius];
  const beacon = (x: number, y: number, z: number, rate = 0.5): void => { glows.push({ position: new Vector3(x, y, z), size: 0.9, color: [0.8, 0.04, 0.03], blink: rate, streak: 0 }); }; // small: they are 340-400 m out
  const work = (x: number, y: number, z: number, warm: boolean): void => {
    glows.push({ position: new Vector3(x, y, z), size: 1.2 + random() * 0.8, color: warm ? [0.7, 0.42, 0.2] : [0.55, 0.6, 0.7], streak: 0 });
  };

  // Sparse, far silhouettes: two vertical test stands, a water tower and a small tank farm.
  // They sit 330-420 m out, black against a near-black sky, so mostly their lights give them away.
  const stand = (angle: number, radius: number, height: number): void => {
    const [x, z] = polar(angle, radius);
    add(x, height / 2, z, 5, height, 5);              // stand tower
    add(x, height * 0.55, z + 4, 9, 1.2, 9);          // engine deck
    add(x + 3, height + 5, z, 0.8, 10, 0.8);          // lightning mast
    add(x - 7, height * 0.82, z, 14, 0.9, 0.9, 0.2);  // crane boom
    add(x, 2.5, z + 6, 22, 5, 10);                    // flame trench
    beacon(x + 3, height + 10.5, z, 0.35);
    work(x - 1, height * 0.55, z + 8.5, true); work(x + 2, height * 0.3, z + 3, false);
  };
  stand(-2.2, 360, 64);
  stand(-1.05, 400, 52);
  {
    const [x, z] = polar(-1.6, 340);
    for (const [dx, dz] of [[-4, -4], [4, -4], [-4, 4], [4, 4]]) add(x + dx, 15, z + dz, 0.7, 30, 0.7);
    beacon(x, 40, z, 0.3);
  }
  for (let i = 0; i < 3; i++) {
    const [x, z] = polar(-2.6 + i * 0.035, 330);
    tanks.push(new Matrix4().compose(new Vector3(x, 7 + i * 2, z), new Quaternion(), new Vector3(9, 14 + i * 4, 9)));
    if (i === 1) work(x, 18, z, false);
  }
  for (let i = 0; i < 8; i++) {
    const [x, z] = polar(-3 + random() * 2.6, 260 + random() * 140);
    work(x, 6 + random() * 4, z, random() > 0.4);
  }

  const mesh = new InstancedMesh(new BoxGeometry(1, 1, 1), silhouette, parts.length);
  mesh.name = 'DistantSite';
  parts.forEach((m, i) => mesh.setMatrixAt(i, m));
  mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere();
  root.add(mesh);
  const tankMesh = new InstancedMesh(new CylinderGeometry(0.5, 0.5, 1, 20), silhouette, tanks.length);
  tankMesh.name = 'TankFarm';
  tanks.forEach((m, i) => tankMesh.setMatrixAt(i, m));
  tankMesh.instanceMatrix.needsUpdate = true; tankMesh.computeBoundingSphere();
  root.add(tankMesh);
  // water tower tank
  const [wx, wz] = polar(-1.6, 340);
  const bowl = new Mesh(new SphereGeometry(7, 20, 12), silhouette); bowl.name = 'WaterTower'; bowl.position.set(wx, 34, wz); bowl.scale.y = 0.75; root.add(bowl);
  const glowMesh = createGlowSprites('DistantLights', glows, { minPixels: 5 });
  glowMesh.renderOrder = 5;
  root.add(glowMesh);
  return root;
}
