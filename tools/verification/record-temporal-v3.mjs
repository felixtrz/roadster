import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
export default async function({page,frame,cdp,workspaceRoot}) {
 await page.setViewportSize({width:1440,height:1000});
 await frame.waitForFunction(()=>window.roadster?.state().length===1);
 const out=path.join(workspaceRoot,'artifacts/replay-recording-v9');await fs.mkdir(out,{recursive:true});
 if ((await frame.evaluate(()=>window.roadster.state()[0].speed)) !== 1) {
  await page.mouse.click(1250,910);
  await frame.waitForFunction(()=>window.roadster.state()[0].speed===1);
 }
 const files=[];
 for(const file of ['public/models/roadster.glb','public/scenes/main.iwsdk.scene.json','src/replay-system.ts','src/replay-effects.ts','src/scene-assets/stage.scene-asset.ts','src/scene-assets/effects.scene-asset.ts','public/textures/vapor-atlas.png','references/roadster/reconstruction/reconstruction.json']) {
  const b=await fs.readFile(path.join(workspaceRoot,file));files.push({file,bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')});
 }
 const frames=[],pending=new Set();
 const listener=(event)=>{
  const index=frames.length;frames.push({index,timestamp:event.metadata.timestamp});
  const work=fs.writeFile(path.join(out,`frame-${String(index).padStart(5,'0')}.jpg`),Buffer.from(event.data,'base64')).then(()=>cdp.send('Page.screencastFrameAck',{sessionId:event.sessionId}));
  pending.add(work);work.finally(()=>pending.delete(work));
 };
 await frame.evaluate(()=>{window.roadster.view(0);window.roadster.seek(0);});
 cdp.on('Page.screencastFrame',listener);
 await cdp.send('Page.startScreencast',{format:'jpeg',quality:88,maxWidth:1440,maxHeight:1000,everyNthFrame:2});
 await frame.evaluate(()=>window.roadster.restart());
 await frame.waitForTimeout(18800);
 await cdp.send('Page.stopScreencast');cdp.off('Page.screencastFrame',listener);await Promise.all(pending);
 const state=await frame.evaluate(()=>window.roadster.state());
 assert.equal(state[0].time,18);assert.equal(state[0].playing,false);assert.equal(state[0].speed,1);
 await fs.writeFile(path.join(out,'frames.json'),JSON.stringify({state,files,frames},null,2));
 return {frames:frames.length,state,path:out};
}
