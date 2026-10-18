import fs from 'node:fs/promises';
import path from 'node:path';
export default async function({page,frame,cdp,workspaceRoot}) {
 await page.setViewportSize({width:1440,height:1000});
 await frame.waitForFunction(()=>window.roadster?.state().length===1);
 const out=path.join(workspaceRoot,'artifacts/replay-recording');await fs.mkdir(out,{recursive:true});
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
 await fs.writeFile(path.join(out,'frames.json'),JSON.stringify({state,frames},null,2));
 return {frames:frames.length,state,path:out};
}
