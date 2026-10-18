// Frame-exact film capture: steps the replay clock and (for XR shots) the emulated headset and
// controllers from a shot plan, then screenshots each frame. Effects and cameras are pure functions
// of replay time, so frames are identical to real-time playback at any capture speed.
// Usage: FILM_PLAN=tools/film/out/plan-2d.json FILM_OUT=artifacts/film/2d FILM_START=0 FILM_COUNT=300 \
//          npx @iwsdk/cli browser run tools/film/capture-frames.mjs --timeout 110000
// Plan: { mode: '2d'|'xr', width, height, hideShell?, frames: [{ t, view?, head?: [x,y,z,qx,qy,qz,qw],
//         left?: [...7], right?: [...7], camera?: { position, target, fov } | null, shellOpacity?: 0..1 }] }
import fs from 'node:fs/promises';
import path from 'node:path';

export default async function ({ page, frame, workspaceRoot }) {
  const plan = JSON.parse(await fs.readFile(path.join(workspaceRoot, process.env.FILM_PLAN), 'utf8'));
  const out = path.join(workspaceRoot, process.env.FILM_OUT);
  await fs.mkdir(out, { recursive: true });
  const start = Number(process.env.FILM_START || 0);
  const count = Number(process.env.FILM_COUNT || plan.frames.length);
  const deadline = Date.now() + Number(process.env.FILM_BUDGET_MS || 100000);
  await page.setViewportSize({ width: plan.width, height: plan.height });
  await frame.waitForFunction(() => window.roadster && window.roadster.state().length === 1, null, { timeout: 60000 });
  await frame.evaluate(({ mode, hideShell }) => {
    window.__filmIntro = undefined;
    let style = document.getElementById('film-style');
    if (!style) { style = document.createElement('style'); style.id = 'film-style'; document.head.appendChild(style); }
    // Dev/emulator chrome never belongs in the film; the transport bar is hidden, the HUD stays.
    style.textContent = `${mode === 'xr' ? '' : 'body > *:not(#scene-container):not(#shell):not(script):not(style):not(canvas) { opacity: 0 !important; pointer-events: none !important; }'}
      #shell .transport, #shell .tooltip { display: none !important; }
      ${hideShell || mode === 'xr' ? '#shell { display: none !important; }' : ''}`;
  }, { mode: plan.mode, hideShell: !!plan.hideShell });
  if (frame !== page.mainFrame()) {
    // Managed-window chrome (Runtime/Editor toggle) lives in the parent page: hide anything fixed
    // that is not the runtime iframe's container.
    await page.evaluate(() => {
      for (const node of document.querySelectorAll('body *')) {
        const st = getComputedStyle(node);
        if ((st.position === 'fixed' || st.position === 'absolute') && !node.querySelector('iframe') && node.tagName !== 'IFRAME') node.style.visibility = 'hidden';
      }
    });
  }
  if (plan.mode === 'xr') {
    // The emulated XR framebuffer keeps the page size it had when the session started, and the
    // managed page is resized between leases: restart the session at the film size in this lease.
    await frame.evaluate(async () => { const s = window.IWER_DEVICE?.activeSession; if (s) { await s.end(); } });
    await frame.waitForTimeout(800);
    await frame.evaluate(() => { const st = document.getElementById('film-style'); if (st) st.textContent = ''; });
    await frame.evaluate(() => { window.roadster.skipIntro?.(); (document.querySelector('#shell .pill-btn.xr') ?? document.querySelector('#shell [data-action="xr"]'))?.click(); });
    await frame.waitForFunction(() => !!window.IWER_DEVICE?.activeSession, null, { timeout: 15000 });
    await frame.waitForTimeout(1200);
    await frame.evaluate(() => { const st = document.getElementById('film-style'); if (st) st.textContent = '#shell { display: none !important; }'; });
    // IWER's emulator UI (frame border, "Remote Control Active" pill, panels) overlays the view.
    await frame.evaluate(() => {
      for (const node of document.querySelectorAll('body *')) {
        if (node.tagName === 'CANVAS' && getComputedStyle(node).zIndex === '3') { node.style.visibility = 'hidden'; continue; }
        if (node.tagName === 'CANVAS' || node.querySelector('canvas')) continue;
        const st = getComputedStyle(node);
        if (st.position === 'fixed' || st.position === 'absolute') node.style.visibility = 'hidden';
      }
    });
  }
  // 2D shots render at 2x device pixels; the screenshot is taken at 1x, so every edge is supersampled.
  const supersample = plan.mode === 'xr' ? null : Number(process.env.FILM_SUPERSAMPLE || plan.supersample || 2);
  if (supersample) await frame.evaluate((r) => window.roadsterSupersample?.(r), supersample);
  const raf = () => frame.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(0)))));
  let done = 0;
  for (let i = start; i < Math.min(plan.frames.length, start + count); i++) {
    if (Date.now() > deadline) break;
    const f = plan.frames[i];
    await frame.evaluate((f) => {
      if (f.view !== undefined) window.roadster.view(f.view);
      // scripted film camera (world-space pose and lens) overrides the director; null hands it back
      if (f.camera !== undefined) window.roadsterFilmCamera?.(f.camera);
      if (f.shellOpacity !== undefined) { const sh = document.getElementById('shell'); if (sh) sh.style.opacity = String(f.shellOpacity); }
      if (f.intro === true && !window.__filmIntro) { window.roadster.showIntro?.(); window.__filmIntro = 'new'; }
      if (f.intro === false && window.__filmIntro !== false) { window.roadster.skipIntro?.(); window.__filmIntro = false; }
      window.roadster.seek(f.t);
    }, f);
    if (f.head) {
      // Through the emulator's own command path: the dev UI re-syncs direct writes from its rig.
      await frame.evaluate(async (f) => {
        const r = window.IWER_DEVICE.remote;
        const tf = (a) => ({ position: { x: a[0], y: a[1], z: a[2] }, orientation: { x: a[3], y: a[4], z: a[5], w: a[6] } });
        await r.dispatch('set_transform', { device: 'headset', ...tf(f.head) });
        if (f.left) await r.dispatch('set_transform', { device: 'controller-left', ...tf(f.left) });
        if (f.right) await r.dispatch('set_transform', { device: 'controller-right', ...tf(f.right) });
      }, f);
    }
    await raf();
    if (await frame.evaluate(() => window.__filmIntro === 'new' && (window.__filmIntro = true))) await frame.waitForTimeout(1800);
    const file = path.join(out, `f${String(i).padStart(5, '0')}.png`);
    if (frame === page.mainFrame()) await page.screenshot({ path: file });
    else await (await frame.frameElement()).screenshot({ path: file });
    done++;
  }
  // hand the camera and HUD back to the app
  await frame.evaluate(() => { window.roadsterFilmCamera?.(null); window.roadsterSupersample?.(null); const sh = document.getElementById('shell'); if (sh) sh.style.opacity = ''; });
  if (plan.mode === 'xr' && !process.env.FILM_KEEP_XR) {
    // never leave the shared managed browser stuck in an XR session
    await frame.evaluate(async () => { const s = window.IWER_DEVICE?.activeSession; if (s) await s.end(); });
  }
  return { start, captured: done, next: start + done, total: plan.frames.length };
}
