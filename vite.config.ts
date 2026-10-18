/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { readdirSync, rmSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { iwsdkDev } from '@iwsdk/vite-plugin-dev';
import { defineConfig, type Plugin } from 'vite';

/** public/ holds AGENTS.md notes for coding agents working in the repo; they are not part of the site. */
const dropAgentNotes = (): Plugin => ({
  name: 'roadster:drop-agent-notes',
  apply: 'build',
  closeBundle() {
    const out = resolve('dist');
    for (const file of readdirSync(out, { recursive: true }) as string[]) {
      if (basename(file) === 'AGENTS.md') rmSync(join(out, file));
    }
  },
});

export default defineConfig({
  plugins: [iwsdkDev(), dropAgentNotes()],
  server: { host: '0.0.0.0', port: 8084, open: false },
  build: {
    outDir: 'dist',
    sourcemap: process.env.NODE_ENV !== 'production',
    target: 'esnext',
    rollupOptions: { input: './index.html' },
  },
  esbuild: { target: 'esnext' },
  // @drawcall/uikitml otherwise pulls a second three/@pmndrs/uikit graph
  // (three@0.185 vs app super-three@0.181). Duplicate Component classes break
  // instanceof checks → "Only pmndrs/uikit components can be added as children".
  resolve: {
    dedupe: [
      'three',
      '@pmndrs/uikit',
      '@pmndrs/uikit-horizon',
      '@pmndrs/uikit-lucide',
    ],
  },
  optimizeDeps: {
    exclude: ['@babylonjs/havok'],
    include: [
      'three',
      '@pmndrs/uikit',
      '@pmndrs/uikit-horizon',
      '@pmndrs/uikit-lucide',
      '@drawcall/uikitml',
    ],
    esbuildOptions: { target: 'esnext' },
  },
  publicDir: 'public',
  base: './',
});
