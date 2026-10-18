# Contributing

Issues and pull requests are welcome.

## Setup

```sh
npm install
npm run dev          # managed dev server at https://localhost:8084/
```

Read [AGENTS.md](AGENTS.md) first: it explains where this IWSDK project differs from a plain Vite app (`iwsdk.config.json` is the project authority, `src/assets.ts` runs in two realms, scene JSON holds composition only, Three.js is imported from `@iwsdk/core`).

## Before you open a pull request

```sh
npm run typecheck
npm run build
npm run verify:runtime
```

All three should pass. For visual changes, include a screenshot of the running app.

## Media and licensing

- Do not commit Tesla footage, frames cut from it, or images or meshes generated from those frames. [NOTICE.md](NOTICE.md) lists what is excluded and how to regenerate it locally; `.gitignore` already covers the usual paths.
- Do not commit large renders, recordings or `.blend` files. Commit the script that produces them instead.
- Contributions are accepted under the project's [MIT licence](LICENSE).

## Python and Blender tools

The scripts under `tools/` and `art/` resolve paths relative to themselves. Blender commands use a `BLENDER` environment variable for the Blender binary. The older car builds (`art/roadster/model/`, `art/roadster/model-v5/`) also need `MESH_REBUILD_SKILL`, the scripts directory of the external mesh-rebuild skill, and the excluded Tripo reference mesh.
