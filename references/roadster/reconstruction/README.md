# Ramp reconstruction: evidence and limits

This package delivers a reproducible, source-constrained ramp and car replay for
IWSDK. It is an approximate reconstruction with explicit camera, scale, depth,
and pose assumptions. The available edited cameras do not establish a uniquely
measured full six-degree-of-freedom trajectory.

Use [reconstruction.json](reconstruction.json) and the
[runtime data contract](DATA_CONTRACT.md). The numerical track is frozen; its
SHA-256 and numerical checks are in [verification.json](verification.json).
Only the second ramp run is included. The separate fleet stunt is excluded.

## Sources and the additional angle

The primary timing source is Tesla's
[Roadster Event](https://www.youtube.com/watch?v=qt5p-_tE8d0), event 07:08–07:26.
Its local excerpt is [ramp-main_0708-0726.mp4](../media/ramp-main_0708-0726.mp4).
The existing [video understanding handoff](../../../VIDEO_UNDERSTANDING.md)
indexes the broadcast's main, closer, and aerial replays.

Further research located Tesla's official
[The Ramp | Roadster](https://www.youtube.com/watch?v=7p5LxFdc-Qg).
The [local edited clip](tesla-the-ramp.mp4) adds a previously missing, wide
overhead camera showing the whole structure and the car's departure and ground
travel. It reveals the long upper overhang. It is used for geometry and limited
motion constraints, with separately fitted replay timing.
[Source identity, credit and hash](tesla-the-ramp.source.json) identify the Tesla
channel. No synchronized or calibrated raw attendee camera feed was acquired.

The main clip decodes at 30000/1001 fps. The edited clip decodes at 24000/1001
fps. [wide-frames.json](wide-frames.json) records each wide still's actual source
frame and timestamp, recovered by matching the JPEG to decoded source frames.
FFmpeg's nominal half-second labels were insufficient: the first selected frame
was about 0.24 seconds later, and fractional-frame drift occasionally changes a
frame index. The [wide contact sheet](wide-sync-sheet.jpg) is for browsing;
the manifest owns precise timestamps.

## Reconstruction method

1. Digitize the ramp's two rails in the main and wide images. Fit an extruded
   elliptical half-loop followed by a tangent overhang through both pinhole
   cameras. Add the visible white ground centerline, which constrains the apron
   direction that the rails alone leave ambiguous. Camera principal points are
   assumed to be image centers; lens distortion is omitted.
2. Use four observed car-center correspondences in the wide shot, IDs 10, 11,
   13 and 15, to constrain relative camera calibration and replay timing jointly.
   Alternate IDs 12, 14 and 16 remain outside that calibration fit. The fixed
   [2D calibration inputs](calibration-observations.json) are screen observations,
   not authored 3D keyframes. All fit priors are visible in
   [fit_geometry.py](../../../tools/reconstruction/fit_geometry.py).
3. Register each main-view sample to the static ramp using SIFT features and
   RANSAC homographies. This removes most camera pan, tilt and zoom. Track the
   canopy by background differencing while attached. For the dark airborne car,
   initialize tight body rectangles by inspection and refine their brightness
   silhouettes. [observations.json](observations.json) retains the observations,
   transforms, residuals, and human-initialized rectangle provenance.
4. Fit attached progress to those observed pixels while solving the front/rear
   tire-contact chord for the authored model's wheelbase. During flight, intersect
   the registered pixel rays with the ramp's vertical Z=0 plane. Fit a smooth
   trajectory with a shared release position and velocity and weak acceleration
   regularization. This is a conditional geometric solve, not triangulated
   ground truth or a vehicle force simulation.
5. Use wide-shot IDs 18 and 20 as ground-trajectory observations after the main
   view loses the car in vapor. Under the calibrated plane their uncorrected
   contact-root heights are about −0.02 and −0.12 m. Ground contact is imposed,
   and the fitted replay mapping places nominal touchdown at about 11.53 main
   seconds, with a ±0.3 s modeling bracket. Ground X after the final observation
   at 12.394 main seconds is explicitly a constant-speed extrapolation.

The metric scale remains a gauge: uniformly scaling geometry and camera
translations preserves the image projections. A 22 m ramp-height prior, informed
by the broadcast altitude and an explicit body-reference offset, selects a
useful scale. Width, aspect, extension, camera height, and focal length also have
priors. They are not surveyed dimensions.

## What was recovered, fitted, or authored

| Item | Status |
| --- | --- |
| Main source times, visible rail and car pixels | Observed, with extraction and proxy uncertainty |
| Ramp deck and camera parameters | Joint regularized fit; not a survey |
| Attached car progress | CV pixel fit constrained to the fitted deck |
| Airborne X/Y | CV pixel fit conditional on camera and Z=0 plane |
| Airborne Z | Constrained to zero; sensitivity is material |
| Attached orientation | Front/rear contact chord |
| Airborne quaternion | Inferred eased inversion-to-wheels-down interpolation |
| Attitude and lift envelopes | Authored from visible plume phases; not thrust measurements |
| Hidden landing | Wide ground observations plus a smooth contact transition |
| Ground travel after 12.394 s | Explicit extrapolation |

The car dimensions in the JSON describe the authored Tripo/Blender-derived mesh,
not measured Tesla specifications. The current wheelbase is 2.826421 m; the
floor/contact origin and model-local +X forward, +Y up, +Z right axes are explicit.

## Timing and altitude limits

The main clip's clock is authoritative. The fitted affine map for the edited
wide air window has a rate of about 0.8103; it is a nuisance parameter conditional
on the camera/profile/body-center proxies. It is not proof of a physical replay
speed or hardware synchronization. A fixed offset alone fits the footage worse.

This affine map does **not** explain the whole edited climb. Independent early
wide IDs 1, 4 and 6 have timing-mapped pixel discrepancies of about 85, 28 and
16 pixels. Their nearest spatial points on the same fitted ramp path are within
about 2, 1 and 0.2 pixels. These diagnostics are retained in
[independent-validation.json](independent-validation.json). Variable editing or
remaining timing/model bias is unresolved; do not apply the air-window mapping
to all replays or retime the main clock from it.

The broadcast altitude digits are manually transcribed in the observations and
shown in [main-dense-sheet.jpg](main-dense-sheet.jpg). During rapid descent they
disagree materially with the image-derived path. A descriptive delay adjustment
improves that comparison, but telemetry smoothing, sensor datum, camera and
plane errors can all contribute. The digits are not used as instantaneous
airborne tire clearance or as an exact flight trajectory.

## Evidence and numerical QA

| Check | Result and meaning |
| --- | --- |
| Main / wide rail RMS | 5.53 / 4.03 px; in-sample geometry fit |
| Wide ground centerline RMS | 0.93 px; in-sample direction fit |
| Main car-center RMS | About 11.5 px; in-sample 2D consistency |
| Withheld wide IDs 12/14/16/17/19 | About 34.1 px RMS, 41.4 px max |
| Delivered polyline tire-contact error | About 0.13 mm; algebraic model/deck consistency only |
| Release | Shared position and analytic velocity; no impulse at the boundary |
| Maximum sampled acceleration | About 34.4 m/s²; regularized replay, not measured capability |
| Quaternion checks | Finite, unit length, no sign flips; eased angular boundaries |

Inspect [main geometry](main-geometry-reprojection.jpg),
[wide geometry and ground axis](overhead-geometry-reprojection.jpg),
[main pose overlays](pose-reprojection-sheet.jpg),
[wide validation overlays](wide-independent-validation-sheet.jpg), and
[trajectory plots](reconstruction-plots.png). Calibration points and trajectory
inputs are explicitly distinguished from withheld points in the validation JSON.
Late cloud-obscured body-center proxies have greater uncertainty than clean
silhouettes. Pixel residuals do not establish metric 3D accuracy.

The Z=0 constraint matters. `depthPlaneSensitivity` in the runtime JSON records
the change in inferred X/Y when the same observed ray intersects Z=−2, 0 or +2 m.
The listed ±5 m X, ±2 m Y/Z and other ranges are modeling ranges, not statistical
confidence intervals or guaranteed error bounds. Homography extrapolation away
from the matched ramp features, approximate lens intrinsics, scale, proxy center
and unobserved depth remain material errors. The independent
[review report](reconstruction-independent-review.json) also records feature
resampling sensitivity and unresolved limitations.

## Reproduction

**The footage and every still or overlay cut from it (`*.mp4`, `*.jpg` in this
folder and `../media/`) are not distributed with the open-source repository**
(see [NOTICE.md](../../../NOTICE.md)). The JSON files here, including
`reconstruction.json`, are the derived numeric results and are all the app needs.
To rerun the reconstruction, first rebuild `../media/` with
`references/roadster/tools/extract_reference.py`, download
[The Ramp | Roadster](https://www.youtube.com/watch?v=7p5LxFdc-Qg) to
`tesla-the-ramp.mp4` here (its hash is in `tesla-the-ramp.source.json`), and
re-extract the wide stills `wide_NN.jpg` at the source frames listed in
`wide-frames.json`. The overhead stills (`overhead-32.jpg`, `overhead-37.jpg`)
come from the same clip; no script in this repository re-extracts them yet.

No service or API key is needed. Install
[requirements.txt](../../../tools/reconstruction/requirements.txt)
in a Python environment compatible with those versions. Then run from the
project root:

```sh
python tools/reconstruction/recover_wide_timestamps.py
python tools/reconstruction/reconstruct.py
python tools/reconstruction/validate_views.py
python tools/reconstruction/verify.py
```

`reconstruct.py` rebuilds the geometry, registration, trajectory, observations,
and main overlays. `validate_views.py` applies the frozen calibration and writes
the held-out report. `verify.py` checks data consistency and writes the delivered
track hash without altering the track. Renderer changes, particle effects and
the final car mesh are separate from this reconstruction package.
