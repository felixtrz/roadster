export default async function ({ frame }) {
  return await frame.evaluate(async () => {
    const d = window.IWER_DEVICE;
    const r1 = await d.remote.dispatch('set_transform', { device: 'headset', position: { x: -50, y: 1.7, z: -17 }, orientation: { x: 0, y: 0.38, z: 0, w: 0.92 } });
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const r2 = await d.remote.dispatch('get_transform', { device: 'headset' });
    return { r1, r2 };
  });
}
