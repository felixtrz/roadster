"""Small Blender authoring/rendering helpers scoped to Roadster.blend."""
from pathlib import Path
import math
import json
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
BLEND = ROOT / "Roadster.blend"


def guard():
    if Path(bpy.data.filepath).resolve() != BLEND:
        raise RuntimeError("Refusing scene mutation outside Roadster.blend")


def save():
    guard()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))


def collection(name, clear=False):
    guard()
    result = bpy.data.collections.get(name)
    if result is None:
        result = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(result)
    if clear:
        for ob in list(result.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
    return result


def material(name, color, metallic=0.0, roughness=0.35, emission=0.0):
    guard()
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Emission Color"].default_value = (*color, 1)
    p.inputs["Emission Strength"].default_value = emission
    if name=='SmokedCanopy':
        p.inputs['Specular IOR Level'].default_value=.30
        p.inputs['IOR'].default_value=1.18
    return mat


def empty(name, at=(0, 0, 0), parent=None, target=None):
    guard()
    ob = bpy.data.objects.new(name, None)
    (target or collection("Authored")).objects.link(ob)
    ob.location = at
    ob.parent = parent
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.15
    return ob


def mesh(name, vertices, faces, mat, parent=None, target=None, smooth=False):
    guard()
    me = bpy.data.meshes.new(name + "Geometry")
    me.from_pydata(vertices, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-8)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (target or collection("Authored")).objects.link(ob)
    ob.parent = parent
    if mat:
        me.materials.append(mat)
    for polygon in me.polygons:
        polygon.use_smooth = smooth
    return ob


def solid_box(name, bounds, mat, parent=None):
    (x0, y0, z0), (x1, y1, z1) = bounds
    points = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
              (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    return mesh(name, points, [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)], mat, parent)


def revolve(name, profile, axis, mat, parent=None, sides=64):
    """Revolve (axis distance, radius) profile; axis is X or Y."""
    vertices = []
    rings=[]
    for distance, radius in profile:
        if radius<1e-8:
            rings.append([len(vertices)])
            vertices.append((distance,0,0) if axis=="X" else (0,distance,0))
            continue
        indices=[]
        for j in range(sides):
            angle = 2 * math.pi * j / sides
            c, s = radius * math.cos(angle), radius * math.sin(angle)
            indices.append(len(vertices));vertices.append((distance, c, s) if axis == "X" else (c, distance, s))
        rings.append(indices)
    faces = []
    for first,second in zip(rings,rings[1:]):
        for j in range(sides):
            if len(first)==1:faces.append((first[0],second[j],second[(j+1)%sides]))
            elif len(second)==1:faces.append((first[j],second[0],first[(j+1)%sides]))
            else:faces.append((first[j],first[(j+1)%sides],second[(j+1)%sides],second[j]))
    return mesh(name, vertices, faces, mat, parent,smooth=('Tire' in name or 'Nozzle' in name))


def line_tube(name, points, radius, mat, parent=None, sides=6):
    vertices=[]
    for i, point in enumerate(points):
        p=Vector(point)
        tangent=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
        tangent.normalize()
        hint=Vector((0,0,1)) if abs(tangent.z)<.9 else Vector((1,0,0))
        a=tangent.cross(hint).normalized();b=tangent.cross(a).normalized()
        for j in range(sides):
            vertices.append(tuple(p+radius*(a*math.cos(j*2*math.pi/sides)+b*math.sin(j*2*math.pi/sides))))
    faces=[]
    for i in range(len(points)-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    return mesh(name,vertices,faces,mat,parent)


def aim(ob, point):
    ob.rotation_euler=(Vector(point)-ob.location).to_track_quat('-Z','Y').to_euler()


def studio():
    guard()
    group=collection("Studio",clear=True)
    floor_mat=material("StudioFloor",(.32,.35,.39),roughness=.65)
    mesh("StudioFloor",[(-200,-200,-.012),(200,-200,-.012),(200,200,-.012),(-200,200,-.012)],[(0,1,2,3)],floor_mat,target=group)
    for name,location,energy,size in [("Key",(4,-5,7),1200,5),("Fill",(-4,-1,4),1000,5),("Rim",(1,5,6),1800,4)]:
        light=bpy.data.lights.new(name,'AREA');light.energy=energy;light.shape='DISK';light.size=size
        ob=bpy.data.objects.new(name,light);group.objects.link(ob);ob.location=location;aim(ob,(0,0,.5))
    world=bpy.context.scene.world or bpy.data.worlds.new("RoadsterStudio")
    bpy.context.scene.world=world;world.use_nodes=True
    world.node_tree.nodes["Background"].inputs[0].default_value=(.28,.31,.36,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=.45
    camera_data=bpy.data.cameras.new("ModelReviewCamera")
    camera=bpy.data.objects.new("ModelReviewCamera",camera_data);group.objects.link(camera)
    camera_data.type='ORTHO';camera_data.ortho_scale=6.1
    bpy.context.scene.camera=camera
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=640;scene.render.resolution_y=480;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX'
    return camera


VIEWS={
    "front":(0,-9,2.5),"left":(9,0,2.3),"back":(0,9,2.5),
    "right":(-9,0,2.3),"top":(0,0,12),"quarter":(7,-8,4.3),"rear-quarter":(-7,8,4.0),
    "low-front":(0,-9,1.5),"low-quarter":(-7,-6,1.5),
}


def render_views(folder, groups=("Authored",), modes=("material","clay"), views=None):
    guard()
    camera=studio();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for group in ("Authored","Ref"):
        if item:=bpy.data.collections.get(group):item.hide_render=group not in groups
    objects=[ob for g in groups if (c:=bpy.data.collections.get(g)) for ob in c.objects if ob.type=='MESH']
    clay=material("ReviewClay",(.34,.42,.48),metallic=0.0,roughness=.55)
    originals={ob: list(ob.data.materials) for ob in objects}
    indices={ob:[p.material_index for p in ob.data.polygons] for ob in objects}
    for mode in modes:
        for ob in objects:
            ob.data.materials.clear()
            for mat in ([clay] if mode=='clay' else originals[ob]):ob.data.materials.append(mat)
            for polygon,index in zip(ob.data.polygons,indices[ob]):polygon.material_index=0 if mode=='clay' else index
        for name in (views or VIEWS):
            low=name.startswith('low-')
            camera.data.type='PERSP' if low else 'ORTHO'
            if low:
                camera.data.sensor_fit='VERTICAL';camera.data.sensor_height=24
                camera.data.lens=24/(2*math.tan(math.radians(42)/2))
            camera.location=VIEWS[name];aim(camera,(0,0,.7 if low else .65))
            if name=='top': camera.rotation_euler=(0,0,0)
            bpy.context.scene.render.filepath=str(folder/f"{mode}-{name}.png")
            bpy.ops.render.render(write_still=True)
    for ob,mats in originals.items():
        ob.data.materials.clear()
        for mat in mats:ob.data.materials.append(mat)
        for polygon,index in zip(ob.data.polygons,indices[ob]):polygon.material_index=index
    metadata={name:{'eye_blender':list(VIEWS[name]),'target_blender':[0,0,.7 if name.startswith('low-') else .65],
               'projection':'perspective' if name.startswith('low-') else 'orthographic',
               'vertical_fov_degrees':42 if name.startswith('low-') else None,
               'ortho_scale_m':None if name.startswith('low-') else 6.1,
               'resolution':[640,480]} for name in (views or VIEWS)}
    existing=folder/'cameras.json'
    if existing.exists():metadata={**json.loads(existing.read_text()),**metadata}
    existing.write_text(json.dumps(metadata,indent=2)+'\n')
