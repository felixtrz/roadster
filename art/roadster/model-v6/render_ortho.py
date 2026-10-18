"""Orthographic side/front/back renders at the blueprint's pixel scale, transparent background.
  Blender -b roadster_v6.blend -P render_ortho.py -- <out_prefix>"""
import bpy, sys, math
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
for c in bpy.data.collections:
    lc = bpy.context.view_layer.layer_collection.children.get(c.name)
    if lc: lc.exclude = c.name != 'RoadsterV6'
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = True
sc.render.film_transparent = True
cam = bpy.data.objects.get('OrthoCam') or bpy.data.objects.new('OrthoCam', bpy.data.cameras.new('OrthoCam'))
if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
sc.camera = cam; cam.data.type = 'ORTHO'
# (name, camera location, look dir, px size, m per px, centre (u, z))
V = [('side', (12, 0, 0.7), 4.6 / 726, (800, 320), (0.0, 0.93)),
     ('front', (0, -12, 0.7), 1.31 / 255, (520, 300), (0.0, 0.66)),
     ('back', (0, 12, 0.7), 1.31 / 267, (560, 300), (0.0, 0.66))]
for name, loc, mpp, (w, h), (cu, cz) in V:
    sc.render.resolution_x, sc.render.resolution_y = w, h
    cam.data.ortho_scale = w * mpp
    l = Vector(loc)
    if name == 'side': cam.location = (12, cu, cz)
    elif name == 'front': cam.location = (cu, -12, cz)
    else: cam.location = (-cu, 12, cz)
    cam.rotation_euler = (Vector((0, 0, cz)) - Vector((cam.location.x, cam.location.y, cz))).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{out}-{name}.png'
    bpy.ops.render.render(write_still=True)
