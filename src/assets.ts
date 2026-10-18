import { AssetType, defineAssets } from '@iwsdk/core';
import reconstruction from '../references/roadster/reconstruction/reconstruction.json';
import { createApron, createRamp } from './scene-assets/stage.scene-asset.js';
import { createThrusters, createVapor } from './scene-assets/effects.scene-asset.js';
import { createSiteLights } from './scene-assets/site-lights.scene-asset.js';
import { createBackdrop } from './scene-assets/backdrop.scene-asset.js';

const assetUrl = (path: string): string => `${import.meta.env.BASE_URL}${path}`;

export default defineAssets({
  roadster: { url: assetUrl('models/roadster.glb'), type: AssetType.GLTF, name: 'Roadster' },
  ramp: createRamp(reconstruction.ramp.centerline, reconstruction.ramp.width),
  apron: createApron(),
  'site-lights': createSiteLights(),
  backdrop: createBackdrop(),
  thrusters: createThrusters(),
  vapor: createVapor(),
  'vapor-lit': { url: assetUrl('textures/vapor-lit.png'), type: AssetType.Texture, name: 'Lit vapor atlas' },
  'replay-controls': { url: assetUrl('ui/replay.uikitml'), type: AssetType.UIKitML, name: 'Replay controls' },
});
