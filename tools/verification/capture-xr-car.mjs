import fs from 'node:fs/promises';import path from 'node:path';
export default async function({frame,workspaceRoot}) {
 await frame.waitForTimeout(250);
 const out=path.join(workspaceRoot,'artifacts/final-validation/xr-car.png');
 await frame.locator('canvas').first().screenshot({path:out});
 const state=await frame.evaluate(()=>window.roadster.state());
 await fs.writeFile(path.join(workspaceRoot,'artifacts/final-validation/xr-car-state.json'),JSON.stringify(state,null,2));
 return {path:out,state};
}
