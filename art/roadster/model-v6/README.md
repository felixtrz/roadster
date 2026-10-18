# Roadster v6: built from parts

The runtime car (`public/models/roadster.glb`) is rebuilt from scratch, as the car's real anatomy: a body skin defined by its character lines, cut into separate panels with panel gaps, plus the front fascia, tail, diffuser, nozzles, wheels and lamps as their own parts. The Tripo mesh (`art/roadster/tripo/`) and the earlier models are only references; nothing from them is reused.

## Rebuild

Run from this directory. `BLENDER` is the path to your Blender binary (for example `/Applications/Blender.app/Contents/MacOS/Blender` on macOS).

```bash
python3 shell.py
"$BLENDER" -b roadster_v6.blend -P build_v6.py -- --export
```

`--export` writes `public/models/roadster.glb` relative to the repository root. The rebuild needs only `design.py`, `shell.py`, `shell.npz` and `roadster_v6.blend`; none of the excluded reference media (see [NOTICE.md](../../../NOTICE.md)).

Review renders: `render_glamour.py` (studio EEVEE views), `render_ortho.py` + `overlay.py` (orthographic renders at the blueprint's pixel scale, overlaid on the turnaround). `overlay.py` needs the AI turnaround image, which is not distributed.

## How it is made

1. **Character lines (`design.py`).** Traced from the orthographic turnaround (`art/roadster/reference-images/turnaround-v2.png`: side view scaled to 4.6 m length, front/rear views to 1.31 m height). Plan widths come from the Tripo sections. The lines are: centreline (nose, hood, cowl, windshield, roof, rear glass, deck, Kamm tail), hood crease / roof rail (glass edge), fender peak / beltline, shoulder, widest line, paint split (rocker sweep into the black rear quarter), rocker bottom and floor.
2. **Skin (`shell.py`).** 99 stations; each section runs through the named points with flat or lightly crowned spans between them (crown only on the roof and doors; hood, fenders and deck are flat facets). Edges along the glass edges, beltline and paint split are hard creases.
3. **Panels (`build_v6.py`).** Design cuts (canopy ends, daylight opening, door shut lines, cowl) split the skin into: hood, cowl, fenders, doors, rear quarters, rockers, canopy glass, side glass, A-pillars, roof rails, rear deck and floor. The arches are cut from the whole skin before the split. Each panel's edges are pulled back to open real gaps over a dark inner body. The hood is one large panel with a transverse line about a quarter of its length ahead of the windscreen (press top view). The headlamps are triangular notches cut into the top surface at the hood corners: each runs about 0.43 m back and inward along the hood crease from the nose corner, is lined with a recessed pocket, and holds a lit arrow on its floor, a lit strip along its outer edge that continues the light blade, and a lamp face on its back wall; the blade runs along the hood's front edge between the two notches. Then come the front fascia (gloss black face stepped back under the blade between white fangs, dark lower lip, splitter), the dark buttress vents, the tail (white lip carrying the full-width red bar on its trailing edge, a recessed body-colour band carrying the RDSTR plate, then a black bay directly under it with four thin-walled brass nozzle tubes set flush and alternating with five dark ports, over a diffuser of vertical fins, and wing end plates just outboard of the corners), the dark wedge vent at the top rear of each front arch with the amber marker in it, the tubular underbody frame seen in the overhead footage, and the wheels (thin-sidewall tyre, near-flush white aero disc, six straight gunmetal spokes, each two bars spreading into a V toward the rim with a recessed bronze insert between them, centre cap, rotor). The glass is a dark smoked bronze.

## Runtime contract

The glTF root `Roadster` faces +X with its origin on the floor at the wheelbase centre. `Wheel_FL/FR/RL/RR` pivots spin about local X. `NozzleAnchor_1..4` sit at the rear nozzles (the lift jets use their own under-floor positions). The lamp materials are emissive (`Lamp_DRL`, `Lamp_Headlamp`, `Lamp_TailRed*`, `Lamp_Amber`). About 69k triangles.

## Deliberate departures and calls

- The side window ends, the windshield wrap and the white roof rails follow the turnaround. The Tripo texture was too noisy to place them.
- The skill's pure convex-facet fit failed on this body, whose panels twist along its length (first attempt kept in `../model-v5/`). The fitting method here is section-based instead, with planar panels between authored creases.
- Wheel radii are 0.382 m front and 0.390 m rear, from the blueprint (the replay's spin radius is 0.353 m).

## Review history

Independent car judges scored v5 at 3.0, 4.6 and 5.2. After the user asked for a rebuild from the car's anatomy, v6 scored 5.6, 6.7, 6.9, 7.3, 7.2 and 7.7. A later judge working directly from Tesla's press photos scored it 5/10 and pointed at the wheels, the rear nozzles and the side vent; those were then rebuilt from the photos. A second photo-based judge scored the result 6 (nose 7, silhouette 7, recognisable from the front three-quarter) and led to the hood line, black nose face, rear plate band and V-spoke fixes. The remaining gap it named is the tunnel-back rear: the real rear glass sits sunk between the buttresses. Reports were summarised in the session.
