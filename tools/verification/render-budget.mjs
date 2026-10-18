// Per-frame render budget at key replay moments, counted at the WebGL level (every draw call in the
// frame, including shadow and post passes): draw calls, triangles, instanced draws, plus scene stats.
// Usage: npx @iwsdk/cli browser run tools/verification/render-budget.mjs --timeout 110000
export default async function ({ frame }) {
  await frame.waitForFunction(() => window.roadster && window.roadster.state().length === 1, null, { timeout: 60000 });
  await frame.evaluate(() => {
    if (window.__budget) return;
    const canvas = [...document.querySelectorAll('canvas')].find((c) => c.getContext('webgl2'));
    const gl = canvas.getContext('webgl2');
    const b = (window.__budget = { calls: 0, tris: 0, instanced: 0 });
    const tri = (mode, count, inst = 1) => (mode === gl.TRIANGLES ? count / 3 : mode === gl.TRIANGLE_STRIP ? count - 2 : 0) * inst;
    for (const [name, fn] of [['drawArrays', (m, f, c) => tri(m, c)], ['drawElements', (m, c) => tri(m, c)],
      ['drawArraysInstanced', (m, f, c, i) => tri(m, c, i)], ['drawElementsInstanced', (m, c, t, o, i) => tri(m, c, i)]]) {
      const orig = gl[name].bind(gl);
      gl[name] = (...a) => { b.calls++; b.tris += fn(...a); if (name.endsWith('Instanced')) b.instanced++; return orig(...a); };
    }
  });
  const frameStats = () => frame.evaluate(() => new Promise((r) => requestAnimationFrame(() => {
    const b = window.__budget; b.calls = 0; b.tris = 0; b.instanced = 0;
    requestAnimationFrame(() => r({ calls: b.calls, tris: Math.round(b.tris), instanced: b.instanced }));
  })));
  await frame.evaluate(() => { window.roadster.skipIntro?.(); window.roadster.pause(); });
  const out = [];
  for (const view of [0, 2]) {
    for (const t of [0.5, 6.0, 8.8, 10.5, 11.8, 13.5]) {
      await frame.evaluate(({ view, t }) => { window.roadster.view(view); window.roadster.seek(t); }, { view, t });
      await frameStats();
      const s = await frameStats();
      const scene = await frame.evaluate(() => {
        let lights = 0, shadow = 0, transparent = 0;
        window.roadsterScene?.().traverseVisible((o) => {
          if (o.isLight && !o.isAmbientLight && !o.isHemisphereLight) { lights++; if (o.castShadow) shadow++; }
          const m = Array.isArray(o.material) ? o.material[0] : o.material; if (m?.transparent) transparent++;
        });
        return { lights, shadow, transparent };
      });
      out.push({ view, t, ...s, ...scene });
    }
  }
  return out;
}
