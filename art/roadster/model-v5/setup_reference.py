"""Fresh v5 rebuild: import the untouched Tripo GLB as RefMesh, orient (face -Y, left +X, Z up),
scale to 4.6 m nominal length, floor at z=0, extract the face table. Run headless:
  Blender -b -P setup_reference.py
"""
import bpy, math, os, sys, json
from mathutils import Matrix
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '')
REPO = os.path.abspath(os.path.join(ROOT, '..', '..', '..'))
S = os.environ.get('MESH_REBUILD_SKILL', '')
if not os.path.isdir(S):
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory '
                     '(the one containing blender_lib.py, facets.py and extract_reference.py).')
S = os.path.join(S, '')
TRIPO = os.path.join(REPO, 'art', 'roadster', 'tripo', 'h31-reference-v1', 'model_url.glb')
if not os.path.isfile(TRIPO):
    raise SystemExit(f'{TRIPO} is missing. The Tripo reference mesh is not distributed (see NOTICE.md).')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=TRIPO)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1: bpy.ops.object.join()
ref = bpy.context.view_layer.objects.active
ref.name = 'RefMesh'
ref.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o)
col = bpy.data.collections.new('Ref'); bpy.context.scene.collection.children.link(col)
for c in ref.users_collection: c.objects.unlink(ref)
col.objects.link(ref)
ref.matrix_world = Matrix.Rotation(math.radians(-90), 4, 'Z') @ ref.matrix_world
bpy.context.view_layer.update()
import numpy as np
co = np.array([ref.matrix_world @ v.co for v in ref.data.vertices])
lo, hi = co.min(0), co.max(0)
print('BOUNDS', lo, hi)
g = {}; exec(open(S + 'extract_reference.py').read(), g)
length = hi[1] - lo[1]
print(g['align']('RefMesh', scale=4.6 / length))
bpy.ops.wm.save_as_mainfile(filepath=ROOT + 'roadster_v5.blend')
print(json.dumps(g['extract']('RefMesh', ROOT + 'reference/')))
