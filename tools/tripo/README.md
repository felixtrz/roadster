# Tripo reference-mesh pipeline

Run from the Roadster project root with Python 3.9+. No extra packages are needed.
The API credential stays in process and is read from macOS Keychain service
`tripo-api`, account `tripo`. Do not create an `.env` file or paste the key into a
command, transcript, or artifact.

Independent reference-image approval is required before either upload or model
generation. The client hashes every input and requires two distinct judges, each
scoring the complete reference set at least 9/10, with saved evidence reports.

```sh
python3 tools/tripo/client.py credential-check
python3 tools/tripo/client.py balance
python3 tools/tripo/client.py manifest \
  --front art/roadster/images/front.png \
  --left art/roadster/images/left.png \
  --back art/roadster/images/back.png \
  --right art/roadster/images/right.png
python3 tools/tripo/client.py plan
```

The `manifest` action creates `art/roadster/tripo/approved-images.json` with
`approved: false` and an empty judgment list. After independent agents have
inspected the images against the video, record their actual reports:

```json
{
  "approved": true,
  "judgments": [
    {"judge": "<first independent agent>", "score": 9.1, "report": "art/roadster/reviews/images-a.md"},
    {"judge": "<second independent agent>", "score": 9.0, "report": "art/roadster/reviews/images-b.md"}
  ]
}
```

Preserve the generated `images` and `parameters` fields when adding those review
records. Do not fabricate scores. Any changed input requires fresh judging and a
new run directory. Separate complete-car images are required; crop a consistent
sheet into individual views with no labels or neighboring cars.

After approval:

```sh
python3 tools/tripo/client.py upload
python3 tools/tripo/client.py submit --execute --max-credits 60
python3 tools/tripo/client.py poll --wait-seconds 45
python3 tools/tripo/client.py download
```

Repeat `poll` as needed; it only queries the existing task. `status` performs one
query. `download` fetches the successful task's mesh and previews and records
SHA-256 hashes. All commands accept `--manifest` and `--run`; run directories must
be below `art/roadster/tripo/`. Submission records an intent before the billable
request, preventing accidental duplicate generation after a timeout. An unknown
outcome requires reconciliation against account usage before any new run.

The default reference uses H3.1, 200,000 faces, detailed geometry, detailed PBR
textures, and fixed geometry/texture seeds. Current public pricing estimates
60 credits (USD 0.60). The API's actual `credits_consumed` and before/after balance
are saved in `ledger.json`. This is a high-detail measurement reference for the
authored model; runtime geometry should be rebuilt and measured in Blender.

The V3 view-key request is explicit:

```json
{
  "inputs": [
    {"front": "<front_file_token>"},
    {"left": "<left_file_token>"},
    {"back": "<back_file_token>"},
    {"right": "<right_file_token>"}
  ],
  "model": "v3.1-20260211",
  "face_limit": 200000,
  "geometry_quality": "detailed",
  "texture": true,
  "pbr": true,
  "texture_quality": "detailed",
  "texture_alignment": "original_image",
  "model_seed": 20261017,
  "texture_seed": 20261017
}
```

The API canonicalizes semantic views to front, left, back, right. At least two
views are required, including front. The docs do not specify exact lens or
elevation. Direct nose, physical-left profile, rear, and physical-right profile,
at the same scale, elevation, and light, avoid ambiguous camera interpretation.
File upload supports PNG/JPEG up to 20 MB; use images at least 256 pixels square.
[Official upload documentation](https://developers.tripo3d.ai/en/docs/files),
[H-series multiview documentation](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard).

Available pinned models include H3.1 `v3.1-20260211`, H3.0 `v3.0-20250812`,
H2.5 `v2.5-20250123`, P1 `P1-20260311`, and P2 preview `P2-20260801`. P-series
targets lower face counts: P1 at most 20,000, P2 triangle output at most 50,000.
The client removes the H-only geometry-quality option for P-series and H2.5.
The default H3.1 supports the detailed reference needed for the Blender rebuild.
[Official P-series documentation](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p),
[H3.1 model and pricing](https://developers.tripo3d.ai/en/models/v3-1),
[pricing](https://developers.tripo3d.ai/en/pricing).

API requests use only `https://openapi.tripo3d.ai/v3`. Redirects are rejected.
Downloads use HTTPS Tripo domains and never receive the API credential. Signed
output links in artifact ledgers may expire; querying the task refreshes them.
[Task queries](https://developers.tripo3d.ai/en/docs/task-query),
[account balance and usage](https://developers.tripo3d.ai/en/docs/account).

## Blender handoff

The external mesh-rebuild skill (set `MESH_REBUILD_SKILL` to its `scripts/` directory) is
`rebuild-generated-mesh/SKILL.md`.
It requires an untouched source mesh, one guarded `.blend` project, fit-derived
dimensions, separate moving parts, repeatable build scripts, measured
cross-sections, same-camera comparisons, and a written record of deliberate
departures. Use metres, Blender Z-up, vehicle forward -Y, vehicle left +X, ground
Z=0. The generated mesh remains a reference, with authored geometry rebuilt from
it. Four wheels need distinct pivots; the car body can move as a rigid assembly.
The skill's no-subdivision/no-bevel flat-facet style is a deliberate choice that
must be reconciled with this smooth car's silhouette during model review.

Keep the source GLB, measured fitting inputs, section overlays, authored output,
triangle/part statistics, and independent render judgments in the car art folder.
Do not claim the Tripo shell itself is the clean, articulated Blender rebuild.
