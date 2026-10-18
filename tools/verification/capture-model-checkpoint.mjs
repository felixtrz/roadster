import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
export default async function({page,frame,workspaceRoot}) {
 const bytes=await fs.readFile(path.join(workspaceRoot,'public/models/roadster.glb'));
 const hash=crypto.createHash('sha256').update(bytes).digest('hex');
 const out=path.join(workspaceRoot,'artifacts/model-runtime',hash.slice(0,12));await fs.mkdir(out,{recursive:true});
 await page.setViewportSize({width:1440,height:1000});
 await frame.waitForFunction(()=>window.roadsterRenderInfo&&window.roadster?.state().length===1);
 await frame.evaluate(()=>{window.roadster.pause();window.roadster.seek(0);window.roadster.view(2);});
 await frame.waitForTimeout(350);
 const file=path.join(out,'car.png');await frame.locator('canvas').first().screenshot({path:file});
 const metadata={modelSha256:hash,state:await frame.evaluate(()=>window.roadster.state()),render:await frame.evaluate(()=>window.roadsterRenderInfo()),imageSha256:crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')};
 await fs.writeFile(path.join(out,'capture.json'),JSON.stringify(metadata,null,2));
 return {path:out,...metadata};
}
