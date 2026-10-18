"""Headless orthographic/perspective review renders.
  Blender -b roadster_v5.blend -P render_views.py -- <out_prefix> <collections comma> [views comma] [mode: solid|material]
"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
out, cols = argv[0], argv[1].split(',')
views = argv[2].split(',') if len(argv) > 2 else ['front', 'left', 'back', 'top', 'quarter', 'rquarter']
mode = argv[3] if len(argv) > 3 else 'solid'
sc = bpy.context.scene
for c in bpy.data.collections:
    lc = bpy.context.view_layer.layer_collection.children.get(c.name)
    if lc: lc.exclude = c.name not in cols
sc.render.engine = 'BLENDER_WORKBENCH' if mode == 'solid' else 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1200, 700
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'MATERIAL' if mode == 'solid' else 'MATERIAL'
sc.display.shading.show_cavity = True
sc.display.shading.show_specular_highlight = True
if mode != 'solid':
    w = bpy.data.worlds.get('W') or bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.5, 0.52, 0.55, 1); bg.inputs[1].default_value = 1.0
    sc.view_settings.view_transform = 'AgX'
cam = bpy.data.objects.get('ReviewCam')
if not cam:
    cam = bpy.data.objects.new('ReviewCam', bpy.data.cameras.new('ReviewCam')); sc.collection.objects.link(cam)
sc.camera = cam
T = Vector((0, 0, 0.6))
V = {'front': ((0, -10, 0.6), 'O', 5.0), 'back': ((0, 10, 0.6), 'O', 5.0), 'left': ((10, 0, 0.6), 'O', 5.2),
     'right': ((-10, 0, 0.6), 'O', 5.2), 'top': ((0, 0, 10), 'O', 5.2),
     'quarter': ((6.5, -7.5, 2.6), 'P', 40), 'rquarter': ((6.5, 7.5, 2.6), 'P', 40), 'low': ((4.2, -6.5, 0.45), 'P', 35), 'hero': ((4.6, -5.2, 1.5), 'P', 45), 'rhero': ((-4.4, 5.4, 1.3), 'P', 45),
     'under': ((0, 0, -10), 'O', 5.2)}
for v in views:
    loc, kind, size = V[v]
    cam.location = loc
    d = (T - Vector(loc)).normalized()
    cam.rotation_euler = d.to_track_quat('-Z', 'Y' if v not in ('top', 'under') else 'Y').to_euler()
    if v in ('top', 'under'): cam.rotation_euler = (0, 0, 0) if v == 'top' else (math.pi, 0, 0)
    cam.data.type = 'ORTHO' if kind == 'O' else 'PERSP'
    if kind == 'O': cam.data.ortho_scale = size
    else: cam.data.lens = size
    sc.render.filepath = f'{out}-{v}.png'
    bpy.ops.render.render(write_still=True)
