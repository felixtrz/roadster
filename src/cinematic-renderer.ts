import { AdditiveBlending, HalfFloatType, LinearMipmapLinearFilter, PlaneGeometry, Vector2, Vector3, WebGLRenderTarget, type World } from '@iwsdk/core';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { FX_TIME, NOISE_GLSL } from './scene-assets/lib/fx-materials.js';

/** The HDR post chain (4x MSAA half-float) is capped at 1.5x device pixels: on high-DPI screens this
 * roughly halves its fill and memory in a dark, bloom-heavy scene where the difference is not visible. */
const postPixelRatio = (deviceRatio: number): number => Math.min(1.5, deviceRatio);

/** Blurred, puddle-masked planar reflection added on top of the dark asphalt. */
const WetReflectionShader = {
  name: 'WetReflection',
  uniforms: {
    color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null },
    siteOffset: { value: new Vector2() }, time: FX_TIME,
  },
  vertexShader: /* glsl */ `
    uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vWorld;
    void main(){ vUv = textureMatrix * vec4(position, 1.0); vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz;
      gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse; uniform vec2 siteOffset; uniform float time;
    varying vec4 vUv; varying vec3 vWorld;
    ${NOISE_GLSL}
    vec2 rot(vec2 p, float a){ float c=cos(a), s=sin(a); return vec2(c*p.x-s*p.y, s*p.x+c*p.y); }
    float wetMask(vec2 p){ float n=.6*fxNoise2(p*.07)+.3*fxNoise2(rot(p,1.1)*.21+17.3)+.1*fxNoise2(rot(p,2.3)*.9+5.1); return smoothstep(.48,.6,n); }
    void main(){
      vec2 lp = vWorld.xz - siteOffset;
      float wet = wetMask(lp);
      vec2 uv = vUv.xy / vUv.w;
      vec2 ripple = (vec2(fxNoise2(lp * 0.6), fxNoise2(lp * 0.6 + 7.3)) - 0.5) * mix(0.0022, 0.0006, wet);
      float blur = mix(0.016, 0.008, wet);
      vec3 acc = vec3(0.0);
      for (int i = 0; i < 8; i++) {
        float a = float(i) * 2.399963;
        float r = sqrt(float(i) + 0.5) / 2.9;
        acc += texture2D(tDiffuse, uv + ripple + vec2(cos(a) * 0.5, sin(a) * 1.2) * r * blur, 2.5).rgb;
      }
      acc /= 8.0;
      // soft-clip hot sources (taillights, lenses) so they smear into a sheen instead of a mirrored slab
      acc = acc / (1.0 + max(max(acc.r, acc.g), acc.b) * 0.6);
      vec3 V = normalize(cameraPosition - vWorld);
      float fresnel = 0.05 + 0.95 * pow(1.0 - clamp(V.y, 0.0, 1.0), 5.0);
      float strength = mix(0.02, 0.13, wet) * fresnel * (1.0 - smoothstep(22.0, 55.0, distance(cameraPosition, vWorld)));
      float edge = (1.0 - smoothstep(95.0, 120.0, abs(lp.x + 60.0))) * (1.0 - smoothstep(22.0, 31.0, abs(lp.y)));
      gl_FragColor = vec4(acc * strength * edge * vec3(0.9, 0.93, 1.0), 1.0);
    }`,
};

/**
 * Browser-only cinematic pipeline: HDR render -> bloom -> filmic output, plus a
 * wet-asphalt planar reflection. While an XR session presents, rendering falls
 * straight through to the stock IWSDK path and the reflection is hidden.
 */
export class CinematicRenderer {
  readonly composer: EffectComposer;
  readonly bloom: UnrealBloomPass;
  private readonly reflector: Reflector;
  private readonly originalRender: World['renderer']['render'];
  private inComposer = false;
  enabled = true;
  reflection = true;
  private readonly onResize = (): void => this.resize();

