# Roadster authored model, V4

The runtime asset `../../../public/models/roadster.glb` contains **70,821 authored triangles, 60 mesh parts and 70 named nodes**. Its V4 review hash is `c7efcb40038e54845c262cef6ecfeef52b97288e23312aaba112077faa43701a`. The untouched Tripo reference `../tripo/h31-reference-v1/model_url.glb` contains 188,630 triangles. None of its generated triangles ship. One H3.1 generation consumed 60 credits; the Tripo ledger records the task, approved input hashes, independent input scores and actual before/after balances.

`Roadster.blend` is the single guarded project, with `Ref`, `Authored` and `Studio` collections. Scripts reject mutation in any other project. Authoring uses metres, Z-up, forward -Y and left +X; the origin is floor at the centre of the four wheel contacts. Export temporarily rotates only `Roadster` +90 degrees about Blender Z, giving runtime +X-forward, +Y-up and left -Z. The saved project restores its authored basis. No runtime wrapper is required.

## Parts and ownership

`BodyShell` owns one shared exterior surface with paint, smoked glass, structural trim and corner-lens regions. Windshield, pointed side glass, roof and rear hatch use exact shared boundary cuts. There are no overlay glass meshes or nearly coplanar white backing surfaces. `Canopy` is a semantic empty. One plane owns each side pane; surrounding shared frame vertices blend over 80 mm. An exact 25 mm white A-frame beside dark trim replaces the broad white bridge while preserving the window nose landmark.

The field uses fixed semantic cross-section rails and C1 longitudinal controls. The nose declines into a flat forward cap, with only a local 60 mm outer-corner fillet and 35 mm lower-cap rake. The shoulder rises from 0.865 m at the front axle to 0.990 m at the rear axle; the outer door rail stays 70 mm below it. These controls remove the earlier nose curl, shoulder sag and accidental ripples.

Corner lenses are exact XZ cuts in the forward cap. All 0.011764 m² of lens area faces runtime +X. WhiteLED strength 8 preserves a bright white/cyan core under tone mapping. A dark strip separates the thin centre bar from the hood. Flush black jambs and a back wall own the intake, above a narrow 77 mm lip. White Boolean cavity walls, duplicate belt roof and intersecting standalone sill tubes are removed. **Keep the belt closed through all Booleans, then remove its duplicate roof.** Opening it earlier can retain cutter geometry.

Spin pivots are `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR`; rotate local X. Tires, aero discs, rims and hubs are separate. `NozzleAnchor_1` through `NozzleAnchor_4` have local +Z rearward, runtime -X. Four brass nozzles, rear relief, contained diffuser channels, shrouds, a blank plate and undertray complete the assembly. Full positions and radii are in `model-contract.json`.

## Reproduce

Run from the project root with Blender 5.1.1 and Python 3 with NumPy/Pillow:

```sh
# Bootstrap only when the guarded project is missing:
"$BLENDER" --background --factory-startup \
  --python art/roadster/model/setup_reference.py

# Recompute measured construction inputs:
python3 art/roadster/model/fit_roadster.py
"$BLENDER" --background \
  art/roadster/model/Roadster.blend --python art/roadster/model/fit_surface_patches.py
python3 art/roadster/model/fit_fair_body.py
python3 art/roadster/model/fit_side_glass_plane.py
python3 art/roadster/model/verify_form.py

# Rebuild, render, export and guarded save:
"$BLENDER" --background \
  art/roadster/model/Roadster.blend --python art/roadster/model/build_roadster.py

# Read-only evidence refresh; no rebuild, export or project save:
"$BLENDER" --background \
  art/roadster/model/Roadster.blend --python art/roadster/model/refresh_review_evidence.py
python3 art/roadster/model/plot_measurements.py
python3 art/roadster/model/validate_glb.py
python3 art/roadster/model/make_review_sheets.py
```

`fit_roadster.py` fits tire circles. `fit_surface_patches.py` preserves the fallible generated proxy sampled at 65 stations/14 rails. `fit_fair_body.py` records source-informed fairing; `fit_side_glass_plane.py` records its plane and departures. `fair_body.py` evaluates the field. `build_roadster.py`, `facade_refinements.py` and `model_lib.py` author the parts. `cleanup_geometry.py` collapses microscopic slivers after all exact cuts: 88 local edge collapses remove 170 redundant triangles, with longest edge 0.108 mm and maximum per-collapse vertex displacement 0.054 mm. No subdivision or bevel modifiers are used. Continuous surfaces use smooth normals; designed corners retain split normals.

## Measurements and limits

The generated proxy is normalized to nominal body length 4.6 m; width 2.431 m, height 1.320 m. Fits give wheelbase 2.8264 m, tracks 2.1026/2.1029 m, front/rear radii 0.34831/0.35769 m. Mean radial residuals are 3.65/4.00 mm, p90 6.75/7.05 mm. The authored envelope including lamps/nozzles is **4.641 × 2.394 × 1.321 m**, with floor minimum zero. These are model measurements, not certified Tesla engineering dimensions.

Bilateral symmetry, floor-corrected circular tires and hidden tire width 0.275 m are deliberate constraints. The fair field departs from proxy dents and the earlier global low-pass bubble. Side-plane corner departures reach 33.2 mm; adjusted interior/frame vertices move at most 56.5 mm. Original YZ aperture landmarks remain. Glass is opaque smoked material because the source does not establish an interior. Hidden undertray, channels and nozzle interiors are bounded authored assumptions. Near-black rough metallic intake shading preserves cavity darkness under image-based lighting; it is a visual approximation, not a measured material property.

`sections/roadster-overlays.png` uses identical mm grids, source blue and authored red. Differences use uniform 4 mm reference-arc samples and closest authored segments, including hidden assumptions/fairing. V4 approximate mean/p90 differences: centre profile 26.1/89.6 mm, wheel-side 50.1/139.3 mm, shoulder plan 51.6/93.4 mm. These are honest deviations from a generated proxy, not source-video accuracy or a visual score. Inspect overlays alongside actual source D01/D02/D03/event-803 and approved v2 images.

## Evidence and review

`renders/contact.png` contains 18 material/clay views including underside and low front/quarter. `source-comparison.png` pairs eight views with the generated proxy. `runtime-glb-renders/` contains ten views imported from the exact public GLB. Low-quarter uses runtime-equivalent eye [6,1.5,7], target [0,0.7,0], vertical FOV 42 degrees. `runtime-captures/` contains actual browser evidence with model/image hashes. Studio round-trips do not substitute for actual runtime images.

`glb-validation.json` matches the official IWSDK preview using exported float32 coordinates promoted to double: dot(AB×AC,AB×AC) < 1e-16. Final export: **zero effective degenerates**, finite unit normals, floor zero, correct axes, all wheel/nozzle frames and one glass owner. `fit/material-side-audit-v4.json` documents retained DoubleSide flags per material, including open skin/cavity/rim/light surfaces. Closed aero discs could cull backfaces; their conservative existing flag is documented, with no duplicate surface implied. `fit/surface-ownership-v4.json` records planar residuals/contact counts; legitimate shared seam contacts are not penetration measurements. Actual glass, rocker and intake artifact checks remain part of independent review.

Independent model scores V1 **6.3**, V2 **7.2**, V3 **7.8** were rejected. V4-b primary preflight and V4-c runtime defect recheck found no critical blocker to full review; neither is final approval. **Fresh V4 score pending.** `review-input-v4/` freezes the complete candidate with SHA256 hashes. Do not edit reviewed bytes or claim 9/10 before the independent judge supplies it.
