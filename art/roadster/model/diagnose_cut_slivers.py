"""Read-only trial of a micron-scale weld after the exact material-boundary cuts."""
from pathlib import Path
import sys,json
import bpy,bmesh
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard
guard()
ob=bpy.data.objects['BodyShell'];original=ob.data
results=[]
for distance in (0,1e-6,2e-6,5e-6,1e-5,2e-5,5e-5):
    bm=bmesh.new();bm.from_mesh(original)
    if distance:
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=distance)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=distance)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    area=np.array([f.calc_area() for f in bm.faces]);counts={}
    for i,mat in enumerate(original.materials):
        a=np.array([f.calc_area() for f in bm.faces if f.material_index==i])
        counts[mat.name]={'faces':len(a),'area':float(a.sum()),'below_threshold':{str(x):int((a<x).sum()) for x in (1e-10,1e-9,1e-8,1e-7)}}
    results.append({'weld_distance_m':distance,'vertices':len(bm.verts),'faces':len(bm.faces),'materials':counts})
    bm.free()
(ROOT/'diagnostics/cut-sliver-trials.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
