# Roadster — ramp stunt video understanding and implementation reference

Prepared October 17, 2026. The ramp stunt is implemented as an IWSDK replay with an authored car, reconstructed ramp, thruster and vapor effects, replay controls, and desktop/XR views. Independent reviews approved the car, stage, and temporal presentation at 9.0/10 each, and runtime correctness at 9.2/10. See [README.md](README.md) for the exact review reports and [final replay recording](artifacts/roadster-replay.mp4). The separate fleet stunt is reference context only and is not implemented.

The quantitative follow-up is in [reconstruction/README.md](references/roadster/reconstruction/README.md), with the [runtime pose/geometry data](references/roadster/reconstruction/reconstruction.json), [independent measurement review](references/roadster/reconstruction/reconstruction-independent-review.json), and [data contract](references/roadster/reconstruction/DATA_CONTRACT.md). Full metric six-degree-of-freedom motion cannot be uniquely recovered from these edited, uncalibrated views: the independent measurement score is 7/10, distinct from visual or runtime quality.

## Start here

1. Watch the [18-second main ramp run](references/roadster/media/ramp-main_0708-0726.mp4). Its local `00:00` corresponds to `07:08` in Tesla's event replay.
2. Open the [main-run contact sheet](references/roadster/contact-sheets/02-main-jump.jpg) alongside the [closer replay angles](references/roadster/contact-sheets/03-replay-angles.jpg).
3. Use the timeline below for the movement beats. Open individual frame links for the original 1920 × 1080 image.
4. Read the implemented IWSDK architecture near the end. Its replay and effects choices are authoring decisions, not measurements of the real vehicle.

## Source and event identity

