"""Studio glamour renders of the RoadsterV5 collection (EEVEE, raytraced reflections).
  Blender -b roadster_v5.blend -P render_glamour.py -- <out_prefix> [views]"""
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
views = argv[1].split(',') if len(argv) > 1 else ['hero', 'side', 'rear', 'low', 'top3q', 'front']
sc = bpy.context.scene
for c in bpy.data.collections:
    lc = bpy.context.view_layer.layer_collection.children.get(c.name)
    if lc: lc.exclude = c.name not in ('RoadsterV5', 'Studio')
st = bpy.data.collections.get('Studio')
if st:
    for o in list(st.objects): bpy.data.objects.remove(o)
else:
    st = bpy.data.collections.new('Studio'); sc.collection.children.link(st)
def link(o): st.objects.link(o); return o
sc.render.engine = 'BLENDER_EEVEE'
ee = sc.eevee
for k, v in (('use_raytracing', True), ('taa_render_samples', 64), ('use_shadows', True)):
    if hasattr(ee, k): setattr(ee, k, v)
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Punchy' if 'AgX - Punchy' in [i.name for i in []] else 'None'
w = bpy.data.worlds.get('Studio') or bpy.data.worlds.new('Studio'); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
grad = nt.nodes.new('ShaderNodeTexGradient'); tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
ramp = nt.nodes.new('ShaderNodeValToRGB')
mp.inputs['Rotation'].default_value = (0, math.radians(-90), 0)
nt.links.new(tc.outputs['Generated'], mp.inputs[0]); nt.links.new(mp.outputs[0], grad.inputs[0])
nt.links.new(grad.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], o.inputs[0])
ramp.color_ramp.elements[0].color = (0.004, 0.005, 0.007, 1); ramp.color_ramp.elements[1].color = (0.09, 0.1, 0.12, 1)
bg.inputs[1].default_value = 1.0
floor = link(bpy.data.objects.new('Floor', bpy.data.meshes.new('Floor')))
import bmesh
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30); bm.to_mesh(floor.data); bm.free()
fm = bpy.data.materials.get('M_StudioFloor') or bpy.data.materials.new('M_StudioFloor'); fm.use_nodes = True
pb = fm.node_tree.nodes['Principled BSDF']; pb.inputs['Base Color'].default_value = (0.012, 0.013, 0.015, 1); pb.inputs['Roughness'].default_value = 0.22
floor.data.materials.append(fm)
def area(name, loc, size, energy, color=(1, 1, 1), target=(0, 0, 0.5), shape='RECTANGLE', sy=None):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.color = color; l.shape = shape; l.size = size; l.size_y = sy or size
    ob = link(bpy.data.objects.new(name, l)); ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob
area('Key', (0, 0, 6.5), 4.0, 2600, sy=7.0)
area('RimL', (6, 2, 2.2), 2.0, 900, (0.75, 0.85, 1.0), sy=6)
area('RimR', (-6, -1, 2.0), 2.0, 700, (1.0, 0.25, 0.3), sy=6)
area('Front', (1.5, -7, 1.6), 3.0, 500)
cam = bpy.data.objects.get('GlamCam') or bpy.data.objects.new('GlamCam', bpy.data.cameras.new('GlamCam'))
if cam.name not in st.objects: st.objects.link(cam)
sc.camera = cam
V = {'hero': ((4.8, -6.0, 1.35), (0, -0.2, 0.55), 50), 'side': ((8.5, 0, 0.75), (0, 0, 0.6), 50),
     'rear': ((-4.6, 5.8, 1.5), (0, 0.4, 0.6), 50), 'low': ((2.6, -5.2, 0.35), (0, -0.6, 0.6), 32),
     'top3q': ((5.5, -5.0, 4.5), (0, 0, 0.4), 45), 'front': ((0, -8.5, 0.9), (0, 0, 0.6), 55),
     'wheel': ((3.0, -2.6, 0.6), (1.0, -1.4, 0.4), 50)}
for v in views:
    loc, tgt, lens = V[v]
    cam.location = loc; cam.data.lens = lens
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{out}-{v}.png'; bpy.ops.render.render(write_still=True)
