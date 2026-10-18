"""Create the isolated Roadster Blender project from the untouched Tripo GLB."""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Matrix
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import BLEND,guard,save,collection,render_views

SOURCE=ROOT.parent/'tripo/h31-reference-v1/model_url.glb'
import os
SKILL=Path(os.environ.get('MESH_REBUILD_SKILL',''))
if not os.environ.get('MESH_REBUILD_SKILL') or not SKILL.is_dir():
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory.')

if BLEND.exists():
    if Path(bpy.data.filepath).resolve()!=BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
else:
    if bpy.data.filepath:
        raise RuntimeError('Bootstrap refuses to overwrite an existing project')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
guard()
if not bpy.data.objects.get('RefMesh'):
    group=collection('Ref')
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    imported=[ob for ob in bpy.data.objects if ob not in before]
    meshes=[ob for ob in imported if ob.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for ob in meshes:ob.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    bpy.ops.object.join()
    ref=bpy.context.object;ref.name='RefMesh'
    for old in list(ref.users_collection):old.objects.unlink(ref)
    group.objects.link(ref)
    # Tripo default export is +X forward; rotate that to the model's -Y forward.
    ref.matrix_world=Matrix.Rotation(-math.pi/2,4,'Z')@ref.matrix_world
    bpy.context.view_layer.update()
    coords=np.array([ref.matrix_world@v.co for v in ref.data.vertices])
    lo,hi=coords.min(0),coords.max(0)
    length=hi[1]-lo[1]
    if length<hi[0]-lo[0] or length<hi[2]-lo[2]:
        raise RuntimeError('Unexpected source orientation; inspect before normalizing')
    scale=4.6/length
    ref.matrix_world=Matrix.Scale(scale,4)@ref.matrix_world
    bpy.context.view_layer.update()
    coords=np.array([ref.matrix_world@v.co for v in ref.data.vertices])
    lo,hi=coords.min(0),coords.max(0)
    translation=tuple(float(v) for v in (-(lo[0]+hi[0])/2,-(lo[1]+hi[1])/2,-lo[2]))
    ref.matrix_world=Matrix.Translation(translation)@ref.matrix_world
    ref['rebuild_aligned']={'nominal_length_m':4.6,'scale':float(scale),'translate':translation,'rotate_z_degrees':-90}
    ref['source_file']=str(SOURCE)
    for ob in imported:
        if ob.name in bpy.data.objects and ob!=ref and ob.type!='MESH':
            bpy.data.objects.remove(ob,do_unlink=True)
    bpy.context.view_layer.update()
ref=bpy.data.objects['RefMesh']
g={};exec((SKILL/'extract_reference.py').read_text(),g)
report=g['extract']('RefMesh',str(ROOT/'reference'))
report['source']=str(SOURCE.relative_to(ROOT.parent.parent.parent))
report['normalization']={'nominal_length_m':4.6,'scale':float(ref['rebuild_aligned']['scale']),
                         'translate':list(ref['rebuild_aligned']['translate']),'rotate_z_degrees':-90}
(ROOT/'reference/report.json').write_text(json.dumps(report,indent=2)+'\n')
save()
render_views(ROOT/'reference/renders',groups=('Ref',),modes=('material',),views=('front','left','back','top','quarter'))
save()
print('ROADSTER_REFERENCE '+json.dumps(report))
