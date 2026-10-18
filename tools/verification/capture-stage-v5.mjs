import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
export default async function({page,frame,workspaceRoot}) {
 const root=path.join(workspaceRoot,'artifacts/stage-review-input-v5');await fs.mkdir(root,{recursive:true});
 const checks=[];
 for(const [aspect,width,height,shots] of [
  ['landscape',1440,1000,[['ready',0,0],['climb',6,0],['release',8.1,0],['flip',8.8,0],['jets',9.5,0],['descent',10.5,0],['landing',11.6,0],['clearance',13,0],['end',18,0],['car',0,2],['wide',8.2,1],['wide-end',18,1],['overhead',9,3]]],
  ['portrait',900,1200,[['release',8.1,0],['descent',10.5,0],['landing',11.6,0],['wide-end',18,1]]]
 ]) {
  await page.setViewportSize({width,height});await frame.waitForFunction(()=>window.roadsterRenderInfo&&window.roadster?.state().length===1);
  await frame.waitForTimeout(300);
  for(const [name,time,view] of shots){
   await frame.evaluate(({time,view})=>{window.roadster.pause();window.roadster.seek(time);window.roadster.view(view);},{time,view});await frame.waitForTimeout(200);
   const filename=`${aspect}-${name}.png`;await frame.locator('canvas').first().screenshot({path:path.join(root,filename)});
   checks.push({filename,time,view,state:await frame.evaluate(()=>window.roadster.state()),render:await frame.evaluate(()=>window.roadsterRenderInfo())});
  }
 }
 await fs.writeFile(path.join(root,'captures.json'),JSON.stringify(checks,null,2));
 const files=[];
 for(const n of [...checks.map(c=>`artifacts/stage-review-input-v5/${c.filename}`),'src/replay-system.ts','src/replay-effects.ts','src/scene-assets/stage.scene-asset.ts','src/scene-assets/effects.scene-asset.ts','public/scenes/main.iwsdk.scene.json','public/models/roadster.glb','public/ui/replay.uikitml','public/textures/vapor-atlas.png','src/assets.ts','references/roadster/reconstruction/reconstruction.json']){
  const b=await fs.readFile(path.join(workspaceRoot,n));files.push({path:n,bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')});
 }
 await fs.writeFile(path.join(root,'snapshot-manifest.json'),JSON.stringify({version:5,files},null,2));
 return {captures:checks.length,path:root};
}
