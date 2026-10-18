import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {readFileSync} from 'node:fs';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const base=fileURLToPath(new URL('../../',import.meta.url));
const three=pathToFileURL(base+'node_modules/three/build/three.module.js').href;
const T=await import(three);
const {GLTFLoader}=await import(pathToFileURL(base+'node_modules/three/examples/jsm/loaders/GLTFLoader.js').href);
const coreStub='export * from '+JSON.stringify(three)+';export const VisibilityState={NonImmersive:"non-immersive",Hidden:"hidden",Visible:"visible",VisibleBlurred:"visible-blurred"};export const Types={Float32:0,Boolean:1,String:2};export const createComponent=(n,s)=>({name:n,schema:s});export const createSystem=()=>class{cleanupFuncs=[];};';
const stubURL='data:text/javascript;base64,'+Buffer.from(coreStub).toString('base64');
async function load(entry){const r=await build({entryPoints:[base+entry],bundle:true,write:false,platform:'node',format:'esm',external:['@iwsdk/core']});return import('data:text/javascript;base64,'+Buffer.from(r.outputFiles[0].text.replaceAll('"@iwsdk/core"',JSON.stringify(stubURL))).toString('base64'));}
const read=p=>JSON.parse(readFileSync(base+p));
const track=read('references/roadster/reconstruction/reconstruction.json'),config=read('iwsdk.config.json');
const {TrackPlayer}=await load('src/replay-track.ts');
const p=new TrackPlayer(track);let maxPositionError=0,maxQuaternionNormError=0,phaseMismatches=0,seed=71;
for(let n=0;n<20000;n++){seed=(1664525*seed+1013904223)>>>0;const t=seed/4294967296*22-2,tc=Math.max(0,Math.min(track.duration,t));let j=0;while(j<track.samples.length-2&&track.samples[j+1].time<=tc)j++;const a=track.samples[j],b=track.samples[j+1],f=(tc-a.time)/(b.time-a.time);p.evaluate(t);const v=new T.Vector3().fromArray(a.position).lerp(new T.Vector3().fromArray(b.position),f);maxPositionError=Math.max(maxPositionError,p.position.distanceTo(v));maxQuaternionNormError=Math.max(maxQuaternionNormError,Math.abs(p.quaternion.length()-1));if(p.phase!==(f<1?a.phase:b.phase))phaseMismatches++;}
const {createThrusters,createVapor}=await load('src/scene-assets/effects.scene-asset.ts'),{createApron,createRamp}=await load('src/scene-assets/stage.scene-asset.ts'),{ReplayEffects}=await load('src/replay-effects.ts');
const apron=createApron(),ramp=createRamp(track.ramp.centerline,track.ramp.width),ground=new T.Box3().setFromObject(apron.getObjectByName('Ground'));let deckError=0;const vertex=ramp.getObjectByName('DrivingDeck').geometry.attributes.position;
for(let i=0;i<track.ramp.centerline.length;i++){const mid=new T.Vector3().fromBufferAttribute(vertex,i*5).add(new T.Vector3().fromBufferAttribute(vertex,i*5+4)).multiplyScalar(.5);deckError=Math.max(deckError,mid.distanceTo(new T.Vector3().fromArray(track.ramp.centerline[i])));}
const bytes=readFileSync(base+'public/models/roadster.glb'),gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');gltf.scene.updateMatrixWorld(true);const modelBox=new T.Box3().setFromObject(gltf.scene);const wheels=['Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR'].map(name=>{const w=gltf.scene.getObjectByName(name);return{object:w,name,center:w.getWorldPosition(new T.Vector3()),radius:w.userData.radius_m}});const knots=[[-500,0,0],...track.ramp.centerline];let maxContactError=0,worstContact;
function distanceXY(p){let d=Infinity;for(let j=1;j<knots.length;j++){const a=knots[j-1],b=knots[j],dx=b[0]-a[0],dy=b[1]-a[1],f=Math.max(0,Math.min(1,((p.x-a[0])*dx+(p.y-a[1])*dy)/(dx*dx+dy*dy)));d=Math.min(d,Math.hypot(p.x-a[0]-f*dx,p.y-a[1]-f*dy));}return d;}
for(const sample of track.samples.filter(x=>x.time<=7.9))for(const w of wheels){const center=w.center.clone().applyQuaternion(new T.Quaternion().fromArray(sample.quaternion)).add(new T.Vector3().fromArray(sample.position)),error=distanceXY(center)-w.radius;if(Math.abs(error)>maxContactError){maxContactError=Math.abs(error);worstContact={time:sample.time,wheel:w.name,signedError:error};}}
// Effects: ReplayEffects(thrusters, vaporRoot, track, {lift, attitude} PointLights, atlas?) and update(time, car, camera).
// The vapor instances are depth-sorted and compacted each frame, so checks compare the active set rather than fixed indices.
const jets=createThrusters(),vapor=createVapor();vapor.position.set(12,0,-34);
const fxLights={lift:new T.PointLight(),attitude:new T.PointLight()},fx=new ReplayEffects(jets,vapor,track,fxLights),cam=new T.PerspectiveCamera();cam.position.set(1,2,3);cam.lookAt(0,0,0);cam.updateMatrixWorld(true);
const billboards=vapor.getObjectByName('VaporBillboards');
function effectState(t){p.evaluate(t);fx.update(t,p,cam);const n=billboards.count;const opacity=Array.from(billboards.geometry.attributes.cloudOpacity.array.slice(0,n));const matrices=Array.from(billboards.instanceMatrix.array.slice(0,n*16));
  const radii=[];for(let i=0;i<n;i++)radii.push(Math.hypot(matrices[i*16+12]-p.position.x,matrices[i*16+14]-p.position.z));
  return{count:n,opacity,matrices,radii,jets:jets.children.map(x=>({s:x.scale.toArray(),v:x.visible})),lights:[fxLights.lift.intensity,fxLights.attitude.intensity],p:jets.position.toArray(),q:jets.quaternion.toArray()};}
