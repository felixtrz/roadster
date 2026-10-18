import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
const base=fileURLToPath(new URL('../../',import.meta.url));
const baseline=JSON.parse(execFileSync(process.execPath,[base+'tools/verification/runtime-harness.mjs'],{encoding:'utf8'}));
const three=pathToFileURL(base+'node_modules/three/build/three.module.js').href;
const T=await import(three);
const {GLTFLoader}=await import(pathToFileURL(base+'node_modules/three/examples/jsm/loaders/GLTFLoader.js').href);
const stub='export * from '+JSON.stringify(three)+';export const VisibilityState={NonImmersive:"non-immersive",Hidden:"hidden",Visible:"visible",VisibleBlurred:"visible-blurred"};export const Types={Float32:0,Boolean:1,String:2};export const createComponent=(n,s)=>({name:n,schema:s});export const createSystem=()=>class{cleanupFuncs=[];};';
const stubURL='data:text/javascript;base64,'+Buffer.from(stub).toString('base64');
async function load(entry){const r=await build({entryPoints:[base+entry],bundle:true,write:false,format:'esm',platform:'node',external:['@iwsdk/core']});return import('data:text/javascript;base64,'+Buffer.from(r.outputFiles[0].text.replaceAll('"@iwsdk/core"',JSON.stringify(stubURL))).toString('base64'));}
const read=p=>JSON.parse(readFileSync(base+p));
const track=read('references/roadster/reconstruction/reconstruction.json'),config=read('iwsdk.config.json');
const {TrackPlayer}=await load('src/replay-track.ts');
const {ReplayEffects}=await load('src/replay-effects.ts');
const {createVapor,createThrusters}=await load('src/scene-assets/effects.scene-asset.ts');
const {RoadsterSystem}=await load('src/replay-system.ts');
const {createApron}=await load('src/scene-assets/stage.scene-asset.ts');
const player=new TrackPlayer(track),camera=new T.PerspectiveCamera();camera.position.set(6,1.5,7);camera.lookAt(0,.7,0);const offset=new T.Vector3(12,0,-34);
const vaporPrototype=createVapor(),jetPrototype=createThrusters(),prototypeMesh=vaporPrototype.getObjectByName('VaporBillboards');
const snapshot=g=>{const v=g.getObjectByName('VaporBillboards');return {opacity:Array.from(v.geometry.attributes.cloudOpacity.array),softness:Array.from(v.geometry.attributes.cloudBottomSoftness.array),seeds:Array.from(v.geometry.attributes.cloudSeed.array),matrices:Array.from(v.instanceMatrix.array)};};
const prototypeSnapshot=JSON.stringify(snapshot(vaporPrototype));
const prototypeJetMaterials=new Set();jetPrototype.traverse(o=>{if(o.isMesh)prototypeJetMaterials.add(o.material);});
const prototypeResources=[prototypeMesh.geometry,prototypeMesh.material,...prototypeJetMaterials];let prototypeDisposed=0;for(const r of prototypeResources)r.addEventListener('dispose',()=>prototypeDisposed++);
const branches=[];
for(const useTexture of [false,true]){
  const atlas=useTexture?new T.Texture():null;let atlasDisposed=0;if(atlas)atlas.addEventListener('dispose',()=>atlasDisposed++);
  const a=vaporPrototype.clone(true),b=vaporPrototype.clone(true),ja=jetPrototype.clone(true),jb=jetPrototype.clone(true);
  assert.equal(a.getObjectByName('VaporBillboards').geometry,prototypeMesh.geometry);
  const fa=new ReplayEffects(ja,a,track,atlas),fb=new ReplayEffects(jb,b,track,atlas);
  const va=a.getObjectByName('VaporBillboards'),vb=b.getObjectByName('VaporBillboards');
  assert.notEqual(va.geometry,prototypeMesh.geometry);assert.notEqual(vb.geometry,prototypeMesh.geometry);assert.notEqual(va.geometry,vb.geometry);
  for(const key of ['cloudOpacity','cloudBottomSoftness','cloudSeed']){assert.notEqual(va.geometry.attributes[key].array,prototypeMesh.geometry.attributes[key].array);assert.notEqual(va.geometry.attributes[key].array,vb.geometry.attributes[key].array);}
  assert.notEqual(va.instanceMatrix.array,vb.instanceMatrix.array);
  assert.notEqual(va.material,vb.material);assert.notEqual(va.material,prototypeMesh.material);
  assert.equal(va.material.uniforms.useAtlas.value,useTexture?1:0);assert.equal(va.material.uniforms.cloudTexture.value,atlas);
  if(atlas)assert.equal(atlas.colorSpace,T.NoColorSpace);
  const beforeB=JSON.stringify(snapshot(b));
  player.evaluate(11.6);fa.update(11.6,player,camera,offset);const stateA=JSON.stringify(snapshot(a));
  assert.equal(JSON.stringify(snapshot(b)),beforeB);assert.equal(JSON.stringify(snapshot(vaporPrototype)),prototypeSnapshot);
  player.evaluate(14);fb.update(14,player,camera,offset);assert.equal(JSON.stringify(snapshot(a)),stateA);
  const jaMaterials=new Set(),jbMaterials=new Set();ja.traverse(o=>{if(o.isMesh)jaMaterials.add(o.material);});jb.traverse(o=>{if(o.isMesh)jbMaterials.add(o.material);});
  for(const m of jaMaterials){assert(!prototypeJetMaterials.has(m));assert(!jbMaterials.has(m));assert.equal(m.uniforms.time.value,11.6);}
  for(const m of jbMaterials)assert.equal(m.uniforms.time.value,14);
  for(const m of prototypeJetMaterials)assert.equal(m.uniforms.time.value,0);
  let deterministic=true,finite=true;for(const t of [0,9.7,10.2,10.5,11.6,14,16,18]){player.evaluate(t);fa.update(t,player,camera,offset);const first=JSON.stringify(snapshot(a));player.evaluate(18);fa.update(18,player,camera,offset);player.evaluate(0);fa.update(0,player,camera,offset);player.evaluate(t);fa.update(t,player,camera,offset);deterministic&&=first===JSON.stringify(snapshot(a));const s=snapshot(a);finite&&=s.matrices.every(Number.isFinite)&&s.opacity.every(v=>Number.isFinite(v)&&v>=0&&v<=1)&&s.softness.every(v=>Number.isFinite(v)&&v>=0&&v<=1);}
  assert(deterministic&&finite);
  player.evaluate(0);fa.update(0,player,camera,offset);assert(va.geometry.attributes.cloudOpacity.array.every(v=>v===0));
  const owned=[va.geometry,vb.geometry,va.material,vb.material,...jaMaterials,...jbMaterials];const disposeCounts=new Map(owned.map(r=>[r,0]));for(const r of owned)r.addEventListener('dispose',()=>disposeCounts.set(r,disposeCounts.get(r)+1));fa.dispose();fb.dispose();assert([...disposeCounts.values()].every(v=>v===1));assert.equal(prototypeDisposed,0);assert.equal(atlasDisposed,0);
  branches.push({texture:useTexture?'world-owned texture':'null/fallback',liveGeometryIndependentFromPrototype:true,instancesMutuallyIsolated:true,prototypeAttributesAndUniformsUnchanged:true,deterministic,finite,resetOpacityZero:true,ownedResourceCount:owned.length,eachOwnedResourceDisposedExactlyOnce:true,prototypeDisposeEvents:prototypeDisposed,atlasDisposeEvents:atlasDisposed});
}
const bytes=readFileSync(base+'public/models/roadster.glb');const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const shadowBranches=[];
for(const useTexture of [false,true]){
  globalThis.window=new EventTarget();const car=new T.Group();car.add(gltf.scene.clone(true));const map={roadster:car,thrusters:jetPrototype.clone(true),vapor:vaporPrototype.clone(true),apron:createApron()};const fields={elapsed:0,playing:false,speed:1,phase:'ready'},entity={object3D:car,getValue:(c,k)=>fields[k],setValue:(c,k,v)=>fields[k]=v};const elements=new Map();map.controls={requireElementById(id){if(!elements.has(id)){const e=new EventTarget();e.setProperties=()=>{};elements.set(id,e);}return elements.get(id);}};
  let visibility='non-immersive';const subscriptions=new Set(),origin=new T.Group(),cam=new T.PerspectiveCamera(42,1.44,config.world.render.near,config.world.render.far);origin.add(cam);const atlas=useTexture?new T.Texture():null;const requests=[];const world={requireSceneObject:id=>map[id],assetManager:{getTexture(id){requests.push(id);return atlas;}},scene:new T.Scene(),camera:cam,renderer:{shadowMap:{enabled:false}},visibilityState:{peek:()=>visibility,subscribe(fn){subscriptions.add(fn);fn(visibility);return()=>subscriptions.delete(fn);}},xrEnabled:true};
  const sys=new RoadsterSystem();sys.world=world;sys.queries={cars:{entities:[entity]}};sys.init();assert.deepEqual(requests,['vapor-atlas']);
  const meshes=[];car.traverse(o=>{if(o.isMesh)meshes.push(o);});assert(meshes.length>0);assert(meshes.every(m=>!m.castShadow));let hotTraversals=0;const traverse=car.traverse;car.traverse=function(...args){hotTraversals++;return traverse.apply(this,args);};
  const checks=[];for(const t of [0,6,10.5,0,9,11.6,18,6,0]){window.roadster.seek(t);sys.update(0);const expected=player.evaluate(t).position.y<1;assert(meshes.every(m=>m.castShadow===expected));checks.push({time:t,carY:player.position.y,castsShadow:expected,allMeshesAgree:true});}assert.equal(hotTraversals,0);
  window.roadster.view(2);window.roadster.seek(0);sys.update(0);assert(Math.abs(cam.getWorldPosition(new T.Vector3()).y-1.5)<1e-9);
  const v=map.vapor.getObjectByName('VaporBillboards');assert.equal(v.material.uniforms.useAtlas.value,useTexture?1:0);assert.equal(v.material.uniforms.cloudTexture.value,atlas);
  sys.cleanupFuncs.forEach(f=>f());assert.equal(subscriptions.size,0);assert(!('roadster'in window));assert(!('roadsterRenderInfo'in window));
  shadowBranches.push({texture:useTexture,assetManagerRequests:requests,meshCount:meshes.length,shadowSeekChecks:checks,hotTraversalCalls:hotTraversals,carViewEyeHeightMetres:1.5,cleanupPassed:true});
}
const scene=read('public/scenes/main.iwsdk.scene.json');
const apronNode=scene.nodes.find(n=>n.id==='apron');assert.deepEqual(apronNode.transform.position,[12,0,-34]);
const apron=createApron(),asphalt=apron.getObjectByName('Ground').material;
const shader={vertexShader:T.ShaderLib.standard.vertexShader,fragmentShader:T.ShaderLib.standard.fragmentShader,uniforms:{}};
asphalt.onBeforeCompile(shader);
assert(shader.vertexShader.includes('roadPosition=position;'));
assert(shader.fragmentShader.includes('float centerPaint='));assert(shader.fragmentShader.includes('float boundaryFade='));assert(shader.fragmentShader.includes('(envMapIntensity*0.015)'));
const floodChecks=[];for(const node of scene.nodes.filter(n=>n.id?.startsWith('flood-'))){const x=node.transform.position[0]-12;const lens=apron.getObjectByName(`FloodLens-${x}-0`);assert(lens);const expected=lens.position.clone().add(new T.Vector3(12,0,-34)),actual=new T.Vector3().fromArray(node.transform.position),distance=expected.distanceTo(actual);assert(distance<.4);floodChecks.push({id:node.id,source:actual.toArray(),lensCenter:expected.toArray(),distance});}
assert.equal(floodChecks.length,5);
const stageChecks={groundShaderPatchApplied:true,groundUsesCanonicalParentOffset:true,floodChecks};
const files=['src/replay-track.ts','src/replay-system.ts','src/replay-controls.ts','src/replay-effects.ts','src/scene-assets/stage.scene-asset.ts','src/scene-assets/effects.scene-asset.ts','src/assets.ts','public/textures/vapor-atlas.png','public/models/roadster.glb','public/scenes/main.iwsdk.scene.json','iwsdk.config.json','tools/verification/runtime-harness.mjs','references/roadster/reconstruction/reconstruction.json'];
const hashes=Object.fromEntries(files.map(f=>[f,createHash('sha256').update(readFileSync(base+f)).digest('hex')]));
console.log(JSON.stringify({baseline,branches,shadowBranches,prototypeDisposeEvents:prototypeDisposed,stageChecks,hashes},null,2));
