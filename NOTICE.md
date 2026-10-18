# Notice

## Licence

The project's code, scripts, scene files and documentation are released under the [MIT licence](LICENSE), Copyright (c) 2026 Felix Zhang.

Some files come from the IWSDK project scaffold and carry a `Copyright (c) Meta Platforms, Inc. and affiliates` header (for example `src/index.ts`, `src/components.ts`, `vite.config.ts`, `src/scene-assets/lib/hardsurface.ts`). They are MIT-licensed by Meta and keep their headers. The same applies to the IWSDK agent skills and rules under `.agents/`, `.claude/`, `.cursor/` and `.github/`.

## Source footage

Footage: Tesla, Roadster Event (Oct 2026).

The ramp, the car's motion and the thruster timing were measured from two public Tesla videos:

- [Roadster Event](https://www.youtube.com/watch?v=qt5p-_tE8d0), the ramp demo at 06:03–07:56 (Tesla, 16 Oct 2026).
- [The Ramp | Roadster](https://www.youtube.com/watch?v=7p5LxFdc-Qg), Tesla's edited overhead clip (Tesla, 16 Oct 2026).

That footage is Tesla's copyrighted work. This repository does not include it, any frame cut from it, or any image generated from those frames.

## Not affiliated

This is an independent fan project. It is not affiliated with, sponsored by or endorsed by Tesla, Inc. or SpaceX. Tesla and Roadster are trademarks of Tesla, Inc. They are used here only to identify the real event the project recreates.

## What is excluded, and why

The root [`.gitignore`](.gitignore) keeps the following out of the published repository. They may exist in a local working copy.

| Path | Contents | Why excluded |
| --- | --- | --- |
| `references/roadster/media/` | MP4 excerpts of the broadcast | Tesla footage |
| `references/roadster/frames/` | Indexed stills from the broadcast | Tesla footage |
| `references/roadster/contact-sheets/` | Sheets of those stills | Tesla footage |
| `references/roadster/reconstruction/*.mp4`, `*.jpg` | The overhead clip, measurement stills, pose overlays and reprojection sheets drawn on footage | Tesla footage |
| `artifacts/thruster-study/` | Full-rate frame studies of the flip and descent | Tesla footage |
| `art/roadster/source-inspection/` | Stills of the car from the broadcast | Tesla footage |
| `art/roadster/reference-images/` | AI-generated turnaround views of the car, made from video stills | Derived from Tesla footage |
| `art/roadster/tripo/` | A Tripo-generated mesh made from those AI images, plus its task ledger | Derived from Tesla footage; the ledger also holds signed service URLs |
| `art/roadster/vfx/*.png` | An AI-generated vapor sprite atlas prompted with a broadcast frame (not used at runtime; the app uses the procedural `public/textures/vapor-lit.png`) | Derived from Tesla footage |
| `art/roadster/model/**/reference/`, `art/roadster/model-v5/reference/`, `*.blend` in those folders | The Tripo mesh imported as a fitting reference, and Blender files that embed it | Derived from Tesla footage |
| Images, videos, meshes and `.blend` files under `art/` and `artifacts/` | Renders, review captures, recorded frames and old model exports (about 2 GB) | Size. They are reproducible from the scripts |
| `artifacts/film/roadster-film.mp4` | The demo film | Its computer-vision segment shows a few seconds of Tesla's broadcast with the reconstruction drawn over it |

Kept and published:

- `references/roadster/reconstruction/reconstruction.json`, `geometry-fit.json` and the other JSON files. They are numeric measurements (pixel coordinates, fitted camera and ramp parameters, the replay track), not media. The app imports `reconstruction.json` at build time.
- `references/roadster/frames.json`, `clips.json` and `source-metadata.json`. They are indexes of timestamps, hashes and descriptions.
- `src/data/thrusters.json`, produced by `tools/thrusters/solve_thrusters.py` from the track.
- `public/models/roadster.glb`, the runtime car. It is modelled from scratch in Blender by `art/roadster/model-v6/` and reuses no geometry or texture from the Tripo mesh (a few plan-view widths were measured from it). Its proportions and character lines were traced from the excluded AI turnaround (see below).
- `public/textures/vapor-lit.png`, generated procedurally by `tools/textures/gen_vapor_atlas.py`.
- `art/roadster/model-v6/roadster_v6.blend` and `shell.npz`, which are needed to rebuild the car.
- `docs/images/`, screenshots of this app.

### Provenance of the car model

The runtime car contains no third-party pixels or mesh data. Its design lines, however, were traced from AI-generated images that were themselves made from stills of Tesla's footage, and details such as the hood-corner headlamp notches and the tail were then checked against Tesla's published press photos (viewed for reference, not included). It depicts Tesla's car. It is noted here so that anyone reusing the model can judge that for themselves.

## Regenerating the reference package

Contributors who want to rerun the measurements can rebuild the excluded media from the public videos. You need `ffmpeg`, `ffprobe`, Python 3 with Pillow, and a downloader such as `yt-dlp`.

```sh
# 1. Download the public replay (format 248+251, as recorded in source-metadata.json).
yt-dlp -f 248+251 --merge-output-format webm -o official-event.webm \
  'https://www.youtube.com/watch?v=qt5p-_tE8d0'

# 2. Rebuild references/roadster/media/, frames/ and contact-sheets/.
python3 references/roadster/tools/extract_reference.py official-event.webm
```

`references/roadster/source-metadata.json` records the expected source hash, and `frames.json` and `clips.json` record the hash of every extracted file, so you can check that you have the same source.

The reconstruction stills also need the overhead clip. Download [The Ramp | Roadster](https://www.youtube.com/watch?v=7p5LxFdc-Qg) to `references/roadster/reconstruction/tesla-the-ramp.mp4`, then follow the reproduction steps in [references/roadster/reconstruction/README.md](references/roadster/reconstruction/README.md).

Do not commit what you download or extract. The `.gitignore` already excludes it.
