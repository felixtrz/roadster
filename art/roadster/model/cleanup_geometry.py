"""Collapse only float32-scale cut slivers after all exact material cuts.

No public export or file save occurs from importing this module. The build calls
the same operation as the repair utility, keeping the authored process repeatable.
"""
from pathlib import Path
import sys,json,math
import bpy,bmesh
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard,collection

AREA_LIMIT=6e-9  # safe margin above IWSDK's 5e-9 m² effective-zero threshold

def clean_cut_slivers():
    guard();records=[]
    for ob in collection('Authored').objects:
        if ob.type!='MESH':continue
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        before_faces=len(bm.faces);steps=0;max_edge=0.0
        while True:
            bad=[f for f in bm.faces if f.is_valid and f.calc_area()<AREA_LIMIT]
            if not bad:break
            face=min(bad,key=lambda f:f.calc_area())
            edge=min(face.edges,key=lambda e:e.calc_length())
            length=edge.calc_length()
            if length>.0005:
                raise RuntimeError(f'Refusing non-local sliver collapse on {ob.name}: {length}m')
            max_edge=max(max_edge,length)
            midpoint=(edge.verts[0].co+edge.verts[1].co)*.5
            bmesh.ops.pointmerge(bm,verts=list(edge.verts),merge_co=midpoint)
            bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-9)
            steps+=1
            if steps>1000:raise RuntimeError('Sliver cleanup did not converge')
        if steps:
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            bm.to_mesh(ob.data);ob.data.update()
            ob.data.set_sharp_from_angle(angle=math.radians(32));ob.data.update()
            records.append({'object':ob.name,'edge_collapses':steps,
                'before_triangles':before_faces,'after_triangles':len(ob.data.polygons),
                'maximum_collapsed_edge_m':max_edge,
                'maximum_per_collapse_vertex_displacement_m':max_edge/2})
        bm.free()
    report={'area_limit_m2':AREA_LIMIT,'official_preview_double_area_squared_threshold':1e-16,
      'method':'Shortest-edge midpoint collapse for exact-boundary cut triangles below IWSDK effective-zero area; no face deletion holes. Maximum accepted edge length0.5mm.',
      'objects':records,'scope':'All authored meshes inspected; only reported meshes changed.'}
    (ROOT/'fit/sliver-cleanup-v4.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    print(json.dumps(clean_cut_slivers(),indent=2))
    if '--commit' in sys.argv:
        from model_lib import save
        root=bpy.data.objects['Roadster'];output=ROOT.parents[2]/'public/models/roadster.glb'
        bpy.ops.object.select_all(action='DESELECT')
        for ob in collection('Authored').objects:ob.select_set(True)
        root.rotation_euler.z=math.pi/2;bpy.context.view_layer.update()
        bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,
            export_yup=True,export_apply=True,export_cameras=False,export_lights=False,
            export_extras=True,export_materials='EXPORT')
        root.rotation_euler.z=0;bpy.context.view_layer.update();save()
        print('Guarded project saved and runtime asset exported.')
    else:
        print('Trial only: no project save or export.')
