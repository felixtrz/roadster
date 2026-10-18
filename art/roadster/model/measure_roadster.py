"""Create skill-format cross-sections and export immutable model metadata."""
from pathlib import Path
import json
import hashlib
import sys
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard,collection
guard()
FIT=json.loads((ROOT/'fit/roadster.json').read_text())
import os
SKILL=Path(os.environ.get('MESH_REBUILD_SKILL',''))
if not os.environ.get('MESH_REBUILD_SKILL') or not SKILL.is_dir():
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory.')
g={};exec((SKILL/'sections.py').read_text(),g)
parts=[o.name for o in collection('Authored').objects if o.type=='MESH']
planes=[
 {'name':'Central side silhouette','axis':'x','value':.001,'window':[-2.5,2.5,0,1.5],'score':[-2.4,2.4,.12,1.4]},
 {'name':'Wheel-side silhouette','axis':'x','value':FIT['front_wheel']['centre_x'],'window':[-2.5,2.5,0,1.5]},
 {'name':'Front axle cross-section','axis':'y','value':FIT['front_wheel']['y'],'window':[-1.4,1.4,0,1.5]},
 {'name':'Cabin cross-section','axis':'y','value':.10,'window':[-1.4,1.4,0,1.5]},
 {'name':'Rear axle cross-section','axis':'y','value':FIT['rear_wheel']['y'],'window':[-1.4,1.4,0,1.5]},
 {'name':'Body shoulder plan','axis':'z','value':.83,'window':[-1.4,1.4,-2.5,2.5]},
]
out_dir=ROOT/('checkpoint-v4/sections' if '--checkpoint' in sys.argv else 'sections')
result=g['run']('roadster',planes,auth_objects=parts,ref_object='RefMesh',out_dir=str(out_dir))
if '--checkpoint' in sys.argv:
 print(json.dumps({'checkpoint_sections':result}));raise SystemExit(0)
objects=collection('Authored').objects
verts=[]
for ob in objects:
 if ob.type=='MESH':verts.extend([tuple(ob.matrix_world@v.co) for v in ob.data.vertices])
coords=np.array(verts);lo=coords.min(0);hi=coords.max(0)
wheel_records={}
for label,fitkey in [('FL','front_wheel'),('FR','front_wheel'),('RL','rear_wheel'),('RR','rear_wheel')]:
 w=FIT[fitkey];side=1 if label.endswith('L') else -1
 # Blender(+x left,-y forward,+z up) -> runtime(-y forward,+z up,-x left).
 wheel_records['Wheel_'+label]={'runtime_position':[-w['y'],w['radius'],-side*w['centre_x']],
  'radius_m':w['radius'],'spin_axis_local':[1,0,0],'suspension_axis_runtime':[0,1,0]}
anchors={}
for i in range(1,5):
 ob=bpy.data.objects['NozzleAnchor_'+str(i)];x,y,z=ob.location
 anchors[ob.name]={'runtime_position':[-y,z,-x],'forward_local':[0,0,1],
                    'rearward_runtime':[-1,0,0]}
