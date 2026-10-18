/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// Self-hosted UI fonts (OFL): bundled by Vite, so the page makes no third-party font requests.
import '@fontsource/inter/300.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/space-grotesk/300.css';
import '@fontsource/space-grotesk/400.css';
import '@fontsource/space-grotesk/500.css';
import { World } from '@iwsdk/core';
import projectOptions from 'virtual:iwsdk-project';
import { RoadsterSystem } from './replay-system.js';

World.create(
  document.getElementById('scene-container') as HTMLDivElement,
  projectOptions,
).then((world) => {
  world.registerSystem(RoadsterSystem);
}).catch((error: unknown) => {
  // Never leave a silent black page: say what failed (WebGL2 unavailable, an asset that did not load...).
  console.error('[roadster] failed to start', error);
  const message = document.createElement('div');
  message.setAttribute('role', 'alert');
  message.style.cssText = 'position:fixed;inset:0;display:grid;place-items:center;padding:24px;background:#050608;color:#e9edf1;font:15px/1.5 system-ui,sans-serif;text-align:center;z-index:100';
  message.textContent = `The replay could not start: ${error instanceof Error ? error.message : String(error)}. Try a current Chrome, Edge, Firefox or Quest browser with WebGL 2.`;
  document.body.append(message);
});
