// Captures the key replay moments for the visual overhaul review.
// Usage: npx @iwsdk/cli browser run tools/verification/capture-overhaul.mjs --timeout 180000
// Env: OVERHAUL_OUT (relative dir, default artifacts/overhaul/work), OVERHAUL_SHOTS (comma list of name:time:view)
import fs from 'node:fs/promises';
import path from 'node:path';

const DEFAULT_SHOTS = [
  ['01-ready', 0, 0], ['02-climb', 5, 0], ['03-release', 8.5, 0], ['04-reorient', 9.5, 0],
  ['05-descent', 10.8, 0], ['06-landing', 11.6, 0], ['07-driveaway', 13.5, 0],
];

export default async function ({ page, frame, workspaceRoot }) {
  const out = path.join(workspaceRoot, process.env.OVERHAUL_OUT || 'artifacts/overhaul/work');
  await fs.mkdir(out, { recursive: true });
  const shots = process.env.OVERHAUL_SHOTS
    ? process.env.OVERHAUL_SHOTS.split(',').map((s) => { const [n, t, v] = s.split(':'); return [n, Number(t), Number(v ?? 0)]; })
    : DEFAULT_SHOTS;
  const width = Number(process.env.OVERHAUL_W || 1600), height = Number(process.env.OVERHAUL_H || 900);
  await page.setViewportSize({ width, height });
  await page.mouse.move(width / 2, 60);
  await frame.waitForFunction(() => window.roadster && window.roadster.state().length === 1, null, { timeout: 60000 });
  await frame.waitForTimeout(800);
  const results = [];
  const shoot = async (file) => {
    if (frame === page.mainFrame()) await page.screenshot({ path: file });
    else await (await frame.frameElement()).screenshot({ path: file });
  };
  if (!process.env.OVERHAUL_NO_INTRO) {
    await frame.evaluate(() => { window.roadster.showIntro?.(); window.roadster.seek(0); });
    await frame.waitForTimeout(2200);
    await shoot(path.join(out, '00-intro.png'));
  }
  await frame.evaluate((post) => { window.roadster.skipIntro?.(); window.roadsterPost?.(post[0], post[1]); }, [process.env.OVERHAUL_POST !== '0', process.env.OVERHAUL_REFLECT !== '0']);
  await frame.waitForTimeout(900);
  for (const [name, time, view] of shots) {
    // Approach the moment by playing the last 0.6 s so time-integrated effects settle.
    await frame.evaluate(({ time, view }) => { window.roadster.view(view); window.roadster.seek(Math.max(0, time - 0.6)); window.roadster.play(); }, { time, view });
    await frame.waitForFunction((t) => window.roadster.state()[0].time >= t, time, { timeout: 15000 }).catch(() => {});
    await frame.evaluate(({ time }) => { window.roadster.seek(time); }, { time });
    await frame.waitForTimeout(350);
    const file = path.join(out, `${name}.png`);
    await shoot(file);
    results.push({ name, time, view, file, state: await frame.evaluate(() => window.roadster.state()[0]) });
  }
  const fps = await frame.evaluate(() => new Promise((resolve) => {
    let n = 0; const start = performance.now();
    const tick = () => { n++; if (performance.now() - start < 2000) requestAnimationFrame(tick); else resolve(n / ((performance.now() - start) / 1000)); };
    window.roadster.seek(10.6); window.roadster.play(); requestAnimationFrame(tick);
  }));
  const info = await frame.evaluate(() => window.roadsterRenderInfo ? window.roadsterRenderInfo().render : null);
  await fs.writeFile(path.join(out, 'captures.json'), JSON.stringify({ results, fps, info }, null, 2));
  return { count: results.length, out, fps, info };
}