contract=json.loads((ROOT/'model-contract.json').read_text())
contract.update({'stage':'v4 full authored model; fresh final independent review pending',
 'revision':'v4',
 'glTF_axes':{'up':'+Y','forward':'+X','left':'-Z'},'runtime_root_correction':'Roadster root has Blender Z +90deg during export; saved .blend remains -Y forward.',
 'origin':'Floor at centre of four wheel-contact rectangle, fitted axle y midpoint0.',
 'blender_bounds':{'min':lo.tolist(),'max':hi.tolist()},
 'runtime_size_m':{'length':float(hi[1]-lo[1]),'width':float(hi[0]-lo[0]),'height':float(hi[2]-lo[2])},
 'wheelbase_m':FIT['wheelbase'],'front_track_m':FIT['front_track'],'rear_track_m':FIT['rear_track'],
 'wheel_nodes':wheel_records,'nozzle_anchors':anchors,
 'source':{'file':'art/roadster/tripo/h31-reference-v1/model_url.glb','triangles':188630,'role':'untouched measurement reference only'},
 'authored':{'file':'public/models/roadster.glb','triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects if o.type=='MESH'),
 'sha256':hashlib.sha256((ROOT.parents[2]/'public/models/roadster.glb').read_bytes()).hexdigest(),
 'mesh_parts':len([o for o in objects if o.type=='MESH']),'objects':len(objects),'generated_source_triangles_shipped':0},
 'fitting':{'wheel_front':FIT['front_wheel']['fit'],'wheel_rear':FIT['rear_wheel']['fit'],
             'cross_sections':'art/roadster/model/sections/roadster.json',
             'fair_primary_controls':'art/roadster/model/fit/fair-body-v4.json',
             'primary_constraints':'art/roadster/model/fit/form-validation-v4.json'},
 'required_parts':['BodyShell continuous exterior with paint/glass/corner-lens face regions',
  'Canopy semantic empty; glass is owned by BodyShell',
  'Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR',
  'NozzleAnchor_1','NozzleAnchor_2','NozzleAnchor_3','NozzleAnchor_4',
  'FrontLightBar','RearLightBar','Undercarriage','DiffuserChannel_1 through DiffuserChannel_5',
  'DiffuserFrame','RearWhiteRelief','RearBlankPlate'],
 'quality_gate':['Tripo mesh remains untouched reference only.',
  'Authored coherent main shell; no fused source shell in runtime export.',
  'Four independent wheels with semantic pivots.',
  'Cross-sections and same-camera clay/material reference comparisons.',
  'Rendered triangles <100000.',
  'Independent final judges >=9/10; v1 scored6.3, v2 scored7.2, v3 scored7.8; V4 full review pending.'],
 'exterior_ownership':{'glass_mesh':'BodyShell','overlay_glass_meshes':0,
  'side_glass':'One coherent fitted plane per side, with shared frame vertices blended over80mm; original YZ aperture landmarks preserved',
  'a_pillar':'Exact25mm white frame beside dark structural trim; broad white bridge removed without changing the window nose landmark',
  'corner_lenses':'Exact XZ triangles cut into forward BodyShell cap; no overlaid surface',
  'front_nose':'Explicit shared cap grid, flat central face, local60mm outer-corner fillet and35mm lower-cap rake; no broad plan sweep or warped cheek unions',
  'front_opening':'A common cutter removes both body and undercarriage; Boolean cavity walls are deleted afterward and flush black jamb/back geometry owns the cavity',
  'rocker':'Belt joins the exact white lower edge; duplicate belt roof removed after all Booleans; redundant intersecting sill tubes removed'},
 'deliberate_departures':[
  'Exact bilateral symmetry and floor-corrected circle-fitted wheels.',
  'Inner tire width is authored at0.275m because the source hides inner surfaces.',
  'The fallible generated reference is sampled at65 stations across14 lateral rails. V4 replaces moving/sorted cross-section indices with fixed semantic rails and C1 source-informed longitudinal controls. This removes unintentional local dents while retaining designed roof, shoulder and outer-side planes.',
  'Windshield, roof, rear hatch, pointed side glazing, paint and corner lenses have shared exterior topology. Exact YZ side aperture and XY roof-edge boundary planes split existing faces before material assignment, eliminating centroid-mask notches.',
  'Side glazing is projected onto a plane fitted to the six source-informed aperture controls; maximum corner departure33.2mm. The surrounding frame blends over80mm. A25mm white front frame and dark structural trim replace the broad white A-pillar bridge while preserving the source window nose landmark.',
  'The leading nose is a declining wedge with monotonic rearward hood/fender rails and a flat central cap. Only the outermost60mm corner is filleted; the lower cap rakes backward35mm. The shoulder rises steadily from0.865m at the front axle to0.990m at the rear axle; the outer white rail stays0.070m below through the door.',
  'The body and undercarriage share an opening; the belt cut reaches below the cavity floor and the splitter is a narrow77mm lip. A separate dark strip within the cavity gives the thin emitting bar a legible background.',
  'The belt remains a closed solid for all Booleans, then its duplicate upper interface and cavity walls are removed. Flush black intake jambs own the cavity and no white Boolean wall remains beneath them. Redundant sill tubes were removed rather than left intersecting the white lower edge.',
  'The glass remains opaque smoked material; source does not support a detailed interior.',
  'Rear white relief, contained concave diffuser channels, front recess and small triangular corner lamps are authored constructions constrained by visible source envelopes. Lens borders are exact XZ cuts into forward-facing cap geometry; all luminous lens area faces runtime+X. WhiteLED emission is8 to retain a bright white/cyan core under tone mapping without postprocessing.',
  'The front recess uses near-black rough metallic shading to preserve darkness under the runtime image-based lighting; this is a visual material approximation rather than a source material measurement.',
  'Hidden undertray and nozzle interiors remain simple authored assumptions. No generated source triangles ship.'
 ],
 'material_and_clay_evidence':'art/roadster/model/renders/contact.png',
 'export_round_trip_evidence':'art/roadster/model/runtime-glb-renders/',
 'microscopic_cut_cleanup':'art/roadster/model/fit/sliver-cleanup-v4.json',
 'material_culling_intent':'art/roadster/model/fit/material-side-audit-v4.json',
 'low_view_evidence':{'eye_runtime':[6,1.5,7],'target_runtime':[0,.7,0],'vertical_fov_degrees':42,
  'resolution':[640,480],'limit':'Blender exact-GLB round-trip at the runtime camera convention; actual browser evidence is captured separately by the root task.'},
 'prior_independent_scores':{'v1':6.3,'v2':7.2,'v3':7.8},
 'primary_preflight':'checkpoint-v4-b; no critical primary blocker; not a final score',
 'independent_quality_score':None})
(ROOT/'model-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print(json.dumps({'sections':result,'authored':contract['authored'],'dimensions':contract['runtime_size_m']}))
