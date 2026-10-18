// Sizes the managed page before an XR session starts (the emulated XR framebuffer keeps its start size).
export default async function ({ page }) {
  await page.setViewportSize({ width: Number(process.env.FILM_W || 1920), height: Number(process.env.FILM_H || 1080) });
  return { ok: true };
}
