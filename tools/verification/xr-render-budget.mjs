// Per-frame render budget inside an emulated XR session (IWER), counted at the WebGL level, with
// the headset at the lane edge looking at the ramp. Ends the session when done.
// Usage: npx @iwsdk/cli browser run tools/verification/xr-render-budget.mjs --timeout 110000
export default async function ({ frame }) {
  await frame.waitForFunction(() => window.roadster && window.roadster.state().length === 1, null, { timeout: 60000 });
  await frame.evaluate(() => {
    if (window.__budget) return;
    const canvas = [...document.querySelectorAll('canvas')].find((c) => c.getContext('webgl2'));
    const gl = canvas.getContext('webgl2');
    const b = (window.__budget = { calls: 0, tris: 0 });
    const tri = (mode, count, inst = 1) => (mode === gl.TRIANGLES ? count / 3 : mode === gl.TRIANGLE_STRIP ? count - 2 : 0) * inst;
    for (const [name, fn] of [['drawArrays', (m, f, c) => tri(m, c)], ['drawElements', (m, c) => tri(m, c)],
      ['drawArraysInstanced', (m, f, c, i) => tri(m, c, i)], ['drawElementsInstanced', (m, c, t, o, i) => tri(m, c, i)]]) {
      const orig = gl[name].bind(gl);
      gl[name] = (...a) => { b.calls++; b.tris += fn(...a); return orig(...a); };
    }
  });
  try {
    await frame.evaluate(() => { window.roadster.skipIntro?.(); (document.querySelector('#shell .pill-btn.xr') ?? document.querySelector('#shell [data-action="xr"]'))?.click(); });
    await frame.waitForFunction(() => !!window.IWER_DEVICE?.activeSession, null, { timeout: 15000 });
    await frame.waitForTimeout(1000);
    await frame.evaluate(async () => {
      const r = window.IWER_DEVICE.remote;
      await r.dispatch('set_transform', { device: 'headset', position: { x: -60, y: 1.65, z: -27 }, orientation: { x: 0, y: -0.38, z: 0, w: 0.92 } });
    });
    const out = [];
    for (const t of [0.5, 6.0, 8.8, 10.5, 11.8, 13.5]) {
      await frame.evaluate((t) => { window.roadster.pause(); window.roadster.seek(t); }, t);
      await frame.waitForTimeout(150);
      const s = await frame.evaluate(() => new Promise((r) => requestAnimationFrame(() => {
        const b = window.__budget; b.calls = 0; b.tris = 0;
        requestAnimationFrame(() => r({ calls: b.calls, tris: Math.round(b.tris) }));
      })));
      out.push({ t, ...s });
    }
    return out;
  } finally {
    await frame.evaluate(async () => { const s = window.IWER_DEVICE?.activeSession; if (s) await s.end(); });
  }
}