  constructor(private readonly world: World, siteOffset: Vector3) {
    const renderer = world.renderer;
    const size = renderer.getSize(new Vector2());
    const ratio = postPixelRatio(renderer.getPixelRatio());
    const target = new WebGLRenderTarget(size.x * ratio, size.y * ratio, { type: HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(renderer, target);
    // Only the scene render is multisampled. The sanitize pass resolves into a single-sample
    // buffer, because bloom blends additively into its read buffer and a resolved MSAA
    // buffer is invalidated (which would leave only the bloom).
    this.composer.renderTarget1.samples = 0; // RenderPass draws into renderTarget2 (the initial read buffer)
    this.composer.addPass(new RenderPass(world.scene, world.camera));
    // Bloom's low mips smear any stray NaN/Inf pixel across the frame; scrub them and clamp fireflies first.
    this.composer.addPass(new ShaderPass({
      name: 'HdrSanitize',
      uniforms: { tDiffuse: { value: null } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform sampler2D tDiffuse; varying vec2 vUv;
        void main(){ vec4 c = texture2D(tDiffuse, vUv);
          bool bad = any(isnan(c.rgb)) || any(isinf(c.rgb));
          gl_FragColor = vec4(bad ? vec3(0.0) : clamp(c.rgb, 0.0, 48.0), 1.0); }`,
    }));
    this.bloom = new UnrealBloomPass(new Vector2(size.x, size.y), 0.5, 0.4, 1.05);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.reflector = new Reflector(new PlaneGeometry(240, 64), {
      textureWidth: Math.max(256, size.x * 0.5), textureHeight: Math.max(256, size.y * 0.5), clipBias: 0.002,
      shader: WetReflectionShader, multisample: 0,
    });
    this.reflector.name = 'WetReflection';
    this.reflector.rotation.x = -Math.PI / 2;
    this.reflector.position.set(siteOffset.x - 60, 0.006, siteOffset.z);
    const material = this.reflector.material as import('@iwsdk/core').ShaderMaterial;
    material.transparent = true; material.depthWrite = false;
    material.blending = AdditiveBlending;
    material.uniforms.siteOffset.value.set(siteOffset.x, siteOffset.z);
    this.reflector.renderOrder = 1;
    // Mipmapped reflection so the shader can sample a pre-blurred level instead of stair-stepped texels.
    const reflectionTexture = this.reflector.getRenderTarget().texture;
    reflectionTexture.generateMipmaps = true;
    reflectionTexture.minFilter = LinearMipmapLinearFilter;
    world.createTransformEntity(this.reflector);

    this.originalRender = renderer.render.bind(renderer);
    renderer.render = (scene, camera) => {
      if (this.enabled && !this.inComposer && scene === world.scene && camera === world.camera && !renderer.xr.isPresenting) {
        this.inComposer = true;
        try { this.composer.render(); } finally { this.inComposer = false; }
        return;
      }
      this.originalRender(scene, camera);
    };
    window.addEventListener('resize', this.onResize);
    this.resize();
  }

  /** Called every frame: hides the reflection inside XR. */
  update(xr: boolean): void {
    this.reflector.visible = !xr && this.enabled && this.reflection;
  }

  private resize(): void {
    const renderer = this.world.renderer;
    const size = renderer.getSize(new Vector2());
    this.composer.setPixelRatio(postPixelRatio(renderer.getPixelRatio()));
    this.composer.setSize(size.x, size.y);
    this.reflector.getRenderTarget().setSize(Math.max(256, Math.floor(size.x * renderer.getPixelRatio() * 0.5)), Math.max(256, Math.floor(size.y * renderer.getPixelRatio() * 0.5)));
  }

  dispose(): void {
    this.world.renderer.render = this.originalRender;
    window.removeEventListener('resize', this.onResize);
    this.composer.dispose();
    this.reflector.dispose();
  }
}