let effectsDeterministic=true,effectsFinite=true;for(const t of [0,6,8.15,9,10.5,11.6,14,18]){const a=effectState(t);effectState(0);effectState(18);const b=effectState(t);effectsDeterministic&&=JSON.stringify(a)===JSON.stringify(b);effectsFinite&&=a.matrices.every(Number.isFinite)&&a.opacity.every(x=>Number.isFinite(x)&&x>=0&&x<=1)&&a.lights.every(Number.isFinite);}
const landing=effectState(11.6),lingering=effectState(14),reset=effectState(0);const visibleBillboardsAtReset=reset.count;
const liftJetsAtDescent=effectState(10.5).jets.filter((j,i)=>i<4&&j.v).length;fx.dispose();
// Lift jets stay at the four car-local corners (not the rear NozzleAnchors).
const cornerJets=jets.children.filter(c=>c.name.startsWith('LiftJet_')).map(c=>c.position.toArray());
assert(effectsDeterministic&&effectsFinite);assert.equal(visibleBillboardsAtReset,0);assert(landing.count>80&&lingering.count>40);assert.equal(liftJetsAtDescent,4);
assert(cornerJets.every(([x,y,z])=>Math.abs(Math.abs(x)-1.05)<1e-6&&Math.abs(Math.abs(z)-.55)<1e-6));
// The full RoadsterSystem now needs a DOM (browser shell), a WebGL renderer (post-processing) and IWSDK entity creation;
// it is verified in the managed browser by tools/verification/capture-overhaul.mjs instead of this node harness.
assert(deckError<1e-5);assert(maxContactError<.015);assert(ground.min.x<Math.min(...track.samples.map(x=>x.position[0]))-3);
console.log(JSON.stringify({track:{count:20000,maxPositionError,maxQuaternionNormError,phaseMismatches},geometry:{deckError,groundMin:ground.min.toArray(),groundMax:ground.max.toArray(),modelSize:modelBox.getSize(new T.Vector3()).toArray(),maxContactError,worstContact},effects:{effectsDeterministic,effectsFinite,visibleBillboardsAtReset,landingPuffs:landing.count,lingeringPuffs:lingering.count,liftJetsAtDescent,cornerJets},runtime:'skipped: browser-verified'}));
