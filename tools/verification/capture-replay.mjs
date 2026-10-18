import fs from 'node:fs/promises';
import path from 'node:path';
export default async function ({page,frame,workspaceRoot}) {
  await page.setViewportSize({width:1440,height:1000});
  await frame.waitForFunction(()=>window.roadster?.state().length===1);
  const out=path.join(workspaceRoot,'artifacts/runtime');
  await fs.mkdir(out,{recursive:true});
  const observations=[];
  for(const [name,time,view] of [['ready',0,0],['climb',6,0],['release',8.2,0],['flip',9,0],['descent',10.5,0],['landing',11.6,0],['driveaway',14,0],['car',0,2],['wide',8.2,1]]) {
    await frame.evaluate(({time,view})=>{window.roadster.pause();window.roadster.seek(time);window.roadster.view(view);},{time,view});
    await frame.waitForTimeout(150);
    observations.push({name,state:await frame.evaluate(()=>window.roadster.state())});
    await frame.locator('canvas').first().screenshot({path:path.join(out,`${name}.png`)});
  }
  await fs.writeFile(path.join(out,'capture-observations.json'),JSON.stringify(observations,null,2));
  return observations;
}
