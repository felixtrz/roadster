// Plays through the climb and captures consecutive frames to check temporal stability.
// Usage: npx @iwsdk/cli browser run tools/verification/flicker-check.mjs --timeout 100000
import fs from 'node:fs/promises';
import path from 'node:path';
export default async function ({ page, frame, workspaceRoot }) {
  const out = path.join(workspaceRoot, process.env.FLICKER_OUT || 'artifacts/verification/flicker');
  await fs.mkdir(out, { recursive: true });
  await page.setViewportSize({ width: 1600, height: 900 });
  await frame.waitForFunction(() => window.roadster && window.roadster.state().length === 1, null, { timeout: 60000 });
  const shots = (process.env.FLICKER_SHOTS || 'climb:5.4:0,air:9.2:2,descent:10.6:0').split(',');
  await frame.evaluate(() => window.roadster.skipIntro?.());
  for (const s of shots) {
    const [name, t, v] = s.split(':');
    await frame.evaluate(({ t, v }) => { window.roadster.view(Number(v)); window.roadster.seek(Number(t) - 0.5); window.roadster.play(); }, { t, v });
    await frame.waitForFunction((tt) => window.roadster.state()[0].time >= tt, Number(t), { timeout: 15000 }).catch(() => {});
    for (let k = 0; k < 4; k++) {
      const el = frame === page.mainFrame() ? page : await frame.frameElement();
      await el.screenshot({ path: path.join(out, `${name}-${k}.png`) });
      await frame.waitForTimeout(40);
    }
  }
  await frame.evaluate(() => window.roadster.pause());
  return { ok: true };
}
