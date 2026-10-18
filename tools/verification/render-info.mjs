export default async function({frame}){await frame.waitForFunction(()=>window.roadsterRenderInfo);return frame.evaluate(()=>window.roadsterRenderInfo());}