The match is Tesla's **Roadster Event**, held October 15, 2026 at SpaceX's McGregor, Texas facility. The official replay is [Roadster Event on Tesla's YouTube channel](https://www.youtube.com/watch?v=qt5p-_tE8d0). The release timestamp in its downloaded metadata is `2026-10-16T00:55:16Z`, which is October 15 in Texas. [AP's October 16 report](https://apnews.com/article/7d5f19665435b7408025bfb7a2f2f0b7) independently identifies the Thursday event.

The official video's description labels **Ramp Demo 06:03–10:55** and **Kickflip Demo 10:56–12:43**. The ramp chapter also includes presenters talking after the action. The useful ramp action and replay angles are approximately **06:28–07:56**. See [downloaded source metadata](references/roadster/source-metadata.json) for the title, Tesla channel identity, published chapter labels, source format, and source hash.

There are three distinct pieces of action to keep straight:

| Sequence | Event time | What happens | Relevance |
| --- | --- | --- | --- |
| First ramp run | ~06:30–07:06 | Drives up, holds almost fully inverted against the overhang, then reverses back down. | Establishes the ramp shape and wheel contact; optional prelude. |
| Second ramp run | ~07:10–07:24 | Climbs again, leaves the lip, changes attitude with visible jets, descends wheels-down into vapor, then drives away. | **The requested recreation.** |
| Separate fleet stunt | ~11:11–11:17, then replays | Takes off beside a row of Tesla vehicles including a Semi, rotates overhead, and lands. | Additional effects/rotation context. It is a separate stunt from the ramp run. |

These divisions come from inspecting the [official ramp excerpt](references/roadster/media/ramp-event_0603-0756.mp4) and [fleet excerpt](references/roadster/media/fleet_1056-1149.mp4), rather than treating a social-media montage as a continuous take.

## Reference package and time conventions

All delivered frames and clips come directly from the official Tesla replay downloaded for this research. Credit: **Tesla, Roadster Event**. The excerpts preserve the broadcast picture and audio. Full-size stills preserve the complete picture, including its HUD and watermark; contact sheets add labels below each image.

| File or folder | Contents |
| --- | --- |
| [Ramp excerpt](references/roadster/media/ramp-event_0603-0756.mp4) | Event 06:03–07:56; both ramp runs and useful replay angles; 113 seconds. |
| [Main run](references/roadster/media/ramp-main_0708-0726.mp4) | Event 07:08–07:26; quick movement reference; 18 seconds. |
| [Fleet excerpt](references/roadster/media/fleet_1056-1149.mp4) | Event 10:56–11:49; separate stunt and replays; 53 seconds. |
| [First-run sheet](references/roadster/contact-sheets/01-first-run.jpg) | A01–A07: climb, inverted hold, reverse, reset. |
| [Main-run sheet](references/roadster/contact-sheets/02-main-jump.jpg) | B01–B15: ascent through drive-away. |
| [Replay sheet](references/roadster/contact-sheets/03-replay-angles.jpg) | R01–R10: close and aerial views of the same ramp jump. |
| [Fleet sheet](references/roadster/contact-sheets/04-fleet-context.jpg) | F01–F05: lineup, takeoff, rotation, landing cloud. |
| [Car-detail sheet](references/roadster/contact-sheets/05-car-details.jpg) | D01–D03: side, front three-quarter, rear/nozzles. |
| [Frame index](references/roadster/frames.json) | All 40 stills: IDs, requested event times, decoded source timestamps, approximate source frame numbers, notes, links, and hashes. |
| [Clip index](references/roadster/clips.json) | Source intervals, file sizes, and SHA-256 hashes for the excerpts. |
| [Extraction script](references/roadster/tools/extract_reference.py) | Rebuilds the package from the same downloaded full replay. |

**Event time** always means time from the start of the YouTube replay. **Main-clip time** means time within the 18-second local clip. Their nominal relation is `event seconds = main-clip seconds + 428`. Video extraction can round by one source frame. The source is **30000/1001 fps (~29.97)**, not exactly 30 fps. Frame filenames use the requested seek time; `frames.json` records the actual decoded source timestamp. The full replay is about 23:20.54; YouTube rounds the duration to 23:21.

Phase boundaries below are visual estimates, usually within ~0.5 second. The indexed still itself has a recorded decode timestamp. Vapor prevents a precise visual claim about the first tire-contact frame.

## First run: useful setup references

| Event time | Frame | Observation / reference value |
| --- | --- | --- |
| 06:08 | [A01](references/roadster/frames/A01_event_06-08.000.jpg) | Rear of white car at the foot of the ramp; rear light bar, black lower body, ramp center stripe. |
| 06:36 | [A03](references/roadster/frames/A03_event_06-36.000.jpg) | Car remains aligned along the lane as the surface becomes steep. |
| 06:46 | [A04](references/roadster/frames/A04_event_06-46.000.jpg) | Best inverted side close-up: tires meet the underside of the overhang. Broadcast HUD reads pitch **170°**, altitude **67.7 ft**, downforce **4697 kg**. These are broadcast values. |
| 06:52 | [A05](references/roadster/frames/A05_event_06-52.000.jpg) | Held near the top; HUD altitude reads about **69.1 ft**. |
| 06:56 | [A06](references/roadster/frames/A06_event_06-56.000.jpg) | Reverse descent has begun; it follows the same ramp back down. |
| 07:04 | [A07](references/roadster/frames/A07_event_07-04.000.jpg) | Reset at the bottom, still pointing toward the ramp. |

The hold is part of this first run. In the second run the car continues over the lip without this long pause. Compare [the first-run sheet](references/roadster/contact-sheets/01-first-run.jpg) with [the main-run sheet](references/roadster/contact-sheets/02-main-jump.jpg).

## Main recreation: climb → release → reorient → descend → land

| Event time | Main-clip time | Frame | Observed beat and what to preserve |
| --- | --- | --- | --- |
| 07:08 | 00:00 | [B01](references/roadster/frames/B01_event_07-08.000.jpg) | Car ready at the bottom. Brief anticipation before movement. |
| 07:11 | 00:03 | [B02](references/roadster/frames/B02_event_07-11.000.jpg) | Enters the curve, with tires following the deck. |
| 07:13 | 00:05 | [B03](references/roadster/frames/B03_event_07-13.000.jpg) | Rapid climb on the steep section; whole body follows the changing surface orientation. |
| 07:15 | 00:07 | [B04](references/roadster/frames/B04_event_07-15.000.jpg) | Upper curve carries the car toward inversion. |
| 07:16 | 00:08 | [B05](references/roadster/frames/B05_event_07-16.000.jpg) | At the lip, nearly upside down. Preserve a readable transition from attached to airborne. |
| 07:16.500 | 00:08.500 | [B06](references/roadster/frames/B06_event_07-16.500.jpg) | Car is visibly leaving the lip; a small sideward plume is visible. |
| 07:17 | 00:09 | [B07](references/roadster/frames/B07_event_07-17.000.jpg) | Detached and rotating beside the ramp, moving outward into the apron. |
| 07:17.500 | 00:09.500 | [B08](references/roadster/frames/B08_event_07-17.500.jpg) | Underbody visible; body approaches a level, wheels-down attitude. |
| 07:18 | 00:10 | [B09](references/roadster/frames/B09_event_07-18.000.jpg) | Upright descent. Several blue-white columns extend downward from under the car. |
| 07:18.500 | 00:10.500 | [B10](references/roadster/frames/B10_event_07-18.500.jpg) | Jets meet the ground; a white cloud grows outward while the car remains above it. |
| 07:19 | 00:11 | [B11](references/roadster/frames/B11_event_07-19.000.jpg) | Low descent, body still level. Cloud occupies much more area than the car. |
| 07:19.500–07:20.500 | 00:11.500–00:12.500 | [B12](references/roadster/frames/B12_event_07-19.500.jpg), [B13](references/roadster/frames/B13_event_07-20.500.jpg) | Landing interval increasingly hidden by vapor. Exact tire contact cannot be established from these views. |
| 07:22 | 00:14 | [B14](references/roadster/frames/B14_event_07-22.000.jpg) | Car visible on the ground, pointing away from the ramp, moving through thinning vapor. |
| 07:26 | End of main clip | [B15](references/roadster/frames/B15_event_07-26.000.jpg) | Overhead ground view after the run, useful for the apron and departure direction. |

For a first timing pass, allow roughly **5–6 seconds of climbing**, **1–1.5 seconds from lip departure to a largely wheels-down attitude**, and **another ~2–3 seconds of descent/landing**. These are estimates from the main broadcast pass. Do not time the animation from the replays. [Main shot at 07:10](https://www.youtube.com/watch?v=qt5p-_tE8d0&t=430s), [local clip](references/roadster/media/ramp-main_0708-0726.mp4).

![Indexed main-run reference sheet](references/roadster/contact-sheets/02-main-jump.jpg)

## Rotation and thruster details: closer replay references

The broadcast returns to the same jump from closer cameras after the car has driven away. These shots repeat earlier action and may use different playback speed. Camera angle, lens, and movement also change. Use them for pose, surfaces, and effects, with the main pass supplying timing.

| Event time | Frame | Useful detail |
| --- | --- | --- |
| 07:33.500 | [R01](references/roadster/frames/R01_event_07-33.500.jpg) | Car at the lip; inverted departure pose. |
| 07:34.500 | [R02](references/roadster/frames/R02_event_07-34.500.jpg) | Body has turned away from the surface; useful intermediate orientation. |
| 07:35.500–07:36 | [R03](references/roadster/frames/R03_event_07-35.500.jpg), [R04](references/roadster/frames/R04_event_07-36.000.jpg) | Underbody becomes visible. One conspicuous plume points sideways while another points more downward. The jet directions change with the car's attitude. |
| 07:38 | [R05](references/roadster/frames/R05_event_07-38.000.jpg) | Bright front lamps, wheels-down body, several long downward jet columns. |
| 07:40 | [R06](references/roadster/frames/R06_event_07-40.000.jpg) | Low body with vapor piling up around and beneath it. |
| 07:44.500 | [R07](references/roadster/frames/R07_event_07-44.500.jpg) | Best overhead view of ramp construction, wheel contact, and overhang. |
| 07:46.500 | [R08](references/roadster/frames/R08_event_07-46.500.jpg) | Departure from the lip from the aerial camera. |
| 07:47 | [R09](references/roadster/frames/R09_event_07-47.000.jpg) | Broad view of underside, corners, and active jets during rotation. |
| 07:49 | [R10](references/roadster/frames/R10_event_07-49.000.jpg) | Roof/body returns to an upright appearance above the apron. |

**Orientation interpretation:** the climb produces nearly 180° of pitch, supported by the first-run HUD. Airborne, the car makes a compound change of attitude and ends wheels-down. The available views do not establish an exact roll/pitch/yaw curve or a uniquely measured rotation axis. Match the inverted → side/underbody → upright silhouettes above. A generic full 360° spin would miss those reference poses. The later fleet jump is a different rotation sequence. [Close replay](https://www.youtube.com/watch?v=qt5p-_tE8d0&t=453s), [aerial replay](https://www.youtube.com/watch?v=qt5p-_tE8d0&t=464s).

Tesla attributes the surface adhesion to an underbody fan suction system and describes attitude-control and rear main thrusters during the presentation. Relevant explanation starts around [08:11](https://www.youtube.com/watch?v=qt5p-_tE8d0&t=491s) and [09:58](https://www.youtube.com/watch?v=qt5p-_tE8d0&t=598s); a timestamped secondary transcript is available [here](https://www.tesla-roadster.info/unveiling). Treat the physical capabilities as Tesla's claims. This handoff describes what the broadcast shows and does not validate the mechanism or forces.

## Scene, scale, car, and effects notes

### Ramp and environment

The ramp is one narrow driving lane with a smooth concave transition from ground to vertical and then a substantial overhang, almost returning to horizontal. It is an open curved ramp. The rear has exposed dark steel trusses; the driving surface is light gray with a white center stripe and red edge lighting. It stands on a large dark paved apron at night, surrounded by red strips and a few bright white stage lights. [A01](references/roadster/frames/A01_event_06-08.000.jpg), [B03](references/roadster/frames/B03_event_07-13.000.jpg), [R07](references/roadster/frames/R07_event_07-44.500.jpg).

The broadcast's upper-ramp altitude is about 68–69 ft (~20.7–21 m). Its datum and sensor placement are unspecified. The later [joint camera/ramp fit](references/roadster/reconstruction/README.md) uses an explicit scale prior and yields a 21.91 m ramp height, 3.96 m lane width, and 12.74 m upper extension. These are conditional fitted dimensions, not surveyed measurements. Avoid interpreting HUD altitude as exact tire clearance during landing. [A04](references/roadster/frames/A04_event_06-46.000.jpg), [A05](references/roadster/frames/A05_event_06-52.000.jpg), [B13](references/roadster/frames/B13_event_07-20.500.jpg).

Thin lines are visible across some aerial shots. Their purpose cannot be established from the video. Do not infer a mechanical role or derive vehicle motion from them. The broadcast camera pans/tilts and changes framing during descent, so raw screen coordinates are insufficient to reconstruct a metric trajectory. [R09](references/roadster/frames/R09_event_07-47.000.jpg).

### Car model references

Use the **white, angular car in this event** as the visual target: low wedge silhouette, dark glass canopy, black lower body/undertray, bright thin front lighting, and continuous red rear light bar. The rear close-up shows four circular rear nozzles above a deep black diffuser. Wheels and underbody will be visible during the stunt, so the underside needs a deliberate shape and material. [Side D01](references/roadster/frames/D01_event_09-38.000.jpg), [front D02](references/roadster/frames/D02_event_11-01.000.jpg), [rear D03](references/roadster/frames/D03_event_13-30.000.jpg), [underbody R04](references/roadster/frames/R04_event_07-36.000.jpg).

A Tripo multiview mesh was generated from independently approved reference views, then used as a measurement reference for a separately authored Blender model. See the [model contract](art/roadster/model/model-contract.json) and [pipeline record](tools/tripo/README.md). The runtime dimensions, wheel pivots, and nozzle anchors are authoring coordinates. Exact Tesla dimensions, mass, center of gravity, and complete nozzle layout are not established by these frames.

### Effects and landing

The visible jets have a narrow blue/cyan-white appearance under stage lighting. During reorientation they are asymmetrical and follow the vehicle's changing attitude. During descent several become long downward columns. At ground contact those columns build a dense, outward-spreading white cloud; red and cyan lighting tint parts of it. The cloud continues expanding and drifting after the short jet phase, with the car emerging on its wheels. [R03–R06](references/roadster/contact-sheets/03-replay-angles.jpg), [B09–B14](references/roadster/contact-sheets/02-main-jump.jpg).

For authoring, separate the narrow jet effect from the much larger ground cloud and time them independently. Preserve outward travel away from the ramp, attitude correction before landing, and a readable settling/drive-away beat. The footage does not establish exact suspension compression, impact forces, or a bounce curve. Original audio is included for further review; no detailed sound transcription or sound-event timing was performed.

## Optional context: the separate fleet kickflip

Watch [the fleet excerpt](references/roadster/media/fleet_1056-1149.mp4) or its [contact sheet](references/roadster/contact-sheets/04-fleet-context.jpg). [F01 at 11:10](references/roadster/frames/F01_event_11-10.000.jpg) shows the obstacle lineup. [F02 at 11:12](references/roadster/frames/F02_event_11-12.000.jpg) shows upward departure, [F03 at 11:13](references/roadster/frames/F03_event_11-13.000.jpg) the airborne rotation, [F04 at 11:14](references/roadster/frames/F04_event_11-14.000.jpg) descent, and [F05 at 11:15](references/roadster/frames/F05_event_11-15.000.jpg) the cloud. This can inform a later second sequence. It is outside the requested ramp recreation's initial scope.

## Implemented IWSDK architecture

The app is a deterministic visual replay of the second run. It does not simulate the real vehicle's forces or control software.

1. **Reconstructed track input.** The frozen [reconstruction JSON](references/roadster/reconstruction/reconstruction.json) supplies 1,081 samples at 60 Hz over 18 seconds. `src/replay-track.ts` interpolates position and quaternion orientation. Attached poses solve front/rear tire contact against the ramp; airborne orientation and jet envelopes retain their documented authoring assumptions.
2. **Scene assets.** `src/scene-assets/stage.scene-asset.ts` builds the fitted ramp deck, exposed support frame, red edge lights, and illuminated apron. `public/scenes/main.iwsdk.scene.json` owns their placement, lights, environment, and spatial control panel. The full stage uses one shared offset from the reconstruction's canonical coordinates.
3. **Car integration.** `public/models/roadster.glb` contains the authored body, independently rotating wheel nodes, and four named rear nozzle anchors. `src/replay-system.ts` applies the track and wheel animation. The Blender source, rebuild scripts, comparisons, and review snapshots remain in `art/roadster/model/`.
4. **Effects.** `src/replay-effects.ts` coordinates local attitude/lift plumes and deterministic expanding vapor particles. Emitted vapor stays in world space, fades after landing, and resets correctly during arbitrary seeking. The cloud atlas is generated from the indexed landing reference. Runtime audio has not been authored; the reference excerpts retain broadcast audio.
5. **Viewing and interaction.** Desktop playback offers Show, Wide, Car, and Overhead views, play/pause, restart, quarter speed, and keyboard stepping. In XR, the tracked viewer controls the camera and uses a world-space panel. The first ramp run and the separate fleet stunt are excluded.
6. **Verification.** Numerical tests check track continuity, wheel contact, effects seeking/reset, camera framing, XR camera independence, and resource ownership. Real browser pointer/keyboard tests and an emulated Quest controller-ray selection pass. Physical headset performance remains unmeasured. Independent model, stage, runtime, and temporal reports preserve their separate scopes and scores.

The scaffold's [AGENTS.md](AGENTS.md) contains project-specific IWSDK instructions and routes app implementation through the installed `iwsdk-dev` skill. Read it before editing the scene or runtime. Its terminology links and the [official setup guide](https://iwsdk.dev/guides/01-project-setup) explain XR (an immersive session), the project configuration, and the starter workflow.

Runtime entry points:

| File | Role |
| --- | --- |
| `iwsdk.config.json` | Active scene, assets/components modules, immersive mode, and feature settings. |
| `src/index.ts` | World creation and runtime system registration. |
| `src/assets.ts` | Shared asset catalog. |
| `src/components.ts` | Shared component declarations. |
| `public/scenes/main.iwsdk.scene.json` | Authored scene composition. |

### Visual completion criteria

- Tires visibly follow the ramp through the steep section and overhang.
- The car leaves the physical lip without clipping or a pose discontinuity.
- The inverted departure, exposed underside, and final wheels-down pose read clearly.
- Small attitude jets precede the stronger downward descent columns.
- The car travels away from the ramp and descends into the apron.
- Ground vapor builds, persists, and clears enough to reveal a grounded car driving away.
- The second run's timing remains comparable to the main broadcast pass.
- Replay camera cuts and the separate fleet stunt do not become extra jumps in the same timeline.

## Creation and verification record

Created using:

```sh
npm create @iwsdk@latest Roadster -- --yes --target vr --language ts --install --git --skip-reference-warmup
```

- Generator and installed `@iwsdk/core`: **1.0.1**; TypeScript; VR starter; locomotion and grabbing enabled; physics disabled in the generated configuration.
- `package.json` name and HTML title: **Roadster**. Git initialized; no commit created.
- Optional reference-assistant warmup was skipped. It remains available through `npm run reference:warmup`.
- `npm run typecheck`: **passed**.
- `npm run build`: **passed**. Generated dependency code produced annotation and large-chunk warnings.
- Reference verification: all local documentation links resolve; 40 frame hashes and 3 clip hashes match; all three 1080p excerpts decode successfully with audio.
- The initial dependency install reported 8 audit findings (4 moderate, 4 high); the generated dependency versions are retained.
- Managed-browser playback, real pointer/keyboard controls, portrait/landscape cameras, and IWER Quest 3 controller-ray interaction have been exercised. No physical headset performance claim is made.
- The starter runtime, assets, scene, and UI have been replaced by the ramp experience. See [README.md](README.md) for current commands and review status.

The reference files live outside `public/`, so they are available to the next developer without becoming application payloads.

## Reproducing or extending the frame extraction

The [script](references/roadster/tools/extract_reference.py) documents the download command and requires Python with Pillow plus FFmpeg/FFprobe. Run it with a path to the full official replay:

```sh
python3 references/roadster/tools/extract_reference.py /path/to/official-event.webm
```

It verifies the recorded source hash, extracts the 40 indexed stills, builds the five contact sheets, and encodes the three excerpts. It also records actual source timestamps and hashes. A different download container or source revision can have a different hash; inspect that source and deliberately update the metadata before using it. The full original replay and exploratory third-party clips are not part of the delivered package.
