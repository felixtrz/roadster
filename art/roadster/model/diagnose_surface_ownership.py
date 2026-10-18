"""Read-only primary normal/contact evidence for the current guarded project."""
from pathlib import Path
import json,sys,math
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard
guard()
polygon=json.loads((ROOT/'fit/fair-body-v4.json').read_text())['side_glass_yz']
co=np.array(json.loads((ROOT/'fit/side-glass-plane-v4.json').read_text())['coefficients'])
def inside(y,z):
    result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>z)!=(b[1]>z) and y<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result
body=bpy.data.objects['BodyShell'];faces=[f for f in body.data.polygons if f.material_index==1 and abs(f.normal.x)>.25 and inside(f.center.y,f.center.z)]
vertices={int(i) for f in faces for i in f.vertices};residual=[]
for i in vertices:
    x,y,z=body.data.vertices[i].co;residual.append(abs(abs(x)-float(co@[1,y,z])))
n=np.array([[abs(f.normal.x),f.normal.y,f.normal.z] for f in faces]);area=np.array([f.area for f in faces]);mean=(n*area[:,None]).sum(0);mean/=np.linalg.norm(mean)
angles=np.degrees(np.arccos(np.clip(n@mean,-1,1)))
dg=bpy.context.evaluated_depsgraph_get();tree=BVHTree.FromObject(body,dg);pairs={}
for name in ['Undercarriage','FrontOpeningJambs','SillRail_L','SillRail_R']:
    ob=bpy.data.objects.get(name)
    pairs[name]=len(tree.overlap(BVHTree.FromObject(ob,dg))) if ob else None
report={'side_glass':{'faces':len(faces),'vertices':len(vertices),
 'maximum_plane_residual_mm':max(residual,default=0)*1000,
 'maximum_face_normal_angle_from_mean_degrees':float(angles.max()),
 'p90_face_normal_angle_degrees':float(np.quantile(angles,.9))},
 'raw_bvh_contact_pairs':pairs,
 'contact_count_limit':'Raw BVH pairs include legitimate shared-edge contacts and do not measure penetration depth. Actual low-angle runtime remains the final seam evidence.',
 'removed_interfaces':{n:dict(bpy.data.objects[n].items()) for n in ['BodyShell','Undercarriage']},
 'baseline_f45_raw_pairs':{'Undercarriage':1941,'SillRail_L':222,'SillRail_R':222,'FrontOpeningJambs':226}}
(ROOT/'fit/surface-ownership-v4.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
