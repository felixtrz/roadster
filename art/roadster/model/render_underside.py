"""Focused underside evidence; does not save scene or alter the GLB."""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import *
guard();camera=studio();bpy.data.objects['StudioFloor'].hide_render=True
collection('Ref').hide_render=True;collection('Authored').hide_render=False
light=bpy.data.lights.new('UndersideReviewFill','AREA');light.energy=1400;light.size=6
ob=bpy.data.objects.new('UndersideReviewFill',light);collection('Studio').objects.link(ob);ob.location=(1,-3,-5);aim(ob,(0,0,.2))
camera.location=(3,-5,-6);aim(camera,(0,0,.3));camera.data.ortho_scale=6.1
objects=[o for o in collection('Authored').objects if o.type=='MESH']
original={o:list(o.data.materials) for o in objects}
indices={o:[p.material_index for p in o.data.polygons] for o in objects}
clay=material('ReviewClay',(.34,.42,.48),roughness=.55)
for mode in ['material','clay']:
 for o in objects:
  o.data.materials.clear()
  for mat in ([clay] if mode=='clay' else original[o]):o.data.materials.append(mat)
  for p,index in zip(o.data.polygons,indices[o]):p.material_index=0 if mode=='clay' else index
 bpy.context.scene.render.filepath=str(ROOT/'renders'/f'{mode}-underside.png')
 bpy.ops.render.render(write_still=True)
