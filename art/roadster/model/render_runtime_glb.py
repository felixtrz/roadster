"""Round-trip inspection of the exact GLB; never saves or changes the project."""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import *
guard();collection('Authored',clear=True)
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT.parents[2]/'public/models/roadster.glb'))
imported=[o for o in bpy.data.objects if o not in before]
group=collection('Authored')
for ob in imported:
 for old in list(ob.users_collection):old.objects.unlink(ob)
 group.objects.link(ob)
# Undo only the parent basis correction for the established inspection cameras.
root=next(o for o in imported if o.name=='Roadster')
root.rotation_mode='XYZ';root.rotation_euler=(0,0,0)
bpy.context.view_layer.update()
render_views(ROOT/'runtime-glb-renders',groups=('Authored',),modes=('material','clay'),views=('front','quarter','rear-quarter','low-front','low-quarter'))
print('Exact exported GLB round-trip rendered; no project save performed')
